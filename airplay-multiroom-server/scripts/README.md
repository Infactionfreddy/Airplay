# Scripts Übersicht

Dieses Verzeichnis enthält hilfreiche Scripts für Installation, Update und Wartung des AirPlay Multiroom Servers.

## 📋 Verfügbare Scripts

### `install.sh`
Installiert den AirPlay Multiroom Server als Systemd-Service.

**Verwendung:**
```bash
sudo ./scripts/install.sh
```

**Was es macht:**
- Erstellt Benutzer und Gruppen
- Installiert Systemd-Service
- Kopiert Konfigurationsdateien
- Startet den Service

---

### `update-server.sh` ⭐
**Aktualisiert den Server auf einem Proxmox LXC-Container von außen.**

**Verwendung (auf Proxmox Host):**
```bash
./scripts/update-server.sh [container-id] [pfad-zum-projekt]

# Beispiel:
./scripts/update-server.sh 100 /tmp/airplay-multiroom-server
```

**Parameter:**
- `container-id` - ID des LXC-Containers (Standard: 100)
- `pfad-zum-projekt` - Pfad zum Projektverzeichnis (Standard: aktuelles Verzeichnis)

**Was es macht:**
1. ✅ Prüft Container-Status
2. ✅ Erstellt Backup der aktuellen Installation
3. ✅ Stoppt den Service
4. ✅ Löscht Python-Cache
5. ✅ Kopiert aktualisierte Dateien
6. ✅ Aktualisiert Python-Dependencies
7. ✅ Lädt Systemd neu
8. ✅ Startet Service und prüft Status

**Features:**
- 🎨 Farbige Ausgabe mit Statusanzeigen
- 💾 Automatisches Backup vor Update
- 🔄 Rollback-Anweisungen bei Fehlern
- 📊 Detaillierte Zusammenfassung nach Update
- ⚡ Fehlerbehandlung und Validierung

**Ausgabe:**
```
═══════════════════════════════════════════════════════════
  1. Systemprüfungen
═══════════════════════════════════════════════════════════

✓ Proxmox Host erkannt
✓ Container 100 gefunden
✓ Container läuft
✓ Quellverzeichnis gefunden
✓ Projektstruktur validiert

...

✓ Update erfolgreich abgeschlossen! 🎉
```

---

### `update-local.sh`
**Aktualisiert den Server direkt im Container via Git-Pull.**

**Verwendung (im Container):**
```bash
cd /opt/airplay-multiroom-server
./scripts/update-local.sh
```

**Voraussetzungen:**
- Git muss installiert sein
- Projekt muss via Git geklont sein
- Muss im Projekt-Root-Verzeichnis ausgeführt werden

**Was es macht:**
1. ✅ Prüft Git-Repository-Status
2. ✅ Sichert lokale Änderungen (git stash)
3. ✅ Stoppt den Service
4. ✅ Löscht Python-Cache
5. ✅ Führt `git pull` aus
6. ✅ Aktualisiert Dependencies
7. ✅ Startet Service neu

**Interaktiv:**
- Zeigt lokale Änderungen an
- Fragt vor Überschreiben um Bestätigung
- Zeigt detaillierte Logs bei Fehlern

---

### `test-discovery.py`
**Testet die automatische AirPlay-Geräteerkennung.**

**Verwendung:**
```bash
./venv/bin/python scripts/test-discovery.py
```

**Was es macht:**
- 🔍 Sucht nach AirPlay-Geräten im Netzwerk
- 📱 Zeigt Details zu jedem gefundenen Gerät
- 📋 Listet unterstützte Features auf (Audio/Video)
- 💡 Gibt Troubleshooting-Tipps bei Problemen

**Ausgabe:**
```
═══════════════════════════════════════════════════════════
📱 Gerät: Küche Sonos
═══════════════════════════════════════════════════════════
📍 IP-Adressen:
   - 10.30.0.64
🔌 Port: 7000
🖥️  Server: Sonos-542A1B5D1E58.local

📋 Eigenschaften:
   am: Sonos
   fv: 366.0
   ft: 0x4A7FDFD5

🎵 Modell: Sonos
✨ Features: 0x4A7FDFD5
   - Audio: ✅
   - Video: ✅
💾 Firmware: 366.0
```

