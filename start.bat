@echo off
setlocal enabledelayedexpansion

echo ===================================================
echo 🔍 Project Edmond: Seamless Local Setup & Launch
echo ===================================================
echo.

rem Check if Python is installed
python --version >nul 2>&1
if errorlevel 1 (
    echo ❌ ERROR: Python is not installed or not in your PATH.
    echo Please install Python 3.9 or higher and try again.
    pause
    exit /b 1
)

rem Check if virtual environment exists, if not create it
if not exist .venv (
    echo 📦 Virtual environment not found. Creating '.venv' ...
    python -m venv .venv
    if errorlevel 1 (
        echo ❌ ERROR: Failed to create virtual environment.
        pause
        exit /b 1
    )
    echo ✅ Virtual environment created.
) else (
    echo 📂 Existing '.venv' virtual environment found.
)

echo.
echo 🔌 Activating virtual environment...
call .venv\Scripts\activate

echo.
echo 📥 Checking and installing Python dependencies...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo ❌ ERROR: Failed to install python packages from requirements.txt.
    pause
    exit /b 1
)
echo ✅ All dependencies verified/installed.

echo.
echo 🚀 Launching Streamlit Search UI...
streamlit run app.py

pause
