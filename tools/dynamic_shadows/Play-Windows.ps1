param(
    [string]$Iwad,
    [ValidatePattern('^[A-Za-z0-9_]{0,8}$')]
    [string]$Map = '',
    [switch]$LegacyLighting,
    [switch]$SkipMaterialBuild,
    [switch]$SkipActorShadows
)

$ErrorActionPreference = 'Stop'
$root = $PSScriptRoot
$exe = Join-Path $root 'runtime\vkdoom.exe'
if (!(Test-Path -LiteralPath $exe -PathType Leaf)) {
    throw "Source-matched Windows executable missing: $exe"
}

if (!$Iwad) {
    Add-Type -AssemblyName System.Windows.Forms
    $picker = New-Object System.Windows.Forms.OpenFileDialog
    $picker.Filter = 'Doom-family WAD|*.wad|All files|*.*'
    $picker.Title = 'Select your Doom-family IWAD'
    if ($picker.ShowDialog() -ne [System.Windows.Forms.DialogResult]::OK) { exit 0 }
    $Iwad = $picker.FileName
}
$iwadPath = (Get-Item -LiteralPath $Iwad -ErrorAction Stop).FullName
$files = New-Object 'System.Collections.Generic.List[string]'
$flashlight = Join-Path $root 'Local-Flashlight.pk3'

$stock = @('DoomII-NormalPBR.pk3','DoomII-SpritePBR.pk3')
$wadHash = (Get-FileHash -Algorithm SHA256 -LiteralPath $iwadPath).Hash.ToLowerInvariant()
$materialRoot = Join-Path $root ('local-materials\' + $wadHash)
$materialsReady = @($stock | Where-Object { Test-Path -LiteralPath (Join-Path $materialRoot $_) -PathType Leaf }).Count -eq $stock.Count
$wantMaterials = !$SkipMaterialBuild -and !$LegacyLighting
if ($wantMaterials -and !$materialsReady) {
    if (Test-Path -LiteralPath $materialRoot) {
        # Keep an incomplete cache for inspection while rebuilding atomically.
        $backup = $materialRoot + '.incomplete-' + [Guid]::NewGuid().ToString('N')
        Move-Item -LiteralPath $materialRoot -Destination $backup
    }
    $generatorExe = Join-Path $root 'tools\material-generator\Build-PR190-Materials.exe'
    Write-Host 'Generating the original PR #190 material profiles for this WAD...' -ForegroundColor Cyan
    if (Test-Path -LiteralPath $generatorExe -PathType Leaf) {
        & $generatorExe --doom2 $iwadPath --out $materialRoot
    } else {
        $python = Get-Command py -ErrorAction SilentlyContinue
        $pythonArgs = @('-3')
        if (!$python) {
            $python = Get-Command python -ErrorAction SilentlyContinue
            $pythonArgs = @()
        }
        $generator = Join-Path $root 'tools\dynamic_shadows\build_pr190_materials.py'
        if (!$python -or !(Test-Path -LiteralPath $generator -PathType Leaf)) {
            throw 'Material generator missing. Extract the complete Windows package. Use -SkipMaterialBuild only to play without generated PBR materials.'
        }
        & $python.Source @pythonArgs $generator --doom2 $iwadPath --out $materialRoot
    }
    if ($LASTEXITCODE -ne 0) {
        throw 'Original PBR material generation failed. See the error above. Use -SkipMaterialBuild only to play without generated PBR materials.'
    }
}
foreach ($name in $stock) {
    $item = Join-Path $materialRoot $name
    if (Test-Path -LiteralPath $item -PathType Leaf) { $files.Add($item) }
}
if (Test-Path -LiteralPath $flashlight -PathType Leaf) { $files.Add($flashlight) }

Write-Host 'ShadeDoomVK SHADOW-002 research: light-facing source-alpha occlusion; owner visual acceptance pending.' -ForegroundColor Yellow
Write-Host "Engine: $exe"
Write-Host "IWAD SHA256: $wadHash"
Write-Host "PBR packs loaded: $(@($files | Where-Object { $_ -like '*PBR.pk3' }).Count) / 2"
if (@($files | Where-Object { $_ -like '*PBR.pk3' }).Count -ne 2) {
    if ($wantMaterials) { throw 'Material generation did not produce both required PBR packs.' }
    Write-Host 'Playing without generated PBR materials, as requested.'
}
$argv = @('-iwad', $iwadPath, '-noautoload', '-noautoexec', '-config', (Join-Path $root 'shadow002.ini'))
if ($files.Count) { $argv += @('-file') + @($files) }
$actor = if ($SkipActorShadows -or $LegacyLighting) { 'false' } else { 'true' }
$world = if ($LegacyLighting) { '0' } else { '1' }
$argv += @(
    '-window', '-width', '1280', '-height', '720',
    '+vid_rendermode', '4',
    '+gl_lights', 'true', '+gl_light_sprites', 'true', '+gl_light_particles', 'true',
    '+gl_spritelight', '2', '+gl_viewmodel_lighting', '2',
    '+gl_lightprobe', 'true', '+gl_customshader', 'true', '+gl_ubershaders', 'false',
    '+gl_levelmesh', 'false', '+gl_light_shadows', $world,
    '+gl_actor_light_shadows', $actor, '+r_actorspriteshadow', '0'
)
# Starting at the game's own menu supports both MAP01 and ExMy IWADs.
# An explicit -Map MAP01 or -Map E1M1 remains available for repeatable playtests.
if ($Map) { $argv += @('+map', $Map) }
# Running the program is the purpose of this script. Never print-only.
Push-Location -LiteralPath $root
try {
    & $exe @argv
    $result = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $result
