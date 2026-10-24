"""CASE-2026-1024-03: generate the streetwear character reference (T2I).

CASE-03 uses a different character from CASE-01/02 (streetwear hip-hop girl,
not Fioni). This script renders the base full-body reference with the local
Illustrious-XL checkpoint (standard SDXL node chain - zero custom nodes),
then the Qwen-edit pipeline derives bust / 3-quarter / OTS / side-profile
anchors from it (see make_anchor03.py).

Usage:
  python make_char.py [seed ...]     # default: 2 candidate seeds
"""
import json
import os
import shutil
import sys
import time
import urllib.request

BASE = "http://127.0.0.1:8188"
CLIENT = "short-dance-choreo"
W, H = 832, 1472  # exact H3 canvas for this case (9:16)
CKPT = "IL-illustriousSemi_v30.safetensors"
OUT_DIR = "F:/MI10-PRO+/MI10-PRO+/MI10-Pro+/ComfyUI/output/case03"
INPUT_DIR = "F:/MI10-PRO+/MI10-PRO+/MI10-Pro+/ComfyUI/input"
SEEDS = [2026102401, 2026102402]

POS = ("masterpiece, best quality, amazing quality, very aesthetic, absurdres, "
       "1girl, solo, full body, standing, facing viewer, cool expression, "
       "slight smirk, short dark brown hair, messy bob cut, amber eyes, "
       "black choker, oversized gray hoodie with hood down, sleeves rolled up, "
       "black cargo pants, white high-top sneakers, hands in pockets, "
       "urban streetwear fashion, clean solid light-gray background, "
       "studio lighting, soft shadow, depth of field, head to toe, "
       "entire body visible in frame")

NEG = ("worst quality, low quality, normal quality, lowres, bad anatomy, "
       "blurry, cropped, extra limbs, deformed hands, bad face, sketch, "
       "jpeg artifacts, signature, watermark, username, artist name, text, "
       "multiple views, outline, gradient background, busy background, "
       "two people, duplicate, monochrome, greyscale")


def post(path, payload):
    req = urllib.request.Request(
        BASE + path, data=json.dumps(payload).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.load(r)


def get(path):
    with urllib.request.urlopen(BASE + path, timeout=30) as r:
        return json.load(r)


def build_graph(seed):
    return {
        "1": {"class_type": "CheckpointLoaderSimple",
              "inputs": {"ckpt_name": CKPT}},
        "2": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 1], "text": POS}},
        "3": {"class_type": "CLIPTextEncode",
              "inputs": {"clip": ["1", 1], "text": NEG}},
        "4": {"class_type": "EmptyLatentImage",
              "inputs": {"width": W, "height": H, "batch_size": 1}},
        "5": {"class_type": "KSampler",
              "inputs": {"model": ["1", 0], "positive": ["2", 0],
                         "negative": ["3", 0], "latent_image": ["4", 0],
                         "seed": seed, "steps": 30, "cfg": 6,
                         "sampler_name": "euler_ancestral",
                         "scheduler": "normal", "denoise": 1.0}},
        "6": {"class_type": "VAEDecode",
              "inputs": {"samples": ["5", 0], "vae": ["1", 2]}},
        "7": {"class_type": "SaveImage",
              "inputs": {"images": ["6", 0],
                         "filename_prefix": "case03/char_%d" % seed}},
    }


def wait_done(pid, timeout_s=1800):
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


def run(seed):
    g = build_graph(seed)
    r = post("/prompt", {"prompt": g, "client_id": CLIENT})
    pid = r.get("prompt_id")
    print("char seed=%d submitted pid=%s" % (seed, pid))
    state, errs = wait_done(pid)
    print("char seed=%d %s" % (seed, state))
    if state != "done":
        print("errors:", str(errs)[:800])
        return None
    src = None
    if os.path.isdir(OUT_DIR):
        cands = [os.path.join(OUT_DIR, n) for n in os.listdir(OUT_DIR)
                 if n.startswith("char_%d_" % seed) and n.endswith(".png")]
        if cands:
            src = max(cands, key=os.path.getmtime)
    if not src:
        print("seed=%d done but no output file found" % seed)
        return None
    print("char seed=%d -> %s" % (seed, src))
    return src


if __name__ == "__main__":
    seeds = [int(a) for a in sys.argv[1:]] or SEEDS
    outs = []
    for s in seeds:
        p = run(s)
        if p:
            outs.append(p)
    print("CHAR RUN FINISHED:", outs)
