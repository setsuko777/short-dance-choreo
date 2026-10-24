#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""样本级精确窗口裁切（M4 产物）。

背景（M4 实测坑）：cloud_cache 的剪映 m4a 用 ffmpeg `-ss` seek（输入/输出
两种模式）都有约 20s 偏差——seek 落点与全解码时间线不一致，导致裁出来的
窗口不是目标段落（实测 RMS 对不上）。本工具改为「全解码 → 按样本切片 →
编码回 WAV」，与全曲分析共用同一条时间线，样本级精确。

依赖：numpy + ffmpeg（static_ffmpeg 自动定位），不依赖 soundfile/librosa。

用法：
  python trim_window.py in.m4a --ss 12.6 --t 15 -o window.wav [--json out.json]
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from beat_tracker import SR, analyze, decode_audio  # noqa: E402
from static_ffmpeg import run  # noqa: E402


def decode_raw(ffmpeg, path):
    """全解码为单声道 f32 PCM（无 seek，时间线与 beat_tracker 一致）。"""
    cmd = [ffmpeg, "-i", str(path), "-f", "f32le", "-ac", "1",
           "-ar", str(SR), "-"]
    r = subprocess.run(cmd, capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg decode failed: " + r.stderr.decode(
            "utf-8", "ignore")[-300:])
    return np.frombuffer(r.stdout, dtype=np.float32).copy()


def encode_wav(ffmpeg, x, out_path):
    cmd = [ffmpeg, "-y", "-f", "f32le", "-ar", str(SR), "-ac", "1",
           "-i", "-", str(out_path)]
    r = subprocess.run(cmd, input=x.astype(np.float32).tobytes(),
                       capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("ffmpeg encode failed: " + r.stderr.decode(
            "utf-8", "ignore")[-300:])


def main():
    ap = argparse.ArgumentParser(description="样本级精确窗口裁切")
    ap.add_argument("input")
    ap.add_argument("--ss", type=float, required=True, help="窗口起点（秒）")
    ap.add_argument("-t", "--duration", type=float, required=True,
                    help="窗口时长（秒）")
    ap.add_argument("-o", "--output", required=True, help="输出 WAV 路径")
    ap.add_argument("--json", default=None,
                    help="顺带跑节拍分析并写 JSON（可选）")
    a = ap.parse_args()

    ffmpeg, _ = run.get_or_fetch_platform_executables_else_raise()
    x = decode_raw(ffmpeg, a.input)
    i0 = int(round(a.ss * SR))
    i1 = min(len(x), i0 + int(round(a.duration * SR)))
    if i0 >= len(x):
        print(json.dumps({"error": "窗口起点超出音频长度",
                          "duration_s": len(x) / SR}, ensure_ascii=False))
        sys.exit(2)
    seg = x[i0:i1]
    if len(seg) < SR:  # 不足 1s 无分析意义
        print(json.dumps({"error": "窗口不足 1 秒"}, ensure_ascii=False))
        sys.exit(2)
    Path(a.output).parent.mkdir(parents=True, exist_ok=True)
    encode_wav(ffmpeg, seg, a.output)
    info = {"output": a.output, "ss": a.ss, "duration_s": round(len(seg) / SR, 3)}
    if a.json:
        r = analyze(a.output)
        Path(a.json).write_text(json.dumps(r, ensure_ascii=False, indent=2),
                                encoding="utf-8")
        info["bpm"] = r["bpm"]
        info["drop_s"] = r.get("drop_s")
    print(json.dumps(info, ensure_ascii=False))


if __name__ == "__main__":
    main()
