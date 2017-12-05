"""
story.py

Story functionality including tracking state and making choices. Doesn't deal
with twitter directly.
"""

import copy
import re

import editdistance

from packable import pack, unpack
from diffable import diff

import macro


def cmd_title(story, node_name, state):
  return (
    [
      "This story is '{}', by {}.".format(story.title.title(), story.author)
    ],
    node_name,
    state
  )

# TODO: these
STORY_COMMANDS = {
  "/title/": cmd_title,
  "/author/": cmd_title,
}

def highlight_content(content, successors, highlight="bracket"):
  """
  Returns a string to display to the player for the given content, highlighting
  the given successors. The 'highlight' argument controls how options that
  occur within the content are highlighted. Valid values include None (base
  content used as-is), "bracket" (the default; square brackets will be added
  around option words), and "link" (option words will be rendered as HTML
  anchor elements that link to an anchor with their name.)
  """
  content = content
  if highlight == "bracket":
    for opt in successors:
      content = re.sub(
        r"\b{}\b".format(re.escape(opt)),
        lambda _: "[{}]".format(opt), # to treat replacement as a literal
        content
      )
  elif highlight == "link":
    for opt in successors:
      content = re.sub(
        r"\b{}\b".format(re.escape(opt)),
        lambda _: r'<a href="#{}">{}</a>'.format(opt, opt),
        content
      )
  return content


def fuzzy_match(target, options, cutoff=None):
  """
  Returns the best fuzzy match for the given target string against the given
  list of options. Returns a pair (match, edit_distance), using (None, -1) if
  an empty list is given, or if a cutoff is given and the minimum edit distance
  is greater than the cutoff.
  """
  best = (None, -1)
  if target in options:
    return (target, 0)
  for op in options:
    ed = editdistance.eval(target, op)
    if (best[1] < 0 and (cutoff is None or ed <= cutoff)) or ed < best[1]:
      best = (op, ed)

  return best


class StoryNode:
  """
  A single node in a story, with a name, content that can fit in a tweet, and a
  dictionary of successors that maps option names to (next_name, state_update)
  pairs. Note that node names must be globally unique.
  """
  def __init__(self, name, content, successors=None):
    self.name = name
    self.content = content
    self.successors = successors or {}

  def __str__(self):
    return "'{}' [ {} ] {{ {} }}".format(
      self.name,
      self.content,
      ", ".join(key for key in self.successors)
    )

  def __hash__(self):
    return (
      hash(self.name) * 17
    + hash(self.content) * 11
    + sum(
        (hash(k) + hash(v)) * (3+i)
          for i, (k, v) in enumerate(self.successors.items())
      )
  )

  def __eq__(self, other):
    if not isinstance(other, StoryNode):
      return False
    if self.name != other.name:
      return False
    if self.content != other.content:
      return False
    if self.successors != other.successors:
      return False
    return True

  def _diff_(self, other):
    results = []
    if self.name != other.name:
      results.append("names ('{}' =/= '{}')".format(self.name, other.name))
    if self.content != other.content:
      results.append(
        "content ('{}' =/= '{}')".format(self.content, other.content)
      )
    if self.successors != other.successors:
      results.extend([
        "successors: {}".format(d)
          for d in diff(self.successors, other.successors)
      ])
    return results

  def _pack_(self):
    """
    Returns a simplified version suitable for json.dumps. See packable.py.

    Example:
    ```
    StoryNode(
      "at_the_beach",
      (
        "You walk along the beach, watching seabirds dance with the waves. "
        "The sea calls to you, but you should go home."
      ),
      {
        "The sea": [ "wading_out", "(set: mood : desolate)" ],
        "go home": "back_home"
      }
    )
    ```
    {
      "name": "at_the_beach",
      "content": "You walk along the beach, watching seabirds dance with the waves. The sea calls to you, but you should go home.",
      "successors": {
        "The sea": [ "wading_out", "(set: mood : desolate)" ],
        "go home": "back_home"
      }
    }
    ```
    """
    result = {
      "name": self.name,
      "content": self.content,
    }
    if self.successors:
      result["successors"] = self.successors
    return result

  def _unpack_(obj):
    """
    Creates a StoryNode from a simple object (see packable.py).
    """
    return StoryNode(
      obj["name"],
      obj["content"],
      obj["successors"] if "successors" in obj else {}
    )

  def is_ending(self):
    """
    Whether or not this node is an ending node.
    """
    return len(self.successors) == 0

