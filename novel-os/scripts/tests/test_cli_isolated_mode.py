#!/usr/bin/env python3
"""CLI 隔离模式测试（每个入口脚本必须自举 sys.path）

背景：脚本里的 `from common import ...` 依赖 CPython 默认把脚本目录放进
sys.path。一旦换到隔离模式（`python -I`、`python -P`、PYTHONSAFEPATH=1、
`python -m` 从别处调用），默认行为消失，入口直接 ModuleNotFoundError。

要求：每个带 argparse 的入口脚本在 `python -I <script> --help` 下必须退出 0。

运行方式:
    python3 scripts/tests/test_cli_isolated_mode.py
"""

import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent.parent


def cli_entrypoints():
    """带 argparse 且有 __main__ 入口的脚本，即用户真正会敲的那批命令。"""
    return sorted(
        p for p in SCRIPT_DIR.glob("*.py")
        if "ArgumentParser" in p.read_text(encoding="utf-8")
        and "__main__" in p.read_text(encoding="utf-8")
    )


class TestCLIIsolatedMode(unittest.TestCase):
    def test_entrypoints_discovered(self):
        found = cli_entrypoints()
        self.assertGreaterEqual(len(found), 10, f"CLI 入口扫描异常: {found}")

    def test_every_entrypoint_survives_isolated_mode(self):
        failures = []
        for script in cli_entrypoints():
            p = subprocess.run(
                [sys.executable, "-I", str(script), "--help"],
                capture_output=True, text=True, encoding="utf-8",
            )
            if p.returncode != 0:
                failures.append(f"{script.name} (exit={p.returncode}): {p.stderr.strip()[:200]}")
        self.assertEqual(failures, [], "以下入口在隔离模式下启动失败:\n" + "\n".join(failures))


if __name__ == "__main__":
    unittest.main(verbosity=2)
