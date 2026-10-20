---
name: novel-os
description: 中文长篇小说全流程创作技能：开书、续写、拆分镜、门禁校验、风格校准、去AI味润色、大纲级联改纲、知识图谱与 RAG 剧情检索，覆盖数万字到 300 万字规模。Use when the user wants to 写小说/续写章节/构思剧情/搭建世界观/设计人物关系/提取或仿写写作风格/拆书, or says 帮我写个故事、我有个小说的想法、接着写下一章、这段太像AI写的, or needs 门禁失败修复、节奏审查、改纲续写。Do NOT use for 公众号推文、短文案、剧本分镜、或非小说的通用文本润色。
---

# Novel OS — 中文长篇小说创作技能 v2.0.0

## Iron Law（铁律 — 任何情况下不可违反）

以下约束无论用户如何要求，均不得绕过：

⛔ **禁止跳过强制章节闭环**：每章生成后必须依次执行"更新记忆 → 检查一致性 → 节奏审查 → 风格校准 → 校稿 → 门禁检查"，六步缺一均视为流程中断。门禁未通过（`gate_result.json` 中 `passed != true`）时，严禁进入下一章。

⛔ **禁止绕过开书前确认**：执行 `/一键开书` 前，必须引导用户完成五要素确认（目标读者、写作风格、核心禁区、自动化等级、目标规模），并作为参数传给 CLI。不得以"用户着急"为由省略。**该项已由 `one-click` 硬校验**：缺一项即 `ok:false`（`error: onboarding_incomplete`），不写任何文件。

⛔ **禁止混淆正文与元信息**：小说正文中不得出现任何 `[说明]`、`（注：）`、`TODO`、写作分析段落或角色定位标记。一旦出现，立即触发 P0 重写，不得保留并"以后修改"。

⛔ **禁止在门禁失败后继续写作**：`gate_result.json` 显示 `passed: false` 时，唯一合法操作是执行 `/修复本章`。不得绕过、手动修改 `gate_result.json`，或以"小问题"为由忽略。

⛔ **禁止任意修改主线规划**：任何 Agent（包括写作特工）均无权修改 `novel_plan.md` 的主线架构。中途改纲须显式执行 `/改纲续写` 并经用户确认。

⛔ **禁止剧情加速**：每章至多触发以下配额 1 项（A 主线矛盾实质推进 / B 主要关系决定性升级 / C 核心秘密完整揭露）。同时触发 2 项及以上 = 越界，Beat Sheet 必须修改后重写，门禁强制失败。快档章节（主线突破）结束后下一章必须是慢档或中档。

## 1. 能力矩阵

| 能力 | 状态 | 入口 |
|------|------|------|
| 交互式脑洞引导 + 知识图谱构建 | `[已实现]` | `/脑洞建图` |
| 新手三命令快速开书 | `[已实现]` | `/一键开书` `/继续写` `/修复本章` |
| 每章六步质量门禁 | `[已实现]` | 自动执行 |
| 长期记忆 + 300万字一致性保证 | `[已实现]` | 门禁+RAG+图谱+锚点+审核五层协同 |
| RAG 剧情检索 + 实体映射 | `[已实现]` | `/剧情检索` `/更新剧情索引` |
| 联网调研 + 知识缺口补充 | `[已实现]` | `/联网调研` |
| 风格提取、累积与跨项目复用 | `[已实现]` | `/风格提取` `/风格库检索` |
| 大纲锚点 + 进度配额强约束 | `[已实现]` | 自动集成 |
| 多步流水线写作（Beat Sheet） | `[已实现]` | 自动集成 |
| 反向刹车 + 事件矩阵冷却 | `[已实现]` | 自动集成 |
| 语义级节奏审查 | `[已实现]` | `/节奏审查` |
| 中途改纲 + 级联更新 | `[已实现]` | `/改纲续写` |
| 跨Agent双智能体审核 | `[已实现]` | `/双审` |
| 读者群体 + 写作风格强制确认 | `[已实现]` | `/一键开书 --target-audience --writing-style --core-taboo` |
| 全自动写书调度（断点续写） | `[部分实现]` | `/一键写书` |
| 小说仿写（联网拆解 + 魔改） | `[部分实现]` | `/仿写` `/拆书` |

