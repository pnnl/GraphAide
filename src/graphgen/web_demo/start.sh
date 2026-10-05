#!/bin/bash

# GraphAide Web Demo - Start Script

set -e

echo "🚀 Starting GraphAide Web Demo..."
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 16+ first."
    exit 1
fi

# Check if npm is installed
if ! command -v npm &> /dev/null; then
    echo "❌ npm is not installed. Please install npm first."
    exit 1
fi

# Install frontend dependencies if node_modules doesn't exist
FRONTEND_DIR="$(dirname "$0")/frontend"
if [ ! -d "$FRONTEND_DIR/node_modules" ]; then
    echo "📦 Installing frontend dependencies..."
    cd "$FRONTEND_DIR"
    npm install
    cd - > /dev/null
fi

# Build frontend
echo "🔨 Building frontend..."
cd "$FRONTEND_DIR"
npm run build
cd - > /dev/null

# Start frontend preview server
echo "🌐 Starting web server..."
cd "$FRONTEND_DIR"
npm run preview
