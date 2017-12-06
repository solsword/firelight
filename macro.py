"""
macro.py

See modules/help.fls for a description of the macro system.
"""

import re
import sys
import copy
import traceback

import utils

import ops

MACRO_START = re.compile(r"\(([a-zA-Z_][a-zA-Z_0-9.]+)~")

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

def split_macro_args(content):
  """
  Splits macro content into different arguments, respecting quoted strings and
  interior macro calls.
  """
  # TODO: Enable escaped tildes!

  # First, find quoted regions:
  qrs = list(utils.find_quoted_regions(content, qc='`').keys())

  # Next, find macro calls:
  mrs = []
  i = 0
  while i < len(content):
    # Look for a macro-start:
    m = MACRO_START.search(content, i)
    if m:
      r = utils.find_region(qrs, m.start())
      if r:
        i = r[1]+1 # skip to end of quoted region
        continue

      # Otherwise this 
      try:
        mend = utils.matching_brace(content, m.start(), qc='`')
        mrs.append((m.start(), mend))
        i = mend + 1
      except utils.UnmatchedError:
        # malformed macro: skip to the end of the macro start
        i = m.end() + 1
    else:
      # No more macros found
      break

  # Combine macro- and quote-excluded regions:
  exrs = sorted(qrs + mrs)

  # Finally, find non-excluded delimiters:
  result = []
  i = 0
  while i < len(content):
    # Compute first-non-excluded-delimiter index:
    try:
      di = content.index('~', i)
    except ValueError:
      di = len(content)

    for exr in exrs:
      if di >= len(content):
        break
      if exr[0] <= di and exr[1]>= di:
        try:
          di = content.index('~', exr[1]+1)
        except ValueError:
          di = len(content)

    result.append(content[i:di])
    i = di + 1

  return result

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
    if c in "()[]+-%&|./*^=<>!\"'" and sval != None:
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
    elif c in "+-&|.":
      units.append(("op", c))
    elif c in "/*%^":
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
    elif c == '`':
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

class ParseUnit:
  """
  A class representing a parsed unit of code (e.g., a constant, an operator, a
  variable lookup, etc.)
  """
  pass


class VariableLookup(ParseUnit):
  """
  A value representing looking up a variable in the story state.
  """
  def __init__(self, name):
    self.name = name

class FunctionCall(ParseUnit):
  """
  A value representing a macro invocation.
  """
  def __init__(self, name, args):
    self.name = name
    self.args = args

