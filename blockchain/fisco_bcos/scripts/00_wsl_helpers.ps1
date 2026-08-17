function Get-IrppWslExecutable {
    $package = Get-AppxPackage -Name 'MicrosoftCorporationII.WindowsSubsystemForLinux' -ErrorAction SilentlyContinue
    if ($package) {
        $packagedWsl = Join-Path $package.InstallLocation 'wsl.exe'
        if (Test-Path -LiteralPath $packagedWsl) {
            return $packagedWsl
        }
    }
    return (Get-Command wsl.exe -ErrorAction Stop).Source
}
