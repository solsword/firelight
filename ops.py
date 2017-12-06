"""
ops.py

Operator definitions for firelight macros.
"""

OPERATOR_PRECEDENCE = {
  '[': 10000,
  '.': 50,
  '%': 20,
  '+': 50,
  '-': 50,
  '*': 100,
  '**': 200,
  '%': 200,
  '%%': 200,
  '|': 200,
  '&': 200,
  '^': 200,
  '^^': 200,
  '/': 200,
  '//': 200,
  '=': 10,
  '<': 10,
  '>': 10,
  '<=': 10,
  '>=': 10,
  '!=': 10,
  '!': 1000,
  'and': 5,
  'or': 5,
  'not': 5,
}

ALL_OPS = {}

class OpError(Exception):
  """
  An OpError indicates a problem with an operator.
  """
  pass

class Operator:
  """
  A class representing an operator.
  """
  def __init__(self, op):
    self.op = op

def op(op, *types):
  """
  Decorator for functions that implement the given operator between the given
  types. Resolution order follows definition order.
  """
  def decorate(f):
    global ALL_OPS
    if op not in ALL_OPS:
      ALL_OPS[op] = []
    ALL_OPS[op].append(tuple(types) + (f,))
    return f
  return decorate

def resolve_op(op, *args):
  """
  Returns the appropriate function for doing operation op on the given types.
  """
  if op not in ALL_OPS:
    raise OpError("Unknown operation '{}'".format(op))

  candidates = ALL_OPS[op]
  for c in candidates:
    if len(c) != len(args)+1:
      continue
    if all(
      (c[i] == '*' or isinstance(args[i], c[i]))
        for i in range(len(args))
    ):
      return c[-1]

  raise OpError(
    "No match for operator '{}' on types {}".format(
      op,
      [ type(a) for a in args ]
    )
  )

def op_result(op, state, *args):
  """
  Returns the result (using resolve_op) of an operation between one or more
  (type, value) pairs.
  """
  f = resolve_op(op, *args)
  return f(state, *args)

def is_true(val):
  """
  Truth-value assignment (just copies Python).
  """
  return bool(val)

def is_numeric(typ):
  return typ in (int, float)

# Unary operators
# ---------------

@op('not', "*")
def u_not(state, val):
  return ("boolean", not is_true(val)), state

@op('+', "*")
def u_plus(state, val):
  # unary-plus is a no-op
  return val, state

@op('-', (int, float))
def u_minus(state, val):
  return -val, state

# TODO: What about this?!?
#@op('%', int)
#def u_flip(state, val):
#  return ~val, state

# Math operators
# --------------

@op('+', (int, float), (int, float))
def plus_nn(state, lhs, rhs):
  if float in (type(lhs), type(rhs)):
    return float(lhs + rhs), state
  else:
    return int(lhs + rhs), state

@op('-', (int, float), (int, float))
def minus_nn(state, lhs, rhs):
  if float in (type(lhs), type(rhs)):
    return float(lhs - rhs), state
  else:
    return int(lhs - rhs), state

@op('*', (int, float), (int, float))
def times_nn(state, lhs, rhs):
  if float in (type(lhs), type(rhs)):
    return float(lhs * rhs), state
  else:
    return int(lhs * rhs), state

@op('/', (int, float), (int, float))
def div_nn(state, lhs, rhs):
  rv = lhs / rhs
  if float in (type(lhs), type(rhs)) or (rv != int(rv)):
    rt = float
  else:
    rt = int
  return rt(rv), state

