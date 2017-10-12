#!/usr/bin/env python3
"""
bot.py
Main file for the Firelight twitter bot. See api.py and story.py for top-level
functionality.
"""

import os
import json
import time

import tweepy

import api
import story
import config

from packable import pack, unpack

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
            story = unpack(json.loads(fin.read()), story.Story)
          except:
            print(
              "Warning: file '{}' could not be read as a Story.".format(
                os.path.join(dirpath, f)
              )
            )
            continue # continue to the next file

          core.db.save_new_story(story)

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
  command = tweet.text.strip().split()[0]
  if command in ("help", "[help]"):
    st = core.db.recall_story("help")
    if not st:
      core.tweet_reply(
        tweet.id,
        "Sorry, there's no help available.",
        force=True
      )
    else:
      tid = core.tweet_reply(
        tweet.id,
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
    target_title = tweet.text[len(command):].strip()
    st = core.db.recall_story(target_title)
    if not st:
      # TODO: Find nearest matches?
      core.tweet_reply(
        tweet.id,
        (
          "Sorry, I don't know a story called '{}'.\n"
          "You can try the [list] command."
        ).format(target_title),
        force=True
      )
    else:
      tid = core.tweet_reply(
        tweet.id,
        story.format_node(st.nodes[st.start]),
        force=True
      )
      core.db.begin_telling(tid, sender, st.name)

  # TODO: More commands here?
  else:
    # TODO: Log failure
    core.tweet_reply(
      tweet.id,
      "CommandError: unrecognized command '{}'".format(command),
      force=True
    )

def main():
  """
  The main loop of the bot.
  """
  tk = get_tokens()
  core = api.TwitterAPI(tk)
  load_stories(core, config.STORIES_DIRECTORY)
  try:
    while True:
      total = 0
      def handle_mention(tw):
        nonlocal total
        total += 1
        print("From: {}\nContent: {}".format(tw.user.screen_name, tw.text))
        sender = tw.user.name
        if tw.is_reply: # a reply to a tweet
          replying_to = tw.in_reply_to_status_id
          rec = core.db.recall_telling(replying_to)
          if rec: # Replying to a live story node
            handle_story_reply(core, tw, replying_to, sender, rec)
          else: # Not a story-interaction reply
            handle_general_command(core, tw, sender)
          thread = core.get_thread_id(tw)
        else: # must be a general command:
          handle_general_command(core, tw, sender)

        # TODO: HERE

      core.handle_mentions(handle_mention)
      print("Processed {} total mentions.".format(total))
      time.sleep(5)
  except KeyboardInterrupt as e:
    print("\nShutting down.")
  core.shutdown()


if __name__ == "__main__":
  main()
