# Erzeugt PrintixSend/Resources/app.ico — ein einfaches, aber ordentliches
# Printix-blaues Icon mit großem "P" statt des Windows-Default-MSI-Icons.
# Wird in der GitHub-Action vor "dotnet publish" aufgerufen.
#
# Das Skript malt drei Größen (16/32/64/128/256 px) und packt sie in eine
# .ico. Kein externes Tool nötig — nur System.Drawing aus .NET Framework,
# das auf jedem Windows-Runner vorhanden ist.

param(
    [string]$OutPath = (Join-Path $PSScriptRoot "..\PrintixSend\Resources\app.ico")
)

$ErrorActionPreference = "Stop"
Add-Type -AssemblyName System.Drawing

$sizes = 16, 32, 48, 64, 128, 256
$pngStreams = @()
$bitmaps    = @()

# Printix-blau (Akzentfarbe aus App.xaml: #0369A1)
$blue  = [System.Drawing.Color]::FromArgb(3, 105, 161)
$white = [System.Drawing.Color]::White

foreach ($size in $sizes) {
    $bmp = New-Object System.Drawing.Bitmap($size, $size, [System.Drawing.Imaging.PixelFormat]::Format32bppArgb)
    $g   = [System.Drawing.Graphics]::FromImage($bmp)
    $g.SmoothingMode     = [System.Drawing.Drawing2D.SmoothingMode]::AntiAlias
    $g.TextRenderingHint = [System.Drawing.Text.TextRenderingHint]::AntiAliasGridFit
    $g.Clear([System.Drawing.Color]::Transparent)

    # Abgerundetes blaues Quadrat als Hintergrund
    $radius = [Math]::Max([int]($size * 0.15), 2)
    $rect = New-Object System.Drawing.RectangleF(0, 0, $size, $size)
    $path = New-Object System.Drawing.Drawing2D.GraphicsPath
    $path.AddArc($rect.X, $rect.Y, $radius*2, $radius*2, 180, 90)
    $path.AddArc($rect.Right - $radius*2, $rect.Y, $radius*2, $radius*2, 270, 90)
    $path.AddArc($rect.Right - $radius*2, $rect.Bottom - $radius*2, $radius*2, $radius*2, 0, 90)
    $path.AddArc($rect.X, $rect.Bottom - $radius*2, $radius*2, $radius*2, 90, 90)
    $path.CloseFigure()

    $brush = New-Object System.Drawing.SolidBrush($blue)
    $g.FillPath($brush, $path)
    $brush.Dispose()

    # "P" in weiß, zentriert
    $fontSize = [float]($size * 0.62)
    $font = New-Object System.Drawing.Font("Segoe UI", $fontSize, [System.Drawing.FontStyle]::Bold, [System.Drawing.GraphicsUnit]::Pixel)
    $sf = New-Object System.Drawing.StringFormat
    $sf.Alignment     = [System.Drawing.StringAlignment]::Center
    $sf.LineAlignment = [System.Drawing.StringAlignment]::Center
    $whiteBrush = New-Object System.Drawing.SolidBrush($white)
    # leichte optische Korrektur: "P" sitzt sonst zu hoch
    $textRect = New-Object System.Drawing.RectangleF(0, [float]($size * -0.04), $size, $size)
    $g.DrawString("P", $font, $whiteBrush, $textRect, $sf)

    $whiteBrush.Dispose()
    $font.Dispose()
    $g.Dispose()

    $stream = New-Object System.IO.MemoryStream
    $bmp.Save($stream, [System.Drawing.Imaging.ImageFormat]::Png)
    $pngStreams += ,$stream
    $bitmaps    += ,$bmp
}

# ICONDIR + ICONDIRENTRY + Daten schreiben
$outDir = Split-Path $OutPath -Parent
if (-not (Test-Path $outDir)) { New-Item -ItemType Directory -Path $outDir | Out-Null }
$fs = [System.IO.File]::Create($OutPath)
try {
    $bw = New-Object System.IO.BinaryWriter($fs)

    # ICONDIR
    $bw.Write([UInt16]0)
    $bw.Write([UInt16]1)                   # Typ: Icon
    $bw.Write([UInt16]$sizes.Count)

    $offset = 6 + 16 * $sizes.Count
    for ($i = 0; $i -lt $sizes.Count; $i++) {
        $size = $sizes[$i]
        $len  = $pngStreams[$i].Length
        # ICONDIRENTRY (16 Bytes)
        $bw.Write([Byte]($(if ($size -ge 256) { 0 } else { $size })))   # Breite  (0 = 256)
        $bw.Write([Byte]($(if ($size -ge 256) { 0 } else { $size })))   # Höhe
        $bw.Write([Byte]0)                 # Farbpalette (0 = keine)
        $bw.Write([Byte]0)                 # Reserviert
        $bw.Write([UInt16]1)               # Color Planes
        $bw.Write([UInt16]32)              # Bits pro Pixel
        $bw.Write([UInt32]$len)            # Bildgröße
        $bw.Write([UInt32]$offset)         # Offset ins ICO
        $offset += $len
    }
    foreach ($stream in $pngStreams) {
        $bw.Write($stream.ToArray())
    }
    $bw.Flush()
} finally {
    $fs.Dispose()
    foreach ($s in $pngStreams) { $s.Dispose() }
    foreach ($b in $bitmaps)    { $b.Dispose() }
}

Write-Host "Icon erzeugt: $OutPath"
