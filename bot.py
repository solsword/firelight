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

def get_tokens(filename=config.DEFAULT_TOKENS_FILE):
  """
  Gets authentication tokens.
  """
  if not os.path.isfile(filename):
    print("Couldn't find authentication file '{}'.".format(filename))
  with open(filename, 'r') as fin:
    tokens = json.load(fin)
  return tokens

def handle_story_reply(core, tweet, in_reply_to, sender, current_state):
  """
  TODO: HERE
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
    # TODO: allow non-reader forks w/ permission
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

  # Compute replies and new state:
  replies, new_node, new_state = st.advance(node, state, tweet.text)

  # Tweet replies:
  latest = core.tweet_replies(in_reply_to, replies, force=True)

  # Update database:
  core.db.extend_telling(in_reply_to, latest, new_node, new_state)

def handle_general_command(core, tweet, sender):
  """
  TODO: HERE
  """
  # TODO: HERE

def main():
  """
  The main loop of the bot.
  """
  tk = get_tokens()
  core = api.TwitterAPI(tk)
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
