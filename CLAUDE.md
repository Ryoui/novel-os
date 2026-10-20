# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## 项目概述

本仓库是 **Novel OS v2.0.0**，一个中文小说全流程创作技能，核心逻辑：

- **技能定义**：`novel-os/SKILL.md`（v2.0.0 主文档，作为 Claude Code 等 AI 工具的 skill 安装使用）
- **真实执行器**：`novel-os/scripts/` 目录下的 Python 脚本，承担门禁校验、RAG 检索、联网调研、多LLM写作、流程编排等硬逻辑
- **小说项目数据**：写作时在用户机器的 `<project-root>/` 下生成（不在本仓库内）
- **人类可读说明**：`docs/README.md`（`novel-os/SKILL.md` 与它分工不同，前者给 AI，后者给人）

## 常用命令

### 运行回归测试

```bash
PYTHONDONTWRITEBYTECODE=1 python3 novel-os/scripts/test_novel_flow_executor.py
```

### 核心脚本入口

```bash
# 一键开书（初始化项目）
python3 novel-os/scripts/novel_flow_executor.py one-click \
  --project-root <项目目录> --title <书名> --genre <题材> --idea <剧情种子>

# 继续写作（两段式：CLI 备料产写作包 → Agent 写正文 → CLI 门禁/索引）
python3 novel-os/scripts/novel_flow_executor.py continue-write \
  --project-root <项目目录> --query "<新剧情>"

# 带高级参数的继续写作（回滚/幂等缓存默认开启，只能用 --no-* 关闭）
python3 novel-os/scripts/novel_flow_executor.py continue-write \
  --project-root <项目目录> --query "<新剧情>" \
  --candidate-k 12 --max-auto-retry-rounds 2 \
  --require-semantic-pacing

# 门禁检查（--require-semantic-pacing 强制要求 /节奏审查 产物）
python3 novel-os/scripts/chapter_gate_check.py \
  --project-root <项目目录> --chapter-file <章节文件> \
  --require-semantic-pacing

# 构建/查询剧情索引
python3 novel-os/scripts/plot_rag_retriever.py build --project-root <项目目录>
python3 novel-os/scripts/plot_rag_retriever.py query --project-root <项目目录> \
  --query "<新剧情>" --top-k 4 --candidate-k 12 --auto-build

# 门禁失败修复计划
python3 novel-os/scripts/gate_repair_plan.py \
  --project-root <项目目录> --chapter-file <章节文件>

# 流程基线评测
python3 novel-os/scripts/benchmark_novel_flow.py --project-root <项目目录> --rounds 5

# 联网调研（生成关键词 / 检测缺口 / 存储结果）
python3 novel-os/scripts/research_agent.py plan --genre <题材> --topic "<主题>" --project-root <目录>
python3 novel-os/scripts/research_agent.py gaps --project-root <目录> --chapter-goal "<章节目标>"
python3 novel-os/scripts/research_agent.py store --project-root <目录> --category "<类别>" --content "<内容>"

# 一键写书（全自动调度）
python3 novel-os/scripts/auto_novel_writer.py plan --synopsis "<简介>" --target-chars 2000000 --genre <题材>
python3 novel-os/scripts/auto_novel_writer.py run --project-root <目录> --synopsis "<简介>" --target-chars 2000000
python3 novel-os/scripts/auto_novel_writer.py report --project-root <目录>

# 章节写作（多LLM支持）
python3 novel-os/scripts/novel_chapter_writer.py --project-root <目录> --provider kimi --dry-run

# 跨工具安装（macOS/Linux）
bash novel-os/scripts/install-portable-skill.sh --tool claude-code --force
# 跨工具安装（Windows / PowerShell）
powershell -ExecutionPolicy Bypass -File novel-os/scripts/install-portable-skill.ps1 -Tool claude-code -Force
```

## 代码架构

### 仓库结构

```
novel-os/                    # 仓库根：只放仓库级内容，不是技能包本身
  novel-os/                  # ← 技能包（安装时整个目录复制出去）
    SKILL.md                 #   技能主文档（v2.0.0），AI 工具读取此文件执行命令
    scripts/                 #   全部执行器与测试（见下）
    references/              #   18 份设计文档（按需读取，不全量加载）
    templates/               #   小说项目初始化模板（one-click 使用其中 11 个）
    assets/style_library/    #   全局风格库（style_fingerprint.py 读写）
    agents/                  #   编辑团队四个角色定义（中性目录；claude-code 安装到 ~/.claude/agents/）
  docs/                      # 人类可读文档（不在分发包内）
    README.md
    archive/plans/           # 历史设计文档
  CLAUDE.md                  # 本文件：仓库开发指引
  .gitattributes / .gitignore
```

`novel-os/scripts/` 关键脚本（完整清单见 `novel-os/SKILL.md` §9）：

```
novel_flow_executor.py       # 主流程编排（one-click / brainstorm / revise-outline / continue-write）
plot_rag_retriever.py        # 两级 RAG 检索（粗筛+精排），零外部依赖
chapter_gate_check.py        # 门禁校验（含 body_metadata_purity 与派生发布判定）
chapter_health.py            # 单章体检 / 跨章趋势 / 本书基线偏离
beat_sheet_generator.py      # Beat Sheet 分镜与逐 Beat 扩写提示
novel_chapter_writer.py      # 多 LLM 写作引擎（批处理用，OpenAI/Claude/Kimi/GLM/MiniMax）
auto_novel_writer.py         # 一键写书调度（断点续写）
research_agent.py            # 联网调研（关键词/缺口/资料入库）
style_fingerprint.py · pacing_tracker.py · story_graph_builder.py · story_graph_updater.py
outline_anchor_manager.py · event_matrix_scheduler.py · anti_resolution_guard.py
chapter_synthesizer.py · cross_agent_reviewer.py · editorial_team_manager.py
interactive_ideation_engine.py · text_humanizer.py · gate_repair_plan.py
benchmark_novel_flow.py · test_novel_flow_executor.py · tests/
install-portable-skill.sh / .ps1   # 跨工具安装（bash / PowerShell 两版，行为一致）
common.py · config.py · performance.py · 三个内部库（无 CLI）
novel_writer_config.template.yaml
```

