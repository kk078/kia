"""Stop monitoring stack."""

$ErrorActionPreference = "Stop"

Write-Host "Stopping monitoring stack..." -ForegroundColor Yellow

docker-compose -f docker-compose.monitoring.yml down

Write-Host "✓ Monitoring services stopped" -ForegroundColor Green
