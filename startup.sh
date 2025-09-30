#!/bin/bash
# Azure App Service startup script

echo "Starting HR Policy Chatbot..."

# Upgrade pip
python -m pip install --upgrade pip

# Install dependencies
echo "Installing dependencies..."
pip install -r requirements.txt

# Start application with Gunicorn
echo "Starting Gunicorn server..."
gunicorn -w 4 -k uvicorn.workers.UvicornWorker app.main:app \
  --bind 0.0.0.0:8000 \
  --timeout 120 \
  --access-logfile - \
  --error-logfile - \
  --log-level info