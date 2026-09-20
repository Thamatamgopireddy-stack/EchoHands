@echo off
setlocal
set "ROOT=%~dp0"
if not exist "%ROOT%.venv\Scripts\python.exe" (
    echo Project virtual environment not found: %ROOT%.venv
    echo Create it and install requirements.txt first.
    exit /b 1
)
"%ROOT%.venv\Scripts\python.exe" "%ROOT%app.py"