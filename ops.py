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
  '~': 200,
  '~~': 200,
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

def op(op, *types):
  """
  Decorator for functions that implements the given operator between the given
  types. Resolution order follows definition order.
  """
  def decorate(f):
    global ALL_OPS
    if op not in ALL_OPS:
      ALL_OPS[op] = []
    ALL_OPS[op].append(tuple(types) + (f,))
    return f
  return decorate

def resolve_op(op, *types):
  """
  Returns the appropriate function for doing operation op on the given types.
  """
  if op not in ALL_OPS:
    raise ValueError("Unknown operation '{}'".format(op))

  candidates = ALL_OPS[op]
  for c in candidates:
    if len(c) != len(args)+1:
      continue
    if all(
      (
        c[i] == '*'
     or (isinstance(c[i], tuple) and types[i] in c[i])
     or types[i] == c[i]
      )
        for i in range(len(types))
    ):
      return c[-1]

  raise ValueError("No match for operator '{}' on types {}".format(op, types))

def op_result(op, state, *args):
  """
  Returns the result (using resolve_op) of an operation between one or more
  (type, value) pairs.
  """
  types = [ a[0] for a in args ]
  f = resolve_op(op, types)
  return f(state, *args)

def is_true(typ, val):
  """
  Truth-value assignment (just copies Python).
  """
  return bool(val)

def is_numeric(typ):
  return typ in ("int", "float")

# Unary operators
# ---------------

@op('not', "*")
def u_not(state, val):
  t, v = val
  return ("boolean", not is_true(v)), state

@op('+', "*")
def u_plus(state, val):
  t, v = val
  # unary-plus is a no-op
  return (t, v), state

@op('-', ("int", "float"))
def u_minus(state, val):
  t, v = val
  return (t, -v), state

@op('~', "int")
def u_flip(state, val):
  t, v = val
  return (t, ~v), state

# Math operators
# --------------

