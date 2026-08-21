#!/bin/bash
set -e

# Wait for WireGuard tools to be available
until command -v wg &> /dev/null; do
    echo "Waiting for WireGuard tools..."
    sleep 1
done

# Single-process waitress (or Flask debug server when FLASK_DEBUG=true)
echo "Starting application..."
exec python3 -m app.main

