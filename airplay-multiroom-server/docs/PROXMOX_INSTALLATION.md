# Installation auf Proxmox LXC Container

Diese Anleitung beschreibt die Installation des AirPlay Multiroom Servers auf einem Debian LXC-Container in Proxmox.

## 1. LXC Container erstellen

```bash
# Auf dem Proxmox Host:
pct create 100 local:vztmpl/debian-12-standard_12.0-1_amd64.tar.zst \
  --hostname airplay-server \
  --memory 1024 \
  --swap 512 \
  --cores 2 \
  --net0 name=eth0,bridge=vmbr0,ip=dhcp \
  --storage local-lvm \
  --rootfs local-lvm:8

pct start 100
```

## 2. Multicast-Routing aktivieren (WICHTIG!)

Für mDNS/AirPlay-Discovery muss Multicast-Traffic vom Container ins Netzwerk weitergeleitet werden:

```bash
# Auf dem Proxmox Host:
iptables -I FORWARD -m pkttype --pkt-type multicast -j ACCEPT

# Permanent machen - in /etc/rc.local hinzufügen:
echo 'iptables -I FORWARD -m pkttype --pkt-type multicast -j ACCEPT' >> /etc/rc.local
chmod +x /etc/rc.local
```

**Alternative für IPv6:**
```bash
ip6tables -I FORWARD -m pkttype --pkt-type multicast -j ACCEPT
```

## 3. In den Container einloggen

```bash
pct enter 100
```

## 4. System aktualisieren

```bash
apt update
apt upgrade -y
```

## 5. Projekt kopieren

**Methode 1: Direkter Dateisystem-Zugriff (auf Proxmox Host)**
```bash
# Projekt auf Host clonen/kopieren
cd /tmp
git clone https://github.com/your-repo/airplay-multiroom-server.git

# In Container kopieren
cp -r /tmp/airplay-multiroom-server /var/lib/lxc/100/rootfs/opt/
```

**Methode 2: rsync (wenn SSH im Container läuft)**
```bash
rsync -avz airplay-multiroom-server/ root@container-ip:/opt/airplay-multiroom-server/
```

## 6. Dependencies installieren

Im Container:

```bash
cd /opt/airplay-multiroom-server

# System-Pakete
apt install -y \
    python3 python3-pip python3-venv python3-dev \
    gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad gstreamer1.0-plugins-ugly \
    gstreamer1.0-libav \
    python3-gi python3-gst-1.0 \
    libgstreamer1.0-dev libgstreamer-plugins-base1.0-dev \
    avahi-daemon avahi-utils libnss-mdns \
    build-essential cmake \
    libssl-dev libavahi-compat-libdnssd-dev \
    libffi-dev
```

## 7. Python Umgebung einrichten

```bash
# Virtual Environment erstellen
python3 -m venv venv

# Aktivieren
source venv/bin/activate

# Python-Pakete installieren
pip install --upgrade pip
pip install -r requirements.txt

# GStreamer Python-Bindings verlinken (wichtig!)
ln -s /usr/lib/python3/dist-packages/gi venv/lib/python3.*/site-packages/
```

## 8. Konfiguration anpassen

```bash
# Konfig-Verzeichnis erstellen
mkdir -p /etc/airplay-multiroom

# Beispiel-Config kopieren
cp config/config.yaml /etc/airplay-multiroom/config.yaml

# Config editieren
nano /etc/airplay-multiroom/config.yaml
```

**Wichtige Einstellungen für automatische Erkennung:**
```yaml
devices:
  auto_discovery: true  # Automatische Erkennung aktivieren
  manual_devices: []    # Leer lassen für nur automatische Erkennung
```

## 9. Benutzer erstellen

```bash
useradd -r -s /bin/false airplay
chown -R airplay:airplay /opt/airplay-multiroom-server
```

## 10. Systemd Service einrichten

```bash
# Service-Datei kopieren
cp systemd/airplay-multiroom-server.service /etc/systemd/system/

# Falls __main__.py fehlt:
cat > /opt/airplay-multiroom-server/src/__main__.py << 'EOF'
"""Entry point for running the package as a module."""
import asyncio
from . import main

if __name__ == '__main__':
    asyncio.run(main())
EOF

# Wrapper-Script erstellen (für Python-Cache-Fix)
cat > /opt/airplay-multiroom-server/start.sh << 'EOF'
#!/bin/bash
cd /opt/airplay-multiroom-server
export PYTHONDONTWRITEBYTECODE=1
find . -type f -name "*.pyc" -delete
exec ./venv/bin/python -m src
EOF

chmod +x /opt/airplay-multiroom-server/start.sh

# Service aktivieren und starten
systemctl daemon-reload
systemctl enable airplay-multiroom-server
systemctl start airplay-multiroom-server
```

## 11. Status prüfen

```bash
# Service-Status
systemctl status airplay-multiroom-server

# Logs ansehen
journalctl -u airplay-multiroom-server -f

# Web-Interface testen
curl http://localhost:5000/api/status
```

## 12. Geräte-Discovery testen

```bash
# Gefundene AirPlay-Geräte anzeigen
avahi-browse -t _raop._tcp -r

# Discovery-Test-Script ausführen
cd /opt/airplay-multiroom-server
./venv/bin/python scripts/test-discovery.py
```

## Troubleshooting

### Keine Geräte werden gefunden

1. **Multicast-Routing prüfen** (auf Proxmox Host):
   ```bash
   iptables -L FORWARD -v | grep multicast
   ```
   
2. **Avahi läuft**:
   ```bash
   systemctl status avahi-daemon
   ```
   
3. **Manuelle Discovery testen**:
   ```bash
   avahi-browse -t _raop._tcp
   ```

### IPv6 Fehler

Falls "Address family not supported" Fehler auftreten, wurde die IPv4-only Konfiguration bereits im Code implementiert:

```python
# In device_manager.py:
self.zeroconf = Zeroconf(interfaces=["0.0.0.0"])  # IPv4-only
```

### RuntimeError bei asyncio

Diese sind bekannt und nicht kritisch. Sie entstehen durch Threading-Interaktion zwischen zeroconf und asyncio. Die Geräte werden trotzdem korrekt erkannt.

### GStreamer Import-Fehler

```bash
# Prüfen ob python3-gi installiert ist
dpkg -l | grep python3-gi

# Symlink prüfen
ls -la /opt/airplay-multiroom-server/venv/lib/python3.*/site-packages/gi

# Neu verlinken falls nötig
ln -sf /usr/lib/python3/dist-packages/gi /opt/airplay-multiroom-server/venv/lib/python3.11/site-packages/
```

## Web-Interface

Nach erfolgreicher Installation:

- **URL**: `http://<container-ip>:5000`
- **Geräte-Liste**: Automatisch erkannte Geräte erscheinen hier
- **API-Endpoints**:
  - `/api/status` - Server-Status
  - `/api/devices` - Liste aller Geräte
  - `/api/stats` - Statistiken

## Container-IP herausfinden

```bash
# Im Container:
ip addr show eth0

# Oder auf Proxmox Host:
pct exec 100 -- ip addr show eth0
```

## Nützliche Befehle

```bash
# Service neu starten
systemctl restart airplay-multiroom-server

# Logs in Echtzeit
journalctl -u airplay-multiroom-server -f

# Python-Cache löschen (bei Problemen nach Code-Änderungen)
find /opt/airplay-multiroom-server -name "*.pyc" -delete

# Container neu starten (von Proxmox Host)
pct restart 100
```
