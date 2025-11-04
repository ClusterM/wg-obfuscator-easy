#!/bin/bash
set -e

# Wait for WireGuard tools to be available
until command -v wg &> /dev/null; do
    echo "Waiting for WireGuard tools..."
    sleep 1
done

# Start Flask application directly (no Gunicorn needed for single worker)
echo "Starting Flask application..."
exec python3 -m app.main

