#!/usr/bin/env python3
"""
debug.py

Story debugging tools.
"""

import sys

import story

from diffable import diff

import load_stories

def debug_explore(story, policy=None):
  """
  Starting with the start node of the given story, picks an arbitrary available
  link at each node and renders the text observed by doing so, ignoring links
  that go back to already-explored nodes. Returns a list of (node,
  observed-text, current-state) triples for each node explored. If given, the
  policy should map from node names to ordered lists of successor-node-names,
  and establishes a priority for choosing destinations. The policy does not
  have to be complete, and if it lists unreachable nodes, these will be
  ignored.
  """
  # TODO: What about conditional reachability?!? Tester (and at some point,
  # node logic) needs to respect this!
  visited = set()
  chronicle = []

  texts, at, state = story.begin()
  visited.add(at)
  chronicle.append((at, '\n\n'.join(texts), state))

  while True:
    successors = story.get(at).successors
    if policy and at in policy:
      ordered = []
      for dest in policy[at]:
        for sc in successors:
          if successors[sc][0] == dest:
            ordered.append(sc)
      remaining = [sc for sc in successors if sc not in ordered]
      ordered.extend(remaining)
    else:
      ordered = [sc for sc in successors]

    decision = None
    for sc in ordered:
      dest = successors[sc][0]
      if dest not in visited:
        decision = sc
        break

    if decision is None: # out of places to visit
      return chronicle

    texts, at, state = story.advance(at, state, decision)
    visited.add(at)
    chronicle.append((at, '\n\n'.join(texts), state))

  return chronicle

def fmt_chronicle(chronicle):
  """
  Formats a debug chronicle as pure text.
  """
  if not chronicle:
    return "<no results>"

  result = "Node: {}\nText: '''\n{}\n'''\nState:\n{}\n".format(
    *chronicle[0]
  )
  last_state = chronicle[0][2]

  for entry in chronicle[1:]:
    result += "Node: {}\nText: '''\n{}\n'''\nState changes:\n  {}\n".format(
      entry[0],
      entry[1],
      '\n  '.join(diff(last_state, entry[2]))
    )

  return result

def main(targets):
  """
  Takes story filenames and debugs each story, printing results to stdout.
  """
  for t in targets:
    st = load_stories.load_story_from_file(t)
    if not st:
      continue # warning already printed
    chronicle = debug_explore(st)
    print('-'*80)
    print(fmt_chronicle(chronicle))
    print('-'*80)

if __name__ == "__main__":
  main(sys.argv[1:])
