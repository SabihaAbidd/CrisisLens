$ErrorActionPreference = "Stop"
$PSNativeCommandUseErrorActionPreference = $false

$projectRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$streamlitExe = "C:\Users\Sabih\AppData\Local\Programs\Python\Python313\Scripts\streamlit.exe"
$logDir = Join-Path $projectRoot "artifacts"
$logPath = Join-Path $logDir "streamlit.log"

if (!(Test-Path $logDir)) {
    New-Item -ItemType Directory -Path $logDir | Out-Null
}

Set-Location $projectRoot

while ($true) {
    Add-Content -Path $logPath -Value "`n[$(Get-Date -Format s)] Starting Streamlit..."
    $previousErrorActionPreference = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"

        # Streamlit emits normal startup messages on stderr. With the global
        # "Stop" preference, PowerShell can otherwise treat those as failures.
        & $streamlitExe run ui/app.py --server.port 8501 --server.headless true 2>&1 |
            ForEach-Object {
                $line = $_.ToString()
                Write-Output $line
                Add-Content -Path $logPath -Value $line
            }
    } catch {
        Add-Content -Path $logPath -Value "[$(Get-Date -Format s)] Launcher caught error: $($_.Exception.Message)"
    } finally {
        $ErrorActionPreference = $previousErrorActionPreference
    }
    Add-Content -Path $logPath -Value "[$(Get-Date -Format s)] Streamlit exited. Restarting in 3 seconds..."
    Start-Sleep -Seconds 3
}
