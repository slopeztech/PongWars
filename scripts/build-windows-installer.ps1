$ErrorActionPreference = "Stop"

$repoRoot = Split-Path -Parent $PSScriptRoot
Set-Location $repoRoot

$iscc = Get-Command "ISCC.exe" -ErrorAction SilentlyContinue
if ($iscc) {
    $isccPath = $iscc.Source
} else {
    $candidates = @(
        (Join-Path $env:LOCALAPPDATA "Programs\Inno\ISCC.exe"),
        (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
        (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
        (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
    )
    $isccPath = $candidates | Where-Object { Test-Path $_ } | Select-Object -First 1
}

if (-not $isccPath) {
    throw "Inno Setup 6 was not found. Install it or add ISCC.exe to PATH."
}

$version = & python -c "from pongwars import __version__; print(__version__)"
if ($LASTEXITCODE -ne 0 -or -not $version) {
    throw "Could not read the project version from pyproject.toml."
}

$buildRoot = Join-Path $repoRoot "build\windows"
$distDir = Join-Path $buildRoot "dist"
$workDir = Join-Path $buildRoot "work"
$packageDir = Join-Path $distDir "PongWars"
$outputDir = Join-Path $buildRoot "installer"
$dataDir = Join-Path $repoRoot "src\pongwars\data"
$entryPoint = Join-Path $repoRoot "src\pongwars\__main__.py"
$scriptFile = Join-Path $PSScriptRoot "windows-installer.iss"

New-Item -ItemType Directory -Force -Path $outputDir | Out-Null

$pyInstallerArgs = @(
    "--noconfirm",
    "--clean",
    "--windowed",
    "--name", "PongWars",
    "--paths", (Join-Path $repoRoot "src"),
    "--add-data", "$dataDir;pongwars\data",
    "--distpath", $distDir,
    "--workpath", $workDir,
    "--specpath", $buildRoot,
    $entryPoint
)

& python -m PyInstaller @pyInstallerArgs
if ($LASTEXITCODE -ne 0) {
    throw "PyInstaller failed with exit code $LASTEXITCODE."
}

& $isccPath "/DAppVersion=$version" "/DSourceDir=$packageDir" "/O$outputDir" "/FPongWars-Setup-$version" $scriptFile
if ($LASTEXITCODE -ne 0) {
    throw "Inno Setup failed with exit code $LASTEXITCODE."
}

Write-Host "Installer created: $(Join-Path $outputDir "PongWars-Setup-$version.exe")"
