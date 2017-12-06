#!/usr/bin/env python
"""
test.py

Unit tests.
"""

import traceback
import sys
import io

import utils

import config

from packable import pack, unpack
from diffable import diff

from story import StoryNode, Story
from state import StateChange, SetValue, IncrementValue, InvertValue

from parse import reflow, remove_comments
from parse import parse_story, render_story, parse_first_node, render_node
import parse

import macro

import fake_api
import load_stories
import bot
import rdb

all_tests = []
def test(f):
  all_tests.append(f)
  return f

def mktest_packable(cls):
  @test
  def test_packable():
    test_stuff = cls._pack_.__doc__.split("```")

    tinst = eval(utils.dedent(test_stuff[1]))
    tobj = eval(utils.dedent(test_stuff[2]))

    uinst = unpack(tobj, cls)
    pobj = pack(tinst)
    urec = unpack(pobj, cls)
    prec = pack(uinst)

    assert tinst == uinst, (
      (
        "Unpacked object doesn't match eval'd version:\n```\n{}\n```\n{}\n```"
        "\nDifferences:\n  {}"
      ).format(str(tinst), str(uinst), "\n  ".join(diff(tinst, uinst)))
    )

    assert pobj == tobj, (
      (
        "Packed object doesn't match given:\n```\n{}\n```\n{}\n```"
        "\nDifferences:\n  {}"
      ).format(
        str(tobj),
        str(pobj),
        "\n  ".join(diff(tobj, pobj))
      )
    )
    assert tinst == urec, (
      (
        "Pack/unpacked object doesn't match:\n```\n{}\n```\n{}\n```"
        "\nDifferences:\n  {}"
      ).format(
        str(tinst),
        str(urec),
        "\n  ".join(diff(tinst, urec))
      )
    )
    assert tobj == prec, (
      (
        "Unpack/packed object doesn't match:\n```\n{}\n```\n{}\n```"
        "\nDifferences:\n  {}"
      ).format(
        str(tobj),
        str(prec),
        "\n  ".join(diff(tobj, prec))
      )
    )

    return True

  test_packable.__name__ = "test_" + cls.__name__.lower() + "_packing"

for cls in [ StoryNode, Story ]:
  mktest_packable(cls)

@test
def test_parse_first_node():
  test_stuff = parse_first_node.__doc__.split("```")

  tinst = eval(utils.dedent(test_stuff[1]))
  tstr = reflow(remove_comments(utils.dedent(test_stuff[2])))

  uinst, leftovers = parse_first_node(tstr)
  assert isinstance(uinst, StoryNode), (
    "Failed to parse a node from:\n```\n{}\n``".format(tstr)
  )
  assert leftovers.strip() == "", (
    "Parsed node had leftovers:\n```\n{}\n```".format(leftovers)
  )
  rstr = render_node(tinst)

  urstr = render_node(uinst)
  ruinst, leftovers = parse_first_node(rstr)
  assert isinstance(ruinst, StoryNode), (
    "Failed to re-parse a node from:\n```\n{}\n``".format(rstr)
  )
  assert leftovers.strip() == "", (
    "Re-parsed node had leftovers:\n```\n{}\n```".format(leftovers)
  )

  assert tinst == uinst, (
    (
      "Parsed Story doesn't match eval'd version:\n```\n{}\n```\n{}\n```"
      "\nDifferences:\n  {}"
    ).format(str(tinst), str(uinst), "\n  ".join(diff(tinst, uinst)))
  )

  assert rstr == urstr, (
    (
      "Rendered Story doesn't match re-rendered version:\n```\n{}\n```\n{}\n```"
      "\nDifferences:\n  {}"
    ).format(
      str(rstr),
      str(urstr),
      "\n  ".join(diff(rstr, urstr))
    )
  )

  assert tinst == ruinst, (
    (
      "Re-parsed Story doesn't match original:\n```\n{}\n```\n{}\n```"
      "\nDifferences:\n  {}"
    ).format(
      str(tinst),
      str(ruinst),
      "\n  ".join(diff(tinst, ruinst))
    )
  )

  return True

