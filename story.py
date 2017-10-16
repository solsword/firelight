"""
story.py

Story functionality including tracking state and making choices. Doesn't deal
with twitter directly.
"""

import copy
import re

from state import StateChange

from packable import pack, unpack
from diffable import diff


# TODO: these
STORY_COMMANDS = {
  "/title/": None,
  "/status/": None
}

def format_node(node, highlight="bracket"):
  """
  Returns a string to display to the player for the given story node. The
  'highlight' argument controls how options that occur within the content are
  highlighted. Valid values include None (base content used as-is),
  "bracket" (the default; square brackets will be added around option
  words), and "link" (option words will be rendered as HTML anchor elements
  that link to an anchor with their name.)
  """
  content = node.content
  if highlight == "bracket":
    for opt in node.successors:
      content = re.sub(r"\b{}\b".format(opt), "[{}]".format(opt), content)
  elif highlight == "link":
    for opt in node.successors:
      content = re.sub(
        r"\b{}\b".format(opt),
        r'<a href="#{}">{}</a>'.format(opt, opt),
        content
      )
  return content


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
    for k in self.successors:
      if isinstance(self.successors[k], str):
        self.successors[k] = (self.successors[k], [])

  def __str__(self):
    return "[ {} ] {{ {} }}".format(
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
    if self.name != other.name:
      return [ "names ('{}' =/= '{}')".format(self.name, other.name) ]
    if self.content != other.content:
      return [ "content ('{}' =/= '{}')".format(self.content, other.content) ]
    if self.successors != other.successors:
      return [
        "successors: {}".format(d)
          for d in diff(self.successors, other.successors)
      ]
    return []

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
        "The sea": ( "wading_out", [ SetValue("mood", "desolate") ] ),
        "go home": ( "back_home", [] )
      }
    )
    ```
    {
      "name": "at_the_beach",
      "content": "You walk along the beach, watching seabirds dance with the waves. The sea calls to you, but you should go home.",
      "successors": {
        "The sea": [ "wading_out", [ "set mood \\"desolate\\"" ] ],
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
      result["successors"] = {
        k: pack(v[0])
          if len(v[1]) == 0
          else pack(v)
          for (k, v) in self.successors.items()
      }
    return result

  def _unpack_(obj):
    """
    Creates a StoryNode from a simple object (see packable.py).
    """
    successors = None
    if "successors" in obj:
      successors = {}
      for key in obj["successors"]:
        if isinstance(obj["successors"][key], str):
          successors[key] = (
            obj["successors"][key],
            []
          )
        else:
          nxt, changes = obj["successors"][key]
          successors[key] = (
            nxt,
            [ unpack(sc, StateChange) for sc in changes ]
          )

    return StoryNode(
      obj["name"],
      obj["content"],
      successors
    )

  def is_ending(self):
    """
    Whether or not this node is an ending node.
    """
    return len(self.successors) == 0

class Story:
  """
  A Story is just a constellation of StoryNodes, 
  """
  def __init__(self, name, start, nodes):
    self.name = name
    self.start = start
    self.nodes = nodes
    if self.start not in self.nodes:
      raise ValueError(
        "Start node '{}' not found among story nodes.".format(self.start)
      )

  def __hash__(self):
    return (
      hash(self.name) * 17
    + hash(self.start) * 11
    + sum(hash(n) * (3+i) for i, n in enumerate(self.nodes.values()))
  )

  def __eq__(self, other):
    if not isinstance(other, Story):
      return False
    if self.name != other.name:
      return False
    if self.nodes != other.nodes:
      return False
    return True

  def _diff_(self, other):
    if self.name != other.name:
      return ["names ('{}' =/= '{}')".format(self.name, other.name)]
    if self.nodes != other.nodes:
      return ["nodes: {}".format(d) for d in diff(self.nodes, other.nodes)]
    return []

  def __str__(self):
    return "Story('{}')".format(self.name)

  def _pack_(self):
    """
    Returns a simplified version suitable for json.dumps. See packable.py.

    Example:
    ```
    Story(
      "The Ocean Calls",
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
              "The sea": ( "wading_out", [ SetValue("mood", "desolate") ] ),
              "go home": ( "back_home", [ SetValue("mood", "warm") ] )
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
      "name": "The Ocean Calls",
      "start": "at_the_beach",
      "nodes": {
        "at_the_beach": {
          "name": "at_the_beach",
          "content": "You walk along the beach, watching seabirds dance with the waves. The sea calls to you, but you should go home.",
          "successors": {
            "The sea": [ "wading_out", [ "set mood \\"desolate\\"" ] ],
            "go home": [ "back_home", [ "set mood \\"warm\\"" ] ]
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
    return {
      "name": self.name,
      "start": self.start,
      "nodes": pack(self.nodes)
    }

  def _unpack_(obj):
    """
    Creates a StoryNode from a simple object (see packable.py).
    """
    return Story(
      obj["name"],
      obj["start"],
      {
        k: unpack(obj["nodes"][k], StoryNode)
          for k in obj["nodes"]
      }
    )

  def get(self, node_name):
    """
    Returns the story node with the given name, or None if no such node exists.
    """
    return self.nodes.get(node_name, None)

  def initial_state(self):
    """
    Returns the initial state for the this story.
    """
    # TODO: More fancy here
    return {
      "_name_": self.name,
      "_status_": "beginning"
    }

  def advance(self, node_name, state, decision, highlight="bracket"):
    """
    Takes a decision (naming an option at the given node) and figures out how
    the story continues, returning a tuple of continuation texts list, new
    current node, and new story state. The 'highlight' argument is passed
    through to the format_node function. Note that the state argument may be
    modified.
    """
    if node_name not in self.nodes:
      return (
        [
          "Sorry, I've gotten confused at '{}' in '{}'.".format(
            node_name,
            self.name
          ),
          "Starting over from the beginning.",
          format_node(self.nodes[self.start], highlight=highlight)
        ],
        self.start,
        self.initial_state()
      )

    node = self.nodes[node_name]
    if state["_status_"] == "finished":
      return (
        [ "This telling has come to an end." ],
        node_name,
        state
      )

    if decision.lower() in STORY_COMMANDS:
      # TODO: What here?
      return (
        [ "Command {}.".format(decision) ],
        node_name,
        state
      )

    matching_key = None
    for k in node.successors:
      if k.lower() == decision.lower():
        matching_key = k

    if matching_key is None:
      # TODO: Better here?
      return (
        [
          "'{}' is not a valid decision at this point in the story.".format(
            decision.lower()
          ),
          format_node(node, highlight=highlight)
        ],
        node_name,
        state
      )

    next_name, state_changes = node.successors[matching_key]

    if state["_status_"] == "beginning":
      state["_status_"] = "unfolding"

    # get the next node:
    next_node = self.get(next_name)
    if next_node is None:
      # TODO: Log these errors!
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
        self.initial_state()
      )

    if next_node.is_ending():
      state["_status_"] = "finished"

    # implement state updates:
    for sc in state_changes:
      sc.apply(state)

    return (
      [ format_node(next_node, highlight=highlight) ],
      next_name,
      state
    )