**300万字一致性五层机制**：① 每章六步门禁 ② RAG 两级检索（粗筛+精排）③ 知识图谱（节点+边+版本，每章回写，改纲级联）④ 大纲锚点（全局进度条 + 章节配额，越界即失败）⑤ 跨Agent独立审核（逐章交叉 + 每10章体检）。

## 2. 新手三命令

| 命令 | 说明 |
|------|------|
| `/一键开书` | 输入题材与剧情种子，自动完成建模 + 建库 + 首章准备 |
| `/继续写` | 自动执行"检索 → 写作 → 门禁 → 索引更新"全链路 |
| `/修复本章` | 门禁失败后自动生成最短修复路径 |

新手模式：`/新手模式 开启`（默认）；高级用户：`/新手模式 关闭`

## 3. 开书前强制确认（写前必过，CLI 硬校验）

执行 `/一键开书` 前，必须逐项向用户确认以下五要素，并作为参数传给 CLI。**缺任何一项，`one-click` 直接返回 `ok:false` + `error: onboarding_incomplete`，不会写任何文件**——这里没有默认值可省略。

| 要素 | 参数 | 取值 |
|------|------|------|
| 目标读者 | `--target-audience` | 年龄段 + 渠道 + 口味（如「起点男频 25-35」） |
| 写作风格 | `--writing-style` | 历史正文 / 网文爽文 / 文艺 / 悬疑推理 / 言情细腻（见 `references/genre-style-matrix.md`） |
| 核心禁区 | `--core-taboo` | 不能写什么；确无禁区也必须显式写 `无` |
| 自动化等级 | `--automation-level` | 手动 / 半自动 / 全自动 |
| 目标规模 | `--target-words` | 总字数（≥10000，按 3500 字/章派生章节数与卷结构） |

```bash
python3 scripts/novel_flow_executor.py one-click \
  --project-root <项目目录> --title <书名> --genre <题材> --idea "<剧情种子>" \
  --target-audience "起点男频 25-35" --writing-style 悬疑推理 \
  --core-taboo "不写真实案件改编" --automation-level 半自动 --target-words 1000000
```

落地方式：五要素写入 `00_memory/idea_seed.md` 的「开书五要素（已确认）」卡片；**核心禁区 → `outline_anchors.json` 的 `global_forbidden_reveals`**（门禁据此判定提前揭露）；**目标规模 → 章节总数**。

用户回答"不确定"时：基于题材和读者群体，给出 2-3 个推荐选项供其选择，不要替他默认。

### 立项完整性（第二道闸口）

五要素齐了但主线计划还是空的（`novel_plan.md` 里仍有 `[待补全]`）时，`/继续写` 不会进入写作：它返回 `awaiting_outline: true` + `00_memory/outline_task.md`（立项补全包）。补完 `novel_plan.md` 再跑 `/继续写`，CLI 复检通过才出写作包。要真正可用的计划，可给 `one-click` 一并传 `--protagonist` / `--protagonist-goal` / `--core-conflict` / `--core-hook`，或由你按补全包补写。

## 4. 强制章节闭环

每次生成新章节后固定执行，按顺序逐项勾选，任何一项未通过都 ⛔ 禁止进入下一章：

