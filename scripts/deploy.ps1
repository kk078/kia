"""Production deployment script for Secondary Brain."""

$ErrorActionPreference = "Stop"

Write-Host "Deploying Secondary Brain to production..." -ForegroundColor Cyan

# Check prerequisites
Write-Host "`nChecking prerequisites..." -ForegroundColor Yellow

$dockerVersion = docker --version 2>&1
if (-not $dockerVersion) {
    Write-Host "ERROR: Docker not found" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Docker: $dockerVersion" -ForegroundColor Green

# Check for .env.production
if (-not (Test-Path ".env.production")) {
    Write-Host "ERROR: .env.production not found" -ForegroundColor Red
    exit 1
}

# Copy .env.production to .env if .env doesn't exist
if (-not (Test-Path ".env")) {
    Write-Host "`nCreating .env from .env.production..." -ForegroundColor Yellow
    Copy-Item .env.production .env
    Write-Host "✓ Created .env - Please edit with your production API keys" -ForegroundColor Green
    Write-Host "  Edit .env and add your API keys, then run this script again" -ForegroundColor Yellow
    exit 0
}

# Validate required environment variables
Write-Host "`nValidating environment variables..." -ForegroundColor Yellow
$envContent = Get-Content .env -Raw
$requiredVars = @("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "LANGFUSE_PUBLIC_KEY", "LANGFUSE_SECRET_KEY")
$missingVars = @()

foreach ($var in $requiredVars) {
    if ($envContent -notmatch "$var=.+" -or $envContent -match "$var=\s*$") {
        $missingVars += $var
    }
}

if ($missingVars.Count -gt 0) {
    Write-Host "WARNING: Missing or empty environment variables:" -ForegroundColor Yellow
    $missingVars | ForEach-Object { Write-Host "  - $_" -ForegroundColor Yellow }
    $continue = Read-Host "Continue anyway? (y/N)"
    if ($continue -ne "y") {
        exit 1
    }
}

# Build and start production stack
Write-Host "`nBuilding and starting production stack..." -ForegroundColor Yellow
docker-compose -f docker-compose.prod.yml build
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Build failed" -ForegroundColor Red
    exit 1
}

Write-Host "`nStarting services..." -ForegroundColor Yellow
docker-compose -f docker-compose.prod.yml up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to start services" -ForegroundColor Red
    exit 1
}

# Wait for services to be healthy
Write-Host "`nWaiting for services to be healthy..." -ForegroundColor Yellow
Start-Sleep -Seconds 10

# Check service status
Write-Host "`nService status:" -ForegroundColor Yellow
docker-compose -f docker-compose.prod.yml ps

Write-Host "`n✓ Production deployment complete!" -ForegroundColor Cyan
Write-Host "`nServices:" -ForegroundColor Yellow
Write-Host "  .NET Gateway:  http://localhost:5000"
Write-Host "  Python API:    http://localhost:8000"
Write-Host "  Langfuse:      http://localhost:3000"
Write-Host "`nTo view logs: docker-compose -f docker-compose.prod.yml logs -f"
Write-Host "To stop: docker-compose -f docker-compose.prod.yml down"
