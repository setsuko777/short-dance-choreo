"""CASE-2026-1024-01 v2 runner: re-generate shots 4+5 with first_frame anchors.

Background (DG-015): in v1 pure Ref2VA mode, H3 ignored the textual push-in /
pull-back and viewpoint instructions - shot 4 came out as a back three-quarter
medium instead of the over-the-shoulder close-up, shot 5 as a frontal full body
instead of the pure side-profile thighs-to-feet framing. QA check 1 therefore
failed on 景别 for ④⑤ (all 5 anchor actions were correct).

v2 fix: switch shots 4+5 to the Hybrid route (task_type="Hybrid") and feed an
explicit first_frame anchor rendered from the same Fioni reference with local
Qwen-Image-Edit-2511 (see make_anchor.py). Frame 0 is then pinned to the intended
composition; ref images (@image#2/@image#3) still lock identity.

Controlled A/B: identical seeds (2026102400+idx), identical durations, identical
audio wiring, identical style/negative stack - only task_type + first_frame +
prompt ordinal renumbering differ. Shots 1/2/3/6 are reused from v1 untouched.

Usage: python run_case01_v2.py            # shots 4 and 5, sequential
       python run_case01_v2.py 4 5        # same, explicit
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request



BASE = "http://127.0.0.1:8188"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skill root
SNAP = os.path.join(ROOT, "scripts", "h3_snapshot.json")
ASSETS = os.path.join(ROOT, "cases", "assets")
OUTDIR = os.path.join(_env.get_comfy_output() or ".", "CASE-2026-1024-01-v2")
STATUS = os.path.join(ASSETS, "run_status_v2.json")
CLIENT = "short-dance-choreo"
V2_SHOTS = (4, 5)

STYLE = ("Crisp clean 2D cel-shaded anime linework, stable frames, vivid "
         "specular highlights, no photorealism.")

# v2 ordinal map (Hybrid route): Picture 1 = first_frame anchor, Picture 2 =
# full-body ref, Picture 3 = bust ref, Audio 1 = drive audio.
SUBJ_HEAD_V2 = """subject_definitions:
@image#2 is the full-body character reference of the girl: long blonde hair in low twin-tails tied with black ribbon bows, large golden-amber eyes, a white leotard-style mini dress with a gold ankh emblem at the chest, black off-shoulder sleeves with white cuffs, a long white waist sash, white thigh-high stockings with garter straps, and white lace-up boots with small wing accents. All proportions and details define her canonical design.
@image#3 is the close-up portrait reference of the same girl, defining her face, eye color and facial details precisely.
@image#1 is the exact opening-frame anchor of this shot: it locks the camera framing, her pose at frame 0 and the clean solid pale-pink studio backdrop. Begin the shot from this composition and keep every design detail and the backdrop unchanged.
<Audio 1> is the background music track of this shot: a sweet 95.5 BPM ukulele rhythm with light percussion. It is directly reused as the target video's complete final audio track.

summary:
[reference generation] One continuous {dur}s dance shot of the girl defined by @image#2 and @image#3, performing a sweet otaku-style dance in a pure-color photo studio, starting exactly from the @image#1 opening-frame composition. {summary}

detailed_description:
2D cel-shaded anime style, clean lineart, rich specular highlights, soft studio lighting on a clean solid pale-pink backdrop.
[Shot {idx}] {desc}

