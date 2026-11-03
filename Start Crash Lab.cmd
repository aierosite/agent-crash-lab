@echo off
cd /d "%~dp0"
python -I -S "%~dp0launch.py"
if errorlevel 1 pause
