param([ValidateSet('dev', 'build', 'preview', 'install')][string]$Action = 'dev')
$ErrorActionPreference = 'Stop'
$runtimeRoot = Join-Path $env:USERPROFILE '.cache/codex-runtimes/codex-primary-runtime/dependencies'
$nodeCommand = Get-Command node -ErrorAction SilentlyContinue
$nodePath = if ($nodeCommand) { $nodeCommand.Source } else { Join-Path $runtimeRoot 'node/bin/node.exe' }
$nodeDir = Split-Path -Parent $nodePath
if ($nodeDir -and (Test-Path $nodeDir)) { $env:PATH = "$nodeDir;$env:PATH" }
Push-Location (Join-Path $PSScriptRoot 'qianduan')
try {
    if ($Action -eq 'install') {
        $pnpmCommand = Get-Command pnpm -ErrorAction SilentlyContinue
        $pnpmPath = if ($pnpmCommand) { $pnpmCommand.Source } else { Join-Path $runtimeRoot 'bin/fallback/pnpm.cmd' }
        & $pnpmPath install --frozen-lockfile --store-dir (Join-Path $PSScriptRoot '.pnpm-store')
    } else {
        $vitePath = Join-Path (Get-Location) 'node_modules/vite/bin/vite.js'
        if (!(Test-Path $vitePath)) { throw 'Run ./frontend.ps1 install first.' }
        switch ($Action) {
            'dev' {
                $occupied = Get-NetTCPConnection -LocalPort 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
                if ($occupied) {
                    Write-Host "检测到端口 5173 已被占用 (PID: $($occupied -join ', '))，正在自动释放..." -ForegroundColor Yellow
                    foreach ($pid_to_kill in $occupied) {
                        Stop-Process -Id $pid_to_kill -Force -ErrorAction SilentlyContinue
                    }
                    Start-Sleep -Milliseconds 600
                }
                & $nodePath $vitePath
            }
            'build' { & $nodePath $vitePath build }
            'preview' { & $nodePath $vitePath preview --host 127.0.0.1 --port 4173 --strictPort }
        }
    }
    if ($LASTEXITCODE -ne 0) { throw "Frontend command failed: $LASTEXITCODE" }
} finally { Pop-Location }
