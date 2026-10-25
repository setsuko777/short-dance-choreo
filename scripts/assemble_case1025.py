"""Assemble CASE-2026-1025-01 final video: 6 shots + window music.

Same pipeline as assemble_case03.py (trim to storyboard duration,
scale-to-cover + center-crop to 1080x1920, 24fps, concat, mux the original
window music). All six shots are Hybrid + first_frame anchors.

Storyboard cut points come from the measured beat grid of 777.mp3 (124.5 BPM,
beat 0.482s) — 拍吸附模式, 误差 0ms:
0.000 / 2.403 / 4.818 / 7.233 / 9.637 / 12.511 / 14.920
-> durations 2.403 / 2.415 / 2.415 / 2.404 / 2.874 / 2.409 (total 14.920s).
The window music is rebuilt by concatenating the same six slices.

Output: cases/assets/CASE-2026-1025-01-final.mp4
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
ffprobe = _env.get_ffprobe()
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ASSETS = os.path.join(ROOT, "cases", "assets")

DUR = [2.403, 2.415, 2.415, 2.404, 2.874, 2.409]
TOTAL = sum(DUR)  # 14.920
N = len(DUR)


def build_window_wav():
    """Concat the six beat-aligned slices back into one continuous window."""
    dst = os.path.join(ASSETS, "qw21_window.wav")
    ins = []
    for i in range(1, N + 1):
        src = os.path.join(ASSETS, "qw21_s%d.wav" % i)
        if not os.path.exists(src):
            print("MISSING", src)
            sys.exit(1)
        ins += ["-i", src]
    fc = "".join("[%d:a]" % i for i in range(N))
    fc += "concat=n=%d:v=0:a=1[ac]" % N
    cmd = [ffmpeg, "-y"] + ins + [
        "-filter_complex", fc, "-map", "[ac]",
        "-c:a", "pcm_s16le", "-ar", "44100", "-ac", "2", dst]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("WINDOW BUILD FAILED")
        print(r.stderr[-1500:])
        sys.exit(1)
    print("window wav ->", dst)
    return dst


def main():
    v2 = "--v2" in sys.argv
    wav = build_window_wav()
    parts = []
    for i, d in enumerate(DUR, 1):
        # v2：镜 2/3/6 用加上下文锚点重跑的片段，1/4/5 沿用 v1
        tag = "case1025_shot%d_v2.mp4" % i if (v2 and i in (2, 3, 6)) \
            else "case1025_shot%d.mp4" % i
        src = os.path.join(ASSETS, tag)
        if not os.path.exists(src):
            print("MISSING", src)
            sys.exit(1)
        parts.append(
            "[%d:v]trim=0:%.3f,setpts=PTS-STARTPTS,"
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1,fps=24[v%d]" % (i - 1, d, i - 1))
    fc = ";".join(parts)
    fc += ";" + "".join("[v%d]" % i for i in range(N))
    fc += "concat=n=%d:v=1:a=0[vc]" % N
    fc += (";[6:a]atrim=0:%.3f,asetpts=PTS-STARTPTS,"
           "afade=t=in:st=0:d=0.15,afade=t=out:st=%.3f:d=0.40[ac]"
           % (TOTAL, TOTAL - 0.40))

    out = os.path.join(ASSETS, "CASE-2026-1025-01-final%s.mp4"
                       % ("-v2" if v2 else ""))
    cmd = [ffmpeg, "-y"]
    for i in range(1, N + 1):
        tag = "case1025_shot%d_v2.mp4" % i if (v2 and i in (2, 3, 6)) \
            else "case1025_shot%d.mp4" % i
        cmd += ["-i", os.path.join(ASSETS, tag)]
    cmd += ["-i", wav]
    cmd += ["-filter_complex", fc, "-map", "[vc]", "-map", "[ac]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
    print(" ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG FAILED")
        print(r.stderr[-1500:])
        sys.exit(1)
    print("ASSEMBLED ->", out)
    r2 = subprocess.run(
        [ffprobe, "-v", "quiet",
         "-show_entries", "stream=codec_name,width,height,r_frame_rate",
         "-show_entries", "format=duration", "-of", "json", out],
        capture_output=True, text=True)
    print(r2.stdout)


if __name__ == "__main__":
    main()
