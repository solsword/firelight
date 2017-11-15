"""
macro.py

# Introduction

Macro engine for Firelight. Macros look like this:

(if:
  : x < 3: less
  : x = 3: three
  : x > 3: more
)

The macro begins with parentheses-name-colon, has several arguments separated
by ':' characters, and then ends with a closing parenthesis. An extra separator
is allowed before the first argument; to give an empty first argument, use ::
at first (or something like an empty string where applicable).

Macros are expanded when rendering story nodes using story state variables.
Node-local variables start with '_', while system variables both start and end
with '_'. Note that some macros, like (set:), have side effects, so
order-of-expansion can matter. Macros are expanded beginning-to-end of node,
one expansion at a time, so that a series of nested expansions will all happen
before any later expansion.

Note that the name of a story node can be used as a macro, with any arguments
becoming available through the (context:) macro, just as when a link includes
an '&' clause. The text of the node will be inserted in place of the call, and
any macros it contains will expanded immediately, using current variable
values, including _node and _prev (see Automatic Variables below). Note that
such included nodes cannot affect the node-specific variables of the including
node, although they can read these variables. The links of included nodes are
ignored.

Note finally that link traversal text is separate from story node text, and
will only be expanded when the relevant link is traversed, so it's the proper
place to do things like set variables to record choices.

# Expressions in Macros:

Some macros, such as (if:) and (set:), evaluate certain parts of arguments as
expressions. Legal operators in expressions are:

  +, -, *, /, //, %, and **
    Standard mathematical operators, with the same meaning as in Python.

  =,  !=, <, >, <=, and >=
    Standard comparisons; same meaning as in Python

  and, or, and not
    Standard boolean operators; same meaning as in Python.

  &, |, ^, ~
    Bitwise operators; same meaning as in Python.
    
  ., *
    '.' concatenates strings, while '*' multiplies strings as in Python.

  /, //, ~, ~~
    , '/' tests whether the left-hand side contains a (regular expression)
    match of the right-hand side, '//' tests whether the LHS contains a
    (simple) match of the RHS, and '~' performs regular expression replacement
    within the LHS, splitting the RHS on an unescaped '/' into pattern and
    replacement parts. '~~' functions like '~' but treats its arguments as
    simple strings instead of regular expressions. '/', '//', '~', and '~~'
    bind leftward, so several searches/replacements can be listed after an
    original string and they'll apply to it one after the other instead of
    applying to each other.

  ^, ^^
    When applied with a string as the LHS, performs a split operation using the
    RHS to create a list. Examples:
      ```>
      "abc def" ^ " " == ["abc", "def"]
      ```>
      "a.b" ^ "." == ["", "", "", ""]
      ```>
      "a.b" ^^ "." == ["a", "b"]
      ```

  +, *
    Standard list operators; same meaning as in Python.

  .
    Concatenates two lists, where '+' would append the second as an element of
    the first.

  |
    When applied with an array as the LHS, '|' performs a join/reduce
    operation, using the RHS string as a join string and converting each
    element to a string, or using the RHS operator for reduction with its RHS
    as the anchor. Examples:
      ```>
      [True, False, True] | or False == True
      ```>
      [True, False, True] | and True == False
      ```>
      [1, 2, 3, 4] | + 0 == 10
      ```>
      [1, 2, 3, 4] | * 1 == 24
      ```>
      [1, 2, 3, 4] | * 1 == 24
      ```

  !
    Performs an map operation, applying the RHS function to each element of the
    LHS list. TODO: Functions?!?


# Built-in Macros:

The following built-in macros can be used. Note that if a story node shares the
name of a built-in macro, the story node will be used instead.

  (if: condition: result | condition: result | ... | else: result)
    Basic conditional text/evaluation. Expands to the first 'result' text for
    which the associated condition evaluates to True, or to the text of the
    first 'else' case (non-first else cases are ignored; the use of 'else' as a
    variable name is discouraged, as it can't be used alone in a conditional).
    Macros in conditions are expanded only as tested, but it's bad practice to
    put side-effect-inducing macros in conditions in any case. All macros in a
    condition will be expanded before testing, so early-termination of and/or
    statements

  (once: text)
    The given text will only appear (and macros inside will only be expanded)
    on the player's first visit to the containing node. Note that a (once:)
    nested inside an (if:) won't trigger on subsequent node visits even if the
    (if:) kept it from appearing the first time. (once:) is exactly equivalent
    to (if: _first: text).

  (again: text)
    The given text will only appear on return visits to a story node. This is
    exactly equivalent to (if: not _first: text).

  (context: N)
    Inserts the value of the given context variable, counting from 1. Use '&'
    clauses on links to set context, or use extra arguments when calling a node
    as a macro.

  TODO: More of these?

# Automatic Variables:

These node-local variables are available by default when evaluating macros in
addition to the normal story state:

  _context: A list of context values set using either '&' clauses in a link to
            this node, or arguments when this node is called as a macro.
  _prev: The node name of the previous story node.
  _node: The name of the current node.
  _once: Set to True the first time a node is encountered by a player, and
         False on subsequent visits. See also the (once:) and (again:) macros.

  TODO: More of these?
"""

import re

import utils

MACRO_START = re.compile(r"([a-zA-Z_][a-zA-Z_0-9.]\+):")

def expand_all(src, story, state):
  """
  Performs repeated macro-expansion on the given string until convergence.
  Returns a pair of (expanded-text, updated-state).
  """
  last_text = None
  text = src
  while last_text != text:
    last_text = text
    text, state = expand_first(text, story, state)

  return text, state

def expand_first(src, story, state):
  """
  Performs a single pass of macro-expansion on the given string. Returns a pair
  of (expanded-text, updated-state).
  """
  ms = MACRO_START.search(src)
  if not ms: # no matches means no expansion needed
    return src, state
  state = copy.deepcopy(state)

  start = ms.start()

  end = utils.matching_brace(src, start, '(', ')')

  macro_name = ms.group(1)
  macro_content = src[ms.end():end]
  macro_args = utils.split_unquoted(macro_content, delim=':', qc='"')

  if macro_name in story.nodes:
    node = story.nodes[macro_name]

    exp, state = call_node(node, story, state, macro_args)

  else:
    # Must be built-in or from a module:
    if macro_name.count('.') == 1:
      # From a module
      module_name, inner_name = macro_name.split('.')

      if module_name in story.modules:
        module = story.modules[module_name]

        if inner_name in module.nodes:
          node = module.nodes[inner_name]
          exp, state = call_node(node, story, state, macro_args)

        else:
          exp, state = error(
            "Module '{}' doesn't define macro '{}'.".format(
              module_name,
              inner_name
            )
          )

      else:
        exp, state = error(
          "Module '{}' for macro '{}' was not loaded by story '{}'.".format(
            module_name,
            macro_name,
            story.title
          )
        )

    elif macro_name in BUILTINS:
      # A built-in macro
      exp = BUILTINS[macro_name](*macro_args)
    else:
      # Unrecognized macro: expands to error text
      # TODO: Better error text
      exp, state = error("Unrecognized macro '{}'.".format(macro_name))

  return src[:start] + exp + src[end:], state


def call_node(node, story, state, args):
  """
  Expands an entire node in-place, returning a pair expansion-text, modified-
  state. The given arguments are made available via the "_context" variable, as
  during node expansion via a contextual link.
  """
  # Preserve local variables:
  local_vars = {
    v: state[v]
      for v in state
      if v.startswith('_') and not v.endswith('_')
  }

  # Set context:
  state["_context"] = args

  # Fully-expand node text:
  exp, state = expand_all(node.content, story, state)

  # Restore locals:
  state.update(local_vars)

  return exp, state

def error(message, state):
  """
  Returns an expansion-text, updated-state pair for the given error.
  """
  message = "Error: " + message
  exp = "<<{}>>".format(message)
  state["_errors_"].append(message)
  return exp, state