- [ ] `/更新记忆` ⚠️ — 同步章节变化到状态追踪器。**跳过后果**：角色状态、伏笔、时间线失去追踪，后续章节产生设定冲突。
- [ ] `/检查一致性` ⚠️ — 检查剧情/设定/角色/时间线冲突。**跳过后果**：矛盾在后续章节累积，百章后几乎无法修复。
- [ ] `/节奏审查` ⛔ — 语义级节奏审查（当前 Agent 自身执行，无需外部 API），写入 `pacing_review.md`。**跳过后果**：关键词脚本检测不到的隐性剧情加速溜过门禁。规范见下。
- [ ] `/风格校准` ⚠️ — 检测并修正文风偏移（题材基调、句长节奏、对话比例）。**跳过后果**：风格逐章漂移，读者流失率上升。
- [ ] `/校稿` ⛔ — 两遍式去AI味润色：清除 AI 模式 → 自审剩余 AI 感 → 二次修改。**跳过后果**：正文保留明显 AI 痕迹，读者识别后丧失沉浸感。详见 `references/humanizer-guide.md`。
- [ ] `/门禁检查` ⛔ — 脚本化校验发布标准（`gate_result.json` `passed: true` 方可解锁下一章）。**跳过后果**：违反 Iron Law，流程强制中断。

### 门禁产物清单（6 个硬性产物，缺一即失败）

路径：`04_editing/gate_artifacts/<chapter_id>/`

| 产物 | 生成者 | 判定规则 |
|------|--------|----------|
| `memory_update.md` | `/更新记忆` | 存在、≥20B、mtime ≥ 章节文件 |
| `consistency_report.md` | `/检查一致性` | 同上 |
| `pacing_review.md` | `/节奏审查` | 同上，且必须含 `节奏审查: 通过` |
| `style_calibration.md` | `/风格校准` | 同上 |
| `copyedit_report.md` | `/校稿` | 同上 |
| `quality_report.md` | `continue-write` 自动写入 | 含全角冒号的 `通过：True`，且 `段落唯一比例 >= 0.85`、`最大重复段落次数 <= 2` |
| `publish_ready.md` | **`/门禁检查` 派生写入** | 不是输入产物：按本次全部检查结果派生，每次运行覆盖重写；手写「可发布」不生效 |

⚠️ **两个最容易踩的规则**：① 每个产物的 mtime 必须不早于章节文件 mtime——改完正文必须重跑全部产物，否则报"文件时间早于章节文件，疑似未执行最新流程"；② `quality_report.md` 由 `continue-write` 自动生成，**手动走流程时必须自行写入**，否则门禁必然失败。

⛔ **第七条判死项：正文纯净度（`body_metadata_purity`）**——门禁不只查产物在不在，还会读正文。出现方括号元信息块（`[写作约束]` / `[相关历史剧情]` / `[待写]`）、`（注：…）`、`TODO`、约束 prompt 原文、代码或文件路径残留，或占位人名（主角 / 同伴 / 配角 / 角色A，同词 ≥3 次或出现在对话标签位）→ 直接判失败，无关闭开关。题材确需把「主角」当真实姓名时，在 `00_memory/purity_allowlist.json` 登记 `{"allow_names": ["主角"]}`。章节还是占位草稿时，门禁同样失败并明确报「占位草稿」。

**为什么不能跳过**：长篇的设定矛盾和风格漂移会随章节指数级放大。门禁每章多花 10 分钟，可避免后期 30 章的全面返工。

### `/节奏审查` 执行规范

由当前 Agent 直接读取章节正文，完成四项语义判断后写入 `pacing_review.md`（脚本按此格式解析，字段名不可改）：

```markdown
# 节奏审查报告

## 一、档位判断
- **本章档位**：[慢档 / 中档 / 快档]
- **判断依据**：[1-2句：主要场景类型、核心矛盾推进幅度]

## 二、A/B/C 配额核查
- **A（主线矛盾实质推进）**：[触发 / 未触发] — [简要说明]
- **B（主要关系决定性升级）**：[触发 / 未触发] — [简要说明]
- **C（核心秘密完整揭露）**：[触发 / 未触发] — [简要说明]
- **配额违规**：[是 / 否]（同时触发 ≥2项 = 违规）

## 三、章末悬念质量
- **悬念等级**：[强 / 中 / 弱 / 无]
- **具体悬念内容**：[用一句话描述章末留下的钩子]

## 四、隐性加速检测
- **是否存在关键词未覆盖的隐性加速**：[是 / 否]
- **说明**：[如有，描述具体表现；无则写"无"]

## 综合结论
节奏审查: [通过 / 失败]
失败原因: [若失败，填写具体原因；通过则填"无"]
```

