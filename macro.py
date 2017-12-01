"""
macro.py

See modules/help.fls for a description of the macro system.
"""

import re
import copy
import traceback

import utils

import ops

MACRO_START = re.compile(r"([a-zA-Z_][a-zA-Z_0-9.]+):")

INT_CONSTANT = re.compile(r"([+-])?(0[xo])?([0-9A-Fa-f])+")

FLOAT_CONSTANT = re.compile(r"([+-])?([0-9]+)(\.[0-9]*)?([eE][+-]?[0-9]+)?")

BUILTINS = {}

def mb(f):
  """
  Decorator for registering builtins.
  """
  global BUILTINS
  fn = f.__name__
  if fn.endswith('_'):
    fn = fn[:-1]
  BUILTINS[fn] = f
  return f

def to_string(value):
  """
  TODO: Something more complicated here?
  """
  return str(value)

def lex_expr(expr):
  """
  Lexes an expression into syntax units.
  """
  i = -1
  sval = None
  units = []
  while i < len(expr)-1:
    i += 1
    c = expr[i]

    # Check for end-of-word with accumulated string value:
    if c in "()[]+-%&|./*~^=<>!\"'" and sval != None:
      units.append(("word", sval))
      sval = None

    if c in ' \n\r\t': # (separate if statement)
      if sval:
        units.append(("word", sval))
        sval = None
    elif c == '(':
      m = MACRO_START.search(expr, i)
      start = m.start()
      if start == i:
        end = utils.matching_brace(expr, i, '(', ')')
        units.append(("call", expr[start:end+1]))
        i = end
      else:
        units.append("group", "open")
    elif c == ')':
      units.append("group", "close")
    elif c == '[':
      units.append("index", "open")
    elif c == ']':
      units.append("index", "close")
    elif c in "+-%&|.":
      units.append(("op", c))
    elif c in "/*~^":
      if expr[i+1] == c:
        units.append(("op", c+c))
        i += 1
      else:
        units.append(("op", c))
    elif c == '=':
      if expr[i+1] == c: # allow '==' with same meaning as '='
        i += 1
      units.append(("op", c))
    elif c in '<>!':
      if expr[i+1] == '=':
        units.append(("op", expr[i:i+2]))
        i += 1
      else:
        units.append(("op", c))
    elif c == 'a' and expr[i:i+3] == 'and':
      if sval != None:
        sval += "and"
      else:
        units.append(("op", "and"))
      i += 2
    elif c == 'o' and expr[i:i+2] == 'or':
      if sval != None:
        sval += "or"
      else:
        units.append(("op", "or"))
      i += 1
    elif c == 'n' and expr[i:i+3] == 'not':
      if sval != None:
        sval += "not"
      else:
        units.append(("op", "not"))
      i += 2
    elif c in "0123456789":
      if sval != None:
        sval += c
      else:
        m = INT_CONSTANT.match(expr, i)
        if m:
          try:
            if m.group(2) == "0x":
              it = int(m.group(0), 16)
            elif m.group(2) == "0o":
              it = int(m.group(0), 8)
            else:
              it = int(m.group(0), 10)
            i = m.end()
            units.append(("int", it))
            continue
          except ValueError:
            pass
        m = FLOAT_CONSTANT.match(expr, i)
        if m:
          try:
            f = float(m.group(0))
            i = m.end()
            units.append(("float", f))
            continue
          except ValueError:
            pass
        # Not recognized as a number: treat as a string.
        if sval is None:
          sval = c
        else:
          sval += c
    elif c in "\"'":
      ei, qc = utils.string_literal(expr, i, qc=c)
      units.append(("string", qc))
      i = ei
    else: # Not a recognized operator: add to string
      # TODO: Add sval as a unit somewhere?
      if sval is None:
        sval = c
      else:
        sval += c

  if sval:
    units.append(("word", sval))
    sval = None

  # After the dust settles:
  return units

class ParseError(Exception):
  """
  A ParseError indicates a problem that occurs when parsing an expression.
  """
  pass

