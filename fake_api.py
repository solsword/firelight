"""
fake_api.py

Fake API for testing. Accesses storage but doesn't connect to Twitter. 
"""

import os
import sys
import json

import persist

import config

class FakeUser:
  """
  A fake User object.
  """
  def __init__(self, screen_name):
    self.screen_name = screen_name

def next_int(state=[0]):
  state[0] += 1
  return state[0]

class FakeTweet:
  """
  A fake Tweet object.
  """
  def __init__(self, sender, replying_to, content):
    self.id = next_int()
    self.user = FakeUser(sender)
    self.in_reply_to_status_id = replying_to
    self.text = content

class FakeTwitterAPI:
  """
  A mockup of TwitterAPI for testing purposes. Uses the given database and
  doesn't talk to Twitter.
  """
  def __init__(self, input_tweets, output_stream, db_filename):
    self.handlers = []
    self.queue = input_tweets
    self.out = output_stream
    self.db = persist.Storage(db_filename)
    self.global_counter = 0

  def register_handler(self, fcn):
    """
    Registers a tweet handler.
    """
    self.handlers.append(fcn)

  def remove_handler(self, fcn):
    """
    Removes a tweet handler.
    """
    self.handlers.remove(fcn)

  def on_status(self, tweet):
    """
    Streaming handler for new statuses.
    """
    for h in self.handlers:
      h(tweet)

  def on_error(self, status_code):
    """
    Handles failed connection attempts.
    """
    if config.DEBUG:
      print(
        "Connection failed with code {}.".format(status_code),
        file=sys.stderr
      )

  def on_timeout(self):
    """
    Handles connection timeouts.
    """
    if config.DEBUG:
      print("Connection timed out.", file=sys.stderr)

  def on_disconnect(self, notice):
    """
    Handles explicit disconnect notices.
    """
    if config.DEBUG:
      print(
        "Disconnecting due to: {}\nReason: {}".format(
          DISCONNECT_CODES[notice["code"]],
          notice["reason"]
        ),
        file=sys.stderr
      )

  def stream_user_tweets(self, screen_name):
    """
    Initiates the (fake) streaming process. screen_name is ignored. This method
    returns after processing the current input queue (sequentially).
    """
    for msg in self.queue:
      self.on_status(msg)

  def stop_streaming(self):
    """
    Stops streaming.
    """
    pass

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
    return message[:config.CHAR_LIMIT]

  def incremenet_counter(self):
    """
    Method for incrementing the global counter. The database is not affected.
    """
    self.global_counter += 1

  def ntag(self):
    """
    Spits out a numeric tag. Overflows wrap. Uses and increments the global
    counter.
    """
    # TODO: We need a more robust solution, as this is exploitable!
    n = self.global_counter
    self.incremenet_counter()
    l = len(config.TAGCHARS)
    n %= l**config.NTAG_SIZE
    tag = config.TAGCHARS[n%l]
    ofs = 0
    for i in range(config.NTAG_SIZE-1):
      ofs += 7
      n //= l
      tag += config.TAGCHARS[(n+ofs)%l]
    return tag

  def format_into_messages(self, content, reply_at=None):
    """
    Takes arbitrary-length content (possibly in reply to a specific user) and
    formats it into a series of tweetable chunks, each of which includes a
    count tag to help avoid duplicate status problems.
    """
    leftovers = content
    results = []
    while leftovers:
      tw, leftovers = self.format_first_message(leftovers, reply_at)
      results.append(tw)

    return results

  def format_first_message(self, content, reply_at=None):
    """
    Takes content and formats part of it into a tweet, returning that tweet
    text and any leftover text as a pair.
    """
    ntag = " " + self.ntag()
    rtag = ""
    if reply_at:
      rtag = "@{} ".format(reply_at)

    reserved = len(rtag) + len(ntag)
    allowance = config.CHAR_LIMIT - reserved
    words = 0
    backup = 0
    for i in range(len(content)):
      if i == len(content) - 1:
        if i <= allowance:
          return (
            "{}{}{}".format(rtag, content, ntag),
            ""
          )
        else:
          return (
            "{}{}{}".format(rtag, content[:allowance], ntag),
            content[allowance:]
          )
      if content[i] in " 	\n":
        if i < allowance:
          backup = i
        else:
          if backup > 0:
            return (
              "{}{}{}".format(rtag, content[:backup], ntag),
              content[backup:]
            )
          else:
            return (
              "{}{}{}".format(rtag, content[:allowance], ntag),
              content[allowance:]
            )
    raise RuntimeError("Fell out of loop in format_first_message.")

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

    tid = next_int()
    self.out.write(
      "Id: {}\nReplying to: {}\n{}\n{}\n{}\n".format(
        tid,
        "<all>",
        '-'*80,
        message,
        '='*80
      )
    )
    return tid

  def tweet_reply(self, reply_to, reply_at, message, force=False):
    """
    Works like tweet, but posts the response in reply to the given tweet ID.
    Note that a target username is also required for the reply to work;
    reply_at may also be a list of usernames to reply to multiple people at
    once.
    """
    if isinstance(reply_at, (list, tuple)):
      message = "{} {}".format(
        ' '.join("@{}".format(at) for at in reply_at),
        message
      )
    else:
      message = "@{} {}".format(reply_at, message)

    if not self.validate(message):
      if force:
        message = self.coerce(message)
      else:
        return None

    tid = next_int()
    self.out.write(
      "Id: {}\nReplying to: {}\n{}\n{}\n{}\n".format(
        tid,
        reply_to,
        '-'*80,
        message,
        '='*80
      )
    )
    return tid

  def tweet_replies(self, reply_to, reply_at, messages, force=False):
    """
    Works like tweet_reply, but sends a chain of responses and returns the ID
    of the last one. Returns None if any reply fails.
    """
    for m in messages:
      reply_to = self.tweet_reply(reply_to, reply_at, m, force=force)
      if reply_to is None:
        return None

    return reply_to

  def tweet_long(self, message, reply_to=None, reply_at=None):
    """
    Posts longer content with automatic numbering and splitting across multiple
    tweets. If the content should be tweeted as a reply, both reply_to and
    reply_at must be given.
    """
    if isinstance(message, (list, tuple)):
      payloads = []
      for m in message:
        payloads.extend(self.format_into_messages(m, reply_at))
    else:
      payloads = self.format_into_messages(message, reply_at)

    if reply_to is None:
      first = self.tweet(payloads[0], force=True)
      last = self.tweet_replies(
        first,
        config.MY_HANDLE,
        payloads[1:],
        force=True
      )
    else:
      last = self.tweet_replies(reply_to, reply_at, payloads, force=True)
    return last
