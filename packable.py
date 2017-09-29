"""
packable.py

Support for objects that can be packed into a simple JSONable format and
unpacked from the same.
"""

def pack(obj):
  """
  Takes an object and packs it into a JSONable form consisting purely of
  dictionaries, lists, numbers, strings, booleans, and Nones. If the object has
  a `_pack_` method, that will be called without arguments and the result
  returned, otherwise if it's one of the above types it'll be returned directly
  (or after having its contents packed).
  """
  if hasattr(obj, "_pack_"):
    return obj._pack_()
  elif isinstance(obj, (list, tuple)):
    return [ pack(o) for o in obj ]
  elif isinstance(obj, dict):
    return {
      pack(k): pack(v)
        for (k, v) in obj.items()
    }
  elif isinstance(obj, (int, float, str, bool, type(None))):
    return obj
  else:
    raise ValueError(
      "Cannot pack value '{}' of type {}.".format(
        repr(obj),
        type(obj)
      )
    )
    return None

def unpack(obj, cls=None):
  """
  The inverse of `pack`, unpacks the given object. As type information is not
  retained during packing, unpack needs to be told what type to unpack things
  as, making the default behavior for lists and dictionaries quite a bit less
  useful. If a target class is specified, its `_unpack_` method will be used.
  """
  if hasattr(cls, "_unpack_"):
    return cls._unpack_(obj)
  elif isinstance(obj, (list, tuple)):
    return [ unpack(it) for it in obj ]
  elif isinstance(obj, dict):
    return {
      k: unpack(v)
        for (k, v) in obj.items()
    }
  elif isinstance(obj, (int, float, str, bool, type(None))):
    return obj
  else:
    raise ValueError(
      "Cannot unpack value '{}' of type {}.".format(
        repr(obj),
        type(obj)
      )
    )
    return None
