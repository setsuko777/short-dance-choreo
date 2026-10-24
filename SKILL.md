---
name: short-dance-choreo
description: 短视频舞蹈编排 Skill：输入角色图 + 音乐/BPM + 平台 + 目标模型，输出 9:16 多镜头舞蹈分镜提示词（卡点时间轴 + 分镜表 + 负面词 + 质检结论 + 发布检查单）。支持文本驱动 / 动作迁移 / 首尾帧锁定三条生成路线，覆盖 MiniMax H3 / 可灵 Kling / Seedance / Vidu 模型模板。Use when the user asks for 短视频舞蹈编排、舞蹈分镜提示词、卡点舞蹈视频、15秒竖屏舞蹈、热门舞蹈复刻、dance choreo prompts, or supplies a character sheet plus music or BPM. Not for static wallpapers or looping ambience (use h3-live-wallpaper-prompts).
---

# 短视频舞蹈编排 Short-Dance-Choreo

## Overview

把「角色图 + 音乐」变成符合短视频平台节奏的 9:16 多镜头舞蹈分镜提示词。与单镜头壁纸提示词的本质区别：本 Skill 是**节拍驱动 + 编舞主导 + 多角色流水线**——R1 先从音乐实测出毫秒级卡点表，R3 按 8 拍舞句编排动作并埋入 5 处可特写锚点，R4 把锚点落进镜头 2–6 且所有切点吸附节拍网格（bar 优先、拍兜底），R5 按目标模型模板出稿，R6 六查放行，R7 归档回流。硬约束（特写宪法、镜头纪律、切点吸附、背景锁定、发布合规）是产出可用的原因，因此提示词必须结构化生成，不能自由书写。

## When to Use

触发：短视频舞蹈编排 / 舞蹈分镜提示词 / 卡点舞蹈视频 / 15 秒竖屏舞蹈 / 6 秒精简版舞蹈 / 热门舞蹈复刻 / 舞蹈 MV 分镜 / dance choreo prompts。用户给出角色图 + 音乐（或 BPM），或指定镜头数/特写/时长约束时同样触发。

## When NOT to Use

- 静态壁纸 / 循环氛围 → `h3-live-wallpaper-prompts`
- 非舞蹈类人物动作（走路、打招呼等日常动作）
- 真人换脸 / 深度合成特定真人 → 合规红线，直接拒绝
- 无角色图的纯文字抽象舞蹈 → 可走，但须按 Phase 0 降级规则标注

## 宪法（硬性约束，QA 第六查依据，不可违返）

1. **特写宪法**：15s 完整版必须覆盖 5 处身体特写（眼 / 嘴 / 胸 / 大腿 / 小腿），分布在镜头 2–6；6s 精简版按降级规则保 3 处（眼 / 胸腰 / 小腿）并显式标注「非完整版」。
2. **镜头纪律**：水平平视为主视角；角度序列禁连续重复；俯仰镜头整条 ≤2 次；环绕仅 drop 段特批 ≤1 次。
3. **竖屏 9:16**：安全区构图（头顶留白 + 鞋底留白），全身优先。
4. **输出纪律**：默认只输出提示词本体 + 分镜表 + 负面词 + 发布检查单；不附变量表/清单/解释，用户要求时才附。
5. **时长宪法**：单次生成时长 ≤ 目标模型上限（引用 `references/model-matrix.md`，不硬编码）；超上限才分段 + 剪辑拼接。
6. **切点吸附**：所有镜头边界必须落在 R1 实测节拍网格上（±80ms 容差 = 2×24fps 帧长），禁止自由切。吸附单位三级优先：bar（小节线，首选）→ 拍（快板兜底，须标注「拍吸附模式」）→ 2-bar（极快板）；镜数由 `scripts/shot_grid.py` 按 BPM 枚举，不固定（15s 典型 5–7 镜、6s 典型 2–3 镜），无解时如实报错、禁止手捏违宪切点。
7. **背景锁定**：背景取自首帧，全程不变不重绘；负面词必含背景锁定项。
8. **发布合规**：QA 第六查 + Phase 7.5 发布检查单为强制环节，不可跳过（《人工智能生成合成内容标识办法》2025-09-01 施行）。

