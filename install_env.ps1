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

# 4.5 accept certain ch's
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/main
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/r
conda tos accept --override-channels --channel https://repo.anaconda.com/pkgs/msys2

# --- 5. Create viz environment and install dependencies ---
Write-Host "Creating conda environment: viz"
& $CondaExe create -y -n viz python=3.11

Write-Host "Installing Python packages into viz..."
& $CondaExe run -n viz pip install numpy opencv-python flask flask-cors werkzeug

Write-Host "`n======================================="
Write-Host " ✅ Conda initialized for PowerShell"
Write-Host " ✅ viz environment created with dependencies"
Write-Host "INSTALL COMPLETED"
Write-Host "======================================="
