#!/usr/bin/env python3
"""RAG 占位桩过滤测试

验证：
- 占位桩章节不进索引
- 旧索引里残留的桩文档在检索时被滤掉
- 骨架片段（只有标题/列表项）不进参考上下文
- 真实正文里提到「待写」二字不误判

运行方式:
    python3 scripts/tests/test_rag_stub_filter.py
"""

import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

STUB_CHAPTER = "# 第1章 开篇\n\n<!-- NOVEL_FLOW_STUB -->\n\n## 正文\n[待写]\n"


def real_chapter(no: int = 2) -> str:
    return f"# 第{no}章 码头对峙\n\n" + "\n\n".join(
        f"陈砚第{i}次把名单摊在码头的木箱上，潮气顺着木板往上爬。"
        f"周遇蹲在缆桩旁，伞尖淌下的水在地上积成一小片。"
        f"“第三个名字是假的。”周遇说，“那个人三年前就不在港区了。”"
        for i in range(1, 9)
    ) + "\n"


class TestStubDetection(unittest.TestCase):
    def test_stub_marker_detected(self):
        from common import is_draft_stub_text

        self.assertTrue(is_draft_stub_text(STUB_CHAPTER))
        self.assertTrue(is_draft_stub_text("# 第2章\n\n<!-- BEAT_SHEET_STUB -->\n\n提示词…"))

    def test_short_placeholder_detected(self):
        from common import is_draft_stub_text

        self.assertTrue(is_draft_stub_text("# 第2章 待写\n\n[待写]\n"))

    def test_long_prose_mentioning_placeholder_is_not_stub(self):
        from common import is_draft_stub_text

        long_text = real_chapter() + "\n[待写]\n" + ("他继续往下写。" * 200)
        self.assertFalse(is_draft_stub_text(long_text))


class TestIndexSkipsStub(unittest.TestCase):
    def setUp(self):
        self.project_root = Path(tempfile.mkdtemp(prefix="rag_stub_"))
        for d in ["00_memory/retrieval", "03_manuscript", "02_knowledge_base"]:
            (self.project_root / d).mkdir(parents=True, exist_ok=True)
        (self.project_root / "03_manuscript" / "第1章-开篇待写.md").write_text(
            STUB_CHAPTER, encoding="utf-8"
        )
        (self.project_root / "03_manuscript" / "第2章-码头对峙.md").write_text(
            real_chapter(), encoding="utf-8"
        )

    def tearDown(self):
        shutil.rmtree(self.project_root, ignore_errors=True)

    def test_build_index_excludes_stub_chapter(self):
        from plot_rag_retriever import build_index

        index = build_index(self.project_root, incremental=False)
        self.assertEqual(index["chapter_count"], 1, index.get("docs"))
        self.assertEqual(index["skipped_stub_docs"], 1)
        self.assertIn("第1章-开篇待写.md", index["skipped_stub_files"])
        files = [d["chapter_file"] for d in index["docs"]]
        self.assertEqual(files, ["第2章-码头对峙.md"])

        saved = json.loads(
            (self.project_root / "00_memory" / "retrieval" / "story_index.json")
            .read_text(encoding="utf-8")
        )
        self.assertEqual(len(saved["docs"]), 1)

    def test_query_never_returns_stub_content(self):
        from plot_rag_retriever import build_index, retrieve

        index = build_index(self.project_root, incremental=False)
        result = retrieve(
            index, self.project_root, "陈砚在码头核对名单", top_k=4,
            candidate_k=8, per_chapter=2, passage_max_chars=360,
        )
        texts = [str(p.get("text", "")) for r in result["retrieved"] for p in r["passages"]]
        self.assertTrue(texts, "应检索到真实章节片段")
        for t in texts:
            self.assertNotIn("NOVEL_FLOW_STUB", t)
            self.assertNotIn("本章目标", t)
        self.assertNotIn(
            "第1章-开篇待写.md", [r.get("chapter_file") for r in result["retrieved"]]
        )

    def test_stale_index_stub_doc_filtered_at_query(self):
        """旧索引（修复前生成）里残留的桩文档，检索时必须滤掉。"""
        from plot_rag_retriever import retrieve

        stale_doc = {
            "chapter_file": "第1章-开篇待写.md",
            "chapter_path": str(self.project_root / "03_manuscript" / "第1章-开篇待写.md"),
            "chapter_no": 1,
            "mtime": 0.0,
            "summary": "# 第1章 开篇 <!-- NOVEL_FLOW_STUB --> ## 正文 [待写]",
            "entities": ["陈砚"],
            "keywords": ["陈砚", "码头", "名单"],
            "events": [],
            "locations": [],
            "foreshadow_refs": [],
            "conflict_level": "unknown",
        }
        index = {"docs": [stale_doc], "chapter_count": 1}
        result = retrieve(
            index, self.project_root, "陈砚在码头核对名单", top_k=4,
            candidate_k=8, per_chapter=2, passage_max_chars=360,
        )
        self.assertEqual(result["retrieved"], [])


class TestSkeletonPassageFilter(unittest.TestCase):
    def test_skeleton_detected(self):
        from plot_rag_retriever import _is_skeleton_passage

        self.assertTrue(_is_skeleton_passage("## 本章目标\n- 建立主角目标\n- 落地核心冲突"))
        self.assertTrue(_is_skeleton_passage("## 场景草图\n- 起始地点：\n- 冲突触发点："))

    def test_prose_not_skeleton(self):
        from plot_rag_retriever import _is_skeleton_passage

        self.assertFalse(_is_skeleton_passage("他推开门，雨声涌进来。\n\n周遇没有抬头。"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