def parse_next_val(units):
  """
  Parses the next value from the given units. Returns a (parse-tree, leftovers)
  pair.
  """
  ut, uv = units[0]
  if ut == "word":
    if uv == "True":
      return ("boolean", True), units[1:]
    elif uv == "False":
      return ("boolean", False), units[1:]
    elif uv == "None":
      return ("none", None), units[1:]
    else:
      return ("variable_lookup", uv), units[1:]
  elif ut == "group":
    subunits = []
    level = 0
    for i in range(1, len(units)):
      sut, suv = units[i]
      if sut == "group":
        if suv == "open":
          level += 1
          subunits.append((sut, suv))
        elif suv == "close":
          level -= 1
          if level < 0:
            break
          else:
            subunits.append((sut, suv))
        else:
          raise RuntimeError("Invalid lex unit 'group' value '{}'.".format(suv))
      else:
        subunits.append((sut, suv))
    if level >= 0:
      raise ParseError("Unmatched '('.")
    return parse_units(subunits), units[i+1:]
  elif ut == "index":
    raise ParseError("Unexpected index (expected value).")
  elif ut == "call":
    return ("eval_macro", uv)
  elif ut == "op":
    raise ParseError("Unexpected operator (expected value).")
  elif ut in ("int", "float", "string"):
    return (ut, uv), units[1:]

def parse_next_op(units):
  """
  Parses the next operator from the units. Returns a (parse-tree, leftovers)
  pair
  """
  ut, uv = units[0]
  if ut == "word":
    raise ParseError("Unexpected variable (expected operator).")
  elif ut == "group":
    raise ParseError("Unexpected group (expected operator).")
  elif ut == "index":
    if uv == "open":
      return ("index", "["), 
    else:
      raise ParseError("Unexpected index end (expected operator).")
  elif ut == "call":
    raise ParseError("Unexpected call (expected operator).")
  elif ut == "op":
    return ("op", uv), units[1:]
  elif ut in ("int", "float", "string"):
    raise ParseError("Unexpected constant (expected operator).")

def scrub_parents(result):
  """
  Scrubs parent entries from a parse tree to make it serializable.
  """
  if "parent" in result:
    del result["parent"]
  if "args" in result:
    for arg in result["args"]:
      if isinstance(arg, dict):
        scrub_parents(arg)

  return result

def escape_upwards(result):
  """
  Escapes upward during parsing, creating a new potential binop context if
  necessary.
  """
  while result["parent"] != None and result["state"] == "complete":
    result = result["parent"]
  if result["state"] == "complete":
    result["parent"] = {
      "parent": None,
      "state": "need_op",
      "grouped": False,
      "op": None,
      "arity": None,
      "args": [result]
    }
    return result["parent"]
  else:
    return result

def rotate_operators(result, new_op):
  """
  Checks if the given new operation should result in a rotated tree due to
  operator precedence, and if so, returns the appropriately-rotated tree.
  If not, it returns None. Note that this function assumes that the operator is
  a standard binary operator, adjustments to arity and/or state for other
  operators must be made separately.
  """
  if len(result["args"]) == 0:
    return None

  target = result["args"][-1]
  top = target["op"]
  if (
    not target.get("grouped", False)
and top not in ("value", "opval")
  ):
    lpr = ops.OPERATOR_PRECEDENCE[top]
    hpr = ops.OPERATOR_PRECEDENCE[new_op]
    if hpr > lpr:
      # Need to swap structure due to operator binding:
      nr = {
        "parent": target,
        "state": "need_val",
        "grouped": False,
        "op": new_op,
        "arity": 2,
        "args": [ target["args"][-1] ]
      }
      # Note: Arity/state for special operators must be fixed separately!
      # Supplant previous RHS:
      target["args"][-1] = nr
      # Return new subtree:
      return nr

  return None

