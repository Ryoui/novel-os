#!/usr/bin/env python3
"""章节质量门禁校验器。

目标：把协议约束转为可执行硬检查，避免流程只停留在文档层。
"""

import argparse
import datetime as dt
import json
import re
import sys
import types
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from common import slugify
from config import QualityConfig

# 确保同目录脚本可直接 import
_SCRIPT_DIR = Path(__file__).parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))


def resolve_chapter(project_root: Path, chapter_file: str) -> Path:
    p = Path(chapter_file)
    if not p.is_absolute():
        p = project_root / p
    return p.resolve()


def required_artifacts(gate_dir: Path) -> Dict[str, Path]:
    return {
        "memory_update": gate_dir / "memory_update.md",
        "consistency_report": gate_dir / "consistency_report.md",
        "style_calibration": gate_dir / "style_calibration.md",
        "copyedit_report": gate_dir / "copyedit_report.md",
        "quality_report": gate_dir / "quality_report.md",
    }


def check_chapter_storage(project_root: Path, chapter_path: Path) -> Tuple[bool, str]:
    if chapter_path.suffix.lower() != ".md":
        return False, "章节文件必须是 .md 格式"
    try:
        rel = chapter_path.relative_to(project_root)
    except ValueError:
        return False, "章节文件不在项目目录内"
    rel_posix = rel.as_posix()
    if not rel_posix.startswith("03_manuscript/"):
        return False, "章节文件必须存放在 03_manuscript/ 目录下"
    return True, "通过"


def find_misplaced_chapters(project_root: Path) -> List[str]:
    kb_dir = project_root / "02_knowledge_base"
    if not kb_dir.exists():
        return []
    bad: List[str] = []
    chapter_name_re = re.compile(r"^第\d+章.*\.md$")
    for p in kb_dir.rglob("*.md"):
        if chapter_name_re.match(p.name):
            bad.append(str(p))
    return bad


def check_file(path: Path, min_bytes: int, chapter_mtime: float) -> Tuple[bool, str]:
    if not path.exists():
        return False, "文件不存在"
    size = path.stat().st_size
    if size < min_bytes:
        return False, f"文件过小({size}B < {min_bytes}B)"
    if path.stat().st_mtime < chapter_mtime:
        return False, "文件时间早于章节文件，疑似未执行最新流程"
    return True, "通过"


def derive_publish_verdict(passed: bool, failures: List[str]) -> str:
    """发布判定由门禁自己派生——不接受 Agent 手写结论。

    结论只取决于本次门禁的全部 failure，和任何自评文件无关。
    """
    if passed:
        return "可发布"
    return "不可发布"


def write_publish_verdict(
    gate_dir: Path, chapter_path: Path, passed: bool, failures: List[str], warnings: List[str]
) -> Path:
    """把派生出的发布结论写进 publish_ready.md（覆盖任何人工/Agent 版本）。"""
    verdict = derive_publish_verdict(passed, failures)
    lines = [
        "# 发布判定（由门禁派生）",
        "",
        f"- 章节：{chapter_path.name}",
        f"- 结论：{verdict}",
        "- 判定来源：`gate_result.json` 的检查结果（脚本派生，不采信手写结论）",
        f"- 生成时间：{dt.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        "",
    ]
    if failures:
        lines.append("## 阻断项")
        lines += [f"- {f}" for f in failures]
    else:
        lines.append("## 阻断项")
        lines.append("- 无")
    if warnings:
        lines += ["", "## 提醒（不阻断发布）"]
        lines += [f"- {w}" for w in warnings]
    lines.append("")
    out = gate_dir / "publish_ready.md"
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def check_quality_report(path: Path) -> Tuple[bool, str]:
    txt = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"通过：\s*(True|False)", txt)
    if not m:
        return False, "quality_report 缺少\"通过：True/False\"结论"
    report_passed = (m.group(1) == "True")

    # 检查段落重复度指标（无论总体是否通过都执行，确保输出详细失败信息）
    dup_failures = []

    # 解析段落唯一比例
    unique_ratio_m = re.search(r"段落唯一比例[：:]\s*([\d.]+)", txt)
    if unique_ratio_m:
        try:
            ratio = float(unique_ratio_m.group(1))
            # 阈值 0.85
            if ratio < 0.85:
                dup_failures.append(f"paragraph_unique_ratio={ratio:.2%} < 0.85")
        except ValueError:
            pass

    # 解析最大重复段落次数
    max_dup_m = re.search(r"最大重复段落次数[：:]\s*(\d+)", txt)
    if max_dup_m:
        try:
            max_dup = int(max_dup_m.group(1))
            # 阈值 2
            if max_dup > 2:
                dup_failures.append(f"max_duplicate_paragraph_repeat={max_dup} > 2")
        except ValueError:
            pass

    failures: List[str] = []
    if not report_passed:
        failures.append("quality_report 显示未通过")
    if dup_failures:
        failures.append("段落重复度检查失败: " + "; ".join(dup_failures))
    if failures:
        return False, "；".join(failures)

    return True, "通过"


