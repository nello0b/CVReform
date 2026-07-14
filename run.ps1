$ErrorActionPreference = "Stop"

$ProjectRoot = $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$ActivateScript = Join-Path $VenvPath "Scripts\Activate.ps1"

Set-Location $ProjectRoot

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating virtual environment..." -ForegroundColor Cyan
    python -m venv $VenvPath
}

. $ActivateScript

Write-Host "Installing project dependencies..." -ForegroundColor Cyan
& $VenvPython -m pip install -e ".[dev]"

Write-Host "Starting CVReform at http://127.0.0.1:8000" -ForegroundColor Green
Write-Host "API documentation: http://127.0.0.1:8000/docs" -ForegroundColor Green
& $VenvPython -m uvicorn app.main:app --reload