**判断标准**：A 触发 = 主线格局发生实质性、不可逆改变（非小摩擦）；B 触发 = 主要角色关系到达决定性节点（结盟/决裂/告白/宣战）；C 触发 = 核心秘密被完整揭露（非暗示）。

**结论为"失败"的条件**：A/B/C 同时触发 ≥2 项 **或** 存在隐性加速 **或** 章末悬念为"无"且非慢档收尾。

门禁对 `pacing_review.md` 有两种模式：**默认严格**——文件缺失直接判失败（`--require-semantic-pacing` 默认开启）；只有显式加 `--no-require-semantic-pacing` 时才退回"脚本自造降级版本 + 记警告"（仅调试/批处理用）。语义节奏审查是六步门禁里唯一无法脚本替代的一步，不能默认放行。

## 5. 低上下文策略

- 写前默认只读：`00_memory/novel_plan.md`、`00_memory/novel_state.md`
- 新剧情优先执行 `/剧情检索`，只读取 `next_plot_context.md` 推荐的 Top 片段
- 单章前置读取上限：**最多 4 个文件**
- 每 10 章做一次深度压缩与深度风格校准

> 状态追踪器（`character_tracker.md` / `timeline.md` / `foreshadowing_tracker.md` / `world_state.md` / `style_anchor.md`）一律位于 `00_memory/`；`02_knowledge_base/` 只放设定与资料，不放追踪器、不放章节正文。

## 6. 五大工作模式

| 模式 | 流程 | 适用场景 | 状态 |
|------|------|---------|------|
| 从模糊想法 | `/脑洞建图` → `/一键开书` → `/继续写` → 章节闭环 | 只有一个灵感 | 已实现 |
| 从样章仿写 | `/仿写` → `/风格提取` → `/题材选风格` → `/继续写` → 章节闭环 | 模仿已有作品 | 部分实现 |
| 已有项目续写 | `/续写` → `/继续写` 或 `/批量写作` → 章节闭环 | 中断后恢复 | 已实现 |
| 中途改纲 | `/改纲续写` → 级联更新 → `/继续写` → 章节闭环 | 剧情走向需调整 | 已实现 |
| 全自动 | `/一键写书` → 系统自动循环至目标字数 | 完全托管 | 部分实现（调度框架就绪） |

详细步骤教程见 `references/user-guide.md`。

## 7. 长篇强约束机制

以下为 300 万字级别长篇的核心保障，详细规范见各参考文档。

### 7.1 知识图谱（替代平面文件）

图结构（节点+边+版本）管理角色、事件、伏笔、世界观规则。每章写后自动提取信息回写图谱，改纲时级联更新。→ `references/story-graph-schema.md`

### 7.2 大纲锚点与进度配额

每章写前读取全局进度条，动态注入约束（"当前第X章，距目标还有200章，本章严禁超过当前节点剧情"）。越界直接触发门禁失败。→ `references/outline-anchor-quota-spec.md`

### 7.3 多步流水线写作

将"写一章"拆解为：生成 Beat Sheet（分镜头）→ 按 Beat 扩写血肉 → 串联合成。强制限制单次生成的剧情跨度，让每个场景充分展开。→ `references/beat-pipeline-spec.md`

### 7.4 反向刹车 + 事件冷却 + 节奏配额

- **节奏三档制**：慢档（铺垫/羁绊，每3-4章≥1章，主线零推进）/ 中档（次要矛盾升温未爆发，≥60%）/ 快档（主线突破，每卷≤2-3次，快档后必须有慢/中档缓冲）
- **配额硬上限**（Iron Law 第 6 条）：每章至多触发 A/B/C 中 1 项；触发后逐章冷却
- **章末强制自检**：① 主线核心矛盾仍未解决？② 章末具体悬念是什么（不得模糊）？
- 非终局章节禁止解决主线核心冲突；事件分类池冷却；非冲突场景强制埋微型伏笔
→ `references/anti-resolution-cooldown-spec.md`

