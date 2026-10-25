"""单次直出模式 runner（SKILL.md v2.0 Phase 2.6 模式 B）

与逐镜 runner（run_case01/03/1025.py）的关键差异：
- **不切镜**：一条提示词一次生成完整时长，无分镜、无装配 trim
- **不钉帧 0**：task_type 保持 Ref2VA（identity 槽位），不设 first_frame
  （DG-019：first_frame 会在 ~1.5s 处把景别硬跳回默认全身，直出无分镜兜底即整条报废）
- **提示词内部写死时间锚点**：from X.Xs to Y.Ys / at Z.Zs the drop

Usage:
    python run_oneshot.py                       # 用内置 CASE-2026-1025-02 参数
    python run_oneshot.py --audio x.wav --image y.png --tag CASE-xx/oneshot
    python run_oneshot.py --prompt-file p.txt   # 覆盖内置提示词
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import argparse
import json
import os
import shutil
import sys
import time
import urllib.error
import urllib.request


BASE = _env.get_api()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SNAP = os.path.join(ROOT, "scripts", "h3_snapshot.json")
ASSETS = os.path.join(ROOT, "cases", "assets")
CLIENT = "short-dance-choreo"

# ---- 默认值：CASE-2026-1025-02（777.mp3 15s 窗 + 单张角色图）----
DEF_AUDIO = "qw21_oneshot.wav"
DEF_IMAGE = "qw21_single.png"
DEF_TAG = "CASE-2026-1025-02/oneshot"
DEF_DUR = 15.0
DEF_SEED = 2026102502

STYLE = ("Crisp clean 2D Japanese cel-shaded anime style, clean lineart, soft "
         "even front fill light, stable frames, no photorealism.")

IDENT = ("a dark-stage K-pop idol girl: silver-white short hair with two low "
         "side buns tied by deep-blue bow ornaments, golden-yellow eyes, a "
         "black sleeveless short dress, deep-blue arm guards with black long "
         "gloves, a gold crescent choker with a four-leaf-clover center and a "
         "gold chest pendant, a black thigh ring on her right leg, black "
         "open-toe high-heel short boots")

BG_LOCK = ("the backdrop stays the deep navy-black stage background with its "
           "white smoke wisps and blue-and-gold paint splashes, held "
           "completely still: unchanged, never repainted, no new background "
           "elements")

AUDIO_LINE = ("<Audio 1> is the background music track: a 124.5 BPM "
              "four-on-the-floor electronic dance beat with a dense kick "
              "pattern and a full low end, with one big drop at 6.9 seconds. "
              "It is directly reused as the target video's complete final "
              "audio track.")

# 时间锚点取自 R1 实测：窗 = 777.mp3 5.341–20.341s，全曲实测 drop=12.23s
# → 窗内 drop = 12.23 - 5.341 = 6.889s（落窗内 45.9%，符合「drop 落 40–55%」）
PROMPT = """subject_definitions:
@image#1 is the character reference of the girl: {ident}. All proportions and details define her canonical design.
@image#2 is the same girl from the same character reference, defining her face, eye color and dynamic dance pose precisely.
{audio}

summary:
[reference generation] One single continuous unbroken 15-second dance shot of the girl defined by @image#1 and @image#2, performing a dark-concept K-pop dance on a navy-black stage. The entire video is one take from start to finish: no cuts, no scene changes, no reframing between locations.

detailed_description:
2D Japanese cel-shaded anime style, clean lineart, soft even front fill light, 9:16 vertical framing.
The beat is 124.5 BPM, one beat every 0.48 seconds, and every accent lands exactly on a beat.
The video is one continuous take divided into four musical phrases with hard time anchors:
- from 0.0s to 2.25s: opening hook. She begins in the dynamic one-leg-up pose from the reference, then slowly raises both arms from her sides up to chest height, forming one strong continuous arm line. Her gaze is locked on the lens.
- from 2.25s to 6.89s: build-up. Her shoulders bounce on every beat, her arms swing side to side in a relaxed groove, and her weight shifts left and right. The motion stays medium speed and continuous.
- at 6.89s the drop hits: on that exact beat she snaps her ribcage open, sweeps both arms wide out to her sides, and plants the raised foot down into a wide grounded stance. This is the single biggest accent of the whole video.
- from 6.89s to 11.25s: she keeps the drop energy, swaying her waist left and right, then crossing her arms over her chest and opening them wide again.
- from 11.25s to 15.0s: she decelerates, brings both arms back down to her sides, returns to a calm frontal stance, and holds a completely still pose for the final beat.

