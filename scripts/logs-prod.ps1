"""View production logs."""

$ErrorActionPreference = "Stop"

$service = $args[0]

if ($service) {
    Write-Host "Viewing logs for $service..." -ForegroundColor Cyan
    docker-compose -f docker-compose.prod.yml logs -f $service
} else {
    Write-Host "Viewing all production logs..." -ForegroundColor Cyan
    docker-compose -f docker-compose.prod.yml logs -f
}
