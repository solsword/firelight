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
        "\n  ".join(
          "{} {}".format(key, config.STATE_STRUCTURE[key])
            for key in config.STATE_STRUCTURE
        )
      )
    ) # TODO: More stuff here?

    # Insert an empty row into our state table if it's empty:
    cur.execute("SELECT Count(*) from state;")
    if cur.fetchone()[0] == 0:
      cur.execute("INSERT INTO state VALUES(0);")

    cur.execute(
      """
      CREATE TABLE IF NOT EXISTS tellings(
        tweet INTEGER PRIMARY KEY,
        reader TEXT NOT NULL,
        story TEXT NOT NULL,
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

  def save_new_story(self, story):
    """
    Saves a new story to the database. Returns True if it succeeds, or False
    (and prints a warning message) if a story by that title already exists.
    """
    cur = self.connection.cursor()
    title = story.name.lower()
    cur.execute("SELECT * FROM stories WHERE title = ?;", (title,))
    if len(cur.fetchall()) > 0:
      print(
        "Warning: attempted to save new story with duplicate title '{}'."
        .format(
          title
        ),
        file=sys.stderr
      )
      return False

    # TODO: maximize packing efficiency
    cur.execute(
      "INSERT INTO stories(title, package) values(?, ?);",
      ( title, json.dumps(pack(story)) )
    )

    self.connection.commit()
    return True

  def update_story(self, story):
    """
    Updates a story in the database, overwriting the current contents.
    """
    cur = self.connection.cursor()
    # TODO: maximize packing efficiency
    cur.execute(
      "UPDATE stories SET package = ? WHERE title = ?;",
      ( json.dumps(pack(story)), story.name.lower() )
    )
    # TODO: Error handling here
    self.connection.commit()

  def recall_story(self, title):
    """
    Looks up a story in the database and returns it, or None if no such story
    exists.
    """
    cur = self.connection.cursor()
    cur.execute(
      "SELECT package FROM stories WHERE title = ?;",
      (title.lower(),)
    )
    rows = cur.fetchall()
    if len(rows) < 1:
      return None

    return unpack(json.loads(rows[0]["package"]), Story)

  def story_list(self):
    """
    Returns a list of all known story titles (each in lower case).
    """
    cur = self.connection.cursor()
    cur.execute("SELECT title FROM stories;")
    return [row["title"] for row in cur.fetchall()]

  def begin_telling(self, tweet, reader, title):
    """
    Creates a new telling in the database starting at the start node of the
    given story with the default starting state.
    """
    cur = self.connection.cursor()
    story = self.recall_story(title)
    # Create a new story for this reader and return its ID.
    cur.execute(
      (
        "INSERT INTO tellings(tweet, reader, story, node, state, is_head) "
        "values(?, ?, ?, ?, ?, ?);"
      ),
      (
        tweet,
        reader,
        story.name,
        story.start,
        json.dumps( story.initial_state() ),
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
        "INSERT INTO tellings(tweet, reader, story, node, state, is_head) "
        "SELECT ?, reader, story, ?, ?, 1 FROM tellings "
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
    returns None. Returns a tuple of reader, story_name, story_node,
    story_state, and is_head. The story state JSON will be unpacked into a
    simple Python object.
    """
    cur = self.connection.cursor()
    cur.execute(
      """
SELECT reader, story, node, state, is_head
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
        row["node"],
        json.loads(row["state"]),
        row["is_head"]
      )
