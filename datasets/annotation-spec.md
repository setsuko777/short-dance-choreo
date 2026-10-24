# 标注规范（Annotation Spec）

> 版本：v1.0（2026-10-24）· AI 预标注 + 人工 10% 抽检 + 争议仲裁（替代不可行的双人交叉标注）

## 标注模板（每条样本一个 YAML）

```yaml
id: "case-2026-0001"
source: "自产 / L2-opus-video-prompts / L3-抖音@xxx"
created_at: "2026-10-24"
# 六维标签（datasets/taxonomy.md，缺一不收）
d1_dance: "K-pop"
d2_energy: "L4"
d3_bpm_band: "120-140"
d4_camera: ["定点", "缓慢推近"]
d5_framing_closeups: ["眼", "嘴", "胸", "大腿", "小腿"]   # 特写五件套硬性字段；6s 版标"降级"
d6_scene_outfit: ["室内自然光", "舞台服"]
# 动作分解（8 拍单元，每拍可特写化标注 + 通过条件）
moves:
  - beat: 1
    action: "起手定点，静态"
    body: "全身"
    closeup_able: false
    pass_condition: "全身及脚部接触地面始终可见"
  - beat: 3
    action: "眼神指向镜头 + 手部上抬"
    body: "眼/手"
    closeup_able: true
    closeup_type: "眼"
    pass_condition: "面部清晰可辨，无手部遮挡"
# 卡点时间轴（毫秒级）+ 吸附锚点
beats_ms: [0, 469, 938, 1407, 1875, 2344, 2813, 3281]
downbeats_ms: [0, 1875, 3750]
alignment_error_ms: 2.8
# 镜头（与 R4 分镜表对齐）
camera:
  - shot: 1
    time_ms: [0, 1875]
    angle: "四分之三侧"
    move: "定点"
# 路线与结果
route: "A"                    # A 文本驱动 / B 动作迁移 / C 首尾帧锁定
result: "成"                  # 成 / 废
fail_reason: null             # 废片原因字典受控词表
prompt_snapshot: "..."        # 投喂模型的提示词原文
```

## 废片原因字典（受控词表）

`drift 漂移` · `limb 肢体崩坏` · `clipping 穿模` · `rhythm 节奏不符` · `framing 构图失败` · `face 面部失真` · `compliance 合规缺项` · `other`

## 标注流程

```
R1–R5 流水线 AI 预标注（全量自动）
   → 人工抽检 10%（随机 + 高危样本必抽）
   → 一致率 ≥80%：样本入库
   → 一致率 <80%：触发标注规范修订（规范版本化），争议样本交编舞师角色终审仲裁
```

## 降权记录（R7 维护）

同废片原因累计 ≥3 例的舞句/镜头模式 → 标「高危」→ move-library 降权或下架，复用需 QA 特批。记录格式：`对象ID / 废片原因 / 累计例数 / 降权日期 / 解禁条件`。

## 案例库（cases/）

每次产出（无论成/废）回流：`cases/YYYY-MM/<case-id>.yaml`（按上模板）。索引与统计由 R7 在归档时更新 `cases/README.md`。
