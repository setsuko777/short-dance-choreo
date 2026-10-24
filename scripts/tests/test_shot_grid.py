#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""shot_grid.py 单元测试：验证切点全部落在拍/bar 网格上且时长合宪。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from shot_grid import enumerate_grids, best_grid, cut_points  # noqa: E402

BEAT = lambda bpm: 60.0 / bpm  # noqa: E731
ok = True


def check(cond, msg):
    global ok
    print(("  PASS " if cond else "  FAIL ") + msg)
    if not cond:
        ok = False


print("== 1. 切点必须落在拍网格上（容差 1ms）==")
for bpm in [88, 96, 104, 112, 120, 128, 136, 150, 160, 174]:
    for total in [15.0, 6.0]:
        g = best_grid(total, bpm)
        if g is None:
            print("  (无解，跳过 %ss@%s)" % (total, bpm))
            continue
        mode, ds = g
        beat = BEAT(bpm)
        t = 0.0
        all_on = True
        for d in ds[:-1]:
            t += d
            n = t / beat
            if abs(n - round(n)) > 0.002:
                all_on = False
        # 末镜截短允许不对齐（视频终点非乐理终点）
        check(all_on, "%ss@%d BPM %s吸附 %d 镜 切点全在拍上" %
              (total, bpm, mode, len(ds)))

print("== 2. 单镜时长必须在 2.0–3.5s ==")
for bpm in [80, 90, 100, 110, 120, 128, 140, 150, 160, 175]:
    for total in [15.0, 6.0]:
        g = best_grid(total, bpm)
        if g is None:
            continue
        _, ds = g
        check(all(2.0 - 1e-9 <= d <= 3.5 + 1e-9 for d in ds),
              "%ss@%d BPM 时长 %s 全部合规" %
              (total, bpm, ["%.2f" % d for d in ds]))

print("== 3. 与 M1 样例一致性（回归保护）==")
g = best_grid(15.0, 96.0)
check(g == ("bar", [2.5] * 6), "15s@96 → 6×2.5s bar（sample-01 同款）")
g = best_grid(6.0, 120.0)
check(g == ("bar", [2.0, 2.0, 2.0]), "6s@120 → 3×2.0s bar（sample-02 同款）")

print("== 4. 无解必须如实返回 None（禁止伪造）==")
# 1 bar > 3.5s 且 2 bar 超限的极端慢板
r = best_grid(6.0, 40.0)
check(r is None, "6s@40BPM（bar=6s）无解 → None")
r = best_grid(15.0, 30.0)
check(r is None, "15s@30BPM（bar=8s）无解 → None")

print("== 5. cut_points 结构完整性 ==")
cp = cut_points(15.0, 128.0)
check(cp is not None and len(cp["shots"]) >= 2, "cut_points 返回 shots 列表")
check(abs(cp["shots"][-1]["end"] - 15.0) < 1e-6, "末镜终点 = 15.0s")
check(all(cp["shots"][i]["end"] == cp["shots"][i + 1]["start"]
          for i in range(len(cp["shots"]) - 1)), "切点首尾相接无缝隙")

print()
print("shot_grid 测试: %s" % ("PASS ✅" if ok else "FAIL ❌"))
sys.exit(0 if ok else 1)
