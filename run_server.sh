#!/bin/bash
echo "Starting Quiz App Server..."
echo "==================================="

if [ -f "venv/Scripts/activate" ]; then
    source venv/Scripts/activate
    python app.py
elif [ -f "venv/bin/activate" ]; then
    source venv/bin/activate
    python3 app.py
elif [ -f "env/bin/activate" ]; then
    source env/bin/activate
    python3 app.py
else
    echo "Virtual environment not found. Checking system python..."
    python3 app.py
fi
