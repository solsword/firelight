// Self-contained javascript engine for Firelight.

// The "STORY" variable should be defined already.
// The HTML should have a node with ID "content".

/*
 * Fetches the current # location
 */
function get_location() {
  return window.location.hash.substr(1);
}

/*
 * Swaps the content to show the given node.
 */
function show_node(node) {
  content = document.getElementById("content");
  content.innerHTML = render_node(node);
}

/*
 * Returns HTML for the given node.
 */
function render_node(node) {
  console.log("N");
  console.log(node);
  result = node["content"];
  successors = node["successors"] || {};
  console.log("A");
  console.log(result);
  Object.keys(successors).forEach(function (key) {
    if (successors[key] instanceof Array) {
      target = successors[key][0]
      changes = successors[key][1]
    } else {
      target = successors[key]
      changes = []
    }
    result = result.replace(
      key,
      "<a href='#"
      + target
      + "' onclick='"
      + JSON.stringify(changes)
      + ".forEach(function (change) { implement_state_change(change); });'>["
      + key
      + "]</a>"
    );
  });
  console.log("B");
  console.log(result);
  return result;
}

/*
 * Implements a state change, updating the global STATE variable.
 */
function implement_state_change(change) {
  var bits = change.split(" ");
  var command = bits[0];
  var target = bits[1];
  var value = JSON.parse(bits.slice(2).join(" "));

  if (command == "set") {
    set_state_value(target, value);
  } else if (command == "add") {
    oldval = get_state_value(target);
    set_state_value(target, oldval + value);
  } else if (command == "invert") {
    oldval = get_state_value(target);
    set_state_value(target, -oldval);
  }
}

/*
 * Gets a state value using the given '.'-delimited key string.
 */
function get_state_value(target) {
  var tlist = target.split(".").reverse();

  var current = STATE;
  while (tlist.length > 0) {
    current = current[tlist.pop()];
  }

  return current;
}

/*
 * Sets a state value using the given '.'-delimited key string.
 */
function set_state_value(target, value) {
  var tlist = target.split(".").reverse();

  var current = STATE;
  while (tlist.length > 1) {
    current = current[tlist.pop()];
  }

  current[tlist[0]] = value;
}


/*
 * Resets the story state and starts over from the beginning.
 */
function reset() {
  STATE = {};
  window.location.hash = "";
  show_node(STORY["nodes"][STORY["start"]]);
}

// Get things started by resetting the story when the document loads, and also
// set up the "reset" button to do so on demand.
window.onload = function() {
  document.getElementById("reset").onclick = function() { reset(); }

  window.onhashchange = function () {
    node = STORY["nodes"][get_location()]
    if (node) {
      show_node(node);
    } else {
      show_node(STORY["nodes"][STORY["start"]]);
    }
  }

  reset();
}
