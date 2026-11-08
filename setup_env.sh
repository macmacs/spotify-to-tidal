#!/bin/bash

# Setup script for spotify_to_tidal project
# Creates virtual environment and installs required packages

set -e  # Exit on any error

echo "🚀 Setting up spotify_to_tidal development environment..."

# Check if Python 3.10+ is available
if ! command -v python3 &> /dev/null; then
    echo "❌ Error: Python 3 is not installed or not in PATH"
    exit 1
fi

# Check Python version
PYTHON_VERSION=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
REQUIRED_VERSION="3.10"

if [ "$(printf '%s\n' "$REQUIRED_VERSION" "$PYTHON_VERSION" | sort -V | head -n1)" != "$REQUIRED_VERSION" ]; then
    echo "❌ Error: Python $REQUIRED_VERSION or higher is required. Found Python $PYTHON_VERSION"
    exit 1
fi

echo "✅ Python $PYTHON_VERSION found"

# Create virtual environment
VENV_DIR="venv"
if [ -d "$VENV_DIR" ]; then
    echo "📁 Virtual environment already exists. Removing old one..."
    rm -rf "$VENV_DIR"
fi

echo "🔧 Creating virtual environment..."
python3 -m venv "$VENV_DIR"

# Activate virtual environment
echo "🔌 Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "⬆️  Upgrading pip..."
pip install --upgrade pip

# Install the project in development mode (this will install all dependencies)
echo "📦 Installing project dependencies..."
pip install -e .

echo ""
echo "✅ Setup complete!"
echo ""
echo "To activate the virtual environment in the future, run:"
echo "  source venv/bin/activate"
echo ""
echo "To deactivate the virtual environment, run:"
echo "  deactivate"
echo ""
echo "To run the application:"
echo "  spotify_to_tidal"
