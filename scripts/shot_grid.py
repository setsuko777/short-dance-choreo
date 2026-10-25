#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""镜头网格枚举器（M3 校准产物）。

背景：宪法要求「切点吸附实测节拍」+「单镜 2.0–3.5s」+「15s 6 镜 / 6s 3 镜」。
实测发现「每镜 1 bar」只在部分 BPM 可行（bar<2.0s 时低于下限，bar>2.7s 时
15s 铺不满），必须按吸附单位分级枚举：
  1. bar 吸附（1 bar 或 2 bar 每镜，末镜截短 ≥2.0s）
  2. 拍吸附（4–8 拍每镜，末镜截短）——快板区间（约 106–144 BPM）唯一可行模式
无解时如实报错，禁止伪造网格。

用法：
  python shot_grid.py 15 128            # 15s 完整版 @128BPM
  python shot_grid.py 6 120             # 6s 精简版 @120BPM
  python shot_grid.py 15 96 --all       # 列出全部可行解
  python shot_grid.py 15 96 --json      # JSON 输出（供管线消费）
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import argparse
import itertools
import json
import sys

MIN_S, MAX_S = 2.0, 3.5
EPS = 1e-9


def _valid(durations):
    return all(MIN_S - EPS <= d <= MAX_S + EPS for d in durations)


def enumerate_grids(total_s, bpm, min_s=MIN_S, max_s=MAX_S,
                    max_shots=8, bar_units=(1, 2), beat_range=(4, 9)):
    """枚举可行镜头网格。返回 [(mode, [durations...]), ...]，按优先级排序。"""
    bar = 240.0 / bpm
    beat = 60.0 / bpm
    grids = []
    # 模式 1：整数 bar 吸附
    for n in range(2, max_shots + 1):
        for combo in itertools.product(bar_units, repeat=n - 1):
            used = sum(combo) * bar
            last = total_s - used
            if last < min_s - EPS or last > max_s + EPS:
                continue
            ds = [k * bar for k in combo] + [last]
            if _valid(ds):
                grids.append(("bar", ds))  # 精确值，禁止取整（误差会随镜数累积）
    # 模式 2：整数拍吸附
    for n in range(2, max_shots + 1):
        for combo in itertools.product(range(*beat_range), repeat=n - 1):
            used = sum(combo) * beat
            last = total_s - used
            if last < min_s - EPS or last > max_s + EPS:
                continue
            ds = [k * beat for k in combo] + [last]
            if _valid(ds):
                grids.append(("beat", ds))  # 精确值，禁止取整
    # 排序：bar 吸附（切点落小节线）强优先 → 镜数接近宪法默认 6 → 时长方差小
    # 音乐性依据：舞蹈剪辑惯例切点优先落 downbeat，拍吸附只是快板兜底
    def key(g):
        mode, ds = g
        return (0 if mode == "bar" else 1,
                abs(len(ds) - 6),
                sum((d - sum(ds) / len(ds)) ** 2 for d in ds))
    grids.sort(key=key)
    return grids


def best_grid(total_s, bpm, **kw):
    grids = enumerate_grids(total_s, bpm, **kw)
    return grids[0] if grids else None


def cut_points(total_s, bpm, **kw):
    """返回 [{shot, start, end}, ...]，切点毫秒级（供分镜表直接填）。"""
    g = best_grid(total_s, bpm, **kw)
    if not g:
        return None
    mode, ds = g
    out, t = [], 0.0
    for i, d in enumerate(ds, 1):
        out.append({"shot": i, "start": round(t, 3), "end": round(t + d, 3),
                    "dur": d})
        t += d
    return {"mode": mode, "bpm": bpm, "shots": out}


def main():
    ap = argparse.ArgumentParser(description="镜头网格枚举（M3 校准）")
    ap.add_argument("total", type=float, help="总时长（秒），15 或 6")
    ap.add_argument("bpm", type=float, help="实测 BPM（R1 输出）")
    ap.add_argument("--all", action="store_true", help="列出全部可行解")
    ap.add_argument("--json", action="store_true", help="JSON 输出")
    ap.add_argument("--max-shots", type=int, default=8)
    a = ap.parse_args()
    grids = enumerate_grids(a.total, a.bpm, max_shots=a.max_shots)
    if not grids:
        msg = {"error": "无可行网格",
               "reason": "BPM=%s 时 1bar=%.3fs / 2bar=%.3fs 均无法在 %ss 内铺出 "
                         "2.0–3.5s 镜头；请更换时长模板或人工指定切点并标注偏离"
                         % (a.bpm, 240.0 / a.bpm, 480.0 / a.bpm, a.total)}
        print(json.dumps(msg, ensure_ascii=False))
        sys.exit(2)
    if a.json:
        print(json.dumps(cut_points(a.total, a.bpm, max_shots=a.max_shots),
                         ensure_ascii=False, indent=2))
        return
    if a.all:
        for mode, ds in grids[:12]:
            print("%s吸附 %d 镜 %s" % (mode, len(ds),
                                       "＋".join("%.2f" % d for d in ds)))
        print("（共 %d 解）" % len(grids))
        return
    mode, ds = grids[0]
    print("推荐：%s吸附 %d 镜 %s" % (mode, len(ds),
                                     "＋".join("%.2f" % d for d in ds)))
    t = 0.0
    for i, d in enumerate(ds, 1):
        print("  镜%d: %.2f–%.2fs (%.2fs)" % (i, t, t + d, d))
        t += d


if __name__ == "__main__":
    main()
