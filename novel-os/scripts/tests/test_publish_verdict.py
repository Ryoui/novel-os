#!/usr/bin/env python3
"""发布判定由门禁派生测试（4 号待办）

核心命题：`publish_ready.md` 是门禁的输出，不是 Agent 的输入。
手写「可发布」不能把失败的门禁翻成通过；门禁每次运行都会重写该文件。

运行方式:
    python3 scripts/tests/test_publish_verdict.py
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

GATE = SCRIPT_DIR / "chapter_gate_check.py"

CLEAN_BODY = "# 第5章 雨夜名单\n\n" + "\n\n".join(
    f"陈砚第{i}次把名单摊在码头木箱上，潮气顺着木缝往上爬，纸角已经卷了。"
    f"周遇蹲在缆桩旁，伞尖淌下的水在地上积成一小片。"
    f"“第三个名字是假的。”他说，“那个人三年前就不在港区了。”"
    for i in range(1, 31)
) + "\n"

QUALITY_PASS = """# 章节质量检查

- 通过：True
- 段落唯一比例：1.0
- 最大重复段落次数：1
"""

QUALITY_FAIL = """# 章节质量检查

- 通过：False
- 段落唯一比例：1.0
- 最大重复段落次数：1
"""

PACING_PASS = "# 节奏审查报告\n\n## 综合结论\n节奏审查: 通过\n失败原因: 无\n"


class TestPublishVerdictDerivation(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_publish_"))
        for d in ["00_memory", "02_knowledge_base", "03_manuscript", "04_editing/gate_artifacts"]:
            (self.project_root / d).mkdir(parents=True, exist_ok=True)
        self.chapter = self.project_root / "03_manuscript" / "第5章-雨夜名单.md"
        self.chapter.write_text(CLEAN_BODY, encoding="utf-8")
        self.gate_dir = (
            self.project_root / "04_editing" / "gate_artifacts" / self.chapter.stem
        )
        self.gate_dir.mkdir(parents=True, exist_ok=True)
        for name in ("memory_update.md", "consistency_report.md",
                     "style_calibration.md", "copyedit_report.md"):
            (self.gate_dir / name).write_text(f"# {name}\n\n已完成。\n", encoding="utf-8")
        (self.gate_dir / "pacing_review.md").write_text(PACING_PASS, encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def _run_gate(self, quality_text: str) -> dict:
        (self.gate_dir / "quality_report.md").write_text(quality_text, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(GATE), "--project-root", str(self.project_root),
             "--chapter-file", str(self.chapter)],
            capture_output=True, text=True, encoding="utf-8",
        )
        return json.loads(proc.stdout)

    def test_handwritten_verdict_cannot_override_failure(self):
        """Agent 在 publish_ready.md 手写「可发布」也翻不了盘。"""
        publish = self.gate_dir / "publish_ready.md"
        publish.write_text("# 发布判定\n\n结论：可发布（通过）\n关键词：可发布 / PASS\n",
                           encoding="utf-8")

        payload = self._run_gate(QUALITY_FAIL)

        self.assertFalse(payload["passed"])
        self.assertFalse(payload["publish_ready"])
        self.assertTrue(payload["publish_blockers"])
        text = publish.read_text(encoding="utf-8")
        self.assertIn("不可发布", text)
        self.assertIn("由门禁派生", text)
        self.assertIn("quality_baseline", text)

    def test_verdict_written_by_gate_on_pass(self):
        payload = self._run_gate(QUALITY_PASS)

        self.assertTrue(payload["passed"], payload.get("failures"))
        self.assertTrue(payload["publish_ready"])
        self.assertEqual(payload["publish_blockers"], [])
        text = (self.gate_dir / "publish_ready.md").read_text(encoding="utf-8")
        self.assertIn("结论：可发布", text)

        verdict_check = next(
            c for c in payload["checks"] if c["name"] == "publish_verdict"
        )
        self.assertTrue(verdict_check["ok"])
        self.assertEqual(verdict_check["message"], "可发布")

    def test_publish_ready_is_not_a_required_input(self):
        """publish_ready.md 缺失不得作为失败项（它是门禁输出）。"""
        payload = self._run_gate(QUALITY_PASS)
        self.assertFalse(
            any("publish_ready" in str(f) for f in payload["failures"]),
            payload["failures"],
        )


if __name__ == "__main__":
    unittest.main(verbosity=2)
