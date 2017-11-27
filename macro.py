"""
macro.py

See modules/help.fls for a description of the macro system.
"""

import re
import copy

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
            ),
            state
          )

      else:
        exp, state = error(
          "Module '{}' for macro '{}' was not loaded by story '{}'.".format(
            module_name,
            macro_name,
            story.title
          ),
          state
        )

    elif macro_name in BUILTINS:
      # A built-in macro
      exp = BUILTINS[macro_name](*macro_args)
    else:
      # Unrecognized macro: expands to error text
      # TODO: Better error text
      exp, state = error("Unrecognized macro '{}'.".format(macro_name), state)

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
      value = BUILTINS[name](*args)
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
