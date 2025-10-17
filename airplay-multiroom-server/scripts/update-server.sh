#!/bin/bash
#
# Update-Script für AirPlay Multiroom Server
# Aktualisiert den Server auf einem Proxmox LXC Container
#
# Verwendung:
#   Auf Proxmox Host ausführen:
#   ./update-server.sh [container-id] [pfad-zum-projekt]
#
# Beispiel:
#   ./update-server.sh 100 /tmp/airplay-multiroom-server
#

set -e  # Bei Fehler abbrechen

# Farben für Ausgabe
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Hilfsfunktionen
print_info() {
    echo -e "${BLUE}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

print_header() {
    echo ""
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo -e "${BLUE}  $1${NC}"
    echo -e "${BLUE}═══════════════════════════════════════════════════════════${NC}"
    echo ""
}

# Parameter
CONTAINER_ID=${1:-100}
SOURCE_DIR=${2:-$(pwd)}

# Banner
clear
echo -e "${GREEN}"
cat << "EOF"
    ___    _      ____  __               __  __          __      __       
   /   |  (_)____/ __ \/ /___ ___  __   / / / /___  ____/ /___ _/ /____   
  / /| | / / ___/ /_/ / / __ `/ / / /  / / / / __ \/ __  / __ `/ __/ _ \  
 / ___ |/ / /  / ____/ / /_/ / /_/ /  / /_/ / /_/ / /_/ / /_/ / /_/  __/  
/_/  |_/_/_/  /_/   /_/\__,_/\__, /   \____/ .___/\__,_/\__,_/\__/\___/   
                            /____/        /_/                              
EOF
echo -e "${NC}"
echo "    Multiroom Server - Update Script"
echo ""

# Prüfungen
print_header "1. Systemprüfungen"

# Prüfen ob auf Proxmox Host
if ! command -v pct &> /dev/null; then
    print_error "pct-Befehl nicht gefunden. Dieses Script muss auf einem Proxmox Host ausgeführt werden!"
    exit 1
fi
print_success "Proxmox Host erkannt"

# Prüfen ob Container existiert
if ! pct status $CONTAINER_ID &> /dev/null; then
    print_error "Container $CONTAINER_ID existiert nicht!"
    echo "Verfügbare Container:"
    pct list
    exit 1
fi
print_success "Container $CONTAINER_ID gefunden"

# Prüfen ob Container läuft
CONTAINER_STATUS=$(pct status $CONTAINER_ID | awk '{print $2}')
if [ "$CONTAINER_STATUS" != "running" ]; then
    print_warning "Container ist nicht gestartet. Starte Container..."
    pct start $CONTAINER_ID
    sleep 3
fi
print_success "Container läuft"

# Prüfen ob Quellverzeichnis existiert
if [ ! -d "$SOURCE_DIR" ]; then
    print_error "Quellverzeichnis nicht gefunden: $SOURCE_DIR"
    exit 1
fi
print_success "Quellverzeichnis gefunden: $SOURCE_DIR"

# Prüfen ob wichtige Dateien vorhanden sind
if [ ! -f "$SOURCE_DIR/requirements.txt" ] || [ ! -d "$SOURCE_DIR/src" ]; then
    print_error "Ungültiges Projektverzeichnis. requirements.txt oder src/ fehlt!"
    exit 1
fi
print_success "Projektstruktur validiert"

# Backup erstellen
print_header "2. Backup erstellen"

BACKUP_DIR="/var/lib/lxc/$CONTAINER_ID/rootfs/opt/airplay-multiroom-server.backup.$(date +%Y%m%d_%H%M%S)"
print_info "Erstelle Backup nach: $BACKUP_DIR"

if [ -d "/var/lib/lxc/$CONTAINER_ID/rootfs/opt/airplay-multiroom-server" ]; then
    cp -r /var/lib/lxc/$CONTAINER_ID/rootfs/opt/airplay-multiroom-server $BACKUP_DIR
    print_success "Backup erstellt"
else
    print_warning "Kein existierendes Verzeichnis zum Backup gefunden (Neuinstallation?)"
fi

# Service stoppen
print_header "3. Service stoppen"

print_info "Stoppe airplay-multiroom-server Service..."
pct exec $CONTAINER_ID -- systemctl stop airplay-multiroom-server 2>/dev/null || true
sleep 2
print_success "Service gestoppt"

# Dateien kopieren
print_header "4. Dateien aktualisieren"

DEST_DIR="/var/lib/lxc/$CONTAINER_ID/rootfs/opt/airplay-multiroom-server"

print_info "Kopiere Dateien nach: $DEST_DIR"

# Verzeichnis erstellen falls es nicht existiert
mkdir -p $DEST_DIR

# Python-Cache entfernen
print_info "Entferne Python-Cache..."
find $DEST_DIR -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find $DEST_DIR -type f -name "*.pyc" -delete 2>/dev/null || true

# Wichtige Verzeichnisse kopieren
print_info "Kopiere Source-Code..."
cp -r $SOURCE_DIR/src $DEST_DIR/
print_success "src/ kopiert"

cp -r $SOURCE_DIR/scripts $DEST_DIR/
print_success "scripts/ kopiert"

cp -r $SOURCE_DIR/web $DEST_DIR/ 2>/dev/null || true
print_success "web/ kopiert"

# Config-Beispiel kopieren (nur wenn noch keine Config existiert)
if [ ! -f "/var/lib/lxc/$CONTAINER_ID/rootfs/etc/airplay-multiroom/config.yaml" ]; then
    print_info "Erstelle initiale Konfiguration..."
    pct exec $CONTAINER_ID -- mkdir -p /etc/airplay-multiroom
    cp $SOURCE_DIR/config/config.yaml /var/lib/lxc/$CONTAINER_ID/rootfs/etc/airplay-multiroom/
    print_success "Config kopiert"
else
    print_info "Config existiert bereits - wird nicht überschrieben"
fi

# Systemd Service aktualisieren
if [ -f "$SOURCE_DIR/systemd/airplay-multiroom-server.service" ]; then
    cp $SOURCE_DIR/systemd/airplay-multiroom-server.service /var/lib/lxc/$CONTAINER_ID/rootfs/etc/systemd/system/
    print_success "Systemd Service aktualisiert"
fi

# requirements.txt kopieren
cp $SOURCE_DIR/requirements.txt $DEST_DIR/
print_success "requirements.txt kopiert"

# README und Docs kopieren (optional)
cp $SOURCE_DIR/README.md $DEST_DIR/ 2>/dev/null || true
cp -r $SOURCE_DIR/docs $DEST_DIR/ 2>/dev/null || true

# Berechtigungen setzen
print_info "Setze Berechtigungen..."
pct exec $CONTAINER_ID -- chown -R airplay:airplay /opt/airplay-multiroom-server
print_success "Berechtigungen gesetzt"

# Python Dependencies aktualisieren
print_header "5. Python Dependencies aktualisieren"

print_info "Aktualisiere Python-Pakete..."
pct exec $CONTAINER_ID -- bash -c "cd /opt/airplay-multiroom-server && source venv/bin/activate && pip install --upgrade pip && pip install -r requirements.txt"
print_success "Dependencies aktualisiert"

# GStreamer-Bindings prüfen
print_info "Prüfe GStreamer Python-Bindings..."
pct exec $CONTAINER_ID -- bash -c "if [ ! -e /opt/airplay-multiroom-server/venv/lib/python3.*/site-packages/gi ]; then ln -s /usr/lib/python3/dist-packages/gi /opt/airplay-multiroom-server/venv/lib/python3.*/site-packages/ 2>/dev/null || true; fi"
print_success "GStreamer-Bindings geprüft"

# Systemd neu laden
print_header "6. Systemd neu laden"

print_info "Lade Systemd-Konfiguration neu..."
pct exec $CONTAINER_ID -- systemctl daemon-reload
print_success "Systemd neu geladen"

# Service starten
print_header "7. Service starten"

print_info "Starte airplay-multiroom-server Service..."
pct exec $CONTAINER_ID -- systemctl start airplay-multiroom-server
sleep 3

# Status prüfen
if pct exec $CONTAINER_ID -- systemctl is-active --quiet airplay-multiroom-server; then
    print_success "Service erfolgreich gestartet"
else
    print_error "Service konnte nicht gestartet werden!"
    print_info "Zeige letzte Logs:"
    pct exec $CONTAINER_ID -- journalctl -u airplay-multiroom-server -n 20 --no-pager
    exit 1
fi

# Container-Info
print_header "8. Zusammenfassung"

CONTAINER_IP=$(pct exec $CONTAINER_ID -- ip -4 addr show eth0 | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -1)

echo ""
print_success "Update erfolgreich abgeschlossen!"
echo ""
echo "Container-Details:"
echo "  • Container-ID: $CONTAINER_ID"
echo "  • IP-Adresse: $CONTAINER_IP"
echo "  • Web-Interface: http://$CONTAINER_IP:5000"
echo ""
echo "Nützliche Befehle:"
echo "  • Status: pct exec $CONTAINER_ID -- systemctl status airplay-multiroom-server"
echo "  • Logs: pct exec $CONTAINER_ID -- journalctl -u airplay-multiroom-server -f"
echo "  • Geräte: pct exec $CONTAINER_ID -- curl -s http://localhost:5000/api/devices | jq"
echo "  • Discovery-Test: pct exec $CONTAINER_ID -- /opt/airplay-multiroom-server/venv/bin/python /opt/airplay-multiroom-server/scripts/test-discovery.py"
echo ""

if [ -n "$BACKUP_DIR" ] && [ -d "$BACKUP_DIR" ]; then
    echo "Backup gespeichert unter:"
    echo "  $BACKUP_DIR"
    echo ""
    print_info "Bei Problemen kann mit folgendem Befehl zurückgesetzt werden:"
    echo "  rm -rf /var/lib/lxc/$CONTAINER_ID/rootfs/opt/airplay-multiroom-server"
    echo "  mv $BACKUP_DIR /var/lib/lxc/$CONTAINER_ID/rootfs/opt/airplay-multiroom-server"
    echo ""
fi

print_info "Zeige Service-Status:"
pct exec $CONTAINER_ID -- systemctl status airplay-multiroom-server --no-pager -l

echo ""
print_success "Update-Prozess abgeschlossen! 🎉"
echo ""
