#!/usr/bin/env python3
"""PowerShell 安装脚本测试（7 号待办）

- .ps1 必须是 UTF-8 with BOM（否则 PS 5.1 按 ANSI 解析中文会语法崩）
- 五种工具都能装出完整目录 + 入口文件 + TOOL_COMPAT.json
- 退出码契约：0 成功 / 2 参数错 / 3 目标已存在 / 4 危险路径
- 与 .sh 版本默认安装目录一致

运行方式:
    python3 scripts/tests/test_install_ps1.py
"""

import json
import platform
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent
REPO = SCRIPT_DIR.parent
PS1 = SCRIPT_DIR / "install-portable-skill.ps1"
SH = SCRIPT_DIR / "install-portable-skill.sh"

TOOLS = ("codex", "claude-code", "opencode", "gemini-cli", "antigravity")
ENTRY = {
    "codex": "ENTRYPOINT.md",
    "claude-code": "CLAUDE.md",
    "opencode": "OPENCODE.md",
    "gemini-cli": "GEMINI.md",
    "antigravity": "ANTIGRAVITY.md",
}
DEFAULT_DEST = {
    "codex": ".codex/skills/novel-os",
    "claude-code": ".claude/skills/novel-os",
    "opencode": ".opencode/skills/novel-os",
    "gemini-cli": ".gemini/skills/novel-os",
    "antigravity": ".antigravity/skills/novel-os",
}


def powershell() -> str:
    return shutil.which("powershell") or shutil.which("pwsh") or ""


def run_ps1(*args):
    return subprocess.run(
        [powershell(), "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(PS1), *args],
        capture_output=True, text=True, encoding="utf-8", errors="replace",
    )


class TestPs1ScriptShape(unittest.TestCase):
    """不依赖 Windows 也能跑的静态检查。"""

    def test_script_exists(self):
        self.assertTrue(PS1.exists(), "缺少 install-portable-skill.ps1")

    def test_script_is_utf8_with_bom(self):
        raw = PS1.read_bytes()
        self.assertEqual(
            raw[:3], b"\xef\xbb\xbf",
            "Windows PowerShell 5.1 读取无 BOM 的 UTF-8 .ps1 会按 ANSI 解析，中文将变乱码并语法报错",
        )

    def test_default_dests_match_bash_script(self):
        ps1 = PS1.read_text(encoding="utf-8-sig")
        sh = SH.read_text(encoding="utf-8")
        for tool, suffix in DEFAULT_DEST.items():
            win_suffix = suffix.replace("/", "\\")
            self.assertIn(win_suffix, ps1, f".ps1 缺少 {tool} 的默认目录")
            self.assertIn(suffix, sh, f".sh 缺少 {tool} 的默认目录")


@unittest.skipUnless(platform.system() == "Windows" and powershell(), "需要 Windows + PowerShell")
class TestPs1Install(unittest.TestCase):
    def setUp(self):
        self.base = Path(tempfile.mkdtemp(prefix="novel_ps1_"))

    def tearDown(self):
        shutil.rmtree(self.base, ignore_errors=True)

    def test_install_all_tools(self):
        for tool in TOOLS:
            with self.subTest(tool=tool):
                dest = self.base / tool
                extra = ["-SkipAgents"] if tool == "claude-code" else []
                proc = run_ps1("-Tool", tool, "-Dest", str(dest), *extra)
                self.assertEqual(proc.returncode, 0, proc.stderr)
                self.assertTrue((dest / "SKILL.md").exists())
                self.assertTrue((dest / ENTRY[tool]).exists())
                for d in ("scripts", "references", "templates"):
                    self.assertTrue((dest / d).is_dir(), f"{tool} 缺少 {d}/")
                manifest = json.loads((dest / "TOOL_COMPAT.json").read_text(encoding="utf-8"))
                self.assertEqual(manifest["tool"], tool)
                self.assertIn("chapter_release_pipeline", manifest)

    def test_existing_dest_requires_force(self):
        dest = self.base / "again"
        self.assertEqual(run_ps1("-Tool", "codex", "-Dest", str(dest)).returncode, 0)
        blocked = run_ps1("-Tool", "codex", "-Dest", str(dest))
        self.assertEqual(blocked.returncode, 3)
        self.assertIn("已存在", blocked.stderr)
        forced = run_ps1("-Tool", "codex", "-Dest", str(dest), "-Force")
        self.assertEqual(forced.returncode, 0, forced.stderr)

    def test_invalid_tool_exit_2(self):
        proc = run_ps1("-Tool", "vscode", "-Dest", str(self.base / "x"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("不支持的工具", proc.stderr)

    def test_missing_tool_exit_2(self):
        proc = run_ps1("-Dest", str(self.base / "y"))
        self.assertEqual(proc.returncode, 2)
        self.assertIn("缺少 -Tool", proc.stderr)

    def test_protected_dest_exit_4(self):
        home = str(Path.home())
        proc = run_ps1("-Tool", "codex", "-Dest", home, "-Force", "-SkipAgents")
        self.assertEqual(proc.returncode, 4)
        self.assertIn("拒绝删除危险路径", proc.stderr)
        self.assertTrue(Path(home).exists(), "拒绝删除后 HOME 必须完好")

    def test_help_exit_0(self):
        proc = run_ps1("-Help")
        self.assertEqual(proc.returncode, 0)
        self.assertIn("用法", proc.stdout)


if __name__ == "__main__":
    unittest.main(verbosity=2)
