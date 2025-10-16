#!/bin/bash
# Quick Start Script - One command to get everything running

set -e  # Exit on error

echo "🚀 Repo Analyst Quick Start"
echo "=========================="

# Check for .env file
if [ ! -f .env ]; then
    if [ -f .env.example ]; then
        echo "📝 Creating .env from .env.example..."
        cp .env.example .env
        echo "⚠️  Please edit .env and add your OpenAI API key"
        echo "   Then run this script again."
        exit 1
    else
        echo "❌ No .env or .env.example found!"
        exit 1
    fi
fi

# Check if API key is set
if grep -q "sk-your-openai-api-key-here" .env; then
    echo "⚠️  Please edit .env and add your actual OpenAI API key"
    echo "   Replace 'sk-your-openai-api-key-here' with your key"
    exit 1
fi

echo "✅ Configuration found"

# Build and start
echo "🔨 Building Docker image..."
docker-compose build

echo "🚀 Starting services..."
docker-compose up -d

# Wait for index
echo "⏳ Waiting for index to build (first run only)..."
sleep 5

# Test with a sample query
echo "🧪 Testing with sample query..."
docker-compose run --rm app python app.py query "How does httpx handle timeouts?"

echo ""
echo "✨ Setup complete! Try these commands:"
echo "   docker-compose run app python app.py query \"your question\""
echo "   docker-compose run app python app.py interactive"
echo "   docker-compose run app python app.py info"
