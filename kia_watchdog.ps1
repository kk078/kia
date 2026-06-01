<#
KIA self-healing watchdog. Runs forever, polls /health every 30s, and if KIA is
unhealthy twice in a row it restarts whatever died: Ollama, the host runner, the
Cloudflare tunnel, and the native API. Logs every action to kia_watchdog.log.

This is what makes the native deployment recover on its own.
#>
$ROOT = "C:\dev"
$log  = "$ROOT\kia_watchdog.log"
function L($m){ Add-Content $log ((Get-Date -Format "yyyy-MM-dd HH:mm:ss") + "  " + $m) }

L "watchdog started"
$fails = 0
while ($true) {
    Start-Sleep -Seconds 30
    $ok = $false
    try {
        $h = Invoke-RestMethod "http://localhost:8000/health" -TimeoutSec 8
        if ($h.status -eq "healthy") { $ok = $true }
    } catch { $ok = $false }

    if ($ok) { $fails = 0; continue }

    $fails++
    L "health check FAILED ($fails)"
    if ($fails -lt 2) { continue }   # tolerate one blip

    L "RECOVERY: checking components"
    # Ollama
    if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
        $env:OLLAMA_HOST = "0.0.0.0"
        Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
        L "  restarted Ollama"
    }
    # Host runner (for /build)
    if (-not (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)) {
        Start-Process "pythonw" -ArgumentList ('"' + "$ROOT\host_runner\runner.py" + '"') -WindowStyle Hidden
        L "  restarted host runner"
    }
    # Cloudflare tunnel (public access)
    try {
        $svc = Get-Service -Name "Cloudflared" -ErrorAction SilentlyContinue
        if ($svc -and $svc.Status -ne "Running") { Start-Service "Cloudflared"; L "  restarted cloudflared" }
    } catch {}
    # Native API
    if (-not (Get-NetTCPConnection -LocalPort 8000 -State Listen -ErrorAction SilentlyContinue)) {
        & "$ROOT\kia_native_run.ps1" -Background
        L "  relaunched native API"
        Start-Sleep 10
    }
    $fails = 0
}
