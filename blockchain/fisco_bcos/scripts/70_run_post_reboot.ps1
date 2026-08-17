[CmdletBinding()]
param(
    [string]$DistroName = 'Ubuntu-22.04'
)

$ErrorActionPreference = 'Stop'
. (Join-Path $PSScriptRoot '00_wsl_helpers.ps1')
$wslExe = Get-IrppWslExecutable
$projectRoot = (Split-Path -Parent $PSScriptRoot)

& (Join-Path $PSScriptRoot '01_post_reboot_audit.ps1')

$registered = @(& $wslExe --list --quiet) | ForEach-Object { $_.Trim([char]0).Trim() }
if ($registered -notcontains $DistroName) {
    throw "Distro $DistroName is not registered. Run 02_import_ubuntu_2204.ps1 first."
}

$resolvedProject = [System.IO.Path]::GetFullPath($projectRoot)
if ($resolvedProject -notmatch '^([A-Za-z]):\\(.*)$') {
    throw "Expected a drive-letter Windows path, found: $resolvedProject"
}
$drive = $Matches[1].ToLowerInvariant()
$pathTail = $Matches[2].Replace('\', '/')
$linuxProject = "/mnt/$drive/$pathTail"

& $wslExe -d $DistroName -u root -- bash "$linuxProject/scripts/10_bootstrap_ubuntu.sh"
if ($LASTEXITCODE -ne 0) { throw 'Ubuntu bootstrap failed.' }

& $wslExe --terminate $DistroName
Start-Sleep -Seconds 2

$steps = @(
    @{ Script = '20_install_fisco.sh'; Arguments = @($linuxProject) },
    @{ Script = '30_build_4node_chain.sh'; Arguments = @() },
    @{ Script = '40_install_console.sh'; Arguments = @() },
    @{ Script = '50_smoke_test.sh'; Arguments = @() },
    @{ Script = '60_collect_manifest.sh'; Arguments = @($linuxProject) }
)

foreach ($step in $steps) {
    $scriptPath = "$linuxProject/scripts/$($step.Script)"
    Write-Host "Running $($step.Script)"
    & $wslExe -d $DistroName -u irpp -- bash $scriptPath @($step.Arguments)
    if ($LASTEXITCODE -ne 0) { throw "Failed: $($step.Script)" }
}

Write-Host 'RQ5 FISCO BCOS environment configuration and smoke tests completed.'
