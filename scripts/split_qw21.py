#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
QW21 四视图 -> 4 张独立角度图 + 6 张 9:16 镜头锚点图

用法:
    python split_qw21.py            # 裁四格 + 生成锚点
    python split_qw21.py --split    # 只裁四格
    python split_qw21.py --anchors  # 只生成锚点

依赖: numpy, PIL（静态 ffmpeg 不需要）
输出: ../cases/assets/  （同时同步到 ComfyUI input/）
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import os
import sys
import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402
_env.ensure_deps()


# ---------- 路径 ----------
HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
ASSETS = os.path.join(SKILL, "cases", "assets")
COMFY_INPUT = _env.get_comfy_input()
SRC = os.path.join(COMFY_INPUT, "QW21-20261009222652_00001_.png")

BG = np.array([179, 179, 179])          # 四视图统一灰底
TOL = 60                                 # 主体判定阈值（RGB 三通道绝对差之和）

# 四视图分隔缝（数值实测：列区间为纯背景缝）
GAPS = [(544, 608), (1008, 1216), (1392, 1600)]

# 四格 = [缝间区域]，末格右边界取 2016（右侧留白）
CELLS = [
    ("qw21_bust",  0,    544),    # 半身特写（正面）
    ("qw21_front", 608,  1008),   # 全身正面
    ("qw21_side",  1216, 1392),   # 全身纯侧
    ("qw21_back",  1600, 2016),   # 全身背面
]

# 9:16 锚点画布
AW, AH = 832, 1472
PAD = 0.06          # 主体四周留白比例


def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)


