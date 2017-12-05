"""
utils.py

Various utility functions.
"""

import re

def or_strlist(alternatives):
  """
  Returns a string listing out alternatives, using commas naturally depending
  on the number of alternatives given. Returns an empty string if given an
  empty list.
  """
  if len(alternatives) == 0:
    return ""
  elif len(alternatives) == 1:
    return alternatives[0]
  elif len(alternatives) == 2:
    return alternatives[0] + " or " + alternatives[1]
  else:
    return ", ".join(alternatives[:-1]) + ", or " + alternatives[-1]

def dedent(string, ts=4):
  """
  Removes common leading whitespace from the given string. Each tab counts as
  the given number of spaces.
  """
  lines = string.split("\n")
  common = None
  for l in lines:
    here = 0
    if not l.strip(): # ignore blank lines
      continue
    for c in l:
      if c not in " \t":
        break
      elif c == " ":
        here += 1
      elif c == "\t":
        here += ts

    if common == None or here < common:
      common = here

  if not common:
    return string

  result = None
  for l in lines:
    if not l.strip():
      rest = ""
    else:
      removed = 0
      rest = l
      while removed < common and rest:
        c, rest = rest[0], rest[1:]
        if c == " ":
          removed += 1
        elif c == "\t":
          removed += ts
        else:
          raise RuntimeWarning(
            "Lost count while removing indentation from:\n'''\n{}\n'''".format(
              string.replace(' ', '␣').replace('\t', '␉').replace('\r', '␍')
            )
          )
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

  Returns the index of the matching brace found.

  Examples:
    ```>
    matching_brace("(()())", 0) == 5
    ```>
    matching_brace("(())", 0) == 3
    ```>
    matching_brace("(())", 1) == 2
    ```>
    matching_brace("()()", 0) == 1
    ```>
    matching_brace("()()", 2) == 3
    ```>
    matching_brace("(()())", 0) == 5
    ```x
    matching_brace("((())", 0)
    ```!
    UnmatchedError
    ```
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
  # must hit return in loop or else
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

  Example:
    ```?
    string_literal(r'"two,\\"three\\""', 0)
    ```=
    (14, "two,\\"three\\"")
    ```
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

def split_unquoted(src, delim=',', qc='"'):
  """
  Splits the entire src string into items delimited by the given delimiter
  (which is interpreted as a regular expression in MULTILINE mode), ignoring
  delimiters that occur within quoted strings surrounded by the given quote
  character (see string_literal above). When the entire content of a delimited
  area is quoted, the string literal's value is used instead of the raw
  characters as the value of that item. Delimited areas are stripped of leading
  and trailing whitespace.

  Example:
    ```?
    split_unquoted(r'one, "two,three", four "five"', delim=',', qc='"')
    ```=
    ["one", "two,three", 'four "five"']
    ```
  """
  escaped = False
  result = []
  d = re.compile(delim, re.MULTILINE)

  # First, find all quoted regions:
  quoted_regions = {}
  i = -1
  while i < len(src):
    i += 1
    c = src[i]
    if c == qc:
      ei, qcont = string_literal(src, i, qc=qc)
      quoted_regions[(i, ei)] = qcont
      i = ei + 1 # skip ahead

  # Next, look for delimiters:
  delimiters = []
  i = -1
  while i < len(src):
    i += 1
    match = d.search(src, pos=i)
    if match:
      mp = match.start()
      is_quoted = False
      for qr in quoted_regions:
        if qr[0] < mp < qr[1]: # was quoted; skip to end of quote
          i = qr[1]
          is_quoted = True
          break

      if is_quoted:
        continue

      delimiters.append(match)
      i = match.end() # skip to end of match

    else:
      # done
      i = len(src)

  i = 0
  bits = []
  while i < len(src) and delimiters:
    ed = delimiters.pop(0)
    bits.append(src[i:ed.start()])
    i = ed.end()
  bits.append(src[i:])

  # Strip fields and replace with literal contents when entire stripped field
  # is one string literal.
  simplified = []
  for b in bits:
    sb = b.strip()
    if sb[0] == qc:
      try:
        ei, sl = string_literal(sb, 0, qc=qc)
        if ei == len(sb) - 1:
          sb = sl
      except UnmatchedError:
        pass

    simplified.append(sb)

  return simplified
