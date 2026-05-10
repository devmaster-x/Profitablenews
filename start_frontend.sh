#!/bin/bash

# News Scraper Frontend Startup Script

echo "🎨 Starting News Scraper Frontend..."

# Check if we're in the right directory
if [ ! -f "package.json" ]; then
    echo "❌ Error: Please run this script from the news-scraper-frontend directory"
    exit 1
fi

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Error: Node.js is not installed. Please install Node.js first."
    echo "Visit: https://nodejs.org/"
    exit 1
fi

# Check Node.js version
node_version=$(node --version | cut -d'v' -f2 | cut -d'.' -f1)
if [ "$node_version" -lt 18 ]; then
    echo "❌ Error: Node.js 18+ is required. Current version: $(node --version)"
    exit 1
fi

echo "✅ Node.js version: $(node --version)"

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ Error: npm is not installed."
    exit 1
fi

# Install dependencies
echo "📦 Installing dependencies..."
npm install

# Check if .env file exists
if [ ! -f ".env" ]; then
    echo "⚠️  Warning: No .env file found. Using default configuration."
    echo "   Create a .env file for custom configuration (see ENVIRONMENT_SETUP.md)"
fi

# Start the development server
echo "🌐 Starting Vite development server..."
echo "   Frontend will be available at: http://localhost:5173"
echo "   Make sure the backend is running at: http://localhost:8000"
echo ""
echo "Press Ctrl+C to stop the server"
echo ""

npm run dev 