<#
.SYNOPSIS
  Install the KIA Host Runner as an always-on Windows scheduled task.

.DESCRIPTION
  Registers a task "KIA Host Runner" that starts at logon, runs runner.py via
  pythonw (no console window), restarts on failure, and runs indefinitely. The
  token is stored in host_runner\.runner_token (gitignored) so the background
  task needs no environment plumbing.

  Run this from an ELEVATED PowerShell (Run as Administrator) so it can register
  the task. The runner itself runs at your normal (non-admin) level unless you
  pass -Elevated.

.PARAMETER Token
  The shared secret. Must match HOST_RUNNER_TOKEN in C:\dev\.env. If omitted,
  reuses an existing .runner_token, or generates a new one and prints it.

.PARAMETER Elevated
  Run the runner with highest privileges (lets installs that need admin succeed
  without a UAC prompt). More powerful and riskier — off by default.

.EXAMPLE
  .\install_task.ps1 -Token "my-long-secret-matching-dotenv"
#>
param(
  [string]$Token = "",
  [switch]$Elevated
)

$ErrorActionPreference = "Stop"
$here = $PSScriptRoot
$tokenFile = Join-Path $here ".runner_token"
$taskName = "KIA Host Runner"

# 1. Resolve the token: param > existing file > generate.
if (-not $Token) {
  if (Test-Path $tokenFile) {
    $Token = (Get-Content $tokenFile -Raw).Trim()
    Write-Host "Reusing existing token from .runner_token."
  } else {
    $Token = ([guid]::NewGuid().ToString('N') + [guid]::NewGuid().ToString('N'))
    Write-Host "Generated a new token:" -ForegroundColor Yellow
    Write-Host "    $Token" -ForegroundColor Yellow
    Write-Host "  -> Put this in C:\dev\.env as HOST_RUNNER_TOKEN=$Token" -ForegroundColor Yellow
    Write-Host "     then: docker compose -f docker-compose.prod.yml up -d python-api" -ForegroundColor Yellow
  }
}
Set-Content -Path $tokenFile -Value $Token -NoNewline -Encoding ascii
Write-Host "Token written to $tokenFile"

# 2. Find pythonw (preferred: no console) or python.
$py = (Get-Command pythonw.exe -ErrorAction SilentlyContinue).Source
if (-not $py) { $py = (Get-Command python.exe -ErrorAction SilentlyContinue).Source }
if (-not $py) { throw "Python not found on PATH. Install Python or add it to PATH." }
Write-Host "Using interpreter: $py"

# 3. (Re)register the scheduled task.
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false -ErrorAction SilentlyContinue

$action  = New-ScheduledTaskAction -Execute $py -Argument "runner.py" -WorkingDirectory $here
$trigger = New-ScheduledTaskTrigger -AtLogOn
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries `
  -StartWhenAvailable -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1) -Hidden
$settings.ExecutionTimeLimit = "PT0S"   # run indefinitely
$runLevel = if ($Elevated) { "Highest" } else { "Limited" }
$principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel $runLevel

Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger `
  -Settings $settings -Principal $principal -Description "KIA host command runner (always-on)" | Out-Null

Start-ScheduledTask -TaskName $taskName
Start-Sleep -Seconds 2

Write-Host ""
Write-Host "Installed and started '$taskName' (RunLevel=$runLevel)." -ForegroundColor Green
Write-Host "Verify:  curl.exe http://localhost:8000/api/v1/exec/status"
Write-Host "Logs:    $here\host_runner.log"
Write-Host "Remove:  .\uninstall_task.ps1"
