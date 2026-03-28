@echo off
echo Starting Quiz App Server...
echo ===================================

if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
    python app.py
) else (
    echo Virtual environment not found. Checking system python...
    python app.py
)

pause