### 7.5 跨Agent双智能体审核

- 逐章审核：写作工具完成 → 不同工具审核（Claude 写 Codex 审，反之亦然）
- 批处理审核：每10章由"极严苛老书虫"人设审核官做三维度体检（逻辑硬伤/阅读体验/去AI化）
- 防死循环：单章最多3轮审核，连续3章"有条件通过"则强制暂停请求人工介入
→ `references/cross-agent-review-protocol.md`

## 8. 命令表

### 新手与创作命令

| 命令 | 功能 | 底层脚本 |
|------|------|----------|
| `/一键开书` | 开书全流程 | `novel_flow_executor.py one-click` |
| `/继续写` | 引导剧情走向 → 串行完整章节流程 | `novel_flow_executor.py continue-write` |
| `/修复本章` | 门禁失败后自动修复 | `gate_repair_plan.py` |
| `/新手模式` | 切换简化/高级交互层 | — |
| `/脑洞建图` | 交互式脑洞拓展 + 知识图谱构建 | `novel_flow_executor.py brainstorm` + `interactive_ideation_engine.py` |
| `/写作` | 生成单章草稿并触发闭环 | 主 Agent 执行 |
| `/续写` | 恢复会话状态并继续 | 主 Agent 执行 |
| `/批量写作` | 连续生成多章 | 主 Agent 执行 |
| `/修改章节` | 修订已写章节并级联更新 | 主 Agent 执行 |
| `/写全篇` | 模糊想法 → 百万字路线图 | 主 Agent 执行（参照 `million-word-roadmap.md`） |
| `/改纲续写` | 改纲 + 锚点重算 + 图谱级联 + RAG 重建 | `novel_flow_executor.py revise-outline` |
| `/一键写书` | 全自动写作调度 | `auto_novel_writer.py` |
| `/双审` | 跨Agent双智能体审核 | `cross_agent_reviewer.py` |
| `/启动编辑团队` | 多角色协作生产单章 | `editorial_team_manager.py`（见 §11） |

### `/继续写` 的续写前引导机制

**两段式分工（重要）**：CLI 子进程拿不到你（宿主 Agent）的模型，所以它**不写正文**。

- **第一段（CLI 备料）**：`continue-write` 做检索 → 约束收集 → Beat Sheet 分镜 → 写写作包，返回 `awaiting_draft: true` + `writing_package`（默认 `00_memory/next_chapter_task.md`），正文保持占位。
- **第二段（你写正文）**：读取写作包，按分镜把正文写进目标章节文件（只写小说正文，不得写元信息/占位人名/写作指令）。
- **第三段（CLI 校验）**：重跑 `/继续写` 或 `/门禁检查`，门禁判定是否可发布。

详见下方条目 6 与 §9 的 `--draft-provider` 说明。看到 `awaiting_draft: true` 时**必须由你自己写正文**，不要指望 CLI 自动成稿。

不带 `--chapter-file` 时，CLI 会**复用最后一个占位章**（`one-click` 生成的第 1 章就是占位稿），不再每跑一次就新建一个 `第N章-待写.md`。

1. **引导提问**：询问本章剧情走向偏好（"你希望本章发生什么？有什么新的脑洞吗？"）
2. **脑洞拓展**：基于当前大纲与知识库，提供 2-3 个可能走向供选择
3. **用户确认**：用户选择一个方向，或提供自己的想法
4. **兜底**：用户回复"不确定"/"随便"/"自动"时，按 `novel_plan.md` 当前节点自动推进
5. **全自动模式**：开书确认卡选择"全自动"时，跳过引导直接按大纲写作
6. **节奏预检（⛔ BLOCKING，写作开始前必须声明）**：① 本章节奏档位（慢/中/快）及依据；② 近3章配额触发记录，确认本章 A/B/C 至多触发 1 项；③ 章末保留的具体悬念是什么。预检未通过时禁止进入写作。

### 质量命令（每章必经）

