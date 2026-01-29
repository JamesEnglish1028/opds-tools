#!/bin/bash
echo "🛑 Stopping all processes..."

./start-readium.sh stop
echo ""
./start-thorium.sh stop
