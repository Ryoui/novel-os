# 多步流水线写作协议（Beat Sheet Pipeline）

> 状态：已实现
## 问题背景

单步生成整章内容时，AI 会为了上下文连贯性而压缩剧情，导致章节空洞、推进过快。将"写一章"拆解为多步协作，强制限制单次生成的剧情跨度，让每个场景充分展开。

## 流水线步骤

### Step 1: Beat Sheet 生成（分镜头）

输入：本章目标、大纲锚点约束、上章结尾
输出：3-5 个 Beat（微场景），每个 Beat 包含：

```json
{
  "beat_id": 1,
  "type": "conflict",
  "summary": "太子在朝堂上提出均田制改革方案",
  "characters": ["李承乾", "魏征", "长孙无忌"],
  "location": "太极殿",
  "micro_conflict": "长孙无忌当场反对，朝堂哗然",
  "emotion_target": "紧张→小胜（争取到皇帝的'再议'）",
  "word_target": 800,
  "anti_resolution": true
}
```

Beat 类型分布规则：
- 每章至少 1 个冲突型 Beat
- 不得连续 2 个同类型 Beat
- 最后一个 Beat 必须留下悬念或新问题

**无 LLM 时的默认内容**：骨架阶段（`beat_sheet_generator.py generate`）不会留下空字段。`summary` 由「章节目标 + Beat 类型 + 在章内的位置」派生，形如

```
冲突对抗｜围绕「陈砚在码头与周遇对峙」——由对手先施加压力，主角试探后反制，冲突至少走两个来回；开场：先把当前处境与压力落到具体场景里
```

`micro_conflict` / `emotion_target` 也按类型给出一句可执行的方向（如「谁在阻止谁做什么：本 Beat 的具体对抗点」／「紧张 → 受挫 → 稳住阵脚」）。这些是**方向**而非成稿：写作者据其展开具体场景，`characters` / `location` 未指定时在扩写提示里明确写「未指定（按本章目标确定）」，不留空白字段。

### Step 2: Beat 扩写（填血肉）

针对每个 Beat 独立扩写，聚焦：
- 环境描写（感官细节，不超过3句）
- 角色动作与微表情
- 对话（带性格差异，避免"报菜名"式对话）
- 内心独白（限主视角角色）

每个 Beat 扩写后约 600-1200 字。

扩写时的硬约束：
- 不得超出当前 Beat 的剧情范围
- 不得提前引入后续 Beat 的冲突
- 对话占比参照题材风格矩阵

### Step 3: 章节合成

将所有 Beat 扩写结果串联：
- 添加过渡句（场景切换、时间推移）
- 统一人称和时态
- 检查章内时间线连续性
- 确保章末钩子（Hook）存在

### Step 4: 进入门禁

合成稿进入标准六步门禁流程。

### Step 5: 图谱回写

门禁通过后，从成稿中提取信息更新知识图谱。

## 与现有流程的集成

`/继续写` 命令的内部流程从：
```
剧情检索 → 写作 → 门禁 → 索引更新
```
扩展为：
```
剧情检索 → 锚点配额检查 → Beat Sheet → Beat 扩写 → 合成 → 门禁 → 图谱回写 → 索引更新
```

## 脚本入口
```bash
# 1) 生成 Beat Sheet（分镜头）
python3 scripts/beat_sheet_generator.py generate \
  --project-root <目录> --chapter <章节号> \
  --chapter-goal "<本章目标>" --beat-count 4 --pacing-depth standard

# 2) 按 Beat 扩写血肉（生成该 Beat 的扩写提示词）
python3 scripts/beat_sheet_generator.py expand \
  --project-root <目录> --chapter <章节号> --beat-id 1

# 3) 校验 Beat Sheet 完整性
python3 scripts/beat_sheet_generator.py validate --project-root <目录> --chapter <章节号>

# 4) 章节合成
python3 scripts/chapter_synthesizer.py synthesize --project-root <目录> --chapter <章节号>

# 5) 合成稿质量校验
python3 scripts/chapter_synthesizer.py validate --project-root <目录> --chapter <章节号>
```

> 注意：没有独立的 `beat_flesh_writer.py`，Beat 扩写由 `beat_sheet_generator.py expand` 承担。