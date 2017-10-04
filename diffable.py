"""
diffable.py

Support for objects that can report their differences.
"""

def diff(a, b):
  """
  Returns a list of strings describing differences between objects 'a' and 'b'.
  If types are compatible (one is a subtype of the other) and either has a
  _diff_ method, the _diff_ method of the subtype will be called (or the diff
  method of 'a' if they're the same type, or 'b' if they're the same type but
  'a' doesn't have a _diff_ method).

  If there are no differences, returns an empty list.
  """
  if a == b:
    return []
  elif isinstance(a, type(b)) or isinstance(b, type(a)):
    if type(a) == type(b) and hasattr(a, "_diff_") or hasattr(b, "_diff"):
      if hasattr(a, "_diff_"):
        return a._diff_(b)
      elif hasattr(b, "_diff_"):
        return [ "~ {}".format(d) for d in b._diff_(a) ]
    elif isinstance(a, type(b)) and hasattr(a, "_diff_"):
      return a._diff_(b)
    elif isinstance(b, type(a)) and hasattr(b, "_diff_"):
      return [ "~ {}".format(d) for d in b._diff_(a) ]
    elif hasattr(a, "_diff_"):
      return a._diff_(b)
    elif hasattr(b, "_diff_"):
      return [ "~ {}".format(d) for d in b._diff_(a) ]
    else: # no _diff_ methods
      differences = []
      if isinstance(a, (list, tuple)):
        if len(a) != len(b):
          differences.append("lengths: {} != {}".format(len(a), len(b)))
        for i in range(min(len(a), len(b))):
          dl = diff(a[i], b[i])
          if dl:
            differences.extend("at [{}]: {}".format(i, d) for d in dl)
      elif isinstance(a, dict):
        for k in a:
          if k not in b:
            differences.append("extra key in A: '{}'".format(k))
          else:
            dl = diff(a[k], b[k])
            if dl:
              differences.extend("at [{}]: {}".format(k, d) for d in dl)
        for k in b:
          if k not in a:
            differences.append("extra key in B: '{}'".format(k))
      elif isinstance(a, (int, float, complex, str, bool)):
        return [ "values: {} != {}".format(a, b) ]
      else:
        return [ "unknown" ]

      return differences or [ "unknown" ]

    return "two"
  else:
    return [ "types: {} != {}".format(type(a), type(b)) ]

  return "three"
