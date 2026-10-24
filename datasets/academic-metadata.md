# 学术数据集元数据卡（Academic Metadata）

> 版本：v1.0（2026-10-24 外部核验）· 纪律：**只引用元数据、论文方法与标注规范，不下载、不重分发任何原始数据**；引用时附来源链接；各仓库许可证不同，商用前逐个人工确认

## 总览

| # | 数据集 | 论文/出处 | 规模 | 格式 | 许可证（核验日 2026-10-24） |
|---|---|---|---|---|---|
| 1 | AIST++ | AIST Dance Video Database（Google） | 十舞种 × 多机位舞蹈视频 + 动捕标注（下载需签 SMPL 协议） | 2D/3D keypoints、SMPL 关节旋转 + root trajectory | Apache License（LICENSE 文件原文确认） |
| 2 | EDGE | CVPR 2023（Stanford-TML） | 在 AIST++ 上训练 | SMPL 序列（.pkl），FBX 可渲染 | MIT License |
| 3 | FineDance | ICCV 2023 | 公开部分 **7.7 小时** | SMPLH 动作 + music_wav + music_npy（librosa 特征，特征提取法跟随 AIST++） | **自定义条款**（LICENSE 为 terms & conditions 协议，非标准 OSS 许可，使用即同意） |
| 4 | DeepDance（EA-MUD） | IEEE TMM（浙大 CAPG） | 多舞种（模型按 genre 切换） | 3D 动捕序列 | **GPL v3.0**（README 明示） |
| 5 | music2dance | Music-oriented human motion generation with GANs | **约 90 分钟**，4 舞种（waltz / cha-cha / tango / rumba） | 3D 动捕 stick frames；训练序列 4.8s = 120 帧 | 仓库无 LICENSE 文件 → **默认保留所有权利**，仅作方法参考 |
| 6 | FlowerDance | **ECCV 2026**（已接收） | genre-conditioned 生成（checkpoint 在 HuggingFace: xlt99/FlowerDance） | 3D 动作序列 | 仓库无 LICENSE 文件 → 仅作方法参考 |

## 逐卡详情

### 1. AIST++（google/aistplusplus_api）

- **链接**：github.com/google/aistplusplus_api
- **十舞种**（D1 标签库种子，已逐项核对）：Break / Pop / Lock / Waack / Middle Hip-hop / LA-style / House / Krump / Street Jazz / Ballet Jazz
- **多机位思想**：同一编舞多视角拍摄 → 本 Skill 机位设计的理论对应物（一个动作从多角度理解 → 分镜可行性预判）
- **标注体系**：2D/3D keypoints + SMPL 关节旋转 + root trajectory；可视化需 SMPL 模型（下载需单独协议）
- **在本 Skill 的用途**：D1 舞种分类体系种子；多机位→机位设计；特征提取法被 FineDance 沿用（music_npy）
- **边界**：不下载原始动捕/视频；引用其分类命名时附链接

### 2. EDGE（Stanford-TML/EDGE）

- **链接**：github.com/Stanford-TML/EDGE
- **论文**：EDGE: Editable Dance Generation From Music（CVPR 2023）
- **方法要点**：transformer-based diffusion + Jukebox 音乐特征；支持 joint-wise conditioning 与 in-betweening → **「分镜级局部改动作」的理论对应物**（ FlowerDance 的 soft masking 同思路）
- **PFC 指标**：physical foot contact 物理合理性指标 → 本 Skill「崩坏风险预检」的学术先例（脚步滑动检测）
- **许可证 MIT**：代码可借鉴（注意：我们只借鉴思路，不搬运代码进 Skill）
- **用途**：崩坏预检指标设计；局部编辑方法论

### 3. FineDance（li-ronghui/FineDance）

- **链接**：github.com/li-ronghui/FineDance
- **论文**：FineDance: A Fine-grained Choreography Dataset（ICCV 2023），arXiv 2212.03741
- **规模**：公开部分 7.7 小时；`label_json` 含 song name / coarse style / **fine-grained genre**（细粒度舞种标注）
- **数据切分**：FineDance@Genre（测试集覆盖更广舞种）与 FineDance@Dancer（按舞者切分）两种
- **用途**：细粒度标注规范参考（我们的 D1–D6 六维标签 + 每拍标注与之同构）；Genre/Dancer 切分思想 → 我们 M4 端到端测试集的切分纪律（同 BPM 不同舞者才算独立样本）
- **注意**：许可证为自定义条款，**商用需人工阅读原文确认**

### 4. DeepDance / EA-MUD（computer-animation-perception-group/DeepDance）

- **链接**：github.com/computer-animation-perception-group/DeepDance（训练代码在 DeepDance_train 子仓）
- **论文**：DeepDance: Music-to-Dance Motion Choreography with Adversarial Learning（IEEE TMM）
- **数据集**：EA-MUD；预训练模型按多舞种（GoogleDrive 分发）
- **音乐特征**：librosa 低层特征提取（`music_feature_extract.py`）→ **R1 工具链的学术先例**（我们用 numpy 自实现同源思路）
- **许可证 GPL v3.0**：借鉴注意 Copyleft 边界——本 Skill 只记录「librosa 特征管线」这一方法论，不复制其代码
- **用途**：R1 特征管线设计参考；多舞种模型切换思想

### 5. music2dance（clementabary/music2dance）

- **链接**：github.com/clementabary/music2dance
- **规模**：约 90 分钟；4 舞种：waltz / cha-cha / tango / rumba；数据源自 Music-to-dance-motion-synthesis 数据集仓
- **⚠️ 已知数据缺陷（README 原文印证）**：**waltz 慢 4 倍、音画不同步** → 直接印证本 Skill 的硬规则：**卡点表必须显式对齐音乐并标注误差**，不能假设数据集自带同步
- **训练序列**：4.8s（120 skeleton frames @25fps）
- **许可证**：无 → 仅作方法参考，不搬运
- **用途**：卡点表误差标注纪律的反面案例；GAN 序列建模思路

### 6. FlowerDance（XulongT/FlowerDance）

- **链接**：github.com/XulongT/FlowerDance · 项目页 sun-happy-ykx.github.io/FlowerDance · checkpoint: huggingface.co/xlt99/FlowerDance
- **论文**：FlowerDance: MeanFlow for Efficient and Refined 3D Dance Generation（**ECCV 2026 已接收**）
- **方法要点**：MeanFlow + Physical Consistency Constraints（少步采样）；非自回归 BiMamba 主干 + Channel-Level Fusion；**time-decayed soft masking 交互式动作编辑**
- **接口**：`python inference.py path/to/music.wav --genre Hiphop --duration 32`；`--list-genres` 列出全部支持舞种
- **用途**：① genre-conditioned 参数化接口 → 我们的舞种→模板参数化样板；② time-decayed soft masking → R3 局部改动作的方法论（改哪几拍不动其他）
- **许可证**：无 → 仅作方法参考

## 引用纪律

1. 元数据卡只记录「公开可查的事实」（规模/格式/许可/方法要点），全部附链接
2. 不下载、不重分发任何原始动捕/视频/音频数据
3. 许可证四类状态要分清：标准 OSS（MIT/Apache/GPL）→ 可借鉴代码思路；自定义条款（FineDance）→ 商用前人工读原文；无 LICENSE（music2dance/FlowerDance）→ 只作方法参考
4. 每条元数据的核验日期标在表头；论文版本以官方 arXiv/project page 为准