@test
def test_parse_story():
  test_stuff = parse_story.__doc__.split("```")

  tinst = eval(utils.dedent(test_stuff[1]))
  tstr = utils.dedent(test_stuff[2])

  uinst = parse_story(tstr)
  rstr = render_story(tinst)

  urstr = render_story(uinst)
  ruinst = parse_story(rstr)

  assert tinst == uinst, (
    (
      "Parsed Story doesn't match eval'd version:\n```\n{}\n```\n{}\n```"
      "\nDifferences:\n  {}"
    ).format(str(tinst), str(uinst), "\n  ".join(diff(tinst, uinst)))
  )

  assert rstr == urstr, (
    (
      "Rendered Story doesn't match re-rendered version:\n```\n{}\n```\n{}\n```"
      "\nDifferences:\n  {}"
    ).format(
      str(rstr),
      str(urstr),
      "\n  ".join(diff(rstr, urstr))
    )
  )

  assert tinst == ruinst, (
    (
      "Re-parsed Story doesn't match original:\n```\n{}\n```\n{}\n```"
      "\nDifferences:\n  {}"
    ).format(
      str(tinst),
      str(ruinst),
      "\n  ".join(diff(tinst, ruinst))
    )
  )

  return True

def mktest_docstring(fcn):
  """
  Generic function for testing examples from docstrings. Looks for
  triple-backtick-quoted regions that are typed by their initial characters.
  There are three types of test:
    
    '>' indicates a test that must simply evaluate to a non-False value.
    '?' indicates an equality test, it should be followed by one or more '='
        blocks, which will each be compared against the '?' block after
        evaluation. Each '=' block must evaluate to a value equal to the '?'
        block.
    'x' indicates an error pathway check; this block should throw an exception
        when evaluated. Use one or more following '!' blocks to name the
        acceptable exception(s).

  All test evaluation will take place in the context of the module that the
  given function comes from.
  """
  @test
  def the_test():
    nonlocal fcn
    test_stuff = fcn.__doc__.split("```")
    native_module = sys.modules[fcn.__module__]
    native_context = native_module.__dict__

    test_eval_true = []
    test_cmp_equal = []
    test_raises = []
    for raw in test_stuff:
      test = raw.strip()
      if not test or test[0] not in ">?=x!":
        continue
      ttype = test[0]
      test = utils.dedent(test[1:]).strip()
      if ttype == '>':
        test_eval_true.append(test)
      elif ttype == '?':
        test_cmp_equal.append((test, []))
      elif ttype == '=':
        if test_cmp_equal:
          test_cmp_equal[-1][1].append(test)
        else:
          test_cmp_equal.append((test, []))
      elif ttype == 'x':
        test_raises.append((test, []))
      elif ttype == '!':
        if test_raises:
          test_raises[-1][1].append(test)
        else:
          test_raises.append((test, []))

    for test in test_eval_true:
      assert eval(test, native_context), "Eval test failed:\n" + test

    for test, against in test_cmp_equal:
      base = eval(test, native_context)
      for ag in against:
        agval = eval(ag, native_context)
        assert base == agval, (
          (
            "Test items not equal:\n```\n{}\n```\n{}\n```"
            "\nDifferences:\n  {}"
          ).format(
            base,
            agval,
            "\n  ".join(diff(base, agval))
          )
        )

    for test, accept in test_raises:
      accept = tuple(eval(a, native_context) for a in accept)
      try:
        eval(test, native_context)
        assert False, "Test failed to raise an error. Expected:\n  {}".format(
          utils.or_strlist(a.__name__ for a in alternatives)
        )
      except accept:
        pass
      except Exception as e:
        assert False, "Test raised unexpected {} error.".format(
          e.__class__.__name__
        )

    return True

  the_test.__name__ = "test_" + fcn.__name__
  return the_test

