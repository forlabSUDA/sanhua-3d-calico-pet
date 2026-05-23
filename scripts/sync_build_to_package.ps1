$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
$buildFinal = Join-Path $repoRoot "build\sanhua_3d_pet_motionfix_all\final"
$package = Join-Path $repoRoot "pet-package\sanhua-3d-calico-motionfix"

if (!(Test-Path -LiteralPath (Join-Path $buildFinal "pet.json"))) {
    throw "Missing build pet.json. Run scripts\motionfix_all_states_puppet.py first."
}
if (!(Test-Path -LiteralPath (Join-Path $buildFinal "spritesheet.webp"))) {
    throw "Missing build spritesheet.webp. Run scripts\motionfix_all_states_puppet.py first."
}

New-Item -ItemType Directory -Force -Path $package | Out-Null
Copy-Item -LiteralPath (Join-Path $buildFinal "pet.json") -Destination (Join-Path $package "pet.json") -Force
Copy-Item -LiteralPath (Join-Path $buildFinal "spritesheet.webp") -Destination (Join-Path $package "spritesheet.webp") -Force

Write-Host "Synced build output into installable package:"
Write-Host "  $package"
