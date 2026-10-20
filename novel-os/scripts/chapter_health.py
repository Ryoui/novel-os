#!/usr/bin/env python3
"""单章体检 + 跨章趋势。

回答一个 benchmark 答不了的问题：这一章作为"作品"是什么状态，以及越写越好还是越写越糟。

指标全部本地可算，不依赖模型：
  字数 / 段落 / 句子 / 对话占比 / 段落唯一度 / 概括跳过密度 /
  AI 高频词密度 / 关键节拍数量 / 章末悬念 / 场景-对白比

用法：
  python3 scripts/chapter_health.py check --project-root <目录> --chapter 12
  python3 scripts/chapter_health.py check --project-root <目录> --chapter-file <章节.md>
  python3 scripts/chapter_health.py trend --project-root <目录> [--last 10]

产物：
  00_memory/retrieval/chapter_health.json         单章最新体检（按章节累积）
  00_memory/retrieval/chapter_health_trend.json  趋势与告警
  00_memory/retrieval/chapter_health_report.md   人读摘要（trend 时刷新）
"""

import argparse
import datetime as dt
import json
import re
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from common import chapter_no_from_name, ensure_dir, is_draft_stub_text, load_json, read_text, save_json, slugify  # noqa: E402

# 体内含英文/拼音引用时不做特殊处理；这里只做本地可算的体检
HEALTH_DIR_REL = "00_memory/retrieval"
HEALTH_FILE = "chapter_health.json"
TREND_FILE = "chapter_health_trend.json"
REPORT_FILE = "chapter_health_report.md"

BASELINE_FILE = "chapter_health_baseline.json"
BASELINE_DEFAULT_CHAPTERS = 10

# 与基线比较的容差：rel 为相对偏离，abs 为允许的绝对变化（基线接近 0 时用）
BASELINE_TOLERANCE: Dict[str, Dict[str, float]] = {
    "char_count": {"rel": 0.30},
    "dialogue_ratio": {"rel": 0.40, "abs": 0.02},
    "paragraph_unique_ratio": {"rel": 0.10, "abs": 0.02},
    "skip_density": {"abs": 0.15},
    "ai_density_per_thousand": {"abs": 5.0},
    "beat_markers": {"abs": 1.0},
}

# 阈值：warn 是"该看一眼"，fail 是"该改"
THRESHOLDS: Dict[str, Dict[str, float]] = {
    "char_count": {"fail_below": 2000, "warn_below": 2500},
    "dialogue_ratio": {"fail_below": 0.02, "fail_above": 0.55, "warn_below": 0.03, "warn_above": 0.45},
    "paragraph_unique_ratio": {"fail_below": 0.85, "warn_below": 0.92},
    "max_duplicate_paragraph_repeat": {"fail_above": 2, "warn_above": 1},
    "skip_density": {"fail_above": 0.50, "warn_above": 0.30},
    "ai_density_per_thousand": {"fail_above": 40.0, "warn_above": 20.0},
    "beat_markers_min": {"fail_below": 2, "warn_below": 3},
}

# 段落切分与统计口径与 novel_flow_executor 保持一致
_PARA_SEP = re.compile(r"\n\s*\n")
_SKIP_PATTERNS = [
    r"此后\s*[^，。]{0,6}(天|日|月|年)", r"经过一番", r"花了(数|几)[日天月年]",
    r"苦修[^，。]{0,3}[日月年]", r"练功大成", r"很快便", r"就这样过去",
    r"不知不觉", r"转眼(间|之间)", r"没过多久", r"随后", r"一段时间后",
]
# 关键节拍：动作 / 对话 / 转折 / 揭示 的粗粒度信号
_BEAT_SIGNALS = {
    "action": r"(推|拉|抓|扣|踢|转身|蹲|站起|跑|走|扔|按|抬|扯|塞|避|退)",
    "dialogue": r"[“\"][^”\"]{2,}[”\"]",
    "turn": r"(却|突然|忽然|不料|谁知|竟然|反而|原来)",
    "reveal": r"(发现|认出|看清|证实|想起|明白|意识到)",
}


