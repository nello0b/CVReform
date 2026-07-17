param(
    # Show Uvicorn startup and request logs alongside Vite output.
    [switch]$ShowBackendLogs,

    # Show backend logs at debug level and enable CV upload metadata logging.
    [switch]$Debug
)

# Treat PowerShell errors as fatal so setup never continues in a broken state.
$ErrorActionPreference = "Stop"

# Resolve paths from this script, regardless of the caller's current directory.
$ProjectRoot = $PSScriptRoot
$VenvPath = Join-Path $ProjectRoot ".venv"
$VenvPython = Join-Path $VenvPath "Scripts\python.exe"
$PythonDependencyStamp = Join-Path $VenvPath ".cvreform-dependencies"
$PyprojectPath = Join-Path $ProjectRoot "pyproject.toml"
$BackendEnvPath = Join-Path $ProjectRoot ".env"
$FrontendPath = Join-Path $ProjectRoot "frontend"
$FrontendEnvPath = Join-Path $FrontendPath ".env"
$FrontendPackagePath = Join-Path $FrontendPath "package.json"
$FrontendLockPath = Join-Path $FrontendPath "package-lock.json"
$FrontendModulesPath = Join-Path $FrontendPath "node_modules"

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

# Create the isolated Python environment only on the first run.
if (-not (Test-Path $VenvPython)) {
    if (-not (Get-Command python.exe -ErrorAction SilentlyContinue)) {
        throw "Python 3.11 or newer is required but was not found on PATH."
    }

    Write-Host "Creating Python virtual environment..." -ForegroundColor Cyan
    & python.exe -m venv $VenvPath
}

Write-Host "Using Python environment: $VenvPython" -ForegroundColor DarkGray

# Install Python packages when they are missing or pyproject.toml has changed.
# The script calls the venv's Python directly; terminal activation is unnecessary.
$PyprojectHash = (Get-FileHash $PyprojectPath -Algorithm SHA256).Hash
$RecordedHash = if (Test-Path $PythonDependencyStamp) {
    (Get-Content $PythonDependencyStamp -Raw).Trim()
}
else {
    ""
}

& $VenvPython -c "import fastapi, httpx, openai, pikepdf, PIL, pydantic_settings, pytest, uvicorn" 2>$null
$PythonDependenciesAvailable = $LASTEXITCODE -eq 0
$PyprojectChanged = $RecordedHash -and $RecordedHash -ne $PyprojectHash

if (-not $PythonDependenciesAvailable -or $PyprojectChanged) {
    Write-Host "Installing Python project dependencies..." -ForegroundColor Cyan
    & $VenvPython -m pip install -e ".[dev]"
    if ($LASTEXITCODE -ne 0) {
        throw "Python dependency installation failed."
    }

    Set-Content -Path $PythonDependencyStamp -Value $PyprojectHash
}
else {
    # Record the current configuration for environments created by older launchers.
    if (-not $RecordedHash) {
        Set-Content -Path $PythonDependencyStamp -Value $PyprojectHash
    }

    Write-Host "Python project dependencies are up to date." -ForegroundColor DarkGray
}

# Locate Node and npm. Calling npm's JavaScript entry point avoids Windows batch prompts.
$NodeCommand = Get-Command node.exe -ErrorAction SilentlyContinue
$NpmCommand = Get-Command npm.cmd -ErrorAction SilentlyContinue
if ($null -eq $NodeCommand -or $null -eq $NpmCommand) {
    throw "Node.js LTS and npm are required but were not found on PATH."
}

$NpmCli = Join-Path (Split-Path $NpmCommand.Source) "node_modules\npm\bin\npm-cli.js"
if (-not (Test-Path $NpmCli)) {
    throw "npm was found, but its npm-cli.js entry point is missing. Reinstall Node.js LTS."
}

# Run npm install only for a new checkout or after package.json changes.
$FrontendDependenciesNeedInstall =
    -not (Test-Path $FrontendModulesPath) -or
    -not (Test-Path $FrontendLockPath) -or
    (Get-Item $FrontendPackagePath).LastWriteTimeUtc -gt (Get-Item $FrontendLockPath).LastWriteTimeUtc

if ($FrontendDependenciesNeedInstall) {
    Write-Host "Installing frontend dependencies..." -ForegroundColor Cyan
    & $NodeCommand.Source $NpmCli --prefix $FrontendPath install
    if ($LASTEXITCODE -ne 0) {
        throw "Frontend dependency installation failed."
    }
}
else {
    Write-Host "Frontend dependencies are up to date." -ForegroundColor DarkGray
}

# Read the local API proxy target so Uvicorn and Vite always use the same address.
if (-not (Test-Path $FrontendEnvPath)) {
    throw "Missing frontend/.env. Copy frontend/.env.example to frontend/.env first."
}

$ProxySetting = Get-Content $FrontendEnvPath |
    Where-Object { $_ -match '^\s*VITE_API_PROXY_TARGET\s*=' } |
    Select-Object -Last 1
if (-not $ProxySetting) {
    throw "VITE_API_PROXY_TARGET is missing from frontend/.env."
}

$ProxyValue = ($ProxySetting -split '=', 2)[1].Trim()
try {
    $BackendUri = [Uri]$ProxyValue
}
catch {
    throw "VITE_API_PROXY_TARGET must be a valid URL, for example http://127.0.0.1:8000."
}

