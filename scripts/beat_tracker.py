#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
beat_tracker.py — R1 节奏分析师工具链（M0 原型）
短视频舞蹈编排 Skill · numpy 零依赖节拍分析

用法:
    python beat_tracker.py <audio_file> [-o output.json] [--bpm-hint 128]

依赖:
    - numpy（venv 已有）
    - ffmpeg 二进制（复用 static_ffmpeg，见 _find_ffmpeg）
    - 无 librosa / scipy 依赖（决策 6C：numpy 保底路线）

输出 JSON:
    {
      "source": ..., "duration_s": ...,
      "bpm": 128.0, "bpm_confidence": 0.87, "bpm_alternatives": [...],
      "beats_ms": [...], "downbeats_ms": [...],
      "sections": [...], "drop_s": 6.0,
      "snap_tolerance_ms": 80, "assumed": false
    }

M0 实测记录（2026-10-24，合成 click 轨 90/120/150 BPM 真值校准）:
    - BPM 恢复误差 ≤ 0.25%
    - 检测器系统延迟 ≈ -28ms（est 早于真值），已由 DETECTOR_LATENCY_MS 补偿
      （成因：对数通量峰右偏 → 局部均值白化将峰左移；属管线群延迟，常数补偿）
    - 段落结构为启发式标签（能量 regime 量化），M0 精度要求是"合理"非"完美"
