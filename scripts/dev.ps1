"""Development script to run all services."""

$ErrorActionPreference = "Stop"

Write-Host "Starting Secondary Brain development environment..." -ForegroundColor Cyan

# Start infrastructure
Write-Host "`nStarting infrastructure..." -ForegroundColor Yellow
docker-compose up -d

# Wait for services
Write-Host "Waiting for services to be ready..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check services
Write-Host "`nService status:" -ForegroundColor Yellow
docker-compose ps

Write-Host "`n✓ Infrastructure running!" -ForegroundColor Cyan
Write-Host "`nServices:" -ForegroundColor Yellow
Write-Host "  Redis:     redis://localhost:6379"
Write-Host "  Weaviate:  http://localhost:8081"
Write-Host "  FalkorDB:  redis://localhost:6380"
Write-Host "  Langfuse:  http://localhost:3000"
Write-Host "`nTo stop: docker-compose down"
