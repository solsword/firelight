"""
story.py

Story functionality including tracking state and making choices. Doesn't deal
with twitter directly.
"""

import persist

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
    state_changes, next_name = self.on_deck.successors[decision]

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
    for sc in unpack(state_changes):
      state = sc(state)

    persist.update_story_state(self.story_id, state)

NODE_REGISTRY = {}

class StoryNode:
  """
  A single node in a story, with a name, content that can fit in a tweet, and a
  dictionary of successors that maps option names to (state_update, next_name)
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