def _strip_markup(text: str) -> str:
    """去掉标题行、HTML 注释与占位标记，只留正文。"""
    body = re.sub(r"(?m)^#.*$", "", text)
    body = re.sub(r"<!--.*?-->", "", body, flags=re.S)
    return body.strip()


def _split_paragraphs(body: str) -> List[str]:
    return [p.strip() for p in _PARA_SEP.split(body) if p.strip()]


def _dialogue_chars(body: str) -> int:
    return sum(len(m.group(1)) for m in re.finditer(r"[“\"]([^”\"]*)[”\"]", body))


def _skip_density(body: str, paragraphs: List[str]) -> float:
    hits = sum(len(re.findall(p, body)) for p in _SKIP_PATTERNS)
    return round(hits / max(len(paragraphs), 1), 3)


def _beat_signal_counts(body: str) -> Dict[str, int]:
    return {name: len(re.findall(pattern, body)) for name, pattern in _BEAT_SIGNALS.items()}


def _tail_suspense(body: str, tail_chars: int = 200) -> Dict[str, Any]:
    """章末是否有悬念信号（关键词口径，与 anti_resolution_guard 一致）。"""
    keywords = ["?", "？", "……", "却", "突然", "竟", "谁知", "不料", "正要",
                "忽然", "然而", "可是", "怎料", "这才发现"]
    tail = body[-tail_chars:] if len(body) > tail_chars else body
    hits = [k for k in keywords if k in tail]
    return {"has_suspense": bool(hits), "hits": hits, "tail_chars": len(tail)}


def _status(metric: str, value: float) -> str:
    """按阈值给出 ok / warn / fail。"""
    th = THRESHOLDS.get(metric, {})
    if "fail_below" in th and value < th["fail_below"]:
        return "fail"
    if "fail_above" in th and value > th["fail_above"]:
        return "fail"
    if "warn_below" in th and value < th["warn_below"]:
        return "warn"
    if "warn_above" in th and value > th["warn_above"]:
        return "warn"
    return "ok"


def measure_chapter(chapter_path: Path) -> Dict[str, Any]:
    """单章体检：输出原始指标 + 每项状态，不做加权评分（避免黑箱数字）。"""
    text = read_text(chapter_path)
    body = _strip_markup(text)
    pure = re.sub(r"\s+", "", body)
    paragraphs = _split_paragraphs(body)
    para_len = [len(p) for p in paragraphs]

    char_count = len(pure)
    dialogue_chars = _dialogue_chars(body)
    dialogue_ratio = round(dialogue_chars / char_count, 4) if char_count else 0.0

    normalized = [re.sub(r"\s+", " ", p).strip() for p in paragraphs]
    counter: Dict[str, int] = {}
    for p in normalized:
        counter[p] = counter.get(p, 0) + 1
    unique_ratio = round(len(counter) / len(paragraphs), 4) if paragraphs else 1.0
    max_dup = max(counter.values()) if counter else 1

    from text_humanizer import detect_patterns  # 复用去 AI 味模块的词表与判定

    humanizer = detect_patterns(body)
    ai_vocab = (humanizer.get("details") or {}).get("ai_vocab") or {}
    ai_per_k = float(ai_vocab.get("density_per_thousand", 0.0))

    beats = _beat_signal_counts(body)
    beat_markers = sum(1 for v in beats.values() if v > 0)

    metrics: Dict[str, float] = {
        "char_count": char_count,
        "paragraph_count": len(paragraphs),
        "sentence_count": len(re.findall(r"[。！？!?]", body)),
        "dialogue_ratio": dialogue_ratio,
        "paragraph_unique_ratio": unique_ratio,
        "max_duplicate_paragraph_repeat": max_dup,
        "skip_density": _skip_density(body, paragraphs),
        "ai_density_per_thousand": round(ai_per_k, 2),
        "ai_issue_count": float(humanizer.get("issue_count", 0)),
        "beat_markers": float(beat_markers),
        "paragraph_variance": round(
            (sum((x - sum(para_len) / len(para_len)) ** 2 for x in para_len) / len(para_len)), 2
        ) if len(para_len) > 1 else 0.0,
    }

    statuses = {
        "char_count": _status("char_count", metrics["char_count"]),
        "dialogue_ratio": _status("dialogue_ratio", metrics["dialogue_ratio"]),
        "paragraph_unique_ratio": _status(
            "paragraph_unique_ratio", metrics["paragraph_unique_ratio"]
        ),
        "max_duplicate_paragraph_repeat": _status(
            "max_duplicate_paragraph_repeat", metrics["max_duplicate_paragraph_repeat"]
        ),
        "skip_density": _status("skip_density", metrics["skip_density"]),
        "ai_density": _status("ai_density_per_thousand", metrics["ai_density_per_thousand"]),
        "beat_markers": _status("beat_markers_min", metrics["beat_markers"]),
    }

    suspense = _tail_suspense(body)
    if not suspense["has_suspense"]:
        statuses["tail_suspense"] = "warn"
    else:
        statuses["tail_suspense"] = "ok"

    fails = [k for k, v in statuses.items() if v == "fail"]
    warns = [k for k, v in statuses.items() if v == "warn"]
    verdict = "risky" if fails else ("attention" if len(warns) >= 2 else "healthy")

    return {
        "chapter_no": chapter_no_from_name(chapter_path.name),
        "chapter_file": chapter_path.name,
        "chapter_path": str(chapter_path),
        "measured_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "metrics": metrics,
        "beat_signals": beats,
        "tail_suspense": suspense,
        "humanizer": {
            "severity": humanizer.get("severity"),
            "issue_count": humanizer.get("issue_count"),
            "issues": humanizer.get("issues", []),
        },
        "statuses": statuses,
        "verdict": verdict,
        "fail_metrics": fails,
        "warn_metrics": warns,
    }


