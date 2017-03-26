#!/usr/bin/env python3

import os
import json
import tweepy

import api

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
  total = 0
  def handle_mention(tw):
    nonlocal total
    total += 1
    print(tw.text)
  core.handle_mentions(handle_mention)
  print("Processed {} total mentions.".format(total))

if __name__ == "__main__":
  main()
