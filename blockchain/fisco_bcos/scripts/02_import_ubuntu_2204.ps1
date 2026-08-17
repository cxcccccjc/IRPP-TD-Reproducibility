[CmdletBinding()]
param(
    [string]$DistroName = 'IRPP-Ubuntu-22.04',
    [string]$InstallRoot = "$env:LOCALAPPDATA\IRPP-WSL\IRPP-Ubuntu-22.04"
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '00_wsl_helpers.ps1')
$wslExe = Get-IrppWslExecutable
$projectRoot = Split-Path -Parent $PSScriptRoot
$assetDir = Join-Path $projectRoot 'assets'
$rootfsPath = Join-Path $assetDir 'ubuntu-jammy-wsl-amd64-ubuntu22.04lts.rootfs.tar.gz'
$rootfsUrl = 'https://cloud-images.ubuntu.com/wsl/jammy/current/ubuntu-jammy-wsl-amd64-ubuntu22.04lts.rootfs.tar.gz'

$existing = @(& $wslExe --list --quiet) | ForEach-Object { $_.Trim([char]0).Trim() }
if ($existing -contains $DistroName) {
    Write-Host "$DistroName is already registered; no import was performed."
    & $wslExe --set-version $DistroName 2
    exit $LASTEXITCODE
}

if (-not (Test-Path -LiteralPath $rootfsPath)) {
    New-Item -ItemType Directory -Force -Path $assetDir | Out-Null
    Write-Host 'Downloading the official Ubuntu 22.04 WSL root filesystem...'
    & curl.exe -fL --retry 10 --retry-all-errors --retry-delay 3 `
        -o $rootfsPath $rootfsUrl
    if ($LASTEXITCODE -ne 0) {
        throw "Ubuntu rootfs download failed with exit code $LASTEXITCODE"
    }
}

$rootfsSize = (Get-Item -LiteralPath $rootfsPath).Length
if ($rootfsSize -lt 100MB) {
    throw "Ubuntu rootfs is unexpectedly small ($rootfsSize bytes)."
}

$allowedParent = [System.IO.Path]::GetFullPath((Join-Path $env:LOCALAPPDATA 'IRPP-WSL'))
$resolvedInstall = [System.IO.Path]::GetFullPath($InstallRoot)
if (-not $resolvedInstall.StartsWith($allowedParent, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "InstallRoot must stay under $allowedParent"
}
if (Test-Path -LiteralPath $resolvedInstall) {
    $items = @(Get-ChildItem -LiteralPath $resolvedInstall -Force)
    if ($items.Count -gt 0) {
        throw "InstallRoot exists and is not empty: $resolvedInstall"
    }
} else {
    New-Item -ItemType Directory -Force -Path $resolvedInstall | Out-Null
}

& $wslExe --set-default-version 2
if ($LASTEXITCODE -ne 0) { throw 'Unable to set WSL2 as the default.' }
& $wslExe --import $DistroName $resolvedInstall $rootfsPath --version 2
if ($LASTEXITCODE -ne 0) { throw "WSL import failed with exit code $LASTEXITCODE" }

Write-Host "Imported $DistroName into $resolvedInstall"
& $wslExe --list --verbose
