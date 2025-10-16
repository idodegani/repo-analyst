# Test Docker Build Script for Windows PowerShell
Write-Host "Testing Docker Build for Repo Analyst" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan

# Check if Docker is running
Write-Host "`nChecking Docker status..." -ForegroundColor Yellow
docker version > $null 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker is not running!" -ForegroundColor Red
    Write-Host "Please start Docker Desktop and try again." -ForegroundColor Yellow
    exit 1
}
Write-Host "Docker is running." -ForegroundColor Green

# Build the Docker image
Write-Host "`nBuilding Docker image..." -ForegroundColor Yellow
docker build -t repo-analyst:latest .
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Docker build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "Docker image built successfully." -ForegroundColor Green

# Test docker-compose
Write-Host "`nTesting docker-compose build..." -ForegroundColor Yellow
docker-compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: docker-compose build failed!" -ForegroundColor Red
    exit 1
}
Write-Host "docker-compose build successful." -ForegroundColor Green

# Show image info
Write-Host "`nDocker image info:" -ForegroundColor Cyan
docker images repo-analyst:latest

Write-Host "`nDocker build test completed successfully!" -ForegroundColor Green
Write-Host "`nTo run the application:" -ForegroundColor Yellow
Write-Host "  docker-compose up -d" -ForegroundColor White
Write-Host '  docker-compose run app python app.py query "your question"' -ForegroundColor White
