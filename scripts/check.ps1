$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$env:SDL_VIDEODRIVER = "dummy"
$env:SDL_AUDIODRIVER = "dummy"

ruff check src tests
ruff format --check src tests
mypy src
pytest --cov=pongwars --cov-report=term-missing

if ($args -contains "-Docs") { & "$PSScriptRoot\docs.ps1" }
