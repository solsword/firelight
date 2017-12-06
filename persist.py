"""
persist.py

Persistent storage for Firelight bot.
"""

import sqlite3
import os
import sys
import datetime
import json

import config

from packable import pack, unpack

from story import Story

class Storage:
  def __init__(self, db_filename=config.DB_FILE):
    self.db_filename = db_filename
    self.connection = None
    self.connect()
    self.setup_tables()
    self.story_cache = {}
    self.module_cache = {}

  def connect(self):
    """
    Connect to the database. Does nothing if already connected.
    """
    if not self.connection:
      if not os.path.isfile(self.db_filename):
        print(
          "Database '{}' doesn't exist; creating it.".format(
            self.db_filename
          )
        )
      self.connection = sqlite3.connect(self.db_filename)
      self.connection.row_factory = sqlite3.Row

  def disconnect(self):
    """
    Disconnect from the database. Does nothing if not connected. Any
    uncommitted transactions will be rolled back first.
    """
    if self.connection:
      self.connection.rollback()
      self.connection.close()
      self.connection = None

  def reset_database(self):
    """
    Cleans out all database information and recreates empty tables.
    """
    cur = self.connection.cursor()
    cur.execute("DROP TABLE IF EXISTS state;")
    cur.execute("DROP TABLE IF EXISTS tellings;")
    cur.execute("DROP TABLE IF EXISTS stories;")
    cur.execute("DROP TABLE IF EXISTS modules;")
    self.connection.commit()

    self.setup_tables()

  def setup_tables(self):
    """
    Creates tables in the database.
    """
    cur = self.connection.cursor()
    cur.execute(
      """
      CREATE TABLE IF NOT EXISTS state(
        {}
      );
      """.format(
        ",\n  ".join(
          "{} {}".format(key, config.STATE_STRUCTURE[key])
            for key in config.STATE_STRUCTURE
        )
      )
    ) # TODO: More stuff here?

    # Insert an empty row into our state table if it's empty:
    cur.execute("SELECT Count(*) from state;")
    if cur.fetchone()[0] == 0:
      cur.execute(
        "INSERT INTO state VALUES({});".format(
          ", ".join("0" for i in range(len(config.STATE_STRUCTURE)))
        )
      )

    cur.execute(
      """
      CREATE TABLE IF NOT EXISTS tellings(
        tweet INTEGER PRIMARY KEY,
        reader TEXT NOT NULL,
        story TEXT NOT NULL,
        author TEXT NOT NULL,
        node TEXT NOT NULL,
        state TEXT NOT NULL,
        is_head BOOLEAN NOT NULL
      );
      """
    )

    cur.execute(
      """
      CREATE TABLE IF NOT EXISTS stories(
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        package TEXT NOT NULL
      );
      """
    )

    cur.execute(
      """
      CREATE TABLE IF NOT EXISTS modules(
        title TEXT NOT NULL,
        author TEXT NOT NULL,
        package TEXT NOT NULL
      );
      """
    )

    self.connection.commit()

  def save_state(self, key, value):
    """
    Writes a piece of state into the database.
    """
    cur = self.connection.cursor()
    if key not in config.STATE_STRUCTURE:
      print(
        "Error: attempt to save key '{}' which isn't in the state structure."
        .format(key)
      )
      return
    cur.execute("UPDATE state SET {} = ?;".format(key), (value,))
    self.connection.commit()

  def load_state(self, key):
    """
    Reads a piece of state from the database.
    """
    cur = self.connection.cursor()
    if key not in config.STATE_STRUCTURE:
      print(
        "Error: attempt to load key '{}' which isn't in the state structure."
        .format(key)
      )
      return None
    cur.execute("SELECT {} FROM state;".format(key))
    row = cur.fetchone()
    value = row[key]
    return value

  def save_new_story(self, story, force=False, is_module=False):
    """
    Saves a new story to the database. Returns True if it succeeds, or False
    (and prints a warning message) if a story by that title already exists.
    Always returns true and replaces any existing story if 'force' is True.
    Saves the story as a module if is_module is True.
    """
    table = "modules" if is_module else "stories"
    cur = self.connection.cursor()
    title = story.title.title()
    author = story.author.title()
    cur.execute(
      "SELECT * FROM {} WHERE title = ? AND author = ?;".format(table),
      (title, author)
    )
    if len(cur.fetchall()) > 0:
      if force:
        self.update_story(story)
      else:
        print(
          (
            "Warning: attempted to save new {} by '{}' "
            "with duplicate title '{}'."
          ).format(
            "module" if is_module else "story",
            author,
            title
          ),
          file=sys.stderr
        )
        return False

    # TODO: maximize packing efficiency
    cur.execute(
      "INSERT INTO {}(title, author, package) values(?, ?, ?);".format(table),
      ( title, author, json.dumps(pack(story)) )
    )

    self.connection.commit()
    return True

  def update_story(self, story, is_module=False):
    """
    Updates a story (or module) in the database, overwriting the current
    contents.
    """
    table = "modules" if is_module else "stories"
    cur = self.connection.cursor()
    # TODO: maximize packing efficiency
    cur.execute(
      "UPDATE {} SET package = ? WHERE title = ? AND author = ?;".format(table),
      ( json.dumps(pack(story)), story.title.title(), story.author.title() )
    )
    # TODO: Error handling here
    self.connection.commit()

  def recall_story(self, title, author=None, is_module=False):
    """
    Looks up a story (or module) in the database and returns it, or None if no
    such story exists. If multiple stories match (when author is given as
    None), a list will be returned.
    """
    cached = self.find_cached(title, author, is_module)
    if cached:
      return cached

    table = "modules" if is_module else "stories"
    cur = self.connection.cursor()
    if author is None:
      cur.execute(
        "SELECT package FROM {} WHERE title = ?;".format(table),
        ( title.title(), )
      )
    else:
      cur.execute(
        "SELECT package FROM {} WHERE title = ? AND author = ?;".format(table),
        ( title.title(), author.title() )
      )
    rows = cur.fetchall()
    if len(rows) < 1:
      return None

    if len(rows) > 1: # Don't cache anything in this case
      result = [ unpack(json.loads(r["package"]), Story) for r in rows ]
      result.set_module_finder(self.find_module)
    else:
      result = unpack(json.loads(rows[0]["package"]), Story)
      result.set_module_finder(self.find_module)

      if is_module:
        self.cache_module(result)
      else:
        self.cache_story(result)

      return result

  def find_module(self, module_name, module_author=None):
    """
    A module finder. Looks up modules by name in the modules database.
    """
    # TODO: Get module author info!
    return self.recall_story(module_name, module_author, is_module=True)

  def story_list(self):
    """
    Returns a list of all known story titles/authors (returned as pairs).
    """
    cur = self.connection.cursor()
    cur.execute("SELECT title, author FROM stories;")
    return [ (row["title"], row["author"]) for row in cur.fetchall()]

  def module_list(self):
    """
    Returns a list of all known module titles/authors (returned as pairs).
    """
    cur = self.connection.cursor()
    cur.execute("SELECT title, author FROM modules;")
    return [ (row["title"], row["author"]) for row in cur.fetchall()]

  def begin_telling(
    self,
    tweet,
    reader,
    story,
    at_node,
    with_state
  ):
    """
    Creates a new telling in the database starting at the start node of the
    given story with the default starting state.
    """
    cur = self.connection.cursor()
    # Create a new story for this reader and return its ID.
    cur.execute(
      (
        "INSERT INTO tellings(tweet, reader, story, author, node, state, "
        "is_head) VALUES(?, ?, ?, ?, ?, ?, ?);"
      ),
      (
        tweet,
        reader,
        story.title.title(),
        story.author.title(),
        at_node,
        json.dumps( with_state ),
        True
      )
    )
    self.connection.commit()

  def extend_telling(self, tweet_from, new_tweet, new_node, new_state):
    """
    Extends an existing telling from the given tweet with the new tweet, using
    the new node name and state as given (the state will be dumped to a JSON
    string). Note that calling this with a "new_tweet" value that's already
    registered will cause an error.
    """
    cur = self.connection.cursor()
    cur.execute(
      (
        "INSERT INTO tellings(tweet, reader, story, author, node, state, "
        "is_head) SELECT ?, reader, story, author, ?, ?, 1 FROM tellings "
        "WHERE tweet = ?;"
      ),
      (
        new_tweet,
        new_node,
        json.dumps( new_state ),
        tweet_from
      )
    )
    cur.execute(
      "UPDATE tellings SET is_head = 0 WHERE tweet = ?;",
      (tweet_from,)
    )
    self.connection.commit()

  def recall_telling(self, tweet):
    """
    Fetches the story state for the given tweet. If no such state exists,
    returns None. Returns a tuple of reader, story_title, story_author,
    story_node, story_state, and is_head. The story state JSON will be unpacked
    into a simple Python object.
    """
    cur = self.connection.cursor()
    cur.execute(
      """
SELECT reader, story, author, node, state, is_head
FROM tellings WHERE tweet = ?;
      """,
      (tweet,)
    )
    row = cur.fetchone()
    if not row:
      return None
    else:
      return (
        row["reader"],
        row["story"],
        row["author"],
        row["node"],
        json.loads(row["state"]),
        row["is_head"]
      )

  def find_cached(self, title, author=None, is_module=False):
    """
    Looks up a story or module in the cache. Returns None if the given item
    isn't cached. Guesses when there are multiple matching items (only possible
    when author is not given).
    """
    cache = self.module_cache if is_module else self.story_cache
    if author:
      k = title + "::" + author
      item = cache.get(k, None)
      if item:
        age, st = item
        cache[k] = (0, st)
        return st
      else:
        return None
    else:
      possible = []
      for sk in cache:
        c_title, c_author = sk.split("::")
        if title == c_title:
          possible.append(sk)
      if not possible:
        return None
      sk = sorted(possible)[0]
      item = cache.get(sk, None)
      if item:
        age, st = item
        cache[sk] = (0, st)
        return st
      else:
        return None

  def cache_story(self, story, is_module=False):
    """
    Caches the given story (or module), booting out the oldest cached item if
    there are too many cached.
    """
    cache = self.module_cache if is_module else self.story_cache
    cache_limit = (
      config.MODULE_CACHE_SIZE
        if is_module
        else config.STORY_CACHE_SIZE
    )
    k = story.title + "::" + story.author
    if k in cache:
      # already cached: replace and update age
      cache[k] = (0, story)
    else:
      # not cached yet, first shrink cache if required:
      if len(cache) >= config.MODULE_CACHE_SIZE:
        oldest = None
        for sk in cache:
          age, st = cache[sk]
          if oldest == None or age > oldest[1]:
            oldest = (sk, age)

        del cache[oldest[0]]

      # now update cache ages
      for sk in cache:
        age, st = cache[sk]
        cache[sk] = (age+1, st)
      # now add to cache at age 0
      cache[k] = (0, story)
