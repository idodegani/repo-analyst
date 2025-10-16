#!/bin/bash
# Test Docker Build Script for Linux/Mac

echo -e "\033[36mTesting Docker Build for Repo Analyst\033[0m"
echo -e "\033[36m=====================================\033[0m"

# Check if Docker is running
echo -e "\n\033[33mChecking Docker status...\033[0m"
if ! docker version > /dev/null 2>&1; then
    echo -e "\033[31mERROR: Docker is not running!\033[0m"
    echo -e "\033[33mPlease start Docker and try again.\033[0m"
    exit 1
fi
echo -e "\033[32mDocker is running.\033[0m"

# Build the Docker image
echo -e "\n\033[33mBuilding Docker image...\033[0m"
if ! docker build -t repo-analyst:latest .; then
    echo -e "\033[31mERROR: Docker build failed!\033[0m"
    exit 1
fi
echo -e "\033[32mDocker image built successfully.\033[0m"

# Test docker-compose
echo -e "\n\033[33mTesting docker-compose build...\033[0m"
if ! docker-compose build; then
    echo -e "\033[31mERROR: docker-compose build failed!\033[0m"
    exit 1
fi
echo -e "\033[32mdocker-compose build successful.\033[0m"

# Show image info
echo -e "\n\033[36mDocker image info:\033[0m"
docker images repo-analyst:latest

echo -e "\n\033[32mDocker build test completed successfully!\033[0m"
echo -e "\n\033[33mTo run the application:\033[0m"
echo -e "  \033[37mdocker-compose up -d\033[0m"
echo -e "  \033[37mdocker-compose run app python app.py query \"your question\"\033[0m"