visual_rules:
- ONE continuous unbroken take for the whole 15 seconds: no cuts, no scene changes, no teleporting, no new characters
- locked character identity to @image#1 and @image#2 for the entire 15 seconds: the same silver-white hair, golden-yellow eyes, black dress, gold choker, arm guards and boots in every single frame
- camera: {camera}
- {bg}
- 9:16 vertical framing maintained for the whole shot
- stable hands with correct finger count; no text, no watermark
- the stage backdrop is completely static: the smoke wisps and paint splashes do not move, grow or change
全程外观零漂移。背景全程保持首帧中的深蓝黑舞台背景，完全不变、不重绘。最后一拍起完全静止定格。"""


UPSCALER_FP32 = "h3_upscaler_sharpness_2000steps_v0.1_fp32.safetensors"
UPSCALER_FP16 = "minimax_h3_latent_upscaler_3d_fp16.safetensors"


def build_graph(dur, audio, image, tag, seed, prompt_text, camera,
                no_upscale=True, mp=None, attn=None, upscaler=None):
    with open(SNAP, encoding="utf-8") as f:
        g = json.load(f)
    g["55"]["inputs"]["prompt"] = STYLE
    g["97"]["inputs"]["prompt"] = prompt_text

    if mp is not None:
        g["29"]["inputs"]["megapixels"] = mp

    # 显存杠杆①：attention 后端。视频的长序列 attention 是显存大头，
    # comfy kitchen attention 为 INT8 量化实现（仅 Nvidia/AMD）
    if attn:
        g["33"]["inputs"]["attention"] = attn

    # 显存杠杆②：latent upscaler 权重精度。默认 fp32，换 fp16 直接省一半权重显存
    if upscaler:
        g["13"]["inputs"]["model_name"] = upscaler

    if no_upscale:
        # 快照里主输出链是 7→12→13(1.5x latent upscale)→19(第二遍采样)→20→21，
        # 184→185 只是「第一段预览」。15s/362 帧走 upscale 后的第二遍采样会 OOM
        # （latent 面积 ×2.25，实测 10.53GiB 已占用下再要 5.45GiB 直接爆）。
        # 直出模式改接第一遍输出：21 ← 184。副作用是 13→19→20 整条链无下游消费者，
        # ComfyUI 不再执行，省下 upscale 与第二遍采样的显存。
        g["21"]["inputs"]["images"] = ["184", 0]
        g["21"]["inputs"]["audio"] = ["184", 1]

    # identity 槽位（Ref2VA）：两张都喂同一张源图（本例只有 1 张角色图，见
    # references/character-sheet.md §8 退化路径：仅 1 张图 → 优先单次直出）
    g["121"]["inputs"]["image"] = image
    g["122"]["inputs"]["image"] = image
    g["27"]["inputs"]["value"] = dur
    g["11"]["inputs"]["noise_seed"] = seed
    g["21"]["inputs"]["filename_prefix"] = tag
    for pass_node in ("7", "14"):
        n = g[pass_node]["inputs"]
        n["audio_mode"] = "lock_source"
        n["add_source_as_reference"] = True
        n["drive_audio"] = ["200", 0]
        n["final_audio"] = ["200", 0]
        # 保持 Ref2VA（不设 task_type=Hybrid / 不设 first_frame）
        n.pop("first_frame", None)
        n["task_type"] = "Ref2VA"
    g["200"] = {"class_type": "LoadAudio", "inputs": {"audio": audio}}
    return g


def ensure_comfy_file(arg):
    """参数是本机路径就同步到 ComfyUI input 并返回文件名；已是文件名则原样返回。

    ComfyUI 的 LoadImage / LoadAudio 只认 input 目录下的文件名，
    直接传本地路径会报 400（Invalid audio file / image not found）。
    """
    if not arg:
        return arg
    if os.path.exists(arg):
        cin = _env.get_comfy_input(required=True)
        name = os.path.basename(arg)
        dst = os.path.join(cin, name)
        try:
            if os.path.abspath(arg) != os.path.abspath(dst):
                shutil.copy2(arg, dst)
                print("  同步 %s → ComfyUI input" % name)
        except Exception as e:
            print("[警告] 同步到 ComfyUI input 失败：%s" % e)
        return name
    return arg


def post(path, payload):
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(BASE + path, data=data,
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode("utf-8"))
    except urllib.error.HTTPError as e:
        # 400 的响应体里才有真正的校验失败原因，必须读出来
        body = e.read().decode("utf-8", "replace")
        print("HTTP %s %s" % (e.code, e.reason))
        try:
            j = json.loads(body)
            print("error:", j.get("error"))
            print("node_errors:", json.dumps(
                j.get("node_errors"), ensure_ascii=False)[:2000])
        except Exception:
            print("body:", body[:2000])
        raise


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=60) as r:
        return json.loads(r.read().decode("utf-8"))


def wait_done(pid, timeout_s=3600):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            h = get("/history/%s" % pid)
        except Exception:
            time.sleep(15)
            continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("completed", False) or st.get("status_str") == "success":
                return True, h[pid]
            if st.get("status_str") == "error":
                return False, h[pid]
        time.sleep(15)
    return False, {"timeout": True}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--audio", default=DEF_AUDIO, help="ComfyUI input 下的音频文件名")
    ap.add_argument("--image", default=DEF_IMAGE, help="ComfyUI input 下的角色图文件名")
    ap.add_argument("--tag", default=DEF_TAG, help="输出目录前缀")
    ap.add_argument("--dur", type=float, default=DEF_DUR)
    ap.add_argument("--seed", type=int, default=DEF_SEED)
    ap.add_argument("--prompt-file", default="", help="覆盖内置提示词的文本文件")
    ap.add_argument("--camera", default=(
        "locked-off tripod for the whole take, full-body medium shot, front "
        "view, horizontal eye level; from 6.89s to 11.25s one extremely slow "
        "push-in, then locked again"))
    ap.add_argument("--with-upscale", action="store_true",
                    help="保留 1.5x latent upscale 的第二遍采样（默认关闭：长时序会 OOM）")
    ap.add_argument("--mp", type=float, default=None,
                    help="覆盖 ResolutionSelector 的 megapixels（降分辨率可换显存）")
    ap.add_argument("--attn", default="",
                    help="attention 后端：comfy kitchen attention（INT8 量化，省显存）")
    ap.add_argument("--upscaler", default="",
                    help="latent upscaler 权重：默认 fp32，可换 %s" % UPSCALER_FP16)
    ap.add_argument("--upscale-by", type=float, default=None, help="upscale 倍率")
    args = ap.parse_args()

    if args.prompt_file:
        with open(args.prompt_file, encoding="utf-8") as f:
            prompt_text = f.read()
    else:
        prompt_text = PROMPT.format(ident=IDENT, audio=AUDIO_LINE,
                                    bg=BG_LOCK, camera=args.camera)

    # 17n+5 网格量化提示
    frames = max(5, round(args.dur * 24))
    grid = frames + (5 - (frames % 17)) % 17
    print("请求 %.3fs → 网格 %d 帧 = %.3fs（DG-018 网格）"
          % (args.dur, grid, grid / 24.0))

    audio = ensure_comfy_file(args.audio)
    image = ensure_comfy_file(args.image)
    g = build_graph(args.dur, audio, image, args.tag,
                    args.seed, prompt_text, args.camera,
                    no_upscale=not args.with_upscale, mp=args.mp,
                    attn=args.attn or None, upscaler=args.upscaler or None)
    if args.upscale_by:
        g["13"]["inputs"]["scale_by"] = args.upscale_by
    payload = {"prompt": g, "client_id": CLIENT}
    r = post("/prompt", payload)
    pid = r.get("prompt_id")
    print("submitted prompt_id = %s" % pid)
    status = {"case": args.tag, "mode": "单次直出(Ref2VA)", "dur_request": args.dur,
              "grid_frames": grid, "audio": audio, "image": image,
              "seed": args.seed, "prompt_id": pid, "state": "running",
              "started": time.time()}
    sp = os.path.join(ASSETS, "run_status_oneshot.json")
    json.dump(status, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)

    ok, hist = wait_done(pid)
    status["finished"] = time.time()
    status["elapsed_s"] = round(status["finished"] - status["started"], 1)
    if not ok:
        status["state"] = "failed"
        status["error"] = str(hist)[:800]
        json.dump(status, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
        print("FAILED:", status["error"])
        sys.exit(1)

    outdir = os.path.join(_env.get_comfy_output(required=True),
                          args.tag.split("/")[0])
    pat = os.path.basename(args.tag)
    # H3 这条链路会出两个文件：
    #   <prefix>_00001.mp4        纯视频，无音轨
    #   <prefix>_00001-audio.mp4  视频 + 音轨  ← 要的是这个
    # 按前缀直接匹配会先命中无后缀那个，导致拿到的成片没有声音。
    hits = {"with_audio": [], "silent": []}
    for root, _dirs, files in os.walk(outdir):
        for name in files:
            if not (name.startswith(pat) and name.endswith(".mp4")):
                continue
            p = os.path.join(root, name)
            (hits["with_audio"] if name.endswith("-audio.mp4")
             else hits["silent"]).append(p)
    src = (max(hits["with_audio"], key=os.path.getmtime)
           if hits["with_audio"]
           else (max(hits["silent"], key=os.path.getmtime) if hits["silent"] else None))
    if src and not src.endswith("-audio.mp4"):
        print("[提示] 未找到 -audio.mp4，取的是无音轨版本：%s"
              % os.path.basename(src))
    if src:
        dst = os.path.join(ASSETS, "case1025_oneshot%s.mp4"
                           % ("" if pat == "oneshot" else "_" + pat))
        shutil.copy2(src, dst)
        status["file"] = dst
        print("done -> %s" % dst)
    else:
        status["state"] = "done_no_file"
        print("done but output not found in %s" % outdir)
    status["state"] = "done"
    json.dump(status, open(sp, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("ONESHOT RUNNER FINISHED")


if __name__ == "__main__":
    main()
