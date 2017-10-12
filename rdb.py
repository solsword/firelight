#!/usr/bin/env python3
"""
rdb.py
Script for resetting the database.
"""

import sys

import config
import persist

def reset_db(filename):
  persist.Storage(filename).reset_database()

if __name__ == "__main__":
  if len(sys.argv) == 1:
    target = config.DB_FILE
  elif len(sys.argv) == 2:
    target = sys.argv[1]
  else:
    print(
      "Too many arguments (needs 0 or 1 = database filename).",
      file=sys.stderr
    )
    exit(1)

  reset_db(target)
