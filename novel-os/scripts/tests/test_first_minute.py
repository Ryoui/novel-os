#!/usr/bin/env python3
"""首分钟体验测试（开书引导 / 回执 / 立项摘要页）

- onboarding 剧本：5 题、每题有问句+选项、3 个套餐、斜杠命令模板，且不写任何文件
- 开书成功返回 receipt（人话）与 project_brief（含文件导航），next_step 是斜杠命令语气
- 缺要素时给斜杠命令示例 + 追问指引，且不写文件
- 自动化等级接受「半自动（每 10 章确认）」这类带说明写法
- outline_gaps 报具体字段名而不是「计划中含未填字段」

运行方式:
    python3 scripts/tests/test_first_minute.py
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

EXECUTOR = SCRIPT_DIR / "novel_flow_executor.py"

FIVE = [
    "--target-audience", "起点男频 25-35",
    "--writing-style", "悬疑推理",
    "--core-taboo", "不写真实案件改编",
    "--automation-level", "半自动",
    "--target-words", "1000000",
]


def run(*args):
    p = subprocess.run([sys.executable, str(EXECUTOR), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(p.stdout)


class TestOnboardingScript(unittest.TestCase):
    def test_script_has_questions_options_presets(self):
        payload = run("onboarding")
        self.assertTrue(payload["ok"])
        self.assertEqual(len(payload["steps"]), 5)
        for step in payload["steps"]:
            self.assertTrue(step["ask"], step)
            self.assertGreaterEqual(len(step["options"]), 3, step)
            self.assertTrue(step["param"].startswith("--"), step)
        self.assertEqual(len(payload["presets"]), 3)
        for preset in payload["presets"]:
            self.assertEqual(len(preset["values"]), 5, preset)
        self.assertIn("/一键开书", payload["slash_command"])
        self.assertIn("如何", payload["how_to_use"][0] + "如何")

    def test_onboarding_writes_nothing(self):
        project_root = Path(tempfile.mkdtemp(prefix="novel_onb_")) / "demo"
        run("onboarding", "--project-root", str(project_root))
        self.assertFalse(project_root.exists(), "onboarding 不得写任何文件")
        shutil.rmtree(project_root.parent, ignore_errors=True)


class TestOpenBookReceipt(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_receipt_")) / "demo"

    def tearDown(self):
        shutil.rmtree(self.project_root.parent, ignore_errors=True)

    def _open(self, *extra):
        return run("one-click", "--project-root", str(self.project_root),
                   "--title", "雨夜名单", "--genre", "悬疑",
                   "--idea", "旧港区失踪名单牵出三年前的旧案", *FIVE, *extra)

    def test_receipt_is_human_readable(self):
        payload = self._open()
        receipt = payload["receipt"]
        self.assertIn("《雨夜名单》已开书", receipt)
        self.assertIn("目标读者", receipt)
        self.assertIn("285 章", receipt)          # 1,000,000 / 3500
        self.assertIn("还差", receipt)
        self.assertIn("回一句「继续」就行", receipt)
        # 不是文件清单
        self.assertNotIn("00_memory/character_tracker.md", receipt)

    def test_project_brief_written_with_navigation(self):
        payload = self._open()
        brief_path = Path(payload["project_brief"])
        self.assertTrue(brief_path.exists())
        brief = brief_path.read_text(encoding="utf-8")
        self.assertIn("立项摘要", brief)
        self.assertIn("开书五要素（已确认）", brief)
        self.assertIn("这些文件是干什么的", brief)
        self.assertIn("这是你的成品", brief)

    def test_gaps_are_field_names(self):
        payload = self._open()
        gaps = payload["outline_gaps"]
        self.assertTrue(gaps)
        joined = "、".join(gaps)
        self.assertIn("核心卖点", joined)
        self.assertNotIn("计划中含未填字段", joined)

    def test_next_step_speaks_slash_not_python(self):
        payload = self._open()
        self.assertIn("/继续写", payload["next_step"])
        self.assertNotIn("python3 scripts/", payload["next_step"])
        self.assertIn("receipt", payload["next_step"])

    def test_automation_level_with_explanation_normalized(self):
        payload = run("one-click", "--project-root", str(self.project_root),
                      "--title", "雨夜名单", "--genre", "悬疑", "--idea", "旧港区失踪名单",
                      "--target-audience", "起点男频 25-35", "--writing-style", "悬疑推理",
                      "--core-taboo", "不写真实案件改编",
                      "--automation-level", "半自动（每 10 章确认）",
                      "--target-words", "1000000")
        self.assertTrue(payload["ok"], payload)
        self.assertEqual(payload["automation_level"], "半自动")

    def test_missing_elements_point_to_onboarding_and_slash(self):
        payload = run("one-click", "--project-root", str(self.project_root),
                      "--title", "雨夜名单", "--genre", "悬疑", "--idea", "x")
        self.assertEqual(payload["error"], "onboarding_incomplete")
        self.assertIn("onboarding", payload["how_to_ask"])
        self.assertIn("/一键开书", payload["next_step"])
        self.assertNotIn("python3 scripts/", payload["next_step"])
        self.assertFalse(self.project_root.exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
