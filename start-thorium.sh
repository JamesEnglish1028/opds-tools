#!/bin/bash

# Configuration
PORT=3000
THORIUM_DIR="../web_reader/thorium-web"
NODE_CMD="pnpm"
LOG_DIR="./logs"
LOG_FILE="$LOG_DIR/thorium.log"
PID_FILE="$LOG_DIR/thorium.pid"

# Resolve absolute path
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_PATH="$SCRIPT_DIR/$THORIUM_DIR"
MODE="${2:-dev}"  # default: dev mode (used only with 'start' or 'restart')

mkdir -p "$LOG_DIR"

start() {
  # Check for running process
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "⚠️ Thorium Web is already running (PID $PID)"
      return
    fi
  fi

  if lsof -i :$PORT &>/dev/null; then
    echo "⚠️  Port $PORT is already in use. Cannot start Thorium Web."
    return
  fi

  # Change into Thorium directory
  cd "$PROJECT_PATH" || {
    echo "❌ Could not find Thorium project at $PROJECT_PATH"
    exit 1
  }

  echo "🚀 Starting Thorium Web ($MODE mode) on port $PORT..."
  nohup $NODE_CMD run "$MODE" > "$SCRIPT_DIR/$LOG_FILE" 2>&1 &
  echo $! > "$SCRIPT_DIR/$PID_FILE"
  echo "📄 Logging to $LOG_FILE"
  cd - > /dev/null
}

stop() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "🛑 Stopping Thorium Web (PID $PID)..."
      kill "$PID"
    else
      echo "⚠️ No active Thorium process found for PID $PID"
    fi
    rm -f "$PID_FILE"
  else
    echo "ℹ️ No PID file found. Thorium may not be running."
  fi
}

status() {
  if [ -f "$PID_FILE" ]; then
    PID=$(cat "$PID_FILE")
    if kill -0 "$PID" 2>/dev/null; then
      echo "✅ Thorium Web is running (PID $PID)"
    else
      echo "⚠️ PID file exists but process is not running"
    fi
  else
    echo "❌ Thorium Web is not running"
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
  build)
    cd "$PROJECT_PATH" || exit 1
    echo "🛠️ Building Thorium Web..."
    $NODE_CMD run build
    cd - > /dev/null
    ;;
  *)
    echo "Usage: $0 [start|stop|status|restart|build] [mode]"
    echo "Examples:"
    echo "  ./start-thorium.sh start dev"
    echo "  ./start-thorium.sh restart start"
    echo "  ./start-thorium.sh build"
    exit 1
    ;;
esac
