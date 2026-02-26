#!/bin/bash
# Start Vantage Telegram Gateway
#
# Usage:
#   ./start.sh              # start gateway only (no mini app)
#   ./start.sh --tunnel     # start gateway + cloudflared tunnel for mini app

set -a
source .env
set +a

source venv/bin/activate

if [ "$1" = "--tunnel" ]; then
  if ! command -v cloudflared &> /dev/null; then
    echo "Error: cloudflared not found. Install with: brew install cloudflared"
    exit 1
  fi

  cleanup() {
    echo ""
    echo "Shutting down..."
    kill $TUNNEL_PID $BOT_PID 2>/dev/null
    wait $TUNNEL_PID $BOT_PID 2>/dev/null
    exit 0
  }
  trap cleanup INT TERM

  TUNNEL_LOG=$(mktemp)
  cloudflared tunnel --url http://localhost:8000 2>"$TUNNEL_LOG" &
  TUNNEL_PID=$!

  echo "Waiting for tunnel..."
  for i in {1..15}; do
    TUNNEL_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" | head -1)
    if [ -n "$TUNNEL_URL" ]; then break; fi
    sleep 1
  done
  rm -f "$TUNNEL_LOG"

  if [ -z "$TUNNEL_URL" ]; then
    echo "Error: Could not get tunnel URL."
    kill $TUNNEL_PID 2>/dev/null
    exit 1
  fi

  export WEBAPP_URL="${TUNNEL_URL}/webapp"
  echo ""
  echo "==================================="
  echo "  Tunnel:  $TUNNEL_URL"
  echo "  MiniApp: $WEBAPP_URL"
  echo "  Admin:   ${TUNNEL_URL}/admin"
  echo "==================================="
  echo ""

  python3 gateway.py &
  BOT_PID=$!
  echo "Gateway running with tunnel. Press Ctrl+C to stop."
  wait
else
  python3 gateway.py
fi
