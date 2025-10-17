#!/bin/bash
#
# Update-Script für AirPlay Multiroom Server (Container-intern)
# Führt ein Git-Pull aus und aktualisiert den Service
#
# Verwendung (im Container):
#   cd /opt/airplay-multiroom-server
#   ./scripts/update-local.sh
#

set -e

# Farben
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

print_info() { echo -e "${BLUE}ℹ${NC} $1"; }
print_success() { echo -e "${GREEN}✓${NC} $1"; }
print_warning() { echo -e "${YELLOW}⚠${NC} $1"; }
print_error() { echo -e "${RED}✗${NC} $1"; }

echo -e "${GREEN}"
echo "══════════════════════════════════════════════════════"
echo "  AirPlay Multiroom Server - Lokales Update"
echo "══════════════════════════════════════════════════════"
echo -e "${NC}"

# Prüfen ob wir im richtigen Verzeichnis sind
if [ ! -f "requirements.txt" ] || [ ! -d "src" ]; then
    print_error "Dieses Script muss im Projekt-Root-Verzeichnis ausgeführt werden!"
    echo "Ausführen mit: cd /opt/airplay-multiroom-server && ./scripts/update-local.sh"
    exit 1
fi

# Prüfen ob git verfügbar ist
if ! command -v git &> /dev/null; then
    print_error "Git ist nicht installiert!"
    echo "Installation: apt install git"
    exit 1
fi

# Prüfen ob es ein Git-Repository ist
if [ ! -d ".git" ]; then
    print_error "Kein Git-Repository gefunden!"
    print_info "Dieses Script funktioniert nur wenn das Projekt via Git geklont wurde."
    exit 1
fi

# Aktuellen Branch anzeigen
CURRENT_BRANCH=$(git branch --show-current)
print_info "Aktueller Branch: $CURRENT_BRANCH"

# Status prüfen
print_info "Prüfe Repository-Status..."
if ! git diff-index --quiet HEAD --; then
    print_warning "Es gibt lokale Änderungen!"
    git status --short
    echo ""
    read -p "Möchten Sie fortfahren? Lokale Änderungen werden gesichert. (j/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Jj]$ ]]; then
        print_info "Update abgebrochen"
        exit 0
    fi
    
    # Lokale Änderungen stashen
    print_info "Sichere lokale Änderungen..."
    git stash
    print_success "Änderungen gesichert (mit 'git stash pop' wiederherstellen)"
fi

# Service stoppen
print_info "Stoppe Service..."
sudo systemctl stop airplay-multiroom-server
print_success "Service gestoppt"

# Python-Cache löschen
print_info "Lösche Python-Cache..."
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find . -type f -name "*.pyc" -delete 2>/dev/null || true
print_success "Cache gelöscht"

# Git Pull
print_info "Lade Updates herunter..."
git pull origin $CURRENT_BRANCH
print_success "Updates heruntergeladen"

# Dependencies aktualisieren
print_info "Aktualisiere Python-Dependencies..."
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
print_success "Dependencies aktualisiert"

# GStreamer-Bindings prüfen
print_info "Prüfe GStreamer-Bindings..."
if [ ! -e venv/lib/python3.*/site-packages/gi ]; then
    ln -s /usr/lib/python3/dist-packages/gi venv/lib/python3.*/site-packages/ 2>/dev/null || true
fi
print_success "GStreamer-Bindings OK"

# Berechtigungen setzen
print_info "Setze Berechtigungen..."
sudo chown -R airplay:airplay /opt/airplay-multiroom-server
print_success "Berechtigungen gesetzt"

# Systemd neu laden
print_info "Lade Systemd-Konfiguration neu..."
sudo systemctl daemon-reload
print_success "Systemd neu geladen"

# Service starten
print_info "Starte Service..."
sudo systemctl start airplay-multiroom-server
sleep 2

# Status prüfen
if systemctl is-active --quiet airplay-multiroom-server; then
    print_success "Service erfolgreich gestartet"
else
    print_error "Service konnte nicht gestartet werden!"
    print_info "Zeige Logs:"
    sudo journalctl -u airplay-multiroom-server -n 30 --no-pager
    exit 1
fi

echo ""
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
print_success "Update erfolgreich abgeschlossen! 🎉"
echo -e "${GREEN}══════════════════════════════════════════════════════${NC}"
echo ""

print_info "Service-Status:"
sudo systemctl status airplay-multiroom-server --no-pager -l

echo ""
echo "Weitere Befehle:"
echo "  • Logs: journalctl -u airplay-multiroom-server -f"
echo "  • Discovery-Test: ./venv/bin/python scripts/test-discovery.py"
echo "  • Geräte anzeigen: curl -s http://localhost:5000/api/devices | jq"
echo ""
