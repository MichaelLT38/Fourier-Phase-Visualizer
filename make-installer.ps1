$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $root

if (-not (Test-Path "dist\FourierDragApp\FourierDragApp.exe")) {
    Write-Host "App executable not found. Building it first..."
    .\build.ps1
}

$isccCmd = Get-Command iscc.exe -ErrorAction SilentlyContinue
$isccCandidates = @(
    "C:\Program Files (x86)\Inno Setup 6\ISCC.exe",
    "C:\Program Files\Inno Setup 6\ISCC.exe",
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe")
)

$isccPath = $null
if ($isccCmd) {
    $isccPath = $isccCmd.Source
} else {
    foreach ($candidate in $isccCandidates) {
        if (Test-Path $candidate) {
            $isccPath = $candidate
            break
        }
    }
}

if (-not $isccPath) {
    Write-Host "Inno Setup was not found."
    Write-Host "Install it from: https://jrsoftware.org/isdl.php"
    Write-Host "Then rerun: ./make-installer.ps1"
    exit 1
}

Write-Host "Using Inno Setup compiler: $isccPath"
& $isccPath "installer\FourierDragApp.iss"

Write-Host ""
Write-Host "Installer build complete."
Write-Host "Share this file:"
Write-Host "  installer\Output\FourierDragApp-Setup.exe"
