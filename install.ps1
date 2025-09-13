# Install.ps1
# Windows PowerShell script to install Miniconda, set execution policy,
# create "viz" env, install dependencies, and unblock profile scripts

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

# --- 3. Initialize conda for PowerShell ---
$CondaExe = "$env:USERPROFILE\Miniconda3\Scripts\conda.exe"
& $CondaExe init powershell

# --- 4. Unblock profile scripts so conda init works ---
$allProfiles = @(
    $PROFILE,
    $PROFILE.AllUsersAllHosts,
    $PROFILE.AllUsersCurrentHost,
    $PROFILE.CurrentUserAllHosts,
    $PROFILE.CurrentUserCurrentHost
) | Where-Object { Test-Path $_ }

foreach ($p in $allProfiles) {
    try {
        Unblock-File -Path $p -ErrorAction SilentlyContinue
        Write-Host "Unblocked profile script: $p"
    } catch {}
}

# --- 5. Create viz environment and install dependencies ---
Write-Host "Creating conda environment: viz"
& $CondaExe create -y -n viz python=3.11

Write-Host "Installing Python packages into viz..."
& $CondaExe run -n viz pip install numpy opencv-python flask flask-cors werkzeug

Write-Host "`n======================================="
Write-Host " ✅ Miniconda installed"
Write-Host " ✅ Conda initialized for PowerShell"
Write-Host " ✅ viz environment created with dependencies"
Write-Host "Next steps:"
Write-Host " 1. Close this PowerShell window"
Write-Host " 2. Open a new PowerShell"
Write-Host " 3. Run: conda activate viz"
Write-Host "======================================="