def parse_units(units, ungrouped=False):
  """
  Parses lexed macro units into an expression parse tree. Unit types (see
  lex_expr):

    word -> variable reference
    call -> macro call
    int, float, string -> constants
    group -> handled by parse_next_val/parse_next_op
    index, op -> operators

  Unless 'ungrouped' is given, the resulting parse tree is treated as a grouped
  tree (further parsing won't edit it for order-of-operations purposes).
  """
  result = {
    "parent": None,
    "state": "blank",
    "grouped": False,
    "op": None,
    "arity": None,
    "args": []
  }
  rest = units
  while rest:
    if result["state"] == "complete":
      result = escape_upwards(result)
      # and keep parsing here
    elif result["state"] == "blank":
      try:
        val, rest = parse_next_val(rest)
        result["args"].append(
          {
            "parent": result,
            "state": "complete",
            "op": "value",
            "value": val
          }
        )
        result["state"] = "need_op"
      except ParseError as e:
        (otyp, op), rest = parse_next_op(rest)
        if op in ['+', '-', '~', 'not']: # unary operators
          result["arity"] = 1
          result["op"] = op
          result["state"] = "need_val"
        else:
          raise e
    elif result["state"] == "need_val":
      backup = rest
      try:
        val, rest = parse_next_val(rest)
        result["args"].append(
          {
            "parent": result,
            "state": "complete",
            "op": "value",
            "value": val
          }
        )
        if len(result["args"]) == result["arity"]:
          result["state"] = "complete"
        # else state stays as need_val
      except ParseError as e:
        (otyp, op), rest = parse_next_op(rest)
        if op in ['+', '-', '~', 'not']: # stacked unary
          nr = {
            "parent": result,
            "state": "need_val",
            "grouped": False,
            "op": op,
            "arity": 1,
            "args": []
          }
          result["args"].append(nr)
          result = nr # shift down into lower context
        elif (
          result["op"] == '.'
      and result["arity"] == 3
      and len(result["args"]) == 2
        ):
          # revise our arity estimate and reset rest:
          result["arity"] = 2
          result["complete"] = True
          rest = backup
        else:
          raise e
    elif result["state"] == "need_op":
      (otyp, op), rest = parse_next_op(rest)
      if op == 'not': # unary operator
        raise ParseError("Expected binary operator but got '{}'.".format(op))
      elif otyp == "index": # recurse to get index parse tree
        rr = rotate_operators(result, '[')
        if rr:
          result = rr
        # else no change
        level = 0
        for i in range(1, len(rest)):
          if rest[i] == ("index", "open"):
            level += 1
          elif rest[i] == ("index", "close"):
            level -= 1
            if level < 0:
              break
        if level >= 0:
          raise ParseError("Unmatched '['.")
        result["arity"] = 2
        result["op"] = '['
        result["state"] = "complete"
        result["args"].append(parse_units(rest[1:i]))
        rest = rest[i+1:]
      else: # a binary (or possibly trinary) operator
        rr = rotate_operators(result, op)
        if rr:
          result = rr
        else:
          result["arity"] = 2
          result["op"] = op
          result["state"] = "need_val"

        # Fix arity/state for special operators:
        if op in ('~', '~~', '.'):
          result["arity"] = 3
        elif op == '|':
          result["arity"] = 3
          result["state"] = "need_opval"
        elif op == '!':
          result["state"] = "need_call"

    elif result["state"] == "need_opval":
      (otyp, op), rest = parse_next_op(rest)
      result["args"].append(
        {
          "parent": result,
          "state": "complete",
          "op": "opval",
          "value": op
        }
      )
      result["state"] = "need_val"
    elif result["state"] == "need_call":
      (vtyp, val), rest = parse_next_val(rest)
      if vtyp == "call":
        result["args"].append(
          {
            "parent": result,
            "state": "complete",
            "op": "value",
            "value": (vtyp, val)
          }
        )
        if len(result["args"]) == result["arity"]:
          result["state"] = "complete"
        else:
          result["state"] = "need_val"
      else:
        raise ParseError("Didn't find required macro call.")

  # No more leftovers

  if result["state"] == "complete":
    pass
  elif result["state"] == "need_op":
    if (
      result["parent"] != None
   or result["op"] != None
   or result["arity"] != None
    ):
      raise ParseError("Ended parsing with leftover expectations.")
  else:
    raise ParseError("Ended parsing in state '{}'.".format(result["state"]))

  result = escape_upwards(result)
  if (
    result["state"] != "need_op"
 or result["parent"] != None
 or result["op"] != None
 or result["arity"] != None
  ):
    raise ParseError("Ended parsing with leftover expectations.")

  result = result["args"][0]
  result["parent"] = None

  if not ungrouped and result["op"] not in ("value", "opval"):
    result["grouped"] = True

  return result

