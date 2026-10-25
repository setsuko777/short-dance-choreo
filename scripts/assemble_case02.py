"""Assemble CASE-2026-1024-02 final video (6s, 2 shots).

Same pipeline as assemble_case01.py (trim to storyboard duration, scale-to-cover
+ center-crop to 1080x1920, 24fps, concat, mux the original window music), for
the 6s two-shot degraded layout: shot 1 = hook + eye anchor (2.53s), shot 2 =
drop burst + closing steps + freeze (3.41s). Ending freeze pose is designed to
match shot 1's opening (fists at chest) for seamless looping.

Output: cases/assets/CASE-2026-1024-02-final.mp4
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

# storyboard durations (s) - cut points on measured downbeats (case-02 §4)
DUR = [2.53, 3.41]
TOTAL = sum(DUR)  # 5.94

# shot 1 uses the v2 anchored re-run (DG-015 fix: frame-0 medium close-up);
# shot 2 is the Hybrid + first_frame anchored drop-burst shot.
SRC = {1: "case02_shot1_v2.mp4", 2: "case02_shot2.mp4"}


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
    fc += ";" + "".join("[v%d]" % i for i in range(len(DUR)))
    fc += "concat=n=%d:v=1:a=0[vc]" % len(DUR)
    fc += (";[%d:a]atrim=0:%.2f,asetpts=PTS-STARTPTS,"
           "afade=t=in:st=0:d=0.15,afade=t=out:st=%.2f:d=0.40[ac]"
           % (len(DUR), TOTAL, TOTAL - 0.40))

    out = os.path.join(ASSETS, "CASE-2026-1024-02-final.mp4")
    cmd = [ffmpeg, "-y"]
    for i in range(1, len(DUR) + 1):
        cmd += ["-i", os.path.join(ASSETS, SRC[i])]
    cmd += ["-i", os.path.join(ASSETS, "w02_ukele_6s.wav")]
    cmd += ["-filter_complex", fc, "-map", "[vc]", "-map", "[ac]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", out]
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
