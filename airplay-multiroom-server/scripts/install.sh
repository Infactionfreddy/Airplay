#!/bin/bash
set -e

# AirPlay Multiroom Server Installation Script für Debian/Ubuntu
# Verwendung: sudo ./install.sh

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Funktionen
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

check_root() {
    if [[ $EUID -ne 0 ]]; then
        log_error "Dieses Script muss als root ausgeführt werden (sudo ./install.sh)"
        exit 1
    fi
}

detect_distro() {
    if [ -f /etc/os-release ]; then
        . /etc/os-release
        OS=$NAME
        VER=$VERSION_ID
    else
        log_error "Kann Distribution nicht erkennen"
        exit 1
    fi
    
    log_info "Erkannte Distribution: $OS $VER"
    
    # Prüfen ob unterstützte Distribution
    case $OS in
        "Debian GNU/Linux"|"Ubuntu")
            ;;
        *)
            log_warning "Distribution möglicherweise nicht vollständig unterstützt"
            ;;
    esac
}

install_system_dependencies() {
    log_info "Installiere System-Dependencies..."
    
    # Package-Listen aktualisieren
    apt update
    
    # Grundlegende Pakete
    apt install -y \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
        build-essential \
        cmake \
        git \
        curl \
        wget \
        ca-certificates \
        gnupg \
        lsb-release
    
    # GStreamer
    log_info "Installiere GStreamer..."
    apt install -y \
        gstreamer1.0-tools \
        gstreamer1.0-plugins-base \
        gstreamer1.0-plugins-good \
        gstreamer1.0-plugins-bad \
        gstreamer1.0-plugins-ugly \
        gstreamer1.0-alsa \
        gstreamer1.0-pulseaudio \
        libgstreamer1.0-dev \
        libgstreamer-plugins-base1.0-dev \
        python3-gi \
        python3-gi-cairo \
        gir1.2-gstreamer-1.0 \
        gir1.2-gst-plugins-base-1.0
    
    # Avahi (mDNS/Bonjour)
    log_info "Installiere Avahi (mDNS/Bonjour)..."
    apt install -y \
        avahi-daemon \
        avahi-utils \
        libnss-mdns \
        libavahi-compat-libdnssd-dev
    
    # Audio-System
    log_info "Installiere Audio-System..."
    apt install -y \
        alsa-utils \
        pulseaudio \
        pulseaudio-utils
    
    # SSL/TLS
    log_info "Installiere SSL/TLS Libraries..."
    apt install -y \
        libssl-dev \
        libffi-dev
    
    # Entwicklungs-Tools (optional)
    apt install -y \
        htop \
        iotop \
        netstat-nat \
        tcpdump \
        nmap
    
    log_success "System-Dependencies erfolgreich installiert"
}

create_user() {
    local username="airplay"
    local homedir="/opt/airplay-multiroom-server"
    
    log_info "Erstelle Benutzer '$username'..."
    
    # Prüfen ob Benutzer bereits existiert
    if id "$username" &>/dev/null; then
        log_info "Benutzer '$username' existiert bereits"
    else
        # Benutzer erstellen
        useradd --system --shell /bin/false --home-dir "$homedir" --create-home "$username"
        log_success "Benutzer '$username' erstellt"
    fi
    
    # Audio-Gruppe hinzufügen (für Audio-Zugriff)
    usermod -a -G audio "$username" || true
}

install_application() {
    local install_dir="/opt/airplay-multiroom-server"
    local config_dir="/etc/airplay-multiroom"
    local log_dir="/var/log/airplay-multiroom"
    
    log_info "Installiere AirPlay Multiroom Server..."
    
    # Verzeichnisse erstellen
    mkdir -p "$install_dir"
    mkdir -p "$config_dir"
    mkdir -p "$log_dir"
    
    # Aktuelle Dateien kopieren
    cp -r src/ "$install_dir/"
    cp -r web/ "$install_dir/"
    cp requirements.txt "$install_dir/"
    
    # Python Virtual Environment erstellen
    log_info "Erstelle Python Virtual Environment..."
    python3 -m venv "$install_dir/venv"
    
    # Dependencies installieren
    log_info "Installiere Python-Dependencies..."
    "$install_dir/venv/bin/pip" install --upgrade pip
    "$install_dir/venv/bin/pip" install -r "$install_dir/requirements.txt"
    
    # Konfigurationsdatei kopieren
    if [ ! -f "$config_dir/config.yaml" ]; then
        cp config/config.yaml "$config_dir/"
        log_info "Standard-Konfiguration nach $config_dir/config.yaml kopiert"
    else
        log_info "Konfiguration bereits vorhanden - nicht überschrieben"
    fi
    
    # Berechtigungen setzen
    chown -R airplay:airplay "$install_dir"
    chown -R airplay:airplay "$log_dir"
    chown -R root:airplay "$config_dir"
    chmod -R 755 "$install_dir"
    chmod -R 750 "$config_dir"
    chmod -R 755 "$log_dir"
    
    log_success "Application erfolgreich installiert"
}