if ($BackendUri.Scheme -ne "http" -or $BackendUri.Host -notin @("127.0.0.1", "localhost")) {
    throw "The local launcher requires VITE_API_PROXY_TARGET to use http://127.0.0.1 or localhost."
}

$BackendHost = $BackendUri.Host
$BackendPort = $BackendUri.Port

# Fail clearly instead of silently connecting Vite to an older backend process.
# The .NET API safely returns an empty list when no ports are listening.
$PortIsInUse = [System.Net.NetworkInformation.IPGlobalProperties]::GetIPGlobalProperties().GetActiveTcpListeners() |
    Where-Object { $_.Port -eq $BackendPort }
if ($PortIsInUse) {
    throw "Port $BackendPort is already in use. Stop that server or change VITE_API_PROXY_TARGET."
}

# Start FastAPI in the background so Vite can remain interactive in this terminal.
Write-Host "Starting FastAPI at $($BackendUri.GetLeftPart([UriPartial]::Authority))" -ForegroundColor Green
$UvicornArguments = @(
    "-m", "uvicorn", "app.main:app", "--reload",
    "--host", $BackendHost, "--port", $BackendPort
)
if ($Debug) {
    $UvicornArguments += @("--log-level", "debug")
    Write-Host "Debug logging is enabled (file contents are never printed)." -ForegroundColor Yellow
}

$BackendArguments = @{
    FilePath = $VenvPython
    ArgumentList = $UvicornArguments
    WorkingDirectory = $ProjectRoot
    PassThru = $true
}

if ($ShowBackendLogs -or $Debug) {
    $BackendArguments["NoNewWindow"] = $true
}
else {
    $BackendArguments["WindowStyle"] = "Hidden"
}

# Load the backend's private feature flags for the child FastAPI process.
$ManagedBackendSettings = @(
    "OPENAI_API_KEY",
    "OPENAI_MODEL",
    "OPENAI_TIMEOUT_SECONDS",
    "OPENAI_MAX_RETRIES",
    "OPENAI_MAX_CONCURRENT_REQUESTS",
    "CVREFORM_ACCEPT_DOCX",
    "CVREFORM_ACCEPT_PDF",
    "CVREFORM_CONVERT_DOCX_TO_PDF",
    "CVREFORM_SEND_PAGE_IMAGES",
    "CVREFORM_PAGE_IMAGE_DPI",
    "SOFFICE_PATH"
)
$PreviousBackendSettings = @{}
foreach ($SettingName in $ManagedBackendSettings) {
    $PreviousBackendSettings[$SettingName] =
        [Environment]::GetEnvironmentVariable($SettingName, "Process")

    if (Test-Path $BackendEnvPath) {
        $SettingValue = Get-EnvironmentFileValue $BackendEnvPath $SettingName
        if ($null -ne $SettingValue) {
            [Environment]::SetEnvironmentVariable($SettingName, $SettingValue, "Process")
        }
    }
}

$PreviousDebugSetting = $env:CVREFORM_DEBUG
$env:CVREFORM_DEBUG = if ($Debug) { "1" } else { "0" }
$Backend = $null
try {
    # Child processes inherit this flag, allowing debug output without changing production behavior.
    $Backend = Start-Process @BackendArguments

    # Uvicorn's reload process starts before its worker is ready to accept requests.
    # Wait for the health endpoint so Vite cannot race the backend during startup.
    $BackendOrigin = $BackendUri.GetLeftPart([UriPartial]::Authority)
    $HealthUri = [Uri]::new("$BackendOrigin/api/v1/health")
    $StartupDeadline = [DateTime]::UtcNow.AddSeconds(30)

    while ($true) {
        $Backend.Refresh()
        if ($Backend.HasExited) {
            throw "FastAPI exited during startup with code $($Backend.ExitCode)."
        }

        try {
            $HealthResponse = Invoke-WebRequest `
                -Uri $HealthUri `
                -UseBasicParsing `
                -TimeoutSec 1
            if ($HealthResponse.StatusCode -eq 200) {
                break
            }
        }
        catch {
            # Connection failures are expected while Uvicorn creates its worker process.
        }

        if ([DateTime]::UtcNow -ge $StartupDeadline) {
            throw "FastAPI did not become ready at $HealthUri within 30 seconds."
        }

        Start-Sleep -Milliseconds 200
    }

    # Vite prints its actual URL, including any port configured in frontend/.env.
    Write-Host "Starting the React development server..." -ForegroundColor Green
    Write-Host "Press Ctrl+C to stop both servers." -ForegroundColor DarkGray
    & $NodeCommand.Source $NpmCli --prefix $FrontendPath run dev
}
finally {
    # Uvicorn reloads through child processes, so terminate the complete process tree.
    if ($null -ne $Backend) {
        & taskkill.exe /PID $Backend.Id /T /F 2>$null | Out-Null
    }

    # Leave the caller's environment exactly as it was before running this script.
    if ($null -eq $PreviousDebugSetting) {
        Remove-Item Env:CVREFORM_DEBUG -ErrorAction SilentlyContinue
    }
    else {
        $env:CVREFORM_DEBUG = $PreviousDebugSetting
    }

    foreach ($SettingName in $ManagedBackendSettings) {
        [Environment]::SetEnvironmentVariable(
            $SettingName,
            $PreviousBackendSettings[$SettingName],
            "Process"
        )
    }
}
