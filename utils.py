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
  the 'op' and 'cl' parameters, which default to '(' and ')'.
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
          src if len(src) < 810 else src[:810] + "\n..."
        )
      )