def check_pacing_review(path: Path) -> Tuple[bool, str]:
    """解析 pacing_review.md 的综合结论字段。

    期望格式：
        节奏审查: 通过
        节奏审查: 失败
        失败原因: <原因>
    """
    txt = path.read_text(encoding="utf-8", errors="ignore")
    m = re.search(r"节奏审查[：:]\s*(通过|失败)", txt)
    if not m:
        return False, "pacing_review.md 缺少「节奏审查: 通过/失败」结论行"
    if m.group(1) == "失败":
        reason_m = re.search(r"失败原因[：:]\s*(.+)", txt)
        reason = reason_m.group(1).strip() if reason_m else "未说明原因"
        return False, f"节奏审查失败：{reason}"
    return True, "通过"


def load_purity_allowlist(
    project_root: Path, override: Optional[str]
) -> Tuple[Set[str], List[str]]:
    """加载正文纯净度白名单。

    默认读取 <project-root>/00_memory/purity_allowlist.json：
        {"allow_names": ["主角"], "allow_patterns": ["这一幕的主角是"]}
    allow_names    — 视为合法人名，不再参与占位名判定
    allow_patterns — 命中文本包含该子串时放行该条元信息命中
    """
    path = Path(override).expanduser() if override else project_root / "00_memory" / "purity_allowlist.json"
    if not path.exists():
        return set(), []
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return set(), []
    if not isinstance(data, dict):
        return set(), []
    names = {str(x).strip() for x in (data.get("allow_names") or []) if str(x).strip()}
    patterns = [str(x) for x in (data.get("allow_patterns") or []) if str(x).strip()]
    return names, patterns


def _line_of(text: str, pos: int) -> int:
    return text.count("\n", 0, pos) + 1


def _snippet(text: str, pos: int, length: int, pad: int = 20) -> str:
    start = max(0, pos - pad)
    end = min(len(text), pos + length + pad)
    return re.sub(r"\s+", " ", text[start:end]).strip()


