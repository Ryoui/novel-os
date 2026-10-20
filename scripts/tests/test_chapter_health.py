#!/usr/bin/env python3
"""单章体检 + 跨章趋势测试（9 号待办）

- 健康章节各指标状态与结论
- 漂移章节（字数下滑 / 对话变少 / AI 套话 / 跳过句）被判 risk
- 跨章趋势能识别方向并给出中文告警
- 产物落盘；benchmark 把作品侧体检并入 summary

运行方式:
    python3 scripts/tests/test_chapter_health.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

HEALTH = SCRIPT_DIR / "chapter_health.py"
BENCH = SCRIPT_DIR / "benchmark_novel_flow.py"


DIALOGUE = ("周遇在旁边低声说：“第{i}回了，脚印还没干。今晚来过的不止一个人，"
            "左边那串是新的，右边那串踩在泥里，脚跟压得比前掌重。”")


def build_chapter(no: int, paragraphs: int, *, dialogue_every: int = 3,
                  ai_words: bool = False, skip_sentences: int = 0) -> str:
    chunks = [f"# 第{no}章 码头{no}"]
    for i in range(1, paragraphs + 1):
        text = (f"第{i}次走到码头，陈砚先数了一遍缆桩上的绳结，{i + 12}个，一个没散。"
                f"他把手电塞进内袋，光柱贴着地面扫过去，照见一层新落的灰。")
        if skip_sentences and i % 4 == 0:
            text += "此后三天，他把所有线索重新梳理了一遍。" * skip_sentences
        if ai_words and i % 3 == 0:
            text += "他不禁感到一阵心悸，嘴角微扬。"
        if dialogue_every and i % dialogue_every == 0:
            text += DIALOGUE.format(i=i)
        chunks.append(text)
    return "\n\n".join(chunks) + "\n"


def run(script: Path, *args):
    p = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(p.stdout)


class TestChapterHealth(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_health_"))
        self.manuscript = self.project_root / "03_manuscript"
        self.manuscript.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def _write(self, no: int, body: str) -> Path:
        path = self.manuscript / f"第{no}章-码头{no}.md"
        path.write_text(body, encoding="utf-8")
        return path

    def test_healthy_chapter_metrics(self):
        self._write(1, build_chapter(1, 40))
        payload = run(HEALTH, "check", "--project-root", str(self.project_root),
                      "--chapter", "1")
        self.assertTrue(payload["ok"])
        m = payload["metrics"]
        self.assertGreater(m["char_count"], 2500)
        self.assertGreater(m["dialogue_ratio"], 0.03)
        self.assertEqual(m["paragraph_unique_ratio"], 1.0)
        self.assertEqual(m["skip_density"], 0.0)
        self.assertIn(payload["verdict"], ("healthy", "attention"))
        self.assertEqual(payload["fail_metrics"], [])

    def test_drifted_chapter_is_risky(self):
        self._write(5, build_chapter(5, 20, dialogue_every=10, ai_words=True,
                                     skip_sentences=2))
        payload = run(HEALTH, "check", "--project-root", str(self.project_root),
                      "--chapter", "5")
        self.assertEqual(payload["verdict"], "risky")
        self.assertIn("char_count", payload["fail_metrics"])
        self.assertGreater(payload["metrics"]["ai_density_per_thousand"], 0)

    def test_check_writes_health_file(self):
        self._write(2, build_chapter(2, 40))
        run(HEALTH, "check", "--project-root", str(self.project_root), "--chapter", "2")
        store = json.loads(
            (self.project_root / "00_memory" / "retrieval" / "chapter_health.json")
            .read_text(encoding="utf-8")
        )
        self.assertIn("2", store["chapters"])
        self.assertIn("metrics", store["chapters"]["2"])

    def test_trend_detects_drift_and_alerts(self):
        specs = [
            (1, 34, dict(dialogue_every=3)),
            (2, 30, dict(dialogue_every=3)),
            (3, 26, dict(dialogue_every=4, ai_words=True)),
            (4, 22, dict(dialogue_every=6, ai_words=True, skip_sentences=1)),
            (5, 18, dict(dialogue_every=8, ai_words=True, skip_sentences=2)),
        ]
        for no, paras, kw in specs:
            self._write(no, build_chapter(no, paras, **kw))

        payload = run(HEALTH, "trend", "--project-root", str(self.project_root))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["chapter_count"], 5)
        self.assertEqual(payload["directions"]["char_count"], "falling")
        self.assertEqual(payload["directions"]["skip_density"], "rising")
        self.assertTrue(any("字数下滑" in a for a in payload["alerts"]))
        self.assertTrue(all("下跌" not in a for a in payload["alerts"]))  # 中文表述
        self.assertGreater(payload["verdict_counts"]["risky"], 0)

        for key in ("trend_file", "report_file"):
            self.assertTrue(Path(payload[key]).exists(), key)
        report = Path(payload["report_file"]).read_text(encoding="utf-8")
        self.assertIn("作品体检报告", report)
        self.assertIn("代理指标", report)

    def test_trend_needs_min_samples(self):
        """2 章不足以谈趋势：方向一律 insufficient_data，且不出漂移类告警。"""
        self._write(1, build_chapter(1, 34))
        self._write(2, build_chapter(2, 18, dialogue_every=10, ai_words=True))
        payload = run(HEALTH, "trend", "--project-root", str(self.project_root))
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["chapter_count"], 2)
        self.assertEqual(
            set(payload["directions"].values()), {"insufficient_data"},
            payload["directions"],
        )
        self.assertFalse(
            any("上升" in a or "下降" in a for a in payload["alerts"]),
            payload["alerts"],
        )

    def test_stub_chapters_ignored(self):
        self._write(1, "# 第1章 待写\n\n<!-- NOVEL_FLOW_STUB -->\n\n## 正文\n[待写]\n")
        payload = run(HEALTH, "trend", "--project-root", str(self.project_root))
        self.assertFalse(payload["ok"])
        self.assertIn("没有可体检的章节", payload["error"])


class TestBaselineDeviation(unittest.TestCase):
    """基线 = 开局章节中位数；偏离检测能在绝对阈值合格时报警。"""

    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_baseline_"))
        self.manuscript = self.project_root / "03_manuscript"
        self.manuscript.mkdir(parents=True, exist_ok=True)
        (self.project_root / "00_memory").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def _write(self, no: int, body: str) -> None:
        (self.manuscript / f"第{no}章-码头{no}.md").write_text(body, encoding="utf-8")

    def _write_drifting_project(self):
        for no in (1, 2, 3, 4):
            self._write(no, build_chapter(no, 40, dialogue_every=2))
        self._write(5, build_chapter(5, 40, dialogue_every=16))

    def test_baseline_built_from_early_chapters(self):
        self._write_drifting_project()
        payload = run(HEALTH, "baseline", "--project-root", str(self.project_root),
                      "--to-chapter", "4")
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["source_chapters"], [1, 2, 3, 4])
        self.assertFalse(payload["reused"])
        self.assertGreater(payload["metrics"]["dialogue_ratio"], 0.15)
        self.assertTrue(Path(payload["baseline_file"]).exists())

    def test_baseline_reused_unless_rebuild(self):
        self._write_drifting_project()
        run(HEALTH, "baseline", "--project-root", str(self.project_root), "--to-chapter", "4")
        again = run(HEALTH, "baseline", "--project-root", str(self.project_root),
                    "--to-chapter", "4")
        self.assertTrue(again["reused"])
        rebuilt = run(HEALTH, "baseline", "--project-root", str(self.project_root),
                      "--to-chapter", "4", "--rebuild")
        self.assertFalse(rebuilt["reused"])

    def test_deviation_flags_drift_when_absolute_checks_pass(self):
        self._write_drifting_project()
        run(HEALTH, "baseline", "--project-root", str(self.project_root), "--to-chapter", "4")

        payload = run(HEALTH, "check", "--project-root", str(self.project_root),
                      "--chapter", "5")
        # 对话占比在绝对阈值上是 ok，但相对本书基线偏离过大
        self.assertEqual(payload["statuses"]["dialogue_ratio"], "ok")
        deviation = payload["deviation"]
        self.assertTrue(deviation["available"])
        self.assertEqual(deviation["verdict"], "diverge")
        item = deviation["metrics"]["dialogue_ratio"]
        self.assertEqual(item["status"], "diverge")
        self.assertLess(item["delta_pct"], -0.6)

    def test_check_aligned_on_baseline_chapter(self):
        self._write_drifting_project()
        run(HEALTH, "baseline", "--project-root", str(self.project_root), "--to-chapter", "4")
        payload = run(HEALTH, "check", "--project-root", str(self.project_root),
                      "--chapter", "4")
        self.assertEqual(payload["deviation"]["verdict"], "aligned")
        self.assertEqual(payload["deviation"]["diverge_metrics"], [])

    def test_trend_reports_baseline_alerts_and_section(self):
        self._write_drifting_project()
        run(HEALTH, "baseline", "--project-root", str(self.project_root), "--to-chapter", "4")
        payload = run(HEALTH, "trend", "--project-root", str(self.project_root))
        self.assertTrue(payload["baseline"]["available"])
        self.assertEqual(payload["baseline"]["source_chapters"], [1, 2, 3, 4])
        self.assertGreaterEqual(payload["deviation_counts"]["diverge"], 1)
        self.assertTrue(any("偏离本书基线" in a for a in payload["alerts"]), payload["alerts"])
        report = Path(payload["report_file"]).read_text(encoding="utf-8")
        self.assertIn("与本书基线偏离", report)
        self.assertIn("diverge", report)

    def test_declared_style_compared_with_anchor(self):
        self._write(1, build_chapter(1, 40, dialogue_every=2))
        (self.project_root / "00_memory" / "style_anchor.md").write_text(
            "# 风格锚点\n\n- **平均句长**：24字\n- **对话占比**：45%\n", encoding="utf-8"
        )
        payload = run(HEALTH, "check", "--project-root", str(self.project_root),
                      "--chapter", "1")
        declared = payload["declared_style"]
        self.assertTrue(declared["available"], declared)
        self.assertEqual(declared["gaps"]["dialogue_ratio"]["declared"], 0.45)
        self.assertIn("avg_sentence_length", declared["gaps"])

    def test_check_without_baseline_says_how_to_build(self):
        self._write(1, build_chapter(1, 40))
        payload = run(HEALTH, "check", "--project-root", str(self.project_root),
                      "--chapter", "1")
        self.assertFalse(payload["deviation"]["available"])
        self.assertIn("baseline", payload["deviation"]["reason"])


class TestBenchmarkComposition(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_bench_health_"))

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def test_benchmark_reports_composition_when_chapters_exist(self):
        manuscript = self.project_root / "03_manuscript"
        manuscript.mkdir(parents=True, exist_ok=True)
        for no in (1, 2, 3):
            (manuscript / f"第{no}章-码头{no}.md").write_text(
                build_chapter(no, 36 - no * 2), encoding="utf-8"
            )
        payload = run(BENCH, "--project-root", str(self.project_root), "--rounds", "1")
        composition = payload["summary"]["composition"]
        self.assertTrue(composition["available"], composition)
        self.assertEqual(composition["chapter_count"], 3)
        self.assertIn("verdict_counts", composition)
        self.assertIn("directions", composition)


if __name__ == "__main__":
    unittest.main(verbosity=2)
