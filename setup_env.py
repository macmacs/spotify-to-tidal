#!/usr/bin/env python3
"""
Setup script for spotify_to_tidal project
Creates virtual environment and installs required packages
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path


def run_command(cmd, shell=False):
    """Run a command and return the result"""
    try:
        result = subprocess.run(cmd, shell=shell, check=True, capture_output=True, text=True)
        return result.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"❌ Error running command: {' '.join(cmd) if isinstance(cmd, list) else cmd}")
        print(f"Error: {e.stderr}")
        sys.exit(1)


def check_python_version():
    """Check if Python version meets requirements"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 10):
        print(f"❌ Error: Python 3.10 or higher is required. Found Python {version.major}.{version.minor}")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor}.{version.micro} found")


def main():
    print("🚀 Setting up spotify_to_tidal development environment...")
    
    # Check Python version
    check_python_version()
    
    # Define virtual environment directory
    venv_dir = Path("venv")
    
    # Remove existing virtual environment if it exists
    if venv_dir.exists():
        print("📁 Virtual environment already exists. Removing old one...")
        shutil.rmtree(venv_dir)
    
    # Create virtual environment
    print("🔧 Creating virtual environment...")
    run_command([sys.executable, "-m", "venv", str(venv_dir)])
    
    # Determine the correct paths for the virtual environment
    if os.name == 'nt':  # Windows
        venv_python = venv_dir / "Scripts" / "python.exe"
        venv_pip = venv_dir / "Scripts" / "pip.exe"
        activate_script = venv_dir / "Scripts" / "activate.bat"
    else:  # Unix-like (Linux, macOS)
        venv_python = venv_dir / "bin" / "python"
        venv_pip = venv_dir / "bin" / "pip"
        activate_script = venv_dir / "bin" / "activate"
    
    # Upgrade pip
    print("⬆️  Upgrading pip...")
    run_command([str(venv_python), "-m", "pip", "install", "--upgrade", "pip"])
    
    # Install the project in development mode
    print("📦 Installing project dependencies...")
    run_command([str(venv_pip), "install", "-e", "."])
    
    print()
    print("✅ Setup complete!")
    print()
    print("To activate the virtual environment:")
    if os.name == 'nt':  # Windows
        print(f"  {activate_script}")
    else:  # Unix-like
        print(f"  source {activate_script}")
    print()
    print("To deactivate the virtual environment:")
    print("  deactivate")
    print()
    print("To run the application:")
    print("  spotify_to_tidal")


if __name__ == "__main__":
    main()
