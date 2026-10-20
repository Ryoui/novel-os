#!/usr/bin/env python3
"""章节自动改名 + 写作包内容测试

- 正文写好后「第N章-待写.md」自动改成真实标题，并迁移门禁产物目录
- 占位桩与已有正式名不受影响
- 写作包必须写明字数下限、不得重复「本章目标」

运行方式:
    python3 scripts/tests/test_chapter_naming_and_package.py
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

CHAPTER_BODY = "# 第2章 后巷的脚印\n\n" + "\n\n".join(
    f"陈砚第{i}次走进那条后巷，脚下的水没过鞋面，砖缝里积着半寸深的泥。"
    f"周遇举着伞跟在半步之后，伞面上砸出的声音盖过了别的东西。"
    f"“这儿有人走过。”她说，“脚印比刚才深。”"
    for i in range(1, 12)
) + "\n"


def _write_pacing_review(project_root: Path, chapter: Path) -> None:
    """补一份语义版节奏审查（门禁默认强制要求它）。"""
    gate_dir = project_root / "04_editing" / "gate_artifacts" / chapter.stem
    gate_dir.mkdir(parents=True, exist_ok=True)
    (gate_dir / "pacing_review.md").write_text(
        "# 节奏审查报告\n\n## 综合结论\n节奏审查: 通过\n失败原因: 无\n", encoding="utf-8"
    )


_ONBOARDING_ARGS = [
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


def run(*args):
    if args and args[0] == "one-click" and "--target-audience" not in args:
        args = (*args, *_ONBOARDING_ARGS)
    p = subprocess.run([sys.executable, str(EXECUTOR), *args],
                       capture_output=True, text=True, encoding="utf-8")
    return json.loads(p.stdout)


class TestAutoNameChapter(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_rename_"))
        (self.project_root / "03_manuscript").mkdir(parents=True, exist_ok=True)
        (self.project_root / "04_editing" / "gate_artifacts").mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def _write(self, name: str, text: str) -> Path:
        path = self.project_root / "03_manuscript" / name
        path.write_text(text, encoding="utf-8")
        return path

    def test_placeholder_renamed_to_real_title(self):
        from novel_flow_executor import auto_name_chapter, slugify

        path = self._write("第2章-待写.md", CHAPTER_BODY)
        old_gate_dir = self.project_root / "04_editing" / "gate_artifacts" / slugify(path.stem)
        old_gate_dir.mkdir(parents=True, exist_ok=True)
        (old_gate_dir / "pacing_review.md").write_text("节奏审查: 通过\n", encoding="utf-8")

        renamed = auto_name_chapter(self.project_root, path)
        self.assertEqual(renamed.name, "第2章-后巷的脚印.md")
        self.assertTrue(renamed.exists())
        self.assertFalse(path.exists())
        # 门禁产物（含 Agent 手写文件）随章节一起迁移
        new_gate_dir = self.project_root / "04_editing" / "gate_artifacts" / slugify(renamed.stem)
        self.assertTrue((new_gate_dir / "pacing_review.md").exists())

    def test_stub_not_renamed(self):
        from novel_flow_executor import auto_name_chapter

        path = self._write("第2章-待写.md", "# 第2章 待写\n\n<!-- NOVEL_FLOW_STUB -->\n\n## 正文\n[待写]\n")
        self.assertEqual(auto_name_chapter(self.project_root, path), path)

    def test_already_named_chapter_untouched(self):
        from novel_flow_executor import auto_name_chapter

        path = self._write("第2章-码头对峙.md", CHAPTER_BODY)
        self.assertEqual(auto_name_chapter(self.project_root, path), path)

    def test_missing_title_not_renamed(self):
        from novel_flow_executor import auto_name_chapter

        path = self._write("第2章-待写.md", CHAPTER_BODY.replace("# 第2章 后巷的脚印", "# 第2章"))
        self.assertEqual(auto_name_chapter(self.project_root, path), path)


class TestWritingPackageContent(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_pkg_"))

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def test_package_declares_floor_and_avoids_repeated_goal(self):
        run("one-click", "--project-root", str(self.project_root), "--title", "雨夜名单",
            "--genre", "悬疑", "--idea", "陈砚在旧港区发现失踪名单")
        payload = run("continue-write", "--project-root", str(self.project_root),
                      "--query", "陈砚在仓库发现对面有人监视")
        self.assertTrue(payload.get("awaiting_draft"))

        text = Path(payload["writing_package"]).read_text(encoding="utf-8")
        self.assertIn("字数下限", text)
        self.assertIn("分镜建议篇幅", text)
        # 本章目标只在 §一 出现一次，不再每个 Beat 抄一遍
        self.assertEqual(text.count("**本章目标**"), 0)
        self.assertIn("扩写指令", text)
        self.assertNotIn("\n[写作约束]", text)


class TestCacheKeyRespectsStrictFlags(unittest.TestCase):
    """严格模式开关必须进幂等缓存键，不能被上一次缓存顶掉。"""

    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="novel_cache_"))
        run("one-click", "--project-root", str(self.project_root), "--title", "雨夜名单",
            "--genre", "悬疑", "--idea", "陈砚在旧港区发现失踪名单")
        chapter = self.project_root / "03_manuscript" / "第2章-短章.md"
        # 足够长以通过质量下限（<2500 字会被门禁判失败，失败结果不入缓存）
        chapter.write_text(
            "# 第2章 短章\n\n" + "\n\n".join(
                f"陈砚第{i}次走进旧港区那间仓库，先数了一遍墙上的钉子，{i + 12}根，一根没少。"
                f"他把手电压低，光柱贴着地皮扫过去，照见一层新落的灰。"
                f"周遇在门口守着，回头低声说：“这是第{i}回了，脚印还没干，有人比我们先到。”"
                for i in range(1, 31)
            ) + "\n",
            encoding="utf-8",
        )
        self.chapter = chapter

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def test_strict_flag_changes_cache_key(self):
        """门禁严格模式开关必须进缓存键：切换后不得命中旧缓存。"""
        _write_pacing_review(self.project_root, self.chapter)
        base = ["continue-write", "--project-root", str(self.project_root),
                "--chapter-file", str(self.chapter), "--query", "陈砚继续追查名单"]
        first = run(*base)
        second = run(*base)
        relaxed = run(*base, "--no-require-semantic-pacing")

        self.assertTrue(first.get("ok"), (first.get("gate_result") or {}).get("failures"))
        self.assertTrue(second.get("idempotent_hit"), "同参数第二次应命中缓存")
        self.assertFalse(relaxed.get("idempotent_hit"),
                         "放松门禁后不得复用严格模式的缓存")
        self.assertNotEqual(first.get("request_id"), relaxed.get("request_id"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
