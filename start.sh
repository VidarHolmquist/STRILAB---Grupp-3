#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

echo "==================================================="
echo "🔍 Project Edmond: Seamless Local Setup & Launch"
echo "==================================================="
echo

# Check if Python is installed
if ! command -v python3 &> /dev/null; then
    echo "❌ ERROR: Python3 is not installed or not in your PATH."
    echo "Please install Python 3.9 or higher and try again."
    exit 1
fi

# Check if virtual environment exists, if not create it
if [ ! -d ".venv" ]; then
    echo "📦 Virtual environment not found. Creating '.venv' ..."
    python3 -m venv .venv
    echo "✅ Virtual environment created."
else
    echo "📂 Existing '.venv' virtual environment found."
fi

echo
echo "🔌 Activating virtual environment..."
source .venv/bin/activate

echo
echo "📥 Checking and installing Python dependencies..."
python3 -m pip install --upgrade pip
pip install -r requirements.txt
echo "✅ All dependencies verified/installed."

echo
echo "🚀 Launching Flask Search UI..."
python3 app.py
