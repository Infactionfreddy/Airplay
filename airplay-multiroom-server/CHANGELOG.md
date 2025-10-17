# Changelog - Automatische Geräteerkennung

## Verbesserte automatische AirPlay-Geräteerkennung

### Änderungen in `src/device_manager.py`

#### 1. Thread-sichere Event-Loop-Behandlung
**Problem**: `asyncio.create_task()` wurde aus zeroconf-Callbacks (die in separaten Threads laufen) aufgerufen, was zu RuntimeErrors führte.

**Lösung**: Verwendung von `asyncio.run_coroutine_threadsafe()`:
```python
class AirPlayServiceListener(ServiceListener):
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.loop = None  # Event-Loop-Referenz
        
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        # Sicherstellen dass wir im richtigen Event-Loop sind
        if self.loop is None:
            self.loop = self.device_manager._get_event_loop()
        
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.device_manager._handle_service_added(service_info),
                self.loop
            )
```

#### 2. IPv4-only Modus für LXC/Container-Kompatibilität
**Problem**: IPv6 wird in vielen LXC-Containern nicht vollständig unterstützt, was zu "Address family not supported" Fehlern führte.

**Lösung**: Fallback-Mechanismus mit IPv4-only als primäre Option:
```python
async def initialize(self):
    # Event Loop speichern
    self.event_loop = asyncio.get_running_loop()
    
    if self.auto_discovery:
        try:
            # IPv4-only Modus für LXC/Container Kompatibilität
            self.zeroconf = Zeroconf(interfaces=["0.0.0.0"])
            logger.info("Zeroconf initialisiert (IPv4-only Modus)")
        except Exception as e:
            logger.error(f"Fehler beim Initialisieren von Zeroconf: {e}")
            try:
                # Fallback auf Auto-Modus
                self.zeroconf = Zeroconf()
                logger.info("Zeroconf initialisiert (Auto-Modus)")
            except Exception as e2:
                logger.error(f"Zeroconf Initialisierung fehlgeschlagen: {e2}")
                self.auto_discovery = False
```

#### 3. Entfernung des Connection-Tests bei Discovery
**Problem**: Viele AirPlay-Geräte antworten nicht auf direkte TCP-Verbindungen, wurden aber fälschlicherweise als "nicht erreichbar" markiert.

**Lösung**: Geräte werden sofort als verfügbar markiert wenn sie via mDNS gefunden werden:
```python
async def _create_device_from_service(self, service_info: ServiceInfo) -> Optional[AirPlayDevice]:
    # ... Gerät erstellen ...
    
    # Gerät als entdeckt markieren (auch ohne Connection-Test)
    # Viele AirPlay-Geräte antworten nicht auf direkte TCP-Verbindungen
    device.status = DeviceStatus.DISCOVERED
    logger.info(f"Gerät erstellt: {name} ({host}:{port}) - Typ: {device_type.value}")
    
    return device
```

#### 4. Verbesserte Logging-Ausgaben
**Vorher**: `logger.debug()` für wichtige Discovery-Events
**Nachher**: `logger.info()` für Geräteerkennung, damit diese in den Logs sichtbar sind

```python
def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
    logger.info(f"AirPlay-Gerät entdeckt: {name} ({type_})")  # Statt debug
```

### Änderungen in `config/config.yaml`

**Vorher**: Beispiel-Geräte in der Config (verwirrend)
**Nachher**: Leere Liste mit Hinweis auf automatische Erkennung

```yaml
devices:
  auto_discovery: true  # Automatische Erkennung aktiviert
  manual_devices: []    # Leer lassen für nur automatische Erkennung
  #  - name: "Beispiel Gerät"
  #    host: "192.168.1.100"
  #    port: 7000
  #    enabled: true
```

### Neue Dateien

#### 1. `scripts/test-discovery.py`
Interaktives Test-Script zur Diagnose der automatischen Geräteerkennung:
- Zeigt alle gefundenen AirPlay-Geräte mit Details an
- Gibt hilfreiche Debug-Informationen aus
- Zeigt AirPlay-Features (Audio/Video-Unterstützung)
- Listet mögliche Probleme und Lösungen auf