> **分层原则**：`novel-os/` 是可直接安装到 AI 工具的技能包，内部一律使用技能相对路径
> （`scripts/...`、`references/...`）；`docs/` 与 `CLAUDE.md` 是仓库级内容，不随技能安装，
> 因此其命令示例统一写成 `novel-os/scripts/...`。

```
### 小说项目目录结构（运行时生成）
```

<project-root>/
  00_memory/
    novel_plan.md           # 主线计划（写前必读）
    novel_state.md          # 当前状态（写前必读，Smart State 模式）
    retrieval/
      story_index.json      # 章节检索索引
      entity_chapter_map.json
      next_plot_context.md  # 当前写前上下文建议
      chapter_meta/*.meta.json  # 章节元数据侧车文件
      eval_baseline.json    # 评测基线结果
  02_knowledge_base/        # 设定与知识库（不存章节正文，不存状态追踪器）
  03_manuscript/            # 章节正文（第NNN章_*.md）
  04_editing/gate_artifacts/<chapter_id>/
    memory_update.md
    consistency_report.md
    pacing_review.md        # 节奏审查结论（节奏审查: 通过）
    style_calibration.md
    copyedit_report.md
    publish_ready.md        # 门禁派生的发布结论（每次重写）
    quality_report.md       # 段落去重指标（通过：True）
    gate_result.json        # passed=true 才能进入下一章
    repair_plan.md          # 失败时生成
  .flow/                    # 执行锁、幂等缓存、快照（内部）

```
> 状态追踪器（`character_tracker.md` / `timeline.md` / `foreshadowing_tracker.md` / `world_state.md` / `style_anchor.md`）由 `one-click` 写入 `00_memory/`，不在 `02_knowledge_base/`。

### 核心机制

**门禁流程**（每章不可跳过，`continue-write` 自动串联）：
1. `/更新记忆` → `memory_update.md`
2. `/检查一致性` → `consistency_report.md`
3. `/节奏审查` → `pacing_review.md`（须含 `节奏审查: 通过`）
4. `/风格校准` → `style_calibration.md`
5. `/校稿` → `copyedit_report.md`（发布结论由门禁派生，不在本步产生）
6. `/门禁检查` → `gate_result.json`（`passed=true` 才解锁下一章）

⚠️ `quality_report.md` 也是硬性产物，由 `continue-write` 自动写入；手动走流程时必须自行生成。完整判定规则见 `novel-os/references/gate-artifacts-spec.md`。

**两级 RAG 检索**（`plot_rag_retriever.py`）：
- 条件触发：轻场景（日常/过渡）自动跳过检索
- 占位桩过滤：建索引时跳过骨架章节（`common.is_draft_stub_text`），检索时再滤掉旧索引残留的桩文档与纯骨架片段
- 粗筛：BM25 风格 TF-IDF，取 `candidate-k`（默认 8）候选
- 精排：片段级语义重排，返回 `top-k`（默认 4）结果
- 查询缓存：相同 query 命中缓存跳过重算，可用 `--no-cache` 覆盖

**幂等与回滚**（`continue-write`）：
- 执行锁（`.flow/continue_write.lock`）防并发
- 写前快照（`.flow/snapshots/`）支持失败回滚
- 幂等缓存（`.flow/continue_write_cache.json`）命中则跳过重跑

**`novel_flow_executor.py` 输出格式**：所有子命令均输出 JSON 到 stdout，`ok: true/false` 为顶层状态字段，测试脚本依赖此格式。

**联网调研**（`research_agent.py`）：
- 通用能力，任何写作场景均可使用（手动/半自动/全自动）
- 根据题材自动生成搜索关键词（9大题材内置调研维度映射）
- 知识缺口检测：扫描已有知识库 vs 章节需求
- 资料按类别自动路由到对应知识库文件
- 适配 Claude Code / OpenCode / Codex 等多种工具

**多LLM写作引擎**（`novel_chapter_writer.py`）：
- 支持 OpenAI / Anthropic / Kimi / GLM / MiniMax / 本地模型 / 任意 OpenAI 兼容 API
- `write_chapter()` 函数可被外部脚本导入调用
- 零外部依赖（使用 urllib.request）
- 仅供 `--draft-provider llm` / `/一键写书` 这类批处理场景；装在 Claude Code 等工具里时正文由宿主 Agent 自己写，不经过本引擎

**正文所有权**：`continue-write` 默认 `--draft-provider auto` → 无外部 LLM 配置时走 `agent` 模式，**CLI 不写正文**，只产出写作包 `00_memory/next_chapter_task.md` 并返回 `awaiting_draft: true`。章节文案只能由宿主 Agent 写；`template` 段落池拼接仅供调试且必被门禁判死。

**一键写书**（`auto_novel_writer.py`）：
- 全自动调度：调研→开书→循环写作→完成报告
- 断点续写：状态持久化到 `.flow/auto_write_state.json`
- 进度报告：卷/章/字数/门禁通过率

## 技能安装说明

本仓库同时是一个 Claude Code skill。`novel-os/SKILL.md` 作为 skill 文件，安装后在对话中触发 `/一键开书`、`/继续写` 等命令。安装脚本支持 Claude Code、Codex、OpenCode、Gemini CLI、Antigravity 五个工具。
```
