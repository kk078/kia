<#
.SYNOPSIS
  Remove the always-on KIA Host Runner scheduled task.

.DESCRIPTION
  Stops and unregisters the "KIA Host Runner" task. After this, KIA can no longer
  execute commands on the host (by design) until you start the runner again
  (manually or by re-installing the task). The .runner_token file is left in
  place; delete it manually if you want to rotate the secret.

  Run from an elevated PowerShell.
#>
$ErrorActionPreference = "Stop"
$taskName = "KIA Host Runner"

$task = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if (-not $task) {
  Write-Host "Task '$taskName' is not installed — nothing to do."
  return
}
Stop-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
Unregister-ScheduledTask -TaskName $taskName -Confirm:$false
Write-Host "Removed '$taskName'. The runner is no longer running at logon." -ForegroundColor Green
Write-Host "(.runner_token left in place; delete it to rotate the secret.)"
