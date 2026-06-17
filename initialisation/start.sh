#!/usr/bin/env bash

# Exit immediately if a command exits with a non-zero status
set -e

# Change directory to project root (parent of script directory)
cd "$(dirname "$0")/.."

echo "==================================================="
echo "🔍 Edmond: Seamless Local Setup & Launch"
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
pip install -r initialisation/requirements.txt
echo "✅ All dependencies verified/installed."

echo
echo "🚀 Launching Streamlit Search UI..."
export PYTHONPATH=.
streamlit run frontend/app.py
