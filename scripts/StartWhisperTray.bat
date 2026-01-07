@echo off
REM Whisper-Tray Launcher
REM This script launches the Whisper dictation tray app

set "SCRIPT_DIR=%~dp0"
set "ROOT_DIR=%SCRIPT_DIR%.."

REM Use venv from root directory, run script from scripts directory
"%ROOT_DIR%\.venv\Scripts\python.exe" "%SCRIPT_DIR%windows_mic_button.py" --model-size small --send-enter --no-start-popup
