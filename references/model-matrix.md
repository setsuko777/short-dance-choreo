# 模型能力矩阵（Model Matrix）

> 版本：v1.0（2026-10-24 外部核验版）· R7 月度复核对象 · SKILL.md 宪法的一切时长/槽位参数**引用本表，不硬编码**
> 复核纪律：表头标注核验日期；模型 Landscape 3–6 个月一变；新模型发布走变更评审后再入表

## 矩阵

| 模型 | 单次时长 | 参考输入 | 音频能力 | 运动控制 | 分辨率/帧率 | 计费口径 |
|---|---|---|---|---|---|---|
| **MiniMax H3**（已开源） | 4–15s（整数秒） | Ref2VA：≤9 图 + ≤3 视频（各 2–15s、总 ≤15s）+ ≤3 音频（各 2–15s、总 ≤15s），混合 ≤12 个；FL2VA：0/1/2 图 | 输出原生 32kHz 立体声；音频参考须配图或视频 | 参考视频可引导动作（V2V motion transfer 为核心能力） | 768p 默认 / 2K（Regenerate-2K）；24fps | 按时长 + 参考素材计费 |
| **可灵 Motion Control**（VIDEO 3.0，2026-03 发布） | 跟随参考视频 3–30s（Match Video）/ ≤10s（Match Image） | 1 角色图 + 1 动作视频（单主体、无切无运镜；短边 ≥340px、长边 ≤3850px） | 保留原声，不生成新音频 | **专职动作迁移**；V3 支持面部元素绑定（1 正面 + ≤3 角度，仅 Match Video） | 720p/1080p | 按参考视频秒数计费（V3 Pro ≈ $0.168/s） |
| **可灵 4.0**（2026-10 发布） | 单次原生 30s，续拍可延至 2min | 全能参考：≤15 项素材（图/视频/主体/音色）；≤10 张关键帧 | — | 高速运动/连续动作/跟拍环绕稳定性增强 | 1080p | 按秒计费 |
| **Seedance 2.5**（4K 版 2026-10-23，定向邀请） | 单次 30s | 多模态参考，须做**角色分工**（identity/motion/camera/style/environment/audio 各司其职） | 原生音视频联合生成 | 提示词驱动 | 480p Draft / 1080p / 4K | Draft 480p 低价打样 → 正片高价 |
| **Vidu Q4 Preview**（2026-10-08） | 3–16s | 参考生视频：≤15 参考图 + ≤3 参考音频；主体库 | 音频参考复刻音色；Q3 起支持 16s 原生音视频直出、唇形同步 ±15ms | 动作参考为六大参考维度之一（Q2 起） | 2K/4K | 按次/时长 |
| （备选范式）**代码渲染**：HyperFrames（heygen-com）/ remotion-dev/skills / onetake | 任意 | HTML Canvas / p5.js / Three.js / Remotion / Manim 逐帧渲染 | Web Audio / Python 合成 | 代码定义，beat 绝对精准、零肢体崩坏 | 任意 | 本地渲染 |

## 使用规则

1. 宪法中的一切时长/槽位参数引用本表；SKILL.md 与 references/ 中出现具体秒数/槽位数时必须能回溯到本表某一行
2. 「Seedance」单独出现时一律带版本号（2.0 无声 / 2.5 有原生音频，代差明显）
3. 备选范式（代码渲染）只在风格化/抽象舞蹈、循环壁纸类需求走 Phase 2.5 分流，不作为主线
4. **月度复核**（R7）：核验日期 + 版本号 + 变更记录；发现参数变化先改本表，再评估是否触发宪法修订

## 复核记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-10-24 | v1.0 | 初版；H3 开源版 / 可灵 MC V3 / 可灵 4.0 / Seedance 2.5 / Vidu Q4 Preview 五家参数经外部信源核验 |

## 信源

- MiniMax H3 官方开源公告：minimax.io/news/minimax-h3-open-source
- 可灵 Motion Control VIDEO 3.0 / 可灵 4.0 官方发布说明
- Seedance 2.5（火山引擎）官方说明
- Vidu Q4 Preview（生数科技）官方说明
- 代码渲染范式：github.com/heygen-com/hyperframes · github.com/remotion-dev/skills · github.com/feitangyuan/onetake
