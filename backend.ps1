param(
    [ValidateSet('dev', 'setup', 'test', 'test-batch')][string]$Action = 'dev'
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot
$BackendScript = Join-Path $ScriptDir 'backend\backend.ps1'

& $BackendScript -Action $Action