def _median(values: List[float]) -> float:
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return 0.0
    mid = n // 2
    return round((ordered[mid] if n % 2 else (ordered[mid - 1] + ordered[mid]) / 2), 4)


def compute_baseline(
    project_root: Path, from_chapter: int = 1, to_chapter: Optional[int] = None
) -> Dict[str, Any]:
    """用开局若干章的中位数作为"本书自身基线"。"""
    chapters = _chapters_of(project_root)
    picked = [
        p for p in chapters
        if chapter_no_from_name(p.name) >= from_chapter
        and (to_chapter is None or chapter_no_from_name(p.name) <= to_chapter)
    ]
    if not picked:
        return {"ok": False, "error": "没有可用的章节来建立基线"}

    records = [measure_chapter(p) for p in picked]
    metric_keys = list(BASELINE_TOLERANCE.keys())
    metrics = {
        key: {"median": _median([float(r["metrics"].get(key, 0.0)) for r in records])}
        for key in metric_keys
    }
    return {
        "ok": True,
        "created_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "source": {
            "chapter_nos": [r["chapter_no"] for r in records],
            "chapter_files": [r["chapter_file"] for r in records],
            "count": len(records),
            "range": [from_chapter, to_chapter],
        },
        "metrics": metrics,
        "note": "开局章节的中位数基线；偏离检测用它比较，不做加权评分",
    }


def _baseline_path(project_root: Path) -> Path:
    return project_root / HEALTH_DIR_REL / BASELINE_FILE


def load_baseline(project_root: Path) -> Optional[Dict[str, Any]]:
    path = _baseline_path(project_root)
    if not path.exists():
        return None
    data = load_json(path, default={})
    return data if isinstance(data, dict) and data.get("metrics") else None


def _dev_status(metric: str, value: float, base: float) -> str:
    tol = BASELINE_TOLERANCE.get(metric, {})
    delta = value - base
    if base and "rel" in tol:
        rel = abs(delta) / abs(base)
        if rel > 2 * tol["rel"]:
            return "diverge"
        if rel > tol["rel"]:
            return "notice"
    if "abs" in tol:
        if abs(delta) > 2 * tol["abs"]:
            return "diverge"
        if abs(delta) > tol["abs"]:
            return "notice"
    return "ok"


