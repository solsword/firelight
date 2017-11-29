"""
macro.py

See modules/help.fls for a description of the macro system.
"""

import re
import copy

import utils

MACRO_START = re.compile(r"([a-zA-Z_][a-zA-Z_0-9.]\+):")

INT_CONSTANT = re.compile(r"([+-])?(0[xo])?([0-9A-Fa-f])\+")

FLOAT_CONSTANT = re.compile(r"([+-])?([0-9]\+)(.[0-9]*)?([eE][+-]?[0-9]\+)?")

OPERATOR_PRECEDENCE = {
  '[': 1000,
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
  '==': 10,
  '<': 10,
  '>': 10,
  '<=': 10,
  '>=': 10,
  '!=': 10,
  '!': 100,
  'and': 5,
  'or': 5,
  'not': 5,
}

def mb_eval(story, state, *args):
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

def mb_cat(story, state, *args):
  """
  The 'cat' macro builtin. Evaluates each argument as text, and returns the
  results concatenated into a list.
  """
  results = []
  for arg in args:
    val, state = eval_text(arg, story, state))
    results.append(val)
  return ''.join(str(r) for r in results)

# TODO: Catch exceptions generated w/ # of arguments
def mb_lookup(story, state, obj, key):
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

def mb_context(story, state, n):
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

def mb_if(story, state, *args):
  """
  The 'if' macro builtin. Evaluates every odd argument as a condition, also
  accepting the special value 'else', and resolves to the evaluation (as text)
  of the first even argument whose condition matched. Unmatched even arguments
  are not evaluated.
  """
  odd = [args[i] for i in range(len(args), 2)]
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

def mb_once(story, state, arg):
  """
  The 'once' macro builtin. Evaluates its argument as text, but only if this is
  the first time that the current node has been visited. Otherwise it returns
  an empty string.
  """
  if state["_first"]:
    return eval_text(arg, story, state)
  else:
    return "", state

def mb_again(story, state, arg):
  """
  The 'again' macro builtin. The converse of mb_once; it evaluates its argument
  as text only on non-initial visits to a node.
  """
  if state["_first"]:
    return "", state
  else:
    return eval_text(arg, story, state)

BUILTINS = {
  "eval": mb_eval,
  "cat": mb_cat,
  "lookup": mb_lookup,
  "context": mb_context,
  "if": mb_if,
  "once": mb_once,
  "again": mb_again,
}

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
  while i < len(expr):
    i += 1
    c = expr[i]

    # Check for end-of-word with accumulated string value:
    if c in "()[]+-%&|./*~^=<>!\"'" and sval != None:
      units.append("word", sval)
      sval = None

    if c in ' \n\r\t': # (separate if statement)
      if sval:
        units.append("word", sval)
        sval = None
    elif c == '(':
      m = MACRO_START.search(expr, i)
      start = m.start()
      if start == i:
        end = utils.matching_brace(src, i, '(', ')')
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
      units.append("op", c)
    elif c in "/*~^":
      if expr[i+1] == c:
        units.append("op", c+c)
        i += 1
      else:
        units.append("op", c)
    elif c == '=':
      if expr[i+1] == c: # allow '==' with same meaning as '='
        i += 1
      units.append("op", c)
    elif c in '<>!':
      if expr[i+1] == '=':
        units.append("op", expr[i:i+2])
        i += 1
      else:
        units.append("op", c)
    elif c == 'a' and expr[i:i+3] == 'and':
      if sval != None:
        sval += "and"
      else:
        units.append("op", "and")
      i += 2
    elif c == 'o' and expr[i:i+2] == 'or':
      if sval != None:
        sval += "or"
      else:
        units.append("op", "and")
      i += 1
    elif c == 'n' and expr[i:i+3] == 'not':
      if sval != None:
        sval += "not"
      else:
        units.append("op", "not")
      i += 2
    elif c in "0123456789":
      if sval != None:
        sval += c
      else:
        m = FLOAT_CONSTANT.match(expr, i)
        if m:
          try:
            f = float(m.group(0))
            i = m.end()
            units.append("float", f)
            continue
          except ValueError:
            pass
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
            units.append("int", it)
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
      units.append("string", qc)
      i = ei
    else: # Not a recognized operator: add to string
      # TODO: Add sval as a unit somewhere?
      if sval is None:
        sval = c
      else:
        sval += c

