"""
state.py

Story state & state changes.
"""

import json

from packable import pack, unpack

class StateChange:
  """
  A StateChange represents an update to the story state. It comes with a target
  which specifies what part of the state to update and a value, which is used
  in different ways depending on the specific kind of StateChange (see the
  various subclasses).
  """
  def __init__(self, key, value=None):
    self.keys = key.split(".")

    for i in range(len(self.keys)):
      try:
        self.keys[i] = int(self.keys[i])
      except:
        pass

    self.value = value

  def __str__(self):
    return "{} {} {}".format(type(self).__name__, self.key, self.value)

  def __hash__(self):
    return (
      hash(self.keys) * 17
    + hash(self.value)
  ) * 31

  def __eq__(self, other):
    if not isinstance(other, self.__class__):
      return False
    if self.keys != other.keys:
      return False
    if self.value != other.value:
      return False
    return True

  def _diff_(self, other):
    if self.keys != other.keys:
      return [ "keys ('{}' =/= '{}')".format(self.keys, other.keys) ]
    if self.value != other.value:
      return [ "values ('{}' =/= '{}')".format(self.value, other.value) ]
    return []

  def _pack_(self):
    """
    Returns a simplified object (see packable.py).

    TODO: Examples here?
    """
    raise NotImplementedError("StateChange is an abstract class.")

  def _unpack_(obj):
    """
    Delegates unpacking to the relevant subclass.
    """
    action = obj.split(' ')[0]
    if action == "set":
      return unpack(obj, SetValue)
    elif action == "add":
      return unpack(obj, IncrementValue)
    elif action == "invert":
      return unpack(obj, InvertValue)

  def find_target(self, state, create=False):
    """
    Returns a target, key pair within the given state object for direct item
    assignment. If 'create' is given as True, missing keys will be inserted as
    empty dictionaries instead of raising an IndexError.
    """

    target = state
    sofar = ""
    for key in self.keys[:-1]:
      if key not in target:
        if create:
          target[key] = {}
        else:
          raise IndexError(
            "Invalid state key '{}' (failed after '{}')".format(
              '.'.join(self.keys),
              sofar
            )
          )
      target = target[key]
      sofar += "." + key

    if self.keys[-1] not in target and not create:
      raise IndexError(
        "Invalid state key '{}' (failed after '{}')".format(
          '.'.join(self.keys),
          sofar
        )
      )

    return target, self.keys[-1]


  def apply(self, state):
    """
    Implemented by sub-classes, this method carries out the actual change
    specified.
    """
    raise NotImplementedError("StateChange is an abstract class.")

class SetValue(StateChange):
  """
  A SetValue change sets a value, erasing any previous value. Unlike other
  changes, SetValue changes can create new keys.
  """
  def apply(self, state):
    target, key = self.find_target(self, state, create=True)
    target[key] = self.value

  def _pack_(self):
    return "set {} {}".format(
      '.'.join(self.keys),
      json.dumps(pack(self.value), indent=None)
    )

  def _unpack_(obj):
    bits = obj.split(' ')
    if bits[0] != "set":
      raise ValueError("Can't unpack '{}' as a SetValue change.".format(obj))
    return SetValue(bits[1], unpack(json.loads(' '.join(bits[2:]))))

class IncrementValue(StateChange):
  """
  An IncrementValue change adds to the given numeric value.
  """
  def apply(self, state):
    target, key = self.find_target(self, state)
    if not isinstance(key, (int, float, complex)):
      raise TypeError(
        "Value '{}' of type {} cannot be incremented.".format(
          '.'.join(self.keys),
          type(target[key])
        )
      )
    target[key] += self.value

  def _pack_(self):
    return "add {} {}".format('.'.join(self.keys), str(self.value))

  def _unpack_(obj):
    bits = obj.split(' ')
    if bits[0] != "add":
      raise ValueError(
        "Can't unpack '{}' as an IncrementValue change.".format(obj)
      )
    nv = None
    try:
      nv = int(bits[2])
    except:
      nv = float(bits[2])
    return IncrementValue(bits[1], nv)

class InvertValue(StateChange):
  """
  An InvertValue change inverts a boolean or numeric value. The value component
  of the change is ignored.
  """
  def apply(self, state):
    target, key = self.find_target(self, state)
    v = target[key]
    if isinstance(v, bool):
      target[key] = not v
    elif isinstance(v, (int, float, complex)):
      target[key] = -v
    else:
      raise TypeError(
        "Value '{}' of type {} cannot be inverted.".format(
          '.'.join(self.keys),
          type(v)
        )
      )

  def _pack_(self):
    return "invert {}".format('.'.join(self.keys))

  def _unpack_(obj):
    bits = obj.split(' ')
    if bits[0] != "invert":
      raise ValueError(
        "Can't unpack '{}' as an InvertValue change.".format(obj)
      )
    return InvertValue(bits[1])
