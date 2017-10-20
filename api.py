"""
api.py

Core internal API for twitter access. Maps actions to tweepy calls.
"""

import tweepy
import persist

import config

# See: https://developer.twitter.com/en/docs/tweets/filter-realtime/guides/streaming-message-types
DISCONNECT_CODES = {
  1: "Shutdown",
  2: "Duplicate Stream",
  3: "Control request",
  4: "Stall",
  5: "Normal",
  6: "Token Revoked",
  7: "Admin Logout",
  8: "Reserved Internal",
  9: "Max Message Limit",
  10: "Stream Exception",
  11: "Broker Stall",
  12: "Shed load",
}

class TwitterAPI(tweepy.StreamListener):
  def __init__(self, tokens):
    self.auth = tweepy.OAuthHandler(
      tokens["consumer_key"],
      tokens["consumer_key_secret"]
    )
    self.auth.set_access_token(tokens["access"], tokens["access_secret"])
    self.api = tweepy.API(self.auth)
    self.db = persist.Storage()
    self.handlers = []
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
      print("Connection failed with code {}.".format(status_code))

  def on_timeout(self):
    """
    Handles connection timeouts.
    """
    if config.DEBUG:
      print("Connection timed out.")

  def on_disconnect(self, notice):
    """
    Handles explicit disconnect notices.
    """
    if config.DEBUG:
      print(
        "Disconnecting due to: {}\nReason: {}".format(
          DISCONNECT_CODES[notice["code"]],
          notice["reason"]
        )
      )

  def stream_user_tweets(self, screen_name):
    """
    Initiates the streaming process for tweets mentioning a particular user
    name (supply without the '@'). This method doesn't return until the
    stream is disconnected.
    """
    self.stream = tweepy.Stream(auth=self.api.auth, listener = self)
    # TODO: Is using a filter here instead of a user stream correct? Seems
    # wrong, but user streams don't give you mentions? *Could* go with a
    # replies-only design?
    self.stream.filter(
      track=["@{}".format(screen_name)]
    )

  def stop_streaming(self):
    """
    Stops streaming.
    """
    self.stream.disconnect()

  def shutdown(self):
    """
    Shuts down the various connections.
    """
    self.stream.disconnect()
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

  def incremenet_counter(self):
    """
    Method for incrementing the global counter just-in-case.
    """
    self.global_counter += 1

  def ntag(self, n):
    """
    Turns a number into an N-character tag. Overflows wrap. Uses and increments
    the global counter.
    """
    # TODO: We need a more robust solution, as this is exploitable!
    n += self.global_counter
    self.global_counter += 1
    l = len(config.TAGCHARS)
    n %= l**config.NTAG_SIZE
    tag = config.TAGCHARS[n%l]
    ofs = 0
    for i in range(config.NTAG_SIZE-1):
      ofs += 7
      n //= l
      tag += config.TAGCHARS[(n+ofs)%l]
    return tag

  def format_into_messages(self, content, reply_at=None, start=0):
    """
    Takes arbitrary-length content (possibly in reply to a specific user) and
    formats it into a series of tweetable chunks, each of which includes a
    count tag to help avoid duplicate status problems.
    """
    leftovers = content
    n = start
    results = []
    while leftovers:
      tw, leftovers = self.format_first_message(content, reply_at, n)
      n += 1
      results.append(tw)

    return results

  def format_first_message(self, content, reply_at=None, number=0):
    """
    Takes content and formats part of it into a tweet, returning that tweet
    text and any leftover text as a pair.
    """
    ntag = " " + self.ntag(number)
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

    status = self.api.update_status(status=message)
    return status.id

  def tweet_reply(self, reply_to, reply_at, message, force=False):
    """
    Works like tweet, but posts the response in reply to the given tweet ID.
    Note that a target username is also required for the reply to work;
    reply_at may also be a list of usernames to reply to multiple people at
    once.
    """
    # TODO: Do we need to explicitly add usernames to content in order to
    # thread tweets? (see:
    #   https://developer.twitter.com/en/docs/tweets/post-and-engage/api-reference/post-statuses-update
    # particularly the section on in_reply_to_status_id)
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

    status = self.api.update_status(
      status=message,
      in_reply_to_status_id=reply_to
    )
    return status.id

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

  def handle_mentions(self, callback):
    """
    Calls the given callback on any fresh mentions, excluding self-mentions.
    Note that rate-limiting makes the streaming approach much better for
    real-time interaction.
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

        if tweet.user.screen_name != config.MY_HANDLE:
          callback(tweet)

    if new_lpm:
      self.db.save_state("last_processed_mention", new_lpm)
