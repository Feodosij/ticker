<#
.SYNOPSIS
    Build (if needed) and run the Ticker container on Windows.
.DESCRIPTION
    Idempotent: safe to re-run. Use -Build to force a rebuild.
.EXAMPLE
    ./scripts/start_windows.ps1
    ./scripts/start_windows.ps1 -Build
#>
param(
    [switch]$Build
)

$ErrorActionPreference = "Stop"

$ImageName     = "ticker:latest"
$ContainerName = "ticker"
$Port          = 8000
$Url           = "http://localhost:$Port"

# Resolve repo root regardless of where the script is invoked from.
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$RootDir   = (Resolve-Path (Join-Path $ScriptDir "..")).Path
Set-Location $RootDir

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker is not installed or not on PATH."
    exit 1
}

if (-not (Test-Path ".env")) {
    Write-Warning "No .env file found in $RootDir."
    Write-Warning "Copy .env.example to .env and add your keys (LLM chat needs OPENROUTER_API_KEY)."
}

# Build the image if forced or if it does not exist yet.
docker image inspect $ImageName *> $null
$ImageExists = ($LASTEXITCODE -eq 0)
if ($Build -or (-not $ImageExists)) {
    Write-Host "Building image $ImageName..."
    docker build -t $ImageName .
    if ($LASTEXITCODE -ne 0) { Write-Error "docker build failed."; exit 1 }
} else {
    Write-Host "Image $ImageName already exists (use -Build to rebuild)."
}

# If a container with our name is already running, we're done.
$Running = docker ps --format "{{.Names}}" | Select-String -SimpleMatch -Pattern $ContainerName
if ($Running) {
    Write-Host "Container '$ContainerName' is already running."
    Write-Host "Ticker is available at $Url"
    exit 0
}

# Remove any stopped container with the same name so `docker run` won't clash.
$Existing = docker ps -a --format "{{.Names}}" | Select-String -SimpleMatch -Pattern $ContainerName
if ($Existing) {
    Write-Host "Removing stopped container '$ContainerName'..."
    docker rm $ContainerName *> $null
}

$RunArgs = @(
    "-d",
    "--name", $ContainerName,
    "-p", "$($Port):8000",
    "-v", "$($RootDir)/db:/app/db"
)
if (Test-Path ".env") {
    $RunArgs += @("--env-file", ".env")
}
$RunArgs += $ImageName

Write-Host "Starting container '$ContainerName'..."
docker run @RunArgs *> $null
if ($LASTEXITCODE -ne 0) { Write-Error "docker run failed."; exit 1 }

Write-Host "Ticker is running at $Url"
Start-Process $Url
