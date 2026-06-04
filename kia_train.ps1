<#
.SYNOPSIS
  Run KIA's LoRA fine-tune pipeline (prepare -> train -> export) with the right env baked in.

.DESCRIPTION
  Loads .env, sets PYTHONUTF8=1 (avoids the Windows cp1252 bug in TRL's chat-template loader),
  and runs the three stages against agents/.venv. Use -Smoke for an 8-step mechanics-validation
  run; omit it for a full 3-epoch run. Use -SkipPrepare to reuse the existing dataset.

  CPU WARNING: with CPU-only torch, a step over 8k-token sequences takes ~1 hour. The 8-step
  smoke run is ~8 hours; a full run on a few hundred traces would take days/weeks. Do the real
  run on a CUDA GPU.

.EXAMPLE
  .\kia_train.ps1 -Smoke
.EXAMPLE
  .\kia_train.ps1            # full run
.EXAMPLE
  .\kia_train.ps1 -SkipPrepare
#>
param(
  [switch]$Smoke,
  [switch]$SkipPrepare
)

$ErrorActionPreference = "Stop"
$ROOT = "C:\dev"; $AGENTS = "$ROOT\agents"; $PY = "$AGENTS\.venv\Scripts\python.exe"

if (Test-Path "$ROOT\.env") {
    Get-Content "$ROOT\.env" | ForEach-Object {
        $l = $_.Trim()
        if ($l -and -not $l.StartsWith('#') -and $l.Contains('=')) {
            $i = $l.IndexOf('=')
            [Environment]::SetEnvironmentVariable($l.Substring(0,$i).Trim(), $l.Substring($i+1).Trim(), 'Process')
        }
    }
}
$env:PYTHONUTF8     = "1"
$env:PYTHONUNBUFFERED = "1"
if ($Smoke) { $env:TRAIN_SMOKE = "1" } else { Remove-Item Env:\TRAIN_SMOKE -ErrorAction SilentlyContinue }

Set-Location $AGENTS

if (-not $SkipPrepare) {
    Write-Host "[1/3] prepare: building SFT dataset from traces..." -ForegroundColor Cyan
    & $PY -m brain_train.prepare
}

$mode = if ($Smoke) { "SMOKE (8 steps)" } else { "FULL (3 epochs)" }
Write-Host "[2/3] train: $mode ..." -ForegroundColor Cyan
& $PY -m brain_train.train_lora

Write-Host "[3/3] export: merge LoRA + write Modelfile..." -ForegroundColor Cyan
& $PY -m brain_train.export_ollama

Write-Host ""
Write-Host "Done. Register in Ollama:" -ForegroundColor Green
Write-Host "  ollama create kia-coder -f $ROOT\data\Modelfile.kia-coder"
