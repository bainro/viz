# Install.ps1
# PowerShell script to install Miniconda, set execution policy, & unblock profile scripts

# --- Execution policy setup ---
# Ensure this session can run scripts
Set-ExecutionPolicy Bypass -Scope Process -Force -ErrorAction SilentlyContinue

# Try to persist a safer policy for this user
try {
    Set-ExecutionPolicy RemoteSigned -Scope CurrentUser -Force -ErrorAction Stop
} catch [System.Management.Automation.PSSecurityException] {
    Write-Host "ExecutionPolicy is locked by Group Policy. Skipping..."
} catch {
    Write-Host "Could not change execution policy: $($_.Exception.Message)"
}

# --- 1. Download Miniconda installer ---
$MinicondaUrl = "https://repo.anaconda.com/miniconda/Miniconda3-latest-Windows-x86_64.exe"
$InstallerPath = "$env:TEMP\Miniconda3-latest-Windows-x86_64.exe"

Write-Host "Downloading Miniconda installer..."
Invoke-WebRequest -Uri $MinicondaUrl -OutFile $InstallerPath

# --- 2. Install Miniconda silently ---
Write-Host "Installing Miniconda..."
Start-Process -FilePath $InstallerPath -ArgumentList "/InstallationType=JustMe", "/AddToPath=1", "/S", "/D=$env:USERPROFILE\Miniconda3" -Wait

Write-Host "`n======================================="
Write-Host " ✅ Miniconda installed"
Write-Host "Next steps:"
Write-Host " 1. Close this PowerShell window"
Write-Host " 2. Open a new PowerShell"
Write-Host " 3. Run: conda activate viz"
Write-Host "======================================="
