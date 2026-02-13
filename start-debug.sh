#!/bin/bash
# Start gateway in foreground with debug logging

cd /Users/tom/Projects/OSAP/vantage-telegram-gateway

set -a
source .env
set +a

# Enable debug mode
export LOG_LEVEL=DEBUG

source venv/bin/activate
python3 gateway.py
