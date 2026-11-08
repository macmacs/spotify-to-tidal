# Environment Setup

This document explains how to set up the development environment for the spotify_to_tidal project.

## Prerequisites

- Python 3.10 or higher
- Git (for cloning the repository)

## Setup Scripts

Two setup scripts are provided:

### 1. Shell Script (Linux/macOS) - `setup_env.sh`

```bash
./setup_env.sh
```

### 2. Python Script (Cross-platform, including Windows) - `setup_env.py`

```bash
python3 setup_env.py
```

## What the Scripts Do

Both scripts perform the same operations:

1. **Check Python Version**: Verifies that Python 3.10+ is installed
2. **Create Virtual Environment**: Creates a new virtual environment in the `venv/` directory
3. **Activate Environment**: Activates the virtual environment
4. **Upgrade pip**: Updates pip to the latest version
5. **Install Dependencies**: Installs the project and all its dependencies in development mode

## Dependencies Installed

The following packages will be installed (as defined in `pyproject.toml`):

- `spotipy~=2.24` - Spotify Web API wrapper
- `tidalapi~=0.8.10` - TIDAL API wrapper
- `pyyaml~=6.0` - YAML parser
- `tqdm~=4.64` - Progress bars
- `sqlalchemy~=2.0` - Database toolkit
- `pytest~=8.0` - Testing framework
- `pytest-mock~=3.8` - Mock plugin for pytest

## After Setup

Once the setup is complete:

### Activate the Virtual Environment

**Linux/macOS:**
```bash
source venv/bin/activate
```

**Windows:**
```cmd
venv\Scripts\activate.bat
```

### Deactivate the Virtual Environment

```bash
deactivate
```

### Run the Application

```bash
spotify_to_tidal
```

## Manual Setup (Alternative)

If you prefer to set up manually:

```bash
# Create virtual environment
python3 -m venv venv

# Activate it (Linux/macOS)
source venv/bin/activate

# Activate it (Windows)
venv\Scripts\activate.bat

# Upgrade pip
pip install --upgrade pip

# Install the project
pip install -e .
```

## Troubleshooting

### Python Version Issues

If you get a Python version error, ensure you have Python 3.10 or higher installed:

```bash
python3 --version
```

### Permission Issues (Linux/macOS)

If you get permission errors with the shell script:

```bash
chmod +x setup_env.sh
./setup_env.sh
```

### Virtual Environment Already Exists

The scripts will automatically remove and recreate the virtual environment if it already exists.
