"""CASE-2026-1024-03: render composition anchors with local Qwen-Image-Edit-2511.

DG-015 rule: every shot whose storyboard framing is 特写/中景 (close-up/medium)
must get a first_frame anchor. CASE-03 shot plan:

  shot 1 (全身/四分之三侧) -> anchor A: char_3q   (3/4 side full body, bounce
                              opening pose - doubles as the opening frame)
  shot 2 (近景/正面)       -> anchor B: char_bust (frontal bust - numeric crop)
  shot 3 (近景/四分之三侧) -> anchor C: 3q_bust   (numeric crop from char_3q)
  shot 4 (特写/过肩)       -> anchor D: ots       (over-the-shoulder close-up)
  shot 5 (中景/纯侧)       -> anchor E: side      (pure side profile, thighs to boots)
  shot 6 (全身/正面)       -> Ref2VA default (H3 default framing = frontal full body)

Rendered anchors (this script): char_3q, ots, side.
Numeric crops (make_anchor03.py --crop): char_bust from char_full, 3q_bust from char_3q.

Graph = the make_anchor.py Revision B recipe (validated on this machine):
edit-2511 fp8 + Multiple-angles LoRA + 30 steps cfg 3, euler/simple.

Usage:
  python make_anchor03.py            # all three renders
  python make_anchor03.py char_3q    # one render
  python make_anchor03.py --crop     # numeric crops only
"""
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = "F:/MI10-PRO+/MI10-PRO+/MI10-Pro+/ComfyUI/input"
OUT_DIR = "F:/MI10-PRO+/MI10-PRO+/MI10-Pro+/ComfyUI/output/anchor03"
ASSETS = os.path.join(ROOT, "cases", "assets")
CLIENT = "short-dance-choreo"
W, H = 832, 1472
STEPS, CFG = 30, 3.0

IDENT = ("Keep the character exactly the same: same face, same amber eyes, "
         "same short dark-brown messy bob-cut hair, same black choker, same "
         "oversized gray hoodie with the hood down and sleeves rolled up, "
         "same black cargo pants and white high-top sneakers. ")

TAIL = ("Replace the background with a clean solid light-gray studio backdrop. "
        "Keep the 2D cel-shaded anime style with clean lineart and soft studio "
        "lighting. Vertical portrait composition, exactly one person in frame, "
        "no text, no watermark.")

# fixed seeds per anchor (reproducible; hash() is per-process randomized)
SEEDS = {"char_3q": 2026102411, "ots": 2026102412, "side": 2026102413}

# name -> (source image in input/, edit prompt)
EDITS = {
    # shot 1 anchor + opening frame: 3/4 side full body, bounce opening stance
    "char_3q": (
        "case03_char_full.png",
        "将镜头向左旋转45度。"
        "The camera moves to her three-quarter left side in a full-body shot: "
        "she stands with knees slightly bent in a relaxed bounce stance, both "
        "hands frameworked at her chest, weight on one leg, cool expression "
        "looking toward the lens. Her whole body from head to sneakers is "
        "fully inside the frame with safety margins at top and bottom. "
        + IDENT + TAIL
    ),
    # shot 4 anchor: over-the-shoulder close-up
    "ots": (
        "case03_char_full.png",
        "将镜头向右旋转90度，再将镜头向前移动转为特写镜头。"
        "The camera is now behind her right shoulder in a tight over-the-shoulder "
        "close-up: the back of her head and hair sit along the right edge of the "
        "frame, her face turned back toward the lens in near profile, her head "
        "and upper torso fill the frame with her face in the upper third, both "
        "arms relaxed at her sides. Exactly one person in frame - no second head, "
        "no second body at the edges. "
        + IDENT + TAIL
    ),
    # shot 5 anchor: pure side profile, thighs to boots
    "side": (
        "case03_char_full.png",
        "将镜头向左旋转90度，再将镜头向下移动。"
        "The camera is now at her left side in a pure side profile - absolutely "
        "no three-quarter angle, no front view - framing a tight medium shot "
        "cropped at the thighs: her head is out of frame above the top edge, "
        "her upper thighs to sneakers fill the entire vertical frame, weight "
        "shifted onto her left leg with the right knee slightly drawn inward, "
        "hands near her chest. "
        + IDENT + TAIL
    ),
}

