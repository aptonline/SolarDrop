#!/bin/zsh
cd "$(dirname "$0")"
echo "Starting SolarDrop..."
echo "Open http://192.168.1.172:8080 in your browser."
exec /usr/bin/env python3 server.py
