"""CASE-2026-1024-02 headless runner: 2 shots on local ComfyUI MiniMax H3.

6s 精简版 · 宅舞 · 小红书（循环优先）。bar 吸附 2 镜降级（95.75 BPM 网格枚举
结论，见案例 §1）：镜 1 = 起手 hook + ①眼（合并），镜 2 = ③胸/腰 drop 爆点 +
⑤小腿收尾动作 + 定格。

接线策略（按 DG-015 降权规则 + CASE-01 v2 实证）：
- 镜 1（正面近景，H3 默认构图）：纯 Ref2VA——CASE-01 v1 同构图镜无需锚点即通过
- 镜 2（过肩特写→中景）：Hybrid + first_frame 构图锚点（复用 CASE-01 v2 的
  OTS 特写锚点 crops，同角色同影棚）；提示词起手姿态与锚点对齐（放弃「从背身
  环绕」运镜描述——H3 环绕不可靠，锚点链已把帧 0 钉在过肩特写）
- 镜 2 同时是 **DG-017 数据点**：3.41s 长于 CASE-01 v2 的 2.5s 特写镜——若漂移
  仍在 ~1–2s 内发生，「短镜抗漂移」假设需修正为「特写镜须更短」或证伪

受控项：seed 基 2026102400+50+idx、音频 lock_source 接线、风格/负面栈、战斗
LoRA 清零，均与 CASE-01 一致。

Usage: python run_case02.py        # shots 1 and 2, sequential
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request



BASE = "http://127.0.0.1:8188"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # skill root
SNAP = os.path.join(ROOT, "scripts", "h3_snapshot.json")
ASSETS = os.path.join(ROOT, "cases", "assets")
OUTDIR = os.path.join(_env.get_comfy_output() or ".", "CASE-2026-1024-02")
STATUS = os.path.join(ASSETS, "run_status_case02.json")
CLIENT = "short-dance-choreo"
SEED_BASE = 2026102400 + 50  # 2026102451/452，避开 CASE-01 的 201–206

STYLE = ("Crisp clean 2D cel-shaded anime linework, stable frames, vivid "
         "specular highlights, no photorealism.")

# Ref2VA header (shot 1): @image#1 = full-body ref, @image#2 = bust ref
SUBJ_HEAD_REF = """subject_definitions:
@image#1 is the full-body character reference of the girl: long blonde hair in low twin-tails tied with black ribbon bows, large golden-amber eyes, a white leotard-style mini dress with a gold ankh emblem at the chest, black off-shoulder sleeves with white cuffs, a long white waist sash, white thigh-high stockings with garter straps, and white lace-up boots with small wing accents. All proportions and details define her canonical design.
@image#2 is the close-up portrait reference of the same girl, defining her face, eye color and facial details precisely.
<Audio 1> is the background music track of this shot: a sweet 95.75 BPM ukulele rhythm with light percussion. It is directly reused as the target video's complete final audio track.

summary:
[reference generation] One continuous {dur}s dance shot of the girl defined by @image#1 and @image#2, performing a sweet otaku-style dance in a pure-color photo studio. {summary}

detailed_description:
2D cel-shaded anime style, clean lineart, rich specular highlights, soft studio lighting on a clean solid pale-pink backdrop.
[Shot {idx}] {desc}

visual_rules:
- locked character identity to @image#1 and @image#2 throughout the shot
- camera: {camera}
- the backdrop stays the clean solid pale-pink studio background, unchanged, never repainted
- tone: sweet and energetic, never fanservice-heavy
- stable hands with correct finger count; no text, no watermark"""

# Hybrid header (shot 2): @image#1 = first_frame anchor, #2 = full-body, #3 = bust
SUBJ_HEAD_HYB = """subject_definitions:
@image#2 is the full-body character reference of the girl: long blonde hair in low twin-tails tied with black ribbon bows, large golden-amber eyes, a white leotard-style mini dress with a gold ankh emblem at the chest, black off-shoulder sleeves with white cuffs, a long white waist sash, white thigh-high stockings with garter straps, and white lace-up boots with small wing accents. All proportions and details define her canonical design.
@image#3 is the close-up portrait reference of the same girl, defining her face, eye color and facial details precisely.
@image#1 is the exact opening-frame anchor of this shot: it locks the camera framing, her pose at frame 0 and the clean solid pale-pink studio backdrop. Begin the shot from this composition and keep every design detail and the backdrop unchanged.
<Audio 1> is the background music track of this shot: a sweet 95.75 BPM ukulele rhythm with light percussion, the drum hitting heavier in this segment. It is directly reused as the target video's complete final audio track.

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