NEG = "blurry, low quality, distorted anatomy, extra fingers, mutated hands, " \
      "photorealistic, 3D render, text, watermark, signature, busy background, " \
      "two people, duplicate head, front view, three-quarter view"

def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)


def build_graph(prompt):
    return {
        "1": {"class_type": "UNETLoader",
              "inputs": {"unet_name": "Qwen\\qwen_image_edit_2511_fp8_e4m3fn.safetensors",
                         "weight_dtype": "fp8_e4m3fn"}},
        "2": {"class_type": "CLIPLoader",
              "inputs": {"clip_name": "qwen_2.5_vl_7b_fp8_scaled.safetensors",
                         "type": "qwen_image", "device": "cpu"}},
        "3": {"class_type": "VAELoader",
              "inputs": {"vae_name": "qwen_image_vae.safetensors"}},
        "4": {"class_type": "LoraLoaderModelOnly",
              "inputs": {"model": ["1", 0],
                         "lora_name": "Qwen\\Qwen-Edit-2509-Multiple-angles.safetensors",
                         "strength_model": 1.0}},
        "5": {"class_type": "PathchSageAttentionKJ",
              "inputs": {"model": ["4", 0],
                         "sage_attention": os.environ.get("SAGE_MODE", "auto"),
                         "allow_compile": False}},
        "6": {"class_type": "CFGNorm",
              "inputs": {"model": ["5", 0], "strength": 1.0, "pre_cfg": False}},
        "7": {"class_type": "LoadImage",
              "inputs": {"image": EDITS_SRC}},
        "8": {"class_type": "ImageScale",
              "inputs": {"image": ["7", 0], "width": W, "height": H,
                         "upscale_method": "lanczos", "crop": "center"}},
        "9": {"class_type": "TextEncodeQwenImageEditPlus",
              "inputs": {"clip": ["2", 0], "prompt": prompt, "image1": ["8", 0]}},
        "10": {"class_type": "CLIPTextEncode",
               "inputs": {"clip": ["2", 0], "text": NEG}},
        "11": {"class_type": "VAEEncode",
               "inputs": {"pixels": ["8", 0], "vae": ["3", 0]}},
        "12": {"class_type": "ReferenceLatent",
               "inputs": {"conditioning": ["9", 0], "latent": ["11", 0]}},
        "13": {"class_type": "KSampler",
               "inputs": {"model": ["6", 0], "positive": ["12", 0],
                          "negative": ["10", 0], "latent_image": ["11", 0],
                          "seed": SEEDS[EDITS_NAME],
                          "steps": STEPS, "cfg": CFG,
                          "sampler_name": "euler", "scheduler": "simple",
                          "denoise": 1.0}},
        "14": {"class_type": "VAEDecode",
               "inputs": {"samples": ["13", 0], "vae": ["3", 0]}},
        "15": {"class_type": "SaveImage",
               "inputs": {"images": ["14", 0],
                          "filename_prefix": "anchor03/%s" % EDITS_NAME}},
    }


EDITS_SRC = None
EDITS_NAME = None


def wait_done(pid, timeout_s=3600):
    t0 = time.time()
    while time.time() - t0 < timeout_s:
        try:
            h = get("/history/%s" % pid)
        except Exception:
            time.sleep(10)
            continue
        if pid in h:
            st = h[pid].get("status", {})
            if st.get("completed"):
                msgs = st.get("messages", [])
                errs = [m for m in msgs if isinstance(m, (list, tuple))
                        and m and m[0] == "execution_error"]
                return ("error", errs) if errs else ("done", None)
        time.sleep(10)
    return ("timeout", None)


