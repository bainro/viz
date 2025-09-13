Write-Host "DEBUG: Checking for conda.exe..."
try {
    $CondaExe = (Get-Command conda.exe -ErrorAction Stop).Source
    Write-Host "DEBUG: Found conda.exe at $CondaExe"
} catch {
    Write-Host "DEBUG: conda.exe not found in PATH"
    $CondaExe = "$env:USERPROFILE\Miniconda3\Scripts\conda.exe"
    Write-Host "DEBUG: Falling back to default Miniconda path: $CondaExe"
}

if ($CondaExe -match "Anaconda3") {
    Write-Host "🐁 Anaconda detected at: $CondaExe"
    Write-Host "Skipping conda init and unblock..."
} else {
    Write-Host "🐁 Miniconda (or no Anaconda) detected at: $CondaExe"
    Write-Host "Running conda init and unblock..."
    & $CondaExe init powershell

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
            Write-Host "DEBUG: Unblocked profile script: $p"
        } catch {
            Write-Host "DEBUG: Failed to unblock $p"
        }
    }
}

echo 'success!'
