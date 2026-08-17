[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$projectRoot = Split-Path -Parent $PSScriptRoot
$template = Join-Path $projectRoot 'config\.wslconfig.template'
$target = Join-Path $env:USERPROFILE '.wslconfig'

if (Test-Path -LiteralPath $target) {
    Write-Host "Existing file was left unchanged: $target"
    Write-Host "Merge the following settings manually after reviewing it: $template"
    exit 2
}

Copy-Item -LiteralPath $template -Destination $target
Write-Host "Created $target"
Write-Host 'Run wsl --shutdown once for the resource ceiling to take effect.'
