# 门禁产物规范

每章都必须在以下目录产生产物：`04_editing/gate_artifacts/<chapter_id>/`
（`<chapter_id>` 由章节文件名 slug 化得到，中文字符保留。）

## 必需产物（5 个 + 1 个质量 + 1 个发布判定 + 1 个脚本输出）

| # | 文件 | 生成者 | 脚本硬性要求 |
|---|------|--------|-------------|
| 1 | `memory_update.md` | `/更新记忆` | 存在、非空、mtime ≥ 章节文件 |
| 2 | `consistency_report.md` | `/检查一致性` | 同上 |
| 3 | `pacing_review.md` | `/节奏审查` | 同上，且必须含 `节奏审查: 通过` 或 `节奏审查: 失败` |
| 4 | `style_calibration.md` | `/风格校准` | 存在、非空、mtime ≥ 章节文件 |
| 5 | `copyedit_report.md` | `/校稿` | 同上 |
| 6 | `quality_report.md` | `continue-write` 自动写入 | 见下方《质量基线判定》 |
| 7 | `publish_ready.md` | **`/门禁检查` 派生写入** | 不是输入，无通过标准；每次门禁运行按实际结果覆盖重写 |
| 8 | `gate_result.json` | `/门禁检查` 自动生成 | 脚本输出，`passed: true` 才解锁下一章 |

失败修复文件（门禁失败时生成）：`repair_plan.md`（由 `/修复本章` 生成）。

> ⚠️ **最容易踩的两个坑**
> 1. `quality_report.md` 由 `continue-write` 自动写入。**手动走六步流程时必须自行生成**，否则门禁必然失败。
> 2. 所有产物的 mtime 必须不早于章节文件 mtime。改完正文必须重跑全部产物，否则报"文件时间早于章节文件，疑似未执行最新流程"。

## 生成与校验顺序

1. `/更新记忆` → `memory_update.md`
2. `/检查一致性` → `consistency_report.md`
3. `/节奏审查` → `pacing_review.md`
4. `/风格校准` → `style_calibration.md`
5. `/校稿` → `copyedit_report.md` + `publish_ready.md`
6. `/门禁检查` → 执行脚本，写入 `gate_result.json`
7. 失败时 `/修复本章` → `repair_plan.md`

## 通过标准（`passed = 所有 failures 为空`）

| 检查项 | 判定规则 |
|--------|---------|
| `chapter_storage_policy` | 章节必须是 `.md`、位于项目目录内、且在 `03_manuscript/` 下 |
| `knowledge_base_isolation` | `02_knowledge_base/` 下不得出现 `第\d+章*.md` |
| 6 个必需产物 | 每个 `size >= 20B`（可用 `--min-bytes` 调整）且 `mtime >= 章节文件 mtime` |
| `publish_verdict` | 由 `passed` 派生：通过 → `可发布`，否则 `不可发布`；结论同时写入 `gate_result.json` 的 `publish_ready` / `publish_blockers` 与 `publish_ready.md` |
| `quality_baseline` | 见下方《质量基线判定》 |
| `anti_resolution_guard` | 反向刹车校验无 errors（模块不可导入时降级为 warning） |
| `pacing_tracker` | 节奏档位与 A/B/C 配额无 errors（同上降级） |
| `pacing_review_semantic` | `pacing_review.md` 结论必须是 `通过`；结论为 `失败` 或缺失结论行即判失败 |
| `body_metadata_purity` | **正文纯净度（判死项）**：正文不得含元信息残留（方括号块 `[写作约束]`/`[相关历史剧情]`/`[待写]`、（注：…）、TODO、约束 prompt 原文、代码/路径残留、`补充推进：` 这类写作指令）；占位人名（主角/同伴/配角/角色A…）同词 ≥3 次或出现在对话标签位即判死。无关闭开关，只可用 `00_memory/purity_allowlist.json` 白名单豁免（`allow_names` / `allow_patterns`）。章节仍为占位草稿时直接给出「占位草稿」结论 |

### 质量基线判定（`quality_report.md`）

1. 必须含**全角冒号**的 `通过：True` 或 `通过：False`（半角冒号不识别）
2. 若存在 `段落唯一比例：<数值>` 行，则要求 `>= 0.85`
3. 若存在 `最大重复段落次数：<整数>` 行，则要求 `<= 2`

### `pacing_review.md` 的两种模式

| 模式 | 触发方式 | 文件缺失时 |
|------|---------|-----------|
| 严格（默认） | 无额外参数（`--require-semantic-pacing` 默认开启） | 直接记 failure，判失败 |
| 宽松 | `--no-require-semantic-pacing` | 脚本自动生成降级版本 + 记 warning，**不阻断** |

`continue-write` 默认即严格：语义节奏审查是六步门禁里唯一无法脚本替代的一步。只有调试或批处理场景才显式用 `--no-require-semantic-pacing` 退回宽松模式——降级版本自身就是脚本生成的，无法独立失败。