install_systemd_service() {
    local service_file="/etc/systemd/system/airplay-multiroom-server.service"
    
    log_info "Installiere systemd-Service..."
    
    # Service-Datei erstellen
    cat > "$service_file" << 'EOF'
[Unit]
Description=AirPlay Multiroom Server
Documentation=https://github.com/your-repo/airplay-multiroom-server
After=network.target sound.service
Wants=network.target

[Service]
Type=simple
User=airplay
Group=airplay
WorkingDirectory=/opt/airplay-multiroom-server
Environment=PATH=/opt/airplay-multiroom-server/venv/bin
Environment=PYTHONPATH=/opt/airplay-multiroom-server
ExecStart=/opt/airplay-multiroom-server/venv/bin/python -m src
ExecReload=/bin/kill -HUP $MAINPID
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=airplay-multiroom-server

# Sicherheitseinstellungen
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/var/log/airplay-multiroom
ReadOnlyPaths=/etc/airplay-multiroom

# Ressourcen-Limits
LimitNOFILE=65536
MemoryMax=1G

[Install]
WantedBy=multi-user.target
EOF

    # systemd neu laden
    systemctl daemon-reload
    
    log_success "systemd-Service installiert"
}

configure_firewall() {
    log_info "Konfiguriere Firewall..."
    
    # Prüfen ob ufw installiert ist
    if command -v ufw &> /dev/null; then
        log_info "Konfiguriere ufw..."
        
        # AirPlay-Ports öffnen
        ufw allow 5000/tcp comment "AirPlay Multiroom Web Interface"
        ufw allow 5001/tcp comment "AirPlay RTSP"
        ufw allow 6000:6010/udp comment "AirPlay RTP Audio"
        ufw allow 7000/tcp comment "AirPlay Output"
        
        # mDNS/Bonjour
        ufw allow 5353/udp comment "mDNS/Bonjour"
        
        log_success "ufw-Regeln hinzugefügt"
    else
        log_warning "ufw nicht installiert - Firewall-Konfiguration übersprungen"
        log_info "Manuelle Firewall-Konfiguration erforderlich:"
        log_info "  - TCP 5000 (Web Interface)"
        log_info "  - TCP 5001 (AirPlay RTSP)"
        log_info "  - UDP 6000-6010 (RTP Audio)"
        log_info "  - TCP 7000 (AirPlay Output)"
        log_info "  - UDP 5353 (mDNS)"
    fi
}

start_services() {
    log_info "Starte Services..."
    
    # Avahi starten
    systemctl enable avahi-daemon
    systemctl start avahi-daemon
    
    # AirPlay Multiroom Server aktivieren
    systemctl enable airplay-multiroom-server
    
    log_success "Services konfiguriert"
}

show_completion_message() {
    echo
    log_success "=== Installation erfolgreich abgeschlossen! ==="
    echo
    log_info "Der AirPlay Multiroom Server wurde installiert:"
    log_info "  • Installationsverzeichnis: /opt/airplay-multiroom-server"
    log_info "  • Konfiguration: /etc/airplay-multiroom/config.yaml"
    log_info "  • Logs: /var/log/airplay-multiroom/"
    echo
    log_info "Nächste Schritte:"
    log_info "  1. Konfiguration anpassen: sudo nano /etc/airplay-multiroom/config.yaml"
    log_info "  2. Service starten: sudo systemctl start airplay-multiroom-server"
    log_info "  3. Status prüfen: sudo systemctl status airplay-multiroom-server"
    log_info "  4. Web-Interface: http://$(hostname -I | awk '{print $1}'):5000"
    echo
    log_info "Logs anzeigen: sudo journalctl -u airplay-multiroom-server -f"
    echo
    log_warning "Vergessen Sie nicht, Ihre Firewall entsprechend zu konfigurieren!"
}

# Hauptinstallation
main() {
    echo "=== AirPlay Multiroom Server Installation ==="
    echo
    
    check_root
    detect_distro
    
    # Bestätigung
    read -p "Installation fortsetzen? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Installation abgebrochen"
        exit 0
    fi
    
    # Installationsschritte
    install_system_dependencies
    create_user
    install_application
    install_systemd_service
    configure_firewall
    start_services
    
    show_completion_message
}

# Script ausführen falls direkt aufgerufen
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi