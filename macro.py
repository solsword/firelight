"""
macro.py

# Introduction

Macro engine for Firelight. Macros look like this:

(if:
  | x < 3: less
  | x = 3: three
  | x > 3: more
)

The macro begins with parentheses-name-colon, has several arguments separated
by '|' characters, and then ends with a closing parenthesis. An extra separator
is allowed before the first argument; to give an empty first argument, use ||
at first (or something like an empty string where applicable).

Macros are expanded when rendering story fragments using story state variables.
Fragment-local variables start with '_'. Note that some macros, like (set:),
have side effects, so order-of-expansion can matter. Macros are expanded
beginning-to-end of fragment, one expansion at a time, so that a series of
nested expansions will all happen before any later expansion.

Note that the name of a story fragment can be used as a macro, with any
arguments becoming available through the (context:) macro, just as when a link
includes an '&' clause. The text of the fragment, with macros expanded as
usual, will be inserted in place of the call.

Note finally that link traversal text is separate from story fragment text, and
will only be expanded when the relevant link is traversed, so it's the proper
place to do things like set variables to record choices.

# Expressions in macros:

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
    RHS to create a list.
    ```
    "abc def" ^ " " == ["abc", "def"]
    "a.b" ^ "." == ["", "", "", ""]
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
      ```
      [True, False, True] | or False == True
  and [True, False, True] | and True == False
  and [1, 2, 3, 4] | + 0 == 10
  and [1, 2, 3, 4] | * 1 == 24
      ```

  !
    Performs an map operation, applying the RHS function to each element of the
    LHS list.


# Built-in macros:

The following built-in macros can be used. Note that if a story fragment shares
the name of a built-in macro, the story fragment will be used instead.

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
    on the player's first visit to the containing fragment. Note that a (once:)
    nested inside an (if:) won't trigger on subsequent fragment visits even if
    the (if:) kept it from appearing the first time. (once:) is exactly
    equivalent to (if: _first: text).

  (again: text)
    The given text will only appear on return visits to a story fragment. This
    is exactly equivalent to (if: not _first: text).

  TODO: More of these?

# Automatic variables:

These fragment-local variables are available by default when evaluating macros
in addition to the normal story state:

  _prev: the fragment name of the previous story fragment.
  _frag: the name of the current fragment.
  _once: set to True the first time a fragment is encountered by a player, and
         False on subsequent visits. See also the (once:) and (again:) macros.
  TODO: More of these?
"""

import re

import utils

MACRO_START = re.compile(r"([a-zA-Z_][a-zA-Z_0-9.]\+:")

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
  start = ms.start()

  return text, state