def parse_next_val(units):
  """
  Parses the next value from the given units. Returns a (parse-tree, leftovers)
  pair.
  """
  ut, uv = units[0]
  if ut == "word":
    if uv == "True":
      return True, units[1:]
    elif uv == "False":
      return False, units[1:]
    elif uv == "None":
      return None, units[1:]
    else:
      return VariableLookup(uv), units[1:]
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
    ms = MACRO_START.match(uv)
    if not ms:
      raise ParseError("Invalid macro token.")
    macro_name = ms.group(1)
    macro_content = uv[ms.end():]
    macro_args = split_macro_args(macro_content)
    return FunctionCall(macro_name, macro_args), units[1:]
  elif ut == "op":
    raise ParseError("Unexpected operator (expected value).")
  elif ut in ("int", "float", "string"):
    return uv, units[1:]

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
      return ops.Operator('['), units[1:]
    else:
      raise ParseError("Unexpected index end (expected operator).")
  elif ut == "call":
    raise ParseError("Unexpected call (expected operator).")
  elif ut == "op":
    return ops.Operator(uv), units[1:]
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
        if op in ['+', '-', 'not']: # unary operators
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
        op, rest = parse_next_op(rest)
        if op.op in ['+', '-', 'not']: # stacked unary
          nr = {
            "parent": result,
            "state": "need_val",
            "grouped": False,
            "op": op.op,
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
      op, rest = parse_next_op(rest)
      if op.op == 'not': # unary operator
        raise ParseError("Expected binary operator but got '{}'.".format(op))
      elif op.op == '[': # recurse to get index parse tree
        rr = rotate_operators(result, op.op)
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
        result["op"] = op.op
        result["state"] = "complete"
        result["args"].append(parse_units(rest[1:i]))
        rest = rest[i+1:]
      else: # a binary (or possibly trinary) operator
        rr = rotate_operators(result, op.op)
        if rr:
          result = rr
        else:
          result["arity"] = 2
          result["op"] = op.op
          result["state"] = "need_val"

        # Fix arity/state for special operators:
        if op.op in ('%', '%%', '.'):
          result["arity"] = 3
        elif op.op == '|':
          result["arity"] = 3
          result["state"] = "need_opval"
        elif op.op == '!':
          result["state"] = "need_call"

    elif result["state"] == "need_opval":
      op, rest = parse_next_op(rest)
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
      val, rest = parse_next_val(rest)
      if isinstance(val, FunctionCall):
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
    parse_expr("`yes`")
    ```=
    {
      "state": "complete",
      "op": "value",
      "value": "yes"
    }
    ```?
    parse_expr("True")
    ```=
    {
      "state": "complete",
      "op": "value",
      "value": True
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
          "value": 1
        },
        {
          "state": "complete",
          "op": "value",
          "value": 2
        }
      ]
    }
    ```?
    parse_expr("`one` or False")
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
          "value": 'one'
        },
        {
          "state": "complete",
          "op": "value",
          "value": False
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
              "value": 1
            },
            {
              "state": "complete",
              "op": "value",
              "value": 2
            }
          ]
        },
        {
          "state": "complete",
          "op": "value",
          "value": 3
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
          "value": 1
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
              "value": 2
            },
            {
              "state": "complete",
              "op": "value",
              "value": 3
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

def eval_tree(tree, story, state, module_finder):
  """
  Evaluates a parse tree and returns an actual value. Use parse_expr to create
  a parse tree. Returns a ((type, value), update_state) complex.
  """
  # Handle the base cases:
  if tree["op"] in ("value", "opval"):
    rv = tree["value"]
    if isinstance(rv, FunctionCall):
      return eval_macro(rv.name, rv.args, story, state, module_finder)
    elif isinstance(rv, VariableLookup):
      if rv.name in state:
        return state[rv.name], state
      else:
        return error("Unknown variable '{}'.".format(rv.name), state)
    else:
      return rv, state

  # Short-circuiting and other special-case operators:
  if tree["op"] == 'or':
    val, state = eval_tree(tree["args"][0], story, state, module_finder)
    if ops.is_true(val):
      return ("boolean", True), state
    else:
      val, state = eval_tree(tree["args"][1], story, state, module_finder)
      return ("boolean", ops.is_true(val)), state
  elif tree["op"] == 'and':
    val, state = eval_tree(tree["args"][0], story, state, module_finder)
    if not ops.is_true(val):
      return ("boolean", False), state
    else:
      val, state = eval_tree(tree["args"][1], story, state, module_finder)
      return ("boolean", ops.is_true(val)), state
  elif tree["op"] == '!':
    val, state = eval_tree(tree["args"][0], story, state, module_finder)
    if isinstance(val, list):
      mstate = {}
      mstate.update(state)
      mstate['@'] = v
      results = []
      for i, v in enumerate(val):
        mstate['#'] = ("int", i)
        mstate['?'] = v
        rv, mstate = eval_tree(tree["args"][1], story, mstate, module_finder)
        results.append(rv)

      del mstate['#']
      del mstate['?']
      del mstate['@']
      state.update(mstate)
      return results, state
    elif isinstance(val, dict):
      mstate = {}
      mstate.update(state)
      mstate['@'] = val
      results = {}
      for k in val:
        mstate['#'] = k
        mstate['?'] = val[k]
        rv, mstate = eval_tree(tree["args"][1], story, mstate, module_finder)
        results[k] = rv

      del mstate['#']
      del mstate['?']
      del mstate['@']
      state.update(mstate)
      return results, state
    else:
      raise EvalError("Cannot map over value: {}".format(val))

  # Get the recursion out of the way:
  arg_values = []
  for a in tree["args"]:
    av, state = eval_tree(a, story, state, module_finder)
    arg_values.append(av)

  # Operator implementations:
  return ops.op_result(tree["op"], state, *arg_values)


def eval_expr(expr, story, state, module_finder=None):
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
    (1, {})
    ```
  """
  state = copy.deepcopy(state)

  pt = parse_expr(expr)

  return eval_tree(pt, story, state, module_finder)

def eval_macro(name, args, story, state, module_finder=None):
  """
  Evaluates the macro with the given name in the context of the given story,
  feeding in the given arguments and using the given state. A return-value,
  updated-state pair is returned.

  The given module_finder function should accept a module name and return a
  Story object for that module, or None if the module can't be found.

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
    ( 1, {} )
    ```?
    eval_macro(
      "if",
      ["1 - 1", "`nope`", "2 * 0", 'nope', "`a` or False", "`yes`", "else","0"],
      eval( # Fake object with .nodes and .title (without importing story):
        "[exec('class T: pass\\\\nt = T()\\\\nt.nodes = []"
      + "\\\\nt.title=\\\"_\\\"'), "
      + "eval('t')][1]"
      ),
      {}
    )
    ```=
    ( "yes", {} )
    ```
  """
  state = copy.deepcopy(state)

  if name in story.nodes: # node-as-macro call
    node = story.nodes[name]

    return eval_text(node.content, story, state, args, module_finder)

  # Must be built-in or from a module:
  # Try to resolve as a module:
  if name.count('.') == 1: # From a module
    module_name, inner_name = name.split('.')

    if module_name not in story.modules:
      return error(
        "Module '{}' for macro '{}' is not included by story '{}'.".format(
          module_name,
          name,
          story.title
        ),
        state
      )

    if not module_finder:
      return error(
        "Attempt to use module '{}' without a module finder.".format(
          module_name
        ),
        state
      )

    module = module_finder(module_name)

    if not module:
      return error("Module '{}' not found.".format(module_name), state)

    if inner_name not in module.nodes:
      return error(
        "Module '{}' doesn't define macro '{}'.".format(
          module_name,
          inner_name
        ),
        state
      )

    node = module.nodes[inner_name]
    # TODO: Some way to return a non-string here?
    return eval_text(
      node.content,
      story,
      state,
      args,
      module_finder
    )

  # if it's not a module reference, it might be a builtin?
  elif name in BUILTINS: # A built-in macro
    try:
      return BUILTINS[name](module_finder, story, state, *args)
    except Exception as e:
      return error(
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

  # otherwise we don't know what this macro is...
  else:
    # Unrecognized macro: expands to error text
    # TODO: Better error text
    return error("Unrecognized macro '{}'.".format(name), state)

def eval_text(text, story, state, context=None, module_finder=None):
  """
  Evaluates a string which may contain macros. Treats everything that's not
  explicitly a macro as text. Returns a pair of computed-value, modified-state,
  although the values of local variables (those that start with '_') will not
  be affected.

  Context may be specified as a list of values.

  The given module_finder function should accept a module name and return a
  Story object for that module, or None if the module can't be found.

  Examples:

    ```?
    eval_text('''\
(once~
 Disclaimer: This is a work of fiction and is not intended to aid in
 identifying edible mushrooms. NEVER eat a mushroom unless you are absolutely
 certain it is not poisonous, as many edible species look very similar to
 poisonous ones, and as a result fatal poisonings occur worldwide every year.
)

(again~
  (if~
  ~ lost = 0 ~ ``no extra text in this case
  ~ lost < 3 ~ You've found your way back. (set~ lost ~ 0)
  ~ lost < 6 ~ You've found the trail again. For a moment there, you were worried. (set~ lost ~ 0)
  ~ else~ Finally, you've found the trail again! Now that you're back, you wonder how you were ever lost. (set~ lost ~ 0)
  )
)

You're alone in the crisp autumn forest, surrounded by vermillion leaves and
the scent of wet earth on a faint trail through the hills.

(once~ You're here for mushrooms, and after a few days of rain, you don't
expect to be disappointed.

[[Uphill|birch|You hike uphill away from the trail.(add~ lost ~ 1)]] from you, a stand of birch an aspen dominates the hilltop.

At the bottom of the hill, a depression has developed into a small [[bog||You set off downhill away from the trail, losing your vantage point as you descend.(add~ lost ~ 2)]].

Ahead of you, a few [[pines|pine|You walk a short distance to the pines, leaving the trail as it twists away uphill.(add~ lost ~ 1)]] proudly retain their needles.

Of course, you could just start searching among the oaks and maples right [[here|oak|You wander a short distance from the trail.(add~ lost ~ 1)]]
)

(again~
  (if~
  ~ (inv.count~ "#mushroom") = 0 ~
    It's a shame you didn't find anything, but hunting is always a matter of
    luck.
  ~ (inv.count~ "#mushroom") < 4 ~
    You've collected a few specimens, but you wish you'd had time to look for
    more.
  ~ else ~
    You've got plenty of mushrooms to sort out when you get back.
  )
  In any case, the sun is starting to dip towards the opposite hill, and you've got ground to cover before you're out of these woods. It's time to go [[home]].
)
''',
eval( # Fake object with .nodes and .title (without importing story)~
  "[exec('class T: pass\\\\nt = T()\\\\nt.nodes = []"
+ "\\\\nt.title=\\\"_\\\"'), "
+ "eval('t')][1]"
),
{"_first": True, "lost": 0}
)[0]
    ```=
'''\
Disclaimer: This is a work of fiction and is not intended to aid in
identifying edible mushrooms. NEVER eat a mushroom unless you are absolutely
certain it is not poisonous, as many edible species look very similar to
poisonous ones, and as a result fatal poisonings occur worldwide every year.

You're alone in the crisp autumn forest, surrounded by vermillion leaves and
the scent of wet earth on a faint trail through the hills.

You're here for mushrooms, and after a few days of rain, you don't
expect to be disappointed.

[Uphill] from you, a stand of birch an aspen dominates the hilltop.

At the bottom of the hill, a depression has developed into a small [bog].

Ahead of you, a few [pines] proudly retain their needles.

Of course, you could just start searching among the oaks and maples right [here]
'''
    ```
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
          "Warning: Unclosed macro treated as text as position {} in:\n{}\n{}"
          .format(
            start,
            ectx,
            ' '*eii + '^' + ' '*(60 - eii - 1)
          ),
          file=sys.stderr
        )
        i = ms.end() + 1 # skip past that match
        continue

      # start and end found -> first add text before macro:
      bits.append(text[i:start])
      i = end + 1

      # eval macro:
      macro_name = ms.group(1)
      macro_content = text[ms.end():end]
      macro_args = split_macro_args(macro_content)

      mv, state = eval_macro(macro_name, macro_args, story, state,module_finder)
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
def set_(mf, story, state, var, expr):
  """
  The 'set' macro builtin. Modifies a state variable, and returns the computed
  value.
  """
  # TODO: Eval var as text?
  val, state = eval_expr(expr, story, state, mf)
  state[var.strip()] = val
  return val, state

@mb
def add(mf, story, state, var, expr):
  """
  The 'set' macro builtin. Modifies a state variable, and returns the computed
  offset value.
  """
  # TODO: Eval var as text?
  val, state = eval_expr(expr, story, state, mf)
  state[var.strip()] += val
  return val, state

@mb
def eval_(mf, story, state, *args):
  """
  The 'eval' macro builtin. Evaluates each argument as an expression, returning
  a single value or a list of values if there is more than one argument.
  """
  if len(args) == 1:
    return eval_expr(arg, story, state, mf)
  else:
    result = []
    for arg in args:
      val, state = eval_expr(arg, story, state, mf)
      result.append(val)
    return result, state

@mb
def text(mf, story, state, *args):
  """
  The 'text' macro builtin. Evaluates each argument as text, joining them
  together into a single result string.
  """
  if len(args) == 1:
    return eval_text(arg, story, state, mf)
  else:
    results = []
    for arg in args:
      val, state = eval_text(arg, story, state, mf)
      results.append(val)
    return ''.join(results), state

# TODO: Catch exceptions generated w/ # of arguments
@mb
def lookup(mf, story, state, obj, key):
  """
  The 'lookup' macro builtin. Evaluates two arguments as expressions and looks
  up the second result within the first.
  """
  obj, state = eval_expr(obj, story, state, mf)
  key, state = eval_expr(key, story, state, mf)
  if key in obj:
    return obj[key], state
  else:
    return (
      error("Lookup failed to find '{}' in '{}'.".format(key, obj)),
      state
    )

@mb
def context(mf, story, state, n):
  """
  The 'context' macro builtin. Returns the value of the nth context variable,
  after evaluating the given expression to find n.
  """
  n, state = eval_expr(n, story, state, mf)
  if n >= 1 and n <= len(state["_context"]):
    return state["_context"][n-1], state
  else:
    # Invalid indices just result in an empty string.
    return None, state

@mb
def if_(mf, story, state, *args):
  """
  The 'if' macro builtin. Evaluates every odd argument as a condition, also
  accepting the special value 'else', and resolves to the evaluation (as an
  expression) of the first even argument whose condition matched. Unmatched
  even arguments are not evaluated.
  """
  return cond_base(mf, story, state, *args, as_text=False)

@mb
def select(mf, story, state, *args):
  """
  The 'select' macro builtin. Works exactly the same as 'if', but evaluates its
  result as text instead of as an expression.
  """
  return cond_base(mf, story, state, *args, as_text=True)

def cond_base(mf, story, state, *args, as_text=False):
  """
  Base code for 'if' and 'select'.
  """
  odd = [args[i] for i in range(0, len(args), 2)]
  even = [args[i] for i in range(1, len(args), 2)]
  # Leftover becomes an implicit else case:
  # TODO: Issue warning here?
  el = None
  if len(odd) > len(even):
    el = odd.pop()

  for i, arg in enumerate(odd):
    val, state = eval_expr(arg, story, state, mf)
    if val: # the string "else" will pass this test
      if as_text:
        return eval_text(even[i], story, state, mf)
      else:
        return eval_expr(even[i], story, state, mf)

  # No condition was true:
  if el is None:
    return None, state
  else:
    if as_text:
      return eval_text(el, story, state, mf)
    else:
      return eval_expr(el, story, state, mf)

@mb
def once(mf, story, state, arg):
  """
  The 'once' macro builtin. Evaluates its argument as text, but only if this is
  the first time that the current node has been visited. Otherwise it returns
  an empty string.
  """
  if state["_first"]:
    return eval_text(arg, story, state, mf)
  else:
    return "", state

@mb
def again(mf, story, state, arg):
  """
  The 'again' macro builtin. The converse of once: it evaluates its argument
  as text only on non-initial visits to a node.
  """
  if state["_first"]:
    return "", state
  else:
    return eval_text(arg, story, state, mf)