class ParseError(Exception):
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
  for arg in result["args"]:
    if isinstance(arg, dict):
      scrub_parents(arg)

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
    elif result["state"] == "blank":
      try:
        val, rest = parse_next_val(rest)
        result["args"].append(
          {
            "parent": result,
            "state": "complete",
            "grouped": True,
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
      try:
        val, rest = parse_next_val(rest)
        result["args"].append(
          {
            "parent": result,
            "state": "complete",
            "grouped": True,
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
        else:
          raise e
    elif result["state"] == "need_op":
      (otyp, op), rest = parse_next_op(rest)
      if op == 'not': # unary operator
        raise ParseError("Expected binary operator but got '{}'.".format(op))
      elif otyp == "index": # recurse to get index parse tree
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
        result["args"].append(parse_units(rest[1:i]))
        rest = rest[i+1:]
        result["state"] = "complete"
      elif op in ('~', '~~'): # trinary substitution operators
        result["arity"] = 3
        result["op"] = op
        result["state"] = "need_val"
      elif op == "|": # possibly operator-trinary
        result["arity"] = 3
        result["op"] = op
        result["state"] = "possibly_optri"
      elif op == '!':
        result["arity"] = 2
        result["op"] = op
        result["state"] = "need_call"
      else: # a normal binary operator
        # TODO: operator precedence here
        result["arity"] = 2
        result["op"] = op
        result["state"] = "need_val"
    elif result["state"] == "possibly_optri":
      orest = rest
      try:
        (otyp, op), rest = parse_next_op(rest)
        result["args"].append(
          {
            "parent": result,
            "state": "complete",
            "grouped": True,
            "op": "opval",
            "value": op
          }
        )
        result["state"] = "need_val"
      except ParseError as e: # just a normal binary operator
        # TODO: operator precedence here
        rest = orest
        result["arity"] = 2 # revise arity
        result["state"] = "need_val"
    elif result["state"] == "need_call":
      (vtyp, val), rest = parse_next_val(rest)
      if vtyp == "call":
        result["args"].append(
          {
            "parent": result,
            "state": "complete",
            "grouped": True,
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

  if result["state"] == "need_op" and len(result["args"] == 1):
    # Ended at valid full-value (expecting operator)
    result = result["args"][0]
    result["parent"] = None
  else:
    raise ParseError("Ended parsing in state '{}'.".format(result["state"]))

  if !ungrouped:
    result["grouped"] = True

  return result

def parse_expr(expr):
  """
  Parses a macro expression into a parse tree of operations.

    ```
    parse_expr("1 + 2")
    ```
    {
      "parent": None,
      "state": "blank",
      "grouped": False,
      "op": None,
      "arity": None,
      "args": []
    }
    ```
  """
  units = lex(expr)
  return scrub_parents(parse_units(units))

def eval_tree(tree):
  """
  Evaluates a parse tree and returns an actual value. Use parse_expr to create
  a parse tree. Returns a (type, value) pair.
  """
  if tree["op"] in ("value", "opval"):
    return tree["value"]
  elif tree["op"] == '+':
    t1, v1 = tree["args"][0]
    t2, v2 = tree["args"][1]
    if t1 == "string":
      return ("string", str(v1) + str(v2))
    elif t1 == "boolean" and t2 == "boolean":
      return ("boolean", t1 or t2)
    elif t1 in ("int", "float") and t2 in ("int", "float"):
      return ("int", v1 + v2)
    elif t1 == "list" and t2 == "list":
      return ("list", v1 + v2)
    elif t1 == "dict" and t2 == "dict":
      result = {}
      result.update(v1)
      result.update(v2)
      return ("dict", result)
    else:
      return ("string", str(v1) + str(v2))
  elif tree["op"] == '-':
    # TODO: HERE


def eval_expr(expr, story, state):
  """
  Evaluates an expression, which may include both macro calls and operators.
  Returns a result-value, updated-state pair.
  """
  state = copy.deepcopy(state)

  pt = parse_expr(expr)

def eval_macro(name, args, story, state):
  """
  Evaluates the macro with the given name in the context of the given story,
  feeding in the given arguments and using the given state. A return-value,
  updated-state pair is returned.
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
      except:
        value = error(
          "Error calling built-in '{}' with arguments:\n{}".format(
            name,
            '\n'.join(str(a) for a in args)
          )
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
    ms = MACRO_START.search(src, i)
    if not ms: # no matches means no expansion needed
      bits.append(text[i:])
      i = len(text) # we're done
    else:
      # There's a match:
      start = ms.start()
      try:
        end = utils.matching_brace(src, start, '(', ')')
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
      macro_content = src[ms.end():end]
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
  state["_errors_"].append(message)
  return exp, state
