#requires -Version 5.1
# Entfernt den SendTo-Shortcut (Dev-Install)
$sendTo = [Environment]::GetFolderPath('SendTo')
$link   = Join-Path $sendTo 'Printix Send.lnk'
if (Test-Path $link) {
    Remove-Item $link -Force
    Write-Host "✓ Entfernt: $link" -ForegroundColor Green
} else {
    Write-Host "Nichts zu entfernen (kein Shortcut in $sendTo)."
}
