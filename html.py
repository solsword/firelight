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
  <style>
body {{
  font-size: 22pt;
  text-align: right;
  background-color: #666;
}}

#title {{
  text-align: center;
  margin: 1em auto 0 auto;
  min-width: 8em;
  width: 50%;
  padding: 0.6em;
  color: black;
  background-color: #eee;
  border-top: 2pt solid #aaa;
  border-left: 2pt solid #aaa;
  border-right: 2pt solid #aaa;
  border-radius: 4pt 4pt 0 0;
}}

#content {{
  text-align: left;
  margin: 0 auto 0 auto;
  padding: 1em;
  min-width: 20em;
  width: 90%;
  color: black;
  background-color: #ddd;
  border: 2pt solid #aaa;
  border-radius: 4pt;
}}

#reset {{
  display: inline-block;
  position: relative;
  top: 0pt;
  right: 5%;

  font-size: 20pt;
  padding: 4pt 6pt 4pt 6pt;
  border-top: 2pt solid #999;
  border-left: 2pt solid black;
  border-right: 2pt solid black;
  border-bottom: 2pt solid black;
  border-radius: 0 0 4pt 4pt;
  background-color: #aaa;
  color: #444;
}}

#reset:active {{
  border-top: 2pt solid #999;
  border-left: 2pt solid #999; 
  border-right: 2pt solid #999; 
  border-bottom: 2pt solid #999; 
  color: #666;
  background-color: #999;
}}

a {{
  color: black;
  text-decoration: none;
}}

a:visited {{
  color: black;
  text-decoration: none;
}}
  </style>
  <script type="text/javascript">
STORY = {story_content};
{engine}
  </script>
</head>
<body>
  <div id="title">
    {title}
  </div>
  <div id="content">
    Loading story...
  </div>
  <button type="button" id="reset">Start Over</button>
</body>
</html>
"""

def package(story):
  with open("story_engine.js", 'r') as fin:
    ejs = fin.read()

  return TEMPLATE.format(
    title=story.name.title(),
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