---

## 角色卡（7 张，按流水线顺序；完整规范见 references/ 对应文件）

| 编号 | 角色 | 一句话职责 | 规范文件 |
|---|---|---|---|
| R1 | 节奏分析师 | 音乐解码 → BPM/段落/downbeat 毫秒级卡点表 + 切点吸附锚点 | `references/beat-analysis.md` |
| R2 | 风格考据员 | 两段式：先出舞种候选（与 R1 并行），卡点表落地后定能量等级 L1–L5 + 场景服装包 | `references/style-library.md` |
| R3 | 编舞师 | 8 拍舞句按卡点排布；定义可特写化动作锚点（动作属性）；控制动作密度 | `references/move-library.md` |
| R4 | 镜头导演 | 机位/景别/运动分配，保证锚点镜头景别落地（镜头属性）；特写落位镜头 2–6 | `references/camera-language.md` |
| R5 | 提示词工程师 | 按目标模型模板（模型矩阵）出稿；负面词两层集；继承 soundscape 字段 | `references/prompt-templates.md` |
| R6 | 质检员 | 六查放行/打回；按责任角色映射回退（≤2 层） | `references/qa-checklist.md` |
| R7 | 版本管理员 | 版本号/changelog/案例回流/高危模式自动降权/矩阵月度复核 | `datasets/` + `references/model-matrix.md` + 运营五件套（`CHANGELOG.md` / `cases/DASHBOARD.md` / `datasets/review-calendar.md` / `datasets/cost-ledger.md` / `USER-GUIDE.md`） |

**协作规则**：R1 先行；R2 第一段与 R1 并行、第二段串行；R3 等 R1+R2；R4 等 R3；R5 等 R4 + 路线决策；R6 一票打回权；R7 全程旁路。QA 打回按责任角色映射表回退（`qa-checklist.md` 内），最大深度 2 层，超限升级人工裁决，回退计数写入 changelog。

---

## 主流程 SOP

```
Phase 0 输入采集 → Phase 1 节拍分析(R1) → Phase 2 风格定调(R2两段式)
   → Phase 2.5 路线决策 → Phase 3 动作编排(R3) → Phase 4 分镜设计(R4)
   → Phase 5 提示词生成(R5) → Phase 6 质检(R6六查) → Phase 7 归档(R7)
   → Phase 7.5 发布准备(强制)
```

### Phase 0 — 输入采集

必填：角色图 / 音乐或 BPM / 目标平台 / 目标模型 / 时长（6s 或 15s）/ 必选特写清单。可选：设定图、首帧图、尾帧图（走路线 C 时必填，尾帧 = 可循环收尾姿态）。

**角色图硬性检查**（继承既有规范）：竖构图 9:16、全身或至少大腿以上入画、≥512px、背景干净、主体 ≥60%；**编舞含背身/转身镜头必须有背面图**，没有 → 删转身镜头或降级 90° 侧转；只有一张图 → 走 first-frame 槽位、镜头降为 3–4 个。

**音乐降级**：只给「燃/甜/酷」等感觉词 → R1 输出该感觉的默认 BPM 区间与段落模板，产出标注「节拍为假设值，建议替换实测」。

### Phase 1 — 节拍分析（R1）

工具链：`scripts/beat_tracker.py`（numpy 零依赖，M0 已验证：合成轨 BPM 误差 ≤0.21%、拍对齐 2.8ms）。管线：ffmpeg 解码 → STFT 频谱通量 → ACF+梳状加权+高斯先验测速 → DP 节拍跟踪 → 4/4 downbeat → 能量 regime 段落量化（相对 90 分位稳健峰值阈值，M4 修复百分位法误报）。