def deviation_vs_baseline(record: Dict[str, Any], baseline: Dict[str, Any]) -> Dict[str, Any]:
    """逐指标与基线比较：相对偏离 + 状态（ok / notice / diverge）。"""
    metrics = baseline.get("metrics") or {}
    out: Dict[str, Any] = {}
    for key in BASELINE_TOLERANCE:
        base = float((metrics.get(key) or {}).get("median", 0.0))
        value = float(record["metrics"].get(key, 0.0))
        delta = round(value - base, 4)
        out[key] = {
            "baseline": base,
            "value": value,
            "delta": delta,
            "delta_pct": round(delta / base, 4) if base else None,
            "status": _dev_status(key, value, base),
        }
    diverged = [k for k, v in out.items() if v["status"] == "diverge"]
    noticed = [k for k, v in out.items() if v["status"] == "notice"]
    return {
        "available": True,
        "baseline_source": (baseline.get("source") or {}).get("chapter_nos", []),
        "metrics": out,
        "diverge_metrics": diverged,
        "notice_metrics": noticed,
        "verdict": "diverge" if diverged else ("notice" if noticed else "aligned"),
    }


def declared_style_gaps(project_root: Path, record: Dict[str, Any]) -> Dict[str, Any]:
    """与 style_anchor.md 里声明的风格参数对照（开书时写的值）。"""
    anchor = project_root / "00_memory" / "style_anchor.md"
    if not anchor.exists():
        return {"available": False, "reason": "没有 style_anchor.md"}
    text = read_text(anchor)
    declared: Dict[str, float] = {}
    m = re.search(r"对话占比\*\*[：:]\s*([\d.]+)", text)
    if m:
        declared["dialogue_ratio"] = round(float(m.group(1)) / 100, 4)
    m = re.search(r"平均句长\*\*[：:]\s*([\d.]+)", text)
    if m:
        declared["avg_sentence_length"] = float(m.group(1))
    if not declared:
        return {"available": False, "reason": "style_anchor.md 中没有可解析的声明值"}

    actual: Dict[str, float] = {}
    if "dialogue_ratio" in declared:
        actual["dialogue_ratio"] = record["metrics"]["dialogue_ratio"]
    if "avg_sentence_length" in declared:
        chars = record["metrics"]["char_count"]
        sentences = record["metrics"]["sentence_count"]
        actual["avg_sentence_length"] = round(chars / sentences, 2) if sentences else 0.0

    gaps = {
        key: {
            "declared": declared[key],
            "actual": actual.get(key, 0.0),
            "delta": round(actual.get(key, 0.0) - declared[key], 4),
        }
        for key in declared
    }
    return {"available": True, "gaps": gaps}


def _chapters_of(project_root: Path) -> List[Path]:
    manuscript = project_root / "03_manuscript"
    if not manuscript.exists():
        return []
    chapters = [p for p in manuscript.glob("*.md") if not is_draft_stub_text(read_text(p))]
    return sorted(chapters, key=lambda p: (chapter_no_from_name(p.name), p.name))


# 趋势判定需要的最小样本：少于 3 章时任何差异都可能是噪声，直接报"数据不足"
MIN_TREND_SAMPLES = 3

DIRECTION_ZH = {
    "rising": "上升",
    "falling": "下降",
    "stable": "平稳",
    "insufficient_data": "数据不足",
}


def _zh(direction: str) -> str:
    return DIRECTION_ZH.get(direction, direction)


