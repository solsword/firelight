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

from parse import parse_story, render_story, parse_first_node, render_node

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
def test_parse_node():
  test_stuff = parse_first_node.__doc__.split("```")

  tinst = eval(utils.dedent(test_stuff[1]))
  tstr = utils.dedent(test_stuff[2])

  uinst = parse_first_node(tstr)
  rstr = render_node(tinst)

  urstr = render_node(uinst)
  ruinst = parse_first_node(rstr)

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
