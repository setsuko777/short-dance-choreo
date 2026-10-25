#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""环境适配层 — 消除本机硬编码路径，让 Skill 在任何人的机器上都能跑。

优先级（高 → 低）：
  1. `config.json`（`--init` 生成，已 gitignore）
  2. 环境变量：SDC_COMFYUI / SDC_FFMPEG / SDC_SITE / SDC_API
  3. 自动探测：当前解释器 → 常见安装位置 → PATH

设计原则：
  - **零第三方依赖**：只用标准库，保证 `--check` 在任何环境都能跑
  - **能用就不打扰**：当前解释器已经装了 numpy/PIL 时，绝不强插 sys.path
  - **失败给行动指引**：不抛裸 traceback，告诉你下一步该做什么

用法:
    python _env.py --check              # 体检：逐项报告是否就绪
    python _env.py --init               # 交互式生成 config.json
    python _env.py --show               # 打印当前生效的配置

脚本内调用:
    import _env
    _env.ensure_deps()                  # 需要 numpy/PIL 时先调这个
    root = _env.get_comfy_root()        # ComfyUI 根目录（可能为 None）
    inp  = _env.get_comfy_input()       #  .../input
    out  = _env.get_comfy_output()      #  .../output
    ff   = _env.get_ffmpeg()            #  ffmpeg 可执行文件路径
    api  = _env.get_api()               #  http://127.0.0.1:8188
