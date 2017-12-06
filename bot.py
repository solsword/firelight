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

def handle_story_reply(core, tweet, in_reply_to, sender, current_state):
  """
  Given an API object (core), a tweet object, an in_reply_to ID that the tweet
  is replying to, a sender, and a current story state as returned by
  persist.Storage.recall_telling, performs the appropriate action(s) in
  response. This method handles tweets that are replies to tweets with valid
  story states, generally delegating much of that work to story.Story.advance.
  """
  reader, title, author, node, state, is_head = current_state

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
  st = core.db.recall_story(title, author)
  if not st:
    core.tweet_long(
      "Sorry, I've forgotten the story '{}' by '{}'. Something is wrong :("
      .format(
        title,
        author
      ),
      reply_to=tweet.id,
      reply_at=tweet.user.screen_name,
    )
    return

  # Compute replies and new state:
  address = tweet.text.strip().split()[0]
  rest = tweet.text.strip()
  if address == "@{}".format(config.MY_HANDLE):
    rest = tweet.text[len(address):].strip()

  command = rest.lower()
  try:
    fh = command.index('#')
  except ValueError as e:
    fh = -1

  if fh >= 0:
    command = command[:fh].strip()

  replies, new_node, new_state = st.advance(node, state, command)

  # Tweet replies:
  latest = core.tweet_long(
    replies,
    reply_to=tweet.id,
    reply_at=sender
  )

  # Update database:
  core.db.extend_telling(in_reply_to, latest, new_node, new_state)

def handle_general_command(core, tweet, sender):
  """
  Handles tweets (receives a tweet object and a sender) which are not replies
  to story tweets, and which are thus interpreted as general commands. Besides
  the tweet object, requires an API (core) and a sender name.
  """
  raw = tweet.text.strip()
  if '#' in raw:
    raw = raw[:raw.index('#')]
  chunks = raw.split()
  command = chunks[0].lower()
  args = raw[len(command):].strip()
  if command == "@{}".format(config.MY_HANDLE):
    command = chunks[1].lower()
    args = raw[len(chunks[0]) + len(command) + 1:].strip()

  if command in ("help", "[help]"):
    st = core.db.recall_story("help")
    if not st:
      core.tweet_long(
        "Sorry, there's no help available.",
        reply_to=tweet.id,
        reply_at=tweet.user.screen_name
      )
    else:
      replies, node_name, state = st.begin()
      tid = core.tweet_long(
        replies,
        reply_to=tweet.id,
        reply_at=tweet.user.screen_name,
      )
      core.db.begin_telling(tid, sender, st, node_name, state)

  elif command in ("list", "[list]"):
    core.tweet_long(
      [
        "Okay, here are all the stories that I know:",
        '\n'.join('"{}" by {}'.format(*t) for t in core.db.story_list())
      ],
      tweet.id,
      tweet.user.screen_name
    )

  elif command in ("tell", "[tell]"):
    # TODO: Get author info here and disambiguate!
    target_title = args.strip().lower()
    st = core.db.recall_story(target_title)
    respond_to = tweet.id
    if not st:
      sl = [ title for (title, author) in core.db.story_list() ]
      # Search for near-matches:
      best_match = story.fuzzy_match(
        target_title,
        sl,
        cutoff=config.TITLE_DISTANCE_THRESHOLD
      )
      if best_match[0] != None:
        st = core.db.recall_story(best_match[0])
        respond_to = core.tweet_long(
          "Ah, you must mean '{}.' Yes, I remember that tale...".format(
            best_match[0].title()
          ),
          respond_to,
          tweet.user.screen_name
        )

    if not st:
      # Nothing even close:
      core.tweet_long(
        (
          "Sorry, I don't know a story called '{}'.\n"
          "If you want, I can [list] the stories I know."
        ).format(target_title.title()),
        respond_to,
        tweet.user.screen_name
      )
    else:
      replies, node_name, state = st.begin()
      tid = core.tweet_long(
        replies,
        respond_to,
        tweet.user.screen_name
      )
      core.db.begin_telling(tid, sender, st, node_name, state)

  # TODO: More commands here?
  else:
    # TODO: Log failure?
    core.tweet_long(
      "Sorry, I don't know what '{}' means. Try 'help'?".format(
        strip_handles(command)
      ),
      tweet.id,
      tweet.user.screen_name
    )

PROCESSING_TOTAL = 0

def run_bot(core, loop=True):
  """
  Runs the bot using the given API object. If loop is false, just runs through
  the main loop once.
  """
  global PROCESSING_TOTAL
  def handle_mention(tw):
    global PROCESSING_TOTAL
    nonlocal core
    print("From: {}\nContent: {}".format(tw.user.screen_name, tw.text))
    sender = tw.user.screen_name
    if tw.in_reply_to_status_id != None: # a reply to a tweet
      replying_to = tw.in_reply_to_status_id
      print("In reply to: {}".format(replying_to))
      rec = core.db.recall_telling(replying_to)
      if rec: # Replying to a live story node
        reader, title, author, node, state, is_head = rec
        print(
          "Handling as reply to node '{}' in \"{}\" by {}.".format(
            node,
            title,
            author
          )
        )
        handle_story_reply(core, tw, replying_to, sender, rec)
      else: # Not a story-interaction reply
        print("Handling reply as a general command.")
        handle_general_command(core, tw, sender)
    else: # must be a general command:
      print("Handling non-reply as a general command.")
      handle_general_command(core, tw, sender)
    PROCESSING_TOTAL += 1

  # Set up our tweet handler:
  core.register_handler(handle_mention)

  # Start processing tweets:
  print("Initiating streaming connection...")
  try:
    backoff = 65
    while True:
      go = time.time()
      try:
        core.stream_user_tweets(config.MY_HANDLE)
      except tweepy.TweepError as e:
        if e.api_code == 187:
          # A duplicate message post; manually increment counter and re-try.
          core.incremenet_counter()
          print("\n...immediate retry after duplicate error...")
          continue
      except Exception as e:
        print("\n...error streaming tweets; retrying after backoff...")
        if config.DEBUG:
          print(e, file=sys.stderr)
          traceback.print_tb(e.__traceback__, file=sys.stderr)
      elapsed = time.time() - go
      if not loop:
        # we've done our single pass
        break
      if elapsed < backoff*3:
        backoff *= 2
      else:
        backoff = 65
      print("\n...backing off for {} seconds...".format(backoff))
      left = backoff
      while left > 0:
        print("  ...{} seconds remaining...".format(left), end="\r")
        time.sleep(1)
        left -= 1
      print("\n...retrying connection now...")
  except KeyboardInterrupt as e:
  # TODO: Get rid of this
  #except ValueError as e:
    print("\nShutting down.")

  core.shutdown()

def main():
  """
  The main loop of the bot.
  """
  tk = api.get_tokens()
  core = api.TwitterAPI(tk)

  run_bot(core)

if __name__ == "__main__":
  main()