@test
def test_macro_regex():
  """
  Tests the macro.MACRO_START regex.
  """
  text = '''
(once~
 Disclaimer: This is a work of fiction and is not intended to aid in
 identifying edible mushrooms. NEVER eat a mushroom unless you are absolutely
 certain it is not poisonous, as many edible species look very similar to
 poisonous ones, and as a result fatal poisonings occur worldwide every year.
)
'''
  assert macro.MACRO_START.search(text, 0) != None, (
    "MACRO_START regex failed."
  )
  return True

for f in [
  utils.string_literal,
  utils.split_unquoted,
  utils.find_quoted_regions,
  utils.matching_brace,
  macro.parse_expr,
  macro.eval_expr,
  macro.eval_macro,
  macro.eval_text,
  parse.parse_metadata,
]:
  mktest_docstring(f)

@test
def test_bot_basics():
  """
  Tests the most basic bot functionality.
  """
  queue = [
    fake_api.FakeTweet( # will be ID 1
      "tester",
      None,
      "@{} tell help #ignored".format(config.MY_HANDLE)
    ),
    fake_api.FakeTweet( # will be ID 2
      "tester",
      4,
      "version"
    ),
    fake_api.FakeTweet( # will be ID 3
      "tester2",
      None,
      "tell \"Help\" by Peter Mawhorter"
    )
  ]
  output = io.StringIO()
  expect_printed = """\
Initiating streaming connection...
From: tester
Content: @gathering_round tell help #ignored
Handling non-reply as a general command.
From: tester
Content: version
In reply to: 4
Handling as reply to node 'help' in "Help" by Peter Mawhorter.
From: tester2
Content: tell "Help" by Peter Mawhorter
Handling non-reply as a general command.
"""
  expect_posted = """\
Id: 4
Replying to: 1
--------------------------------------------------------------------------------
@tester Firelight is an interactive story engine. Options appear in brackets. Help topics: [version] [links] 🐵🦊🐴🐃
================================================================================
Id: 5
Replying to: 2
--------------------------------------------------------------------------------
@tester This is Firelight version 0.1. [back] 🐒🦊🐴🐃
================================================================================
Id: 6
Replying to: 3
--------------------------------------------------------------------------------
@tester2 Firelight is an interactive story engine. Options appear in brackets. Help topics: [version] [links] 🦍🦊🐴🐃
================================================================================
"""

  # Clean out the test database:
  rdb.reset_db("test/test.db")

  # create a fake API object
  fcore = fake_api.FakeTwitterAPI(queue, output, "test/test.db")

  # load test stories
  load_stories.load_stories_from_directory(
    fcore,
    "test/stories"
  )
  load_stories.load_stories_from_directory(
    fcore,
    "test/modules",
    as_modules=True
  )

  # run the bot through one processing loop, capturing stdout
  old_stdout = sys.stdout
  capture = io.StringIO()
  sys.stdout = capture

  bot.run_bot(fcore, loop=False)

  sys.stdout = old_stdout

  posted = output.getvalue()
  printed = capture.getvalue()

  assert printed == expect_printed, (
    (
      "Bot printed output differs from expected output:\n```\n{}\n```\n{}\n```"
      "\nDifferences:\n  {}"
    ).format(
      printed,
      expect_printed,
      "\n  ".join(diff(printed, expect_printed))
    )
  )

  assert posted == expect_posted, (
    (
      "Bot posted output differs from expected output:\n```\n{}\n```\n{}\n```"
      "\nDifferences:\n  {}"
    ).format(
      posted,
      expect_posted,
      "\n  ".join(diff(posted, expect_posted))
    )
  )

  return True

def main():
  for t in all_tests:
    try:
      result = t()
    except Exception as e:
      result = e

    if result == True:
      print("{} ... passed".format(t.__name__))
    else:
      print("{} X".format(t.__name__))
      print()
      if isinstance(result, Exception):
        ef = ''.join(
          traceback.format_exception(
            type(result),
            result,
            result.__traceback__
          )
        )
        print(ef)
      else:
        print(result)
      print()


if __name__ == "__main__":
  main()
