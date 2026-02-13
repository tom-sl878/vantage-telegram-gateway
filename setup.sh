#!/bin/bash
# Setup script for Vantage Telegram Gateway

set -e

echo "=== Vantage Telegram Gateway Setup ==="
echo ""

# Check Python version
echo "Checking Python version..."
python3 --version

# Create virtual environment
echo ""
echo "Creating virtual environment..."
python3 -m venv venv

# Activate virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# Install dependencies
echo ""
echo "Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

# Create .env if it doesn't exist
if [ ! -f .env ]; then
    echo ""
    echo "Creating .env file from template..."
    cp .env.example .env
    echo "⚠️  IMPORTANT: Edit .env and add your TELEGRAM_BOT_TOKEN"
else
    echo ""
    echo "✓ .env file already exists"
fi

# Create media inbox directory
echo ""
echo "Creating media inbox directory..."
mkdir -p ~/.openclaw/media/inbound

echo ""
echo "=== Setup Complete ==="
echo ""
echo "Next steps:"
echo "1. Edit .env and add your TELEGRAM_BOT_TOKEN"
echo "2. Start the backend API (in another terminal):"
echo "   cd /Users/tom/Projects/OSAP/Vantage/backend"
echo "   source .venv/bin/activate"
echo "   .venv/bin/uvicorn app.main:app --reload"
echo ""
echo "3. Start the gateway:"
echo "   source venv/bin/activate"
echo "   python3 gateway.py"
echo ""
