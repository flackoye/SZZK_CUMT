param(
    [switch]$NoBrowser = $false
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot
$BackendDir = Join-Path $ScriptDir 'backend'
$VenvPython = Join-Path $BackendDir '.venv\Scripts\python.exe'

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host " SZIC While-Drilling Intelligence Platform Launcher" -ForegroundColor Cyan
Write-Host " Rule: Backend First (127.0.0.1:8000) -> Frontend Second (127.0.0.1:5173)" -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan

# 1. Check Python virtual environment
if (!(Test-Path $VenvPython)) {
    Write-Host "[1/3] Backend environment not found. Running setup..." -ForegroundColor Yellow
    & (Join-Path $BackendDir 'backend.ps1') setup
}

# Clean up any leftover processes on 8000 or 5173
$oldPids = Get-NetTCPConnection -LocalPort 8000, 5173 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
if ($oldPids) {
    foreach ($p in $oldPids) { Stop-Process -Id $p -Force -ErrorAction SilentlyContinue }
    Start-Sleep -Milliseconds 500
}

# 2. Launch backend process
Write-Host "[2/3] Starting backend server (127.0.0.1:8000)..." -ForegroundColor Cyan
$backendProc = Start-Process -FilePath $VenvPython -ArgumentList "-m uvicorn app.main:app --host 127.0.0.1 --port 8000" -WorkingDirectory $BackendDir -PassThru

# 3. Wait for backend health check
$maxAttempts = 30
$healthy = $false
Write-Host "Waiting for backend health check (http://127.0.0.1:8000/health)..." -NoNewline
for ($i = 0; $i -lt $maxAttempts; $i++) {
    Start-Sleep -Milliseconds 800
    try {
        $resp = Invoke-RestMethod -Uri "http://127.0.0.1:8000/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp -and $resp.status -eq 'ok' -and $resp.model_ready -eq $true) {
            $healthy = $true
            break
        }
    } catch {
        # continue waiting
    }
    Write-Host "." -NoNewline
}
Write-Host ""

if (!$healthy) {
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
    throw "Backend startup timed out or model failed to load. Check backend runtime logs."
}

Write-Host "[SUCCESS] Backend service and V3-Full model are ready!" -ForegroundColor Green

# 4. Launch frontend dev server
Write-Host "[3/3] Starting Vue frontend dashboard (127.0.0.1:5173)..." -ForegroundColor Cyan
try {
    & (Join-Path $ScriptDir 'frontend.ps1') dev
} finally {
    Write-Host "Stopping backend process (PID: $($backendProc.Id))..." -ForegroundColor Yellow
    Stop-Process -Id $backendProc.Id -Force -ErrorAction SilentlyContinue
}
