"""
parse.py

Story format parsing for Firelight. Reads markup similar to Markdown and
translates it into simple Python structures suitable for unpacking.
"""

import re
import json

import utils

from packable import pack, unpack

from story import StoryNode, Story

META_KEY = re.compile(r"^% ([A-Za-z0-9_.-][A-Za-z0-9_.-]*):", re.MULTILINE)
COMMENT = re.compile(r"``.*$", re.MULTILINE)
NODE_START = re.compile(
  r"^\s*#\s*([A-Za-z0-9_.-][A-Za-z0-9_.-]*)\s*$",
  re.MULTILINE
)

def remove_comments(src):
  """
  Removes comments from the given source, returning a revised string.
  """
  return COMMENT.sub("", src)

def normalize_newlines(src):
  """
  Returns a version of the given text where all newline variants have been
  converted to simple '\\n'.
  """
  return src.replace('\n\r', '\n').replace('\r\n', '\n').replace('\r', '\n')

def reflow(src):
  """
  Parses manually broken lines and reflows them such that only places where
  there were 2+ newlines are counted as newlines (a single newline each) and
  places with a single newline are now just spaces.
  """
  # get rid of extra newlines at front and back:
  src = re.sub("^\s*([^\n])", r"\1", src)
  src = re.sub("([^\n])\s*$", r"\1", src)
  # get rid of newlines between non-empty lines:
  src = re.sub("([^\n])[ \t]*\n[ \t]*([^\n])", r"\1 \2", src)
  # filter multiple newlines down to one:
  src = re.sub("\n\s*", "\n", src)
  return src

