#requires -Version 5.1
<#
.SYNOPSIS
  Dev-Install: legt manuell einen SendTo-Shortcut auf die gebaute
  PrintixSend.exe — ohne MSI.

.DESCRIPTION
  Nützlich zum schnellen Testen ohne MSI-Build.
  Shortcut wird in %APPDATA%\Microsoft\Windows\SendTo abgelegt.

.EXAMPLE
  .\scripts\install-sendto.ps1
  # oder explizit:
  .\scripts\install-sendto.ps1 -ExePath "C:\path\PrintixSend.exe"
#>
param(
    [string]$ExePath
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')

if (-not $ExePath) {
    $candidates = @(
        "$root\PrintixSend\bin\Release\net8.0-windows\win-x64\publish\PrintixSend.exe",
        "$root\PrintixSend\bin\Release\net8.0-windows\win-arm64\publish\PrintixSend.exe",
        "$root\PrintixSend\bin\Debug\net8.0-windows\win-x64\PrintixSend.exe"
    )
    $ExePath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}
if (-not $ExePath -or -not (Test-Path $ExePath)) {
    throw "PrintixSend.exe nicht gefunden. Erst bauen: .\scripts\build-msi.ps1 oder dotnet publish."
}

$sendTo = [Environment]::GetFolderPath('SendTo')
$link   = Join-Path $sendTo 'Printix Send.lnk'

$wsh = New-Object -ComObject WScript.Shell
$sc  = $wsh.CreateShortcut($link)
$sc.TargetPath       = $ExePath
$sc.WorkingDirectory = Split-Path $ExePath
$sc.Description      = "Dateien über Printix Send an Drucker oder Capture senden"
$sc.IconLocation     = $ExePath
$sc.Save()

Write-Host "✓ SendTo-Verknüpfung angelegt: $link" -ForegroundColor Green
Write-Host "  Ziel: $ExePath"
