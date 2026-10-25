"""CASE-2026-1025-01 headless runner: 6 shots on local ComfyUI MiniMax H3.

15s 抖音 · K-pop 暗黑系 · 124.5 BPM 拍吸附（bar 1.928s < 2.0s 下限 → 按拍切分）。
窗口 = 777.mp3 7.737–22.657s（14.920s），实测 drop=12.555s 落在成片 32.1%。
分镜切点（成片内相对）：0.000 / 2.403 / 4.818 / 7.233 / 9.637 / 12.511 / 14.920。

接线策略（DG-015 降权规则 + CASE-01/02/03 实证）：
- 6 镜全部 Hybrid + first_frame（本例无 Ref2VA 镜：四视图里没有可直接当默认构图的
  全身正面源，逐镜锚点全部由 split_qw21.py 数值裁切产出，构图已知可控）
- 每镜锚点：a1_full / a2_eye / a4_chest / a3_mouth / a5_thigh / a6_calf（832×1472 9:16）
- identity 槽：#2 = qw21_front.png（全身）、#3 = qw21_bust.png（面部）
- 每镜音频切片独立 lock_source
- 镜 6 提示词明示「最后一拍起完全静止」（DG-018 对策：73 帧 = 3.042s，
  定格必须落在 trim 点 2.409s 之前）

受控项：seed 基 2026102500+idx、音频 lock_source 接线、风格/负面栈、战斗 LoRA 清零，
均与 CASE-01/02/03 一致。

Usage: python run_case04.py [shot ...]   # default: all six, sequential
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
OUTDIR = os.path.join(_env.get_comfy_output() or ".", "CASE-2026-1025-01")
STATUS_PATH = os.path.join(ASSETS, "run_status_case1025.json")
CLIENT = "short-dance-choreo"
SEED_BASE = 2026102500  # 501..506，避开 201-206 / 251-252 / 261-266

STYLE = ("Crisp clean 2D Japanese cel-shaded anime style, clean lineart, soft "
         "even front fill light, stable frames, no photorealism.")

IDENT = ("a dark-stage K-pop idol girl: silver-white short hair with two low "
         "side buns tied by deep-blue bow ornaments, golden-yellow eyes, a "
         "black sleeveless short dress, deep-blue arm guards with black long "
         "gloves, a gold crescent choker with a four-leaf-clover center and a "
         "gold chest pendant, a black thigh ring on her right leg, black "
         "open-toe high-heel short boots")

BG_LOCK = ("the backdrop stays the clean solid light-gray studio background, "
           "unchanged, never repainted")

AUDIO_LINE = ("<Audio 1> is the background music track of this shot: a 124.5 "
              "BPM four-on-the-floor electronic dance beat with a dense kick "
              "pattern and a full low end. It is directly reused as the "
              "target video's complete final audio track.")

SUBJ_HEAD = """subject_definitions:
@image#2 is the full-body character reference of the girl: {ident}. All proportions and details define her canonical design.
@image#3 is the close-up portrait reference of the same girl, defining her face, eye color and facial details precisely.
@image#1 is the exact opening-frame anchor of this shot: it locks the camera framing, her pose at frame 0 and the clean solid light-gray studio backdrop. Begin the shot from this composition and keep every design detail and the backdrop unchanged.
{audio}

summary:
[reference generation] One continuous {dur}s dance shot of the girl defined by @image#2 and @image#3, performing a dark-concept K-pop dance in a pure-color photo studio, starting exactly from the @image#1 opening-frame composition. {summary}

detailed_description:
2D Japanese cel-shaded anime style, clean lineart, soft even front fill light, 9:16 vertical framing, clean solid light-gray backdrop.
[Shot {idx}] {desc}
The beat is 124.5 BPM, one beat every 0.48 seconds, and every accent lands exactly on a beat.