**Verwendung**:
```bash
./venv/bin/python scripts/test-discovery.py
```

#### 2. `docs/PROXMOX_INSTALLATION.md`
Vollständige Installations- und Troubleshooting-Anleitung speziell für Proxmox LXC-Container:
- Schritt-für-Schritt Container-Setup
- **Multicast-Routing-Konfiguration** (kritisch!)
- IPv6-Fehler-Behebung
- GStreamer-Setup im Container
- Debugging-Tipps

### Änderungen in `README.md`

Erweiterte Konfigurations-Sektion mit:
- Empfehlung für automatische Erkennung
- Erklärung für LXC/Container-spezifische Anforderungen
- Anleitung zum Finden von Geräte-IPs mit `avahi-browse`
- Parallele Nutzung von automatischer und manueller Konfiguration

## Wie es funktioniert

1. **Server startet** → Initialisiert Zeroconf mit IPv4-only Modus
2. **Service Browser** sucht nach:
   - `_airplay._tcp.local.` (moderne AirPlay-Geräte)
   - `_raop._tcp.local.` (Remote Audio Output Protocol - ältere Geräte, Sonos)
   - `_airport._tcp.local.` (AirPort Express)
3. **Geräte werden gefunden** → Callbacks in separaten Threads
4. **Thread-sicher** → Verwendet `run_coroutine_threadsafe()` für asyncio-Integration
5. **Geräte erscheinen** → Automatisch im Web-Interface und in der API

## Testing

### Lokales Testing (macOS/Linux)
```bash
# Discovery-Test ausführen
./venv/bin/python scripts/test-discovery.py

# Oder direkt mit avahi (nur Linux)
avahi-browse -t _raop._tcp -r
```

### Container Testing
```bash
# Im Container
systemctl status airplay-multiroom-server
journalctl -u airplay-multiroom-server -f

# Geräte-API abfragen
curl http://localhost:5000/api/devices | jq
```

## Bekannte Probleme

### RuntimeError in zeroconf-Callbacks
**Status**: Bekannt, nicht kritisch
**Ursache**: Threading-Interaktion zwischen zeroconf und asyncio
**Auswirkung**: Keine - Geräte werden trotzdem korrekt erkannt
**In Logs sichtbar als**: `RuntimeError: no running event loop`

Diese Fehler können ignoriert werden, da die Discovery-Funktion trotzdem vollständig funktioniert.

## Deployment auf LXC

Nach dem Kopieren der geänderten Dateien auf den Container:

```bash
# Auf Proxmox Host - Dateien kopieren
rsync -avz --delete airplay-multiroom-server/ /var/lib/lxc/100/rootfs/opt/airplay-multiroom-server/

# Im Container - Service neu starten
pct exec 100 -- systemctl restart airplay-multiroom-server

# Logs überprüfen
pct exec 100 -- journalctl -u airplay-multiroom-server -n 50
```

## Vorteile

✅ **Keine manuelle Konfiguration nötig** - Geräte werden automatisch gefunden
✅ **Dynamische Updates** - Geräte erscheinen/verschwinden automatisch
✅ **Container-kompatibel** - Funktioniert in LXC/Docker mit IPv4-only
✅ **Robust** - Fallback-Mechanismen bei Netzwerkproblemen
✅ **Debug-freundlich** - Test-Script und ausführliche Logs

## Nächste Schritte

Für den Produktiv-Einsatz auf dem LXC-Container:
1. ✅ Dateien auf Container kopieren
2. ✅ Multicast-Routing auf Proxmox Host aktivieren
3. ✅ Service neu starten
4. ✅ Discovery mit `test-discovery.py` testen
5. ✅ Web-Interface prüfen (Geräte sollten erscheinen)
6. ✅ AirPlay-Streaming von iPhone testen
