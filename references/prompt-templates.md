# R5 提示词工程师 — Prompt Templates 规范

> 版本：v1.0（2026-10-24）· 对应 SKILL.md Phase 5 · 模型参数一律引用 `model-matrix.md`，不硬编码

## 职责

把 R4 的分镜表转成**可直接投喂目标视频模型的提示词本体**，配槽位分配表 + 两层负面词。输出只给提示词本体（SKILL.md 输出纪律）。

## 通用结构（所有模型通用的字段体系，继承 h3-prompt-writing）

```
Subject(不变) + Move(≤3) + Rhythm(卡点/BPM) + Camera + Framing(9:16) + Light
  + overall_soundscape + non_diegetic_music(风格/BPM/鼓点描述)
```

多镜生成时**逐镜给全**（每镜一条完整提示词），不合并成一段。

## 槽位分配表（一个参考一个职责）

| 素材 | 职责标签 | 说明 |
|---|---|---|
| 角色设定图 / 三视图 | identity | 跨镜外观零漂移 |
| 首帧图 | opening | 起手姿态 + 背景（背景锁定来源） |
| 尾帧图 | ending | 收姿（路线 C 必填） |
| 动作参考视频 | motion | 路线 B 复刻编舞 |
| 用户音乐 | audio | audio reference（H3/Vidu）；可灵 MC 保留原声；Seedance 2.0 无声 |
| 风格参考 | style | 一个参考只担一个职责，不重叠 |

---

## 模型模板

### 1. MiniMax H3（Ref2VA / FL2VA）

- 槽位：≤9 图 + ≤3 视频（各 2–15s、总 ≤15s）+ ≤3 音频（各 2–15s、总 ≤15s），混合 ≤12；FL2VA 走 0/1/2 图
- 时长 4–15s 整数秒；输出原生 32kHz 立体声
- 提示词用中文本体；音频参考须配图或视频
- 追加负面词：中文锁定句「所有镜头中外观零漂移。背景全程保持首帧中的【底色与图案】，完全不变、不重绘。」
- 官方 prompting guidance 以 minimax.io 开源公告为准（信源见 `datasets/sources.md` #21）

### 2. 可灵 Motion Control（路线 B 主力）

- 输入：1 角色图 + 1 动作视频（Match Video 3–30s / Match Image ≤10s；单主体、无切无运镜；短边 ≥340px、长边 ≤3850px）
- 景别匹配：全身动作参考 → 全身角色图
- V3 面部绑定：1 正面 + ≤3 角度（仅 Match Video）
- 保留原声，不生成新音频；720p/1080p
- 追加负面词：面部绑定说明（Match Video 模式挂面部元素）

### 3. 可灵 4.0

- 单次原生 30s（续拍延至 2min）；全能参考 ≤15 项素材 + ≤10 张关键帧；1080p

### 4. Seedance 2.5

- 单次 30s；多模态参考须做**角色分工**（identity/motion/camera/style/environment/audio 各司其职）
- 原生音视频联合生成；480p Draft 打样 → 1080p/4K 正片
- **Seedance 2.0 无声**：涉及 Seedance 一律带版本号；2.0 需后期配乐
- 单镜需求追加 `no shot change`

### 5. Vidu Q4

- 3–16s；参考生视频 ≤15 参考图 + ≤3 参考音频；主体库
- 音频参考复刻音色；唇形同步 ±15ms
- 追加负面词：`no third person, no role swapping`

### 6. 通用 T2V（兜底）

纯文字描述动作；无参考槽位；背景一致性最弱 → 优先引导用户走带参考槽位的模型。

---

## 单次直出模板（One-shot，Phase 2.6 模式 B）

逐镜拼接是「一条提示词 = 一镜」；直出是「一条提示词 = 整条片」。
差别不在字段多少，而在**时间锚点必须写死**——模型执行的是一段连续时序，任何「随后 / 接着 / 然后」都会让它自由发挥。

### 结构（按顺序拼，不分段换行成列表）

```
[Subject 不变外观]
[Move 段落1: from 0.0s to X.Xs ...]
[Move 段落2: from X.Xs to Y.Ys ...]
[Move 段落3: at Y.Ys the drop ... / from Y.Ys to Z.Zs ...]
[Move 段落4: from Z.Zs to 15.0s ... hold a completely still pose for the final beat]
[Camera: 连续运镜脚本，变化 ≤3 次，写死变化时间点]
[Framing 9:16 + Light]
[背景锁定句 + 外观锁定句（前置到紧跟 Subject）]
[overall_soundscape + non_diegetic_music]
```

