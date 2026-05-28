"""Setup script for Secondary Brain development environment."""

$ErrorActionPreference = "Stop"

Write-Host "Setting up Secondary Brain development environment..." -ForegroundColor Cyan

# Check prerequisites
Write-Host "`nChecking prerequisites..." -ForegroundColor Yellow

$pythonVersion = python --version 2>&1
if ($pythonVersion -notmatch "Python 3\.1[1-9]") {
    Write-Host "ERROR: Python 3.11+ required. Found: $pythonVersion" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Python: $pythonVersion" -ForegroundColor Green

$dotnetVersion = dotnet --version 2>&1
if ($dotnetVersion -notmatch "8\.0") {
    Write-Host "ERROR: .NET SDK 8.0 required. Found: $dotnetVersion" -ForegroundColor Red
    exit 1
}
Write-Host "✓ .NET SDK: $dotnetVersion" -ForegroundColor Green

$uvVersion = uv --version 2>&1
if (-not $uvVersion) {
    Write-Host "ERROR: uv not found. Install with: irm https://astral.sh/uv/install.ps1 | iex" -ForegroundColor Red
    exit 1
}
Write-Host "✓ uv: $uvVersion" -ForegroundColor Green

# Start infrastructure
Write-Host "`nStarting infrastructure services..." -ForegroundColor Yellow
docker-compose up -d
Start-Sleep -Seconds 5

# Check services
Write-Host "`nChecking infrastructure services..." -ForegroundColor Yellow

$services = @(
    @{Name="Redis"; Port=6379},
    @{Name="Weaviate"; Port=8081},
    @{Name="FalkorDB"; Port=6380},
    @{Name="Langfuse"; Port=3000}
)

foreach ($service in $services) {
    $result = Test-NetConnection -ComputerName localhost -Port $service.Port -WarningAction SilentlyContinue
    if ($result.TcpTestSucceeded) {
        Write-Host "✓ $($service.Name) (port $($service.Port))" -ForegroundColor Green
    } else {
        Write-Host "✗ $($service.Name) (port $($service.Port)) - NOT RESPONDING" -ForegroundColor Red
    }
}

# Install Python dependencies
Write-Host "`nInstalling Python dependencies..." -ForegroundColor Yellow
Set-Location agents
uv sync
Set-Location ..

# Create .env if it doesn't exist
if (-not (Test-Path .env)) {
    Write-Host "`nCreating .env from .env.example..." -ForegroundColor Yellow
    Copy-Item .env.example .env
    Write-Host "✓ Created .env - Please edit with your API keys" -ForegroundColor Green
} else {
    Write-Host "✓ .env already exists" -ForegroundColor Green
}

Write-Host "`n✓ Setup complete!" -ForegroundColor Cyan
Write-Host "`nNext steps:" -ForegroundColor Yellow
Write-Host "1. Edit .env with your API keys (Anthropic, OpenAI, etc.)"
Write-Host "2. Run tests: uv run pytest tests/unit -v"
Write-Host "3. Start developing!"
