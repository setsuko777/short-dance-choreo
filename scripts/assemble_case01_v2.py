"""Assemble CASE-2026-1024-01 v2 final video: v1 shots 1/2/3/6 + v2 shots 4/5.

Same pipeline as assemble_case01.py (trim to storyboard duration, scale-to-cover
+ center-crop to 1080x1920, 24fps, concat, mux the original window music), but
shots 4 and 5 come from the v2 first_frame-anchored run (shotN_v2.mp4) while the
four unchanged shots are reused from v1 (shotN.mp4).

Output: cases/assets/CASE-2026-1024-01-final-v2.mp4
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

# storyboard durations (s) - cut points on measured downbeats (unchanged from v1)
DUR = [2.52, 2.53, 2.52, 2.53, 2.52, 2.34]
TOTAL = sum(DUR)  # 14.96

# v2 shot map: 4 and 5 replaced by the first_frame-anchored renders
SRC = {1: "shot1.mp4", 2: "shot2.mp4", 3: "shot3.mp4",
       4: "shot4_v2.mp4", 5: "shot5_v2.mp4", 6: "shot6.mp4"}


def main():
    parts = []
    for i, d in enumerate(DUR, 1):
        src = os.path.join(ASSETS, SRC[i])
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

    out = os.path.join(ASSETS, "CASE-2026-1024-01-final-v2.mp4")
    cmd = [ffmpeg, "-y"]
    for i in range(1, 7):
        cmd += ["-i", os.path.join(ASSETS, SRC[i])]
    cmd += ["-i", os.path.join(ASSETS, "w01_ukele_15s.wav")]
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
