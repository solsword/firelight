#!/usr/bin/env python
"""
load_stories.py

Script that loads stories from the stories/ directory into the database. If
arguments are given, loads those files instead.
"""

import os
import sys
import json
import traceback

import api
import story
import config
import parse

from packable import pack, unpack

def load_story_from_file(filename, fmt="auto"):
  """
  Loads a Story object from a filename. Prints a warning and does nothing if
  the file cannot be loaded. The fmt argument decides which format to load,
  "json" for JSON format, and "story" for Markdown-like format, or "auto" to
  choose based on the start of the file (just checks whether the first two
  non-whitespace characters are '{' and '"', in which case it uses JSON). 
  """
  with open(filename, 'r') as fin:
    try:
      raw = fin.read()
      fmtstr = fmt
      if fmt == "auto":
        if raw[:1024].translate(
          { ord(c): None for c in ' \t\n\r' }
        ).startswith('{"'):
          fmt = "json"
          fmtstr = "json (detected)"
        else:
          fmt = "story"
          fmtstr = "story (default)"

      if fmt == "json":
        st = unpack(json.loads(raw), story.Story)
      elif fmt == "story":
        st = parse.parse_story(raw)
      else:
        raise ValueError("Invalid story format '{}'.".format(fmtstr))
    except Exception as e:
      print(
        "Warning: file '{}' could not be read as a Story in format '{}'."
        .format(filename, fmtstr)
      )
      if config.DEBUG:
        print(e, file=sys.stderr)
        traceback.print_tb(e.__traceback__, file=sys.stderr)
      return None

  return st

def load_story(core, filename, force=False, fmt="auto", is_module=False):
  """
  Loads a story into the database of the given core API object from the given
  file. Duplicates are overwritten without a warning if 'force' is True,
  otherwise a warning is issued and nothing happens.  If is_module is True, the
  story is loaded (and stored) as a module instead of as a story.
  """
  st = load_story_from_file(filename, fmt=fmt)
  if not st:
    return # warning already printed
  core.db.save_new_story(st, force=force, is_module=is_module)

def load_stories_from_directory(core, directory, force=False, as_modules=False):
  """
  Scans the given directory recursively for '.flj' and '.fls' files and calls
  load_story on each, passing the 'force' and 'as_modules" parameters through.
  """
  for dirpath, dirnames, filenames in os.walk(directory):
    for f in filenames:
      if f.endswith(".flj"):
        load_story(
          core,
          os.path.join(dirpath, f),
          force=force,
          is_module=as_modules
        )
      if f.endswith(".fls"):
        load_story(
          core,
          os.path.join(dirpath, f),
          force=force,
          is_module=as_modules
        )

def main(targets=None, force=False, as_modules=False):
  """
  Main script code for loading stories.
  """
  global PROCESSING_TOTAL
  tk = api.get_tokens()
  core = api.TwitterAPI(tk)
  if targets:
    for t in targets:
      is_module = False
      if (
        as_modules
     or (
          t.startswith(config.MODULES_DIRECTORY)
       or t.startswith("./" + config.MODULES_DIRECTORY)
        )
      ):
        is_module = True

      if t.endswith(".flj"):
        load_story(core, t, force=force, fmt="json", is_module=is_module)
      elif t.endswith(".fls"):
        load_story(core, t, force=force, fmt="story", is_module=is_module)
      else:
        load_story(core, t, force=force, fmt="auto", is_module=is_module)
  else:
    load_stories_from_directory(
      core,
      config.STORIES_DIRECTORY,
      force=force,
      as_modules=False
    )
    load_stories_from_directory(
      core,
      config.MODULES_DIRECTORY,
      force=force,
      as_modules=True
    )

if __name__ == "__main__":
  if "-h" in sys.argv:
    print("""\
Usage:

  load_stories.py [-h] [-f] [targets]

Options:

  -h: help (this message)
  -f: force (replace old stories w/ matching titles)
  -m: as_modules (all targets are loaded as modules; no effect without targets)

Function:           

  Loads stories (*.fls files) from the config.STORIES_DIRECTORY directory (see
  config.py) into the story database. If one or more targets are given, loads
  exactly those files instead (regardless of extension). Prints a warning
  message if a loaded story has the same name as an existing story, and ignores
  that story. If '-f' is given, replaces old stories without any message
  instead.

  Also loads modules from the config.MODULES_DIRECTORY if no targets are given.
  If a target is given that's clearly within the config.MODULES_DIRECTORY (the
  target path starts with that directory) then that target will be loaded as a
  module instead of as a story.
"""
    )
    exit(0)

  force = False
  while "-f" in sys.argv:
    sys.argv.remove("-f")
    force = True
  while "-m" in sys.argv:
    sys.argv.remove("-m")
    as_modules = True
  if len(sys.argv) == 1:
    main(force=force)
  else:
    main(sys.argv[1:], force=force, as_modules=as_modules)
