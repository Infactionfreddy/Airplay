#!/bin/bash

# AirPlay Multiroom Server Deinstallationsskript
# Verwendung: sudo ./uninstall.sh

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

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
        log_error "Dieses Script muss als root ausgeführt werden (sudo ./uninstall.sh)"
        exit 1
    fi
}

stop_service() {
    log_info "Stoppe AirPlay Multiroom Server Service..."
    
    if systemctl is-active --quiet airplay-multiroom-server; then
        systemctl stop airplay-multiroom-server
        log_info "Service gestoppt"
    fi
    
    if systemctl is-enabled --quiet airplay-multiroom-server; then
        systemctl disable airplay-multiroom-server
        log_info "Service deaktiviert"
    fi
}

remove_systemd_service() {
    log_info "Entferne systemd-Service..."
    
    local service_file="/etc/systemd/system/airplay-multiroom-server.service"
    
    if [[ -f "$service_file" ]]; then
        rm "$service_file"
        systemctl daemon-reload
        log_success "systemd-Service entfernt"
    fi
}

remove_application() {
    log_info "Entferne Application..."
    
    local install_dir="/opt/airplay-multiroom-server"
    local log_dir="/var/log/airplay-multiroom"
    
    # Installation entfernen
    if [[ -d "$install_dir" ]]; then
        rm -rf "$install_dir"
        log_success "Installationsverzeichnis entfernt"
    fi
    
    # Logs entfernen (optional)
    if [[ -d "$log_dir" ]]; then
        read -p "Log-Dateien ebenfalls entfernen? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$log_dir"
            log_success "Log-Verzeichnis entfernt"
        fi
    fi
}

remove_user() {
    log_info "Entferne Benutzer..."
    
    local username="airplay"
    
    if id "$username" &>/dev/null; then
        userdel "$username" 2>/dev/null || true
        log_success "Benutzer '$username' entfernt"
    fi
}

remove_config() {
    log_info "Entferne Konfiguration..."
    
    local config_dir="/etc/airplay-multiroom"
    
    if [[ -d "$config_dir" ]]; then
        read -p "Konfigurationsdateien ebenfalls entfernen? (y/N): " -n 1 -r
        echo
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            rm -rf "$config_dir"
            log_success "Konfigurationsverzeichnis entfernt"
        else
            log_info "Konfiguration beibehalten in: $config_dir"
        fi
    fi
}

cleanup_firewall() {
    log_info "Entferne Firewall-Regeln..."
    
    if command -v ufw &> /dev/null; then
        # UFW-Regeln entfernen (falls vorhanden)
        ufw --force delete allow 5000/tcp 2>/dev/null || true
        ufw --force delete allow 5001/tcp 2>/dev/null || true
        ufw --force delete allow 6000:6010/udp 2>/dev/null || true
        ufw --force delete allow 7000/tcp 2>/dev/null || true
        ufw --force delete allow 5353/udp 2>/dev/null || true
        
        log_success "UFW-Regeln entfernt"
    else
        log_warning "UFW nicht installiert - manuelle Firewall-Bereinigung erforderlich"
    fi
}

main() {
    echo "=== AirPlay Multiroom Server Deinstallation ==="
    echo
    
    check_root
    
    # Warnung
    log_warning "WARNUNG: Diese Aktion entfernt den AirPlay Multiroom Server komplett!"
    read -p "Deinstallation fortsetzen? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Deinstallation abgebrochen"
        exit 0
    fi
    
    # Deinstallationsschritte
    stop_service
    remove_systemd_service
    remove_application
    remove_user
    remove_config
    cleanup_firewall
    
    echo
    log_success "=== Deinstallation erfolgreich abgeschlossen! ==="
    echo
    log_info "Der AirPlay Multiroom Server wurde vollständig entfernt."
    log_info "System-Dependencies (GStreamer, Avahi, etc.) wurden beibehalten."
}

main "$@"