| 命令 | 功能 |
|------|------|
| `/更新记忆` | 同步状态追踪器 |
| `/检查一致性` | 检查剧情/设定/时间线冲突 |
| `/节奏审查` | 语义级节奏审查，写入 `pacing_review.md` |
| `/风格校准` | 检测文风偏移 |
| `/校稿` | 去AI味润色 |
| `/门禁检查` | 脚本化校验发布标准 |

### 检索、风格与分析命令

| 命令 | 功能 | 底层脚本 |
|------|------|----------|
| `/更新剧情索引` | 扫描章节建立索引 | `plot_rag_retriever.py build` |
| `/剧情检索` | RAG 检索相关片段 | `plot_rag_retriever.py query` |
| `/检索记忆` · `/伏笔状态` · `/角色状态` · `/时间线` | 查询 `00_memory/` 下追踪器 | 主 Agent 直读 |
| `/联网调研` | 联网搜索补充知识库 | `research_agent.py` |
| `/题材选风格` · `/风格迁移` · `/风格库检索` | 风格选择与迁移 | 主 Agent + `style_fingerprint.py` |
| `/风格提取` | 从样章提取风格入库 | `style_fingerprint.py <样章...> --profile-name <名>` |
| `/拆书` · `/仿写` | 拆解结构 / 提写法模板 | 主 Agent 执行（`adaptation-workflow.md`） |

### `/改纲续写` 使用说明

**适用场景**：修改了 `novel_plan.md` 之后，必须通过此命令重新对齐三层索引（大纲锚点 + 知识图谱 + RAG 索引），才能继续写作。

**前置条件**（顺序不可颠倒）：① 手动编辑 `00_memory/novel_plan.md` 完成改纲；② 确认改纲影响的起始章节 `--from-chapter`。

**三步级联**：① 锚点重算（必须成功，否则中止，先备份 `outline_anchors.json`）→ ② 图谱级联标记（`last_updated >= from_chapter` 的节点标 `cascade_pending=True`）→ ③ RAG 索引全量重建。

```bash
python3 scripts/novel_flow_executor.py revise-outline \
  --project-root <项目目录> \
  --from-chapter <起始章节号> \
  --change-description "<本次改纲的简要说明>"
```

| 参数 | 类型 | 必选 | 说明 |
|------|------|------|------|
| `--project-root` | 路径 | 是 | 小说项目根目录 |
| `--from-chapter` | 整数（≥1） | 是 | 改纲影响的起始章节号 |
| `--change-description` | 字符串 | 否 | 本次改纲的简要说明（写入报告） |
| `--emit-json` | 路径 | 否 | 额外把 JSON 结果落盘到该路径（stdout 已始终输出 JSON） |

**成功判定**：`ok = anchors_recalculated AND report_written`（图谱标记与 RAG 构建为软失败，不影响 `ok`）。

**产物**：`.flow/backup_anchors_<时间戳>.json`、`00_memory/outline_anchors.json`、`00_memory/revise_outline_report.md`。

**后续操作**：检查报告确认级联节点无误 → 处理 `cascade_pending=True` 节点 → 执行 `/继续写`。

## 9. 脚本入口

