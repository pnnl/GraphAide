#!/bin/bash

# GraphAide Web Demo - Development Mode (Hot Reload)

set -e

echo "🚀 Starting GraphAide Web Demo (Development Mode)"
echo ""
echo "📝 Instructions:"
echo "  1. Terminal 1 (API Server) - Run: graphaide serve --port 8000"
echo "  2. This script - Starts the React dev server on http://localhost:5173"
echo ""

# Check if Node.js is installed
if ! command -v node &> /dev/null; then
    echo "❌ Node.js is not installed. Please install Node.js 16+ first."
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

# Start frontend dev server
echo "🌐 Starting dev server (hot reload enabled)..."
echo "    → Open browser at: http://localhost:5173"
echo ""

cd "$FRONTEND_DIR"
npm run dev
