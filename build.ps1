<#
    Build WindowsAIBackup.exe

        powershell -ExecutionPolicy Bypass -File .\build.ps1

    Produces dist\WindowsAIBackup.exe — a single self-contained file with no
    Python installation required on the target machine.
#>
[CmdletBinding()]
param(
    [switch] $SkipDeps,
    [switch] $Clean
)

$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot

function Write-Step($Text) {
    Write-Host ''
    Write-Host "==> $Text" -ForegroundColor Cyan
}

if ($Clean) {
    Write-Step 'Cleaning previous build output'
    foreach ($dir in 'build', 'dist', '__pycache__') {
        if (Test-Path $dir) { Remove-Item $dir -Recurse -Force }
    }
    Get-ChildItem -Filter '*.spec' -File | Remove-Item -Force
}

if (-not $SkipDeps) {
    Write-Step 'Installing build dependencies'
    python -m pip install --upgrade pip
    python -m pip install -r requirements.txt pyinstaller
}

Write-Step 'Running tests'
python -m pytest tests -q
if ($LASTEXITCODE -ne 0) { throw 'Tests failed - not building.' }

Write-Step 'Building single-file executable'
python -m PyInstaller `
    --onefile `
    --name WindowsAIBackup `
    --console `
    --clean `
    --noconfirm `
    --collect-submodules waib `
    --add-data "waib/data;waib/data" `
    --hidden-import cryptography.hazmat.primitives.ciphers.aead `
    --hidden-import cryptography.hazmat.primitives.asymmetric.ed25519 `
    --hidden-import yaml `
    --exclude-module tkinter `
    --exclude-module matplotlib `
    --exclude-module numpy `
    --exclude-module PIL `
    --exclude-module pytest `
    entrypoint.py

if ($LASTEXITCODE -ne 0) { throw 'PyInstaller failed.' }

$exe = Join-Path $PSScriptRoot 'dist\WindowsAIBackup.exe'
if (-not (Test-Path $exe)) { throw "Expected $exe to exist." }

Write-Step 'Smoke test'
& $exe --version
& $exe catalog --validate
& $exe scan | Select-Object -First 6

$size = [math]::Round((Get-Item $exe).Length / 1MB, 1)
Write-Host ''
Write-Host "Built: $exe ($size MB)" -ForegroundColor Green
Write-Host ''
Write-Host 'Usage:' -ForegroundColor Cyan
Write-Host '    .\dist\WindowsAIBackup.exe                 # interactive menu'
Write-Host '    .\dist\WindowsAIBackup.exe scan'
Write-Host '    .\dist\WindowsAIBackup.exe backup --secrets'
Write-Host '    .\dist\WindowsAIBackup.exe restore -b <folder> --apply'
