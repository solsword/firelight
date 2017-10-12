"""
config.py

Configuration for firelight twitter bot.
"""

DEBUG = True

CHAR_LIMIT = 140

MY_HANDLE = "gathering_round"

DEFAULT_TOKENS_FILE = "tokens"

DB_FILE = "firelight.db"

STATE_STRUCTURE = {
  "last_processed_mention": "INTEGER"
}

STORIES_DIRECTORY = "stories"
