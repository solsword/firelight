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
  if not os.path.isfile(filename):
    print("Couldn't find authentication file '{}'.".format(filename))
  with open(filename, 'r') as fin:
    tokens = json.load(fin)
  return tokens

def main():
  tk = get_tokens()
  core = api.TwitterAPI(tk)
  #core.tweet("test")
  try:
    while True:
      total = 0
      def handle_mention(tw):
        nonlocal total
        total += 1
        print("From: {}\nContent: {}".format(tw.user.screen_name, tw.text))
      core.handle_mentions(handle_mention)
      print("Processed {} total mentions.".format(total))
      time.sleep(5)
  except KeyboardInterrupt as e:
    print("\nShutting down.")
  core.shutdown()


if __name__ == "__main__":
  main()