def check_body_metadata(
    chapter_path: Path,
    allow_names: Set[str],
    allow_patterns: List[str],
) -> Tuple[bool, str, Dict[str, Any]]:
    """正文纯净度硬检查：元信息残留或占位人名 → 判死。

    占位名不做字面判死，只在「同词 ≥3 次」或「出现在对话标签位」时判定，
    避免误杀「这部剧的主角」这类正常叙述。
    """
    cfg = QualityConfig()
    text = chapter_path.read_text(encoding="utf-8", errors="ignore")

    stub_hits: List[str] = []
    if cfg.stub_marker in text:
        stub_hits.append(cfg.stub_marker)
    if cfg.beat_sheet_stub_marker in text:
        stub_hits.append(cfg.beat_sheet_stub_marker)
    if re.search(r"(?m)^\[待写\]\s*$", text):
        stub_hits.append("[待写]")
    if stub_hits:
        detail = {
            "stub": True,
            "violations": [
                {"category": "占位草稿", "hit": h, "line": 1, "snippet": ""} for h in stub_hits
            ],
            "counts": {"占位草稿": len(stub_hits)},
        }
        return (
            False,
            f"章节仍是占位草稿（正文未写）：命中 {'、'.join(stub_hits)}",
            detail,
        )

    violations: List[Dict[str, Any]] = []
    counts: Dict[str, int] = {}

    for pattern, category, hint in cfg.body_meta_markers:
        for m in re.finditer(pattern, text):
            hit = m.group(0)
            if allow_patterns and any(ap in hit for ap in allow_patterns):
                continue
            violations.append(
                {
                    "category": category,
                    "hit": hit,
                    "line": _line_of(text, m.start()),
                    "snippet": _snippet(text, m.start(), len(hit)),
                    "hint": hint,
                }
            )
            counts[category] = counts.get(category, 0) + 1

    candidates = [n for n in cfg.placeholder_names if n not in allow_names]
    for name in candidates:
        occurrences = text.count(name)
        tag_m = re.search(
            rf"{re.escape(name)}(?:说|道|问|答|喊|笑|点头|摇头|压低声音)", text
        )
        if occurrences >= 3 or tag_m:
            hits_lines = [
                _line_of(text, m.start()) for m in re.finditer(re.escape(name), text)
            ][:4]
            violations.append(
                {
                    "category": "占位人名",
                    "hit": name,
                    "line": hits_lines[0] if hits_lines else 1,
                    "lines": hits_lines,
                    "count": occurrences,
                    "snippet": _snippet(text, text.find(name), len(name)),
                    "hint": "把占位人名替换为真实角色名，或先执行 /更新记忆 补全人物档案",
                }
            )
            counts["占位人名"] = counts.get("占位人名", 0) + 1

    if not violations:
        return True, "通过", {"stub": False, "violations": [], "counts": {}}

    parts: List[str] = []
    for category, count in counts.items():
        if category == "占位人名":
            names = [
                f"「{v['hit']}」×{v.get('count', 0)}"
                for v in violations
                if v["category"] == "占位人名"
            ]
            parts.append(f"{category}{'、'.join(names)}")
        else:
            parts.append(f"{category}×{count}")
    lines = sorted({v["line"] for v in violations})
    line_part = "（第" + "/".join(str(x) for x in lines[:6]) + "行）" if lines else ""
    message = f"命中 {len(violations)} 处正文污染：" + "、".join(parts) + line_part

    return (
        False,
        message,
        {"stub": False, "violations": violations[:10], "counts": counts},
    )


def generate_script_pacing_review(
    tier: str,
    triggered_quotas: List[str],
    has_suspense: bool,
    arg_errors: List[str],
    pt_errors: List[str],
) -> str:
    """Python 自动模式下，从脚本检查结果生成 pacing_review.md（无需 LLM）。

    Claude Code 对话模式下此函数不被调用；Claude 直接写入语义分析内容。
    """
    quota_violated = len(triggered_quotas) >= 2
    pacing_errors = arg_errors + pt_errors
    passed = not quota_violated and not pacing_errors

    tier_map = {"fast": "快档", "medium": "中档", "slow": "慢档"}
    tier_zh = tier_map.get(tier, "未知")

    a_status = "触发" if "A" in triggered_quotas else "未触发"
    b_status = "触发" if "B" in triggered_quotas else "未触发"
    c_status = "触发" if "C" in triggered_quotas else "未触发"

    suspense_level = "中" if has_suspense else "无"
    fail_reason = "；".join(pacing_errors) if pacing_errors else "无"

    verdict = "通过" if passed else "失败"

    return f"""# 节奏审查报告（脚本自动生成）

> 本报告由 chapter_gate_check.py 脚本自动生成，基于 anti_resolution_guard 和 pacing_tracker 检查结果。
> Claude Code 对话模式下应由 `/节奏审查` 步骤生成语义版本替换本文件。

## 一、档位判断
- **本章档位**：{tier_zh}
- **判断依据**：由写前 event_matrix 推荐的事件类型推断

## 二、A/B/C 配额核查
- **A（主线矛盾实质推进）**：{a_status} — 关键词检测
- **B（主要关系决定性升级）**：{b_status} — 关键词检测
- **C（核心秘密完整揭露）**：{c_status} — 关键词检测
- **配额违规**：{"是" if quota_violated else "否"}（同时触发 ≥2项 = 违规）

## 三、章末悬念质量
- **悬念等级**：{suspense_level}（脚本关键词检测）
- **具体悬念内容**：脚本模式下不做语义分析

## 四、隐性加速检测
- **是否存在关键词未覆盖的隐性加速**：否（脚本模式不做语义分析）
- **说明**：如需语义检测，请在 Claude Code 对话中执行 `/节奏审查`

## 综合结论
节奏审查: {verdict}
失败原因: {fail_reason}
"""


