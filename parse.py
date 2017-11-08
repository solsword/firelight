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
  first = NODE_START.search(src)
  before = src[:first.start()]
  if not first or not re.match("[ \t\n\r]*", before, flags=re.MULTILINE):
    return (None, src)
  second = NODE_START.search(src, pos=first.end())
  content = src[first.end():second.start()]
  # TODO: HERE


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
