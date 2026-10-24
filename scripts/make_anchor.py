"""CASE-2026-1024-01 v2: render first_frame composition anchors with local Qwen-Image-Edit-2511.

DG-015 fix verification: H3 ignored textual push-in / pull-back instructions in pure
Ref2VA mode (shots 4+5 framing wrong in v1). v2 feeds an explicit first_frame anchor
(composition lock at frame 0) via the Hybrid route, so the canvas景别 is pinned.

Anchors are rendered from the same Fioni full-body reference used as H3 ref image,
so identity stays consistent. Output: 832x1472 (exact H3 canvas, no stretch).

Revision B (this version): pass 1 with the 4-step Lightning LoRA at cfg=1 was too
weak for a viewpoint change - shot 4 anchor came out as a full-body back view with
a spurious second head at the edge, shot 5 anchor as a full-body profile instead
of the thighs-to-boots crop. Revision B switches to the base edit model + the
Multiple-angles LoRA with the author's short camera instructions, 30 steps cfg 3.

Usage:
  python make_anchor.py 4        # shot-4 over-the-shoulder close-up anchor
  python make_anchor.py 5        # shot-5 pure side-profile thighs-to-boots anchor
  python make_anchor.py          # both, sequentially
"""
import json
import os
import shutil
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_DIR = "F:/MI10-PRO+/MI10-PRO+/MI10-Pro+/ComfyUI/input"
OUT_DIR = "F:/MI10-PRO+/MI10-PRO+/MI10-Pro+/ComfyUI/output/anchor"
CLIENT = "short-dance-choreo"
W, H = 832, 1472  # exact H3 canvas for this case (9:16, 0.5MP, mult 32)
STEPS, CFG = 30, 3.0

IDENT = ("Keep the character exactly the same: same face, same large golden-amber "
         "eyes, same long blonde hair in low twin-tails tied with black ribbon "
         "bows, same white leotard-style mini dress with gold ankh emblem at the "
         "chest, same black off-shoulder sleeves with white cuffs, same long "
         "white waist sash, same white thigh-high stockings with garter straps "
         "and white lace-up boots with small wing accents. ")

TAIL = ("Replace the background with a clean solid pale-pink studio backdrop. "
        "Keep the 2D cel-shaded anime style with clean lineart and soft studio "
        "lighting. Vertical portrait composition, exactly one person in frame, "
        "no text, no watermark.")

# Edit prompts: short camera instruction (Multiple-angles LoRA trained phrasing)
# + composition lock + identity lock + background lock.
EDITS = {
    4: (
        "将镜头向右旋转90度，再将镜头向前移动转为特写镜头。"
        "The camera is now behind her right shoulder in a tight over-the-shoulder "
        "close-up: the back of her head and hair sit along the right edge of the "
        "frame, her face turned back toward the lens in near profile, her head "
        "and upper torso fill the frame with her face in the upper third, both "
        "arms relaxed at her sides. Exactly one person in frame - no second head, "
        "no second body at the edges. "
        + IDENT + TAIL
    ),
    5: (
        "将镜头向左旋转90度，再将镜头向下移动。"
        "The camera is now at her left side in a pure side profile - absolutely "
        "no three-quarter angle, no front view - framing a tight medium shot "
        "cropped at the thighs: her head is out of frame above the top edge, her "
        "upper thighs to boots fill the entire vertical frame, weight shifted "
        "onto her left leg with the right knee slightly drawn inward, hands near "
        "her chest. "
        + IDENT + TAIL
    ),
}

NEG = "blurry, low quality, distorted anatomy, extra fingers, mutated hands, " \
      "photorealistic, 3D render, text, watermark, signature, busy background, " \
      "two people, duplicate head"


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)


def build_graph(idx, prompt):
    g = {
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
              "inputs": {"model": ["4", 0], "sage_attention": "auto",
                         "allow_compile": False}},
        "6": {"class_type": "CFGNorm",
              "inputs": {"model": ["5", 0], "strength": 1.0, "pre_cfg": False}},
        "7": {"class_type": "LoadImage", "inputs": {"image": "fioni_full.png"}},
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
                          "seed": 2026102400 + idx, "steps": STEPS, "cfg": CFG,
                          "sampler_name": "euler", "scheduler": "simple",
                          "denoise": 1.0}},
        "14": {"class_type": "VAEDecode",
               "inputs": {"samples": ["13", 0], "vae": ["3", 0]}},
        "15": {"class_type": "SaveImage",
               "inputs": {"images": ["14", 0],
                          "filename_prefix": "anchor/case01_anchor%d" % idx}},
    }
    return g


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


def run(idx):
    prompt = EDITS[idx]
    g = build_graph(idx, prompt)
    r = post("/prompt", {"prompt": g, "client_id": CLIENT})
    pid = r.get("prompt_id")
    print("anchor%d submitted pid=%s" % (idx, pid))
    state, errs = wait_done(pid)
    print("anchor%d %s" % (idx, state))
    if state != "done":
        print("errors:", str(errs)[:800])
        return False
    src = None
    if os.path.isdir(OUT_DIR):
        cands = [os.path.join(OUT_DIR, n) for n in os.listdir(OUT_DIR)
                 if n.startswith("case01_anchor%d_" % idx) and n.endswith(".png")]
        if cands:
            src = max(cands, key=os.path.getmtime)
    if not src:
        print("anchor%d done but no output file found" % idx)
        return False
    dst = os.path.join(INPUT_DIR, "case01_anchor%d.png" % idx)
    shutil.copy2(src, dst)
    print("anchor%d -> %s" % (idx, dst))
    return True


if __name__ == "__main__":
    args = [int(a) for a in sys.argv[1:]] or [4, 5]
    ok = True
    for idx in args:
        ok = run(idx) and ok
    print("ANCHOR RUN FINISHED", "OK" if ok else "WITH FAILURES")
