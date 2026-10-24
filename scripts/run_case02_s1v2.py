"""CASE-2026-1024-02 shot1 re-run (v2): Hybrid + first_frame anchor.

DG-015 single-dimension fix: the first shot1 run (Ref2VA) came out full-body at
frame 0 while the storyboard asks for a medium close-up (near shot) - the eye
anchor moment itself framed correctly, but the shot opens too wide. Fix = crop a
medium close-up anchor from the shot's own frame 0 (numeric bbox, proven pattern
from CASE-01 v2) and re-run shot 1 on the Hybrid route with the identical seed
(2026102451), duration (2.53s) and audio wiring - controlled A/B on route only.

Output: cases/assets/case02_shot1_v2.mp4
"""
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request

BASE = "http://127.0.0.1:8188"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "scripts", "h3_snapshot.json")
ASSETS = os.path.join(ROOT, "cases", "assets")
OUTDIR = "F:/MI10-PRO+/MI10-PRO+/MI10-Pro+/ComfyUI/output/CASE-2026-1024-02"
STATUS = os.path.join(ASSETS, "run_status_case02_s1v2.json")
CLIENT = "short-dance-choreo"

STYLE = ("Crisp clean 2D cel-shaded anime linework, stable frames, vivid "
         "specular highlights, no photorealism.")

SUBJ_HEAD_HYB = """subject_definitions:
@image#2 is the full-body character reference of the girl: long blonde hair in low twin-tails tied with black ribbon bows, large golden-amber eyes, a white leotard-style mini dress with a gold ankh emblem at the chest, black off-shoulder sleeves with white cuffs, a long white waist sash, white thigh-high stockings with garter straps, and white lace-up boots with small wing accents. All proportions and details define her canonical design.
@image#3 is the close-up portrait reference of the same girl, defining her face, eye color and facial details precisely.
@image#1 is the exact opening-frame anchor of this shot: it locks the camera framing, her pose at frame 0 and the clean solid pale-pink studio backdrop. Begin the shot from this composition and keep every design detail and the backdrop unchanged.
<Audio 1> is the background music track of this shot: a sweet 95.75 BPM ukulele rhythm with light percussion. It is directly reused as the target video's complete final audio track.

summary:
[reference generation] One continuous 2.53s dance shot of the girl defined by @image#2 and @image#3, performing a sweet otaku-style dance in a pure-color photo studio, starting exactly from the @image#1 opening-frame composition. opening hook fused with the eye anchor: fists winding up then a snapping heart gesture with a bright locked gaze

detailed_description:
2D cel-shaded anime style, clean lineart, rich specular highlights, soft studio lighting on a clean solid pale-pink backdrop.
[Shot 1] The girl faces the lens directly in a frontal medium close-up, both hands in fists held at her chest, winding up. On the first beat she snaps both hands open into a heart gesture, eyes bright and locked on the lens, mouth corners rising with the beat, fingers steady. Her face sits in the upper third of the frame.

visual_rules:
- locked character identity to @image#2 and @image#3 throughout the shot
- the opening composition of @image#1 is the exact frame 0 of this shot; do not reframe away from it
- camera: fixed tripod, medium close-up, front view
- the backdrop stays the clean solid pale-pink studio background, unchanged, never repainted
- tone: sweet and energetic, never fanservice-heavy
- stable hands with correct finger count; no text, no watermark"""

COMBAT_LORAS = ("159", "162", "166", "169")


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)


def main():
    with open(SNAP, encoding="utf-8") as f:
        g = json.load(f)
    g["55"]["inputs"]["prompt"] = STYLE
    g["97"]["inputs"]["prompt"] = SUBJ_HEAD_HYB
    g["121"]["inputs"]["image"] = "fioni_full.png"
    g["122"]["inputs"]["image"] = "fioni_bust.png"
    g["27"]["inputs"]["value"] = 2.53
    g["11"]["inputs"]["noise_seed"] = 2026102451  # identical to shot1 v1 run
    g["21"]["inputs"]["filename_prefix"] = "CASE-2026-1024-02/shot1v2"
    for pass_node in ("7", "14"):
        n = g[pass_node]["inputs"]
        n["audio_mode"] = "lock_source"
        n["add_source_as_reference"] = True
        n["drive_audio"] = ["200", 0]
        n["final_audio"] = ["200", 0]
        n["task_type"] = "Hybrid"
        n["first_frame"] = ["300", 0]
    g["200"] = {"class_type": "LoadAudio",
                "inputs": {"audio": "case02_s1.wav"}}
    g["300"] = {"class_type": "LoadImage",
                "inputs": {"image": "case02_s1_anchor.png"}}
    for nid in COMBAT_LORAS:
        g[nid]["inputs"]["strength_model"] = 0.0

    status = {"case": "CASE-2026-1024-02-s1v2", "state": "submitting",
              "started": time.time()}
    json.dump(status, open(STATUS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    try:
        r = post("/prompt", {"prompt": g, "client_id": CLIENT})
    except urllib.error.HTTPError as e:
        body = e.read().decode("utf-8", "ignore")[:600]
        status.update(state="submit_failed", error=body)
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("SUBMIT FAILED:", body)
        sys.exit(1)
    pid = r["prompt_id"]
    status.update(state="running", prompt_id=pid)
    json.dump(status, open(STATUS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("shot1v2 submitted pid=%s" % pid)
    t0 = time.time()
    while time.time() - t0 < 2700:
        try:
            h = get("/history/%s" % pid)
        except Exception:
            time.sleep(15)
            continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("completed"):
                msgs = st.get("messages", [])
                errs = [m for m in msgs if isinstance(m, (list, tuple))
                        and m and m[0] == "execution_error"]
                if errs:
                    status.update(state="error", errors=str(errs)[:800])
                    json.dump(status, open(STATUS, "w", encoding="utf-8"),
                              ensure_ascii=False, indent=1)
                    print("ERROR:", errs)
                    sys.exit(1)
                break
        time.sleep(20)
    src = None
    for name in sorted(os.listdir(OUTDIR)) if os.path.isdir(OUTDIR) else []:
        if name.startswith("shot1v2_0000") and name.endswith(".mp4"):
            src = os.path.join(OUTDIR, name)
    if not src:
        status.update(state="done_no_file")
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print("done but output not found in", OUTDIR)
        sys.exit(1)
    dst = os.path.join(ASSETS, "case02_shot1_v2.mp4")
    shutil.copy2(src, dst)
    status.update(state="done", file=dst)
    json.dump(status, open(STATUS, "w", encoding="utf-8"),
              ensure_ascii=False, indent=1)
    print("shot1v2 done ->", dst)


if __name__ == "__main__":
    main()