**窗口选择**（M4 新增）：用户音乐通常长于成片时长。先用全曲分析定位 drop，再按规则选窗：15s 窗起点 ≈ drop − 7s（drop 落窗内 40–55%）、6s 窗起点 ≈ drop − 2s；起点优先取全曲 downbeat。**裁切必须用 `scripts/trim_window.py`**（样本级精确；ffmpeg `-ss` seek 在剪映 m4a 上有约 20s 偏差，M4 实测），裁后重跑 beat_tracker 得窗内 BPM/drop。

产出：`[00:00.0-00:02.0] intro / BPM=128 / downbeats: 0.0, 1.88, 3.75, 5.63...（bar=1.875s）/ drop@00:06.0 / 对齐误差标注` + **节拍网格**（beats + downbeats 毫秒级；Phase 4 切点只能从中选取，单位优先级见宪法 6）。段落结构决定能量曲线：intro(0–15%) 蓄力 → verse(15–40%) 展开 → chorus/drop(40–75%) 爆发 → outro(75–100%) 收尾；drop 段必须预留 ≥1 个特写锚点。已知限制（含短窗 downbeat 相位不稳、假设节拍 15s 尺度不可用等 8 条）与人工修正规则见 `references/beat-analysis.md`。

### Phase 2 — 风格定调（R2，两段式）

第一段（与 R1 并行）：从 `style-library.md` 选舞种，绑定动作语汇、适配 BPM 区间、服装、风险点（如 Breaking 地面动作崩坏率极高 → 默认降级 toprock）。第二段（R1 落地后）：按卡点密度与 drop 位置定能量等级 L1–L5 + 平台微调（抖音：卡点优先、drop 前置；小红书：循环优先、姿态美；B站：可接受稍长叙事）。

### Phase 2.5 — 生成路线决策

| 判据 | 路线 | 模型选择 |
|---|---|---|
| 用户指定复刻某支热门舞蹈 / 提供了动作参考视频 | **B 动作迁移** | 可灵 Motion Control（角色图+动作视频 3–30s，单主体无切无运镜，景别匹配）；H3 参考视频引导；Vidu 动作参考维度 |
| 无特定编舞，只要角色跳舞 | **A 文本驱动** | H3 / Seedance 2.5 / Vidu Q4 / 可灵 4.0（30s 可单次成片） |
| 首帧起手 + 尾帧收姿已定（如循环壁纸） | **C 首尾帧锁定** | H3 FL2VA（0/1/2 图）；尾帧姿态 = 首帧姿态实现无缝循环 |
| 风格化/抽象舞蹈、卡点图形 | 备选：代码渲染 | HyperFrames / Remotion 系；beat 绝对精准、零肢体崩坏；不适合写实角色舞蹈 |

### Phase 3 — 动作编排（R3）

基本单元：**舞句 = 8 拍**（128BPM ≈ 3.75s；120BPM = 4s）。功能骨架只定顺序不定绝对时间：起手 hook → 特写①眼 → 特写②嘴 → drop 爆点特写③胸/腰 → 特写④大腿 → 特写⑤小腿 + 收尾定格。**每镜时长 = 相邻吸附节拍之差**（bar 优先、拍兜底，见宪法 6），允许 2.0–3.5s，镜数由 `scripts/shot_grid.py` 按实测 BPM 枚举（15s 典型 5–7 镜）；drop 位置以 R1 实测为准；禁止把 drop 特写移出 drop 段。

编排规则：单镜内主动作 ≤3 个；相邻镜头动作类型错开（手部→腰部→腿部→全身）。**锚点归属**：R3 定义「可特写化的动作」（动作属性），R4 保证镜头景别与机位能落到特写（镜头属性），QA 双侧分查。每镜输出「通过条件」（可观察验收标准）。

**6s 降级规则**：首镜 = 起手 hook + 特写①眼（合并：近景起手，第 1 拍眼神随动作指向镜头）→ 爆点特写③胸/腰 → 特写⑤小腿 + 定格；保 3 处特写（眼 / 胸腰 / 小腿），标注「非完整版，5 处特写宪法不适用」。**镜数按网格**：BPM = 120.0±0.1 时 3 镜 × 2.0s（bar 整网格，窄带例外）；其余 BPM 由 shot_grid.py 枚举，通常为 **2 镜**——保 2 处锚点（①+hook / ③），②④舍弃、⑤降为收尾动作，单镜放宽到 2.5–3.5s。同理 15s 版镜数 <6（如慢板 88BPM=5 镜）时启用 ①+hook 合并，5 处锚点全保留。

