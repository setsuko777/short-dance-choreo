#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
角色设定图（四视图 / 多视图拼图）→ 独立角度图 + 9:16 构图锚点（通用版）

与案例专用脚本 scripts/split_qw21.py 的区别：本脚本不硬编码任何一张图的坐标，
全部由数值检测得出（背景色自动估计 → 整体 bbox 收紧 → 列投影找背景缝 → 切格），
适用于任意「横向排列 + 近似纯色背景」的角色设定图。

典型流程（每步都可单独跑，便于中途用视觉确认）：

    # 1) 只看检测结果，不写文件
    python split_char_sheet.py --src X.png --detect

    # 2) 切格（从左到右；用 --map 指定每个格的角度名）
    python split_char_sheet.py --src X.png --split --map bust,front,side,back

    # 3) 生成粗锚点：全身 / 上半身 / 下半身（contain 模式，保留上下文，见 DG-019）
    python split_char_sheet.py --anchors --anchor-src front

    # 4) 出纵向条带探针图 —— 用于视觉定位眼/嘴/胸/大腿/小腿落在哪个比例区间
    python split_char_sheet.py --probe --from bust

    # 5) 人工定稿某个特写锚点（比例是相对该格主体 bbox 的 [上,下,左,右]）
    #    取景要保留上下文（含完整头部 + 肩），不要顶格特写 —— DG-019
    python split_char_sheet.py --tune eye --from bust --box 0.00,0.52,0.15,0.85

    # 6) 同步到 ComfyUI input/（Hybrid 路线的 LoadImage 只认这个目录）
    python split_char_sheet.py --sync

    # 一次跑完 2+3+6
    python split_char_sheet.py --src X.png --map bust,front,side,back --all

产物命名：全部以 --tag 为前缀（默认 char），落 --outdir（默认 ../cases/assets/）。
定稿参数持久化到 <outdir>/<tag>_anchors.json，换图重跑时可直接复用。

