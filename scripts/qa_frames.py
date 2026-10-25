"""QA helper: pull N frames out of a generated shot and build a hstack sheet.

Usage:
    python qa_frames.py <tag> <shot> [frame,frame,...]

<tag>  = shot filename prefix, e.g. case1025 -> cases/assets/case1025_shot%d.mp4
<shot> = shot index (1..6)
frames = comma separated frame numbers (default 0,18,36,54,72)

Output: cases/assets/_qa_<tag>_s<shot>.jpg  (5-up horizontal sheet)
Also drops the individual frames as cases/assets/_qa_<tag>_s<shot>_f<NN>.png
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import os
import subprocess
import sys


sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层
_env.ensure_deps()


ffmpeg = _env.get_ffmpeg()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "cases", "assets")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    suffix = "_v2" if "--v2" in sys.argv else ""
    tag = args[0]
    shot = int(args[1])
    frames = [int(x) for x in args[2].split(",")] if len(args) > 2 \
        else [0, 18, 36, 54, 72]
    src = os.path.join(ASSETS, "%s_shot%d%s.mp4" % (tag, shot, suffix))
    if not os.path.exists(src):
        print("MISSING", src)
        sys.exit(1)
    pngs = []
    for f in frames:
        dst = os.path.join(ASSETS, "_qa_%s_s%d%s_f%02d.png" % (tag, shot, suffix, f))
        subprocess.run([ffmpeg, "-y", "-i", src,
                        "-vf", "select=eq(n\\,%d)" % f, "-vsync", "0",
                        "-frames:v", "1", dst], capture_output=True)
        pngs.append(dst)
    ins = []
    for p in pngs:
        ins += ["-i", p]
    w = 250
    h = int(round(w * 1472 / 832))
    fc = ""
    for i in range(len(pngs)):
        fc += "[%d:v]scale=%d:%d[v%d];" % (i, w, h, i)
    fc += "".join("[v%d]" % i for i in range(len(pngs)))
    fc += "hstack=inputs=%d[out]" % len(pngs)
    out = os.path.join(ASSETS, "_qa_%s_s%d%s.jpg" % (tag, shot, suffix))
    r = subprocess.run([ffmpeg, "-y"] + ins +
                       ["-filter_complex", fc, "-map", "[out]", "-q:v", "3",
                        out], capture_output=True, text=True)
    if r.returncode != 0:
        print("MONTAGE FAILED")
        print(r.stderr[-800:])
        sys.exit(1)
    print("sheet ->", out)


if __name__ == "__main__":
    main()