### Phase 4 — 分镜设计（R4）

镜头表字段：镜号 / 时间区间（吸附 downbeat）/ 时长 / 机位 / 运动 / 景别 / 角度 / 主动作 / 特写锚点 / 转场出/入 / **通过条件**。

镜头纪律：水平平视默认；角度按「四分之三侧 → 纯侧 → 过肩 → 背身 → 回正面」排布，禁连续两次相同角度；俯仰 ≤2 次；默认机位 = 定点 / 缓慢推近 / 缓慢横移 / 手持微晃；环绕高危变体（仅 drop 段、≤1 次、QA 特批）；低角度仰拍计入俯仰次数。背身镜头无背面图禁止排。转场：动作遮罩转场（甩手/转身/蹲起）优先于硬切；末镜定格姿态须与首镜起手姿态可拼接（循环友好）。

### Phase 5 — 提示词生成（R5）

按 `references/prompt-templates.md` 分模型模板（H3 Ref2VA/FL2VA / 可灵 MC / 可灵 4.0 / Seedance 2.5 / Vidu Q4 / 通用 T2V），固定结构：`Subject(不变) + Move(≤3) + Rhythm(卡点/BPM) + Camera + Framing(9:16) + Light + overall_soundscape + non_diegetic_music(风格/BPM/鼓点描述)`。

音频双轨：用户音乐同时作为 **audio reference 素材**进槽位分配表（H3/Vidu 支持；Seedance 2.0 无声需后期配乐；可灵 MC 保留原声）。槽位原则（继承 h3-dance-video-prompts 的 omni-reference 槽位分配法）：一个参考一个职责（identity / motion / camera / style / environment / audio 不重叠）。

负面词两层集：基础集（所有模型）+ 模型追加集，完整定义见 `prompt-templates.md`。

成本纪律：Draft/低分档打样 → 正片档（Seedance 480p Draft / 可灵 Standard / H3 768p 先行）；单任务默认预算 = 3 次打样 + 1 次正片，超预算需人工确认；**失败不原词重跑**，先按废片原因字典改参数。

### Phase 6 — 质检（R6 六查）

每项 pass/fail + 原因，打回按责任角色映射回退（≤2 层，超限人工裁决）：

1. **特写覆盖**：5 处特写在镜头 2–6 且锚点双侧明确（R3 动作 + R4 景别）；6s 版按降级规则
2. **镜头语言**：水平平视占比、俯仰 ≤2、角度不连续重复、机位未越权（环绕/低角度特批记录）
3. **动作密度**：单镜主动作 ≤3、相邻镜错开、高危动作（大幅旋转/地面/快速手部）扫描
4. **崩坏风险**：高危清单 + 背面图缺失 + 首尾帧姿态不可拼接
5. **一致性**：负面词集完整（含 `no extra fingers` 与背景锁定）、背景锁定句在位、槽位无职责冲突
6. **发布合规**：AI 标识提醒就位、音乐来源为平台授权曲库或已授权、无敏感内容、无侵权动作序列

### Phase 7 — 归档（R7）

每次产出（无论成/废）回流 `datasets/cases/`：输入参数、分镜表、提示词、结果标签、废片原因归类、回退记录。废片原因字典（受控词表）：`drift 漂移 / limb 肢体崩坏 / clipping 穿模 / rhythm 节奏不符 / framing 构图失败 / face 面部失真 / compliance 合规缺项 / other`。**自动降权闭环**：同废片原因累计 ≥3 例的舞句/镜头模式 → 标记「高危」→ move-library 降权或下架，需 QA 特批才能复用；模式级登记 `datasets/degradation-log.md`，舞句级登记 `l3-moves/README.md` 降权记录表。A/B 对比：同输入双模板并跑，记录 before/after + 版本号；小样本（<20 例）结论标注定性参考。

