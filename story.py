"""
story.py

Story functionality including tracking state and making choices. Doesn't deal
with twitter or persistence directly.
"""

class Story:
  """
  Keeps track of story state, and presents bits of content in a stream, waiting
  for user input at branches.
  """
  def __init__(self):
    self.nodes = []

class StoryNode:
  """
  A single node in a story, with content that can fit in a tweet and state
  changes stored as a function.
  """
  def __init__(self, content, update_sate):
    self.content = content
    self.update_state = update_state
