#!/bin/bash

# Configuration
PORT=15080
READIUM_BINARY="./ReadiumCLI/readium"
LOG_DIR="./logs"
LOG_FILE="$LOG_DIR/readium.log"
PID_FILE="$LOG_DIR/readium.pid"
ENV_FILE=".env"

# Load environment variables (like R2 keys and endpoint)
set -a
[ -f "$ENV_FILE" ] && source "$ENV_FILE"
set +a

# Ensure log directory exists
mkdir -p "$LOG_DIR"

start() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "⚠️ Readium CLI is already running (PID $PID)"
      return
    fi
  fi

  if lsof -i :$PORT &>/dev/null; then
    echo "⚠️ Port $PORT is already in use. Cannot start Readium CLI."
    return
  fi

  echo "🚀 Starting Readium CLI with R2 support on port $PORT..."
  nohup "$READIUM_BINARY" serve "./" \
    --address localhost \
    --port $PORT \
    --debug \
    --s3-endpoint "$R2_ENDPOINT" \
    --s3-region auto \
    --s3-access-key "$R2_ACCESS_KEY" \
    --s3-secret-key "$R2_SECRET_KEY" \
    > "$LOG_FILE" 2>&1 &

  echo $! > "$PID_FILE"
  echo "📄 Logging to $LOG_FILE"
  echo "🌐 Endpoint: http://localhost:$PORT"
}

stop() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "🛑 Stopping Readium CLI (PID $PID)..."
      kill "$PID"
    else
      echo "⚠️ PID file exists but no process found for PID $PID"
    fi
    rm -f "$PID_FILE"
  else
    echo "ℹ️ No PID file found. Readium may not be running."
  fi
}

status() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "✅ Readium CLI is running (PID $PID)"
    else
      echo "⚠️ PID file exists but process not running"
    fi
  else
    echo "❌ Readium CLI is not running"
  fi
}

restart() {
  stop
  sleep 1
  start
}

case "$1" in
  start|"")
    start
    ;;
  stop)
    stop
    ;;
  status)
    status
    ;;
  restart)
    restart
    ;;
  *)
    echo "Usage: $0 [start|stop|status|restart]"
    exit 1
    ;;
esac
