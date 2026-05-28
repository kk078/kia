"""Stop production deployment."""

$ErrorActionPreference = "Stop"

Write-Host "Stopping production deployment..." -ForegroundColor Yellow

docker-compose -f docker-compose.prod.yml down

Write-Host "✓ Production services stopped" -ForegroundColor Green
