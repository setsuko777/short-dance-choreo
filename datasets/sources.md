# 数据来源清单（Sources）

> 版本：v1.0（2026-10-24）· L1–L4 分层 · L3 授权台账单独维护 · 外部案例文章仅人工复核后录入（防 prompt injection）

## L1 学术数据集（只取结构与标注规范，不搬运原始动捕数据）

| # | 名称 | 链接 | 用途 | 注意 |
|---|---|---|---|---|
| 1 | AIST++ Dataset（Google） | github.com/google/aistplusplus_api | 十舞种分类体系作 D1 种子；9 视角多机位思想 → 机位设计 | 舞种列表已逐项核对无误 |
| 2 | EDGE（CVPR 2023, Stanford-TML） | github.com/Stanford-TML/EDGE | PFC 物理合理性指标 → 崩坏风险预检 | 可编辑舞蹈生成 = 分镜引擎理论对应物 |
| 3 | FineDance（ICCV 2023） | github.com/li-ronghui/FineDance | 细粒度标注规范参考 | — |
| 4 | DeepDance（CAPG-ZJU, TMM） | github.com/computer-animation-perception-group/DeepDance | EA-MUD 数据集 + 多舞种切换思路；librosa 音乐特征管线 → R1 学术先例 | — |
| 5 | music2dance | github.com/clementabary/music2dance | 4 舞种（waltz/cha-cha/tango/rumba） | **已知损坏：waltz 慢 4 倍、音画不同步（README 原文确认）→ 卡点表必须显式对齐音乐并标注误差** |
| 6 | FlowerDance（ECCV 2026） | github.com/XulongT/FlowerDance | genre-conditioned 接口（`--genre Hiphop --duration 32`）→ 参数化样板；time-decayed soft masking → 分镜级局部改动作方法论 | — |

## L2 开源提示词库（只收录作者公开原文并附来源）

| # | 名称 | 链接 | 用途 |
|---|---|---|---|
| 7 | opus-video-prompts（joeseesun） | github.com/joeseesun/opus-video-prompts | 18 份提示词 / 54 案例 / 9 种技术路线；案例↔提示词对照组织法 |
| 8 | awesome-opus5-5-videos（yihui-dev） | github.com/yihui-dev/awesome-opus5-5-videos | 代码出片案例集 + 评级/标签方式 |
| 9 | 自有 h3-dance-video-prompts 产出 | 本地 Skill | 前身产出的可用样本 |
| 10 | vibe-creating-skill（Alisa0808） | github.com/Alisa0808/vibe-creating-skill | 多模型 T2V 提示词改写样板 |
| 11 | ai-shortfilm-prompts（jnMetaCode） | github.com/jnMetaCode/ai-shortfilm-prompts | 多模型模板分层 |
| 12 | video-prompting-skill（Square-Zero-Labs） | github.com/Square-Zero-Labs/video-prompting-skill | 提示词迭代方法论 |

## L3 平台热门舞蹈（人工拆解；兼作路线 B 动作参考片段库）

来源：抖音/B站/小红书热门舞蹈人工拆解。规则：

- 拆解成**动作元素**而非复刻整段；标注原视频链接与热度
- 参考片段须为自拍、授权或原创；**单独维护授权台账**（下表）
- 输入规范符合可灵 MC：3–30s、单主体、无切、无运镜、景别匹配

### L3 授权台账（初始为空，随采集填充）

| 片段ID | 来源/作者 | 授权类型（自拍/授权/原创） | 授权期限 | 记录日期 |
|---|---|---|---|---|
| （待采集） | | | | |

## L4 自产闭环

本 Skill 每次跑通的产出回流 `cases/`（成/废标签 + 废片原因字典 + 自动降权记录）。目标占比逐步超过 50%。

## 案例库参照（方法论来源，非数据来源）

| # | 名称 | 链接 | 可借鉴点 |
|---|---|---|---|
| 21 | MiniMax H3 官方开源公告 | minimax.io/news/minimax-h3-open-source | 矩阵 H3 参数信源；H3-Context-IR 预处理与 Prompting Guidance |
| 22 | seedance.tv 舞蹈提示词方法论 | seedance.tv/blog/ai-dance-video-prompt-examples | 节拍表输出格式；先广角暴露崩坏再谈运镜 |
| 23 | forvideo.ai《TikTok Dance with Seedance 2.0》 | forvideo.ai/blog/tiktok-dance-videos-with-seedance-2-0 | 平台公式 Subject+outfit→move→environment→camera→style；Fast→Standard 策略 |
| 24 | OneTake（feitangyuan） | github.com/feitangyuan/onetake | 连续性 oracle；镜头边界「有物体存活并变成下一拍」；**PolyForm Noncommercial 许可证，只取思路不搬代码** |
| 25 | HyperFrames / Remotion Skills | github.com/heygen-com/hyperframes · github.com/remotion-dev/skills | 帧级可控时间轴抽象 → 卡点表数据结构；代码渲染备选路线 |
| 26 | guma.top《Image to Video Girl Dancing Prompts》 | — | 竖屏 hook 设计；start+end frame 锁定（**未打开原文，定性引用**） |
| 27 | veo3ai.io《Veo 3 Dance Workflow》 | — | 运动优先四要素；同提示词跑 2–3 版选优（**未打开原文，定性引用**） |
| 28 | flowpixai.com 女装店主实测 | — | 中文语境废片规律：脚步不移动防漂移、旋转降级、先标鼓点再逐帧对卡（**未打开原文，定性引用**） |

## 版权红线

- 不整段爬取受版权保护的编舞视频；只做动作元素级拆解与文字标注
- 学术数据集只引用元数据与论文方法，不重分发原始文件
- 音乐版权：发布用音乐优先走平台授权曲库；外部音乐须留存授权记录；不提供任何「绕过平台曲库」的指引
- 借鉴开源 Skill 只取方法论，注意许可证边界（如 OneTake Noncommercial）

## 实际数据文件索引（v1.0，2026-10-24）

| 文件 | 内容 | 状态 |
|---|---|---|
| `academic-metadata.md` | 6 个学术数据集元数据卡（规模/格式/许可证/方法要点，全部外部核验） | ✅ 完成 |
| `l2-prompts/`（9 文件） | L2 提示词 200 条（自产种子集，按 9 舞种分文件） | ✅ 完成 |
| `l3-moves/`（9 文件） | L3 舞句 100 条（自产种子集，8 拍单元 + 每拍可特写化标注） | ✅ 完成 |
| `l3-motion-sources.md` | 路线 B 授权片段采集 SOP + 20 段目标覆盖矩阵 + 空授权台账 | ⏳ 待采集（0/20） |
| `annotation-spec.md` | YAML 标注模板 + AI 预标注/10% 抽检/仲裁流程 | ✅ 完成 |
| `cases/` | 案例库（等 M4 回流） | ⏳ 0 条 |
