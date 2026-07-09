<#
.SYNOPSIS
    Stop and remove the FinAlly container on Windows.
.DESCRIPTION
    Idempotent: does nothing (successfully) if the container isn't there.
    The ./db data volume is left untouched — your portfolio persists.
#>

$ErrorActionPreference = "Stop"

$ContainerName = "finally"

if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Error "docker is not installed or not on PATH."
    exit 1
}

$Existing = docker ps -a --format "{{.Names}}" | Select-String -SimpleMatch -Pattern $ContainerName
if ($Existing) {
    Write-Host "Stopping and removing container '$ContainerName'..."
    docker rm -f $ContainerName *> $null
    Write-Host "Stopped. Data in ./db is preserved."
} else {
    Write-Host "No container named '$ContainerName' found. Nothing to do."
}
