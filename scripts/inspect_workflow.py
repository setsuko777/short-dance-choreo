"""Inspect a ComfyUI UI-format workflow JSON: nodes, widgets, links."""
import json
import sys

path = sys.argv[1]
d = json.load(open(path, encoding="utf-8"))
print("top keys:", list(d.keys()))
nodes = d.get("nodes", [])
print("nodes:", len(nodes))
for n in nodes:
    t = n.get("type", "?")
    w = n.get("widgets_values", [])
    ins = {i.get("name"): i.get("link") for i in n.get("inputs", []) if isinstance(i, dict)}
    print("  id=%s type=%s" % (n.get("id"), t))
    print("     widgets:", str(w)[:100])
    if ins:
        print("     inputs:", ins)
print("links:", len(d.get("links", [])))
for lk in d.get("links", [])[:60]:
    # link format: [link_id, from_node, from_slot, to_node, to_slot, type]
    if isinstance(lk, list) and len(lk) >= 5:
        print("   link", lk[0], ":", lk[1], "[", lk[2], "] ->", lk[3], "[", lk[4], "]", lk[5] if len(lk) > 5 else "")
