#!/usr/bin/env python3
"""novel_flow_executor 端到端回归测试。"""

import json
import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EXECUTOR = ROOT / "novel_flow_executor.py"
PY = "python3"


def run_cmd(args):
    proc = subprocess.run([PY, str(EXECUTOR), *args], capture_output=True, text=True)
    if proc.returncode not in (0, 1):
        raise AssertionError(f"命令异常: rc={proc.returncode}\nstdout={proc.stdout}\nstderr={proc.stderr}")
    try:
        payload = json.loads(proc.stdout)
    except Exception as exc:
        raise AssertionError(f"输出不是 JSON: {proc.stdout}") from exc
    return proc.returncode, payload


def _clean_chapter_body() -> str:
    """构造一段干净正文：真实人名、有对白、段落互不重复、过 2500 字。"""
    return "# 第2章 短章\n\n" + "\n\n".join(
        f"第{i}次走进旧港区那间仓库，陈砚先数了一遍墙上的钉子，{i + 12}根，一根没少。"
        f"他把手电压低，光柱贴着地皮扫过去，照见一层新落的灰。"
        f"周遇在门口守着，回头低声说：“这是第{i}回了，脚印还没干，有人比我们先到。”"
        for i in range(1, 31)
    ) + "\n"


class TestNovelFlowExecutor(unittest.TestCase):
    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="novel_flow_exec_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def test_one_click_init(self):
        _, payload = run_cmd([
            "one-click",
            "--project-root",
            str(self.tmpdir),
            "--title",
            "雾港回声",
            "--genre",
            "悬疑",
            "--idea",
            "主角在旧港区发现失踪名单",
        ])
        self.assertTrue(payload.get("ok"))
        self.assertTrue((self.tmpdir / "00_memory" / "novel_plan.md").exists())
        self.assertTrue((self.tmpdir / "03_manuscript" / "第1章-开篇待写.md").exists())

    def test_continue_write_awaits_agent_draft(self):
        """无 LLM 时不再伪造正文：产出写作包，等宿主 Agent 写（A 方案）。"""
        run_cmd([
            "one-click",
            "--project-root",
            str(self.tmpdir),
            "--title",
            "雾港回声",
            "--genre",
            "悬疑",
            "--idea",
            "陈砚在旧港区发现失踪名单",
        ])
        _, payload = run_cmd([
            "continue-write",
            "--project-root",
            str(self.tmpdir),
            "--query",
            "陈砚在站台发现名单，与周遇发生冲突",
        ])
        self.assertTrue(payload.get("ok"))
        self.assertTrue(payload.get("awaiting_draft"))
        self.assertFalse(payload.get("auto_draft_applied"))
        self.assertEqual(payload.get("draft_provider_used"), "agent")
        self.assertIsNone(payload.get("llm_error_msg"))

        # 正文保持占位，CLI 不得自行成稿
        chapter_text = Path(payload["chapter_file"]).read_text(encoding="utf-8")
        self.assertIn("NOVEL_FLOW_STUB", chapter_text)
        self.assertNotIn("[写作约束]", chapter_text)

        # 写作包必须落盘，并明确交付要求
        package = Path(payload["writing_package"])
        self.assertTrue(package.exists(), f"写作包缺失: {package}")
        package_text = package.read_text(encoding="utf-8")
        self.assertIn("本章写作包", package_text)
        self.assertIn("本章目标", package_text)
        self.assertIn("交付要求", package_text)
        self.assertIn("占位名", package_text)
        # 扩写提示必须内联，而不是只给路径；且不得残留约束块标题行
        self.assertIn("扩写指令", package_text)
        self.assertIn("通用扩写要求", package_text)
        self.assertNotIn("\n[写作约束]", package_text)
        self.assertNotIn("\n[相关历史剧情]", package_text)
        self.assertIn("next_step", payload)
        self.assertIn("写作包已就绪", payload["next_step"])

    def test_continue_write_template_provider_is_explicit_only(self):
        """--draft-provider template 仍可用，但产物会被正文纯净度判死。"""
        run_cmd([
            "one-click",
            "--project-root",
            str(self.tmpdir),
            "--title",
            "雾港回声",
            "--genre",
            "悬疑",
            "--idea",
            "陈砚在旧港区发现失踪名单",
        ])
        _, payload = run_cmd([
            "continue-write",
            "--project-root",
            str(self.tmpdir),
            "--query",
            "陈砚在站台发现名单，与周遇发生冲突",
            "--draft-provider",
            "template",
            "--no-rollback-on-failure",
        ])
        self.assertTrue(payload.get("auto_draft_applied"))
        self.assertFalse(payload.get("gate_passed_final"))
        failures = (payload.get("gate_result") or {}).get("failures") or []
        self.assertTrue(
            any(str(f).startswith("body_metadata_purity") for f in failures),
            f"脚手架稿应被正文纯净度判死，实际 failures={failures}",
        )
        chapter_text = Path(payload["chapter_file"]).read_text(encoding="utf-8")
        self.assertNotIn("[写作约束]", chapter_text)
        self.assertNotIn("[相关历史剧情]", chapter_text)

    def test_continue_write_auto_retry_fix_kb(self):
        run_cmd([
            "one-click",
            "--project-root",
            str(self.tmpdir),
            "--title",
            "雾港回声",
            "--genre",
            "悬疑",
            "--idea",
            "主角在旧港区发现失踪名单",
        ])
        kb_bad = self.tmpdir / "02_knowledge_base" / "第99章-误放.md"
        kb_bad.write_text("误放章节", encoding="utf-8")
        chapter = self.tmpdir / "03_manuscript" / "第2章-短章.md"
        chapter.write_text(_clean_chapter_body(), encoding="utf-8")

        _, payload = run_cmd([
            "continue-write",
            "--project-root",
            str(self.tmpdir),
            "--chapter-file",
            str(chapter),
            "--query",
            "陈砚继续追查名单",
            "--min-paragraphs",
            "2",
        ])
        actions = payload.get("auto_retry_actions", [])
        self.assertTrue(any("迁移误放章节" in x for x in actions), actions)
        self.assertFalse(kb_bad.exists())

    def test_continue_write_idempotent_cache_hit(self):
        run_cmd([
            "one-click",
            "--project-root",
            str(self.tmpdir),
            "--title",
            "雾港回声",
            "--genre",
            "悬疑",
            "--idea",
            "主角在旧港区发现失踪名单",
        ])
        chapter = self.tmpdir / "03_manuscript" / "第2章-短章.md"
        chapter.write_text(_clean_chapter_body(), encoding="utf-8")
        common_args = [
            "continue-write",
            "--project-root",
            str(self.tmpdir),
            "--chapter-file",
            str(chapter),
            "--query",
            "陈砚继续调查失踪名单",
            "--no-auto-draft",
            "--no-auto-retry",
            "--min-chars",
            "100",
            "--min-paragraphs",
            "2",
            "--min-sentences",
            "3",
        ]
        _, p1 = run_cmd(common_args)
        _, p2 = run_cmd(common_args)
        _, p3 = run_cmd(common_args)
        self.assertTrue(p1.get("ok"))
        self.assertTrue(p2.get("ok"))
        self.assertTrue(p3.get("idempotent_hit"))

    def test_continue_write_rollback_on_failure(self):
        run_cmd([
            "one-click",
            "--project-root",
            str(self.tmpdir),
            "--title",
            "雾港回声",
            "--genre",
            "悬疑",
            "--idea",
            "主角在旧港区发现失踪名单",
        ])
        chapter = self.tmpdir / "03_manuscript" / "第2章-短章.md"
        chapter.write_text("# 第2章 短章\n\n这是一段极短正文。", encoding="utf-8")
        before = chapter.read_text(encoding="utf-8")

        _, payload = run_cmd([
            "continue-write",
            "--project-root",
            str(self.tmpdir),
            "--chapter-file",
            str(chapter),
            "--query",
            "主角推进剧情",
            "--no-auto-draft",
            "--no-auto-retry",
            "--min-paragraphs",
            "12",
            "--force-run",
        ])
        self.assertFalse(payload.get("ok"))
        self.assertTrue(payload.get("rollback_applied"))
        after = chapter.read_text(encoding="utf-8")
        self.assertEqual(before, after)

    def test_continue_write_auto_fix_quality_baseline(self):
        run_cmd([
            "one-click",
            "--project-root",
            str(self.tmpdir),
            "--title",
            "雾港回声",
            "--genre",
            "悬疑",
            "--idea",
            "主角在旧港区发现失踪名单",
        ])
        chapter = self.tmpdir / "03_manuscript" / "第2章-短章.md"
        # 使用已有的草稿内容而非极短文本，避免填充内容引发其他质量失败
        chapter.write_text(
            "# 第2章 短章\n\n"
            "主角在旧港区发现了一份失踪名单，上面有十几个名字。\n\n"
            "他仔细翻看，发现其中几个名字与最近的案件有关联。\n\n"
            "这不仅仅是一份名单，而是一条线索。",
            encoding="utf-8",
        )

        _, payload = run_cmd([
            "continue-write",
            "--project-root",
            str(self.tmpdir),
            "--chapter-file",
            str(chapter),
            "--query",
            "主角继续调查并与同伴沟通",
            "--no-auto-draft",
            "--auto-retry",
            "--min-chars",
            "100",  # 降低阈值，已有内容足够
            "--min-paragraphs",
            "2",  # 降低阈值，已有内容足够
            "--min-sentences",
            "3",  # 降低阈值，已有内容足够
            "--pacing-mode",
            "fast",
            "--no-rollback-on-failure",  # 避免 rollback 覆盖质量修复
            "--force-run",
        ])
        # 验证：不再产生任何"补字"动作，正文内容不被伪造
        actions = payload.get("auto_retry_actions", [])
        self.assertFalse(
            any("质量最小修复" in x for x in actions),
            f"不应再出现造字修复动作，实际 actions={actions}",
        )
        # 验证：rollback 没有发生（内容被保留）
        self.assertFalse(payload.get("rollback_applied", False))