| 脚本 | 用途 |
|------|------|
| `novel_flow_executor.py one-click` | `/一键开书` |
| `novel_flow_executor.py continue-write --project-root <目录> --query "<新剧情>"` | `/继续写`（全功能默认开启） |
| `novel_flow_executor.py revise-outline --project-root <目录> --from-chapter <N>` | `/改纲续写` |
| `novel_flow_executor.py brainstorm --project-root <目录>` | `/脑洞建图` |
| `plot_rag_retriever.py build/query` | `/更新剧情索引` `/剧情检索` |
| `chapter_gate_check.py` | `/门禁检查`（`--require-semantic-pacing` 强制语义节奏审查） |
| `gate_repair_plan.py` | `/修复本章` |
| `pacing_tracker.py init/record/check/status` | 节奏档位与 A/B/C 配额记账（`/节奏审查` 的底层依据） |
| `anti_resolution_guard.py check/constraint` | 反向刹车校验 / 约束 prompt 生成 |
| `outline_anchor_manager.py init/check/advance/recalculate` | 大纲锚点初始化 / 配额检查 / 推进 |
| `story_graph_builder.py init/add-node/add-edge/export/validate/generate-context` | 知识图谱 CRUD / 校验 / Mermaid 导出 |
| `story_graph_updater.py extract/apply/diff/cascade` | 章节完成后自动提取信息更新图谱 |
| `beat_sheet_generator.py generate/expand/validate` | Beat Sheet 生成 / 扩写提示 / 校验 |
| `chapter_synthesizer.py synthesize/validate` | 章节合成 / 合成稿质量校验 |
| `event_matrix_scheduler.py init/status/recommend/record` | 事件矩阵冷却 / 推荐 / 记录 |
| `cross_agent_reviewer.py review/batch-review/record/unresolved` | `/双审` 跨Agent审核任务生成 / 结果记录 |
| `editorial_team_manager.py snapshot/record-review/status/need-human` | 编辑团队状态管理 |
| `interactive_ideation_engine.py init/status/collect/advance/generate` | 交互式脑洞引导 5 轮收敛 |
| `style_fingerprint.py <样章...> --profile-name <名>` | `/风格提取` |
| `text_humanizer.py detect/report/prompt` | AI痕迹检测 / 两遍式润色 prompt 生成 |
| `novel_chapter_writer.py --provider <provider>` | 多 LLM 章节写作引擎（OpenAI/Claude/Kimi/GLM/MiniMax/本地） |
| `research_agent.py keywords/gaps/plan/store` | `/联网调研` |
| `auto_novel_writer.py plan/run/progress/report` | `/一键写书` |
| `benchmark_novel_flow.py` | 流程基线评测 |

**内部库（无 CLI，勿直接调用）**：`common.py`、`config.py`、`performance.py`、`content_expansion_engine.py`、`dynamic_draft_generator.py`、`long_term_context_manager.py`。

**`continue-write` 标准用法**：默认全部开启（知识图谱/大纲锚点/Beat Sheet/AI痕迹纠正/滚动/幂等缓存均为默认值）。高级用户按需关闭：

```bash
python3 scripts/novel_flow_executor.py continue-write \
  --project-root <项目目录> --query "<新剧情>" \
  --no-beat-sheet --no-constraints --no-graph-update
```

> `--rollback-on-failure` 与 `--idempotent-cache` 默认即为 `True`，传入属空操作，只能用 `--no-*` 关闭。完整参数见 `references/command-playbook.md`。

**谁写正文（`--draft-provider`）**：

| 取值 | 由谁写 | 何时用 |
|------|--------|--------|
| `auto`（默认） | 配了外部 LLM 就用 LLM，否则 `agent` | 常规 |
| `agent` | **你自己**（宿主 Agent 读写作包写正文） | 装到 Claude Code / MiMoCode 等工具后的默认结局 |
| `llm` | `novel_chapter_writer.py` 调外部 API | `/一键写书` 这类无人值守批处理 |
| `template` | 段落池拼接的占位脚手架 | 仅调试。**产物必被门禁判死（含占位人名），不可发布** |

`agent` 模式下 CLI 不写正文，只返回 `awaiting_draft: true` + `writing_package`（`00_memory/next_chapter_task.md`）。此时你必须：读写作包 → 把正文写进目标章节文件 → 重跑 `/继续写` 或 `/门禁检查`。

## 10. 参考文档导航

