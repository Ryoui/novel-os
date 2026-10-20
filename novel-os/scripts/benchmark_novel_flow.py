#!/usr/bin/env python3
"""小说流程评测基线脚本。"""

import argparse
import datetime as dt
import json
import os
import statistics
import subprocess
import sys
from pathlib import Path
from typing import Dict, List


ROOT = Path(__file__).resolve().parent
EXECUTOR = ROOT / "novel_flow_executor.py"

DEFAULT_QUERIES = [
    "主角在站台发现名单并与同伴发生冲突",
    "主角根据坐标追查内鬼线索，出现时间线矛盾",
    "反派势力突然介入，主角被迫调整联盟关系",
]


def run_cmd(args: List[str]) -> Dict[str, object]:
    env = os.environ.copy()
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    proc = subprocess.run([sys.executable, str(EXECUTOR), *args], capture_output=True, text=True, env=env)
    if proc.returncode not in (0, 1):
        raise RuntimeError(f"命令异常 rc={proc.returncode}: {proc.stderr}")
    try:
        return json.loads(proc.stdout)
    except Exception as exc:
        raise RuntimeError(f"输出非JSON: {proc.stdout}") from exc


def mean(xs: List[float]) -> float:
    return round(statistics.mean(xs), 4) if xs else 0.0


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="评测 novel_flow_executor 的流程指标基线")
    p.add_argument("--project-root", required=True)
    p.add_argument("--queries-file", help="JSON 文件，格式为字符串数组")
    p.add_argument("--rounds", type=int, default=3)
    p.add_argument("--init-if-needed", action="store_true", default=True)
    p.add_argument("--title", default="评测样书")
    p.add_argument("--genre", default="悬疑")
    p.add_argument("--idea", default="陈砚在旧港区发现失踪名单")
    # 开书五要素（CLI 已强制校验，评测默认给一组合法值）
    p.add_argument("--target-audience", default="起点男频 25-35")
    p.add_argument("--writing-style", default="悬疑推理")
    p.add_argument("--core-taboo", default="不写真实案件改编")
    p.add_argument("--automation-level", default="半自动")
    p.add_argument("--target-words", type=int, default=1000000)
    p.add_argument("--force-run", action="store_true", help="评测时强制执行，忽略幂等缓存")
    p.add_argument("--emit-json")
    return p.parse_args()


def main() -> int:
    args = parse_args()
    project_root = Path(args.project_root).expanduser().resolve()
    project_root.mkdir(parents=True, exist_ok=True)

    queries = DEFAULT_QUERIES
    if args.queries_file:
        queries = json.loads(Path(args.queries_file).expanduser().resolve().read_text(encoding="utf-8"))
        if not isinstance(queries, list) or not all(isinstance(x, str) for x in queries):
            raise SystemExit("queries-file 必须是字符串数组 JSON")

    if args.init_if_needed and not (project_root / "00_memory" / "novel_plan.md").exists():
        run_cmd([
            "one-click",
            "--project-root",
            str(project_root),
            "--title",
            args.title,
            "--genre",
            args.genre,
            "--idea",
            args.idea,
            "--target-audience", args.target_audience,
            "--writing-style", args.writing_style,
            "--core-taboo", args.core_taboo,
            "--automation-level", args.automation_level,
            "--target-words", str(args.target_words),
            "--protagonist", "陈砚",
            "--protagonist-goal", "查清三年前的旧案",
            "--core-conflict", "失踪名单背后的旧案",
            "--core-hook", "一张名单牵出三条人命",
        ])

    runs = []
    for i in range(max(1, args.rounds)):
        q = queries[i % len(queries)]
        payload = run_cmd([
            "continue-write",
            "--project-root",
            str(project_root),
            "--query",
            q,
        ] + (["--force-run"] if args.force_run else []))
        q_result = payload.get("query_result", {})
        rstats = (q_result.get("result") or {}).get("retrieval_stats", {}) if isinstance(q_result, dict) else {}
        runs.append({
            "ok": bool(payload.get("ok")),
            "gate_passed_final": bool(payload.get("gate_passed_final")),
            "runtime_ms": float(payload.get("runtime_ms", 0)),
            "retry_actions": len(payload.get("auto_retry_actions", []) or []),
            "idempotent_hit": bool(payload.get("idempotent_hit")),
            "retrieval_candidates": float(rstats.get("candidate_pool", 0)),
            "retrieval_context_chars": float(rstats.get("estimated_context_chars", 0)),
        })

    total = len(runs)
    summary = {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "project_root": str(project_root),
        "total_runs": total,
        "ok_rate": round(sum(1 for r in runs if r["ok"]) / total, 4) if total else 0.0,
        "gate_pass_rate": round(sum(1 for r in runs if r["gate_passed_final"]) / total, 4) if total else 0.0,
        "retry_rate": round(sum(1 for r in runs if r["retry_actions"] > 0) / total, 4) if total else 0.0,
        "idempotent_hit_rate": round(sum(1 for r in runs if r["idempotent_hit"]) / total, 4) if total else 0.0,
        "avg_runtime_ms": mean([r["runtime_ms"] for r in runs]),
        "avg_retrieval_candidates": mean([r["retrieval_candidates"] for r in runs]),
        "avg_retrieval_context_chars": mean([r["retrieval_context_chars"] for r in runs]),
    }

    # 流程指标之外，再给一份"作品侧"体检——流程跑通不等于章节能读
    composition: Dict[str, object] = {"available": False, "reason": "没有已写章节（占位桩不计）"}
    try:
        from chapter_health import build_trend

        trend = build_trend(project_root)
        if trend["chapter_count"] > 0:
            composition = {
                "available": True,
                "chapter_count": trend["chapter_count"],
                "verdict_counts": trend["verdict_counts"],
                "directions": trend["directions"],
                "alerts": trend["alerts"],
                "note": "代理指标，不等同读者感受；详见 chapter_health.py trend",
            }
    except Exception as exc:  # 体检失败不影响流程指标
        composition = {"available": False, "error": str(exc)}

    summary["composition"] = composition

    out = project_root / "00_memory" / "retrieval" / "eval_baseline.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"summary": summary, "runs": runs}, ensure_ascii=False, indent=2), encoding="utf-8")

    payload = {"ok": True, "summary": summary, "output": str(out)}
    if args.emit_json:
        Path(args.emit_json).expanduser().resolve().write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
