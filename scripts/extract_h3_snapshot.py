"""Extract embedded API prompt graph from an H3 output mp4 and summarize nodes."""
import json
import subprocess
import sys

sys.path.insert(0, "C:/Users/Admin/.workbuddy/binaries/python/envs/default/Lib/site-packages")
from static_ffmpeg import run

ffmpeg, ffprobe = run.get_or_fetch_platform_executables_else_raise()

src = sys.argv[1]
out = sys.argv[2] if len(sys.argv) > 2 else "h3_snapshot.json"

r = subprocess.run(
    [ffprobe, "-v", "quiet", "-show_entries", "format_tags=prompt", "-of", "json", src],
    capture_output=True, text=True)
tags = json.loads(r.stdout).get("format", {}).get("tags", {})
prompt_raw = tags.get("prompt")
if not prompt_raw:
    print("NO_EMBEDDED_PROMPT")
    sys.exit(1)

graph = json.loads(prompt_raw)
# VHS embeds the API graph directly (dict node_id -> {class_type, inputs})
with open(out, "w", encoding="utf-8") as f:
    json.dump(graph, f, ensure_ascii=False, indent=1)
print("SAVED", out, "| nodes:", len(graph))
print()
for nid, n in sorted(graph.items(), key=lambda kv: int(kv[0]) if kv[0].isdigit() else 0):
    ct = n.get("class_type", n.get("type", "?"))
    ins = n.get("inputs", {})
    # summarize scalar inputs only (links appear as [id, slot] lists)
    scal = {k: v for k, v in ins.items() if not isinstance(v, (list, dict))}
    links = {k: v for k, v in ins.items() if isinstance(v, list)}
    print("#%s %s" % (nid, ct))
    for k, v in scal.items():
        sv = str(v)
        print("    %s = %s" % (k, sv[:70] + ("..." if len(sv) > 70 else "")))
    for k, v in links.items():
        print("    %s <- #%s[%s]" % (k, v[0], v[1]))