# shot: (dur_request_s, summary, desc, camera)
SHOTS = {
    1: (2.53, "opening hook fused with the eye anchor: fists winding up then a "
              "snapping heart gesture with a bright locked gaze",
        "The girl faces the lens directly in a frontal medium close-up, both hands "
        "in fists held at her chest, winding up. On the first beat she snaps both "
        "hands open into a heart gesture, eyes bright and locked on the lens, mouth "
        "corners rising with the beat, fingers steady. Her face sits in the upper "
        "third of the frame.",
        "fixed tripod, medium close-up, front view"),
    2: (3.41, "drop burst from the anchored over-the-shoulder close-up: wide arm "
              "expansion, freeze, then a pull-back to medium for the closing steps",
        "The camera holds the over-the-shoulder close-up from behind her right "
        "shoulder with only a slight handheld drift: the back of her head and hair "
        "sit along the right edge, her face turned back toward the lens in near "
        "profile in the upper third. On the heavy drum downbeat she throws both "
        "arms wide, chest naturally expanding, arms rising then freezing in a held "
        "pose, back straight, expression confident. The camera then slowly pulls "
        "back to a medium shot as she alternates her feet in gentle steps, hands "
        "swinging lightly, the rhythm easing into a final freeze with both hands "
        "back in fists at her chest. Torso and both feet fully inside frame.",
        "handheld over-the-shoulder close-up, then slow pull-back to medium shot"),
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
    hybrid = idx == 2  # 过肩特写→中景镜走锚点链（DG-015 降权动作①）
    g["55"]["inputs"]["prompt"] = STYLE
    if hybrid:
        g["97"]["inputs"]["prompt"] = SUBJ_HEAD_HYB.format(
            dur=dur, summary=summary, desc=desc, camera=camera, idx=idx)
        g["121"]["inputs"]["image"] = "fioni_full.png"
        g["122"]["inputs"]["image"] = "fioni_bust.png"
        g["300"] = {"class_type": "LoadImage",
                    "inputs": {"image": "case02_anchor2.png"}}
    else:
        g["97"]["inputs"]["prompt"] = SUBJ_HEAD_REF.format(
            dur=dur, summary=summary, desc=desc, camera=camera, idx=idx)
        g["121"]["inputs"]["image"] = "fioni_full.png"
        g["122"]["inputs"]["image"] = "fioni_bust.png"
    g["27"]["inputs"]["value"] = dur
    g["11"]["inputs"]["noise_seed"] = SEED_BASE + idx
    g["21"]["inputs"]["filename_prefix"] = "CASE-2026-1024-02/shot%d" % idx
    for pass_node in ("7", "14"):
        n = g[pass_node]["inputs"]
        n["audio_mode"] = "lock_source"
        n["add_source_as_reference"] = True
        n["drive_audio"] = ["200", 0]
        n["final_audio"] = ["200", 0]
        if hybrid:
            n["task_type"] = "Hybrid"
            n["first_frame"] = ["300", 0]
    g["200"] = {"class_type": "LoadAudio",
                "inputs": {"audio": "case02_s%d.wav" % idx}}
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
    status = {"case": "CASE-2026-1024-02", "shots": {}, "started": time.time()}
    only = [int(a) for a in sys.argv[1:]] or sorted(SHOTS)
    for idx in only:
        dur, summary, desc, camera = SHOTS[idx]
        g = build_graph(idx, dur, summary, desc, camera)
        entry = {"dur_request": dur, "state": "submitting",
                 "route": "Hybrid+anchor" if idx == 2 else "Ref2VA"}
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
        print("shot%d submitted pid=%s dur=%.2f (%s)" % (idx, pid, dur, entry["route"]))
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        state, errs = wait_done(pid, 2700)  # 45 min per shot
        entry["state"] = state
        if state != "done":
            entry["errors"] = str(errs)[:800] if errs else None
            print("shot%d %s" % (idx, state))
            json.dump(status, open(STATUS, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            break
        src = None
        for name in sorted(os.listdir(OUTDIR)) if os.path.isdir(OUTDIR) else []:
            if name.startswith("shot%d_0000" % idx) and name.endswith(".mp4"):
                src = os.path.join(OUTDIR, name)
        if src:
            dst = os.path.join(ASSETS, "case02_shot%d.mp4" % idx)
            shutil.copy2(src, dst)
            entry["file"] = dst
            print("shot%d done -> %s" % (idx, dst))
        else:
            entry["state"] = "done_no_file"
            print("shot%d done but output file not found in %s" % (idx, OUTDIR))
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("CASE-02 RUNNER FINISHED")


if __name__ == "__main__":
    main()