class TestPacingAndGateFixes(unittest.TestCase):
    """P1-3/P1-4/P0-2 修复专项测试。"""

    def setUp(self):
        self.tmpdir = Path(tempfile.mkdtemp(prefix="novel_pacing_test_"))

    def tearDown(self):
        shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _init_project(self):
        run_cmd([
            "one-click", "--project-root", str(self.tmpdir),
            "--title", "修复测试", "--genre", "悬疑", "--idea", "测试用例",
        ])

    def test_evaluate_quality_standard_high_skip_density_fails(self):
        """standard 模式极高概括跳过密度（>0.5）应升级为硬失败。"""
        import sys
        sys.path.insert(0, str(ROOT))
        import importlib
        nfe = importlib.import_module("novel_flow_executor")
        import argparse

        # 构造一段极高概括跳过密度的文本（几乎全是跳过句）
        skip_heavy = (
            "经过一番苦修，终于练功大成。\n\n"
            "此后数日，没过多久便突破瓶颈。\n\n"
            "转眼间，一切都完成了。\n\n"
            "随后又经过一番历练，很快就完成了任务。\n\n"
            "苦修数月，不知不觉就成功了。\n\n"
        ) * 20  # 重复 20 次保证字数

        args = argparse.Namespace(
            min_chars=100,
            min_paragraphs=2,
            min_dialogue_ratio=0.0,
            max_dialogue_ratio=1.0,
            min_sentences=1,
            pacing_mode="standard",
        )
        result = nfe.evaluate_quality(skip_heavy, args)
        failures = result.get("failures", [])
        self.assertTrue(
            any("pacing_skip_density_critical" in f for f in failures),
            f"standard 模式极高 skip density 应硬失败，实际 failures={failures}",
        )

    def test_evaluate_quality_immersive_skip_density_fails(self):
        """immersive 模式概括跳过密度超阈值应硬失败。"""
        import sys
        sys.path.insert(0, str(ROOT))
        import importlib
        nfe = importlib.import_module("novel_flow_executor")
        import argparse

        skip_text = ("经过一番苦修练功大成。\n\n此后便突破了瓶颈。\n\n" ) * 30

        args = argparse.Namespace(
            min_chars=100, min_paragraphs=2,
            min_dialogue_ratio=0.0, max_dialogue_ratio=1.0,
            min_sentences=1, pacing_mode="immersive",
        )
        result = nfe.evaluate_quality(skip_text, args)
        failures = result.get("failures", [])
        self.assertTrue(
            any("pacing_skip_density_too_high" in f for f in failures),
            f"immersive 模式 skip density 应硬失败，实际 failures={failures}",
        )

    def test_publish_ready_reflects_quality_failure(self):
        """质量未通过时，publish_ready.md 应写入 FAIL 关键词，而非 PASS。"""
        import sys
        sys.path.insert(0, str(ROOT))
        import importlib
        nfe = importlib.import_module("novel_flow_executor")

        self._init_project()
        chapter_files = list((self.tmpdir / "03_manuscript").glob("第*章*.md"))
        self.assertTrue(chapter_files, "初始化应创建章节文件")
        chapter_path = chapter_files[0]

        fake_quality: dict = {
            "ok": False,
            "char_count": 100,
            "paragraph_count": 2,
            "dialogue_ratio": 0.05,
            "ai_phrase_hits": [],
            "failures": ["char_count<2500 (current: 100)"],
        }
        nfe.write_gate_artifacts(self.tmpdir, chapter_path, "测试查询", fake_quality, None)

        publish_path = (
            self.tmpdir / "04_editing" / "gate_artifacts"
            / nfe.slugify(chapter_path.stem) / "publish_ready.md"
        )
        self.assertTrue(publish_path.exists(), "publish_ready.md 应被写入")
        content = publish_path.read_text(encoding="utf-8")
        self.assertIn("FAIL", content, "质量不达标时 publish_ready.md 应含 FAIL 关键词")
        self.assertNotIn("PASS", content, "质量不达标时 publish_ready.md 不应含 PASS")

    def test_decompose_overrides_disable_memory_update(self):
        """_decompose_beat_scenes 的 config_overrides 必须包含 auto_update_memory=False。"""
        import sys
        sys.path.insert(0, str(ROOT))
        import importlib
        nfe = importlib.import_module("novel_flow_executor")
        import inspect, textwrap

        src = inspect.getsource(nfe._decompose_beat_scenes)
        self.assertIn(
            "auto_update_memory",
            src,
            "_decompose_beat_scenes 必须在 decompose_overrides 中包含 auto_update_memory",
        )


if __name__ == "__main__":
    unittest.main()
