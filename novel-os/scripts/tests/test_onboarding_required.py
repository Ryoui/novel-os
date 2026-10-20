#!/usr/bin/env python3
"""开书五要素强制 + 立项闸口测试（2 号待办）

- 任一要素缺失 → 拒绝开书（ok:false, error=onboarding_incomplete），且不写任何文件
- 五要素齐 → idea_seed 落盘结构化确认卡，锚点使用派生章节数
- 核心禁区 → global_forbidden_reveals（不再硬编码「终极BOSS身份」）
- 计划仍有 [待补全] → continue-write 返回 awaiting_outline，不建章节桩、不出写作包
- 补齐计划后 → 正常进入写作备料

运行方式:
    python3 scripts/tests/test_onboarding_required.py
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

FIVE = {
    "--target-audience": "起点男频 25-35",
    "--writing-style": "悬疑推理",
    "--core-taboo": "不写真实案件改编",
    "--automation-level": "半自动",
    "--target-words": "1000000",
}
PLAN_FIELDS = {
    "--protagonist": "陈砚",
    "--protagonist-goal": "查清三年前的旧案",
    "--core-conflict": "失踪名单背后的旧案",
    "--core-hook": "一张名单牵出三条人命",
}


def run(*args):
    p = subprocess.run([sys.executable, str(EXECUTOR), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(p.stdout)


def one_click_args(project_root: Path, overrides: dict) -> list:
    args = ["one-click", "--project-root", str(project_root),
            "--title", "雨夜名单", "--genre", "悬疑", "--idea", "旧港区失踪名单牵出旧案"]
    flags = {**FIVE, **PLAN_FIELDS, **overrides}
    for k, v in flags.items():
        if v is None:
            continue
        args += [k, v]
    return args


class TestOnboardingRequired(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_onboarding_")) / "demo"

    def tearDown(self):
        shutil.rmtree(self.project_root.parent, ignore_errors=True)

    def test_missing_any_element_refuses_to_open_project(self):
        cases = {
            "--target-audience": "缺目标读者",
            "--writing-style": "缺写作风格",
            "--core-taboo": "缺核心禁区",
            "--automation-level": "缺自动化等级",
            "--target-words": "缺目标规模",
        }
        for flag in cases:
            with self.subTest(flag=flag):
                payload = run(*one_click_args(self.project_root, {flag: None}))
                self.assertFalse(payload.get("ok"))
                self.assertEqual(payload.get("error"), "onboarding_incomplete")
                self.assertTrue(
                    any(flag in m for m in payload.get("missing", [])),
                    payload.get("missing"),
                )
                self.assertFalse(self.project_root.exists(), "拒绝开书时不得写任何文件")

    def test_invalid_style_and_level_rejected(self):
        for overrides, hint in (
            ({"--writing-style": "玄幻爽文"}, "不在支持范围"),
            ({"--automation-level": "全手动"}, "不合法"),
            ({"--target-words": "5000"}, "过小"),
        ):
            with self.subTest(overrides=overrides):
                payload = run(*one_click_args(self.project_root, overrides))
                self.assertFalse(payload.get("ok"))
                self.assertTrue(
                    any(hint in m for m in payload.get("missing", [])),
                    payload.get("missing"),
                )

    def test_complete_onboarding_writes_structured_seed(self):
        payload = run(*one_click_args(self.project_root, {}))
        self.assertTrue(payload.get("ok"), payload)
        self.assertEqual(payload.get("outline_gaps"), [])

        seed = (self.project_root / "00_memory" / "idea_seed.md").read_text(encoding="utf-8")
        for line in ("## 开书五要素（已确认）", "- 目标读者：起点男频 25-35",
                     "- 写作风格：悬疑推理", "- 核心禁区：不写真实案件改编",
                     "- 自动化等级：半自动", "- 目标规模：1000000 字"):
            self.assertIn(line, seed)
        # 空模板章节必须被填上，不能留空标题
        self.assertIn("## 一句话脑洞\n旧港区失踪名单牵出旧案", seed)

        anchors = json.loads(
            (self.project_root / "00_memory" / "outline_anchors.json").read_text(encoding="utf-8")
        )
        self.assertEqual(anchors["total_chapters_target"], 285)
        self.assertEqual(anchors["global_forbidden_reveals"], ["不写真实案件改编"])
        self.assertNotIn("终极BOSS身份", json.dumps(anchors, ensure_ascii=False))

    def test_incomplete_plan_blocks_writing(self):
        payload = run(*one_click_args(self.project_root, {
            "--protagonist": None, "--core-conflict": None, "--core-hook": None,
            "--protagonist-goal": None,
        }))
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("outline_gaps"))
        self.assertTrue(Path(payload["outline_task"]).exists())

        writing = run("continue-write", "--project-root", str(self.project_root),
                      "--query", "陈砚查看码头")
        self.assertTrue(writing.get("ok"))
        self.assertTrue(writing.get("awaiting_outline"))
        self.assertTrue(writing.get("outline_gaps"))
        self.assertNotIn("writing_package", writing)
        task_text = Path(writing["outline_task"]).read_text(encoding="utf-8")
        self.assertIn("立项补全任务", task_text)
        self.assertIn("核心卖点", task_text)

    def test_outline_gate_leaves_no_execution_lock(self):
        """立项闸口早退不得留下执行锁，否则下一次 /继续写 会报 another_run_in_progress。"""
        run(*one_click_args(self.project_root, {
            "--protagonist": None, "--core-conflict": None, "--core-hook": None,
            "--protagonist-goal": None,
        }))
        first = run("continue-write", "--project-root", str(self.project_root),
                    "--query", "陈砚查看码头")
        self.assertTrue(first.get("awaiting_outline"))
        self.assertFalse((self.project_root / ".flow" / "continue_write.lock").exists(),
                         "早退后仍留有执行锁")

        second = run("continue-write", "--project-root", str(self.project_root),
                     "--query", "陈砚查看码头")
        self.assertTrue(second.get("awaiting_outline"), second)
        self.assertNotEqual(second.get("error"), "another_run_in_progress")

    def test_complete_plan_proceeds_to_package(self):
        run(*one_click_args(self.project_root, {}))
        writing = run("continue-write", "--project-root", str(self.project_root),
                      "--query", "陈砚查看码头")
        self.assertTrue(writing.get("ok"))
        self.assertFalse(writing.get("awaiting_outline"))
        self.assertTrue(writing.get("awaiting_draft"))
        self.assertTrue(Path(writing["writing_package"]).exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