def parse_expr(expr):
  """
  Parses a macro expression into a parse tree of operations.

  Examples:
    ```?
    parse_expr("True")
    ```=
    {
      "state": "complete",
      "op": "value",
      "value": ("boolean", True)
    }
    ```?
    parse_expr("1 + 2")
    ```=
    {
      "state": "complete",
      "grouped": True,
      "op": '+',
      "arity": 2,
      "args": [
        {
          "state": "complete",
          "op": "value",
          "value": ("int", 1)
        },
        {
          "state": "complete",
          "op": "value",
          "value": ("int", 2)
        }
      ]
    }
    ```?
    parse_expr("'one' or False")
    ```=
    {
      "state": "complete",
      "grouped": True,
      "op": 'or',
      "arity": 2,
      "args": [
        {
          "state": "complete",
          "op": "value",
          "value": ("string", 'one')
        },
        {
          "state": "complete",
          "op": "value",
          "value": ("boolean", False)
        }
      ]
    }
    ```?
    parse_expr("1 * 2 + 3")
    ```=
    {
      "state": "complete",
      "grouped": True,
      "op": '+',
      "arity": 2,
      "args": [
        {
          "state": "complete",
          "grouped": False,
          "op": '*',
          "arity": 2,
          "args": [
            {
              "state": "complete",
              "op": "value",
              "value": ("int", 1)
            },
            {
              "state": "complete",
              "op": "value",
              "value": ("int", 2)
            }
          ]
        },
        {
          "state": "complete",
          "op": "value",
          "value": ("int", 3)
        }
      ]
    }
    ```?
    parse_expr("1 + 2 * 3")
    ```=
    {
      "state": "complete",
      "grouped": True,
      "op": '+',
      "arity": 2,
      "args": [
        {
          "state": "complete",
          "op": "value",
          "value": ("int", 1)
        },
        {
          "state": "complete",
          "grouped": False,
          "op": '*',
          "arity": 2,
          "args": [
            {
              "state": "complete",
              "op": "value",
              "value": ("int", 2)
            },
            {
              "state": "complete",
              "op": "value",
              "value": ("int", 3)
            }
          ]
        }
      ]
    }
    ```
  """
  units = lex_expr(expr)
  return scrub_parents(parse_units(units))

class EvalError(Exception):
  """
  An EvalError indicates a problem that occurs when evaluating an expression.
  """
  pass

def eval_tree(tree, state):
  """
  Evaluates a parse tree and returns an actual value. Use parse_expr to create
  a parse tree. Returns a ((type, value), update_state) complex.
  """
  # Handle the base cases:
  if tree["op"] in ("value", "opval"):
    return tree["value"], state

  # Short-circuiting and other special-case operators:
  if tree["op"] == 'or':
    (t, v), state = eval_tree(tree["args"][0], state)
    if ops.is_true(t, v):
      return ("boolean", True), state
    else:
      (t, v), state = eval_tree(tree["args"][1], state)
      return ("boolean", ops.is_true(t, v)), state
  elif tree["op"] == 'and':
    (t, v), state = eval_tree(tree["args"][0], state)
    if not ops.is_true(t, v):
      return ("boolean", False), state
    else:
      (t, v), state = eval_tree(tree["args"][1], state)
      return ("boolean", ops.is_true(t, v)), state
  elif tree["op"] == '!':
    (t, v), state = eval_tree(tree["args"][0], state)
    if t == "list":
      mstate = {}
      mstate.update(state)
      mstate['@'] = v
      results = []
      for i, val in enumerate(v):
        mstate['#'] = ("int", i)
        mstate['?'] = val
        (rt, rv), mstate = eval_tree(tree["args"][1], mstate)
        results.append((rt, rv))

      del mstate['#']
      del mstate['?']
      del mstate['@']
      state.update(mstate)
      return ("list", results), state
    elif t == "dict":
      mstate = {}
      mstate.update(state)
      mstate['@'] = v
      results = {}
      for k in v:
        mstate['#'] = k
        mstate['?'] = v[k]
        (rt, rv), mstate = eval_tree(tree["args"][1], mstate)
        results[k] = (rt, rv)

      del mstate['#']
      del mstate['?']
      del mstate['@']
      state.update(mstate)
      return ("dict", results), state
    else:
      raise EvalError("Cannot map over value: {}".format((t, v)))

  # Get the recursion out of the way:
  arg_values = []
  for a in tree["args"]:
    (at, av), state = eval_tree(a, state)
    arg_values.append((at, av))

  # Operator implementations:
  return ops.op_result(tree["op"], state, *arg_values)