依赖：numpy, PIL
"""
import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _env  # noqa: E402  环境适配层（消除本机硬编码路径）
_env.ensure_deps()
import argparse
import json
import os
import sys


_env.ensure_deps()              # numpy / PIL 缺一不可，缺了会给行动指引
import numpy as np              # noqa: E402
from PIL import Image, ImageDraw  # noqa: E402

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
DEFAULT_OUT = os.path.join(SKILL, "cases", "assets")

AW, AH = 832, 1472          # 9:16 锚点画布
PAD = 0.08                  # contain 模式四周留白比例（留够边，避免主体贴框）
TOL = 60                    # 主体判定阈值（RGB 三通道绝对差之和）
THIN = 0.001                # bbox 行列判定阈值：> 宽度×THIN 才计入
                            #   （经验：0.004 会把呆毛/发梢这类细结构过滤掉，导致头顶被裁）
MARGIN = 0.03               # tighten 后向外补的余量比例


# ---------------------------------------------------------------- 基础工具

def load(path):
    return np.asarray(Image.open(path).convert("RGB")).astype(np.int16)


def save_canvas(img, path):
    img.save(path)
    return path


def estimate_bg(a):
    """取四边 2% 区域的中位数作为背景色"""
    b = max(2, int(min(a.shape[0], a.shape[1]) * 0.02))
    edge = np.concatenate([
        a[:b].reshape(-1, 3), a[-b:].reshape(-1, 3),
        a[:, :b].reshape(-1, 3), a[:, -b:].reshape(-1, 3),
    ])
    return np.median(edge, axis=0)


def mask_of(a, bg, tol=TOL):
    return np.abs(a - bg).sum(axis=2) > tol


def bbox_of(a, bg, tol=TOL, thin=THIN):
    """相对传入数组自身坐标系的主体 bbox (x0,y0,x1,y1)，无主体返回 None

    thin: 一行/一列至少要有 宽度×thin 个非背景像素才计入主体。
    调小可保住呆毛、发梢、手指等细结构（代价：噪点也可能进来）。
    """
    m = mask_of(a, bg, tol)
    thr = max(1, int(m.shape[1] * thin))
    ys = np.where(m.sum(axis=1) > thr)[0]
    xs = np.where(m.sum(axis=0) > thr)[0]
    if len(ys) == 0 or len(xs) == 0:
        return None
    return int(xs.min()), int(ys.min()), int(xs.max()) + 1, int(ys.max()) + 1


def find_gaps(a, bg, tol=TOL, min_gap_ratio=0.012):
    """列投影找「整列近似纯背景」的连续段 = 视图之间的分隔缝"""
    m = mask_of(a, bg, tol)
    col = m.sum(axis=0)
    thr = max(2, int(a.shape[0] * 0.004))
    isgap = col <= thr
    min_gap = max(6, int(a.shape[1] * min_gap_ratio))
    gaps, i, n = [], 0, len(isgap)
    while i < n:
        if isgap[i]:
            j = i
            while j + 1 < n and isgap[j + 1]:
                j += 1
            if j - i + 1 >= min_gap:
                gaps.append((i, j + 1))
            i = j + 1
        else:
            i += 1
    return gaps


def crop_916(a, bg, box, pad=PAD, tighten=True, mode="contain", margin=MARGIN):
    """按比例裁一块区域 → 可选收紧主体 bbox → 装进 9:16 画布

    box   = (上, 下, 左, 右)，比例值，相对传入数组的主体 bbox（tighten=True 时）
            或直接相对传入数组（tighten=False 时）
    mode  = contain 完整装下、四周留背景边（全身/中景；DG-019 推荐）
            cover   放大填满后居中裁切（顶格特写；DG-019 已列为高风险档，慎用）
    """
    y0f, y1f, x0f, x1f = box
    if tighten:
        bb = bbox_of(a, bg)
        if bb is None:
            raise SystemExit("未检出主体，检查背景色/阈值（--bg / --tol）")
        x0, y0, x1, y1 = bb
    else:
        y0, x0, y1, x1 = 0, 0, a.shape[0], a.shape[1]
    H, W = y1 - y0, x1 - x0
    sub = a[y0 + int(H * y0f): y0 + int(H * y1f),
            x0 + int(W * x0f): x0 + int(W * x1f)]
    if sub.size == 0:
        raise SystemExit("裁切区域为空，检查 --box 比例")

    if tighten:
        bb = bbox_of(sub, bg)
        if bb is not None:
            bx0, by0, bx1, by1 = bb
            my = int(sub.shape[0] * margin)
            mx = int(sub.shape[1] * margin)
            by0 = max(0, by0 - my); by1 = min(sub.shape[0], by1 + my)
            bx0 = max(0, bx0 - mx); bx1 = min(sub.shape[1], bx1 + mx)
            sub = sub[by0:by1, bx0:bx1]

    h, w = sub.shape[:2]
    img = Image.fromarray(sub.astype(np.uint8))

    if mode == "cover":
        scale = max(AW / w, AH / h)
        nw, nh = max(AW, int(round(w * scale))), max(AH, int(round(h * scale)))
        img = img.resize((nw, nh), Image.LANCZOS)
        left, top = (nw - AW) // 2, (nh - AH) // 2
        return img.crop((left, top, left + AW, top + AH))

    tw, th = AW * (1 - 2 * pad), AH * (1 - 2 * pad)
    scale = min(tw / w, th / h)
    nw, nh = max(1, int(round(w * scale))), max(1, int(round(h * scale)))
    img = img.resize((nw, nh), Image.LANCZOS)
    canvas = Image.new("RGB", (AW, AH), tuple(int(v) for v in bg))
    canvas.paste(img, ((AW - nw) // 2, (AH - nh) // 2))
    return canvas


# ---------------------------------------------------------------- Phase: detect

def do_detect(src, tol, min_gap_ratio, map_names):
    a = load(src)
    H, W = a.shape[:2]
    bg = estimate_bg(a)
    ob = bbox_of(a, bg, tol)
    if ob is None:
        raise SystemExit("整图未检出主体：背景色估计失败？试试 --bg R,G,B 或放大 --tol")
    x0, y0, x1, y1 = ob
    print("源图 %dx%d   背景估计 RGB=%s   整体 bbox=%s" %
          (W, H, np.round(bg, 1).tolist(), (x0, y0, x1, y1)))
    crop = a[y0:y1, x0:x1]
    gaps = find_gaps(crop, bg, tol, min_gap_ratio)
    print("检出分隔缝 %d 处: %s" % (len(gaps), [(g[0] + x0, g[1] + x0) for g in gaps]))

    regions, prev = [], 0
    for g0, g1 in gaps:
        regions.append((prev, g0))
        prev = g1
    regions.append((prev, crop.shape[1]))
    print("切格 %d 个:" % len(regions))
    for i, (s, e) in enumerate(regions):
        sub = crop[:, s:e]
        bb = bbox_of(sub, bg, tol)
        name = map_names[i] if map_names and i < len(map_names) else "view%d" % (i + 1)
        if bb is None:
            print("  [%d] %-8s 列 %4d-%4d  主体: 未检出" % (i, name, s + x0, e + x0))
        else:
            bw, bh = bb[2] - bb[0], bb[3] - bb[1]
            print("  [%d] %-8s 列 %4d-%4d  主体 %dx%d  高占比 %.2f" %
                  (i, name, s + x0, e + x0, bw, bh, bh / crop.shape[0]))
    if map_names and len(map_names) != len(regions):
        print("  注意: --map 给了 %d 个名字，实际切出 %d 格，多出的名字被忽略/缺少的用 viewN"
              % (len(map_names), len(regions)))
    return a, bg, crop, regions


# ---------------------------------------------------------------- Phase: split

def do_split(crop, bg, regions, map_names, tag, outdir, tol):
    made = []
    for i, (s, e) in enumerate(regions):
        name = map_names[i] if map_names and i < len(map_names) else "view%d" % (i + 1)
        sub = crop[:, s:e]
        bb = bbox_of(sub, bg, tol)
        if bb is None:
            print("  跳过 %s（未检出主体）" % name)
            continue
        bx0, by0, bx1, by1 = bb
        mx = int(sub.shape[1] * 0.02); my = int(sub.shape[0] * 0.02)
        bx0 = max(0, bx0 - mx); bx1 = min(sub.shape[1], bx1 + mx)
        by0 = max(0, by0 - my); by1 = min(sub.shape[0], by1 + my)
        # 纵向统一取整图高度：保证各格脚底对齐、比例一致（不各自收紧 y）
        img = Image.fromarray(crop[:, bx0 + s: bx1 + s].astype(np.uint8))
        p = os.path.join(outdir, "%s_%s.png" % (tag, name))
        img.save(p)
        print("  %-16s %dx%d" % (p, img.width, img.height))
        made.append(name)
    return made


# ---------------------------------------------------------------- Phase: anchors

COARSE = [
    # (后缀, 区域[上,下,左,右], mode, 说明)
    ("full",  (0.00, 1.00, 0.00, 1.00), "contain", "全身（起手/收尾镜通用）"),
    ("upper", (0.00, 0.62, 0.00, 1.00), "contain", "上半身近景（含完整头部，眼/嘴镜用）"),
    ("lower", (0.45, 1.00, 0.00, 1.00), "contain", "下半身中景（大腿/小腿镜用）"),
]


def anchors_path(tag, outdir):
    return os.path.join(outdir, "%s_anchors.json" % tag)


def do_anchors(crop, bg, regions, map_names, tag, outdir, anchor_src, tol):
    """按 --anchor-src 指定格生成 3 张粗锚点（随后用 --probe + --tune 细化）"""
    idx = None
    for i, nm in enumerate(map_names):
        if nm == anchor_src:
            idx = i
            break
    if idx is None:
        # 退而求其次：取主体最高（最像全身）的那一格
        best = -1
        for i, (s, e) in enumerate(regions):
            bb = bbox_of(crop[:, s:e], bg, tol)
            if bb is None:
                continue
            hgt = bb[3] - bb[1]
            if hgt > best:
                best, idx = hgt, i
        print("  未找到 --anchor-src=%s，自动改用第 %d 格（主体最高）" % (anchor_src, idx))
    if idx is None or idx >= len(regions):
        raise SystemExit("无法定位锚点来源格")

    s, e = regions[idx]
    a = crop[:, s:e]
    made = []
    for suf, box, mode, desc in COARSE:
        img = crop_916(a, bg, box, mode=mode, tighten=True)
        p = os.path.join(outdir, "%s_%s.png" % (tag, suf))
        img.save(p)
        print("  %-24s %s  (%s)" % (p, desc, mode))
        made.append(suf)

    cfg_path = anchors_path(tag, outdir)
    cfg = json.load(open(cfg_path, encoding="utf-8")) if os.path.exists(cfg_path) \
        else {"tag": tag, "src_cell": map_names[idx] if idx < len(map_names) else "view%d" % (idx + 1),
              "tuned": {}}
    cfg["src_cell"] = map_names[idx] if idx < len(map_names) else "view%d" % (idx + 1)
    json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    return made


# ---------------------------------------------------------------- Phase: probe

def do_probe(crop, bg, regions, map_names, tag, outdir, probe_from, tol, steps=16):
    """输出带纵向刻度的条带图，供视觉定位眼/嘴/胸/大腿/小腿所在比例区间"""
    idx = map_names.index(probe_from) if probe_from in map_names else None
    if idx is None:
        raise SystemExit("--from %s 不在 --map 中（当前: %s）" % (probe_from, map_names))
    s, e = regions[idx]
    a = crop[:, s:e]
    bb = bbox_of(a, bg, tol)
    x0, y0, x1, y1 = bb
    sub = a[y0:y1, x0:x1]
    h, w = sub.shape[:2]
    disp_h = 1200
    disp_w = max(1, int(w * disp_h / h))
    img = Image.fromarray(sub.astype(np.uint8)).resize((disp_w, disp_h), Image.LANCZOS)
    canvas = Image.new("RGB", (disp_w + 150, disp_h), (250, 250, 250))
    canvas.paste(img, (150, 0))
    d = ImageDraw.Draw(canvas)
    for i in range(steps + 1):
        y = int(disp_h * i / steps)
        d.line([(0, y), (disp_w + 150, y)], fill=(220, 60, 60), width=1)
        d.text((4, y + 2), "%.3f" % (i / steps), fill=(30, 30, 30))
    d.rectangle([(0, 0), (149, disp_h - 1)], outline=(120, 120, 120))
    p = os.path.join(outdir, "_probe_%s_%s.png" % (tag, probe_from))
    canvas.save(p)
    print("  探针图 %s  （纵向刻度为相对主体 bbox 的比例，用于 --tune --box 上,下,左,右）" % p)
    return p


# ---------------------------------------------------------------- Phase: tune

def do_tune(crop, bg, regions, map_names, tag, outdir, tune_name, tune_from,
            box, mode, tol, note=""):
    idx = map_names.index(tune_from) if tune_from in map_names else None
    if idx is None:
        raise SystemExit("--from %s 不在 --map 中（当前: %s）" % (tune_from, map_names))
    s, e = regions[idx]
    a = crop[:, s:e]
    img = crop_916(a, bg, box, mode=mode, tighten=True)
    p = os.path.join(outdir, "%s_%s.png" % (tag, tune_name))
    img.save(p)

    cfg_path = anchors_path(tag, outdir)
    cfg = json.load(open(cfg_path, encoding="utf-8")) if os.path.exists(cfg_path) \
        else {"tag": tag, "src_cell": tune_from, "tuned": {}}
    cfg["tuned"][tune_name] = {"from": tune_from, "box": list(box), "mode": mode,
                               "note": note, "file": os.path.basename(p)}
    json.dump(cfg, open(cfg_path, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("  %-28s %s  box=%s  mode=%s" % (p, tune_name, box, mode))
    return p


def do_tune_all(crop, bg, regions, map_names, tag, outdir, tol):
    """按 anchors.json 里已定稿的全部参数重生成（换图/改阈值后复用）"""
    cfg_path = anchors_path(tag, outdir)
    if not os.path.exists(cfg_path):
        raise SystemExit("没有 %s，先跑 --tune 定稿" % cfg_path)
    cfg = json.load(open(cfg_path, encoding="utf-8"))
    for name, item in cfg.get("tuned", {}).items():
        do_tune(crop, bg, regions, map_names, tag, outdir, name, item["from"],
                tuple(item["box"]), item.get("mode", "contain"), tol, item.get("note", ""))


# ---------------------------------------------------------------- sync

def do_sync(outdir, tag, comfy=None):
    comfy = comfy or _env.get_comfy_input()
    if not comfy or not os.path.isdir(comfy):
        print("  ComfyUI input 目录未找到（用 --comfy 指定，或跑 python _env.py --init）")
        return []
    names = [f for f in os.listdir(outdir)
             if f.startswith(tag) and f.endswith(".png") and not f.startswith("_")]
    for f in names:
        dst = os.path.join(comfy, f)
        with open(os.path.join(outdir, f), "rb") as s, open(dst, "wb") as d:
            d.write(s.read())
    print("  同步 %d 个文件 → %s" % (len(names), comfy))
    return names


# ---------------------------------------------------------------- main

def main():
    ap = argparse.ArgumentParser(description="角色四视图切分 + 9:16 锚点生成（通用版）")
    ap.add_argument("--src", help="角色设定图路径")
    ap.add_argument("--map", default="", help="从左到右每格的角度名，逗号分隔，如 bust,front,side,back")
    ap.add_argument("--tag", default="char", help="输出文件名前缀（默认 char）")
    ap.add_argument("--outdir", default=DEFAULT_OUT)
    ap.add_argument("--comfy", default=None,
                    help="ComfyUI input 目录（--sync 用；留空则自动探测）")
    ap.add_argument("--bg", default="", help="背景色 R,G,B；不给则自动估计")
    ap.add_argument("--tol", type=int, default=TOL, help="主体判定阈值（默认 60）")
    ap.add_argument("--gap", type=float, default=0.012, help="最小分隔缝宽度/图宽（默认 0.012）")
    ap.add_argument("--anchor-src", default="front", help="粗锚点取自哪一格（默认 front）")
    ap.add_argument("--probe", action="store_true", help="输出纵向条带探针图")
    ap.add_argument("--from", dest="src_from", default="front", help="probe/tune 的来源格")
    ap.add_argument("--tune", default="", help="定稿锚点名，如 eye / mouth / chest / thigh / calf")
    ap.add_argument("--box", default="", help="定稿区域 上,下,左,右（相对该格主体 bbox 的比例）")
    ap.add_argument("--mode", default="contain", choices=["contain", "cover"],
                    help="contain=完整装下留边（默认，DG-019 推荐）；cover=顶格特写（高风险）")
    ap.add_argument("--note", default="", help="定稿备注，写进 anchors.json")
    ap.add_argument("--detect", action="store_true")
    ap.add_argument("--split", action="store_true")
    ap.add_argument("--anchors", action="store_true")
    ap.add_argument("--replay", action="store_true", help="按 anchors.json 重生成全部定稿锚点")
    ap.add_argument("--sync", action="store_true")
    ap.add_argument("--all", action="store_true", help="= --split --anchors --sync")
    args = ap.parse_args()

    if args.all:
        args.split = args.anchors = args.sync = True
    if not any([args.detect, args.split, args.anchors, args.probe, args.tune,
                args.replay, args.sync]):
        args.detect = True

    map_names = [x.strip() for x in args.map.split(",") if x.strip()]
    os.makedirs(args.outdir, exist_ok=True)

    cache = os.path.join(args.outdir, ".%s_state.json" % args.tag)
    state = None
    if os.path.exists(cache):
        try:
            state = json.load(open(cache, encoding="utf-8"))
        except Exception:
            state = None

    if args.src:
        if not os.path.exists(args.src):
            raise SystemExit("源图不存在: %s" % args.src)
        if not map_names:
            print("提示: 未给 --map，格子将命名为 view1..viewN；"
                  "建议显式指定角度名（如 --map bust,front,side,back）")
        ctx = do_detect(args.src, args.tol, args.gap, map_names)
        a, bg, crop, regions = ctx
        if args.bg:
            bg = np.array([float(x) for x in args.bg.split(",")])
            print("  使用手动背景色 RGB=%s" % np.round(bg, 1).tolist())
        names = map_names or ["view%d" % (i + 1) for i in range(len(regions))]
        state = {"src": os.path.abspath(args.src), "map": names, "bg": bg.tolist(),
                 "tol": args.tol, "regions": regions,
                 "bbox": bbox_of(load(args.src), bg, args.tol)}
        json.dump(state, open(cache, "w", encoding="utf-8"))
    elif state:
        a = load(state["src"])
        bg = np.array(state["bg"])
        regions = [tuple(r) for r in state["regions"]]
        x0, y0, x1, y1 = state["bbox"]
        crop = a[y0:y1, x0:x1]
        names = state["map"]
        print("复用上次状态: %s  格数 %d  %s" % (state["src"], len(regions), names))
    else:
        raise SystemExit("首次运行必须给 --src")

    if args.split:
        print("[split]")
        do_split(crop, bg, regions, names, args.tag, args.outdir, args.tol)
    if args.anchors:
        print("[anchors]")
        do_anchors(crop, bg, regions, names, args.tag, args.outdir,
                   args.anchor_src, args.tol)
    if args.probe:
        print("[probe]")
        do_probe(crop, bg, regions, names, args.tag, args.outdir, args.src_from, args.tol)
    if args.tune:
        if not args.box:
            raise SystemExit("--tune 需要 --box 上,下,左,右")
        print("[tune]")
        box = tuple(float(x) for x in args.box.split(","))
        do_tune(crop, bg, regions, names, args.tag, args.outdir, args.tune,
                args.src_from, box, args.mode, args.tol, args.note)
    if args.replay:
        print("[replay]")
        do_tune_all(crop, bg, regions, names, args.tag, args.outdir, args.tol)
    if args.sync:
        print("[sync]")
        do_sync(args.outdir, args.tag, args.comfy)
    print("完成")


if __name__ == "__main__":
    main()