def extract_chapter_number(raw: str) -> int:
    """从章节标识或文件名中提取首个数字序列作为章节号。"""
    m = re.search(r"(\d+)", raw or "")
    return int(m.group(1)) if m else 0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="检查章节是否完成强制门禁：更新记忆→一致性→风格校准→校稿")
    p.add_argument("--project-root", required=True, help="小说项目根目录")
    p.add_argument("--chapter-file", required=True, help="章节文件路径（可相对 project-root）")
    p.add_argument("--chapter-id", help="章节标识；默认从章节文件名推导")
    p.add_argument("--min-bytes", type=int, default=20, help="门禁产物最小字节数")
    p.add_argument("--emit-json", help="额外导出 JSON 结果路径")
    p.add_argument("--pacing-tier", choices=["slow", "medium", "fast"],
                   help="当前章预期节奏档位（传入 pacing_tracker check 做预演）")
    p.add_argument("--pacing-event-types", default="",
                   help="当前章事件类型，逗号分隔（档位推断用）")
    p.add_argument("--require-semantic-pacing", action="store_true",
                   help="强制要求 /节奏审查 产出的 pacing_review.md；缺失时判失败而非自动生成降级版本")
    p.add_argument("--purity-allowlist",
                   help="正文纯净度白名单路径；默认 <project-root>/00_memory/purity_allowlist.json")
    return p.parse_args()