def eval_expr(expr, story, state):
  """
  Evaluates an expression, which may include both macro calls and operators.
  Returns a result-value, updated-state pair.

  Exmaples:
    ```?
    eval_expr(
      '1',
      eval( # Fake object with .nodes and .title (without importing story):
        "[exec('class T: pass\\\\nt = T()\\\\nt.nodes = []"
      + "\\\\nt.title=\\\"_\\\"'), "
      + "eval('t')][1]"
      ),
      {}
    )
    ```=
    (('int', 1), {})
    ```
  """
  state = copy.deepcopy(state)

  pt = parse_expr(expr)

  return eval_tree(pt, state)

def eval_macro(name, args, story, state):
  """
  Evaluates the macro with the given name in the context of the given story,
  feeding in the given arguments and using the given state. A return-value,
  updated-state pair is returned.

  Examples:
    ```?
    eval_macro(
      "if",
      ["True", "1", "else", "0"],
      eval( # Fake object with .nodes and .title (without importing story):
        "[exec('class T: pass\\\\nt = T()\\\\nt.nodes = []"
      + "\\\\nt.title=\\\"_\\\"'), "
      + "eval('t')][1]"
      ),
      {}
    )
    ```=
    (
      "1",
      {"_context": []}
    )
    ```
  """
  state = copy.deepcopy(state)

  if name in story.nodes:
    node = story.nodes[name]

    value, state = eval_text(node.content, story, state, args)

  else:
    # Must be built-in or from a module:
    if name.count('.') == 1:
      # From a module
      module_name, inner_name = name.split('.')

      if module_name in story.modules:
        module = story.modules[module_name]

        if inner_name in module.nodes:
          node = module.nodes[inner_name]
          # TODO: Some way to return a non-string here?
          value, state = eval_text(node.content, story, state, args)

        else:
          value, state = error(
            "Module '{}' doesn't define macro '{}'.".format(
              module_name,
              inner_name
            ),
            state
          )

      else:
        value, state = error(
          "Module '{}' for macro '{}' was not loaded by story '{}'.".format(
            module_name,
            name,
            story.title
          ),
          state
        )

    elif name in BUILTINS:
      # A built-in macro
      try:
        value, state = BUILTINS[name](story, state, *args)
      except Exception as e:
        value, state = error(
          "Error calling built-in '{}' with arguments:\n{}\nDetails:\n{}"
          .format(
            name,
            '\n'.join(str(a) for a in args),
            ''.join(
              traceback.format_exception(
                type(e),
                e,
                e.__traceback__
              )
            )
          ),
          state
        )
    else:
      # Unrecognized macro: expands to error text
      # TODO: Better error text
      value, state = error("Unrecognized macro '{}'.".format(name), state)

  return value, state

def eval_text(text, story, state, context=None):
  """
  Evaluates a string which may contain macros. Treats everything that's not
  explicitly a macro as text. Returns a pair of computed-value, modified-state,
  although the values of local variables (those that start with '_') will not
  be affected.

  Context may be specified as a list of values.
  """
  context = context or []

  state = copy.deepcopy(state)

  # Preserve local variables:
  local_vars = {
    v: copy.deepcopy(state[v])
      for v in state
      if v.startswith('_') and not v.endswith('_')
  }

  # Set context:
  state["_context"] = context

  # Split up text into strings and macros:
  i = 0
  bits = []
  while i < len(text):
    ms = MACRO_START.search(text, i)
    if not ms: # no matches means no expansion needed
      bits.append(text[i:])
      i = len(text) # we're done
    else:
      # There's a match:
      start = ms.start()
      try:
        end = utils.matching_brace(text, start, '(', ')')
      except utils.UnmatchedError as e:
        ectx = text[max(0, i-10):i+50]
        ectx = ectx \
          .replace('\n', '\u2424') \
          .replace('\r', '\u240d') \
          .replace('\t', '\u2409')
        eii = 10 - max(0, 10 - i)
        print(
          "Warning: Unclosed macro treated as text:\n{}\n{}'''".format(
            start,
            ectx,
            ' '*eii + '^' + ' '*(60 - eii - 1)
          ),
          file=sys.stderr
        )
        i = ms+1 # skip past that match
        continue

      # start and end found -> first add text before macro:
      bits.append(text[i:start])
      i = end + 1

      # eval macro:
      macro_name = ms.group(1)
      macro_content = text[ms.end():end]
      macro_args = utils.split_unquoted(macro_content, delim=':', qc='"')

      mv, state = eval_macro(macro_name, macro_args, story, state)
      bits.append(to_string(mv))

  # Restore locals:
  state.update(local_vars)

  return ''.join(bits), state