def parse_metadata(src):
  """
  Parses the initial metadata block of an .fls file, returning a pair
  containing a dictionary of metadata and a metadata-free source text. The
  metadata block must appear at the top of the file, and each line must start
  with a percent sign.

  All fields will be parsed as string keys/values, stripping whitespace from
  both ends. The exception is the 'state' field, whose value will be passed
  through json.loads (after stripping '%' characters from the start of each
  line). If the same field name is given multiple times, the last one will
  override all earlier ones.

  Blank lines are allowed within the metadata block, and are ignored
  completely; their use is not suggested. Fields may be given in any order;
  each field ends when a line begins with a percent sign, followed by a single
  space and then a word followed by a colon. Use indentation to continue values
  over multiple lines; any indentation after the starting '%' on a line is
  removed from resulting values, as are any spaces at the beginning and end of
  a line, although a single space is inserted between each line of a multi-line
  value.

  Macro expansion does not occur within metadata fields.
  
  Examples:

    ```?
      parse_metadata('''
      % title: The Title
      % author: The Author
      % start: start_node_name
      % note: Note text.
      %  Multiple lines may be indented.
      % other_key: some made-up value
      % state: {
      %   "this is": "the starting story state",
      %   "it must be in": "JSON format",
      %   "the '%' at the beginning of each line": "will be removed"
      % }
      ''')
    ```=
    (
      {
        'title': 'The Title',
        'author': 'The Author',
        'start': 'start_node_name',
        'note': 'Note text. Multiple lines may be indented.',
        'other_key': 'some made-up value',
        'state': {
          'this is': 'the starting story state',
          'it must be in': 'JSON format',
          "the '%' at the beginning of each line": 'will be removed'
        },
        'modules': []
      },
      ''
    )
    ```?
parse_metadata(
  remove_comments('''
% title: Mushrooms in Autumn
% author: Peter Mawhorter
% start: trail
% modules: [ "inv" ]
% note: Mushroom placement and appearances based on the "Field Guide to Common
%   Macrofungi in Eastern Forests and their Ecosystem Functions" by Ostry,
%   Anderson, and O'Brien of the United States Department of Agriculture Forest
%   Service (General Technical Report NRS-79) General disclaimer: This is a
%   work of fiction and is not intended to aid in identifying edible mushrooms.
%   NEVER eat a mushroom unless you are absolutely certain it is not poisonous,
%   as many edible species look very similar to poisonous ones, and as a result
%   fatal poisonings occur worldwide every year.
% state: {
%  "lost": 0,
%  "worry": 0, `` TODO: Use this value!
%  "properties": {
%    "smoky-polypore": "inedible",
%    "bears-head-tooth": "choice",
%    "turkey-tail": "inedible",
%    "diamond-polypore": "too-old",
%    "": ""
%  },
%  "inv-desc": {
%    "spade": "Your trusty spade.",
%    "bears-head-tooth": "A shaggy mass of branching white tendrils with brownish tips.",
%    "smoky-polypore": "Several leathery strips of fungus ripped from their base, white on top and dark gray on the bottom.",
%    "turkey-tail": "Several pretty striped brown frills with white edges, still clinging to a few pieces of dead bark.",
%    "diamond-polypore": "A few creamy-yellow trumpet-shaped mushrooms with delicate white honeycomb-lattice frills beneath.",
%    "": ""
%  },
%  "inv-cat": {
%    "spade": "tool",
%    "bears-head-tooth": "mushroom",
%    "smoky-polypore": "mushroom"
%  },
%  "inv": [
%    { "id": "spade", "#": 1 }
%  ]
%}
hello
''')
)
    ```=
    (
      {
        'title': 'Mushrooms in Autumn',
        'author': 'Peter Mawhorter',
        'start': 'trail',
        'modules': [ "inv" ],
        'note': 'Mushroom placement and appearances based on the "Field Guide to Common Macrofungi in Eastern Forests and their Ecosystem Functions" by Ostry, Anderson, and O\\'Brien of the United States Department of Agriculture Forest Service (General Technical Report NRS-79) General disclaimer: This is a work of fiction and is not intended to aid in identifying edible mushrooms. NEVER eat a mushroom unless you are absolutely certain it is not poisonous, as many edible species look very similar to poisonous ones, and as a result fatal poisonings occur worldwide every year.',
        'state': {
          "lost": 0,
          "worry": 0,
          "properties": {
            "smoky-polypore": "inedible",
            "bears-head-tooth": "choice",
            "turkey-tail": "inedible",
            "diamond-polypore": "too-old",
            "": ""
          },
          "inv-desc": {
            "spade": "Your trusty spade.",
            "bears-head-tooth": "A shaggy mass of branching white tendrils with brownish tips.",
            "smoky-polypore": "Several leathery strips of fungus ripped from their base, white on top and dark gray on the bottom.",
            "turkey-tail": "Several pretty striped brown frills with white edges, still clinging to a few pieces of dead bark.",
            "diamond-polypore": "A few creamy-yellow trumpet-shaped mushrooms with delicate white honeycomb-lattice frills beneath.",
            "": ""
          },
          "inv-cat": {
            "spade": "tool",
            "bears-head-tooth": "mushroom",
            "smoky-polypore": "mushroom"
          },
          "inv": [
            { "id": "spade", "#": 1 }
          ]
        }
      },
      'hello\\n'
    )
    ```
  """
  # Default values:
  metadata = {
    "title": "Untitled",
    "author": "Unknown",
    "start": "Error: you must specify a starting story node.",
    "modules": "[]",
    "state": "{}"
  }
  leftovers = ""
  lines = src.split('\n')
  current_key = None
  for i, line in enumerate(lines):
    if line.strip() == '':
      continue
    elif line[0] == '%':
      match = META_KEY.search(line)
      if match:
        current_key = match.group(1)
        metadata[current_key] = line[match.end():].strip()
      elif current_key:
        metadata[current_key] += ' ' + line[1:].strip()
      else:
        continue # ignore this line
    else:
      break

  metadata["state"] = json.loads(metadata["state"])
  metadata["modules"] = json.loads(metadata["modules"])
  return metadata, '\n'.join(lines[i:])

