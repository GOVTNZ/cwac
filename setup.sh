#!/bin/bash

# This script (attempts) to set up CWAC automatically.
# Ensure Python 3.12+ is 'python'.

echo "Creating virtual environment..."
python -m venv .venv
source .venv/bin/activate

echo "Installing Python dependencies..."
pip install -r requirements-dev.txt

echo "Install mypy stubs..."
mypy --install-types

echo "Update pre-commit hooks..."
pre-commit autoupdate

echo "Installing pre-commit hooks..."
pre-commit install

echo "Installing Node dependencies..."
npm install

echo "Setup completed!"
