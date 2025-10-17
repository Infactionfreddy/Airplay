# AirPlay Multiroom Server

Ein Debian-basierter AirPlay Multiroom-Server, der Audio-Streams von AirPlay-Sendern empfängt und diese synchronisiert an mehrere AirPlay-Geräte weiterleitet.

## Features

- 🎵 Empfängt AirPlay-Streams von iOS/macOS Geräten
- 🔄 Synchronisierte Wiedergabe auf mehreren AirPlay-Geräten
- ⏱️ Einstellbare Verzögerung für perfekte Synchronisation
- 🔍 Automatische Geräteerkennung via mDNS/Bonjour
- 🌐 Web-Interface für Konfiguration und Überwachung
- 🖥️ Systemd-Integration für automatischen Start

## Architektur

```
AirPlay Sender (iPhone/Mac) → [Multiroom Server] → AirPlay Devices (HomePod, etc.)
                                      ↓
                               Audio Processing Pipeline
                                      ↓
                              Synchronized Broadcasting
```

## Systemanforderungen

- Debian 11+ oder Ubuntu 20.04+
- Python 3.8+
- GStreamer 1.0
- Avahi (mDNS)
- Mindestens 1GB RAM
- Netzwerkverbindung zu allen Zielgeräten

## Installation

### 1. System-Dependencies installieren

```bash
sudo apt update
sudo apt install -y \
    python3 python3-pip python3-venv \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    avahi-daemon avahi-utils libnss-mdns \
    build-essential cmake \
    libssl-dev libavahi-compat-libdnssd-dev
```

### 2. Projekt einrichten

```bash
cd /opt
sudo git clone https://github.com/your-repo/airplay-multiroom-server.git
cd airplay-multiroom-server
sudo ./scripts/install.sh
```

### 3. Service starten

```bash
sudo systemctl enable airplay-multiroom-server
sudo systemctl start airplay-multiroom-server
```

## Konfiguration

Die Konfiguration erfolgt über `/etc/airplay-multiroom/config.yaml`:

### Automatische Geräteerkennung (empfohlen)

Der Server erkennt AirPlay-Geräte automatisch über mDNS/Bonjour. Dies ist die einfachste Methode:

```yaml
devices:
  auto_discovery: true  # Automatische Erkennung aktiviert
  manual_devices: []    # Keine manuellen Geräte nötig
```

Der Server findet automatisch:
- Sonos-Lautsprecher mit AirPlay 2
- HomePods und HomePod minis
- Apple TV
- AirPort Express
- Andere AirPlay-fähige Geräte

**Wichtig für LXC/Container-Umgebungen:**
- Multicast-Routing muss auf dem Host aktiviert sein
- Auf Proxmox: `iptables -I FORWARD -m pkttype --pkt-type multicast -j ACCEPT`
- Avahi-Daemon muss im Container laufen

### Manuelle Gerätekonfiguration (optional)

Falls automatische Erkennung nicht funktioniert oder zusätzliche Geräte hinzugefügt werden sollen:

```yaml
devices:
  auto_discovery: true  # Kann parallel aktiviert bleiben
  manual_devices:
    - name: "Wohnzimmer"
      host: "192.168.1.100"
      port: 7000
      enabled: true
    - name: "Küche"
      host: "192.168.1.101"
      port: 7000
      enabled: true
```

**Geräte-IPs herausfinden:**
```bash
# AirPlay-Geräte im Netzwerk anzeigen
avahi-browse -t _raop._tcp -r

# Oder:
avahi-browse -t _airplay._tcp -r
```

### Synchronisations-Einstellungen

```yaml
airplay:
  buffer_time: 2.0  # Sekunden Puffer für Synchronisation
  
synchronization:
  global_delay: 0.5  # Globale Verzögerung in Sekunden
  device_delays:
    "Wohnzimmer": 0.0
    "Küche": 0.1  # 100ms zusätzliche Verzögerung
```

## Web-Interface

Nach der Installation ist das Web-Interface unter `http://server-ip:5000` erreichbar.

## Architektur-Details

### Komponenten

1. **AirPlay Receiver** (`src/airplay_receiver.py`)
   - Empfängt AirPlay-Streams über RAOP/RTSP
   - Dekodiert Audio (ALAC/AAC)

2. **Audio Pipeline** (`src/audio_pipeline.py`)
   - GStreamer-basierte Audio-Verarbeitung
   - Buffering und Format-Konvertierung

3. **Device Manager** (`src/device_manager.py`)
   - mDNS-Geräteerkennung
   - Verbindungsmanagement

4. **Multiroom Coordinator** (`src/multiroom_coordinator.py`)
   - Synchronisation zwischen Geräten
   - Verzögerungsmanagement

5. **Web Interface** (`web/`)
   - Konfiguration und Monitoring
   - Geräteverwaltung

### Audio-Pipeline

```
AirPlay Input → Decoder → Buffer → Sync Engine → Multiple AirPlay Outputs
                    ↓
              Format Conversion
                    ↓
              Timing Alignment
```

## Server aktualisieren

### Auf Proxmox LXC Container

**Automatisches Update vom Proxmox Host:**
```bash
# Projekt aktualisieren
cd /tmp/airplay-multiroom-server
git pull

# Update-Script ausführen
./scripts/update-server.sh 100 /tmp/airplay-multiroom-server
```

**Oder direkt im Container:**
```bash
cd /opt/airplay-multiroom-server
./scripts/update-local.sh
```

Siehe [`scripts/README.md`](scripts/README.md) für Details zu allen verfügbaren Scripts.

### Standard-Installation

```bash
cd /opt/airplay-multiroom-server
git pull
sudo systemctl stop airplay-multiroom-server
pip install -r requirements.txt
sudo systemctl start airplay-multiroom-server
```

## Troubleshooting

### Häufige Probleme

1. **Keine Geräte gefunden**
   - Prüfen Sie die mDNS-Konfiguration
   - Stellen Sie sicher, dass Avahi läuft: `sudo systemctl status avahi-daemon`
   - Bei LXC: Multicast-Routing aktivieren (siehe [Proxmox Installation](docs/PROXMOX_INSTALLATION.md))
   - Discovery testen: `./venv/bin/python scripts/test-discovery.py`

2. **Audio-Aussetzer**
   - Erhöhen Sie die Puffergröße in der Konfiguration
   - Prüfen Sie die Netzwerkqualität

3. **Synchronisationsprobleme**
   - Justieren Sie die gerätespezifischen Verzögerungen
   - Verwenden Sie eine Kabel-Netzwerkverbindung wenn möglich

### Logs

```bash
# Service-Logs anzeigen
sudo journalctl -u airplay-multiroom-server -f

# Debug-Modus aktivieren
sudo systemctl edit airplay-multiroom-server
# Fügen Sie hinzu: Environment="DEBUG=1"
```

## Entwicklung

### Entwicklungsumgebung einrichten

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### Tests ausführen

```bash
python -m pytest tests/
```

## Lizenz

MIT License - siehe LICENSE Datei für Details.

## Beiträge

Beiträge sind willkommen! Bitte erstellen Sie ein Issue bevor Sie größere Änderungen vornehmen.