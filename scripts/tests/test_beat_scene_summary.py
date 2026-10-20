#!/usr/bin/env python3
"""分镜场景概要测试（5 号待办）

- beat sheet 每 Beat 的 summary 必须是可读的场景方向，不含 [待填充]
- 概要引用本章目标与 Beat 类型，末 Beat 带章末悬念提示
- 微冲突 / 情绪弧线 有内容
- 写作包 §二 分镜直接显示真实概要，不再是「（场景由你按本节扩写提示设计）」

运行方式:
    python3 scripts/tests/test_beat_scene_summary.py
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

BEATS = SCRIPT_DIR / "beat_sheet_generator.py"
EXECUTOR = SCRIPT_DIR / "novel_flow_executor.py"

GOAL = "陈砚在码头与周遇对峙，名单上出现第三个名字"

_ONBOARDING = [
    "--target-audience", "起点男频 25-35",
    "--writing-style", "悬疑推理",
    "--core-taboo", "不写真实案件改编",
    "--automation-level", "半自动",
    "--target-words", "1000000",
    "--protagonist", "陈砚",
    "--protagonist-goal", "查清三年前的旧案",
    "--core-conflict", "失踪名单背后的旧案",
    "--core-hook", "一张名单牵出三条人命",
]


def run(script: Path, *args):
    p = subprocess.run([sys.executable, str(script), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(p.stdout)


class TestBeatSceneSummary(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_beats_"))

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def _generate(self, beat_count: int = 4) -> dict:
        run(BEATS, "generate", "--project-root", str(self.project_root),
            "--chapter", "2", "--chapter-goal", GOAL, "--beat-count", str(beat_count))
        return json.loads(
            (self.project_root / "00_memory" / "beats" / "ch0002_beat_sheet.json")
            .read_text(encoding="utf-8")
        )

    def test_every_beat_has_readable_summary(self):
        sheet = self._generate()
        for beat in sheet["beats"]:
            summary = beat["summary"]
            self.assertNotIn("[待填充]", summary)
            self.assertGreater(len(summary), 20, summary)
            self.assertIn("围绕「", summary)
            self.assertTrue(beat["micro_conflict"], beat)
            self.assertTrue(beat["emotion_target"], beat)

    def test_summary_carries_goal_and_type(self):
        sheet = self._generate()
        first = sheet["beats"][0]
        self.assertIn("陈砚在码头与周遇对峙", first["summary"])
        self.assertIn("冲突", first["summary"])
        self.assertIn("开场", first["summary"])

    def test_last_beat_promises_chapter_hook(self):
        sheet = self._generate()
        self.assertIn("章末", sheet["beats"][-1]["summary"])
        self.assertIn("悬念", sheet["beats"][-1]["summary"])

    def test_expand_prompt_has_no_blank_fields(self):
        self._generate()
        run(BEATS, "expand", "--project-root", str(self.project_root),
            "--chapter", "2", "--beat-id", "1")
        text = (self.project_root / "00_memory" / "beats" / "ch0002_beat01_expand.md") \
            .read_text(encoding="utf-8")
        self.assertNotIn("[待填充]", text)
        self.assertNotIn("**地点**: \n", text)
        self.assertIn("未指定", text)

    def test_writing_package_shows_real_summaries(self):
        run(EXECUTOR, "one-click", "--project-root", str(self.project_root),
            "--title", "雨夜名单", "--genre", "悬疑",
            "--idea", "旧港区失踪名单牵出三年前的旧案", *_ONBOARDING)
        payload = run(EXECUTOR, "continue-write", "--project-root", str(self.project_root),
                      "--query", GOAL)
        package = Path(payload["writing_package"]).read_text(encoding="utf-8")
        self.assertNotIn("（场景由你按本节扩写提示设计）", package)
        self.assertIn("围绕「", package)
        self.assertIn("微冲突", package)


if __name__ == "__main__":
    unittest.main(verbosity=2)
