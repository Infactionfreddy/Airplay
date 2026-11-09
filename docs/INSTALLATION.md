# Installation

[← Zurück zur README](../README.md)

## Voraussetzungen

- Debian 11+ oder Ubuntu 20.04+ (andere Distributionen: Warnung im Skript)
- Python 3.8+
- Root-Rechte (`sudo`)
- GStreamer 1.0, Avahi, PulseAudio/ALSA (werden vom Skript installiert)
- Mind. 1 GB RAM; Netzwerkzugang zu allen AirPlay-Geräten
- Für LXC/Proxmox: Multicast-Weiterleitung auf dem Host, siehe `airplay-multiroom-server/docs/PROXMOX_INSTALLATION.md`

## Schritt für Schritt

1. Repository klonen:
   ```bash
   cd /opt
   sudo git clone https://github.com/Infactionfreddy/Airplay.git
   cd Airplay/airplay-multiroom-server
   ```
2. Installationsskript ausführen:
   ```bash
   sudo ./scripts/install.sh
   ```
   Das Skript installiert Systempakete, legt den Systembenutzer `airplay` an, kopiert `src/`, `web/` und `requirements.txt` nach `/opt/airplay-multiroom-server`, erstellt ein venv, kopiert `config/config.yaml` nach `/etc/airplay-multiroom/` (nur falls nicht vorhanden), schreibt die systemd-Unit, öffnet UFW-Ports (5000/tcp, 5001/tcp, 6000-6010/udp, 7000/tcp, 5353/udp) und aktiviert Avahi sowie den Dienst.
3. Konfiguration anpassen: `sudo nano /etc/airplay-multiroom/config.yaml`
4. Dienst starten und prüfen:
   ```bash
   sudo systemctl start airplay-multiroom-server
   sudo systemctl status airplay-multiroom-server
   ```
5. Web-Interface öffnen: `http://<server-ip>:5000`
6. Optional Discovery testen: `/opt/airplay-multiroom-server/venv/bin/python scripts/test-discovery.py`

> **Achtung:** Das Skript kopiert `web/`; dieses Verzeichnis fehlt im aktuellen Repository, wodurch das Skript wegen `set -e` abbrechen kann (Annahme). Die Python-Bindings (`python3-gi`) kommen aus dem System; ggf. Symlink nach `venv/lib/python3.*/site-packages/gi` setzen (wie in den Update-Skripten).

## Update

**Im Container/Server (Git-Klon):**
```bash
cd /opt/airplay-multiroom-server
./scripts/update-local.sh
```
Stasht lokale Änderungen, stoppt den Dienst, löscht den Python-Cache, `git pull`, aktualisiert Abhängigkeiten, setzt Rechte und startet neu.

**Vom Proxmox-Host:**
```bash
./scripts/update-server.sh 100 /tmp/airplay-multiroom-server
```
Erstellt ein Backup, kopiert Dateien in den Container (`pct exec`), aktualisiert Abhängigkeiten und startet den Dienst. Eine bestehende Config wird nicht überschrieben. Rollback: Backup-Verzeichnis zurückverschieben (Befehle gibt das Skript aus).

## Deinstallation

```bash
sudo ./scripts/uninstall.sh
```
Stoppt/deaktiviert den Dienst, entfernt Unit und Installationsverzeichnis, fragt nach Logs und Konfiguration, löscht den Benutzer `airplay` und entfernt UFW-Regeln. System-Pakete (GStreamer, Avahi) bleiben erhalten.
