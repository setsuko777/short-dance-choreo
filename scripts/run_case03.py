"""CASE-2026-1024-03 headless runner: 6 shots on local ComfyUI MiniMax H3.

15s 完整版 · Hip-hop · B站（拍吸附兜底 + 短窗 downbeat 相位不稳定实证）。
窗口 = w03_lowride_15s.wav（源曲 12.45–27.45s，drop 实测 7.40s 落窗内 49.3%）。
分镜切点：0.00 / 2.41 / 4.75 / 7.09 / 9.43 / 11.77 / 15.00（拍吸附，4 拍间距）。

接线策略（DG-015 降权规则 + CASE-01 v2 / CASE-02 实证）：
- 镜 1（全身/四分之三侧）：Hybrid + first_frame = char_3q（H3 默认构图是正面全身，
  四分之三侧必须锚定）
- 镜 2（近景/正面）：Hybrid + first_frame = char_bust（正面胸像数值裁切）
- 镜 3（近景/四分之三侧）：Hybrid + first_frame = anchor3（3/4 侧胸像数值裁切）
- 镜 4（特写/过肩）：Hybrid + first_frame = ots（过肩特写锚点）
- 镜 5（中景/纯侧）：Hybrid + first_frame = side（纯侧大腿到靴锚点）
- 镜 6（全身/正面）：纯 Ref2VA——H3 默认构图即正面全身，无需锚点
- 每镜音频切片独立 lock_source；镜 6 提示词明示定格 ~2.8s 前完成（DG-018 对策：
  3.23s 请求 → 90 帧 = 3.75s，定格必须落在 trim 点之前）

受控项：seed 基 2026102400+60+idx、音频 lock_source 接线、风格/负面栈、战斗
LoRA 清零，均与 CASE-01/02 一致。

Usage: python run_case03.py [shot ...]   # default: all six, sequential
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
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "scripts", "h3_snapshot.json")
ASSETS = os.path.join(ROOT, "cases", "assets")
OUTDIR = os.path.join(_env.get_comfy_output() or ".", "CASE-2026-1024-03")
STATUS = os.path.join(ASSETS, "run_status_case03.json")
CLIENT = "short-dance-choreo"
SEED_BASE = 2026102400 + 60  # 261..266，避开 CASE-01 的 201–206 与 CASE-02 的 251–252

STYLE = ("Crisp clean 2D cel-shaded anime linework, stable frames, vivid "
         "specular highlights, no photorealism.")

IDENT = ("a streetwear girl: short dark-brown messy bob-cut hair, amber eyes, "
         "a black choker, an oversized gray hoodie with the hood down and "
         "sleeves rolled up, a small white winged print on the chest, black "
         "cargo pants and white high-top sneakers")

BG_LOCK = ("the backdrop stays the clean solid light-gray studio background, "
           "unchanged, never repainted")

AUDIO_LINE = ("<Audio 1> is the background music track of this shot: a 104.25 "
              "BPM hip-hop rhythm with a clear bass line and heavy drums. It "
              "is directly reused as the target video's complete final audio "
              "track.")

# Hybrid header: @image#1 = first_frame anchor, #2 = full-body ref, #3 = bust ref
SUBJ_HEAD_HYB = """subject_definitions:
@image#2 is the full-body character reference of the girl: {ident}. All proportions and details define her canonical design.
@image#3 is the close-up portrait reference of the same girl, defining her face, eye color and facial details precisely.
@image#1 is the exact opening-frame anchor of this shot: it locks the camera framing, her pose at frame 0 and the clean solid light-gray studio backdrop. Begin the shot from this composition and keep every design detail and the backdrop unchanged.
{audio}

summary:
[reference generation] One continuous {dur}s dance shot of the girl defined by @image#2 and @image#3, performing a cool street-hip-hop dance in a pure-color photo studio, starting exactly from the @image#1 opening-frame composition. {summary}

detailed_description:
2D cel-shaded anime style, clean lineart, rich specular highlights, hard-top studio lighting on a clean solid light-gray backdrop.
[Shot {idx}] {desc}

visual_rules:
- locked character identity to @image#2 and @image#3 throughout the shot
- the opening composition of @image#1 is the exact frame 0 of this shot; do not reframe away from it
- camera: {camera}
- {bg}
- tone: cool and confident, never fanservice-heavy
- stable hands with correct finger count; no text, no watermark
所有镜头中外观零漂移。背景全程保持首帧中的底色与图案，完全不变、不重绘。"""

# Ref2VA header (shot 6): @image#1 = full-body ref, @image#2 = bust ref
SUBJ_HEAD_REF = """subject_definitions:
@image#1 is the full-body character reference of the girl: {ident}. All proportions and details define her canonical design.
@image#2 is the close-up portrait reference of the same girl, defining her face, eye color and facial details precisely.
{audio}

summary:
[reference generation] One continuous {dur}s dance shot of the girl defined by @image#1 and @image#2, performing a cool street-hip-hop dance in a pure-color photo studio. {summary}

detailed_description:
2D cel-shaded anime style, clean lineart, rich specular highlights, hard-top studio lighting on a clean solid light-gray backdrop.
[Shot {idx}] {desc}

