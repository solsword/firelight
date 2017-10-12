#!/usr/bin/env python3
"""
bot.py
Main file for the Firelight twitter bot. See api.py and story.py for top-level
functionality.
"""

import re
import os
import sys
import json
import time
import traceback

import tweepy

import api
import story
import config

from packable import pack, unpack

def strip_handles(message):
  return re.sub('@', r'@\\', message)

def get_tokens(filename=config.DEFAULT_TOKENS_FILE):
  """
  Gets authentication tokens.
  """
  if not os.path.isfile(filename):
    print("Couldn't find authentication file '{}'.".format(filename))
  with open(filename, 'r') as fin:
    tokens = json.load(fin)
  return tokens

def load_stories(core, directory):
  """
  Loads stories into the database of the given core API object from files
  ending in '.fls'. Prints warnings for unloadable files and duplicate titles,
  skipping affected files/stories.
  """
  for dirpath, dirnames, filenames in os.walk(directory):
    for f in filenames:
      if f.endswith(".fls"):
        with open(os.path.join(dirpath, f), 'r') as fin:
          try:
            st = unpack(json.loads(fin.read()), story.Story)
          except Exception as e:
            print(
              "Warning: file '{}' could not be read as a Story.".format(
                os.path.join(dirpath, f)
              )
            )
            if config.DEBUG:
              print(e, file=sys.stderr)
              traceback.print_tb(e.__traceback__, file=sys.stderr)
            continue # continue to the next file

          core.db.save_new_story(st)

def handle_story_reply(core, tweet, in_reply_to, sender, current_state):
  """
  Given an API object (core), a tweet object, an in_reply_to ID that the tweet
  is replying to, a sender, and a current story state as returned by
  persist.Storage.recall_telling, performs the appropriate action(s) in
  response. This method handles tweets that are replies to tweets with valid
  story states, generally delegating much of that work to story.Story.advance.
  """
  reader, story, node, state, is_head = current_state

  # Check sender identity:
  if sender != reader:
    print(
      "  Got non-reader reply '{}' from {} (not {}); ignoring.".format(
        tweet.text,
        sender,
        reader
      )
    )
    # TODO: allow non-reader forks w/ permission? (permissions system)
    return

  # Recall the story being responded to:
  st = core.db.recall_story(story)
  if not st:
    # TODO: Tweet error reply
    core.tweet_reply(
      tweet.id,
      tweet.user.name,
      "TellingError: story not found: '{}'".format(story),
      force=True
    )
    return

  # Compute replies and new state:
  replies, new_node, new_state = st.advance(node, state, tweet.text)

  # Tweet replies:
  latest = core.tweet_replies(in_reply_to, replies, force=True)

  # Update database:
  core.db.extend_telling(in_reply_to, latest, new_node, new_state)

def handle_general_command(core, tweet, sender):
  """
  Handles tweets (receives a tweet object and a sender) which are not replies
  to story tweets, and which are thus interpreted as general commands. Besides
  the tweet object, requires an API (core) and a sender name.
  """
  chunks = tweet.text.strip().split()
  command = chunks[0]
  args = tweet.text.strip()[len(command):]
  if command == "@{}".format(config.MY_HANDLE):
    command = chunks[1]
    args = tweet.text.strip()[len(chunks[0]) + len(command) + 1:]

  if command in ("help", "[help]"):
    st = core.db.recall_story("help")
    if not st:
      core.tweet_reply(
        tweet.id,
        tweet.user.name,
        "Sorry, there's no help available.",
        force=True
      )
    else:
      tid = core.tweet_reply(
        tweet.id,
        tweet.user.name,
        story.format_node(st.nodes[st.start]),
        force=True
      )
      core.db.begin_telling(tid, sender, "help")

  elif command in ("list", "[list]"):
    # TODO: automatic tweet breaking
    core.tweet_replies(
      tweet.id,
      [
        "Okay, here are all the stories that I know:",
        '"' + '"\n"'.join(core.db.story_list()) + '"'
      ],
      force=True
    )

  elif command in ("tell", "[tell]"):
    target_title = args
    st = core.db.recall_story(target_title)
    if not st:
      # TODO: Find nearest matches?
      core.tweet_reply(
        tweet.id,
        tweet.user.name,
        (
          "Sorry, I don't know a story called '{}'.\n"
          "You can try the [list] command."
        ).format(target_title),
        force=True
      )
    else:
      tid = core.tweet_reply(
        tweet.id,
        tweet.user.name,
        story.format_node(st.nodes[st.start]),
        force=True
      )
      core.db.begin_telling(tid, sender, st.name)

  # TODO: More commands here?
  else:
    # TODO: Log failure
    core.tweet_reply(
      tweet.id,
      tweet.user.name,
      "CommandError: unrecognized command '{}'".format(strip_handles(command)),
      force=True
    )

PROCESSING_TOTAL = 0

def main():
  """
  The main loop of the bot.
  """
  global PROCESSING_TOTAL
  tk = get_tokens()
  core = api.TwitterAPI(tk)
  load_stories(core, config.STORIES_DIRECTORY)

  def handle_mention(tw):
    global PROCESSING_TOTAL
    nonlocal core
    print("From: {}\nContent: {}".format(tw.user.screen_name, tw.text))
    sender = tw.user.name
    if tw.in_reply_to_status_id != None: # a reply to a tweet
      replying_to = tw.in_reply_to_status_id
      rec = core.db.recall_telling(replying_to)
      if rec: # Replying to a live story node
        handle_story_reply(core, tw, replying_to, sender, rec)
      else: # Not a story-interaction reply
        handle_general_command(core, tw, sender)
    else: # must be a general command:
      handle_general_command(core, tw, sender)
    PROCESSING_TOTAL += 1

  try:
    while True:
      PROCESSING_TOTAL = 0
      try:
        core.handle_mentions(handle_mention)
      except Exception as e:
        print("..error processing mentions; retrying next cycle...")
        if config.DEBUG:
          print(e, file=sys.stderr)
          traceback.print_tb(e.__traceback__, file=sys.stderr)

      print("Processed {} total mentions.".format(PROCESSING_TOTAL))
      time.sleep(3)
  except KeyboardInterrupt as e:
    print("\nShutting down.")
  core.shutdown()


if __name__ == "__main__":
  main()
