param(
    [string]$OutputDirectory = 'C:\Reborn\artifacts\bloodfang-original-pet-20260914'
)
$ErrorActionPreference = 'Stop'
Add-Type -AssemblyName System.Drawing
$frames = @(
    'idle-01', 'idle-19', 'move-04', 'move-10',
    'attack-01', 'attack-16', 'death-01', 'death-42',
    'angry-01', 'angry-19', 'happy-04', 'happy-10'
)
$cellWidth = 400
$cellHeight = 435
$bitmap = New-Object System.Drawing.Bitmap (1600, 1305)
$graphics = [System.Drawing.Graphics]::FromImage($bitmap)
$graphics.Clear([System.Drawing.Color]::FromArgb(37, 36, 40))
$graphics.InterpolationMode = [System.Drawing.Drawing2D.InterpolationMode]::HighQualityBicubic
$font = New-Object System.Drawing.Font ('Segoe UI', 13, [System.Drawing.FontStyle]::Bold)
$brush = New-Object System.Drawing.SolidBrush ([System.Drawing.Color]::FromArgb(244, 233, 222))
try {
    for ($i = 0; $i -lt $frames.Length; $i++) {
        $x = ($i % 4) * $cellWidth
        $y = [math]::Floor($i / 4) * $cellHeight
        $path = Join-Path $OutputDirectory ('motion\' + $frames[$i] + '.png')
        $frame = [System.Drawing.Image]::FromFile($path)
        try { $graphics.DrawImage($frame, $x, $y + 35, 400, 400) }
        finally { $frame.Dispose() }
        $graphics.DrawString($frames[$i].ToUpperInvariant().Replace('-', ' / FRAME '), $font, $brush, $x + 14, $y + 6)
    }
    $target = Join-Path $OutputDirectory 'bloodfang-animation-contact-sheet.png'
    $bitmap.Save($target, [System.Drawing.Imaging.ImageFormat]::Png)
    Write-Output $target
}
finally {
    $font.Dispose()
    $brush.Dispose()
    $graphics.Dispose()
    $bitmap.Dispose()
}
