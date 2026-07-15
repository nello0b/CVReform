# Run this script once after cloning CVReform to install its local dependencies.
$ErrorActionPreference = "Stop"

# Resolve every project path relative to this script, not the current terminal folder.
$ProjectRoot = $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$PyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
$PythonDependencyStamp = Join-Path $VenvPath ".cvreform-dependencies"
$BackendEnvPath = Join-Path $ProjectRoot ".env"
$BackendEnvExamplePath = Join-Path $ProjectRoot ".env.example"
$FrontendPath = Join-Path $ProjectRoot "frontend"
$FrontendEnvPath = Join-Path $FrontendPath ".env"
$FrontendEnvExamplePath = Join-Path $FrontendPath ".env.example"

Set-Location $ProjectRoot

function Get-EnvironmentFileValue {
    param([string]$Path, [string]$Name)

    $Setting = Get-Content $Path |
        Where-Object { $_ -match "^\s*$([regex]::Escape($Name))\s*=" } |
        Select-Object -Last 1
    if (-not $Setting) {
        return $null
    }

    return (($Setting -split '=', 2)[1].Trim()).Trim('"').Trim("'")
}

# Create private backend configuration without overwriting a developer's choices.
if (-not (Test-Path $BackendEnvPath)) {
    if (-not (Test-Path $BackendEnvExamplePath)) {
        throw ".env.example is missing."
    }

    Copy-Item $BackendEnvExamplePath $BackendEnvPath
    Write-Host "Created .env from .env.example." -ForegroundColor Cyan
}

# LibreOffice is only required when accepted DOCX files should be converted to PDF.
$AcceptDocxValue = Get-EnvironmentFileValue $BackendEnvPath "CVREFORM_ACCEPT_DOCX"
$ConvertDocxValue = Get-EnvironmentFileValue $BackendEnvPath "CVREFORM_CONVERT_DOCX_TO_PDF"
$AcceptDocx = $AcceptDocxValue -in @("1", "true", "yes", "on")
$ConvertDocxToPdf = $ConvertDocxValue -in @("1", "true", "yes", "on")
if ($AcceptDocx -and $ConvertDocxToPdf) {
    $ConfiguredSofficePath = Get-EnvironmentFileValue $BackendEnvPath "SOFFICE_PATH"
    $SofficeCommand = Get-Command soffice.exe -ErrorAction SilentlyContinue
    $SofficeCandidates = @()
    if ($ConfiguredSofficePath) {
        $SofficeCandidates += $ConfiguredSofficePath
    }
    if ($env:ProgramFiles) {
        $SofficeCandidates += Join-Path $env:ProgramFiles "LibreOffice\program\soffice.exe"
    }
    if (${env:ProgramFiles(x86)}) {
        $SofficeCandidates += Join-Path ${env:ProgramFiles(x86)} "LibreOffice\program\soffice.exe"
    }

    $SofficePath = $SofficeCandidates | Where-Object { Test-Path $_ } | Select-Object -First 1
    if ($null -eq $SofficeCommand -and -not $SofficePath) {
        $WingetCommand = Get-Command winget.exe -ErrorAction SilentlyContinue
        if ($null -eq $WingetCommand) {
            throw "DOCX-to-PDF conversion requires LibreOffice. Install it or disable CVREFORM_CONVERT_DOCX_TO_PDF."
        }

        Write-Host "Installing LibreOffice for PDF conversion..." -ForegroundColor Cyan
        & $WingetCommand.Source install --source winget --exact `
            --id TheDocumentFoundation.LibreOffice `
            --accept-package-agreements --accept-source-agreements
        if ($LASTEXITCODE -ne 0) {
            throw "LibreOffice installation failed. Install it manually or disable PDF support."
        }
    }
    else {
        Write-Host "LibreOffice is available for PDF conversion." -ForegroundColor DarkGray
    }
}
else {
    Write-Host "DOCX-to-PDF conversion is disabled; skipping LibreOffice setup." -ForegroundColor DarkGray
}

# Python is required to create the backend's isolated virtual environment.
$PythonCommand = Get-Command python.exe -ErrorAction SilentlyContinue
if ($null -eq $PythonCommand) {
    throw "Python 3.11 or newer is required. Install Python, reopen PowerShell, and rerun setup.ps1."
}

if (-not (Test-Path $VenvPython)) {
    Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
    & $PythonCommand.Source -m venv $VenvPath
    if ($LASTEXITCODE -ne 0) {
        throw "Could not create the Python virtual environment."
    }
}

# Install the FastAPI application and its development/test dependencies.
Write-Host "Installing Python project dependencies..." -ForegroundColor Cyan
& $VenvPython -m pip install -e ".[dev]"
if ($LASTEXITCODE -ne 0) {
    throw "Python dependency installation failed."
}

# Record the installed configuration so run.ps1 does not install it again unnecessarily.
$PyprojectHash = (Get-FileHash $PyprojectPath -Algorithm SHA256).Hash
Set-Content -Path $PythonDependencyStamp -Value $PyprojectHash

# Node.js and npm are required to install and run the React frontend.
$NodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$NpmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $NodeCommand -or $null -eq $NpmCommand) {
    throw "Node.js LTS and npm are required. Install Node.js, reopen PowerShell, and rerun setup.ps1."
}

# Call npm through Node directly to avoid Windows batch-file termination prompts.
$NpmCli = Join-Path (Split-Path $NpmCommand.Source) "node_modules\npm\bin\npm-cli.js"
if (-not (Test-Path $NpmCli)) {
    throw "npm was found, but npm-cli.js is missing. Reinstall Node.js LTS."
}

Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
& $NodeCommand.Source $NpmCli --prefix $FrontendPath install
if ($LASTEXITCODE -ne 0) {
    throw "Frontend dependency installation failed."
}

# Create the developer's private environment file without overwriting existing settings.
if (-not (Test-Path $FrontendEnvPath)) {
    if (-not (Test-Path $FrontendEnvExamplePath)) {
        throw "frontend/.env.example is missing."
    }

    Copy-Item $FrontendEnvExamplePath $FrontendEnvPath
    Write-Host "Created frontend/.env from frontend/.env.example." -ForegroundColor Cyan
}

Write-Host "CVReform setup is complete. Start it with .\run.ps1" -ForegroundColor Green
