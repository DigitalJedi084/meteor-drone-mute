<#
Switch which Meteor (meteorb) ROM variant VPinMAME loads.

  .\install-variant.ps1 breathing_bass
  .\install-variant.ps1 heartbeat
  .\install-variant.ps1 invader_march
  .\install-variant.ps1 clean        # silent: drone muted
  .\install-variant.ps1 forum        # silent: forum patch
  .\install-variant.ps1 original     # stock ROMs (from the backup)

Writes both roms\meteorb.zip and the loose files in roms\meteorb\, since PinMAME can load either.
#>
param(
    [Parameter(Mandatory)][ValidateSet('breathing_bass', 'heartbeat', 'invader_march', 'clean', 'forum', 'original')]
    [string]$Variant,
    [string]$VPinMAME = 'C:\vPinball\VisualPinball\VPinMAME'
)
$ErrorActionPreference = 'Stop'
$here = $PSScriptRoot
$roms = Join-Path $VPinMAME 'roms'
$backup = Join-Path $VPinMAME 'roms_backup_meteorb_original'

if (-not (Test-Path (Join-Path $backup 'meteorb.zip'))) {
    New-Item -ItemType Directory -Force $backup | Out-Null
    Copy-Item (Join-Path $roms 'meteorb.zip') $backup
    Write-Host "Backed up the current meteorb.zip to $backup"
}

$src = switch ($Variant) {
    'original' { Join-Path $backup 'meteorb.zip' }
    { $_ -in 'clean', 'forum' } { Join-Path $here "$Variant\meteorb.zip" }
    default { Join-Path $here "variants\$Variant\meteorb.zip" }
}
if (-not (Test-Path $src)) { throw "Missing $src - build it first (see README)." }

Copy-Item $src (Join-Path $roms 'meteorb.zip') -Force
$dir = Join-Path $roms 'meteorb'
if (Test-Path $dir) {
    $tmp = Join-Path $env:TEMP "meteorb_$([guid]::NewGuid())"
    Expand-Archive $src $tmp
    Copy-Item (Join-Path $tmp '*.716') $dir -Force
    Remove-Item $tmp -Recurse -Force
}
Write-Host "Installed '$Variant' as meteorb. Restart the table to hear it."
