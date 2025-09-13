# Install.ps1
# Windows PowerShell script to install Miniconda, create "viz" env, and install dependencies

# Ensure profile scripts can load (needed for conda init)
# This sets policy only for the current user (safe, doesn't touch system-wide)
Write-Host "Setting PowerShell execution policy to RemoteSigned for current user..."
Set-ExecutionPolicy Bypass -Scope Process -Force
Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force

# 1. Download Miniconda installer
$MinicondaUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
$InstallerPath = "$env:TEMP\Miniconda3-latest-Windows-x86_64.exe"

Write-Host "Downloading Miniconda installer..."
Invoke-WebRequest -Uri $MinicondaUrl -OutFile $InstallerPath

# 2. Install Miniconda silently
Write-Host "Installing Miniconda..."
Start-Process -FilePath $InstallerPath -ArgumentList "/InstallationType=JustMe", "/AddToPath=1", "/S", "/D=$env:USERPROFILE\Miniconda3" -Wait

# 3. Initialize conda for PowerShell
$CondaExe = "$env:USERPROFILE\Miniconda3\Scripts\conda.exe"
& $CondaExe init powershell

Write-Host "Setup complete! Restart Powershell and navigate back here"
