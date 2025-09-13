# Install.ps1
# Windows PowerShell script for setting up Miniconda and a conda env named "viz"

# 1. Download latest Miniconda installer (64-bit Windows)
$MinicondaUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
$InstallerPath = "$env:TEMP\Miniconda3-latest-Windows-x86_64.exe"

Write-Host "Downloading Miniconda installer..."
Invoke-WebRequest -Uri $MinicondaUrl -OutFile $InstallerPath

# 2. Run the installer silently
Write-Host "Installing Miniconda silently..."
Start-Process -FilePath $InstallerPath -ArgumentList "/InstallationType=JustMe", "/AddToPath=1", "/S", "/D=$env:USERPROFILE\Miniconda3" -Wait

# 3. Initialize conda for PowerShell
$CondaExe = "$env:USERPROFILE\Miniconda3\Scripts\conda.exe"
& $CondaExe init powershell

# Reload shell so conda works
Write-Host "Reloading PowerShell profile to enable conda..."
. $PROFILE

# 4. Create the environment (if it doesn’t already exist)
Write-Host "Creating conda environment: viz"
& $CondaExe create -y -n viz python=3.11

# 5. Activate environment
Write-Host "Activating viz environment..."
& $CondaExe activate viz

Write-Host "Setup complete! Conda environment 'viz' is ready."
