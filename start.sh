#!/bin/bash
# Start Vantage Telegram Gateway with environment variables

set -a  # automatically export all variables
source .env
set +a

source venv/bin/activate
python3 gateway.py
