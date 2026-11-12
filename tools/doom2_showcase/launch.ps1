param(
    [Parameter(Mandatory)]
    [ValidateSet('DoomII', 'DBP50', 'Gallery', 'Flashlight')]
    [string]$Game,

    [Parameter(Mandatory)]
    [string]$Exe,

    [Parameter(Mandatory)]
    [string]$Doom2,

    [Parameter(Mandatory)]
    [string]$Packages,

    [string]$DBP50,

    [switch]$DesktopShortcut
)

$ErrorActionPreference = 'Stop'
$engine = (Get-Item -LiteralPath $Exe).FullName
$iwad = (Get-Item -LiteralPath $Doom2).FullName
$root = (Get-Item -LiteralPath $Packages).FullName
$gameFiles = @()
$map = 'MAP01'
$uber = 'true'
$weapon = 'true'

switch ($Game) {
    'DBP50' {
        if (!$DBP50) { throw 'Supply -DBP50 with the DBP50 PWAD path.' }
        $gameFiles += (Get-Item -LiteralPath $DBP50).FullName
    }
    'Gallery' {
        $map = 'SGSHOW'
        $uber = 'false'
        $weapon = 'false'
    }
}
if ($Game -in 'DoomII', 'DBP50') {
    $gameFiles += Join-Path $root "$Game-NormalPBR.pk3"
    $gameFiles += Join-Path $root "$Game-SpritePBR.pk3"
}
if ($Game -eq 'Gallery') {
    $gameFiles += Join-Path $root 'DoomII-Material-Gallery.pk3'
} else {
    $gameFiles += Join-Path $root 'Local-Flashlight.pk3'
}
foreach ($file in $gameFiles) {
    if (!(Test-Path -LiteralPath $file -PathType Leaf)) { throw "Package missing: $file" }
}

$config = Join-Path $root "$Game.ini"
$save = Join-Path $root "$Game-saves"
New-Item -ItemType Directory -Force -Path $save | Out-Null
$argv = @('-iwad', $iwad, '-noautoload', '-noautoexec', '-file') + $gameFiles + @(
    '-config', $config, '-savedir', $save, '-window', '-width', '1280', '-height', '720',
    '+vid_rendermode', '4', '+gl_viewmodel_lighting', '2',
    '+gl_spritelight', '2', '+gl_lights', 'true', '+gl_light_sprites', 'true',
    '+gl_light_particles', 'true', '+gl_lightprobe', 'true', '+gl_customshader', 'true',
    '+gl_ubershaders', $uber, '+r_drawplayersprites', $weapon, '+gl_levelmesh', 'false',
    '+gl_light_shadows', '0', '+vk_rayquery', 'false', '+cl_capfps', 'true', '+gl_precache', 'true',
    '+map', $map
)
if ($Game -eq 'Gallery') {
    $argv += @('+bind', 'F1', 'openmenu MaterialGalleryMenu')
}
# All filesystem arguments are resolved Windows paths, where double quotes
# are invalid. Quoting each argument also preserves whitespace in paths.
$arguments = ($argv | ForEach-Object { '"' + $_ + '"' }) -join ' '
$workingDir = Split-Path -Parent $engine
if ($DesktopShortcut) {
    $names = @{
        DoomII = 'Doom II Materials'
        DBP50 = 'DBP50 Materials'
        Gallery = 'Doom II Material Gallery'
        Flashlight = 'Doom II Flashlight'
    }
    $desktop = [Environment]::GetFolderPath('Desktop')
    $path = Join-Path $desktop "ShadeDoomVK - $($names[$Game]) (Hardware).lnk"
    $shell = New-Object -ComObject WScript.Shell
    $link = $shell.CreateShortcut($path)
    $link.TargetPath = $engine
    $link.Arguments = $arguments
    $link.WorkingDirectory = $workingDir
    $link.IconLocation = "$engine,0"
    $link.Save()
    Write-Output $path
} else {
    Start-Process -FilePath $engine -WorkingDirectory $workingDir -ArgumentList $arguments -WindowStyle Normal
}
