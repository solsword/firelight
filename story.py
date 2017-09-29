"""
story.py

Story functionality including tracking state and making choices. Doesn't deal
with twitter directly.
"""

import persist
from state import StateChange

from packable import pack, unpack

class Telling:
  """
  Keeps track of story state, and presents bits of content in a stream, waiting
  for user input at branches. Structure is determined by node links.
  """
  def __init__(self, reader, start_node):
    self.on_deck = start_node
    self.decisions = []
    self.nodes = []
    self.story_id = persist.create_new_story(reader, start_node.name)

  def current_content(self, highlight="bracket"):
    """
    Returns a string to display to the player for the current story node. The
    'highlight' argument controls how options that occur within the content are
    highlighted. Valid values include None (base content used as-is),
    "bracket" (the default; square brackets will be added around option
    words), and "link" (option words will be rendered as HTML anchor elements
    that link to an anchor with their name.)
    """
    content = self.on_deck.content
    if highlight == "bracket":
      for opt in self.on_deck.successors:
        content = re.sub(r"\b{}\b".format(opt), "[{}]".format(opt), content)
    elif highlight == "link":
      for opt in self.on_deck.successors:
        content = re.sub(
          r"\b{}\b".format(opt),
          r'<a href="#{}">{}</a>'.format(opt, opt),
          content
        )
    return content

  def advance(self, decision):
    """
    Takes a decision (naming an option at the current node) and advances the
    story, taking the currently-on-deck node and adding it to the history along
    with the decision reached, and putting the next node on deck after
    implementing state changes.
    """
    if decision not in self.on_deck.successors:
      raise ValueError(
        "Invalid decision '{}' at node '{}'.".format(
          decision,
          self.on_deck.name
        )
      )
    next_name, state_changes = self.on_deck.successors[decision]

    self.nodes.append(self.on_deck)
    self.decisions.append(decision)

    if next_name not in NODE_REGISTRY:
      raise ValueError(
        "Decision '{}' at node '{}' leads to missing node '{}'.".format(
          decision,
          self.on_deck.name,
          next_name
        )
      )

    # implement state updates:
    self.on_deck = NODE_REGISTRY[next_name]

    state = persist.get_story_state(self.story_id)
    for sc in state_changes:
      sc.apply(state)

    persist.update_story_state(self.story_id, state)


# Holds all loaded StoryNode objects by name:
NODE_REGISTRY = {}

class StoryNode:
  """
  A single node in a story, with a name, content that can fit in a tweet, and a
  dictionary of successors that maps option names to (next_name, state_update)
  pairs. Note that node names must be globally unique.
  """
  def __init__(self, name, content, successors):
    if name in NODE_REGISTRY:
      raise ValueError("A story node named '{}' already exists.".format(name))
    NODE_REGISTRY[name] = self
    self.name = name
    self.content = content
    self.successors = successors

  def __str__(self):
    return "[ {} ] {{ {} }}".format(
      self.content,
      ", ".join(key for key in self.successors)
    )

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
        "go home": ( "back_home", [ SetValue("mood", "warm") ] )
      }
    )
    ```
    {
      "name": "at_the_beach",
      "content": "You walk along the beach, watching seabirds dance with the waves. The sea calls to you, but you should go home.",
      "successors": {
        "The sea": [ "wading_out", [ "set mood \"desolate\"" ] ],
        "go home": [ "back_home", [ "set mood \"warm\"" ] ]
      }
    }
    ```
    """
    return {
      "name": self.name,
      "content": self.content,
      "successors": pack(self.successors)
    }

  def _unpack_(obj):
    """
    Creates a StoryNode from a simple object (see packable.py).
    """
    successors = {}
    for key in obj["successors"]:
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