def error(message, state):
  """
  Returns an expansion-text, updated-state pair for the given error.
  """
  message = "Error: " + message
  exp = "<<{}>>".format(message)
  if "_errors_" not in state:
    state["_errors_"] = []
  state["_errors_"].append(message)
  return exp, state

def pt_string(parse_tree, indent=0):
  result = ''
  for k in parse_tree:
    if k not in ("parent", "args"):
      result += "{}: {}\n".format(k, parse_tree[k])

  if "args" in parse_tree:
    ind = ' '*(indent+2)
    result += "args:\n"
    for a in parse_tree["args"]:
      result += ('\n' + ind).join((ind + pt_string(a, indent+2)).split('\n'))

  return result

# Macro built-in functions:
# -------------------------

@mb
def eval_(story, state, *args):
  """
  The 'eval' macro builtin. Evaluates each argument, returning a single value
  or a list of values if there is more than one argument.
  """
  if len(args) == 1:
    return eval_expr(arg, story, state)
  else:
    result = []
    for arg in args:
      val, state = eval_expr(arg, story, state)
      result.append(val)
    return result, state

@mb
def cat(story, state, *args):
  """
  The 'cat' macro builtin. Evaluates each argument as text, and returns the
  results concatenated into a list.
  """
  results = []
  for arg in args:
    val, state = eval_text(arg, story, state)
    results.append(val)
  return ''.join(str(r) for r in results)

# TODO: Catch exceptions generated w/ # of arguments
@mb
def lookup(story, state, obj, key):
  """
  The 'lookup' macro builtin. Evaluates two arguments as expressions and looks
  up the second result within the first.
  """
  obj, state = eval_expr(obj, story, state)
  key, state = eval_expr(key, story, state)
  if key in obj:
    return obj[key], state
  else:
    return (
      error("Lookup failed to find '{}' in '{}'.".format(key, obj)),
      state
    )

@mb
def context(story, state, n):
  """
  The 'context' macro builtin. Returns the value of the nth context variable,
  after evaluating the given expression to find n.
  """
  n, state = eval_expr(n, story, state)
  if n >= 1 and n <= len(state["_context"]):
    return state["_context"][n-1], state
  else:
    # Invalid indices just result in an empty string.
    return None, state

@mb
def if_(story, state, *args):
  """
  The 'if' macro builtin. Evaluates every odd argument as a condition, also
  accepting the special value 'else', and resolves to the evaluation (as text)
  of the first even argument whose condition matched. Unmatched even arguments
  are not evaluated.
  """
  odd = [args[i] for i in range(0, len(args), 2)]
  even = [args[i] for i in range(1, len(args), 2)]
  # Leftover becomes an implicit else case:
  # TODO: Issue warning here?
  el = None
  if len(odd) > len(even):
    el = odd.pop()

  for i, arg in enumerate(odd):
    val, state = eval_expr(arg, story, state)
    if val: # the string "else" will pass this test
      return eval_text(even[i], story, state)

  # No condition was true:
  if el is None:
    return None, state
  else:
    return eval_expr(el, story, state)

@mb
def once(story, state, arg):
  """
  The 'once' macro builtin. Evaluates its argument as text, but only if this is
  the first time that the current node has been visited. Otherwise it returns
  an empty string.
  """
  if state["_first"]:
    return eval_text(arg, story, state)
  else:
    return "", state

@mb
def again(story, state, arg):
  """
  The 'again' macro builtin. The converse of once: it evaluates its argument
  as text only on non-initial visits to a node.
  """
  if state["_first"]:
    return "", state
  else:
    return eval_text(arg, story, state)
