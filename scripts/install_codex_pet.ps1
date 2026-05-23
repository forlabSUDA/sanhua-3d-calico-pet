$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$packageName = "sanhua-3d-calico-motionfix"
$source = Join-Path $repoRoot "pet-package\$packageName"
$destRoot = Join-Path $env:USERPROFILE ".codex\pets"
$dest = Join-Path $destRoot $packageName

if (!(Test-Path -LiteralPath (Join-Path $source "pet.json"))) {
    throw "Missing pet.json in $source"
}
if (!(Test-Path -LiteralPath (Join-Path $source "spritesheet.webp"))) {
    throw "Missing spritesheet.webp in $source"
}

New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -LiteralPath (Join-Path $source "pet.json") -Destination (Join-Path $dest "pet.json") -Force
Copy-Item -LiteralPath (Join-Path $source "spritesheet.webp") -Destination (Join-Path $dest "spritesheet.webp") -Force

Write-Host "Installed Codex pet:"
Write-Host "  $dest"
Write-Host "Open Codex > Settings > Appearance > Pets and choose: 三花猫猫 3D 修复版"