| 你想做什么 | 读哪个文档 |
|-----------|-----------|
| 第一次使用，从零开书 | `references/user-guide.md` |
| 查看某个命令的完整参数 | `references/command-playbook.md` |
| 理解门禁产物和通过标准 | `references/gate-artifacts-spec.md` |
| 规划百万字级别的卷章结构 | `references/million-word-roadmap.md` |
| 选择合适的写作风格 | `references/genre-style-matrix.md` |
| 理解 RAG 检索的设计原理 | `references/rag-consistency-design.md` |
| 使用联网调研功能 | `references/research-guide.md` |
| 使用全自动写书功能 | `references/auto-write-guide.md` |
| 执行 /校稿 去AI味润色 | `references/humanizer-guide.md` |
| 了解知识图谱数据结构 | `references/story-graph-schema.md` |
| 了解大纲锚点与进度配额 | `references/outline-anchor-quota-spec.md` |
| 了解多步流水线写作 | `references/beat-pipeline-spec.md` |
| 了解反向刹车与事件冷却 | `references/anti-resolution-cooldown-spec.md` |
| 了解跨Agent审核协议 | `references/cross-agent-review-protocol.md` |
| 了解脑洞引导流程 | `references/interactive-brainstorming-playbook.md` |
| 仿写或魔改已有小说 | `references/adaptation-workflow.md` |
| 了解编辑团队架构与工作协议 | `references/editorial-team-protocol.md` |
| 安装到其他 AI 工具 | `references/multi-tool-install.md` |

## 11. Agent 编辑团队（`/启动编辑团队`）

### 11.1 为什么需要

单 Agent 写作有三个根性问题：**AI 幻觉**（捏造从未出现的地名/人名/设定）、**角色错乱**（位置、能力、语气全错）、**思路污染正文**（分析过程渗入小说正文）。编辑团队通过职责严格分离，在生产流程中内建三道防火墙。

### 11.2 团队架构

```
总编辑（主 Agent）── 协调 + 汇总 + 最终裁判
  ├─► 策划主编 planning-editor        读规划文件 → 生成 Chapter Brief
  ├─► 写作特工 novelist               只收 Brief，只输出纯正文
  ├─► 反AI编辑 anti-ai-editor        ┐ 并行审核
  └─► 连载核实官 consistency-reviewer ┘
```

四个角色定义在 `.claude/agents/`，由 `install-portable-skill.sh --tool claude-code` 安装到 `~/.claude/agents/`。非 Claude Code 工具请改用 `cross_agent_reviewer.py review|batch-review`。

### 11.3 正文隔离协议（最关键的安全机制）

| Agent | 允许输出 | 严禁输出 |
|-------|---------|---------|
| 写作特工 | `NOVEL_TEXT_START` → `NOVEL_TEXT_END` 之间的纯正文 | 分析说明、角色定位、写作思路、meta 注记 |
| 反AI编辑 | 报告 + `HUMANIZED_TEXT` 标记内的净化正文 | 在正文中插入任何注释 |
| 连载核实官 | 结构化核查报告 | 直接修改正文 |
| 总编辑 | 最终章节包（正文与报告分区） | 把审核意见混入正文区 |

**P0 检测触发器**（命中任一即强制重写）：`[` `]` 包裹的说明文字（如 `[此处填写]`、`[角色A]`）；`（注：）`、`【写作说明】`、`TODO`、`作者按` 等元信息标记；写作推理过程或分析性段落出现在正文区。

### 11.4 执行要点

完整逐步流程、角色一致性校验清单、自由创作与规划遵守的分工边界，见 `references/editorial-team-protocol.md`。四条必备脚本调用：

```bash
# 团队启动前：生成上下文快照，取得 context_file 与 current_chapter_no
python3 scripts/editorial_team_manager.py snapshot --project-root <路径>

# 汇总判定后：记录审核结果
python3 scripts/editorial_team_manager.py record-review \
  --project-root <路径> --chapter N --stage final \
  --verdict pass --p0 0 --p1 2 --p2 3

# 查看最近10章审核历史
python3 scripts/editorial_team_manager.py status --project-root <路径>

# 检测是否需要人工介入（true 则暂停并向用户汇报）
python3 scripts/editorial_team_manager.py need-human --project-root <路径>
```

**硬约束**：策划主编负责遵守（情节任务必须推进、本章禁区不得触碰、角色位置状态真实）；写作特工负责创新（章节入口角度、场景呈现、对话内容、细节选择）。**任何 Agent 都无权**改变主线规划、让角色提前到达不该到的地方、发明规划文件外的重要设定。
