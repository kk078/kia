"""Test script to run lint, typecheck, and tests."""

$ErrorActionPreference = "Stop"

Write-Host "Running Secondary Brain test suite..." -ForegroundColor Cyan

Set-Location agents

# Lint
Write-Host "`n[1/4] Running ruff linter..." -ForegroundColor Yellow
uv run ruff check .
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Linting failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Linting passed" -ForegroundColor Green

# Format check
Write-Host "`n[2/4] Checking code formatting..." -ForegroundColor Yellow
uv run ruff format --check .
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Format check failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Format check passed" -ForegroundColor Green

# Typecheck
Write-Host "`n[3/4] Running mypy type checker..." -ForegroundColor Yellow
uv run mypy .
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Type checking failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Type checking passed" -ForegroundColor Green

# Unit tests
Write-Host "`n[4/4] Running unit tests..." -ForegroundColor Yellow
uv run pytest tests/unit -v
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Unit tests failed" -ForegroundColor Red
    exit 1
}
Write-Host "✓ Unit tests passed" -ForegroundColor Green

Set-Location ..

Write-Host "`n✓ All tests passed!" -ForegroundColor Cyan