**Nützlich für:**
- Debugging von Discovery-Problemen
- Überprüfung von Multicast-Routing
- Ermittlung von Geräte-IPs und -Ports
- Verifizierung der Netzwerk-Konfiguration

---

### `dev-setup.sh`
Richtet eine Entwicklungsumgebung ein.

**Verwendung:**
```bash
./scripts/dev-setup.sh
```

**Was es macht:**
- Erstellt Python Virtual Environment
- Installiert Dependencies
- Richtet Development-Tools ein

---

### `uninstall.sh`
Deinstalliert den AirPlay Multiroom Server komplett.

**Verwendung:**
```bash
sudo ./scripts/uninstall.sh
```

**Was es macht:**
- Stoppt und deaktiviert Service
- Entfernt Systemd-Service
- Löscht Konfigurationsdateien
- Entfernt Benutzer und Gruppen

---

## 🔧 Verwendungsbeispiele

### Kompletter Update-Workflow (Proxmox Host)

```bash
# 1. Projekt lokal aktualisieren
cd /tmp/airplay-multiroom-server
git pull

# 2. Update auf Container ausführen
./scripts/update-server.sh 100 .

# 3. Logs überprüfen
pct exec 100 -- journalctl -u airplay-multiroom-server -n 50

# 4. Discovery testen
pct exec 100 -- /opt/airplay-multiroom-server/venv/bin/python \
    /opt/airplay-multiroom-server/scripts/test-discovery.py
```

### Update direkt im Container

```bash
# 1. In Container einloggen
pct enter 100

# 2. Update ausführen
cd /opt/airplay-multiroom-server
./scripts/update-local.sh

# 3. Discovery testen
./venv/bin/python scripts/test-discovery.py
```

### Nur Discovery testen

```bash
# Von Proxmox Host
pct exec 100 -- /opt/airplay-multiroom-server/venv/bin/python \
    /opt/airplay-multiroom-server/scripts/test-discovery.py

# Im Container
cd /opt/airplay-multiroom-server
./venv/bin/python scripts/test-discovery.py
```

---

## 🚨 Troubleshooting

### Update-Script findet Container nicht

```bash
# Container-Liste anzeigen
pct list

# Mit richtiger ID ausführen
./scripts/update-server.sh <ihre-container-id> .
```

### Git-Fehler bei update-local.sh

```bash
# Git installieren
apt install git

# Repository klonen statt kopieren
cd /opt
rm -rf airplay-multiroom-server
git clone https://github.com/Infactionfreddy/Airplay/airplay-multiroom-server.git
cd airplay-multiroom-server
./scripts/update-local.sh
```

### Berechtigungsfehler

```bash
# Scripts ausführbar machen
chmod +x scripts/*.sh
chmod +x scripts/*.py

# Mit sudo ausführen falls nötig
sudo ./scripts/update-local.sh
```

### Discovery findet keine Geräte

```bash
# Multicast-Routing prüfen (auf Proxmox Host)
iptables -L FORWARD -v | grep multicast

# Falls nicht vorhanden, aktivieren
iptables -I FORWARD -m pkttype --pkt-type multicast -j ACCEPT

# Avahi-Daemon prüfen (im Container)
systemctl status avahi-daemon

# Falls nicht läuft, starten
systemctl start avahi-daemon
```

---

## 📝 Hinweise

- **Backups**: `update-server.sh` erstellt automatisch Backups vor dem Update
- **Rollback**: Bei Problemen siehe Ausgabe des Scripts für Rollback-Befehle
- **Logs**: Immer Logs nach Update überprüfen: `journalctl -u airplay-multiroom-server -f`
- **Testing**: Discovery-Test ausführen um sicherzustellen dass Geräte gefunden werden
