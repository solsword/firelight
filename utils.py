"""
utils.py

Various utility functions.
"""

def dedent(string, ts=4):
  """
  Removes common leading whitespace from the given string. Each tab counts as
  the given number of spaces.
  """
  lines = string.split("\n")
  common = None
  for l in lines:
    here = 0
    for c in l:
      if c not in " \t":
        break
      elif c == " ":
        here += 1
      elif c == "\t":
        here += ts

    if here > 0 and (common == None or here < common):
      common = here

  if not common:
    return string

  result = None
  for l in lines:
    removed = 0
    rest = l
    while removed < common and rest:
      c, rest = rest[0], rest[1:]
      if c == " ":
        removed += 1
      elif c == " ":
        removed += 4
      else:
        raise RuntimeWarning("Lost count while removing indentation.")
        break

    if result == None:
      result = rest
    else:
      result += "\n" + rest

  return result


class UnmatchedError(Exception):
  """
  Exception for the case in matching_brace where no matching brace exists in
  the given string.
  """
  pass

def matching_brace(src, idx, op='(', cl=')'):
  """
  Finds the matching closing brace starting from the given index in the given
  string (the given index is assumed to be an open brace; this assumption is
  not checked). The opening and closing brace characters may be specified using
  the 'op' and 'cl' parameters, which default to '(' and ')'. Nested braces of
  the same type and strings quoted using double quotes are ignored.
  """
  layer = 0
  quoted = False
  escaped = False
  for i in range(idx+1, len(src)):
    c = src[i]
    if c == '\\':
      escaped = not escaped
    elif escaped:
      escaped = False
    elif c == '"':
      quoted = not quoted
    elif quoted:
      pass
    elif c == cl:
      if layer < 0:
        raise RuntimeError("Braces balance became negative?!?")
      elif layer == 0:
        return i
      else:
        layer -= 1
    elif c == op:
      layer += 1
    else:
      raise UnmatchedError(
        "Unmatched '{}' at position {} in string:\n'''\n{}\n'''".format(
          op,
          idx,
          src if len(src) < 800 else (
            "...\n" + src[:800] + "\n..."
              if idx < 80 else src[max(0, idx-80):idx+720] + "\n..."
          )
        )
      )

def string_literal(src, idx, qc='"'):
  """
  Finds the matching end quote starting from the given index in the given
  string (the given index is assumed to be a quote; this assumption is not
  checked). The quote character may be specified using the 'qc' parameter,
  which defaults to '"'. Nested quotes of the same type are allowed if escaped
  with a backslash, and backslashes themselves may be escaped; the list of
  escape codes is:

      '\\<quote character>' -> literal quote character
      '\\\\' -> literal backslash
      '\\n' -> newline
      '\\r' -> carriage return
      '\\t' -> horizontal tab

  Invalid escape codes, such as '\\z', will result in a literal backslash along
  with the given letter in the output. Returns a pair containing the end index
  of the found string and the string content.
  """
  escaped = False
  result = ""
  for i in range(idx+1, len(src)):
    c = src[i]
    if escaped:
      escaped = False
      if c == qc:
        result += qc
      elif c == '\\':
        result += '\\'
      elif c == 'n':
        result += '\n'
      elif c == 'r':
        result += '\r'
      elif c == 't':
        result += '\t'
      else: # unrecognized escape code
        result += '\\' + c
    elif c == '\\':
      escaped = True
    elif c == qc:
      return (i, result)
    else:
      result += c
  # need to hit return inside of loop, otherwise we've run out of source
  # material without finding a matching quote.
  raise UnmatchedError(
    "Unmatched '{}' at position {} in string:\n'''\n{}\n'''".format(
      qc,
      idx,
      src if len(src) < 800 else (
        "...\n" + src[:800] + "\n..."
          if idx < 80 else src[max(0, idx-80):idx+720] + "\n..."
      )
    )
  )
