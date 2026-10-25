"""Assemble CASE-2026-1024-03 final video: 6 shots + window music.

Same pipeline as assemble_case01_v2.py (trim to storyboard duration,
scale-to-cover + center-crop to 1080x1920, 24fps, concat, mux the original
window music). All six shots come from the CASE-03 run (shots 1-5 Hybrid +
first_frame anchors, shot 6 Ref2VA).

Storyboard cut points: 0.00 / 2.41 / 4.75 / 7.09 / 9.43 / 11.77 / 15.00
(拍吸附, 4-beat spacing) -> durations 2.41 / 2.34 / 2.34 / 2.34 / 2.34 / 3.23.

Output: cases/assets/CASE-2026-1024-03-final.mp4
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

DUR = [2.41, 2.34, 2.34, 2.34, 2.34, 3.23]
TOTAL = sum(DUR)  # 15.00


def main():
    parts = []
    for i, d in enumerate(DUR, 1):
        src = os.path.join(ASSETS, "case03_shot%d.mp4" % i)
        if not os.path.exists(src):
            print("MISSING", src)
            sys.exit(1)
        parts.append(
            "[%d:v]trim=0:%.2f,setpts=PTS-STARTPTS,"
            "scale=1080:1920:force_original_aspect_ratio=increase,"
            "crop=1080:1920,setsar=1,fps=24[v%d]" % (i - 1, d, i - 1))
    fc = ";".join(parts)
    fc += ";" + "".join("[v%d]" % i for i in range(6))
    fc += "concat=n=6:v=1:a=0[vc]"
    fc += (";[6:a]atrim=0:%.2f,asetpts=PTS-STARTPTS,"
           "afade=t=in:st=0:d=0.20,afade=t=out:st=%.2f:d=0.50[ac]"
           % (TOTAL, TOTAL - 0.5))

    out = os.path.join(ASSETS, "CASE-2026-1024-03-final.mp4")
    cmd = [ffmpeg, "-y"]
    for i in range(1, 7):
        cmd += ["-i", os.path.join(ASSETS, "case03_shot%d.mp4" % i)]
    cmd += ["-i", os.path.join(ASSETS, "w03_lowride_15s.wav")]
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
