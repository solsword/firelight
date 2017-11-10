"""
parse.py

Story format parsing for Firelight. Reads markup similar to Markdown and
translates it into simple Python structures suitable for unpacking.
"""

import re
import json

from story import StoryNode, Story

META_KEY = re.compile(r"^% \([A-Za-z0-9_.-][A-Za-z0-9_.-]*\):")
COMMENT = re.compile(r"``.*$")
NODE_START = re.compile(r"^#\s*\([A-Za-z0-9_.-][A-Za-z0-9_.-]*\)\s*$")

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

def parse_metadata(src):
  """
  Parses the initial metadata block of an .fls file, returning a pair
  containing a dictionary of metadata and a metadata-free source text. The
  metadata block must appear at the top of the file, and each line must start
  with a percent sign. Example:

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
  """
  # Default values:
  metadata = {
    "title": "Untitled",
    "author": "Unknown",
    "start": "Error: you must specify a starting story node.",
    "state": "{}"
  }
  leftovers = ""
  lines = src.split('\n')
  for i, line in enumerate(lines):
    if line.strip() == '':
      continue
    elif line[0] == '%':
      match = META_KEY.search(line)
      if match:
        current_key = match.group(0)
        metadata[current_key] = line[match.end():].strip()
      else:
        metadata[current_key] += ' ' + line[1:].strip()
    else:
      break

  metadata[state] = json.loads(metadata[state])
  return metadata, '\n'.join(lines[i:])

def parse_first_node(src):
  """
  Takes a chunk of story source and parses the first node from it (which should
  start immediately at the top of the source modulo comments and empty space).

  Returns (None, src) if there isn't a node definition present, or the parsed
  node plus the remaining source if there is.
  """
  src = src.strip()
  first = NODE_START.search(src)
  # No node found:
  if not first or first.start != 0:
    return (None, src)

  node = {}

  # Search for the next node, or else use the end of the source:
  second = NODE_START.search(src, pos=first.end())
  if second:
    node_end = second.start()
  else:
    node_end = len(src)

  # Grab the name and content:
  node["name"] = first.group(0)
  content = src[first.end():node_end]
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
  Parses a Story object from the contents of an .fls file.
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
