@echo off
cd /d "%~dp0"
set PYTHONUTF8=1
start "" "%~dp0..\.venv\Scripts\pythonw.exe" -X utf8 "%~dp0main.py"
