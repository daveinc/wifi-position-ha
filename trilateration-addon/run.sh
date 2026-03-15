#!/usr/bin/with-contenv bashio
set -e

bashio::log.info "Starting WiFi Position Tracker..."
exec python3 /app/server.py