visual_rules:
- locked character identity to @image#2 and @image#3 throughout the shot
- the opening composition of @image#1 is the exact frame 0 of this shot; do not reframe away from it
- camera: {camera}
- the backdrop stays the clean solid pale-pink studio background, unchanged, never repainted
- tone: sweet and energetic, never fanservice-heavy
- stable hands with correct finger count; no text, no watermark"""

# v2 shot 4/5 descriptions: rewritten to start from the anchored frame-0 pose
# (v1 wording described a camera move that the anchor now performs at frame 0).
SHOTS_V2 = {
    4: (2.53, "drop burst: a wide arm expansion frozen on the heavy drum",
        "The camera holds the over-the-shoulder close-up from behind her right shoulder "
        "with only a slight handheld drift: the back of her head and hair sit along the "
        "right edge, her face turned back toward the lens in near profile in the upper "
        "third. On the heavy drum downbeat she throws both arms wide, chest naturally "
        "expanding, arms rising then freezing in a held pose, back straight, expression "
        "confident. Torso fully inside frame.",
        "handheld over-the-shoulder close-up, held framing"),
    5: (2.52, "thigh close-up: a knee-in tap with a light skirt swirl",
        "The camera holds the pure side-profile medium framing from thighs to boots with "
        "a barely-there slow drift. She shifts her weight onto her left leg, draws the "
        "right knee inward then taps the floor, her skirt and long waist sash swirling "
        "lightly, hands returning to her chest. Thighs to feet fully inside frame.",
        "fixed side-profile medium shot, thighs to boots"),
}

COMBAT_LORAS = ("159", "162", "166", "169")  # H3_Combat_V2 / GunFu -> zeroed


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)


def build_graph(idx, dur, summary, desc, camera):
    with open(SNAP, encoding="utf-8") as f:
        g = json.load(f)
    g["55"]["inputs"]["prompt"] = STYLE
    g["97"]["inputs"]["prompt"] = SUBJ_HEAD_V2.format(
        dur=dur, summary=summary, desc=desc, camera=camera, idx=idx)
    g["121"]["inputs"]["image"] = "fioni_full.png"
    g["122"]["inputs"]["image"] = "fioni_bust.png"
    g["27"]["inputs"]["value"] = dur
    g["11"]["inputs"]["noise_seed"] = 2026102400 + idx
    g["21"]["inputs"]["filename_prefix"] = "CASE-2026-1024-01-v2/shot%d" % idx
    for pass_node in ("7", "14"):
        n = g[pass_node]["inputs"]
        n["audio_mode"] = "lock_source"
        n["add_source_as_reference"] = True
        n["drive_audio"] = ["200", 0]
        n["final_audio"] = ["200", 0]
        # v2: Hybrid route with an explicit first_frame composition anchor.
        n["task_type"] = "Hybrid"
        n["first_frame"] = ["300", 0]
    g["200"] = {"class_type": "LoadAudio",
                "inputs": {"audio": "case01_s%d.wav" % idx}}
    g["300"] = {"class_type": "LoadImage",
                "inputs": {"image": "case01_anchor%d.png" % idx}}
    for nid in COMBAT_LORAS:
        g[nid]["inputs"]["strength_model"] = 0.0
    return g


def wait_done(pid, timeout_s):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
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
                return ("error", errs) if errs else ("done", None)
        time.sleep(20)
    return ("timeout", None)


def main():
    os.makedirs(ASSETS, exist_ok=True)
    status = {"case": "CASE-2026-1024-01-v2", "shots": {}, "started": time.time()}
    only = [int(a) for a in sys.argv[1:]] or list(V2_SHOTS)
    for idx in only:
        dur, summary, desc, camera = SHOTS_V2[idx]
        g = build_graph(idx, dur, summary, desc, camera)
        entry = {"dur_request": dur, "state": "submitting"}
        status["shots"]["shot%d" % idx] = entry
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        try:
            r = post("/prompt", {"prompt": g, "client_id": CLIENT})
        except urllib.error.HTTPError as e:
            body = e.read().decode("utf-8", "ignore")[:600]
            entry.update(state="submit_failed", error=body)
            print("shot%d SUBMIT FAILED: %s" % (idx, body))
            json.dump(status, open(STATUS, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            if "CUDA" in body or "memory" in body.lower():
                break
            continue
        pid = r.get("prompt_id")
        entry["prompt_id"] = pid
        entry["state"] = "running"
        print("shot%d submitted pid=%s dur=%.2f" % (idx, pid, dur))
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        state, errs = wait_done(pid, 2700)  # 45 min per shot
        entry["state"] = state
        if state != "done":
            entry["errors"] = str(errs)[:800] if errs else None
            print("shot%d %s" % (idx, state))
            json.dump(status, open(STATUS, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            break  # OOM/timeout: stop queueing more
        src = None
        for name in sorted(os.listdir(OUTDIR)) if os.path.isdir(OUTDIR) else []:
            if name.startswith("shot%d_0000" % idx) and name.endswith(".mp4"):
                src = os.path.join(OUTDIR, name)
        if src:
            dst = os.path.join(ASSETS, "shot%d_v2.mp4" % idx)
            shutil.copy2(src, dst)
            entry["file"] = dst
            print("shot%d done -> %s" % (idx, dst))
        else:
            entry["state"] = "done_no_file"
            print("shot%d done but output file not found in %s" % (idx, OUTDIR))
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("V2 RUNNER FINISHED")


if __name__ == "__main__":
    main()
