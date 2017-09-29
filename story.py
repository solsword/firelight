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
  def __init__(self, reader, story, start_node):
    self.story = story
    self.on_deck = start_node
    self.decisions = []
    self.nodes = []
    self.reader = reader
    self.story_id = persist.create_new_story(reader, story.name)
    self.status = "starting"

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
    if self.status == "finished":
      raise RuntimeError(
        "Attempted to advance finished story '{}'::{}.".format(
          self.stoy.name,
          self.reader
        )
      )

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

    if self.status == "starting":
      self.status = "unfolding"

    # put the next node on deck:
    nod = self.story.get(next_name)
    if nod is None:
      raise ValueError(
        "Decision '{}' at node '{}' leads to missing node '{}'.".format(
          decision,
          self.on_deck.name,
          next_name
        )
      )

    self.on_deck = nod

    if nod.is_ending():
      self.status = "finished"

    # implement state updates:
    state = persist.get_story_state(self.story_id)
    state["_status_"] = self.status
    for sc in state_changes:
      sc.apply(state)

    persist.update_story_state(self.story_id, state)


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
        "The sea": [ "wading_out", [ "set mood \"desolate\"" ] ],
        "go home": "back_home"
      }
    }
    ```
    """
    return {
      "name": self.name,
      "content": self.content,
      "successors": {
        k: pack(v[0])
          if len(v[1]) == 0
          else pack(v)
          for (k, v) in self.successors.items()
      }
    }

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
            "The sea": [ "wading_out", [ "set mood 'desolate'" ] ],
            "go home": [ "back_home", [ "set mood 'warm'" ] ]
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
      "nodes": pack(self.successors)
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

  def get(node_name):
    """
    Returns the story node with the given name, or None if no such node exists.
    """
    return self.nodes.get(node_name, None)
