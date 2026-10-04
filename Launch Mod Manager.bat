@echo off
title Warlock Mod Manager
cd /d "%~dp0"
python --version >nul 2>&1
if errorlevel 1 (
  echo Python is required. Install Python 3 and tick "Add python.exe to PATH".
  pause
  exit /b 1
)
python app.py
if errorlevel 1 pause