class Story:
  """
  A Story is just a constellation of StoryNodes with an author, a title, and
  some default initial state.
  """
  def __init__(
    self,
    title,
    author,
    start,
    nodes,
    modules=None,
    setup=None,
    module_finder=None
  ):
    self.title = title
    self.author = author
    self.start = start
    self.nodes = nodes
    self.modules = modules or []
    self.setup = setup or {}
    self.current_node_text = ""
    self.module_finder = module_finder
    if self.start not in self.nodes:
      raise ValueError(
        "Start node '{}' not found among story nodes.".format(self.start)
      )

  def __hash__(self):
    return (
      hash(self.title) * 17
    + hash(self.author) * 5
    + hash(self.start) * 11
    + sum(hash(n) * (3+i) for i, n in enumerate(self.nodes.values()))
  )

  def __eq__(self, other):
    if not isinstance(other, Story):
      return False
    if self.title != other.title:
      return False
    if self.author != other.author:
      return False
    if self.nodes != other.nodes:
      return False
    return True

  def _diff_(self, other):
    if self.title != other.title:
      return ["titles ('{}' =/= '{}')".format(self.title, other.title)]
    if self.author != other.author:
      return ["authors ('{}' =/= '{}')".format(self.author, other.author)]
    if self.nodes != other.nodes:
      return ["nodes: {}".format(d) for d in diff(self.nodes, other.nodes)]
    return []

  def __str__(self):
    return "Story('{}')".format(self.title)

  def _pack_(self):
    """
    Returns a simplified version suitable for json.dumps. See packable.py.

    Example:
    ```
    Story(
      "The Ocean Calls",
      "Anonymous",
      "at_the_beach",
      {
        "at_the_beach":
          StoryNode(
            "at_the_beach",
            (
            "You walk along the beach, watching seabirds dance with the waves. "
            "The sea calls to you, but you should go home."
            ),
            {
              "The sea": [ "wading_out", "(set: mood : desolate)" ],
              "go home": [ "back_home", "(set: mood : warm)" ]
            }
          ),
        "wading_out":
          StoryNode(
            "wading_out",
            "You wade out into the icy water, shivering with anticipation."
          ),
        "back_home":
          StoryNode(
            "back_home",
            "You step into the warmth of your living room and lock the door."
          )
      }
    )
    ```
    {
      "title": "The Ocean Calls",
      "author": "Anonymous",
      "start": "at_the_beach",
      "nodes": {
        "at_the_beach": {
          "name": "at_the_beach",
          "content": "You walk along the beach, watching seabirds dance with the waves. The sea calls to you, but you should go home.",
          "successors": {
            "The sea": [ "wading_out", "(set: mood : desolate)" ],
            "go home": [ "back_home", "(set: mood : warm)" ]
          }
        },
        "wading_out": {
          "name": "wading_out",
          "content": "You wade out into the icy water, shivering with anticipation."
        },
        "back_home": {
          "name": "back_home",
          "content": "You step into the warmth of your living room and lock the door."
        },
      }
    }
    ```
    """
    result = {
      "title": self.title,
      "author": self.author,
      "start": self.start,
      "nodes": pack(self.nodes)
    }
    if self.modules:
      result["modules"] = self.modules
    if self.setup:
      result["setup"] = self.setup

    return result

  def _unpack_(obj):
    """
    Creates a StoryNode from a simple object (see packable.py). Note that the
    unpacked story node will not have a module finder.
    """
    return Story(
      obj["title"],
      obj["author"],
      obj["start"],
      {
        k: unpack(obj["nodes"][k], StoryNode)
          for k in obj["nodes"]
      },
      modules=obj["modules"] if "modules" in obj else None,
      setup=obj["setup"] if "setup" in obj else None
    )

  def set_module_finder(self, finder):
    """
    Sets the module finder.
    """
    self.module_finder = finder

  def get(self, node_name):
    """
    Returns the story node with the given name, or None if no such node exists.
    """
    return self.nodes.get(node_name, None)

  def initial_state(self):
    """
    Returns the initial state for the this story.
    """
    result = copy.deepcopy(self.setup)
    result["_title_"] = self.title
    result["_author_"] = self.author
    result["_status_"] = "beginning"
    result["_visited_"] = {}
    result["_errors_"] = []
    return result

  def visit(self, state, node, prev):
    """
    Returns an updated state accounting for a visit to the given node. Call
    before display_node to set automatic variables. Use node names as
    arguments, not actual nodes.
    """
    state["_prev"] = prev
    state["_node"] = node
    if node in state["_visited_"]:
      state["_once"] = False
      state["_visited_"][node] += 1
    else:
      state["_once"] = True
      state["_visited_"][node] = 1
    return state

  # TODO: Prefix-based option selection as promised in help.flj
  def advance(self, node_name, state, decision, highlight="bracket"):
    """
    Takes a decision (naming an option at the given node) and figures out how
    the story continues, returning a tuple of continuation texts list, new
    current node, and new story state. The 'highlight' argument is passed
    through to the highlight_content function. Note that the state argument may
    be modified.
    """
    if node_name not in self.nodes:
      fresh_state = self.initial_state()
      fresh_state = self.visit(fresh_state, self.start, None)
      origin, fresh_state = self.display_node(
        self.nodes[self.start],
        fresh_state,
        highlight=highlight
      )
      self.current_node_text = origin
      return (
        [
          "Sorry, I've gotten confused at '{}' in '{}'.".format(
            node_name,
            self.title
          ),
          "Starting over from the beginning.",
          origin
        ],
        self.start,
        fresh_state
      )

    node = self.nodes[node_name]
    if state["_status_"] == "finished":
      self.current_node_text = "This telling has come to an end."
      return (
        [ "This telling has come to an end." ],
        node_name,
        state
      )

    if decision.lower() in STORY_COMMANDS:
      cmd = STORY_COMMANDS[decision.lower()]
      responses, new_node, new_state = cmd(self, node_name, state)
      return (
        responses,
        new_node,
        new_state
      )

    matching_key, _ = fuzzy_match(
      decision.lower(),
      [ k.lower() for k in node.successors.keys() ],
      cutoff=config.ACTION_DISTANCE_THRESHOLD
    )

    if matching_key is None:
      # TODO: Better here?
      return (
        [
          "I'm not sure what you mean by '{}'.".format(
            decision.lower()
          ),
          self.current_node_text # Don't re-run the node
        ],
        node_name,
        state
      )

    next_name = node.successors[matching_key][0]
    transition_text, new_state = self.display_transition(
      node,
      matching_key,
      state
    )

    if new_state["_status_"] == "beginning":
      new_state["_status_"] = "unfolding"

    # get the next node:
    next_node = self.get(next_name)
    if next_node is None:
      # TODO: Log these errors!
      fresh_state = self.initial_state()
      fresh_state = self.visit(fresh_state, self.start, None)
      origin, fresh_state = self.display_node(
        self.nodes[self.start],
        fresh_state,
        highlight=highlight
      )
      fresh_state = self.visit(fresh_state, self.start)
      self.current_node_text = origin
      return (
        [
          "Sorry, I've forgotten '{}' which should come after '{}'.".format(
            next_node,
            node_name
          ),
          "Starting over from the beginning.",
          format_node(self.nodes[self.start], highlight=highlight)
        ],
        self.start,
        fresh_state
      )

    if next_node.is_ending():
      new_state["_status_"] = "finished"

    new_state = self.visit(new_state, next_node.name, node_name)
    next_text, new_state = self.display_node(
      next_node,
      new_state,
      context=None, #TODO: links-with-context!!!
      highlight=highlight
    )
    self.current_node_text = next_text
    return (
      [ transition_text, next_text ],
      next_name,
      new_state
    )

  def display_node(self, node, state, context=None, highlight="bracket"):
    """
    Computes display text for the given node, including evaluating the node's
    content. Returns a (display_text, updated_state) pair. The 'context'
    argument is passed as the _context variable during node evaluation, while
    the 'highlight' variable controls how options within the text are
    highlighted (see highlight_content below) and the 'module_finder' argument
    is passed into eval_text.
    """
    if isinstance(node, str):
      node = self.get(node)
      text, new_state = macro.eval_text(
        node.content,
        self,
        state,
        context,
        self.module_finder
      )
    return (
      highlight_content(text, node.successors, highlight=highlight),
      new_state
    )

  def display_transition(self, node, option, state):
    """
    Computes transition text for taking the given option at the given node.
    Similar to display_node (see above).
    """
    transition_text = node.successors[option][1]
    result, new_state = macro.eval_text(
      transition_text,
      self,
      state,
      self.module_finder
    )
    return result.strip(), new_state