def _direction(series: List[float], tolerance: float = 0.10) -> str:
    """首尾对比判断趋势方向。

    样本不足 MIN_TREND_SAMPLES 章时返回 insufficient_data：2 个点的差异
    无法区分"趋势"与"噪声"，报方向会制造假告警。
    """
    values = [v for v in series if v is not None]
    if len(values) < MIN_TREND_SAMPLES:
        return "insufficient_data"
    head = sum(values[: max(1, len(values) // 2)]) / max(1, len(values) // 2)
    tail = sum(values[len(values) // 2:]) / max(1, len(values) - len(values) // 2)
    if head == 0:
        return "stable" if tail == 0 else "rising"
    delta = (tail - head) / abs(head)
    if delta > tolerance:
        return "rising"
    if delta < -tolerance:
        return "falling"
    return "stable"


def build_trend(project_root: Path, last: Optional[int] = None) -> Dict[str, Any]:
    chapters = _chapters_of(project_root)
    if last and last > 0:
        chapters = chapters[-last:]

    records = [measure_chapter(p) for p in chapters]
    series = {
        key: [round(float(r["metrics"].get(key, 0.0)), 4) for r in records]
        for key in (
            "char_count", "dialogue_ratio", "paragraph_unique_ratio",
            "skip_density", "ai_density_per_thousand", "beat_markers",
        )
    }
    labels = [f"第{r['chapter_no']}章" for r in records]

    directions = {key: _direction(values) for key, values in series.items()}

    # 与本书基线比较
    baseline = load_baseline(project_root)
    baseline_info: Dict[str, Any] = {"available": False}
    if baseline:
        baseline_info = {
            "available": True,
            "source_chapters": (baseline.get("source") or {}).get("chapter_nos", []),
            "metrics": baseline.get("metrics", {}),
        }
        for record in records:
            record["deviation"] = deviation_vs_baseline(record, baseline)

    alerts: List[str] = []
    if len(series["char_count"]) >= 3 and all(
        series["char_count"][i] > series["char_count"][i + 1]
        for i in range(len(series["char_count"]) - 3, len(series["char_count"]) - 1)
    ):
        alerts.append("连续 3 章字数下滑：可能在赶进度")
    if directions["ai_density_per_thousand"] == "rising":
        alerts.append("AI 高频词密度上升：文风在向模型默认值靠")
    if directions["dialogue_ratio"] in {"rising", "falling"}:
        alerts.append(f"对话占比{_zh(directions['dialogue_ratio'])}：场景类型可能单一化")
    if directions["paragraph_unique_ratio"] == "falling":
        alerts.append("段落唯一度下降：出现重复句式或模板化段落")
    if directions["skip_density"] == "rising":
        alerts.append("概括跳过密度上升：剧情在加速推进")
    if record_fails := [r["chapter_no"] for r in records if r["verdict"] == "risky"]:
        alerts.append(f"体检不合格的章节：{record_fails}")

    streak = 0
    max_streak = 0
    if baseline_info.get("available"):
        for record in records:
            dev = record.get("deviation") or {}
            for key in dev.get("diverge_metrics", []):
                item = dev["metrics"][key]
                pct = item.get("delta_pct")
                shown = f"{pct:+.0%}" if isinstance(pct, (int, float)) else f"{item['delta']:+.3f}"
                alerts.append(
                    f"第{record['chapter_no']}章偏离本书基线：{key} {item['value']}"
                    f"（基线 {item['baseline']}，{shown}）"
                )
            if dev.get("verdict") == "diverge":
                streak += 1
                max_streak = max(max_streak, streak)
            else:
                streak = 0
        if max_streak >= 2:
            alerts.append(f"连续 {max_streak} 章偏离基线：文风在漂移")
        if not any(r.get("deviation") for r in records):
            alerts.append("基线尚无有效偏离数据")

    verdict_counts = {"healthy": 0, "attention": 0, "risky": 0}
    for r in records:
        verdict_counts[r["verdict"]] = verdict_counts.get(r["verdict"], 0) + 1

    return {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_root": str(project_root),
        "chapter_count": len(records),
        "chapters": labels,
        "series": series,
        "directions": directions,
        "alerts": alerts,
        "verdict_counts": verdict_counts,
        "baseline": baseline_info,
        "deviation_counts": {
            "diverge": sum(1 for r in records
                           if (r.get("deviation") or {}).get("verdict") == "diverge"),
            "notice": sum(1 for r in records
                          if (r.get("deviation") or {}).get("verdict") == "notice"),
        },
        "records": records,
    }


def _write_report(project_root: Path, trend: Dict[str, Any]) -> Path:
    lines = [
        "# 作品体检报告（跨章趋势）",
        "",
        f"- 生成时间：{trend['generated_at']}",
        f"- 覆盖章节：{trend['chapter_count']} 章（{', '.join(trend['chapters']) or '无'}）",
        f"- 体检结论分布：健康 {trend['verdict_counts'].get('healthy', 0)} / "
        f"需关注 {trend['verdict_counts'].get('attention', 0)} / "
        f"风险 {trend['verdict_counts'].get('risky', 0)}",
        "",
        "## 一、指标趋势",
        "",
        "| 指标 | 方向 | 序列 |",
        "|------|------|------|",
    ]
    for key, values in trend["series"].items():
        direction = trend["directions"][key]
        lines.append(f"| {key} | {_zh(direction)} | {' → '.join(str(v) for v in values)} |")

    lines += ["", "## 二、告警"]
    lines += [f"- {a}" for a in trend["alerts"]] or ["- 无"]

    lines += ["", "## 三、与本书基线偏离", ""]
    baseline_info = trend.get("baseline") or {}
    if baseline_info.get("available"):
        src = baseline_info.get("source_chapters") or []
        lines.append(f"基线来源：第 {', '.join(str(x) for x in src)} 章的中位数")
        lines.append("")
        lines.append("| 章节 | 指标 | 基线 | 本章 | 偏离 | 状态 |")
        lines.append("|------|------|------|------|------|------|")
        for record in trend["records"]:
            dev = record.get("deviation") or {}
            for key, item in (dev.get("metrics") or {}).items():
                if item["status"] == "ok":
                    continue
                pct = item.get("delta_pct")
                shown = f"{pct:+.0%}" if isinstance(pct, (int, float)) else f"{item['delta']:+.3f}"
                lines.append(
                    f"| {record['chapter_file']} | {key} | {item['baseline']} | "
                    f"{item['value']} | {shown} | {item['status']} |"
                )
        if not any(
            item["status"] != "ok"
            for record in trend["records"]
            for item in ((record.get("deviation") or {}).get("metrics") or {}).values()
        ):
            lines.append("| - | - | - | - | - | 全部在容差内 |")
    else:
        lines.append("尚未建立基线：先执行 `chapter_health.py baseline --project-root <目录>`。")

    lines += ["", "## 四、逐章结论", "", "| 章节 | 结论 | 失败项 | 提醒项 | 偏离 |", "|------|------|--------|--------|------|"]
    for r in trend["records"]:
        fails = "、".join(r["fail_metrics"]) or "-"
        warns = "、".join(r["warn_metrics"]) or "-"
        dev_verdict = (r.get("deviation") or {}).get("verdict", "-")
        lines.append(f"| {r['chapter_file']} | {r['verdict']} | {fails} | {warns} | {dev_verdict} |")

    lines += [
        "",
        "> 这些是本地可算的**代理指标**，不等于读者感受。它们能发现\"越写越像 AI / 越写越赶\"这类漂移，",
        "> 不能替代追读率与真实反馈。阈值见 `scripts/chapter_health.py` 的 `THRESHOLDS`。",
        "",
    ]

    out = project_root / HEALTH_DIR_REL / REPORT_FILE
    ensure_dir(out.parent)
    out.write_text("\n".join(lines), encoding="utf-8")
    return out


def cmd_check(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    if args.chapter_file:
        chapter = Path(args.chapter_file)
        if not chapter.is_absolute():
            chapter = project_root / chapter
        chapter = chapter.resolve()
    else:
        no = int(args.chapter or 0)
        matches = [p for p in (project_root / "03_manuscript").glob("*.md")
                   if chapter_no_from_name(p.name) == no]
        if not matches:
            return {"ok": False, "command": "check", "error": f"找不到第 {no} 章"}
        chapter = matches[0]

    if not chapter.exists():
        return {"ok": False, "command": "check", "error": f"章节文件不存在: {chapter}"}

    record = measure_chapter(chapter)

    baseline = load_baseline(project_root)
    record["deviation"] = (
        deviation_vs_baseline(record, baseline) if baseline
        else {"available": False, "reason": "未建立基线，先跑 chapter_health.py baseline"}
    )
    record["declared_style"] = declared_style_gaps(project_root, record)

    health_file = project_root / HEALTH_DIR_REL / HEALTH_FILE
    ensure_dir(health_file.parent)
    store = load_json(health_file, default={"chapters": {}})
    chapters = store.get("chapters")
    if not isinstance(chapters, dict):
        chapters = {}
    chapters[str(record["chapter_no"])] = record
    store["chapters"] = chapters
    store["updated_at"] = record["measured_at"]
    save_json(health_file, store, indent=2)

    return {
        "ok": True,
        "command": "check",
        "chapter_file": str(chapter),
        "verdict": record["verdict"],
        "statuses": record["statuses"],
        "metrics": record["metrics"],
        "fail_metrics": record["fail_metrics"],
        "warn_metrics": record["warn_metrics"],
        "tail_suspense": record["tail_suspense"],
        "deviation": record["deviation"],
        "declared_style": record["declared_style"],
        "health_file": str(health_file),
    }


def cmd_baseline(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    path = _baseline_path(project_root)

    if path.exists() and not args.rebuild:
        existing = load_baseline(project_root)
        return {
            "ok": True,
            "command": "baseline",
            "baseline_file": str(path),
            "reused": True,
            "source_chapters": (existing or {}).get("source", {}).get("chapter_nos", []),
            "next_step": "如需重算基线，追加 --rebuild",
        }

    baseline = compute_baseline(project_root, args.from_chapter, args.to_chapter or None)
    if not baseline.get("ok"):
        return {"ok": False, "command": "baseline", "error": baseline.get("error")}

    ensure_dir(path.parent)
    save_json(path, baseline, indent=2)
    return {
        "ok": True,
        "command": "baseline",
        "baseline_file": str(path),
        "reused": False,
        "source_chapters": baseline["source"]["chapter_nos"],
        "metrics": {k: v["median"] for k, v in baseline["metrics"].items()},
        "next_step": "现在可以跑 check / trend 看与基线的偏离",
    }


def cmd_trend(args: argparse.Namespace) -> Dict[str, Any]:
    project_root = Path(args.project_root).expanduser().resolve()
    trend = build_trend(project_root, last=args.last)
    if trend["chapter_count"] == 0:
        return {"ok": False, "command": "trend",
                "error": "没有可体检的章节（占位桩不计入）"}

    out = project_root / HEALTH_DIR_REL / TREND_FILE
    ensure_dir(out.parent)
    payload = {k: v for k, v in trend.items() if k != "records"}
    save_json(out, {**payload, "records": trend["records"]}, indent=2)
    report = _write_report(project_root, trend)

    return {
        "ok": True,
        "command": "trend",
        "chapter_count": trend["chapter_count"],
        "chapters": trend["chapters"],
        "series": trend["series"],
        "directions": trend["directions"],
        "baseline": trend["baseline"],
        "deviation_counts": trend["deviation_counts"],
        "alerts": trend["alerts"],
        "verdict_counts": trend["verdict_counts"],
        "trend_file": str(out),
        "report_file": str(report),
    }


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="单章体检与跨章趋势（本地可算，不依赖模型）")
    sub = p.add_subparsers(dest="cmd", required=True)

    c = sub.add_parser("check", help="体检单章")
    c.add_argument("--project-root", required=True)
    c.add_argument("--chapter", type=int, help="章节号")
    c.add_argument("--chapter-file", help="章节文件路径（可相对 project-root）")

    t = sub.add_parser("trend", help="跨章趋势与告警")
    t.add_argument("--project-root", required=True)
    t.add_argument("--last", type=int, default=0, help="只看最近 N 章（默认全部）")

    b = sub.add_parser("baseline", help="用开局章节建立本书自身基线")
    b.add_argument("--project-root", required=True)
    b.add_argument("--from-chapter", type=int, default=1)
    b.add_argument("--to-chapter", type=int, default=BASELINE_DEFAULT_CHAPTERS,
                   help=f"基线取样截止章（默认 {BASELINE_DEFAULT_CHAPTERS}）")
    b.add_argument("--rebuild", action="store_true", help="覆盖已有基线")

    return p.parse_args()


def main() -> int:
    args = parse_args()
    handlers = {"check": cmd_check, "trend": cmd_trend, "baseline": cmd_baseline}
    payload = handlers[args.cmd](args)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0 if payload.get("ok") else 1


if __name__ == "__main__":
    raise SystemExit(main())