visual_rules:
- locked character identity to @image#2 and @image#3 throughout the shot
- the opening composition of @image#1 is the exact frame 0 of this shot; do not reframe away from it
- camera: {camera}
- {bg}
- 9:16 vertical framing maintained for the whole shot
- stable hands with correct finger count; no text, no watermark{lock}
所有镜头中外观零漂移。背景全程保持首帧中的纯灰色背景，完全不变、不重绘。"""

# shot: (dur, summary, desc, camera, anchor image)
SHOTS = {
    1: (2.403,
        "opening hook: arms lifting into a strong arm line then a right-hand "
        "point frozen at the lens",
        "The girl stands frontally in a full-body medium shot. She slowly "
        "lifts both arms from her sides up to chest height, forming one "
        "strong continuous arm line. Then she shifts her weight to her right "
        "with a light shoulder bounce on the beat, and on the last beat her "
        "right hand points straight out at the lens and holds that point "
        "perfectly still until the end of the shot. Her whole body from head "
        "to boots stays fully inside the frame with safety margins at top and "
        "bottom.",
        "locked-off tripod, full-body medium shot, front view, horizontal eye "
        "level",
        "qw21_a1_full.png"),
    2: (2.415,
        "eye anchor: the gaze turning from off-frame to the lens as the "
        "camera pushes in",
        "Framed in a three-quarter view close-up of her face, the camera "
        "slowly pushes in toward her eyes. Her gaze turns slowly from the "
        "off-frame side and locks onto the lens. Her right hand lifts with "
        "the back of the hand resting near her jawline and it never covers "
        "her face; her eyes follow her own hand for half a beat and then "
        "return to the lens. Her face stays in the upper third of the frame "
        "and the golden-yellow eye color stays identical.",
        "slow push-in, close-up on the eyes, three-quarter side view",
        "qw21_a2_eye.png"),
    3: (2.415,
        "chest-and-waist drop burst: the ribcage snapping open on the "
        "downbeat then arms sweeping wide",
        "Front view medium close-up on her chest and waist. On the very first "
        "heavy drum downbeat her ribcage snaps open and both shoulders pull "
        "back in one sharp hit. Then her waist sways left and right in a "
        "clean controlled isolation. Finally she wraps her arms across her "
        "chest and opens them wide to both sides. Her torso stays upright "
        "with no twisting and no clipping; the gold crescent choker with its "
        "four-leaf-clover center and the gold chest pendant keep a stable "
        "shape; her arms never cross above the shoulder line.",
        "locked-off tripod, medium close-up on chest and waist, front view, "
        "horizontal eye level",
        "qw21_a4_chest.png"),
    4: (2.404,
        "mouth anchor: lips parting on the beat in pure profile",
        "Pure side profile close-up of the lower half of her face. Her head "
        "tilts slightly and her chin lifts a little; her lips part and close "
        "on the beat, lightly biting her lower lip then opening slightly. "
        "Then her fingertips touch the corner of her lips and slide downward "
        "away from her mouth. Her lips stay clearly visible with a clean "
        "defined outline for the entire shot; her hand never covers the mouth "
        "for more than an instant; her facial geometry stays undistorted.",
        "locked-off tripod, close-up on the mouth, pure side view",
        "qw21_a3_mouth.png"),
    5: (2.874,
        "thigh anchor: a side-front step with a skirt swing and a knee bounce",
        "Three-quarter side view close-up on her thighs. She sinks her weight "
        "and steps her right leg out to the side-front, then extends and "
        "draws the leg back with the skirt swinging naturally, and on the "
        "last two beats her knees bounce lightly in place. Both legs stay "
        "visible with the correct count of two; the black thigh ring stays on "
        "her right leg; no foot slides out of frame.",
        "slow lateral tracking move, close-up on the thighs, three-quarter "
        "side view",
        "qw21_a5_thigh.png"),
    6: (2.409,
        "calf anchor: two heel taps easing into a complete closing freeze "
        "that matches the opening stance",
        "Front view close-up on her lower legs and feet. She lifts her heels "
        "for two tapping steps, then brings both feet together with a slight "
        "ankle turn. From about 2.4 seconds onward she stands completely "
        "motionless, frozen in a frontal stance with both arms hanging "
        "naturally at her sides, and holds that stillness until the end of "
        "the shot. Her feet never slide out of frame and their total travel "
        "stays within one foot width.",
        "locked-off tripod, close-up on the lower legs and feet, front view",
        "qw21_a6_calf.png"),
}

COMBAT_LORAS = ("159", "162", "166", "169")  # H3_Combat_V2 / GunFu -> zeroed

# ---------------- v2：DG-019 对策 ----------------
# 对策① 锚点加上下文（见 split_qw21.py --v2）
V2_ANCHOR = {2: "qw21_a2_eye_v2.png",
             3: "qw21_a4_chest_v2.png",
             6: "qw21_a6_calf_v2.png"}
# 对策② 构图锁定句（追加进 visual_rules）
FRAMING_LOCK = ("- the framing, scale and camera distance of @image#1 are held "
                "identical for every single frame of this shot: no zoom, no "
                "pull-back, no reframing, no change of shot size")
# 对策②附 取消机位运动：v2 三镜一律定点机位（缓慢推近/横移本身就会改变构图）
V2_SHOT = {
    2: (2.415,
        "eye anchor: the gaze turning from off-frame to the lens, framing held "
        "frozen",
        "Framed in a three-quarter view upper-body close-up, she fills the "
        "frame from the top of her head to her chest and the camera holds "
        "absolutely still. Her gaze turns slowly from the off-frame side and "
        "locks onto the lens. Her right hand lifts with the back of the hand "
        "resting near her jawline and it never covers her face; her eyes "
        "follow her own hand for half a beat and then return to the lens. Her "
        "face stays in the upper third of the frame and the golden-yellow eye "
        "color stays identical.",
        "locked-off tripod, upper-body close-up, three-quarter side view",
        "qw21_a2_eye_v2.png"),
    3: (2.415,
        "chest-and-waist drop burst: the ribcage snapping open on the "
        "downbeat then arms sweeping wide, framing held frozen",
        "Front view upper-body medium shot: her head is fully visible at the "
        "top of the frame and her chest and waist occupy the center. The "
        "camera holds absolutely still. On the very first heavy drum downbeat "
        "her ribcage snaps open and both shoulders pull back in one sharp "
        "hit. Then her waist sways left and right in a clean controlled "
        "isolation. Finally she wraps her arms across her chest and opens "
        "them wide to both sides. Her head, silver-white hair, gold crescent "
        "choker with its four-leaf-clover center and the gold chest pendant "
        "stay visible and undistorted for the entire shot; her torso stays "
        "upright with no twisting and no clipping; her arms never cross above "
        "the shoulder line.",
        "locked-off tripod, upper-body medium shot, front view, horizontal "
        "eye level",
        "qw21_a4_chest_v2.png"),
    6: (2.409,
        "calf anchor: two heel taps easing into a complete closing freeze "
        "that matches the opening stance, framing held frozen",
        "Front view lower-body medium shot from her skirt hem down to her "
        "feet, and the camera holds absolutely still. She lifts her heels for "
        "two tapping steps, then brings both feet together with a slight "
        "ankle turn. From about 2.4 seconds onward she stands completely "
        "motionless, frozen in a frontal stance with both arms hanging "
        "naturally at her sides, and holds that stillness until the end of "
        "the shot. Her feet and the black open-toe high-heel short boots stay "
        "fully visible and never slide out of frame; their total travel stays "
        "within one foot width.",
        "locked-off tripod, lower-body medium shot, front view",
        "qw21_a6_calf_v2.png"),
}


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)


def build_graph(idx, dur, summary, desc, camera, anchor, v2=False):
    with open(SNAP, encoding="utf-8") as f:
        g = json.load(f)
    g["55"]["inputs"]["prompt"] = STYLE
    lock = ("\n" + FRAMING_LOCK) if v2 else ""
    fmt = dict(dur=dur, summary=summary, desc=desc, camera=camera, idx=idx,
               ident=IDENT, bg=BG_LOCK, audio=AUDIO_LINE, lock=lock)
    g["97"]["inputs"]["prompt"] = SUBJ_HEAD.format(**fmt)
    g["121"]["inputs"]["image"] = "qw21_front.png"
    g["122"]["inputs"]["image"] = "qw21_bust.png"
    g["300"] = {"class_type": "LoadImage", "inputs": {"image": anchor}}
    g["27"]["inputs"]["value"] = dur
    g["11"]["inputs"]["noise_seed"] = SEED_BASE + idx + (100 if v2 else 0)
    g["21"]["inputs"]["filename_prefix"] = (
        "CASE-2026-1025-01/shot%d_v2" % idx if v2
        else "CASE-2026-1025-01/shot%d" % idx)
    for pass_node in ("7", "14"):
        n = g[pass_node]["inputs"]
        n["audio_mode"] = "lock_source"
        n["add_source_as_reference"] = True
        n["drive_audio"] = ["200", 0]
        n["final_audio"] = ["200", 0]
        n["task_type"] = "Hybrid"
        n["first_frame"] = ["300", 0]
    g["200"] = {"class_type": "LoadAudio",
                "inputs": {"audio": "qw21_s%d.wav" % idx}}
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
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    v2 = "--v2" in sys.argv
    shots = V2_SHOT if v2 else SHOTS
    global STATUS_PATH
    STATUS_PATH = os.path.join(ASSETS, "run_status_case1025%s.json"
                               % ("_v2" if v2 else ""))
    status = {"case": "CASE-2026-1025-01" + ("-v2" if v2 else ""),
              "shots": {}, "started": time.time()}
    only = [int(a) for a in args] or sorted(shots)
    for idx in only:
        dur, summary, desc, camera, anchor = shots[idx]
        g = build_graph(idx, dur, summary, desc, camera, anchor, v2=v2)
        entry = {"dur_request": dur, "state": "submitting", "v2": v2,
                 "route": "Hybrid+anchor(%s)" % anchor}
        status["shots"]["shot%d" % idx] = entry
        json.dump(status, open(STATUS_PATH, "w", encoding="utf-8"),
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
        print("shot%d submitted pid=%s dur=%.3f (%s)" % (idx, pid, dur,
                                                        entry["route"]))
        json.dump(status, open(STATUS_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        state, errs = wait_done(pid, 2700)  # 45 min per shot
        entry["state"] = state
        if state != "done":
            entry["errors"] = str(errs)[:800] if errs else None
            print("shot%d %s" % (idx, state))
            json.dump(status, open(STATUS, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
            break
        pat = "shot%d_v2_0000" % idx if v2 else "shot%d_0000" % idx
        src = None
        for name in sorted(os.listdir(OUTDIR)) if os.path.isdir(OUTDIR) else []:
            if name.startswith(pat) and name.endswith(".mp4"):
                src = os.path.join(OUTDIR, name)
        if src:
            dst = os.path.join(ASSETS, "case1025_shot%d%s.mp4" % (idx, "_v2" if v2 else ""))
            shutil.copy2(src, dst)
            entry["file"] = dst
            print("shot%d done -> %s" % (idx, dst))
        else:
            entry["state"] = "done_no_file"
            print("shot%d done but output file not found in %s" % (idx, OUTDIR))
        json.dump(status, open(STATUS_PATH, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
    print("CASE-1025 RUNNER FINISHED")


if __name__ == "__main__":
    main()
