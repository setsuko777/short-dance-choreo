#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""单次直出模式的「内部节奏点抽检表」工具（SKILL.md v2.0 宪法 9）

按秒抽帧 + 横向拼图，用于六查第 1/4/5 项：
- 查 1 特写覆盖：核对其点名的身体部位是否真的出现过
- 查 4 崩坏风险：每 2s 一帧（15s ≥8 帧），无分镜兜底
- 查 5 一致性：对比 f0 与末帧的背景/发色/服装（后半段漂移高发）

取点规则：必取 drop ±1 帧、必取最后一帧、其余每 2s 一帧。

用法:
    python qa_oneshot.py <mp4> [时间点,秒...]
    python qa_oneshot.py ../cases/assets/case1025_oneshot.mp4 0,2,4,6,6.889,8,10,12,14,14.96
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import json
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层
_env.ensure_deps()


FFMPEG = _env.get_ffmpeg()
FFPROBE = _env.get_ffprobe()

HERE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(os.path.dirname(HERE), "cases", "assets")

DEFAULT_POINTS = "0,2,4,6,6.889,8,10,12,14"


def probe_duration(src):
    r = subprocess.run(
        [FFPROBE, "-v", "quiet", "-show_entries", "format=duration",
         "-show_entries", "stream=width,height,nb_frames,r_frame_rate",
         "-of", "json", src], capture_output=True, text=True)
    return json.loads(r.stdout)


def main():
    src = sys.argv[1] if len(sys.argv) > 1 else os.path.join(ASSETS, "case1025_oneshot.mp4")
    pts = [float(x) for x in
           (sys.argv[2] if len(sys.argv) > 2 else DEFAULT_POINTS).split(",")]
    tag = os.path.splitext(os.path.basename(src))[0]

    info = probe_duration(src)
    st = info["streams"][0]
    dur = float(info["format"]["duration"])
    fps = eval(st.get("r_frame_rate", "24/1"))
    last = (int(st.get("nb_frames", 0)) - 1) / fps if st.get("nb_frames") else dur - 1 / fps
    print("视频 %s  %sx%s  %.3fs  fps=%.3f  末帧@%.3fs"
          % (os.path.basename(src), st["width"], st["height"], dur, fps, last))
    pts = pts + [round(last, 3)]          # 宪法 9：必取最后一帧

    frames = []
    for i, t in enumerate(pts):
        out = os.path.join(ASSETS, "_qa_%s_t%06.3f.png" % (tag, t))
        r = subprocess.run([FFMPEG, "-y", "-v", "quiet", "-i", src,
                            "-ss", "%.3f" % t, "-frames:v", "1", out],
                           capture_output=True)
        if not os.path.exists(out):
            # 末帧可能落在 seek 边界之外：回退用 -sseof 从尾部取
            subprocess.run([FFMPEG, "-y", "-v", "quiet", "-sseof", "-0.05",
                            "-i", src, "-frames:v", "1", out], capture_output=True)
        if not os.path.exists(out):
            print("  抽帧失败 t=%.3f（跳过）" % t)
            continue
        frames.append(out)
    print("抽帧 %d 张" % len(frames))

    # 横向拼图（统一高度 640）
    from PIL import Image
    ims = []
    for f in frames:
        im = Image.open(f)
        h = 640
        ims.append(im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS))
    W = sum(i.width for i in ims) + 6 * (len(ims) - 1)
    cv = Image.new("RGB", (W, 640), (255, 255, 255))
    x = 0
    for im in ims:
        cv.paste(im, (x, 0))
        x += im.width + 6
    out = os.path.join(ASSETS, "_qa_%s_timeline.jpg" % tag)
    cv.save(out, quality=92)
    print("拼图 %s  (%dx%d)" % (out, cv.width, cv.height))
    print("时间点:", pts)


if __name__ == "__main__":
    main()
