<#
.SYNOPSIS
  Novel OS 技能安装脚本（Windows / PowerShell 版）。

.DESCRIPTION
  与 install-portable-skill.sh 行为一致：把 SKILL.md、templates/、references/、
  scripts/（以及存在时的 assets/）复制到目标技能目录，写入入口文件与 TOOL_COMPAT.json。
  claude-code 额外把 agents/*.md（编辑团队角色定义）安装到 ~/.claude/agents/。

.EXAMPLE
  .\install-portable-skill.ps1 -Tool claude-code

.EXAMPLE
  .\install-portable-skill.ps1 -Tool gemini-cli -Dest "$HOME\.gemini\skills\novel-os" -Force
#>
[CmdletBinding()]
param(
    [string]$Tool = "",
    [string]$Dest = "",
    [switch]$Force,
    [switch]$SkipAgents,
    [switch]$Help
)

$ErrorActionPreference = "Stop"

$ValidTools = @("codex", "claude-code", "opencode", "gemini-cli", "antigravity")

function Show-Usage {
    @"
用法：
  install-portable-skill.ps1 -Tool <codex|claude-code|opencode|gemini-cli|antigravity> [-Dest <目录>] [-Force] [-SkipAgents]

示例：
  .\install-portable-skill.ps1 -Tool codex
  .\install-portable-skill.ps1 -Tool claude-code -Dest "$HOME\.claude\skills\novel-os"
  .\install-portable-skill.ps1 -Tool gemini-cli -Dest "$HOME\.gemini\skills\novel-os" -Force
"@ | Write-Host
}

function Get-DefaultDest {
    param([string]$ToolName)
    switch ($ToolName) {
        "codex"       { return (Join-Path $HOME ".codex\skills\novel-os") }
        "claude-code" { return (Join-Path $HOME ".claude\skills\novel-os") }
        "opencode"    { return (Join-Path $HOME ".opencode\skills\novel-os") }
        "gemini-cli"  { return (Join-Path $HOME ".gemini\skills\novel-os") }
        "antigravity" { return (Join-Path $HOME ".antigravity\skills\novel-os") }
        default       { [Console]::Error.WriteLine("不支持的工具: $ToolName"); exit 2 }
    }
}

function Test-ProtectedDest {
    <# 禁止危险目标：空路径、盘符根目录、HOME、当前目录。 #>
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path)) { return $true }

    $full = [System.IO.Path]::GetFullPath($Path).TrimEnd('\', '/')
    if ([string]::IsNullOrWhiteSpace($full)) { return $true }

    $roots = @()
    foreach ($drive in [System.IO.DriveInfo]::GetDrives()) {
        $roots += $drive.RootDirectory.FullName.TrimEnd('\', '/')
    }

    $homeFull = [System.IO.Path]::GetFullPath($HOME).TrimEnd('\', '/')
    $cwdFull = [System.IO.Path]::GetFullPath((Get-Location).Path).TrimEnd('\', '/')

    if ($full -eq $homeFull) { return $true }
    if ($full -eq $cwdFull) { return $true }
    if ($roots -contains $full) { return $true }
    return $false
}

function Write-Utf8NoBom {
    param([string]$Path, [string]$Text)
    $dir = Split-Path -Parent $Path
    if ($dir -and -not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    $encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $encoding)
}

function Write-EntryFile {
    param([string]$ToolName, [string]$DestDir)

    $pipeline = '章节发布必须执行：`/更新记忆 -> /检查一致性 -> /节奏审查 -> /风格校准 -> /校稿 -> /门禁检查`。'
    $beginner = '新手建议：`/一键开书 -> /继续写`；失败时执行 `/修复本章`。'

    switch ($ToolName) {
        "codex" {
            $body = @"
# Codex 入口

直接使用 ``SKILL.md`` 作为技能入口。
推荐命令链路：``/一键开书 -> /继续写 -> /修复本章(仅失败时)``
"@
            Write-Utf8NoBom -Path (Join-Path $DestDir "ENTRYPOINT.md") -Text ($body + "`n")
        }
        "claude-code" {
            $body = @"
# Claude Code 入口

请将本目录作为技能目录使用，核心入口为 ``SKILL.md``。
$pipeline
$beginner
开书五要素为硬校验：``one-click`` 缺一项即拒绝，不再生成空壳计划。
"@
            Write-Utf8NoBom -Path (Join-Path $DestDir "CLAUDE.md") -Text ($body + "`n")
        }
        "opencode" {
            $body = @"
# OpenCode 入口

将本目录作为技能包加载，入口说明见 ``SKILL.md``。
$pipeline
$beginner
"@
            Write-Utf8NoBom -Path (Join-Path $DestDir "OPENCODE.md") -Text ($body + "`n")
        }
        "gemini-cli" {
            $body = @"
# Gemini CLI 入口

将本目录作为项目提示技能目录，入口说明见 ``SKILL.md``。
$pipeline
$beginner
"@
            Write-Utf8NoBom -Path (Join-Path $DestDir "GEMINI.md") -Text ($body + "`n")
        }
        "antigravity" {
            $body = @"
# Antigravity 入口

将本目录作为代理技能目录，入口说明见 ``SKILL.md``。
$pipeline
$beginner
"@
            Write-Utf8NoBom -Path (Join-Path $DestDir "ANTIGRAVITY.md") -Text ($body + "`n")
        }
    }
}

function Write-Manifest {
    param([string]$ToolName, [string]$DestDir)

    $manifest = [ordered]@{
        tool                    = $ToolName
        installed_at            = (Get-Date -Format "yyyy-MM-dd HH:mm:ss")
        platform                = "windows"
        entry_files             = @("SKILL.md")
        chapter_release_pipeline = @("/更新记忆", "/检查一致性", "/节奏审查", "/风格校准", "/校稿", "/门禁检查")
        recommended_prewrite    = @("/继续写（内部已包含条件触发检索）")
        recommended_postwrite   = @("/继续写（内部已包含门禁与索引更新）")
        recommended_beginner_flow = @("/一键开书", "/继续写", "/修复本章（仅失败时）")
    }
    $json = $manifest | ConvertTo-Json -Depth 5
    Write-Utf8NoBom -Path (Join-Path $DestDir "TOOL_COMPAT.json") -Text ($json + "`n")
}

function Install-ClaudeAgents {
    param([string]$SourceRoot, [bool]$Overwrite)

    # agents/ 是中性目录；.claude/agents 仅为旧布局兜底
    $agentsSrc = Join-Path $SourceRoot "agents"
    if (-not (Test-Path $agentsSrc)) {
        $legacySrc = Join-Path $SourceRoot ".claude\agents"
        if (Test-Path $legacySrc) { $agentsSrc = $legacySrc } else { return }
    }

    $agentsDest = Join-Path $HOME ".claude\agents"
    if (-not (Test-Path $agentsDest)) { New-Item -ItemType Directory -Path $agentsDest -Force | Out-Null }

    $installed = 0
    foreach ($agentFile in Get-ChildItem -Path $agentsSrc -Filter *.md -File) {
        $target = Join-Path $agentsDest $agentFile.Name
        if ((Test-Path $target) -and -not $Overwrite) {
            Write-Host "[agents] 跳过（已存在，使用 -Force 覆盖）：$target"
            continue
        }
        Copy-Item -Path $agentFile.FullName -Destination $target -Force
        Write-Host "[agents] 已安装：$target"
        $installed++
    }

    if ($installed -gt 0) {
        Write-Host "[agents] 共安装 $installed 个编辑团队 Agent 到 $agentsDest"
    }
}

# ── 参数校验 ───────────────────────────────────────────────────
if ($Help) { Show-Usage; exit 0 }

if ([string]::IsNullOrWhiteSpace($Tool)) {
    [Console]::Error.WriteLine("缺少 -Tool 参数")
    Show-Usage
    exit 2
}

if ($ValidTools -notcontains $Tool) {
    [Console]::Error.WriteLine("不支持的工具: $Tool")
    Show-Usage
    exit 2
}

$ScriptDir = $PSScriptRoot
if ([string]::IsNullOrWhiteSpace($ScriptDir)) {
    $ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
}
$SourceRoot = Split-Path -Parent $ScriptDir

if ([string]::IsNullOrWhiteSpace($Dest)) {
    $Dest = Get-DefaultDest -ToolName $Tool
}
$Dest = [System.IO.Path]::GetFullPath($Dest)

if ((Test-Path $Dest) -and -not $Force) {
    [Console]::Error.WriteLine("目标目录已存在：$Dest")
    [Console]::Error.WriteLine("如需覆盖请追加 -Force")
    exit 3
}

if ((Test-Path $Dest) -and $Force) {
    if (Test-ProtectedDest -Path $Dest) {
        [Console]::Error.WriteLine("拒绝删除危险路径: $Dest")
        exit 4
    }
    Remove-Item -Path $Dest -Recurse -Force
}

New-Item -ItemType Directory -Path $Dest -Force | Out-Null

# ── 复制核心内容 ───────────────────────────────────────────────
Copy-Item -Path (Join-Path $SourceRoot "SKILL.md") -Destination $Dest -Force
foreach ($dirName in @("templates", "references", "scripts")) {
    $src = Join-Path $SourceRoot $dirName
    if (-not (Test-Path $src)) {
        [Console]::Error.WriteLine("缺少必需目录：$src")
        exit 5
    }
    Copy-Item -Path $src -Destination $Dest -Recurse -Force
}
$assetsSrc = Join-Path $SourceRoot "assets"
if (Test-Path $assetsSrc) {
    Copy-Item -Path $assetsSrc -Destination $Dest -Recurse -Force
}

Write-EntryFile -ToolName $Tool -DestDir $Dest
Write-Manifest -ToolName $Tool -DestDir $Dest

if (($Tool -eq "claude-code") -and (-not $SkipAgents)) {
    Install-ClaudeAgents -SourceRoot $SourceRoot -Overwrite ([bool]$Force)
}

Write-Host "安装完成"
Write-Host "tool=$Tool"
Write-Host "dest=$Dest"
exit 0
