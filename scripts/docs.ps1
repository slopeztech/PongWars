$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
if (-not (Get-Command doxygen -ErrorAction SilentlyContinue)) {
    throw "doxygen is not installed (winget install DimitriVanHeesch.Doxygen)"
}
doxygen docs\Doxyfile
if ((Test-Path docs\doxygen_warnings.log) -and (Get-Item docs\doxygen_warnings.log).Length -gt 0) {
    Get-Content docs\doxygen_warnings.log
    throw "Doxygen produced warnings"
}