visual_rules:
- locked character identity to @image#1 and @image#2 throughout the shot
- camera: {camera}
- {bg}
- tone: cool and confident, never fanservice-heavy
- stable hands with correct finger count; no text, no watermark
所有镜头中外观零漂移。背景全程保持首帧中的底色与图案，完全不变、不重绘。"""

# shot: (dur, summary, desc, camera, anchor image or None for Ref2VA)
SHOTS = {
    1: (2.41,
        "opening hook: a street bounce stance settling into a shoulder-sink freeze",
        "The girl stands in a three-quarter side full-body shot, knees slightly "
        "bent keeping a relaxed bounce groove, hands in her hoodie pockets. On "
        "the first bass hit her shoulders sink slightly and both hands come up "
        "to framework at her chest, freezing there, expression cool. Her whole "
        "body from head to sneakers stays fully inside the frame with safety "
        "margins at top and bottom.",
        "fixed tripod, full body, three-quarter side view",
        "case03_char_3q.png"),
    2: (2.34,
        "eye anchor: cold gaze locked on the lens as the camera pushes in",
        "The girl faces the lens directly; the camera slowly pushes in to a "
        "medium close-up. Her head sways slightly with the beat, eyes locked "
        "on the lens, expressionless for half a beat, then her chin tucks "
        "slightly. Her face sits in the upper third of the frame.",
        "slow push-in, medium close-up, front view",
        "case03_char_bust.png"),
    3: (2.34,
        "mouth anchor: lips moving readable with the beat",
        "The girl is framed in a three-quarter side medium close-up, head "
        "tilted slightly, her mouth opening and closing with the beat, chin "
        "tucking then her head returning to center, expression cool and "
        "confident.",
        "fixed tripod, medium close-up, three-quarter side view",
        "case03_anchor3.png"),
    4: (2.34,
        "chest and waist drop burst: wide arm expansion freezing open",
        "The camera holds an over-the-shoulder close-up from behind her right "
        "shoulder with only a slight handheld drift: the back of her head and "
        "hair sit along the right edge, her face turned back toward the lens "
        "in near profile in the upper third. On the heavy drum downbeat she "
        "throws both arms wide, chest naturally expanding and freezing open, "
        "back straight, torso tilting slightly then returning, expression "
        "cool. Torso fully inside frame.",
        "handheld over-the-shoulder close-up with slight drift",
        "case03_ots.png"),
    5: (2.34,
        "thigh anchor: side step with a knee bend, no foot sliding",
        "The girl is seen in a pure side profile: one leg steps out sideways, "
        "then the knee bends with weight staying stable and no foot sliding, "
        "then she pushes back up. The camera slowly pulls back to a medium "
        "shot. Her thighs to sneakers stay fully inside the frame.",
        "slow pull-back to medium shot, pure side view",
        "case03_side.png"),
    6: (3.23,
        "calf anchor: alternating steps easing into the closing freeze that "
        "matches the opening stance",
        "The girl stands frontally in a full-body shot, alternating her feet "
        "in gentle steps with arms swinging naturally, the rhythm gradually "
        "easing. By about 2.8 seconds she settles into the final freeze - the "
        "exact same stance as the opening frame: knees slightly bent, both "
        "hands frameworked at her chest - and holds it perfectly motionless "
        "until the end of the shot. Head to sneakers fully inside frame.",
        "fixed tripod, full body, front view",
        None),
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


def build_graph(idx, dur, summary, desc, camera, anchor):
    with open(SNAP, encoding="utf-8") as f:
        g = json.load(f)
    hybrid = anchor is not None
    g["55"]["inputs"]["prompt"] = STYLE
    fmt = dict(dur=dur, summary=summary, desc=desc, camera=camera, idx=idx,
               ident=IDENT, bg=BG_LOCK, audio=AUDIO_LINE)
    g["97"]["inputs"]["prompt"] = (SUBJ_HEAD_HYB if hybrid
                                   else SUBJ_HEAD_REF).format(**fmt)
    g["121"]["inputs"]["image"] = "case03_char_full.png"
    g["122"]["inputs"]["image"] = "case03_char_bust.png"
    if hybrid:
        g["300"] = {"class_type": "LoadImage", "inputs": {"image": anchor}}
    g["27"]["inputs"]["value"] = dur
    g["11"]["inputs"]["noise_seed"] = SEED_BASE + idx
    g["21"]["inputs"]["filename_prefix"] = "CASE-2026-1024-03/shot%d" % idx
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
                "inputs": {"audio": "case03_s%d.wav" % idx}}
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
    status = {"case": "CASE-2026-1024-03", "shots": {}, "started": time.time()}
    only = [int(a) for a in sys.argv[1:]] or sorted(SHOTS)
    for idx in only:
        dur, summary, desc, camera, anchor = SHOTS[idx]
        g = build_graph(idx, dur, summary, desc, camera, anchor)
        entry = {"dur_request": dur, "state": "submitting",
                 "route": ("Hybrid+anchor(%s)" % anchor) if anchor else "Ref2VA"}
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
            dst = os.path.join(ASSETS, "case03_shot%d.mp4" % idx)
            shutil.copy2(src, dst)
            entry["file"] = dst
            print("shot%d done -> %s" % (idx, dst))
        else:
            entry["state"] = "done_no_file"
            print("shot%d done but output file not found in %s" % (idx, OUTDIR))
        json.dump(status, open(STATUS, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("CASE-03 RUNNER FINISHED")


if __name__ == "__main__":
    main()
