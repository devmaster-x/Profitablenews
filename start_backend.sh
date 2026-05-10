#!/bin/bash

# News Scraper Backend Startup Script

echo "🚀 Starting News Scraper Backend..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: Please run this script from the news-scraper-backend directory"
    exit 1
fi

# Check if Poetry is installed
if ! command -v poetry &> /dev/null; then
    echo "❌ Error: Poetry is not installed. Please install Poetry first."
    echo "Visit: https://python-poetry.org/docs/#installation"
    exit 1
fi

# Check if Python 3.12+ is available
python_version=$(python3 --version 2>&1 | grep -oP '\d+\.\d+' | head -1)
if [ "$(echo "$python_version >= 3.12" | bc -l)" -eq 0 ]; then
    echo "❌ Error: Python 3.12+ is required. Current version: $python_version"
    exit 1
fi

echo "✅ Python version: $python_version"

# Install dependencies
echo "📦 Installing dependencies..."
poetry install

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: No .env file found. Using default configuration."
    echo "   Create a .env file for custom configuration (see ENVIRONMENT_SETUP.md)"
fi

# Start the application
echo "🌐 Starting FastAPI server..."
echo "   API will be available at: http://localhost:8000"
echo "   API docs will be available at: http://localhost:8000/docs"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

poetry run python -m app.main 