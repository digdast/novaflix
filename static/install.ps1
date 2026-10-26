# ==============================================================================
# NovaFlix Sovereign Media Server - Windows Quick Install Script
# Usage:
#   irm https://novaflix.ertechlab.com/install.ps1 | iex
# ==============================================================================

Write-Host "=================================================" -ForegroundColor Cyan
Write-Host "  NovaFlix Sovereign Media Server - Windows Setup" -ForegroundColor Cyan
Write-Host "=================================================" -ForegroundColor Cyan

$InstallDir = "$env:LOCALAPPDATA\NovaFlix"
if (!(Test-Path $InstallDir)) {
    New-Item -ItemType Directory -Path $InstallDir -Force | Out-Null
}

Write-Host "[*] Checking Python and Git..." -ForegroundColor Yellow
if (!(Get-Command python -ErrorAction SilentlyContinue)) {
    Write-Host "[!] Python not found. Installing Python via winget..." -ForegroundColor Yellow
    winget install Python.Python.3.12 --accept-package-agreements --accept-source-agreements
}

Write-Host "[*] Fetching NovaFlix Server codebase..." -ForegroundColor Yellow
if (Test-Path "$InstallDir\.git") {
    Set-Location $InstallDir
    git pull
} else {
    try {
        git clone --depth 1 https://github.com/digdast/novaflix.git $InstallDir
        Set-Location $InstallDir
    } catch {
        Write-Host "[*] Downloading archive from NovaFlix hub..." -ForegroundColor Yellow
        $zipPath = "$env:TEMP\NovaFlix-Portable.zip"
        Invoke-WebRequest -Uri "https://novaflix.ertechlab.com/downloads/NovaFlix-Portable.zip" -OutFile $zipPath
        Expand-Archive -Path $zipPath -DestinationPath $InstallDir -Force
    }
}

Set-Location $InstallDir

Write-Host "[*] Setting up Python virtual environment..." -ForegroundColor Yellow
python -m venv "$InstallDir\venv"
& "$InstallDir\venv\Scripts\pip.exe" install --upgrade pip --quiet
& "$InstallDir\venv\Scripts\pip.exe" install -r "$InstallDir\requirements.txt" --quiet

# Create Desktop Shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut("$env:USERPROFILE\Desktop\NovaFlix Server.lnk")
$Shortcut.TargetPath = "$InstallDir\venv\Scripts\uvicorn.exe"
$Shortcut.Arguments = "novaflix.main:app --host 0.0.0.0 --port 8096"
$Shortcut.WorkingDirectory = $InstallDir
$Shortcut.IconLocation = "$InstallDir\static\favicon.ico,0"
$Shortcut.Save()

Write-Host "[*] Launching NovaFlix Server on http://localhost:8096..." -ForegroundColor Green
Start-Process "$InstallDir\venv\Scripts\uvicorn.exe" -ArgumentList "novaflix.main:app --host 0.0.0.0 --port 8096" -WorkingDirectory $InstallDir

Start-Sleep -Seconds 2
Start-Process "http://localhost:8096"

Write-Host "=================================================" -ForegroundColor Green
Write-Host "  NovaFlix Server is now running on http://localhost:8096!" -ForegroundColor Green
Write-Host "  A shortcut has been placed on your Desktop." -ForegroundColor Green
Write-Host "=================================================" -ForegroundColor Green
