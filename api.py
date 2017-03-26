"""
api.py

Core internal API for twitter access. Maps actions to tweepy calls.
"""

import tweepy
import persist

import config

class TwitterAPI:
  def __init__(self, tokens):
    self.auth = tweepy.OAuthHandler(
      tokens["consumer_key"],
      tokens["consumer_key_secret"]
    )
    self.auth.set_access_token(tokens["access"], tokens["access_secret"])
    self.api = tweepy.API(self.auth)
    self.db = persist.Storage()

  def validate(self, message):
    """
    Returns False if the given message isn't valid.
    """
    return len(message) <= config.CHAR_LIMIT

  def tweet(self, message):
    """
    Posts the given tweet, if it's valid, returning True. If there's a problem,
    it returns False.
    """
    if not self.validate(message):
      return False

    self.api.update_status(status=message)
    return True

  def handle_mentions(self, callback):
    """
    Calls the given callback on any fresh mentions.
    """
    lpm = self.db.load_state("last_processed_mention")
    if lpm:
      print("Filtering on lpm: '{}'".format(lpm))
      cursor = tweepy.Cursor(
        self.api.mentions_timeline,
        since_id=lpm
      )
    else:
      cursor = tweepy.Cursor(self.api.mentions_timeline)
    new_lpm = None
    for page in cursor.pages():
      for tweet in page:
        if tweet.id == lpm: # quit if we reach processed stuff
          break
        if not new_lpm: # save first id encountered:
          new_lpm = tweet.id
        callback(tweet)

    if new_lpm:
      self.db.save_state("last_processed_mention", new_lpm)
