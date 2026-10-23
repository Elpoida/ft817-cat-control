$ErrorActionPreference = "Stop"
$root = Split-Path -Parent $PSScriptRoot

Push-Location $root
try {
    if (!(Test-Path .venv)) { py -m venv .venv }
    & .\.venv\Scripts\python.exe -m pip install --upgrade pip
    & .\.venv\Scripts\python.exe -m pip install pyinstaller pyserial
    & .\.venv\Scripts\python.exe -m PyInstaller --noconfirm --clean --onefile --windowed `
        --name FT817CAT-cleanroom --icon packaging\icon.ico `
        --version-file packaging\version_info.txt --add-data "static;static" `
        --collect-submodules serial server.py
    Write-Host "Built dist\FT817CAT-cleanroom.exe"
}
finally {
    Pop-Location
}
