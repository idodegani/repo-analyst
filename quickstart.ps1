# Quick Start Script for Windows - One command to get everything running

Write-Host "🚀 Repo Analyst Quick Start" -ForegroundColor Cyan
Write-Host "==========================" -ForegroundColor Cyan

# Check for .env file
if (!(Test-Path .env)) {
    if (Test-Path .env.example) {
        Write-Host "📝 Creating .env from .env.example..." -ForegroundColor Yellow
        Copy-Item .env.example .env
        Write-Host "⚠️  Please edit .env and add your OpenAI API key" -ForegroundColor Red
        Write-Host "   Then run this script again." -ForegroundColor Red
        exit 1
    } else {
        Write-Host "❌ No .env or .env.example found!" -ForegroundColor Red
        exit 1
    }
}

# Check if API key is set
$envContent = Get-Content .env -Raw
if ($envContent -match "sk-your-openai-api-key-here") {
    Write-Host "⚠️  Please edit .env and add your actual OpenAI API key" -ForegroundColor Red
    Write-Host "   Replace 'sk-your-openai-api-key-here' with your key" -ForegroundColor Red
    exit 1
}

Write-Host "✅ Configuration found" -ForegroundColor Green

# Build and start
Write-Host "🔨 Building Docker image..." -ForegroundColor Yellow
docker-compose build
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Docker build failed!" -ForegroundColor Red
    exit 1
}

Write-Host "🚀 Starting services..." -ForegroundColor Yellow
docker-compose up -d
if ($LASTEXITCODE -ne 0) {
    Write-Host "❌ Failed to start services!" -ForegroundColor Red
    exit 1
}

# Wait for index
Write-Host "⏳ Waiting for index to build (first run only)..." -ForegroundColor Yellow
Start-Sleep -Seconds 5

# Test with a sample query
Write-Host "🧪 Testing with sample query..." -ForegroundColor Yellow
docker-compose run --rm app python app.py query "How does httpx handle timeouts?"

Write-Host ""
Write-Host "✨ Setup complete! Try these commands:" -ForegroundColor Green
Write-Host '   docker-compose run app python app.py query "your question"' -ForegroundColor White
Write-Host "   docker-compose run app python app.py interactive" -ForegroundColor White
Write-Host "   docker-compose run app python app.py info" -ForegroundColor White