def main() -> int:
    args = parse_args()

    project_root = Path(args.project_root).expanduser().resolve()
    chapter_path = resolve_chapter(project_root, args.chapter_file)
    chapter_id = slugify(args.chapter_id or chapter_path.stem)

    gate_dir = project_root / "04_editing" / "gate_artifacts" / chapter_id
    gate_dir.mkdir(parents=True, exist_ok=True)

    result = {
        "checked_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_root": str(project_root),
        "chapter_file": str(chapter_path),
        "chapter_id": chapter_id,
        "passed": False,
        "checks": [],
        "failures": [],
        "warnings": [],
    }

    if not chapter_path.exists():
        result["failures"].append(f"章节文件不存在: {chapter_path}")
        out = gate_dir / "gate_result.json"
        out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 2

    ok, msg = check_chapter_storage(project_root, chapter_path)
    result["checks"].append(
        {"name": "chapter_storage_policy", "path": str(chapter_path), "ok": ok, "message": msg}
    )
    if not ok:
        result["failures"].append(f"chapter_storage_policy: {msg}")

    misplaced = find_misplaced_chapters(project_root)
    if misplaced:
        result["failures"].append("knowledge_base_contains_chapter_files: 发现章节文件混入 02_knowledge_base")
        result["checks"].append(
            {
                "name": "knowledge_base_isolation",
                "path": str(project_root / "02_knowledge_base"),
                "ok": False,
                "message": f"发现 {len(misplaced)} 个疑似章节文件",
            }
        )
        for p in misplaced:
            result["warnings"].append(f"请迁移文件到 03_manuscript: {p}")
    else:
        result["checks"].append(
            {
                "name": "knowledge_base_isolation",
                "path": str(project_root / "02_knowledge_base"),
                "ok": True,
                "message": "通过",
            }
        )

    chapter_mtime = chapter_path.stat().st_mtime
    artifacts = required_artifacts(gate_dir)

    for name, file_path in artifacts.items():
        ok, msg = check_file(file_path, args.min_bytes, chapter_mtime)
        item = {"name": name, "path": str(file_path), "ok": ok, "message": msg}
        result["checks"].append(item)
        if not ok:
            result["failures"].append(f"{name}: {msg}")

    quality_path = artifacts["quality_report"]
    if quality_path.exists() and quality_path.stat().st_size >= args.min_bytes:
        ok, msg = check_quality_report(quality_path)
        item = {
            "name": "quality_baseline",
            "path": str(quality_path),
            "ok": ok,
            "message": msg,
        }
        result["checks"].append(item)
        if not ok:
            result["failures"].append(f"quality_baseline: {msg}")

    # ── 反向刹车校验（anti_resolution_guard check）────────────────────
    # 检查章末悬念、禁止揭露、分辨率信号，将 errors → failures / warnings → warnings
    try:
        import anti_resolution_guard as _arg_mod  # noqa: PLC0415

        _arg_cfg = _arg_mod.AntiResConfig()
        _arg_args = types.SimpleNamespace(
            project_root=str(project_root),
            chapter_file=str(chapter_path),
            is_finale=False,
        )
        _arg_result: Dict[str, Any] = _arg_mod.cmd_check(_arg_args, _arg_cfg)

        _arg_errors: List[str] = _arg_result.get("errors", []) or []
        _arg_warnings: List[str] = _arg_result.get("warnings", []) or []
        _arg_checks: Dict[str, Any] = _arg_result.get("checks", {}) or {}

        result["checks"].append(
            {
                "name": "anti_resolution_guard",
                "path": str(chapter_path),
                "ok": len(_arg_errors) == 0,
                "message": "通过" if not _arg_errors else "；".join(_arg_errors),
                "details": _arg_checks,
            }
        )
        for _e in _arg_errors:
            result["failures"].append(f"anti_resolution_guard: {_e}")
        for _w in _arg_warnings:
            result["warnings"].append(f"anti_resolution_guard: {_w}")
    except Exception as _exc:
        # 脚本不可用时降级为警告，不阻断门禁
        result["warnings"].append(f"anti_resolution_guard 不可用（跳过）: {_exc}")
        result["checks"].append(
            {
                "name": "anti_resolution_guard",
                "path": str(chapter_path),
                "ok": True,
                "message": f"跳过（脚本加载失败）: {_exc}",
            }
        )

    # ── 节奏档位校验（pacing_tracker check）────────────────────────
    # 校验卷内快档配额、慢档密度、连续快档上限
    try:
        import pacing_tracker as _pt_mod  # noqa: PLC0415

        _pt_cfg = _pt_mod.PacingConfig()
        _ch_no = extract_chapter_number(chapter_id)
        _pt_args = types.SimpleNamespace(
            project_root=str(project_root),
            chapter=_ch_no,
            max_fast_per_volume=_pt_cfg.max_fast_per_volume,
            # 传入当前章预期档位，让 check 做"含本章"的预演校验
            current_tier=getattr(args, "pacing_tier", None),
            current_event_types=getattr(args, "pacing_event_types", "") or "",
        )
        _pt_result: Dict[str, Any] = _pt_mod.cmd_check(_pt_args, _pt_cfg)

        _pt_errors: List[str] = _pt_result.get("errors", []) or []
        _pt_warnings: List[str] = _pt_result.get("warnings", []) or []

        result["checks"].append(
            {
                "name": "pacing_tracker",
                "path": str(project_root / "00_memory" / "pacing_history.json"),
                "ok": len(_pt_errors) == 0,
                "message": "通过" if not _pt_errors else "；".join(_pt_errors),
                "details": {
                    "chapter": _ch_no,
                    "volume": _pt_result.get("volume"),
                    "stats": _pt_result.get("stats", {}),
                },
            }
        )
        for _e in _pt_errors:
            result["failures"].append(f"pacing_tracker: {_e}")
        for _w in _pt_warnings:
            result["warnings"].append(f"pacing_tracker: {_w}")
    except Exception as _exc:
        result["warnings"].append(f"pacing_tracker 不可用（跳过）: {_exc}")
        result["checks"].append(
            {
                "name": "pacing_tracker",
                "path": str(project_root / "00_memory" / "pacing_history.json"),
                "ok": True,
                "message": f"跳过（脚本加载失败）: {_exc}",
            }
        )

    # ── 节奏审查（pacing_review.md）────────────────────────────────
    # 优先使用 Agent 写入的语义版本；不存在时从脚本检查结果自动生成降级版本。
    # --require-semantic-pacing 开启时不做降级，缺失即判失败。
    _pr_path = gate_dir / "pacing_review.md"
    _pr_missing = not _pr_path.exists()
    if _pr_missing:
        # 从已完成的脚本检查中提取数据，生成回退版本
        _pr_arg_check = next(
            (c for c in result["checks"] if c.get("name") == "anti_resolution_guard"), {}
        )
        _pr_pt_check = next(
            (c for c in result["checks"] if c.get("name") == "pacing_tracker"), {}
        )
        _pr_quota = (_pr_arg_check.get("details") or {}).get("quota_abc") or {}
        _pr_triggered = _pr_quota.get("triggered_quotas") or []
        _pr_suspense = ((_pr_arg_check.get("details") or {}).get("tail_suspense") or {}).get(
            "has_suspense", True
        )
        _pr_tier = ((_pr_pt_check.get("details") or {}).get("current_tier")) or "medium"
        _pr_arg_errors: List[str] = [
            f for f in result["failures"] if f.startswith("anti_resolution_guard:")
        ]
        _pr_pt_errors: List[str] = [
            f for f in result["failures"] if f.startswith("pacing_tracker:")
        ]
        _pr_content = generate_script_pacing_review(
            _pr_tier, _pr_triggered, _pr_suspense, _pr_arg_errors, _pr_pt_errors
        )
        _pr_path.write_text(_pr_content, encoding="utf-8")
        if args.require_semantic_pacing:
            result["failures"].append(
                "pacing_review_semantic: pacing_review.md 缺失，未执行 /节奏审查"
                "（--require-semantic-pacing 强制要求语义版本）"
            )
        else:
            result["warnings"].append(
                "pacing_review.md 不存在，已从脚本检查结果自动生成降级版本"
                "（正式流程请执行 /节奏审查，或加 --require-semantic-pacing 强制校验）"
            )

    if _pr_path.exists() and _pr_path.stat().st_size >= args.min_bytes:
        _pr_ok, _pr_msg = check_pacing_review(_pr_path)
        result["checks"].append(
            {
                "name": "pacing_review_semantic",
                "path": str(_pr_path),
                "ok": _pr_ok,
                "message": _pr_msg,
            }
        )
        if not _pr_ok:
            result["failures"].append(f"pacing_review_semantic: {_pr_msg}")

    # ── 正文纯净度（元信息残留 / 占位人名）────────────────────────
    # 判死项：门禁校验的是「这段文字能不能发」，而不只是产物文件在不在。
    _allow_names, _allow_patterns = load_purity_allowlist(
        project_root, getattr(args, "purity_allowlist", None)
    )
    _body_ok, _body_msg, _body_details = check_body_metadata(
        chapter_path, _allow_names, _allow_patterns
    )
    result["checks"].append(
        {
            "name": "body_metadata_purity",
            "path": str(chapter_path),
            "ok": _body_ok,
            "message": _body_msg,
            "details": _body_details,
        }
    )
    if not _body_ok:
        result["failures"].append(f"body_metadata_purity: {_body_msg}")

    result["passed"] = len(result["failures"]) == 0
    result["publish_ready"] = result["passed"]
    result["publish_blockers"] = list(result["failures"])

    publish_path = write_publish_verdict(
        gate_dir, chapter_path, result["passed"], result["failures"], result["warnings"]
    )
    result["checks"].append(
        {
            "name": "publish_verdict",
            "path": str(publish_path),
            "ok": result["passed"],
            "message": derive_publish_verdict(result["passed"], result["failures"]),
        }
    )

    gate_result = gate_dir / "gate_result.json"
    gate_result.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    if args.emit_json:
        emit_path = Path(args.emit_json).expanduser().resolve()
        emit_path.parent.mkdir(parents=True, exist_ok=True)
        emit_path.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
