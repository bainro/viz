# Install.ps1
# Windows PowerShell script to install Miniconda, create "viz" env, and install dependencies

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

# Reload profile
Write-Host "Reloading PowerShell profile..."
. $PROFILE

# 4. Create viz environment
Write-Host "Creating conda environment: viz"
& $CondaExe create -y -n viz python=3.11

# 5. Install dependencies
Write-Host "Installing Python packages..."
& $CondaExe run -n viz pip install numpy opencv-python flask flask-cors werkzeug

# 6. Activate environment
Write-Host "Activating environment: viz"
& $CondaExe activate viz

Write-Host "Setup complete! Conda environment 'viz' is ready with all dependencies installed."
