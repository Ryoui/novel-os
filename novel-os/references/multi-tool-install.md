# 跨工具安装教程

本技能支持以下工具的一键安装：
- Codex
- Claude Code
- OpenCode
- Gemini CLI
- Antigravity

两个等价脚本，按平台选一个：

| 平台 | 脚本 | 参数写法 |
|------|------|---------|
| macOS / Linux / WSL | `scripts/install-portable-skill.sh` | `--tool codex --dest <目录> --force` |
| Windows（PowerShell 5.1+ / PowerShell 7） | `scripts/install-portable-skill.ps1` | `-Tool codex -Dest <目录> -Force` |

两者行为一致：复制 `SKILL.md`、`templates/`、`references/`、`scripts/`（存在则连同 `assets/`），
写入对应工具入口文件与 `TOOL_COMPAT.json`；`claude-code` 额外把 `agents/*.md`（编辑团队角色定义）安装到 `~/.claude/agents/`。

## 1. Codex
```bash
# macOS / Linux
bash scripts/install-portable-skill.sh --tool codex --force
# Windows
powershell -ExecutionPolicy Bypass -File scripts\install-portable-skill.ps1 -Tool codex -Force
```
默认安装到：`~/.codex/skills/novel-os`

## 2. Claude Code
```bash
# macOS / Linux
bash scripts/install-portable-skill.sh --tool claude-code --force
# Windows
powershell -ExecutionPolicy Bypass -File scripts\install-portable-skill.ps1 -Tool claude-code -Force
```
默认安装到：`~/.claude/skills/novel-os`（Agent 定义另装到 `~/.claude/agents/`）

## 3. OpenCode
```bash
bash scripts/install-portable-skill.sh --tool opencode --force
powershell -ExecutionPolicy Bypass -File scripts\install-portable-skill.ps1 -Tool opencode -Force
```
默认安装到：`~/.opencode/skills/novel-os`

## 4. Gemini CLI
```bash
bash scripts/install-portable-skill.sh --tool gemini-cli --force
powershell -ExecutionPolicy Bypass -File scripts\install-portable-skill.ps1 -Tool gemini-cli -Force
```
默认安装到：`~/.gemini/skills/novel-os`

## 5. Antigravity
```bash
bash scripts/install-portable-skill.sh --tool antigravity --force
powershell -ExecutionPolicy Bypass -File scripts\install-portable-skill.ps1 -Tool antigravity -Force
```
默认安装到：`~/.antigravity/skills/novel-os`

## 自定义目录
```bash
bash scripts/install-portable-skill.sh --tool <tool> --dest <目标目录> --force
powershell -ExecutionPolicy Bypass -File scripts\install-portable-skill.ps1 -Tool <tool> -Dest <目标目录> -Force
```

## 退出码（两脚本一致）

| 码 | 含义 |
|----|------|
| 0 | 安装成功 |
| 2 | 参数错误（缺 `--tool`/`-Tool`、工具不支持） |
| 3 | 目标目录已存在且未加 `--force`/`-Force` |
| 4 | 拒绝删除危险路径（盘符根目录、`$HOME`、当前目录） |
| 5 | 源目录缺失（`scripts/`、`references/`、`templates/` 不全） |

## Windows 注意事项

- `.ps1` 文件必须保存为 **UTF-8 with BOM**：Windows PowerShell 5.1 读取无 BOM 的 UTF-8 脚本会按 ANSI 解析，中文全部变乱码并触发语法错误。
- 默认执行策略可能禁止运行脚本，用 `-ExecutionPolicy Bypass` 单次绕过即可，不必改全局策略。
- PowerShell 7+（pwsh）同样可用，行为一致。

## 安装后检查
确认以下文件存在：
- `SKILL.md`
- 对应工具入口文件（`ENTRYPOINT.md` / `CLAUDE.md` / `OPENCODE.md` / `GEMINI.md` / `ANTIGRAVITY.md`）
- `TOOL_COMPAT.json`（含 `tool`、`installed_at`、`chapter_release_pipeline`）
- 目录内 `scripts/`、`references/`、`templates/` 齐全
