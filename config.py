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
  "last_processed_mention": "INTEGER",
  "unique_counter": "INTEGER",
}

STORIES_DIRECTORY = "stories"
MODULES_DIRECTORY = "modules"

TITLE_DISTANCE_THRESHOLD = 6

ACTION_DISTANCE_THRESHOLD = 4

MODULE_CACHE_SIZE = 128
STORY_CACHE_SIZE = 1024

NTAG_SIZE = 4

#TAGCHARS = "-_/\\|'\"[]{}()+=<>,.!$%^&*~`ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

TAGCHARS = [
  chr(x) for x in [
0x1F435,
0x1F412,
0x1F98D,
0x1F436,
0x1F415,
0x1F429,
0x1F43A,
0x1F98A,
0x1F431,
0x1F408,
0x1F981,
0x1F42F,
0x1F405,
0x1F406,
0x1F434,
0x1F40E,
0x1F984,
0x1F993,
0x1F98C,
0x1F42E,

0x1F402,
0x1F403,
0x1F404,
0x1F437,
0x1F416,
0x1F417,
0x1F43D,
0x1F40F,
0x1F411,
0x1F410,
0x1F42A,
0x1F42B,
0x1F992,
0x1F418,
0x1F98F,
0x1F42D,
0x1F401,
0x1F400,
0x1F439,
0x1F430,

0x1F407,
0x1F43F,
0x1F994,
0x1F987,
0x1F43B,
0x1F428,
0x1F43C,
0x1F43E,

0x1F983,
0x1F414,
0x1F413,
0x1F423,
0x1F424,
0x1F425,
0x1F426,
0x1F427,
0x1F54A,
0x1F985,
0x1F986,
0x1F989,

0x1F438,

0x1F40A,
0x1F422,
0x1F98E,
0x1F40D,
0x1F432,
0x1F409,
0x1F995,
0x1F996,

0x1F40C,
0x1F98B,
0x1F41B,
0x1F41C,
0x1F41D,
0x1F41E,
0x1F997,
0x1F577,
0x1F578,
0x1F982,

0x1F490,
0x1F338,
0x1F4AE,
0x1F3F5,
0x1F339,
0x1F940,
0x1F33A,
0x1F33B,
0x1F33C,
0x1F337,

0x1F331,
0x1F332,
0x1F333,
0x1F334,
0x1F335,
0x1F33E,
0x1F33F,
0x2618 ,
0x1F340,
0x1F341,
0x1F342,
0x1F343,

0x1F347,
0x1F348,
0x1F349,
0x1F34A,
0x1F34B,
0x1F34C,
0x1F34D,
0x1F34E,
0x1F34F,
0x1F350,
0x1F351,
0x1F352,
0x1F353,
0x1F95D,
0x1F345,
0x1F965,

0x1F951,
0x1F346,
0x1F954,
0x1F955,
0x1F33D,
0x1F336,
0x1F952,
0x1F966,
0x1F344,
0x1F95C,
0x1F330,

0x1f574,
  ]
]
