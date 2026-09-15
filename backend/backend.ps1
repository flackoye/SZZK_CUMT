param(
    [ValidateSet('dev', 'setup', 'test', 'test-batch')][string]$Action = 'dev'
)

$ErrorActionPreference = 'Stop'
$ScriptDir = $PSScriptRoot
$VenvPython = Join-Path $ScriptDir ".venv\Scripts\python.exe"

Push-Location $ScriptDir
try {
    if ($Action -eq 'setup') {
        if (!(Test-Path $VenvPython)) {
            Write-Host "Creating Python virtual environment in .venv..." -ForegroundColor Cyan
            $systemPython = "C:\Python314\python.exe"
            if (!(Test-Path $systemPython)) {
                $pyCmd = Get-Command py -ErrorAction SilentlyContinue
                if ($pyCmd) { & py -m venv --system-site-packages .venv }
                else { throw "Cannot find Python 3.14 or py launcher." }
            } else {
                & $systemPython -m venv --system-site-packages .venv
            }
        }
        Write-Host "Installing requirements..." -ForegroundColor Cyan
        & $VenvPython -m pip install -r requirements.txt -i https://pypi.org/simple
        Write-Host "Backend setup completed successfully!" -ForegroundColor Green
    }
    elseif ($Action -eq 'dev') {
        if (!(Test-Path $VenvPython)) {
            throw "Virtual environment not found. Please run: .\backend.ps1 setup"
        }
        $occupied = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue | Select-Object -ExpandProperty OwningProcess -Unique
        if ($occupied) {
            Write-Host "检测到端口 8000 已被占用 (PID: $($occupied -join ', '))，正在自动释放旧服务..." -ForegroundColor Yellow
            foreach ($pid_to_kill in $occupied) {
                Stop-Process -Id $pid_to_kill -Force -ErrorAction SilentlyContinue
            }
            Start-Sleep -Milliseconds 600
        }
        Write-Host "Starting SZIC Inference Backend on http://127.0.0.1:8000 ..." -ForegroundColor Green
        & $VenvPython -m uvicorn app.main:app --host 127.0.0.1 --port 8000
    }
    elseif ($Action -eq 'test') {
        if (!(Test-Path $VenvPython)) {
            throw "Virtual environment not found. Please run: .\backend.ps1 setup"
        }
        Write-Host "Testing model inference with sample data..." -ForegroundColor Cyan
        & $VenvPython test_cli.py
    }
    elseif ($Action -eq 'test-batch') {
        if (!(Test-Path $VenvPython)) {
            throw "Virtual environment not found. Please run: .\backend.ps1 setup"
        }
        Write-Host "Testing 11-borehole batch inference pipeline..." -ForegroundColor Cyan
        & $VenvPython test_batch_regression.py
    }
}
finally {
    Pop-Location
}
