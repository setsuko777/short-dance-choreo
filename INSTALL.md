# 安装这个技能（这一段是给 AI 看的）

> 用户把本技能包交给你（AI / Codex / Claude Code / WorkBuddy 等）时，请按本文件完成安装。
> 人类用户只需说一句：「按这个包里的 INSTALL.md，帮我把技能装上」。

## 你要做的事

把本目录下的 `short-dance-choreo` 文件夹，安装到**当前客户端的用户级技能目录**。

### 第 1 步：找到用户级技能目录

按以下顺序探测，命中即用：

1. 环境变量：`SKILLS_DIR`、`CODEX_SKILLS_DIR`、`CODEX_HOME/skills`、`CLAUDE_SKILLS_DIR`
2. 常见用户级路径（Windows 用 `%USERPROFILE%`，macOS/Linux 用 `~`）：
   - `~/.workbuddy/skills/`
   - `~/.claude/skills/`
   - `~/.codex/skills/`
   - `~/.config/codex/skills/`
   - `~/.cursor/skills/`
3. 若都不存在，在用户主目录下搜索名为 `skills` 的目录，
   **或直接用当前客户端已有的其它技能所在目录**（与它们并列即可）。
4. 仍找不到就问用户，不要瞎猜。

### 第 2 步：复制

把 `short-dance-choreo` **整个文件夹**复制进去，结果必须是：

```
<skills_dir>/short-dance-choreo/SKILL.md
```

`SKILL.md` 必须在二级目录里，不能把内容平铺到 `skills/` 根下。

### 第 3 步：验证并回报

确认 `<skills_dir>/short-dance-choreo/SKILL.md` 存在，然后告诉用户：
- 安装位置
- 下次怎么用（见下）

## 不要做的事

- **不要**改技能包内的文件名与目录结构（技能靠目录名被识别）
- **不要**在安装阶段执行 `scripts/` 下的任何脚本——那些是使用时才跑的
- **不要**把任何本机绝对路径写进技能文件（路径由 `scripts/_env.py` 在运行时自动探测）
- **不要**为了「让它能跑」去修改 SKILL.md 或宪法条目

## 装好之后怎么用

用户只要说一句话，例如：

> 「用这张角色图 + 这首音乐，出一个 15 秒竖屏舞蹈分镜，平台抖音」

技能会自动交付：卡点表 / 分镜表 / 提示词 / 负面词 / 质检结论 / 发布检查单。

如果用户要**直接生成视频**（而不是只要提示词），需要本机有 ComfyUI + MiniMax H3，
那时才需要跑一次环境自检：

```bash
cd <skills_dir>/short-dance-choreo/scripts
python _env.py --check
```

只想要提示词的话，**什么都不用装**，这一步可以完全跳过。
