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
