#requires -Version 5.1
<#
.SYNOPSIS
  Lokaler Build für Printix Send (WPF + MSI).

.DESCRIPTION
  1. dotnet publish der WPF-App (self-contained, single-file)
  2. dotnet build der WiX-Setup-Projekts → MSI

.PARAMETER Platform
  x64 (default) oder ARM64

.PARAMETER Config
  Release (default) oder Debug

.EXAMPLE
  .\scripts\build-msi.ps1 -Platform x64
  .\scripts\build-msi.ps1 -Platform ARM64
#>
param(
    [ValidateSet('x64','ARM64')]
    [string]$Platform = 'x64',
    [ValidateSet('Release','Debug')]
    [string]$Config   = 'Release'
)

$ErrorActionPreference = 'Stop'
$root = Resolve-Path (Join-Path $PSScriptRoot '..')
Push-Location $root
try {
    $rid = if ($Platform -eq 'x64') { 'win-x64' } else { 'win-arm64' }

    Write-Host "== 1/2: Publish WPF-App ($rid, $Config) =="
    dotnet publish .\PrintixSend\PrintixSend.csproj `
        -c $Config `
        -r $rid `
        -p:Platform=$Platform `
        --self-contained true

    Write-Host ""
    Write-Host "== 2/2: Build MSI ($Platform) =="
    dotnet build .\PrintixSend.Setup\PrintixSend.Setup.wixproj `
        -c $Config `
        -p:Platform=$Platform

    $msi = Get-ChildItem -Path .\PrintixSend.Setup\bin\$Platform\$Config -Filter "PrintixSend-*.msi" -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($msi) {
        Write-Host ""
        Write-Host "✓ MSI fertig: $($msi.FullName)" -ForegroundColor Green
    }
    else {
        Write-Warning "MSI wurde nicht gefunden — Build-Log prüfen."
    }
}
finally {
    Pop-Location
}
