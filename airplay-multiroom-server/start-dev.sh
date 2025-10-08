#!/bin/bash

# AirPlay Multiroom Server - Quick Start Script
# Verwendung: ./start-dev.sh

cd "$(dirname "$0")"

# Prüfen ob Virtual Environment existiert
if [[ ! -d "venv" ]]; then
    echo "Virtual Environment nicht gefunden. Führen Sie zuerst ./scripts/dev-setup.sh aus."
    exit 1
fi

# Virtual Environment aktivieren
source venv/bin/activate

# PYTHONPATH setzen
export PYTHONPATH="$(pwd)"

# Development-Konfiguration verwenden
if [[ ! -f "config/dev-config.yaml" ]]; then
    echo "Entwicklungs-Konfiguration nicht gefunden. Verwende Standard-Konfiguration."
    CONFIG_FILE="config/config.yaml"
else
    CONFIG_FILE="config/dev-config.yaml"
fi

echo "Starte AirPlay Multiroom Server (Development Mode)..."
echo "Konfiguration: $CONFIG_FILE"
echo "Web-Interface: http://localhost:5000"
echo ""
echo "Zum Stoppen: Ctrl+C"
echo ""

# Server starten
python -m src --config "$CONFIG_FILE" --debug