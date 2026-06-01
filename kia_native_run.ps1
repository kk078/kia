<#
Run KIA's API NATIVELY (no Docker/Podman/WSL): uvicorn from the host .venv,
embedded Chroma + SQLite, everything on localhost.

Loads C:\dev\.env into the process, applies native overrides, ensures Ollama and
the host runner are up, then starts uvicorn. -Background runs it detached + logged.
#>
param([switch]$Background)

$ROOT   = "C:\dev"
$AGENTS = "$ROOT\agents"
$PY     = "$AGENTS\.venv\Scripts\python.exe"

# 1. Load .env into the process environment (pydantic reads os.environ regardless of cwd).
if (Test-Path "$ROOT\.env") {
    Get-Content "$ROOT\.env" | ForEach-Object {
        $l = $_.Trim()
        if ($l -and -not $l.StartsWith('#') -and $l.Contains('=')) {
            $i = $l.IndexOf('=')
            [Environment]::SetEnvironmentVariable($l.Substring(0,$i).Trim(), $l.Substring($i+1).Trim(), 'Process')
        }
    }
}

# 2. Native overrides — embedded stores, localhost everything, Windows data paths.
$env:VECTOR_BACKEND        = "chroma"
$env:STORAGE_BACKEND       = "sqlite"
$env:CHROMA_PATH           = "$ROOT\data\chroma"
$env:SQLITE_PATH           = "$ROOT\data\kia.db"
$env:OLLAMA_BASE_URL       = "http://localhost:11434"
$env:HOST_RUNNER_URL       = "http://localhost:8765"
$env:TRAINING_CAPTURE_PATH = "$ROOT\data\kia_train.jsonl"
$env:CONNECTORS_CONFIG     = "$ROOT\data\connectors.json"
$env:ENVIRONMENT           = "production"

# 3. Ensure Ollama (bound to all interfaces) and the host runner are up.
if (-not (Get-Process ollama -ErrorAction SilentlyContinue)) {
    $env:OLLAMA_HOST = "0.0.0.0"
    Start-Process "ollama" -ArgumentList "serve" -WindowStyle Hidden
    Start-Sleep 5
}
if (-not (Get-NetTCPConnection -LocalPort 8765 -State Listen -ErrorAction SilentlyContinue)) {
    Start-Process "pythonw" -ArgumentList ('"' + "$ROOT\host_runner\runner.py" + '"') -WindowStyle Hidden
}

# 4. Launch uvicorn from the agents source dir (api package resolves via cwd).
if ($Background) {
    Start-Process $PY `
        -ArgumentList "-m","uvicorn","api.main:app","--host","0.0.0.0","--port","8000" `
        -WorkingDirectory $AGENTS -WindowStyle Hidden `
        -RedirectStandardOutput "$ROOT\kia_api.out.log" -RedirectStandardError "$ROOT\kia_api.err.log"
} else {
    Set-Location $AGENTS
    & $PY -m uvicorn api.main:app --host 0.0.0.0 --port 8000
}
