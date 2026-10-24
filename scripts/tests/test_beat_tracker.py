#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
test_beat_tracker.py — M0 准出测试
1) 合成 click 轨（已知 BPM 真值）：BPM 恢复误差 < 1%，拍对齐中位误差 < 30ms
2) 3 首真实曲目（慢/中/快）：输出 BPM、DP 自洽校验、段落结构
"""
import json
import sys
import tempfile
import wave
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import beat_tracker as bt

SR = 22050


def make_click_track(bpm, seconds=30.0, seed=0):
    """合成测试轨：每拍一个 1kHz 短 tick + 低幅白噪声底。"""
    rng = np.random.default_rng(seed)
    n = int(seconds * SR)
    x = rng.normal(0, 0.01, n)          # 噪声底
    period = 60.0 / bpm
    t = 0.0
    while t < seconds:
        i0 = int(t * SR)
        tick = np.sin(2 * np.pi * 1000 * np.arange(0, 0.02, 1 / SR)) * \
            np.exp(-np.arange(0, 0.02, 1 / SR) / 0.004) * 0.9
        end = min(n, i0 + len(tick))
        x[i0:end] += tick[:end - i0]
        t += period
    return np.clip(x, -1, 1)


def write_wav(x, path):
    pcm = (x * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(pcm.tobytes())


def main():
    print("=" * 62)
    print("M0 测试 1/2：合成 click 轨（BPM 真值已知）")
    print("=" * 62)
    ok = True
    with tempfile.TemporaryDirectory() as td:
        for bpm_true in (90.0, 120.0, 150.0):
            wav = Path(td) / f"click_{int(bpm_true)}.wav"
            write_wav(make_click_track(bpm_true), wav)
            r = bt.analyze(str(wav))
            err = abs(r["bpm"] - bpm_true) / bpm_true * 100
            # 拍对齐：每个真值拍找最近估计拍，记录带符号偏移
            beats = np.array(r["beats_ms"]) / 1000.0
            period = 60.0 / bpm_true
            true_beats = np.arange(0, r["duration_s"], period)
            offs = []
            for tb in true_beats:
                if len(beats):
                    k = int(np.argmin(np.abs(beats - tb)))
                    offs.append(beats[k] - tb)
            med_off = float(np.median(np.abs(offs))) * 1000 if offs else 999
            med_signed = float(np.median(offs)) * 1000 if offs else 999
            status = "PASS" if (err < 1.0 and med_off < 30) else "FAIL"
            if status == "FAIL":
                ok = False
            print(f"  真值 {bpm_true:5.1f} BPM → 估计 {r['bpm']:6.2f} "
                  f"(误差 {err:.2f}%, DP自洽 {r['bpm_dp_check']:6.2f}) | "
                  f"拍对齐 |误差|中位 {med_off:5.1f}ms "
                  f"(带符号 {med_signed:+.1f}ms) | 置信 {r['bpm_confidence']:.2f} | {status}")

    print()
    print("=" * 62)
    print("M0 测试 2/2：真实曲目（慢 / 中 / 快）")
    print("=" * 62)
    tracks = [
        "C:/Users/Admin/cloud_cache/7376164934629738505_可爱童真节奏  Happy Ukulele Fun Kids.m4a",
        "C:/Users/Admin/cloud_cache/7376219644744435738_时尚动感嘻哈节奏  Lowride Cruiser.m4a",
        "C:/Users/Admin/cloud_cache/7491937596432467994_活力 动感 潮流 快闪 鼓点.m4a",
    ]
    results = {}
    for t in tracks:
        p = Path(t)
        if not p.exists():
            print(f"  [跳过] 文件不存在: {p.name}")
            continue
        r = bt.analyze(str(p))
        results[p.name] = r
        secs = " ".join(f"{s['label']}@{s['start_s']}-{s['end_s']}s"
                        for s in r["sections"][:6])
        print(f"  {p.name[:28]:30s} BPM {r['bpm']:6.2f} "
              f"(DP自洽 {r['bpm_dp_check']:6.2f}, 差 "
              f"{abs(r['bpm']-r['bpm_dp_check'])/r['bpm']*100:.1f}%) "
              f"置信 {r['bpm_confidence']:.2f} | drop {r['drop_s']}s")
        print(f"      段落: {secs}")
        # 抽检前 5 拍间距规律性
        b = np.array(r["beats_ms"][:8]) / 1000.0
        if len(b) > 3:
            ibi = np.diff(b)
            print(f"      前8拍间距(ms): {[round(v*1000) for v in ibi]}")

    out = Path(__file__).resolve().parent.parent / "m0_test_results.json"
    out.write_text(json.dumps(results, ensure_ascii=False, indent=2),
                   encoding="utf-8")
    print(f"\n完整结果已写入: {out}")
    print("M0 准出: " + ("PASS ✅" if ok else "FAIL ❌（合成轨未达标）"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
