#!/usr/bin/env python3
"""
html.py

Packages firelight stories as HTML files.
"""

import json

from packable import pack, unpack
from story import Story

TEMPLATE = """\
<html>
<head>
  <title>{title}</title>
  <script type="text/javascript">
STORY = {story_content};
{engine}
  </script>
</head>
<body>
  <div id="content">
    Loading story...
  </div>
  <input type="button" id="reset">Start Over</input>
</body>
</html>
"""

def package(story):
  with open("story_engine.js", 'r') as fin:
    ejs = fin.read()

  return TEMPLATE.format(
    title=story.name,
    story_content = pack(story),
    engine = ejs
  )

if __name__ == "__main__":
  import sys, os
  if len(sys.argv) < 2:
    print("Error: Missing argument 'target stories'", file=sys.stderr)
  for tf in sys.argv[1:]:
    with open(tf, 'r') as fin:
      html = package(unpack(json.load(fin), Story))
      basename = os.path.basename(tf)
      output = "{}.html".format(basename)
      i = 0
      while os.path.exists(output):
        old = output
        output = "{}.{}.html".format(basename, i)
        print(
          "Warning: target file '{}' already exists, using '{}' instead..."
          .format(old, output),
          file=sys.stderr
        )
        i += 1

      with open(output, 'w') as fout:
        fout.write(html)

