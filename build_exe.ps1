param([string]$AppName = "Do")

$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $projectRoot

$venvDirectory = Join-Path $projectRoot ".venv-desktop"
$venvPython = Join-Path $venvDirectory "Scripts\python.exe"
if (-not (Test-Path -LiteralPath $venvPython)) {
    $basePython = Get-Command python -ErrorAction SilentlyContinue
    if ($basePython) {
        & $basePython.Source -m venv $venvDirectory
    } else {
        py -3.12 -m venv $venvDirectory
    }
    if ($LASTEXITCODE -ne 0) { throw "Could not create the desktop build environment. Install 64-bit Python 3.12 and retry." }
}

& $venvPython -m pip install -r requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { throw "Could not install desktop app dependencies." }

& $venvPython -m PyInstaller --clean --noconfirm --onefile --windowed `
    --name $AppName `
    --add-data "frontend;frontend" `
    --collect-all webview `
    --collect-all pystray `
    --hidden-import=pyaudio `
    --hidden-import=pyttsx3.drivers.sapi5 `
    --hidden-import=pystray `
    .\desktop_app.py
if ($LASTEXITCODE -ne 0) { throw "PyInstaller could not build $AppName.exe." }

$exampleEnv = Join-Path $projectRoot ".env.example"
$distEnv = Join-Path $projectRoot "dist\.env"
if (-not (Test-Path -LiteralPath $distEnv)) {
    Copy-Item -LiteralPath $exampleEnv -Destination $distEnv
}

Write-Host "Build complete: $projectRoot\dist\$AppName.exe"
Write-Host "Add your Gemini key to $distEnv before launching the app."
