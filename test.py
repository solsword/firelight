#!/usr/bin/env python
"""
test.py

Unit tests.
"""

import traceback

import utils

from packable import pack, unpack
from diffable import diff

from story import StoryNode, Story
from state import StateChange, SetValue, IncrementValue, InvertValue

from parse import reflow, remove_comments
from parse import parse_story, render_story, parse_first_node, render_node

all_tests = []
def test(f):
  all_tests.append(f)
  return f

@test
def test_matching_brace():
  idx = utils.matching_brace("(())", 0)
  assert idx == 3, "Found wrong matching brace."

  idx = utils.matching_brace("(())", 1)
  assert idx == 2, "Found wrong matching brace."

  idx = utils.matching_brace("()()", 0)
  assert idx == 1, "Found wrong matching brace."

  idx = utils.matching_brace("()()", 2)
  assert idx == 3, "Found wrong matching brace."

  idx = utils.matching_brace("(()())", 0)
  assert idx == 5, "Found wrong matching brace."

  try:
    idx = utils.matching_brace("((())", 0)
    assert False, "Found a false match ({}).".format(idx)
  except utils.UnmatchedError:
    pass

  return True

def mktest_eval_equals(fcn):
  @test
  def test_function():
    test_stuff = fcn.__doc__.split("```")

    gla = dict(globals())
    gla[fcn.__name__] = fcn
    tfirst = eval(utils.dedent(test_stuff[1]), gla)
    tsecond = eval(utils.dedent(test_stuff[2]), gla)

    assert tfirst == tsecond, (
      (
        "First object doesn't match second:\n```\n{}\n```\n{}\n```"
        "\nDifferences:\n  {}"
      ).format(str(tfirst), str(tsecond), "\n  ".join(diff(tfirst, tsecond)))
    )

    return True

  test_function.__name__ = "test_" + fcn.__name__.lower() + "_example"

for f in [
  utils.string_literal,
  utils.split_unquoted,
]:
  mktest_eval_equals(f)

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
