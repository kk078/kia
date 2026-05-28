"""Start monitoring stack."""

$ErrorActionPreference = "Stop"

Write-Host "Starting monitoring stack..." -ForegroundColor Cyan

docker-compose -f docker-compose.monitoring.yml up -d

Write-Host "`nWaiting for services to start..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

Write-Host "`nMonitoring services:" -ForegroundColor Yellow
Write-Host "  Prometheus:  http://localhost:9090"
Write-Host "  Grafana:     http://localhost:3002 (admin/admin)"
Write-Host "  Loki:        http://localhost:3100"

Write-Host "`n✓ Monitoring stack started!" -ForegroundColor Green
