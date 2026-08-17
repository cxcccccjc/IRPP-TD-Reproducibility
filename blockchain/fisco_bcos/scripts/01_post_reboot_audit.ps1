[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '00_wsl_helpers.ps1')
$wslExe = Get-IrppWslExecutable
$projectRoot = Split-Path -Parent $PSScriptRoot
$logDir = Join-Path $projectRoot 'logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$logPath = Join-Path $logDir "post_reboot_audit_$stamp.txt"

$featureNames = @(
    'Microsoft-Windows-Subsystem-Linux',
    'VirtualMachinePlatform'
)

$lines = [System.Collections.Generic.List[string]]::new()
$lines.Add("timestamp=$((Get-Date).ToString('o'))")
$lines.Add("computer=$env:COMPUTERNAME")

foreach ($featureName in $featureNames) {
    $feature = Get-WindowsOptionalFeature -Online -FeatureName $featureName
    $lines.Add("feature.$featureName=$($feature.State)")
    if ($feature.State -ne 'Enabled') {
        throw "Required Windows feature is not enabled: $featureName"
    }
}

$wslStatus = (& $wslExe --status 2>&1 | Out-String).Trim()
$wslVersion = (& $wslExe --version 2>&1 | Out-String).Trim()
$wslList = (& $wslExe --list --verbose 2>&1 | Out-String).Trim()
$lines.Add("wsl.status=`n$wslStatus")
$lines.Add("wsl.version=`n$wslVersion")
$lines.Add("wsl.list=`n$wslList")

$lines | Set-Content -LiteralPath $logPath -Encoding utf8
Write-Host "Audit written to $logPath"
Write-Host $wslVersion

if ($wslVersion -match 'Usage:|Copyright \(c\) Microsoft') {
    throw 'The Store WSL runtime is not active yet. Run: wsl --update --web-download, then rerun this audit.'
}
