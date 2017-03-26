"""
persist.py

Persistent storage for Firelight bot.
"""

import sqlite3
import os
import datetime

import config

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
      CREATE TABLE IF NOT EXISTS stories(
        id INTEGER PRIMARY KEY,
        reader TEXT NOT NULL,
        state TEXT NOT NULL
      );
      """
    )
    # TODO: More tables...
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
    cur.execute("UPDATE state SET ? = ?;", (key, value,))
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
    cur.execute("SELECT ? FROM state;", (key,))
    row = cur.fetchone()
    print("HZK", " | ".join("'" + str(val) + "'" for val in row))
    value = row[0]
    return value
