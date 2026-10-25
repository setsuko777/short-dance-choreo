"""QA: 逐镜检测首帧锚点命中度 + 镜内漂移（DG-015 / DG-017 的数值判据）。

对每一镜：
1. 抽 f0 与末帧
2. 与对应构图锚点图做像素比对：背景带（左侧 90px 竖条）均值/std、整图 MAD
3. 用「非背景像素」求主体包围盒中心 x，记录首帧→末帧的水平漂移
4. 输出首帧命中判定：bg 均值差 < 4 且 std < 3 视为背景锁定

Usage: python qa_anchor_hit.py <tag> <frame_count> <anchor1,anchor2,...>
例:   python qa_anchor_hit.py case1025 73 qw21_a1_full.png,qw21_a2_eye.png,...
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import os
import subprocess
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层
_env.ensure_deps()


ffmpeg = _env.get_ffmpeg()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "cases", "assets")


def frame_png(src, n, dst):
    subprocess.run([ffmpeg, "-y", "-i", src,
                    "-vf", "select=eq(n\\,%d)" % n, "-vsync", "0",
                    "-frames:v", "1", dst], capture_output=True)


def stats(path, bgx=90):
    a = np.asarray(Image.open(path).convert("RGB")).astype(np.float32)
    bg = a[80:-80, 0:bgx]
    return a, bg.mean(), bg.std()


def subject_center_x(a):
    """非背景像素 = 与四角背景色差异 > 18 的像素。"""
    ref = np.concatenate([a[40:80, 0:60].reshape(-1, 3),
                          a[40:80, -60:].reshape(-1, 3)])
    base = ref.mean(axis=0)
    d = np.abs(a - base).sum(axis=2)
    m = d > 18
    if m.sum() < 500:
        return None
    ys, xs = np.nonzero(m)
    return float(xs.mean()) / a.shape[1]


def main():
    tag = sys.argv[1]
    nframes = int(sys.argv[2])
    anchors = sys.argv[3].split(",")
    last = nframes - 1
    print("%-6s %-22s %8s %8s %8s %8s %8s" %
          ("shot", "anchor", "bgΔmean", "bg_std", "MAD", "cx@0", "cx@last"))
    for i, anc in enumerate(anchors, 1):
        src = os.path.join(ASSETS, "%s_shot%d.mp4" % (tag, i))
        ap = os.path.join(ASSETS, anc)
        if not os.path.exists(src) or not os.path.exists(ap):
            print("shot%d MISSING (src=%s anchor=%s)" %
                  (i, os.path.exists(src), os.path.exists(ap)))
            continue
        f0 = os.path.join(ASSETS, "_qa_%s_s%d_f00.png" % (tag, i))
        fl = os.path.join(ASSETS, "_qa_%s_s%d_flast.png" % (tag, i))
        frame_png(src, 0, f0)
        frame_png(src, last, fl)
        a0, bm0, bs0 = stats(f0)
        aa, bma, bsa = stats(ap)
        al, bml, bsl = stats(fl)
        mad = float(np.abs(a0 - aa).mean())
        c0 = subject_center_x(a0)
        cl = subject_center_x(al)
        print("shot%d   %-22s %8.2f %8.2f %8.2f %8s %8s" % (
            i, anc, bm0 - bma, bs0, mad,
            "%.3f" % c0 if c0 else "n/a",
            "%.3f" % cl if cl else "n/a"))


if __name__ == "__main__":
    main()
