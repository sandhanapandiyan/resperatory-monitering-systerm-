#!/bin/bash

# --- Neonatal Monitoring System Runner ---

# 1. Activate virtual environment
if [ -d "venv" ]; then
    source venv/bin/activate
else
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
fi

# 2. Cleanup existing processes (Port 5000 for Flask, 8501 for Streamlit)
echo "Cleaning up existing processes..."
pkill -f "python app.py"
pkill -f "streamlit run streamlit_app.py"
sleep 2

# 3. Start Flask Backend in background
echo "Starting Flask Backend Processing Server..."
python app.py &
backend_pid=$!

# 3. Start Streamlit UI
echo "Starting Streamlit UI Dashboard..."
# Streamlit usually blocks the terminal, so we run it as the foreground process
streamlit run streamlit_app.py

# Cleanup on exit
trap "kill $backend_pid; exit" INT TERM