"""
import json
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
SKILL = os.path.dirname(HERE)
CONFIG_PATH = os.path.join(SKILL, "config.json")
EXAMPLE_PATH = os.path.join(SKILL, "config.example.json")

CONFIG_KEYS = ("comfyui_root", "python_site", "ffmpeg", "api")


# ---------------------------------------------------------------- 配置读取

def load_config():
    if not os.path.exists(CONFIG_PATH):
        return {}
    try:
        with open(CONFIG_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("[警告] config.json 解析失败，忽略：%s" % e)
        return {}


def _cfg(key):
    """配置 → 环境变量 → None"""
    c = load_config()
    if c.get(key):
        return c[key]
    env_map = {"comfyui_root": "SDC_COMFYUI", "python_site": "SDC_SITE",
               "ffmpeg": "SDC_FFMPEG", "api": "SDC_API"}
    return os.environ.get(env_map.get(key, ""), "") or None


# ---------------------------------------------------------------- ComfyUI

def _looks_like_comfy(path):
    if not path or not os.path.isdir(path):
        return False
    # ComfyUI 根目录特征：有 main.py + models/ 或 input/
    has_main = os.path.exists(os.path.join(path, "main.py"))
    has_models = os.path.isdir(os.path.join(path, "models"))
    has_input = os.path.isdir(os.path.join(path, "input"))
    return has_main or (has_models and has_input) or has_input


SKIP_DIRS = {
    "windows", "program files", "program files (x86)", "programdata",
    "$recycle.bin", "system volume information", "appdata", "node_modules",
    ".git", "venv", ".venv", "env", "conda", "anaconda", "miniconda",
    "python", "python39", "python310", "python311", "python312", "python313",
    "steam", "epic games", "tencent", "wechat", "qq",
}


def _find_dir_named(root, name, max_depth=4, budget=4000):
    """在 root 下按名字找目录，带深度上限、黑名单与访问预算（避免全盘扫描卡死）"""
    hits = []
    # 盘符根（F:/、F:\）必须保留末尾分隔符，否则 os.walk 会当成
    # 「驱动器相对路径」返回 F:xxx 而不是 F:/xxx
    if not (len(root) <= 3 and root[1:2] == ":"):
        root = root.rstrip("/\\") or root
    root_len = len(root)
    visited = 0
    for dirpath, dirnames, _filenames in os.walk(root, topdown=True):
        visited += 1
        if visited > budget:
            break
        depth = dirpath[root_len:].count(os.sep) + dirpath[root_len:].count("/")
        if depth >= max_depth:
            dirnames[:] = []
        dirnames[:] = [d for d in dirnames
                       if d.lower() not in SKIP_DIRS and not d.startswith(".")]
        if os.path.basename(dirpath).lower() == name.lower():
            hits.append(dirpath)
            dirnames[:] = []
    return hits


def _candidate_comfy_roots(deep=False):
    """候选 ComfyUI 根目录。

    deep=False（默认，秒回）：只查常见安装位置。
    deep=True：逐盘符受控搜索，可能耗时数秒到数十秒，只在 --init 时用。
    """
    cands = []
    home = os.path.expanduser("~")
    for p in (home, os.path.join(home, "Documents"),
              os.path.join(home, "Desktop"),
              "C:/", "D:/", "E:/", "F:/", "G:/"):
        if os.path.isdir(p):
            cands.append(os.path.join(p, "ComfyUI"))
    if deep:
        for drive in ("D:/", "E:/", "F:/", "G:/", "C:/"):
            if not os.path.isdir(drive):
                continue
            try:
                cands.extend(_find_dir_named(drive, "ComfyUI", max_depth=4,
                                             budget=900))
            except Exception:
                pass
    seen, out = set(), []
    for c in cands:
        k = os.path.normcase(os.path.abspath(c))
        if k not in seen:
            seen.add(k)
            out.append(c)
    return out


def get_comfy_root(required=False):
    """ComfyUI 根目录。找不到时返回 None（required=True 则报错退出）"""
    p = _cfg("comfyui_root")
    if p and _looks_like_comfy(p):
        return p
    for c in _candidate_comfy_roots(deep=False):
        if _looks_like_comfy(c):
            return c
    # 常见位置没命中，做一次受控深度搜索（实测通常 <2s）
    for c in _candidate_comfy_roots(deep=True):
        if _looks_like_comfy(c):
            return c
    if required:
        sys.exit(
            "[环境] 未找到 ComfyUI。三选一：\n"
            "  1) python scripts/_env.py --init     （交互式写 config.json）\n"
            "  2) 设环境变量 SDC_COMFYUI=<ComfyUI 根目录>\n"
            "  3) 只用「只出提示词」模式，本模式下不需要 ComfyUI")
    return None


def get_comfy_input(required=False):
    r = get_comfy_root(required=required)
    return os.path.join(r, "input") if r else None


def get_comfy_output(required=False):
    r = get_comfy_root(required=required)
    return os.path.join(r, "output") if r else None


def get_api():
    return _cfg("api") or "http://127.0.0.1:8188"


# ---------------------------------------------------------------- 依赖

def _site_candidates():
    """候选 site-packages：当前解释器 → 当前解释器的 venv → WorkBuddy 内置 venv"""
    cands = []
    exe_dir = os.path.dirname(sys.executable)
    cands.append(os.path.join(exe_dir, "Lib", "site-packages"))
    cands.append(os.path.join(os.path.dirname(exe_dir), "Lib", "site-packages"))
    # WorkBuddy 内置隔离 venv（装在 ~/.workbuddy/binaries/python/envs/<name>）
    wb = os.path.join(os.path.expanduser("~"), ".workbuddy", "binaries",
                      "python", "envs")
    if os.path.isdir(wb):
        try:
            for name in sorted(os.listdir(wb)):
                sp = os.path.join(wb, name, "Lib", "site-packages")
                if os.path.isdir(sp):
                    cands.append(sp)
        except Exception:
            pass
    return cands


def ensure_deps(required=("numpy", "PIL")):
    """确保 numpy / PIL 可导入。

    当前解释器已经能 import 就直接返回（绝大多数正确配置的 Python）；
    否则把 config 里配的 site-packages 目录插入 sys.path 再试。
    """
    missing = []
    for mod in required:
        try:
            __import__(mod)
        except Exception:
            missing.append(mod)
    if not missing:
        return True

    sp = _cfg("python_site")
    if sp and os.path.isdir(sp) and sp not in sys.path:
        sys.path.insert(0, sp)
    for c in _site_candidates():
        if os.path.isdir(c) and c not in sys.path:
            sys.path.insert(0, c)

    still = []
    for mod in missing:
        try:
            __import__(mod)
        except Exception:
            still.append(mod)
    if still:
        sys.exit(
            "[环境] 缺少依赖：%s\n"
            "  解决：pip install numpy pillow\n"
            "  或用已有的 Python 环境跑；若依赖装在别处，执行\n"
            "  python scripts/_env.py --init  并填 python_site 一项"
            % ", ".join(still))
    return True


# ---------------------------------------------------------------- ffmpeg

def get_ffmpeg(required=True):
    """ffmpeg 可执行文件路径：配置 → PATH → static_ffmpeg → 常见位置"""
    p = _cfg("ffmpeg")
    if p and os.path.exists(p):
        return p
    w = shutil.which("ffmpeg")
    if w:
        return w
    # static_ffmpeg（pip install static-ffmpeg，常见于无系统 ffmpeg 的环境）
    try:
        from static_ffmpeg import run
        return run.get_or_fetch_platform_executables_else_raise()[0]
    except Exception:
        pass
    for c in _site_candidates():
        cand = os.path.join(c, "static_ffmpeg", "bin", "win32", "ffmpeg.exe")
        if os.path.exists(cand):
            return cand
    if required:
        sys.exit(
            "[环境] 未找到 ffmpeg。三选一：\n"
            "  1) 装 ffmpeg 并加入 PATH（推荐）\n"
            "  2) pip install static-ffmpeg（脚本会自动取用其二进制）\n"
            "  3) python scripts/_env.py --init 并填 ffmpeg 一项")
    return None


def get_ffprobe(required=True):
    ff = get_ffmpeg(required=required)
    if not ff:
        return None
    cand = ff.replace("ffmpeg.exe", "ffprobe.exe").replace("ffmpeg", "ffprobe")
    if os.path.exists(cand):
        return cand
    w = shutil.which("ffprobe")
    return w or ff


# ---------------------------------------------------------------- CLI

def _probe(label, fn, required=False):
    try:
        v = fn()
    except SystemExit:
        v = None
    except Exception:
        v = None
    ok = bool(v)
    flag = "OK  " if ok else ("缺失" if not required else "缺失")
    if not ok and not required:
        flag = "未配置"
    print("  [%s] %-14s %s" % (flag, label, v if ok else "—"))
    return ok


def cmd_check():
    print("环境自检 — short-dance-choreo")
    print("配置文件: %s %s" % (CONFIG_PATH,
                               "（存在）" if os.path.exists(CONFIG_PATH) else "（未创建，走自动探测）"))
    print()
    print("Python 依赖：")
    for mod in ("numpy", "PIL"):
        try:
            __import__(mod)
            print("  [OK  ] %s" % mod)
        except Exception:
            print("  [缺失] %s" % mod)
    print()
    print("外部工具：")
    _probe("ffmpeg", lambda: get_ffmpeg(required=False), required=True)
    print()
    print("ComfyUI（仅本地实跑需要，只出提示词可不配）：")
    _probe("根目录", lambda: get_comfy_root(), required=False)
    print("  API 地址: %s" % get_api())
    print()
    print("提示词模式（无 ComfyUI 也能用）只需：Python 依赖 + ffmpeg")


def cmd_init():
    print("生成 config.json（直接回车=留空，走自动探测）")
    cfg = load_config()
    roots = [c for c in _candidate_comfy_roots(deep=True) if _looks_like_comfy(c)]
    print()
    if len(roots) > 1:
        print("探测到多个 ComfyUI：")
        for i, r in enumerate(roots, 1):
            print("  %d) %s" % (i, r))
        hint = roots[0]
    elif roots:
        hint = roots[0]
    else:
        hint = ""
    print("ComfyUI 根目录" + ("（探测到：%s）" % hint if hint else "（未探测到）"))
    v = input("  > ").strip() or hint
    if v:
        cfg["comfyui_root"] = v

    print("ffmpeg 路径（留空则用 PATH 或 static-ffmpeg）")
    v = input("  > ").strip()
    if v:
        cfg["ffmpeg"] = v

    print("python site-packages（留空则用当前解释器的依赖）")
    v = input("  > ").strip()
    if v:
        cfg["python_site"] = v

    cfg.setdefault("api", "http://127.0.0.1:8188")
    json.dump(cfg, open(CONFIG_PATH, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)
    print()
    print("已写入 %s" % CONFIG_PATH)
    print("再跑一次确认：python _env.py --check")


def cmd_show():
    print(json.dumps({
        "config_path": CONFIG_PATH,
        "config": load_config(),
        "effective": {
            "comfyui_root": get_comfy_root(),
            "comfy_input": get_comfy_input(),
            "comfy_output": get_comfy_output(),
            "ffmpeg": get_ffmpeg(required=False),
            "api": get_api(),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    a = sys.argv[1] if len(sys.argv) > 1 else "--check"
    if a == "--check":
        cmd_check()
    elif a == "--init":
        cmd_init()
    elif a == "--show":
        cmd_show()
    else:
        print(__doc__)