def parse_first_node(src):
  """
  Takes a chunk of story source and parses the first node from it (which should
  start immediately at the top of the source modulo comments and empty space).

  Returns (None, src) if there isn't a node definition present, or the parsed
  node plus the remaining source if there is.

  Example:

  ```
  StoryNode(
    "at_the_beach",
    "You walk along the beach, watching seabirds dance with the waves. The sea calls to you, but you should go home.",
    {
      "The sea": ["wading_out", "(set: mood | desolate)"],
      "go home": ["back_home", "(set: mood | warm)"]
    }
  )
  ```
  # at_the_beach

  You walk along the beach, watching seabirds dance with the waves. [[The
  sea|wading_out|(set: mood | desolate)]] calls to you, but you should [[go
  home|back_home|(set: mood | warm)]].
  ```

  """
  src = src.strip()
  first = NODE_START.search(src)
  # No node found:
  if not first or first.start() != 0:
    return (None, src)

  node = {}

  # Search for the next node, or else use the end of the source:
  second = NODE_START.search(src, pos=first.end())
  if second:
    node_end = second.start()
  else:
    node_end = len(src)

  # Grab the name and content:
  node["name"] = first.group(1)
  content = reflow(src[first.end():node_end])
  leftovers = src[node_end:]

  # Find and transform all links in the text, replacing them with their display
  # text and creating link entries for each. Note that if the display text is
  # not unique, all instances within the node will be highlighted.
  link_extents = []
  i = 0
  while i < len(content) - 1:
    i += 1 # we intentionally skip i = 0 since we match the second '['
    if content[i-1:i+1] == "[[":
      try:
        close = utils.matching_brace(content, i, '[', ']')
      except utils.UnmatchedError:
        # TODO: Print a warning here?
        continue

      # Push to create reverse ordering so link replacement doesn't change
      # indices of earlier link_extents.
      link_extents.insert(0, (i+1, close))

      # jump ahead to the end of this link
      i = close

  node["successors"] = {}
  for start, end in link_extents:
    # Ordering is last-to-first, so that replacement here doesn't affect
    # indices of earlier links.
    contents = content[start:end]
    contents = contents.strip()
    # TODO: Error if this strip results in an empty string?

    # First, figure out display text:
    if contents[0] == '"':
      end, val = utils.string_literal(contents, 0, '"')
      if '|' in contents[end:]:
        display_end = contents.index('|',end)
        display = val + contents[end:display_end]
      else:
        display_end = len(contents)
        display = val + contents[end:]
    else:
      try:
        display_end = contents.index('|')
        display = contents[:display_end]
      except ValueError:
        display_end = len(contents)
        display = contents

    # Next figure out the link destination:
    if display_end < len(contents):
      try:
        dest_end = contents.index('|', display_end+1)
        destination = contents[display_end+1:dest_end].strip()
        if destination == "":
          destination = display
      except ValueError:
        dest_end = len(contents)
        destination = contents[display_end+1:].strip()
    else:
      destination = display
      dest_end = len(contents)

    # Finally, grab the transition text:
    transition = contents[dest_end+1:].strip()

    # Revise the source to replace the link literal with its display text:
    content = content[:start-2] + display + content[end+2:]

    # Add to our links information:
    if transition:
      node["successors"][display] = [destination, transition]
    else:
      node["successors"][display] = destination

  # Put the revised content into our node:
  node["content"] = content

  return (unpack(node, StoryNode), leftovers)


def parse_story(src):
  """
  Parses a Story object from the contents of an .fls file. Example:

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
            "The sea": [ "wading_out", "(set: mood | desolate)" ],
            "go home": [ "back_home", "(set: mood | warm)" ]
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
  % title: The Ocean Calls
  % author: Anonymous
  % start: at_the_beach

  # at_the_beach

  You walk along the beach, watching seabirds dance with the waves. [[The
  sea|wading_out|(set: mood | desolate)]] calls to you, but you should [[go
  home|back_home|(set: mood | warm)]].

  # wading_out

  You wade out into the icy water, shivering with anticipation.

  # back_home

  You step into the warmth of your living room and lock the door.
  ```
  """
  # Get rid of comments and normalize newlines:
  src = remove_comments(normalize_newlines(src))

  # Parse metadata block:
  meta, src = parse_metadata(src)

  # Parse story nodes:
  nodes = []
  sn, src = parse_first_node(src)
  while sn:
    nodes.append(sn)
    sn, src = parse_first_node(src)

  # Return result:
  return Story(
    meta["title"],
    meta["author"],
    meta["start"],
    { node.name: node for node in nodes}, 
    meta["state"]
  )


def render_node(node):
  """
  Renders an individual story node into a format that could be parsed with
  parse_first_node.
  """
  # TODO: Flow into 80 characters here?
  content = node.content
  for display in node.successors:
    if isinstance(node.successors[display], str):
      destination = node.successors[display]
      if destination == display:
        content = re.sub(
          r"\b{}\b".format(re.escape(display)),
          lambda _: "[[{}]]".format(display), # lambda -> use result literally
          content
        )
      else:
        content = re.sub(
          r"\b{}\b".format(re.escape(display)),
          lambda _: "[[{}|{}]]".format(display, destination),
          content
        )
    else:
      destination, transition = node.successors[display]
      if destination == display:
        content = re.sub(
          r"\b{}\b".format(re.escape(display)),
          lambda _: "[[{}||{}]]".format(display, transition),
          content
        )
      else:
        content = re.sub(
          r"\b{}\b".format(re.escape(display)),
          lambda _: "[[{}|{}|{}]]".format(display, destination, transition),
          content
        )
  return """\
# {}

{}
""".format(node.name, content)

def render_story(story):
  """
  The inverse of parse_story, render_story takes a Story object and returns a
  string that could be used to reconstruct that Story using parse_story.
  """
  result = """\
% title: {}
% author: {}
% start: {}
""".format(story.title, story.author, story.start)

  if story.setup:
    setup_str = json.dumps(story.setup)
    preamble += "% state: " + "\n% ".join(setup_str.split('\n')) + "\n"

  for node_name in story.nodes:
    result += '\n' + render_node(story.nodes[node_name])

  return result