@op('//', (int, float), (int, float))
def div_nn(state, lhs, rhs):
  return ("int", int(lhs // rhs)), state

@op('**', (int, float), (int, float))
def pow_nn(state, lhs, rhs):
  if float in (type(lhs), type(rhs)) or rhs < 0:
    return float(lhs ** rhs), state
  else:
    return int(lhs ** rhs), state

@op('%', (int, float), (int, float))
def mod_nn(state, lhs, rhs):
  if float in (type(lhs), type(rhs)):
    return float(lhs % rhs), state
  else:
    return int(lhs % rhs), state

# Comparisons
# -----------

@op('=', '*', '*')
def eq(state, lhs, rhs):
  return lhs == rhs, state

@op('!=', '*', '*')
def neq(state, lhs, rhs):
  return lhs != rhs, state

@op('<', '*', '*')
def less(state, lhs, rhs):
  if (
    isinstance(lhs, type(rhs))
 or isinstance(rhs, type(lhs))
 or (is_numeric(type(lhs)) and is_numeric(type(rhs)))
  ):
    try:
      return lhs < rhs, state
    except TypeError:
      return False, state
  else:
    # TODO: Use string comparison here?
    return False, state

@op('>', '*', '*')
def greater(state, lhs, rhs):
  if (
    isinstance(lhs, type(rhs))
 or isinstance(rhs, type(lhs))
 or (is_numeric(type(lhs)) and is_numeric(type(rhs)))
  ):
    try:
      return lhs > rhs, state
    except TypeError:
      return False, state
  else:
    # TODO: Use string comparison here?
    return False, state

@op('<=', '*', '*')
def leq(state, lhs, rhs):
  if (
    isinstance(lhs, type(rhs))
 or isinstance(rhs, type(lhs))
 or (is_numeric(type(lhs)) and is_numeric(type(rhs)))
  ):
    try:
      return lhs <= rhs, state
    except TypeError:
      return False, state
  else:
    # TODO: Use string comparison here?
    return False, state

@op('>=', '*', '*')
def geq(state, lhs, rhs):
  if (
    isinstance(lhs, type(rhs))
 or isinstance(rhs, type(lhs))
 or (is_numeric(type(lhs)) and is_numeric(type(rhs)))
  ):
    try:
      return lhs >= rhs, state
    except TypeError:
      return False, state
  else:
    # TODO: Use string comparison here?
    return False, state

# Note: boolean operators are handled in macro.py because they're
# short-circuiting.

# Bitwise operators
# -----------------

@op('&', int, int)
def bit_and(state, lhs, rhs):
  return lhs & rhs, state

@op('|', int, int)
def bit_and(state, lhs, rhs):
  return lhs | rhs, state

@op('^', int, int)
def bit_and(state, lhs, rhs):
  return lhs ^ rhs, state

# String operators
# ----------------

@op('+', str, str)
def plus_str(state, lhs, rhs):
  return lhs + rhs, state

@op('-', str, str)
def minus_str(state, lhs, rhs):
  return lhs.replace(rhs, ""), state

@op('*', str, int)
def times_str(state, lhs, rhs):
  return lhs * rhs, state

@op('/', str, str)
def search_str(state, lhs, rhs):
  return re.search(rhs, lhs) != None, state

@op('//', str, str)
def search_simple_str(state, lhs, rhs):
  return rhs in lhs, state

@op('%', str, str, str)
def replace_str(state, lhs, rhs, rrhs):
  return re.sub(rhs, rrhs, lhs), state

@op('%%', str, str, str)
def replace_simple_str(state, lhs, rhs, rrhs):
  return lhs.replace(rhs, rrhs), state

@op('^', str, str)
def split_str(state, lhs, rhs):
  return re.split(rhs, lhs), state

@op('^^', str, str)
def split_str(state, lhs, rhs):
  return lhs.split(rhs), state

# List operators
# --------------

@op('+', list, list)
def cat_lst(state, lhs, rhs):
  return lhs + rhs, state

@op('.', list, "*")
def app_lst(state, lhs, rhs):
  return ("list", lhs[:] + [ rhs ]), state

@op('*', list, int)
def times_lst(state, lhs, rhs):
  result = []
  for i in range(rhs):
    for v in lhs:
      result.append(v)
  return result, state

@op('/', list, "*")
def search_lst(state, lhs, rhs):
  return rhs in lhs, state

@op('%', list, "*", "*")
def replace_lst(state, lhs, find, repl):
  result = []
  for val in lhs:
    if val == find:
      result.append(repl)
    else:
      result.append(val)
  return result, state

@op('|', list, Operator, "*")
def reduce_lst(state, lst, op, val):
  # Special defaults for zero-length list:
  if len(lst) == 0:
    if isinstance(val, int):
      return 0, state
    elif isinstance(val, float):
      return 0.0, state
    elif isinstance(val, str):
      return "", state
    elif isinstance(val, list):
      return [], state
    elif isinstance(val, dict):
      return {}, state
    else:
      return None, state

  result = lst[0]
  for lv in lst[1:]:
    result, state = op_result(op, state, result, val)
    result, state = op_result(op, state, result, lv)

  return result, state

# '!' mapping is handled elsewhere because the call needs special evaluation

# Dictionary operators
# --------------------

@op('+', dict, dict)
def union_dict(state, lhs, rhs):
  result = {}
  result.update(lhs)
  result.update(rhs)
  return result, state

@op('|', dict, dict)
def rev_union_dict(state, lhs, rhs):
  result = {}
  result.update(rhs)
  result.update(lhs)
  return result, state

@op('&', dict, dict)
def intersect_dict(state, lhs, rhs):
  result = {}
  for k in lhs:
    if k in rhs:
      result[k] = rhs[k]
  return result, state

@op('-', dict, dict)
def sub_dict(state, lhs, rhs):
  result = {}
  for k in lhs:
    if k not in rhs:
      result[k] = lhs[k]
  return result, state

@op('.', dict, "*", "*")
def ins_dict(state, lhs, key, val):
  result = {}
  result.update(lhs)
  result[key] = val
  return result, state

# Default string operators
# ------------------------

@op('+', str, "*")
def plus_str_default(state, lhs, rhs):
  return lhs + str(rhs), state

@op('+', "*", str)
def plus_default_str(state, lhs, rhs):
  return str(lhs) + rhs, state
