"""Fetch ComfyUI execution history, find a MiniMax H3 execution snapshot.

Prints candidate prompt_ids whose prompt graph contains H3-related nodes
(VHS_VideoCombine + LoadImage + PrimitiveString prompt nodes), and dumps
the most recent one's full prompt graph to a JSON file for reuse as a
headless submission template.
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import json
import sys
import urllib.request

BASE = "http://127.0.0.1:8188"
OUT = sys.argv[1] if len(sys.argv) > 1 else "h3_snapshot.json"


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=15) as r:
        return json.load(r)


hist = get("/history")
print("history entries:", len(hist))

H3_MARKERS = ("MiniMax", "H3", "minimax", "h3")
cands = []
for pid, item in hist.items():
    prompt = item.get("prompt")
    if not prompt:
        continue
    # API snapshot format: prompt is [extra_data, outputs, nodes]
    if isinstance(prompt, list):
        nodes = prompt[2] if len(prompt) > 2 else {}
    else:
        nodes = prompt
    if not isinstance(nodes, dict):
        continue
    blob = json.dumps(nodes)
    if any(m in blob for m in H3_MARKERS):
        status = item.get("status", {}).get("status_str", "?")
        cands.append((pid, status, nodes))

print("H3 candidates:", len(cands))
for pid, st, nodes in cands[:10]:
    types = {}
    for n in nodes.values():
        t = n.get("type", n.get("class_type", "?"))
        types[t] = types.get(t, 0) + 1
    print(" ", pid, st, dict(list(types.items())[:10]))

if not cands:
    print("NO_H3_SNAPSHOT")
    sys.exit(1)

# pick most recent: history keys are prompt_ids; use item order (newest first
# in ComfyUI's /history dict insertion order is not guaranteed, so prefer
# entries with execution_success and largest node count)
best = None
for pid, st, nodes in cands:
    if st != "success":
        continue
    if best is None or len(nodes) > len(best[2]):
        best = (pid, st, nodes)
if best is None:
    best = cands[0]

pid, st, nodes = best
with open(OUT, "w", encoding="utf-8") as f:
    json.dump({"prompt_id": pid, "nodes": nodes}, f, ensure_ascii=False, indent=1)
print("SAVED", OUT, "prompt_id", pid, "status", st, "nodes", len(nodes))
# show key node inputs for template editing
for nid, n in sorted(nodes.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
    t = n.get("type", "?")
    ins = n.get("inputs", {})
    keys = list(ins.keys())
    print("  #%s %s | inputs: %s" % (nid, t, keys))