### 五条硬规则

1. **时间锚点用绝对秒数**，取自 R1 实测卡点表（段落边界 + drop）。不写相对词。
   ```
   from 0.0s to 2.4s: ...; from 2.4s to 4.8s: ...; at 4.8s (the drop): ...; from 10.0s to 15.0s: ...
   ```
2. **机位变化 ≤3 次**且写死变化时间点：`the camera holds static, then slowly pushes in from 4.8s to 7.0s, then holds`。
   直出模式默认「全程定点 + 一次极缓推近」——非默认景别在长时序里守不住（DG-019），且没有分镜兜底。
3. **锁定句前置**：背景锁定 + 外观零漂移紧跟 Subject，不要放在末尾。长生成后半段是高漂移区（DG-015）。
4. **结尾定格句不可省**：`hold a completely still pose for the final beat`。
   逐镜模式有装配 trim 兜底，直出没有（DG-018）。
5. **主动作总数 ≤8**，按段落分配（起手 1–2 / 展开 2–3 / 爆点 1–2 / 收尾 1）。
   同一条提示词里塞太多动作，模型会丢后半段。

### 各模型直出适配

| 模型 | 单次上限 | 直出注意 |
|---|---|---|
| 可灵 4.0 | 30s | 15s 直出的首选；{首/尾}帧关键帧可用于钉住起手与收姿 |
| Seedance 2.5 | 30s | 原生音视频联合生成；2.0 无声需后期配乐；480p Draft 打样 |
| Vidu Q4 | 16s | 15s 可行；多参考图分工 |
| MiniMax H3 | 15s 整数秒 | **直出上限恰好 15s**；单条长生成的景别保持是弱项（DG-019），但**不设 first_frame 走 Ref2VA 反而很稳**（CASE-2026-1025-02 实证）。本地跑须过显存预算（`model-matrix.md`）：16GB 卡上 362 帧必须跳过 1.5x latent upscale |
| 可灵 MC | 3–30s | 直出即路线 B 原生形态（动作视频本身就是连续一条） |

### 直出提示词示例骨架（占位符替换为实测值）

```
{Dsubject}。{Doutfit}。
from 0.0s to {t1}s: {hook 起手，静止或极缓，眼神看向镜头};
from {t1}s to {t2}s: {展开动作 ×2–3，手臂/肩/腰};
at {t_drop}s (the drop): {最强动作，双臂展开/转身};
from {t_drop}s to {t3}s: {延续爆点余韵，减速};
from {t3}s to {total}s: {收尾} and hold a completely still pose for the final beat.
The camera {连续运镜脚本}。{Dframing 9:16}。{Dlight}。
{背景锁定句}。{外观零漂移句}。
{overall_soundscape} {non_diegetic_music: 风格/BPM/鼓点}
```

> 直出模式的提示词**仍需走 R5 的负面词两层集**，且第 5 查（一致性）权重要提高——无分镜兜底，后半段漂移即整条报废。

---

## 负面词两层集

**基础集（所有模型通用）**：

```
distorted hands, extra fingers, extra limbs, changing face, warped body,
unstable background, background repaint, scene flicker, feet sliding out of frame,
morphing body proportions, text, watermark
```

**模型追加集**：

| 模型 | 追加 |
|---|---|
| H3 | 中文锁定句：「所有镜头中外观零漂移。背景全程保持首帧中的【底色与图案】，完全不变、不重绘。」 |
| 可灵 MC | 面部绑定说明（Match Video 模式） |
| Seedance | 单镜需求追加 `no shot change` |
| Vidu | `no third person, no role swapping` |

## 音频双轨

用户音乐 = R1 分析输入（Phase 1）+ **audio reference 生成素材**（本 Phase）。H3/Vidu 进槽位分配表；可灵 MC 保留参考视频原声；Seedance 2.0 无声 → 产出中标注「音频需后期配乐」并在发布检查单提示平台曲库。

## 打样 → 正片成本纪律

- 打样档：Seedance 480p Draft / 可灵 Standard / H3 768p / Vidu 标准档
- 正片档：Seedance 1080p–4K / 可灵 1080p / H3 2K / Vidu 2K–4K
- 单任务默认预算 = **3 次打样 + 1 次正片**，超预算需人工确认
- **失败不原词重跑**：先按废片原因字典（见 `qa-checklist.md`）定位再改参数

## 与其他角色的接口

- ← R4（分镜表）+ Phase 2.5 路线决策
- → R6（提示词 + 槽位分配表）
- QA 回退映射：提示词格式 / 负面词缺失 / 槽位职责冲突 → 回退本角色
