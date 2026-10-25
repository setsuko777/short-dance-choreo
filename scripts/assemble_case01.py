"""Assemble CASE-2026-1024-01 final video from 6 generated shots.

Per shot: trim video to the storyboard duration, scale-to-cover + center-crop
to 1080x1920, 24fps. Concat 6 segments, then mux the original window music
(w01_ukele_15s.wav) as the audio track (guarantees beat sync - cuts land on
measured downbeats). Output: cases/assets/CASE-2026-1024-01-final.mp4
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

# storyboard durations (s) - cut points on measured downbeats
DUR = [2.52, 2.53, 2.52, 2.53, 2.52, 2.34]
TOTAL = sum(DUR)  # 14.96


def main():
    parts = []
    for i, d in enumerate(DUR, 1):
        src = os.path.join(ASSETS, "shot%d.mp4" % i)
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

    cmd = [ffmpeg, "-y"]
    for i in range(1, 7):
        cmd += ["-i", os.path.join(ASSETS, "shot%d.mp4" % i)]
    cmd += ["-i", os.path.join(ASSETS, "w01_ukele_15s.wav")]
    cmd += ["-filter_complex", fc, "-map", "[vc]", "-map", "[ac]",
            "-c:v", "libx264", "-preset", "medium", "-crf", "18",
            "-pix_fmt", "yuv420p", "-r", "24",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart",
            os.path.join(ASSETS, "CASE-2026-1024-01-final.mp4")]
    print(" ".join(cmd))
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print("FFMPEG FAILED")
        print(r.stderr[-1500:])
        sys.exit(1)
    print("ASSEMBLED ->", os.path.join(ASSETS, "CASE-2026-1024-01-final.mp4"))
    # verify
    r2 = subprocess.run(
        [_env.get_ffprobe(), "-v", "quiet",
         "-show_entries", "stream=codec_name,width,height,r_frame_rate",
         "-show_entries", "format=duration", "-of", "json",
         os.path.join(ASSETS, "CASE-2026-1024-01-final.mp4")],
        capture_output=True, text=True)
    print(r2.stdout)


if __name__ == "__main__":
    main()