"""

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import numpy as np

SR = 22050            # 解码采样率（单声道）
FRAME = 1024          # STFT 帧长（46ms）
HOP = 256             # 帧移（11.6ms，约 86 帧/秒，保 onset 时间精度）
FPS_ENV = SR / HOP    # 包络帧率
MIN_BPM, MAX_BPM = 60.0, 200.0
SNAP_TOLERANCE_MS = 80        # 切点吸附容差 = 2 × 24fps 帧长
CHUNK_FRAMES = 8192           # STFT 分块帧数（控制内存）
DETECTOR_LATENCY_MS = 28.0    # 检测器群延迟补偿（M0 合成轨校准值）
WHITEN_WIN_S = 0.25           # 局部均值白化窗（须 < 最快拍周期/2，防隔拍干涉）


# ---------------------------------------------------------------- ffmpeg 解析

def _find_ffmpeg():
    """定位 ffmpeg 二进制：环境变量 → PATH → static_ffmpeg 已知位置。"""
    env = os.environ.get("FFMPEG_PATH")
    if env and Path(env).exists():
        return env
    w = shutil.which("ffmpeg")
    if w:
        return w
    candidates = []
    try:
        sp = Path(sys.executable).resolve().parent.parent / "Lib" / "site-packages"
        candidates.append(sp / "static_ffmpeg" / "bin" / "win32" / "ffmpeg.exe")
    except Exception:
        pass
    candidates.append(
        Path("C:/Users/Admin/.workbuddy/binaries/python/envs/default/"
             "Lib/site-packages/static_ffmpeg/bin/win32/ffmpeg.exe"))
    for c in candidates:
        if c.exists():
            return str(c)
    raise RuntimeError("未找到 ffmpeg：请设置 FFMPEG_PATH 或将其加入 PATH")


def decode_audio(path, ffmpeg):
    """解码为单声道 22050Hz float32 PCM（stdout 管道，不落临时文件）。"""
    cmd = [ffmpeg, "-v", "error", "-i", str(path),
           "-ac", "1", "-ar", str(SR), "-f", "f32le", "-"]
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if proc.returncode != 0:
        raise RuntimeError("ffmpeg 解码失败: " +
                           proc.stderr.decode("utf-8", "replace")[:500])
    x = np.frombuffer(proc.stdout, dtype=np.float32).astype(np.float64)
    if x.size == 0:
        raise RuntimeError("解码结果为空")
    return x


# ---------------------------------------------------------------- 特征提取（分块，控内存）

def _frame_view(x, start_frame, n_frames):
    """取第 start_frame 起 n_frames 帧的加窗视图（不复制大数组）。"""
    lo = start_frame * HOP
    seg = x[lo:lo + (n_frames - 1) * HOP + FRAME]
    if seg.size < FRAME:
        seg = np.pad(seg, (0, FRAME - seg.size))
    idx = np.arange(FRAME)[None, :] + HOP * np.arange(n_frames)[:, None]
    idx = np.clip(idx, 0, seg.size - FRAME)
    return seg[idx] * np.hanning(FRAME)


def extract_features(x):
    """单次分块扫描。返回:
        flux_log : log 压缩后的原始通量（供速度估计，无白化干涉）
        env      : 局部均值白化 + 归一化的 onset 包络（供节拍 DP）
        rms      : 每帧 RMS 能量（供段落 regime 量化）
    """
    n_frames_total = max(1, (len(x) - FRAME) // HOP + 1)
    flux = np.zeros(n_frames_total)
    rms = np.zeros(n_frames_total)
    prev_mag = None
    for start in range(0, n_frames_total, CHUNK_FRAMES):
        n = min(CHUNK_FRAMES, n_frames_total - start)
        frames = _frame_view(x, start, n)
        rms[start:start + n] = np.sqrt((frames ** 2).mean(axis=1))
        mag = np.abs(np.fft.rfft(frames, axis=1))
        # onset 通量：块内相邻帧差 + 与上一块末帧的跨界差
        mag_ext = (np.vstack([prev_mag[None, :], mag])
                   if prev_mag is not None else mag)
        d = np.diff(mag_ext, axis=0)
        flux_block = np.clip(d, 0, None).sum(axis=1)
        if prev_mag is not None:
            flux[start:start + len(flux_block)] = flux_block
        else:
            flux[start + 1:start + 1 + len(flux_block)] = flux_block
        prev_mag = mag[-1]
    flux_log = np.log1p(flux * 100.0)
    # 白化窗取 0.25s（86fps 下 21 帧）：短于最快拍周期的一半，
    # 避免高速段（如 150BPM=34 帧/拍）出现隔拍强弱交替导致 ACF 倍/半速误判
    w = max(3, int(WHITEN_WIN_S * FPS_ENV))
    local_mean = np.convolve(flux_log, np.ones(w) / w, mode="same")
    env = np.clip(flux_log - local_mean, 0, None)
    mx = env.max()
    if mx > 0:
        env = env / mx
    return flux_log, env, rms


# ---------------------------------------------------------------- 速度估计（自相关 + 梳状加权 + 高斯先验）

def _acf_at(ac, period):
    lo = int(np.floor(period))
    hi = min(lo + 1, len(ac) - 1)
    a = period - lo
    return ac[lo] * (1 - a) + ac[hi] * a


def estimate_tempo(flux_log):
    """60–200 BPM、0.25 步进扫描；梳状加权（period + 0.5×2period）+ 高斯先验
    （中心 120、σ 45）。不用硬性半/倍速折叠——折叠曾把 150BPM 误判成 75；
    先验只温和打破平局。输入用未白化的 log 通量（白化会在高速段造成
    隔拍强弱交替，使 ACF 偏好半速）。
    返回 (bpm, confidence, alternatives[[bpm, score], ...])。
    """
    e = flux_log - flux_log.mean()
    n = len(e)
    max_lag = min(int(2 * 60.0 / MIN_BPM * FPS_ENV) + 2, n - 1)
    lags = np.arange(max_lag + 1)
    ac = np.array([float(e[:n - l] @ e[l:]) for l in lags]) / n
    ac /= (ac[0] + 1e-12)
    scored = []
    for bpm in np.arange(MIN_BPM, MAX_BPM + 0.1, 0.25):
        period = 60.0 / bpm * FPS_ENV
        s = _acf_at(ac, period) + 0.5 * _acf_at(ac, 2 * period)
        prior = float(np.exp(-((bpm - 120.0) / 45.0) ** 2))
        scored.append((s * prior, float(bpm)))
    scored.sort(reverse=True)
    best_score, best_bpm = scored[0]
    vals = np.array([s for s, _ in scored])
    conf = float(np.clip((best_score - vals.mean()) / (vals.std() + 1e-9), 0, 1))
    alts = [[round(b, 2), round(s, 5)] for s, b in scored[:3]]
    return round(best_bpm, 2), round(conf, 3), alts


# ---------------------------------------------------------------- 节拍跟踪（DP，Ellis 式）

def track_beats(env, bpm):
    """动态规划节拍跟踪；转移仅允许间隔≈拍周期（0.75–1.3×），
    偏离惩罚 4·dev + 25·dev²（强网格锁定，防拍点漂移）。"""
    period = 60.0 / bpm * FPS_ENV
    lo = max(1, int(round(period * 0.75)))
    hi = max(lo + 1, int(round(period * 1.3)))
    n = len(env)
    NEG = -1e18
    best = np.full(n, NEG)
    back = np.zeros(n, dtype=np.int64)
    init_until = min(n, max(2, int(2 * period)))
    best[:init_until] = env[:init_until]
    for i in range(n):
        j1 = i - lo
        if j1 < 0:
            continue
        j0 = max(0, i - hi)
        seg = best[j0:j1 + 1]
        k = int(np.argmax(seg))
        j = j0 + k
        if best[j] <= NEG / 2:
            continue
        dev = abs((i - j) - period) / period
        cand = best[j] + env[i] - (4.0 * dev + 25.0 * dev * dev)
        if cand > best[i]:
            best[i] = cand
            back[i] = j
    valid = np.where(best > NEG / 2)[0]
    if valid.size == 0:  # 兜底：梳状脉冲
        step = max(1, int(round(period)))
        beats = np.arange(0, n, step)
    else:
        end = int(valid[np.argmax(best[valid])])
        chain = [end]
        while back[chain[-1]] != 0 and back[chain[-1]] != chain[-1]:
            chain.append(int(back[chain[-1]]))
        beats = np.array(sorted(chain))
    # 检测器群延迟补偿（M0 合成轨校准，见模块 docstring）
    return beats * HOP / SR + DETECTOR_LATENCY_MS / 1000.0


def find_downbeats(env, beats, bpm):
    """4/4 假设：选使 beat≡phase 上 onset 强度最大的相位。"""
    if len(beats) < 8:
        return beats.copy()
    beat_frames = np.round(beats * FPS_ENV).astype(int)
    beat_frames = beat_frames[(beat_frames >= 0) & (beat_frames < len(env))]
    if beat_frames.size < 8:
        return beats.copy()
    best_phase, best_val = 0, -1.0
    for phase in range(4):
        v = env[beat_frames[phase::4]].sum()
        if v > best_val:
            best_phase, best_val = phase, v
    return beats[best_phase::4]


# ---------------------------------------------------------------- 段落结构（启发式：能量 regime 量化）

def _smooth(v, seconds):
    w = max(1, int(seconds * FPS_ENV))
    if w <= 1:
        return v.copy()
    return np.convolve(v, np.ones(w) / w, mode="same")


def detect_sections(env, rms, duration_s):
    """能量 regime 量化（相对稳健峰值阈值）→ 运行段（最短 8s，短段并入邻段）→ 标签。
    drop = 从低/中进入高能量段的跃变点中 onset 密度最高者。
    启发式实现，M0 精度要求"合理"：intro/drop/outro 位置大致可信，
    细粒度 verse/chorus 划分允许人工修正。

    M4 勘误（2026-10-24）：原实现用 35/65 百分位量化，在「高能平台占全曲
    多数」的曲目上系统性失效——两个百分位都落进平台内部，按平台自身起伏
    乱切（实测 Ukulele 真 drop@20s 被报成 47.16s；Lowride 无 drop 被报
    163.63s；快闪真入口@9s 被兜底报 27.81s，三曲全误）。改为相对 90 分位
    稳健峰值的固定比例阈值：高能 = >72% 峰值，低能 = <40% 峰值。
    """
    fps = FPS_ENV
    # 短窗自适应（M4）：min_len=8s / 平滑 4s 是为整曲标定的；15s/6s 的成片
    # 窗口里段长本身就只有 3-8s，硬编码会把 intro 段吞掉、把 6s 窗合并成一段
    # 被迫走兜底。窗口 <30s 时收紧到 平滑 2s / 最短段 3s。
    if duration_s < 30.0:
        smooth_s, min_len_s = 2.0, 3.0
    else:
        smooth_s, min_len_s = 4.0, 8.0
    e = _smooth(rms, smooth_s)
    ref = float(np.percentile(e, 90)) + 1e-12   # 稳健峰值（抗单点爆响）
    hi_t, lo_t = 0.72 * ref, 0.40 * ref
    level = np.ones(len(e), dtype=int)
    level[e < lo_t] = 0
    level[e > hi_t] = 2

    min_len = int(min_len_s * fps)
    runs = []
    start = 0
    for i in range(1, len(level) + 1):
        if i == len(level) or level[i] != level[start]:
            runs.append([start, i, int(level[start])])
            start = i
    merged = []
    for r in runs:
        if merged and (r[1] - r[0]) < min_len:
            merged[-1][1] = r[1]          # 短段并入前段（前段 level 主导）
        else:
            merged.append(r)
    # 首段过短并入第二段：仅整曲模式。短窗（<30s）里 intro 段本身就是
    # 2-4s 的蓄力段，吞掉它就抹掉了 drop 前的低→高跃变，整窗退化成单一
    # 高能段被迫走兜底（M4 实测：6s 窗 intro 2.04s 被吞 → drop 误报 0.99s）。
    if (duration_s >= 30.0 and len(merged) >= 2
            and (merged[0][1] - merged[0][0]) < min_len):
        merged[1][0] = merged[0][0]       # 首段过短则并入第二段
        merged.pop(0)

    onset_d = _smooth(env, 2.0)
    drop_cands = []
    for k in range(1, len(merged)):
        if merged[k][2] == 2 and merged[k - 1][2] <= 1:
            t = merged[k][0] / fps
            d = float(onset_d[merged[k][0]:merged[k][1]].mean())
            drop_cands.append((d, t))
    drop_s = None
    fallback_drop = False
    if drop_cands:
        drop_cands.sort(reverse=True)
        drop_s = round(drop_cands[0][1], 2)
    elif len(e) > int(5.0 * fps):
        # 兜底：全程高能（无低→高跃变，如 30s 快闪）→ onset 密度在 15% 后的最大点
        start_f = int(0.15 * len(e))
        seg = onset_d[start_f:]
        if seg.size:
            drop_frame = start_f + int(np.argmax(seg))
            drop_s = round(drop_frame / fps, 2)
            fallback_drop = True
            # 把 drop 所在运行段一分为二，使段落标签与 drop_s 一致
            for k, (a, b, lv) in enumerate(merged):
                if a <= drop_frame < b:
                    merged[k] = [a, drop_frame, lv]
                    merged.insert(k + 1, [drop_frame, b, lv])
                    break

    n = len(merged)
    sections = []
    for k, (a, b, lv) in enumerate(merged):
        t0, t1 = a / fps, min(b / fps, duration_s)
        if n == 1:
            label = "verse"
        elif k == 0:
            label = "intro" if lv <= 1 else "chorus"
        elif drop_s is not None and abs(t0 - drop_s) < 4.0:
            label = "drop"
        elif lv == 2:
            label = "chorus"
        elif k == n - 1 and lv <= 1:
            label = "outro"
        else:
            label = "verse"
        sections.append({"start_s": round(t0, 2), "end_s": round(t1, 2),
                         "label": label, "level": lv})
    # 相邻同标签合并（level 0/1 都映射 verse，不合并会产生连续 verse 碎裂）
    coalesced = []
    for s in sections:
        if coalesced and coalesced[-1]["label"] == s["label"]:
            coalesced[-1]["end_s"] = s["end_s"]
            coalesced[-1]["level"] = max(coalesced[-1]["level"], s["level"])
        else:
            coalesced.append(dict(s))
    return coalesced, drop_s


# ---------------------------------------------------------------- 主流程

def analyze(path, bpm_hint=None):
    ffmpeg = _find_ffmpeg()
    x = decode_audio(path, ffmpeg)
    duration_s = len(x) / SR
    flux_log, env, rms = extract_features(x)
    bpm, conf, alts = estimate_tempo(flux_log)
    if bpm_hint:  # 用户提示只做微调（±3 BPM 吸附）
        bpm = round(min(max(bpm, bpm_hint - 3), bpm_hint + 3), 2)
    beats = track_beats(env, bpm)
    downbeats = find_downbeats(env, beats, bpm)
    sections, drop_s = detect_sections(env, rms, duration_s)
    # 自洽校验：DP 拍间距中位数 vs 估计周期
    if len(beats) > 4:
        bpm_dp = round(60.0 / float(np.median(np.diff(beats))), 2)
    else:
        bpm_dp = bpm
    return {
        "source": str(path),
        "duration_s": round(duration_s, 2),
        "bpm": bpm,
        "bpm_dp_check": bpm_dp,
        "bpm_confidence": conf,
        "bpm_alternatives": alts,
        "beat_period_s": round(60.0 / bpm, 4),
        "beats_ms": [round(t * 1000, 1) for t in beats],
        "downbeats_ms": [round(t * 1000, 1) for t in downbeats],
        "sections": sections,
        "drop_s": drop_s,
        "snap_tolerance_ms": SNAP_TOLERANCE_MS,
        "assumed": bpm_hint is not None,
        "detector_latency_comp_ms": DETECTOR_LATENCY_MS,
        "method": ("numpy-stft-flux + acf-comb-tempo(prior) + dp-beats + "
                   "4/4-downbeat + energy-regime-sections"),
    }


def main():
    ap = argparse.ArgumentParser(description="R1 节拍分析（numpy 零依赖）")
    ap.add_argument("audio")
    ap.add_argument("-o", "--output", default=None)
    ap.add_argument("--bpm-hint", type=float, default=None)
    args = ap.parse_args()
    try:
        r = analyze(args.audio, args.bpm_hint)
    except Exception as e:
        print(json.dumps({"error": str(e)}, ensure_ascii=False))
        sys.exit(1)
    if args.output:
        Path(args.output).write_text(
            json.dumps(r, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({
        "source": Path(r["source"]).name,
        "duration_s": r["duration_s"],
        "bpm": r["bpm"],
        "bpm_dp_check": r["bpm_dp_check"],
        "bpm_confidence": r["bpm_confidence"],
        "bpm_alternatives": r["bpm_alternatives"],
        "n_beats": len(r["beats_ms"]),
        "n_downbeats": len(r["downbeats_ms"]),
        "drop_s": r["drop_s"],
        "sections": [(s["label"], s["start_s"], s["end_s"]) for s in r["sections"]],
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
