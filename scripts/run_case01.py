"""CASE-2026-1024-01 headless runner: 6 shots on local ComfyUI MiniMax H3.

Submits 6 shot graphs sequentially (VRAM-safe), polls history for completion,
copies outputs to cases/assets/. Progress written to cases/assets/run_status.json.

Deviations from the ditz5s snapshot template (documented, reversible):
  1. drive_audio wired (LoadAudio) + audio_mode=lock_source +
     add_source_as_reference=True  -> music becomes the shot soundtrack and an
     official <Audio 1> reference for motion timing (beat-driven dance).
  2. Combat-flavour LoRAs (H3_Combat_V2 x2, GunFu x2) zeroed -> sweet dance,
     not gunplay. Motion_Repair / turbo / speed_slider kept.
  3. ref images -> Fioni full-body + bust portrait (copied to ComfyUI input/).
  4. Per-shot prompt (English rendering of case-01 Chinese shot descriptions,
     same content), per-shot length/seed/filename_prefix.
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
OUTDIR = os.path.join(_env.get_comfy_output() or ".", "CASE-2026-1024-01")
STATUS = os.path.join(ASSETS, "run_status.json")
CLIENT = "short-dance-choreo"

STYLE = ("Crisp clean 2D cel-shaded anime linework, stable frames, vivid "
         "specular highlights, no photorealism.")

SUBJ_HEAD = """subject_definitions:
@image#1 is the full-body character reference of the girl: long blonde hair in low twin-tails tied with black ribbon bows, large golden-amber eyes, a white leotard-style mini dress with a gold ankh emblem at the chest, black off-shoulder sleeves with white cuffs, a long white waist sash, white thigh-high stockings with garter straps, and white lace-up boots with small wing accents. All proportions and details define her canonical design.
@image#2 is the close-up portrait reference of the same girl, defining her face, eye color and facial details precisely.
<Audio 1> is the background music track of this shot: a sweet 95.5 BPM ukulele rhythm with light percussion. It is directly reused as the target video's complete final audio track.

summary:
[reference generation] One continuous {dur}s dance shot of the girl defined by @image#1 and @image#2, performing a sweet otaku-style dance in a pure-color photo studio. {summary}

detailed_description:
2D cel-shaded anime style, clean lineart, rich specular highlights, soft studio lighting on a clean solid pale-pink backdrop.
[Shot 1] {desc}

visual_rules:
- locked character identity to @image#1 and @image#2 throughout the shot
- camera: {camera}
- the backdrop stays the clean solid pale-pink studio background, unchanged, never repainted
- tone: sweet and energetic, never fanservice-heavy
- stable hands with correct finger count; no text, no watermark"""

# shot: (dur_request_s, summary, desc, camera)
SHOTS = [
    (2.52, "opening hook: a heart gesture pushed toward the lens",
     "The girl stands three-quarter to camera in a full-body vertical composition, shoulders relaxed. On the first beat she brings both hands to her chest in a heart shape and slowly pushes it toward the lens, her head bobbing gently with the rhythm, expression sweet and confident. Head and shoes stay inside safe margins.",
     "fixed tripod, full body, three-quarter view"),
    (2.53, "eye close-up: a bright locked gaze with a snapping heart gesture",
     "The girl faces the lens directly in a medium close-up as the camera slowly pushes in. She snaps both hands open into a heart gesture, eyes bright and locked on the lens, mouth corners rising with the beat, fingers steady. Her face sits in the upper third of the frame.",
     "slow push-in, close-up, front view"),
    (2.52, "mouth close-up: lip sync and a deepening smile",
     "The girl in a three-quarter close-up cups her face with both hands then slowly opens them, lips moving with the beat as if singing along, her smile gradually deepening, eyes glancing at the lens through her fingers.",
     "fixed tripod, close-up, three-quarter view"),
    (2.53, "drop burst: a wide arm expansion frozen on the heavy drum",
     "The girl stands with her back to the soft light; the camera drifts from behind her shoulder into an over-the-shoulder close-up. On the heavy drum downbeat she throws both arms wide, chest naturally expanding, arms rising then freezing in a held pose, back straight, expression confident. Torso fully inside frame.",
     "handheld drift from behind shoulder to over-the-shoulder close-up"),
    (2.52, "thigh close-up: a knee-in tap with a light skirt swirl",
     "The girl in pure side profile shifts her weight onto one leg, draws the other knee inward then taps the floor, her skirt swirling lightly, hands returning to her chest, as the camera slowly pulls back to a medium shot. Thighs to feet fully inside frame.",
     "slow pull-back to medium shot, pure side view"),
    (2.34, "calf close-up: alternating steps easing into the closing freeze",
     "The girl faces the lens in a full-body shot, alternating steps with both feet, hands swinging gently, the rhythm slowing into a final freeze - the ending pose identical to the opening frame, both hands in a heart at the chest.",
     "fixed tripod, full body, front view"),
]

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
    g["97"]["inputs"]["prompt"] = SUBJ_HEAD.format(
        dur=dur, summary=summary, desc=desc, camera=camera)
    g["121"]["inputs"]["image"] = "fioni_full.png"
    g["122"]["inputs"]["image"] = "fioni_bust.png"
    g["27"]["inputs"]["value"] = dur
    g["11"]["inputs"]["noise_seed"] = 2026102400 + idx
    g["21"]["inputs"]["filename_prefix"] = "CASE-2026-1024-01/shot%d" % idx
    for pass_node in ("7", "14"):
        n = g[pass_node]["inputs"]
        n["audio_mode"] = "lock_source"
        n["add_source_as_reference"] = True
        n["drive_audio"] = ["200", 0]
        n["final_audio"] = ["200", 0]
    g["200"] = {"class_type": "LoadAudio",
                "inputs": {"audio": "case01_s%d.wav" % idx}}
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
    status = {"case": "CASE-2026-1024-01", "shots": {}, "started": time.time()}
    only = [int(a) for a in sys.argv[1:]] or list(range(1, 7))
    for idx in only:
        dur, summary, desc, camera = SHOTS[idx - 1]
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
        # collect output
        src = None
        for name in sorted(os.listdir(OUTDIR)) if os.path.isdir(OUTDIR) else []:
            if name.startswith("shot%d_0000" % idx) and name.endswith(".mp4"):
                src = os.path.join(OUTDIR, name)
        if src:
            dst = os.path.join(ASSETS, "shot%d.mp4" % idx)
            shutil.copy2(src, dst)
            entry["file"] = dst
            print("shot%d done -> %s" % (idx, dst))
        else:
            entry["state"] = "done_no_file"
            print("shot%d done but output file not found in %s" % (idx, OUTDIR))
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("RUNNER FINISHED")


if __name__ == "__main__":
    main()
