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

  def shutdown(self):
    """
    Shuts down the various connections.
    """
    self.db.disconnect()

  def validate(self, message):
    """
    Returns False if the given message isn't valid.
    """
    return len(message) <= config.CHAR_LIMIT

  def coerce(self, message):
    """
    Takes a possibly-invalid message and returns a valid message, which may be
    incomplete or otherwise degraded. Note that e.g., links may be broken.
    """
    return message[config.CHAR_LIMIT]

  def tweet(self, message, force=False):
    """
    Posts the given tweet, if it's valid, returning the tweet's ID. If there's
    a problem, it returns None. If force is given, as much as possible of the
    message is posted, even if there is a problem.
    """
    if not self.validate(message):
      if force:
        message = self.coerce(message)
      else:
        return None

    self.api.update_status(status=message)
    # TODO: How to get ID of what we just tweeted?
    return ID

  def tweet_reply(self, reply_to, message, force=False):
    """
    Works like tweet, but posts the response in reply to the given tweet ID.
    """
    if not self.validate(message):
      if force:
        message = self.coerce(message)
      else:
        return None

    # TODO: Correct argument name here; how to get ID?
    self.api.update_status(status=message, in_reply_to=reply_to)
    return ID

  def tweet_replies(self, reply_to, messages, force=False):
    """
    Works like tweet_reply, but sends a chain of responses and returns the ID
    of the last one. Returns None if any reply fails.
    """
    for m in messages:
      reply_to = self.tweet_reply(reply_to, m, force=force)
      if reply_to is None:
        return None

    return reply_to

  def handle_mentions(self, callback):
    """
    Calls the given callback on any fresh mentions.
    """
    lpm = self.db.load_state("last_processed_mention")
    if lpm:
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
