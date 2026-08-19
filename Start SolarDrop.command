#!/bin/zsh
cd "$(dirname "$0")"
echo "Starting SolarDrop..."
echo "Starting SolarDrop with automatic LAN IP detection..."
exec /usr/bin/env python3 server.py