@op('+', ("int", "float"), ("int", "float"))
def plus_nn(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("float" if "float" in (t1, t2) else "int", v1 + v2), state

@op('-', ("int", "float"), ("int", "float"))
def minus_nn(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("float" if "float" in (t1, t2) else "int", v1 - v2), state

@op('*', ("int", "float"), ("int", "float"))
def times_nn(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("float" if "float" in (t1, t2) else "int", v1 * v2), state

@op('/', ("int", "float"), ("int", "float"))
def div_nn(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  rv = v1 / v2
  if "float" in (t1, t2) or (rv != int(rv)):
    rt = "float"
  else:
    rt = "int"
  return (rt, rv), state

@op('//', ("int", "float"), ("int", "float"))
def div_nn(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("int", int(v1 // v2)), state

@op('**', ("int", "float"), ("int", "float"))
def pow_nn(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("float" if "float" in (t1, t2) or v2 < 0 else "int", v1 ** v2), state

@op('%', ("int", "float"), ("int", "float"))
def mod_nn(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("float" if "float" in (t1, t2) else "int", v1 % v2), state

# Comparisons
# -----------

@op('=', '*', '*')
def eq(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("boolean", t1 == t2 and v1 == v2)

@op('!=', '*', '*')
def neq(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("boolean", t1 != t2 or v1 != v2)

@op('<', '*', '*')
def less(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  if t1 == t2 or (is_numeric(t1) and is_numeric(t2)):
    try:
      return ("boolean", v1 < v2)
    except TypeError:
      return False
  else:
    # TODO: Use string comparison here?
    return False

@op('>', '*', '*')
def greater(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  if t1 == t2 or (is_numeric(t1) and is_numeric(t2)):
    try:
      return ("boolean", v1 > v2)
    except TypeError:
      return False
  else:
    # TODO: Use string comparison here?
    return False

@op('<=', '*', '*')
def leq(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  if t1 == t2 or (is_numeric(t1) and is_numeric(t2)):
    try:
      return ("boolean", v1 <= v2)
    except TypeError:
      return False
  else:
    # TODO: Use string comparison here?
    return False

@op('>=', '*', '*')
def geq(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  if t1 == t2 or (is_numeric(t1) and is_numeric(t2)):
    try:
      return ("boolean", v1 >= v2)
    except TypeError:
      return False
  else:
    # TODO: Use string comparison here?
    return False

# Note: boolean operators are handled in macro.py because they're
# short-circuiting.

# Bitwise operators
# -----------------

@op('&', "int", "int")
def bit_and(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("int", v1 & v2), state

@op('|', "int", "int")
def bit_and(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("int", v1 | v2), state

@op('^', "int", "int")
def bit_and(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("int", v1 ^ v2), state

# '~' is defined above with the other unary operators

# String operators
# ----------------

@op('+', "string", "string")
def plus_str(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("string", v1 + v2), state

@op('-', "string", "string")
def minus_str(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("string", v1.replace(v2, "")), state

@op('*', "string", "int")
def times_str(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("string", v1 * v2), state

@op('/', "string", "string")
def search_str(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("boolean", re.search(v2, v1) != None), state

@op('//', "string", "string")
def search_simple_str(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("boolean", v2 in v1), state

@op('~', "string", "string", "string")
def replace_str(state, lhs, rhs, rrhs):
  t1, v1 = lhs
  t2, v2 = rhs
  t3, v3 = rrhs
  return ("string", re.sub(v2, v3, v1)), state

@op('~~', "string", "string", "string")
def replace_simple_str(state, lhs, rhs, rrhs):
  t1, v1 = lhs
  t2, v2 = rhs
  t3, v3 = rrhs
  return ("string", v1.replace(v2, v3)), state

@op('^', "string", "string")
def split_str(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("string", re.split(v2, v1)), state

@op('^^', "string", "string")
def split_str(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("string", v1.split(v2)), state

# List operators
# --------------

@op('+', "list", "list")
def cat_lst(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("list", v1 + v2), state

@op('.', "list", "*")
def app_lst(state, lhs, rhs):
  _, lst = lhs
  return ("list", lst[:] + [ rhs ]), state

@op('*', "list", "int")
def times_lst(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  result = []
  for i in range(v2):
    for v in v1:
      result.append(v)
  return ("list", result), state

@op('/', "list", "*")
def search_lst(state, lhs, rhs):
  _, lst = lhs
  return ("boolean", rhs in lst), state

@op('~', "list", "*", "*")
def replace_lst(state, lhs, find, repl):
  _, lst = lhs
  result = []
  for val in lst:
    if val == find:
      result.append(repl)
    else:
      result.append(val)
  return ("list", result), state

@op('|', "list", "op", "*")
def reduce_lst(state, lhs, rhs, rrhs):
  _, lst = lhs
  _, op = rhs
  typ, val = rrhs
  # Special defaults for zero-length list:
  if len(lst) == 0:
    if typ == "int":
      return ("int", 0), state
    elif typ == "float":
      return ("float", 0), state
    elif typ == "string":
      return ("string", ""), state
    elif typ == "list":
      return ("list", []), state
    elif typ == "dict":
      return ("dict", {}), state

  result = lst[0]
  for lv in lst[1:]:
    result, state = op_result(op, state, result, (typ, val))
    result, state = op_result(op, state, result, lv)

  return result, state

# '!' mapping is handled elsewhere because the call needs special evaluation

# Dictionary operators
# --------------------

@op('+', "dict", "dict")
def union_dict(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  result = {}
  result.update(v1)
  result.update(v2)
  return ("dict", result), state

@op('|', "dict", "dict")
def rev_union_dict(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  result = {}
  result.update(v2)
  result.update(v1)
  return ("dict", result), state

@op('&', "dict", "dict")
def intersect_dict(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  result = {}
  for k in v1:
    if k in v2:
      result[k] = v2[k]
  return ("dict", result), state

@op('-', "dict", "dict")
def sub_dict(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  result = {}
  for k in v1:
    if k not in v2:
      result[k] = v1[k]
  return ("dict", result), state

@op('.', "dict", "*", "*")
def ins_dict(state, lhs, key, val):
  _, dct = lhs
  result = {}
  result.update(dct)
  result[key] = val
  return ("dict", result), state

# Default string operators
# ------------------------

@op('+', "string", "*")
def plus_str_default(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("string", v1 + str(v2)), state

@op('+', "*", "string")
def plus_default_str(state, lhs, rhs):
  t1, v1 = lhs
  t2, v2 = rhs
  return ("string", str(v1) + v2), state