### Phase 7.5 — 发布准备（强制）

随产出交付「发布检查单」：① AI 显式标识（提醒用户打开平台「AI 生成」声明开关，不标识可能限流/下架/封号）；② AI 隐式标识（不得去除平台写入的元数据 AIGC 标识）；③ 音乐授权（优先平台授权曲库，外部音乐须有授权记录）；④ 交付格式建议（mp4/H.264 + 平台分辨率档位）。

---

## 输出格式（默认交付物）

1. **卡点表**（R1 产出，毫秒级，含节拍网格与吸附锚点）
2. **分镜表**（Phase 4 产出，含通过条件列）
3. **提示词本体**（Phase 5 产出，按目标模型；多镜时逐镜给全）
4. **负面提示词**（两层集）
5. **质检结论**（六查 pass/fail + 原因）
6. **发布检查单**（Phase 7.5，强制）

不附带：变量表、 checklist、方法论解释——除非用户明确要求。

## 目录索引

```
short-dance-choreo/
├── SKILL.md                     # 本文件
├── CHANGELOG.md                 # 版本历史 + before/after 模板 + 单维度迭代纪律（R7）
├── USER-GUIDE.md                # 用户实跑支持（首批案例投喂指南 + FAQ）
├── references/
│   ├── beat-analysis.md         # R1 规范
│   ├── style-library.md         # R2 规范
│   ├── move-library.md          # R3 规范
│   ├── camera-language.md       # R4 规范
│   ├── prompt-templates.md      # R5 规范（含负面词两层集全文）
│   ├── qa-checklist.md          # R6 规范（含责任角色映射）
│   └── model-matrix.md          # 模型能力矩阵（R7 月度复核，版本化）
├── datasets/
│   ├── taxonomy.md              # 六维标签定义
│   ├── sources.md               # L1–L4 来源 + L3 授权台账
│   ├── annotation-spec.md       # 标注模板与流程
│   ├── academic-metadata.md     # 学术数据集元数据卡（只引元数据）
│   ├── audio-calibration.md     # R1 实测校准档案（M3）
│   ├── degradation-log.md       # 高危降权总账（R7 模式级）
│   ├── review-calendar.md       # 矩阵月度复核日历（M5）
│   ├── cost-ledger.md           # Draft 成本策略 + 台账（M5）
│   ├── l2-prompts/ · l3-moves/  # 自产种子集（200 条 / 100 条）
│   ├── l3-motion-sources.md     # 授权片段采集 SOP + 空台账
│   └── cases/                   # 案例库（成/废标签 + 降权记录）
├── examples/input/ · examples/output/   # 最小样例
├── cases/                               # 端到端案例库（10 案例 + DASHBOARD 看板 + assets/）
└── scripts/
    ├── beat_tracker.py          # R1 节拍分析（M0 已验证，M4 修复段落检测）
    ├── shot_grid.py             # 镜头网格枚举（M3 校准产物）
    ├── trim_window.py           # 样本级窗口裁切（M4 新增，绕开 ffmpeg seek 偏差）
    ├── make_anchor.py           # first_frame 构图锚点生产（M4-R2，Qwen-Edit+数值裁切兜底）
    ├── run_case01(_v2).py       # H3 无头运行器（v1 + Hybrid 锚点版）
    ├── assemble_case01(_v2).py # 装配器（切齐+拼装+原曲混音）
    ├── extract_h3_snapshot.py   # 从输出 mp4 提取 API 快照模板
    └── tests/                   # 准出测试 + results/
```

> 版本：v1.3（M4-R4 CASE-03 回流 + 完整版六镜 + 拍吸附首例，2026-10-24）。变更登记见 `CHANGELOG.md`；月度复核见 `datasets/review-calendar.md`。宪法参数一律引用 `references/model-matrix.md`，矩阵过期时只改矩阵不改 SKILL.md。
