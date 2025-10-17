# 🚀 Update-Scripts - Schnellstart

## Zwei Methoden zum Aktualisieren:

### 1️⃣ Vom Proxmox Host (Empfohlen)

```bash
# Einmalig: Projekt auf Host clonen
cd /tmp
git clone https://github.com/Infactionfreddy/Airplay/airplay-multiroom-server.git
cd airplay-multiroom-server

# Bei jedem Update:
git pull
./scripts/update-server.sh 100 .
```

**Vorteile:**
- ✅ Automatisches Backup
- ✅ Vollständige Fehlerbehandlung
- ✅ Detaillierte Status-Ausgabe
- ✅ Rollback-Anweisungen

---

### 2️⃣ Direkt im Container

```bash
# Einmalig: Git im Container installieren
pct exec 100 -- apt install git

# Einmalig: Projekt via Git clonen (statt kopieren)
pct exec 100 -- bash -c 'cd /opt && rm -rf airplay-multiroom-server && git clone https://github.com/Infactionfreddy/Airplay/airplay-multiroom-server.git'

# Bei jedem Update:
pct exec 100 -- bash -c 'cd /opt/airplay-multiroom-server && ./scripts/update-local.sh'
```

**Vorteile:**
- ✅ Schneller bei häufigen Updates
- ✅ Keine Dateikopie nötig
- ✅ Git-Versionskontrolle

---

## 🧪 Nach dem Update testen

```bash
# Service-Status prüfen
pct exec 100 -- systemctl status airplay-multiroom-server

# Logs anzeigen
pct exec 100 -- journalctl -u airplay-multiroom-server -n 50

# Discovery testen
pct exec 100 -- /opt/airplay-multiroom-server/venv/bin/python /opt/airplay-multiroom-server/scripts/test-discovery.py

# Geräte über API abfragen
pct exec 100 -- curl -s http://localhost:5000/api/devices | jq
```

---

## 📦 Was wird aktualisiert?

- ✅ Python Source-Code (`src/`)
- ✅ Scripts (`scripts/`)
- ✅ Web-Interface (`web/`)
- ✅ Python Dependencies (`requirements.txt`)
- ✅ Systemd Service-Datei
- ❌ **Config wird NICHT überschrieben** (`/etc/airplay-multiroom/config.yaml`)

---

## 🔙 Rollback bei Problemen

Falls nach dem Update Probleme auftreten:

```bash
# Backup-Verzeichnis finden
ls -la /var/lib/lxc/100/rootfs/opt/ | grep backup

# Aktuellen Stand löschen
rm -rf /var/lib/lxc/100/rootfs/opt/airplay-multiroom-server

# Backup wiederherstellen
mv /var/lib/lxc/100/rootfs/opt/airplay-multiroom-server.backup.YYYYMMDD_HHMMSS \
   /var/lib/lxc/100/rootfs/opt/airplay-multiroom-server

# Service neu starten
pct exec 100 -- systemctl restart airplay-multiroom-server
```

---

## 💡 Tipps

1. **Vor größeren Updates:** Snapshot des Containers erstellen
   ```bash
   pct snapshot 100 pre-update
   ```

2. **Multicast-Routing prüfen** (wichtig nach Proxmox-Updates):
   ```bash
   iptables -L FORWARD -v | grep multicast
   # Falls nicht vorhanden:
   iptables -I FORWARD -m pkttype --pkt-type multicast -j ACCEPT
   ```

3. **Logs während Update live verfolgen:**
   ```bash
   # In neuem Terminal/Session
   pct exec 100 -- journalctl -u airplay-multiroom-server -f
   ```

---

## 📖 Weitere Dokumentation

- [`scripts/README.md`](README.md) - Detaillierte Script-Dokumentation
- [`../docs/PROXMOX_INSTALLATION.md`](../docs/PROXMOX_INSTALLATION.md) - Vollständige Installationsanleitung
- [`../CHANGELOG.md`](../CHANGELOG.md) - Änderungshistorie
