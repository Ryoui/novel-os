#!/usr/bin/env python3
"""正文纯净度检查测试（P0-1）

验证门禁新增的 body_metadata_purity：
- 元信息残留 / 占位人名 → 判死
- 正常叙述里的单次「主角」→ 不误杀
- 项目白名单可放行

运行方式:
    python3 scripts/tests/test_body_metadata_purity.py
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


CLEAN_BODY = (
    "# 第5章 雨夜名单\n\n"
    "陈砚推开木门，雨声一下子涌进来。周遇靠在窗边，手里捏着半张湿透的名单。\n\n"
    "两人谁也没先开口。楼下的街灯灭了一盏，剩下的那盏把雨水照成一道斜线。\n\n"
    "「第三个人不是我们的人。」周遇把名单摊在桌上，指尖压住最后一个名字。\n\n"
    "陈砚没有去看那张纸。他先关上了门，才说：「从头讲。」\n"
)


class TestBodyMetadataDetection(unittest.TestCase):
    """check_body_metadata 单元行为"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="novel_purity_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _check(self, body: str, allow_names=None, allow_patterns=None):
        from chapter_gate_check import check_body_metadata

        path = self.tmpdir / "第5章.md"
        path.write_text(body, encoding="utf-8")
        return check_body_metadata(path, allow_names or set(), allow_patterns or [])

    def test_constraint_prompt_leak_fails(self):
        ok, msg, _ = self._check(
            "# 第3章\n\n[写作约束]\n- 本章禁止揭露：终极BOSS身份\n\n他走进雨里。"
        )
        self.assertFalse(ok)
        self.assertIn("方括号元信息块", msg)

    def test_python_dict_residue_fails(self):
        ok, msg, _ = self._check(
            "# 第3章\n\n事情比预想的复杂。{'ok': True, 'command': 'check' —— 他继续走。"
        )
        self.assertFalse(ok)
        self.assertIn("代码/路径残留", msg)

    def test_note_marker_fails(self):
        ok, msg, _ = self._check("# 第3章\n\n他推开门。（注：此处待补充）屋里没人。")
        self.assertFalse(ok)
        self.assertIn("注记标记", msg)

    def test_draft_stub_fails_with_stub_reason(self):
        ok, msg, details = self._check(
            "# 第1章\n\n<!-- NOVEL_FLOW_STUB -->\n\n## 正文\n[待写]"
        )
        self.assertFalse(ok)
        self.assertIn("占位草稿", msg)
        self.assertTrue(details["stub"])

    def test_placeholder_name_repeated_fails(self):
        ok, msg, _ = self._check(
            "# 第5章\n\n主角走进房间。主角看了看。主角又坐下。主角起身。"
        )
        self.assertFalse(ok)
        self.assertIn("占位人名", msg)
        self.assertIn("主角", msg)

    def test_placeholder_name_in_dialogue_tag_fails(self):
        ok, msg, _ = self._check("# 第5章\n\n同伴说：「走吧。」")
        self.assertFalse(ok)
        self.assertIn("占位人名", msg)

    def test_single_placeholder_name_in_narration_passes(self):
        """防误杀：叙述句里出现一次「主角」不算污染。"""
        ok, msg, _ = self._check(
            "# 第5章\n\n主角走进了房间，环顾四周，看到墙上挂着一幅画。风从窗缝里钻进来。"
        )
        self.assertTrue(ok, msg)

    def test_allowlist_names_pass(self):
        ok, msg, _ = self._check(
            "# 第5章\n\n主角走进房间。主角看了看。主角又坐下。主角起身。",
            allow_names={"主角"},
        )
        self.assertTrue(ok, msg)

    def test_allowlist_patterns_pass(self):
        ok, msg, _ = self._check(
            "# 第5章\n\n[此处填写]这一幕的主角是陈砚。", allow_patterns=["[此处填写]"]
        )
        self.assertTrue(ok, msg)

    def test_clean_body_passes(self):
        ok, msg, _ = self._check(CLEAN_BODY)
        self.assertTrue(ok, msg)


class TestGateIntegration(unittest.TestCase):
    """门禁接线：检查项进入 gate_result.json 并写进 failures"""

    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_purity_gate_"))
        for d in ["00_memory", "02_knowledge_base", "03_manuscript",
                  "04_editing/gate_artifacts"]:
            (self.project_root / d).mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def _run_gate(self, body: str):
        chapter = self.project_root / "03_manuscript" / "第5章-雨夜名单.md"
        chapter.write_text(body, encoding="utf-8")
        proc = subprocess.run(
            [sys.executable, str(SCRIPT_DIR / "chapter_gate_check.py"),
             "--project-root", str(self.project_root),
             "--chapter-file", str(chapter)],
            capture_output=True, text=True, encoding="utf-8",
        )
        payload = json.loads(proc.stdout)
        check = next(
            c for c in payload["checks"] if c.get("name") == "body_metadata_purity"
        )
        return payload, check

    def test_gate_marks_contaminated_chapter_failed(self):
        payload, check = self._run_gate(
            "# 第5章\n\n[相关历史剧情]\n- 第1章：## 本章目标\n\n[写作约束]\n"
            "- 本章禁止揭露：终极BOSS身份\n\n事情比预想的复杂。"
        )
        self.assertFalse(check["ok"])
        self.assertIn("body_metadata_purity", " ".join(payload["failures"]))
        self.assertFalse(payload["passed"])

    def test_gate_records_pass_for_clean_body(self):
        """正文干净时该检查项本身必须为通过（其他产物缺失不应牵连本项）。"""
        _, check = self._run_gate(CLEAN_BODY)
        self.assertTrue(check["ok"], check["message"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
