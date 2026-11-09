# AirPlay Multiroom Server

![Python](https://img.shields.io/badge/Python-3.8%2B-3776AB?logo=python&logoColor=white) ![Lizenz](https://img.shields.io/badge/Lizenz-MIT-green)

Ein Debian-basierter AirPlay-Multiroom-Server, der Audio-Streams von AirPlay-Sendern (iOS/macOS) empfängt und synchronisiert an mehrere AirPlay-Geräte weiterleiten soll.

> **Hinweis:** Das Projekt liegt im Unterordner `airplay-multiroom-server/`. Laut Code-Stand sind Teile noch Platzhalter (z. B. RSA-Schlüssel, mDNS-Registrierung des Empfängers). Details siehe [Architektur](docs/ARCHITEKTUR.md).

## Features

- 🎵 Empfang von AirPlay-Streams (RAOP/RTSP) von iOS/macOS-Geräten
- 🔄 Synchronisierte Wiedergabe auf mehreren AirPlay-Geräten (Ziel)
- ⏱️ Einstellbare globale und gerätespezifische Verzögerung
- 🔍 Automatische Geräteerkennung via mDNS/Bonjour
- 🌐 Web-Interface für Konfiguration und Überwachung (Port 5000)
- 🖥️ Systemd-Integration für automatischen Start
- 🛠️ Skripte für Installation, Update (auch für Proxmox-LXC), Deinstallation und Discovery-Test

## Tech-Stack

- Python 3.8+ mit `asyncio`
- GStreamer (über PyGObject) für die Audio-Pipeline
- zeroconf / Avahi für mDNS
- Flask, aiohttp, websockets für das Web-Interface
- PyYAML für die Konfiguration, cryptography für Verschlüsselung
- pytest, black, flake8 für die Entwicklung

## Schnellstart

### Voraussetzungen

- Debian 11+ oder Ubuntu 20.04+
- Python 3.8+, GStreamer 1.0, Avahi
- mind. 1 GB RAM, Netzwerkzugang zu allen Zielgeräten

### Installation

```bash
cd /opt
sudo git clone https://github.com/Infactionfreddy/Airplay.git
cd Airplay/airplay-multiroom-server
sudo ./scripts/install.sh
```

### Start

```bash
sudo systemctl enable airplay-multiroom-server
sudo systemctl start airplay-multiroom-server
```

Web-Interface: `http://<server-ip>:5000`

Entwicklungsmodus: `./scripts/dev-setup.sh` und danach `./start-dev.sh`.

## Konfiguration

Die Konfiguration erfolgt über eine YAML-Datei (`/etc/airplay-multiroom/config.yaml`, Vorlage: `config/config.yaml`). Der Code liest keine Umgebungsvariablen aus; im alten README wird lediglich `DEBUG=1` für systemd erwähnt (im gezeigten Code nicht ausgewertet, stattdessen `--debug`).

| Einstellung | Standard | Beschreibung |
|---|---|---|
| `web.port` | 5000 | Port des Web-Interfaces |
| `airplay.port` | 5001 | Port des AirPlay-Empfängers |
| `airplay.buffer_time` | 2.0 | Puffer in Sekunden |
| `synchronization.global_delay` | 0.5 | Globale Verzögerung (s) |
| `devices.auto_discovery` | true | mDNS-Erkennung |
| `logging.level` | INFO | Log-Level |

Alle Optionen: [docs/KONFIGURATION.md](docs/KONFIGURATION.md).

## Projektstruktur

```
airplay-multiroom-server/
├── config/config.yaml          # Beispielkonfiguration
├── docs/PROXMOX_INSTALLATION.md
├── scripts/                    # install, update, uninstall, dev-setup, test-discovery
├── src/
│   ├── __init__.py             # Hauptklasse AirPlayMultiroomServer
│   ├── airplay_receiver.py     # RAOP/RTSP-Empfänger
│   ├── audio_pipeline.py       # GStreamer-Pipeline
│   ├── config_manager.py       # YAML-Konfiguration
│   ├── device_manager.py       # mDNS-Geräteverwaltung
│   ├── multiroom_coordinator.py# Synchronisation
│   └── web_interface.py        # Web-UI/API
├── systemd/airplay-multiroom-server.service
├── requirements.txt
└── start-dev.sh
```

## Dokumentation

- [Architektur](docs/ARCHITEKTUR.md)
- [Installation](docs/INSTALLATION.md)
- [Konfiguration](docs/KONFIGURATION.md)
- [Entwicklung](docs/ENTWICKLUNG.md)
- [API](docs/API.md)
- [Proxmox-Installation](airplay-multiroom-server/docs/PROXMOX_INSTALLATION.md)
- [Skript-Übersicht](airplay-multiroom-server/scripts/README.md)

## Troubleshooting

- **Keine Geräte gefunden:** `sudo systemctl status avahi-daemon`, bei LXC Multicast-Routing aktivieren (`iptables -I FORWARD -m pkttype --pkt-type multicast -j ACCEPT` auf dem Proxmox-Host), Test: `./venv/bin/python scripts/test-discovery.py`.
- **Audio-Aussetzer:** `airplay.buffer_time` erhöhen, Netzwerkqualität prüfen.
- **Sync-Probleme:** gerätespezifische Verzögerungen justieren, nach Möglichkeit LAN statt WLAN.
- **Logs:** `sudo journalctl -u airplay-multiroom-server -f`

## Lizenz

MIT License – siehe [LICENSE](airplay-multiroom-server/LICENSE).

## Beiträge

Beiträge sind willkommen! Bitte vor größeren Änderungen ein Issue erstellen.