def subject_bbox(a, tol=TOL):
    """在灰底图上定位主体 bbox"""
    mask = np.abs(a - BG).sum(axis=2) > tol
    ys = np.where(mask.sum(axis=1) > 3)[0]
    xs = np.where(mask.sum(axis=0) > 3)[0]
    if len(ys) == 0 or len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def to_916(a, bbox, pad=PAD):
    """把 bbox 内主体装进 9:16 画布（保持宽高比，居中，四周留白）"""
    x0, y0, x1, y1 = bbox
    sub = a[y0:y1, x0:x1]
    h, w = sub.shape[:2]
    # 目标：内容占画布 (1-2*pad)
    tw, th = AW * (1 - 2 * pad), AH * (1 - 2 * pad)
    scale = min(tw / w, th / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    img = Image.fromarray(sub.astype(np.uint8)).resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (AW, AH), tuple(int(v) for v in BG))
    canvas.paste(img, ((AW - nw) // 2, (AH - nh) // 2))
    return canvas


def crop_916(a, y0f, y1f, x0f, x1f, pad=PAD, tighten=True, mode="contain"):
    """按相对比例裁一块区域 -> 区域内再收紧主体 bbox -> 装进 9:16 画布

    mode:
      contain —— 完整装下、四周留灰边（全身/中景用）
      cover   —— 放大填满后居中裁切（特写用，主体撑满画面）
    """
    H, W = a.shape[:2]
    x0, x1 = int(W * x0f), int(W * x1f)
    y0, y1 = int(H * y0f), int(H * y1f)
    sub = a[y0:y1, x0:x1]

    if tighten:
        bb = subject_bbox(sub)
        if bb is not None:
            bx0, by0, bx1, by1 = bb
            # 上下保留 2% 余量（身体局部在纵向是连续的，切太紧会变成大特写）
            my = int(sub.shape[0] * 0.02)
            mx = int(sub.shape[1] * 0.02)
            by0 = max(0, by0 - my); by1 = min(sub.shape[0], by1 + my)
            bx0 = max(0, bx0 - mx); bx1 = min(sub.shape[1], bx1 + mx)
            sub = sub[by0:by1, bx0:bx1]

    h, w = sub.shape[:2]
    img = Image.fromarray(sub.astype(np.uint8))

    if mode == "cover":
        # 放大到同时盖住宽与高，再居中裁
        scale = max(AW / w, AH / h)
        nw, nh = max(AW, int(round(w * scale))), max(AH, int(round(h * scale)))
        img = img.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - AW) // 2, (nh - AH) // 2
        img = img.crop((left, top, left + AW, top + AH))
        return img

    tw, th = AW * (1 - 2 * pad), AH * (1 - 2 * pad)
    scale = min(tw / w, th / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (AW, AH), tuple(int(v) for v in BG))
    canvas.paste(img, ((AW - nw) // 2, (AH - nh) // 2))
    return canvas


def do_split():
    a = load(SRC)
    H, W, _ = a.shape
    print("源图 %dx%d" % (W, H))
    out = []
    for name, x0, x1 in CELLS:
        sub = a[:, x0:x1]
        bb = subject_bbox(sub)
        if bb is None:
            print("  %s 未检出主体" % name)
            continue
        bx0, by0, bx1, by1 = bb
        # 向外留 2% 边距
        mx = int(sub.shape[1] * 0.02)
        my = int(sub.shape[0] * 0.02)
        bx0 = max(0, bx0 - mx); bx1 = min(sub.shape[1], bx1 + mx)
        by0 = max(0, by0 - my); by1 = min(sub.shape[0], by1 + my)
        img = Image.fromarray(sub[by0:by1, bx0:bx1].astype(np.uint8))
        p = os.path.join(ASSETS, name + ".png")
        img.save(p)
        print("  %-12s %dx%d  (格内 bbox %s)" % (name, img.width, img.height, (bx0, by0, bx1, by1)))
        out.append(name)
    return out


# ---------------- 6 张镜头锚点 ----------------
# (输出名, 来源格, 裁切区域[上,下,左,右 比例], contain/cover, 说明)
ANCHORS = [
    # 镜1 起手 hook：正面全身，广角铺陈 → 完整装下
    ("qw21_a1_full",  "qw21_front", (0.00, 1.00, 0.00, 1.00), "contain", "镜1 起手 正面全身"),
    # 镜2 特写①眼：瞳孔实测 bust (x=0.385, y=0.283) —— 框以此为中心
    ("qw21_a2_eye",   "qw21_bust",  (0.24, 0.34, 0.30, 0.48), "cover",   "镜2 眼部特写"),
    # 镜3 特写②嘴：眼 0.283 / 下巴 0.375 → 嘴落在 0.36。
    #   已知限制：原设定图嘴部被长刘海遮挡（bust/front 双图唇色检测均无命中），
    #   故锚点图只保证「下半脸近景 + 嘴位居中」的构图，嘴的可见性交由提示词与 QA 抽检。
    ("qw21_a3_mouth", "qw21_bust",  (0.28, 0.42, 0.30, 0.50), "cover",   "镜3 下半脸近景(嘴位居中)"),
    # 镜4 特写③胸腰：front 项圈 0.20–0.26 / 胸饰 0.30–0.32 / 腰 0.36–0.44 → 取 0.23–0.43（切掉裙摆）
    ("qw21_a4_chest", "qw21_front", (0.23, 0.43, 0.15, 0.85), "cover",   "镜4 胸腰特写(drop 爆点)"),
    # 镜5 特写④大腿：front 裙摆下缘 0.48 → 膝 0.645
    ("qw21_a5_thigh", "qw21_front", (0.48, 0.66, 0.18, 0.82), "cover",   "镜5 大腿特写"),
    # 镜6 特写⑤小腿 + 定格：front 膝上 0.64 → 脚 0.95（保住膝盖入画）
    ("qw21_a6_calf",  "qw21_front", (0.64, 0.95, 0.20, 0.80), "cover",   "镜6 小腿/脚特写 + 定格"),
]


# ---- v2 锚点：给孤立切片加上下文（DG-019 对策①）----
# 原则：取到自然边界（头顶/裙摆/肩线/脚底），保留可自洽的人体轮廓，
#       而不是取身体中段的孤立 ECU。
# (输出名, 来源格, 裁切区域[上,下,左,右 比例], 说明)
# 注意：v2 一律用 contain（完整装下、不裁切）。cover 会把头顶切掉——那正好
#  recreate 我们想修的「缺上下文」问题。
# (输出名, 来源格, 裁切区域[上,下,左,右 比例], 说明)
V2_ANCHORS = [
    # 镜2 眼：从「单眼 ECU」改为「头顶→胸 上半身近景」，眼落在上三分之一
    ("qw21_a2_eye_v2",   "qw21_bust",  (0.00, 0.72, 0.12, 0.66),
     "镜2 v2 上半身近景(头顶→胸, 眼在上三分之一)"),
    # 镜3 胸腰：从「胸腰 ECU(无头)」改为「头顶→胯 正面中近景」，头部必须在画内
    ("qw21_a4_chest_v2", "qw21_front", (0.00, 0.76, 0.08, 0.92),
     "镜3 v2 正面中近景(头顶→胯, 含头部)"),
    # 镜6 小腿：从「膝下→脚」改为「裙摆→脚 正面下半身」，用裙摆作自然上边界
    ("qw21_a6_calf_v2",  "qw21_front", (0.44, 1.00, 0.12, 0.88),
     "镜6 v2 正面下半身(裙摆→脚)"),
]


def do_anchors_v2():
    made = []
    for name, src, (y0f, y1f, x0f, x1f), desc in V2_ANCHORS:
        p = os.path.join(ASSETS, src + ".png")
        if not os.path.exists(p):
            print("  缺少来源 %s，先跑 --split" % src)
            continue
        a = load(p)
        canvas = crop_916(a, y0f, y1f, x0f, x1f, mode="contain", tighten=False)
        op = os.path.join(ASSETS, name + ".png")
        canvas.save(op)
        print("  %-20s %dx%d  %s" % (name, canvas.width, canvas.height, desc))
        made.append(name)
    return made


def do_anchors():
    made = []
    for name, src, (y0f, y1f, x0f, x1f), mode, desc in ANCHORS:
        p = os.path.join(ASSETS, src + ".png")
        if not os.path.exists(p):
            print("  缺少来源 %s，先跑 --split" % src)
            continue
        a = load(p)
        # cover 模式不二次收紧：区域坐标已按人体比例精确定位，再收紧会破坏构图中心
        canvas = crop_916(a, y0f, y1f, x0f, x1f, mode=mode,
                          tighten=(mode != "cover"))
        op = os.path.join(ASSETS, name + ".png")
        canvas.save(op)
        print("  %-16s %dx%d  %-4s %s" % (name, canvas.width, canvas.height, mode, desc))
        made.append(name)
    return made


def sync_comfy(names):
    n = 0
    for name in names:
        src = os.path.join(ASSETS, name + ".png")
        if os.path.exists(src):
            import shutil
            shutil.copy(src, os.path.join(COMFY_INPUT, name + ".png"))
            n += 1
    if n:
        print("  已同步 %d 张到 ComfyUI input/" % n)


if __name__ == "__main__":
    os.makedirs(ASSETS, exist_ok=True)
    args = sys.argv[1:]
    mode = "all"
    if "--split" in args:
        mode = "split"
    elif "--v2" in args:
        mode = "v2"
    elif "--anchors" in args:
        mode = "anchors"

    if mode in ("all", "split"):
        print("[1/2] 裁切四格")
        do_split()
    if mode == "v2":
        print("[v2] 生成加上下文的 9:16 锚点")
        made = do_anchors_v2()
    elif mode in ("all", "anchors"):
        print("[2/2] 生成 9:16 锚点")
        made = do_anchors()
    else:
        made = []
    print("[同步]")
    sync_comfy([c[0] for c in CELLS] + [a[0] for a in ANCHORS]
               + [a[0] for a in V2_ANCHORS])
    print("完成")