def run_render(name):
    global EDITS_SRC, EDITS_NAME
    src, prompt = EDITS[name]
    EDITS_SRC, EDITS_NAME = src, name
    g = build_graph(prompt)
    r = post("/prompt", {"prompt": g, "client_id": CLIENT})
    pid = r.get("prompt_id")
    print("%s submitted pid=%s" % (name, pid))
    state, errs = wait_done(pid)
    print("%s %s" % (name, state))
    if state != "done":
        print("errors:", str(errs)[:800])
        return False
    out = None
    if os.path.isdir(OUT_DIR):
        cands = [os.path.join(OUT_DIR, n) for n in os.listdir(OUT_DIR)
                 if n.startswith(name + "_") and n.endswith(".png")]
        if cands:
            out = max(cands, key=os.path.getmtime)
    if not out:
        print("%s done but no output file found" % name)
        return False
    dst = os.path.join(ASSETS, name + ".png")
    shutil.copy2(out, dst)
    print("%s -> %s" % (name, dst))
    return True


def subject_bbox(path):
    """Numeric subject bbox via background-color mask (solid bg assumed)."""
    raw = os.path.join(ASSETS, "_tmp.raw")
    ff = "C:/Users/Admin/.workbuddy/binaries/python/envs/default/Lib/site-packages/static_ffmpeg/bin/win32/ffmpeg.exe"
    subprocess.run([ff, "-v", "error", "-i", path, "-f", "rawvideo",
                    "-pix_fmt", "rgb24", "-y", raw], check=True)
    import numpy as np
    a = np.fromfile(raw, dtype=np.uint8)
    # probe dimensions via ffprobe-like: we know 832x1472 for these assets
    a = a.reshape(H, W, 3).astype(int)
    os.remove(raw)
    bg = np.median(a[:20, :20].reshape(-1, 3), axis=0)
    mask = np.abs(a - bg).sum(axis=2) > 60
    ys = np.where(mask.sum(axis=1) > 3)[0]
    xs = np.where(mask.sum(axis=0) > 3)[0]
    return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())


def run_crop():
    """Crop head+shoulders bust anchors from the source renders."""
    py = "C:/Users/Admin/.workbuddy/binaries/python/envs/default/Scripts/python.exe"
    for src_name, out_name in [("case03_char_full.png", "case03_char_bust.png"),
                               ("case03_char_3q.png", "case03_anchor3.png")]:
        src = os.path.join(ASSETS, src_name)
        if not os.path.exists(src):
            print("crop src missing: %s" % src)
            continue
        x0, y0, x1, y1 = subject_bbox(src)
        head_h = y1 - y0
        # bust crop: from slightly above the head top down to ~55% of body height
        top = max(0, y0 - int(0.06 * head_h))
        bot = min(H, y0 + int(0.55 * head_h))
        # horizontal: center on subject, width = 60% of canvas
        cx = (x0 + x1) // 2
        cw = int(W * 0.62)
        left = max(0, min(W - cw, cx - cw // 2))
        dst = os.path.join(ASSETS, out_name)
        ff = "C:/Users/Admin/.workbuddy/binaries/python/envs/default/Lib/site-packages/static_ffmpeg/bin/win32/ffmpeg.exe"
        subprocess.run([ff, "-v", "error", "-i", src, "-vf",
                        "crop=%d:%d:%d:%d,scale=%d:%d:flags=lanczos" % (
                            cw, bot - top, left, top, W, H),
                        "-y", dst], check=True)
        print("crop %s: bbox=(%d,%d)-(%d,%d) -> %s" % (src_name, x0, y0, x1, y1, dst))
    return True


if __name__ == "__main__":
    args = sys.argv[1:]
    ok = True
    if "--crop" in args:
        ok = run_crop()
    else:
        names = [a for a in args if a in EDITS] or list(EDITS)
        for n in names:
            ok = run_render(n) and ok
        ok = run_crop() and ok
    print("ANCHOR03 RUN FINISHED", "OK" if ok else "WITH FAILURES")
