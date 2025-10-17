"""
Geräte-Manager für AirPlay-Geräteerkennung und -verwaltung
"""
import asyncio
import logging
import socket
import struct
from typing import Dict, List, Optional, Set, Callable
from dataclasses import dataclass
from enum import Enum
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ServiceInfo
import time

logger = logging.getLogger(__name__)


class DeviceType(Enum):
    """AirPlay-Gerätetypen"""
    AIRPLAY_AUDIO = "airplay_audio"
    AIRPLAY_VIDEO = "airplay_video" 
    AIRPORT_EXPRESS = "airport_express"
    HOMEPOD = "homepod"
    APPLE_TV = "apple_tv"
    UNKNOWN = "unknown"


class DeviceStatus(Enum):
    """Gerätestatus"""
    DISCOVERED = "discovered"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    DISCONNECTED = "disconnected"
    ERROR = "error"


@dataclass
class AirPlayDevice:
    """Repräsentiert ein AirPlay-Gerät"""
    device_id: str
    name: str
    host: str
    port: int
    device_type: DeviceType
    
    # Geräteeigenschaften
    model: Optional[str] = None
    manufacturer: Optional[str] = None
    firmware_version: Optional[str] = None
    features: Optional[int] = None
    
    # Netzwerk-Informationen
    mac_address: Optional[str] = None
    ip_addresses: Optional[List[str]] = None
    
    # Status
    status: DeviceStatus = DeviceStatus.DISCOVERED
    last_seen: Optional[float] = None
    connection_attempts: int = 0
    
    # mDNS-Eigenschaften
    txt_records: Optional[Dict[str, str]] = None
    
    def __post_init__(self):
        if self.last_seen is None:
            self.last_seen = time.time()
            
    def is_available(self) -> bool:
        """Prüft ob das Gerät verfügbar ist"""
        if self.status in [DeviceStatus.ERROR, DeviceStatus.DISCONNECTED]:
            return False
            
        # Timeout-Prüfung (Gerät als nicht verfügbar betrachten nach 60 Sekunden)
        if self.last_seen and (time.time() - self.last_seen) > 60.0:
            return False
            
        return True
        
    def supports_audio(self) -> bool:
        """Prüft ob das Gerät Audio unterstützt"""
        if self.features is None:
            return True  # Annahme: Audio wird unterstützt
            
        # AirPlay Feature-Flags prüfen
        # Bit 0: Audio
        return bool(self.features & 0x01)
        
    def get_airplay_url(self) -> str:
        """Gibt die AirPlay-URL zurück"""
        return f"rtsp://{self.host}:{self.port}"
        
    def update_from_service_info(self, service_info: ServiceInfo):
        """Aktualisiert Geräteinformationen aus mDNS ServiceInfo"""
        # TXT-Records verarbeiten
        if service_info.properties:
            self.txt_records = {}
            for key, value in service_info.properties.items():
                try:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    value_str = value.decode('utf-8') if isinstance(value, bytes) else str(value)
                    self.txt_records[key_str] = value_str
                except UnicodeDecodeError:
                    logger.warning(f"Konnte TXT-Record nicht dekodieren: {key}={value}")
                    
            # Spezifische Eigenschaften extrahieren
            if 'am' in self.txt_records:
                self.model = self.txt_records['am']
            if 'fv' in self.txt_records:
                self.firmware_version = self.txt_records['fv']
            if 'ft' in self.txt_records:
                try:
                    self.features = int(self.txt_records['ft'], 16)
                except ValueError:
                    pass
                    
        # IP-Adressen
        self.ip_addresses = [socket.inet_ntoa(addr) for addr in service_info.addresses]
        
        # Letztes Mal gesehen aktualisieren
        self.last_seen = time.time()


class AirPlayServiceListener(ServiceListener):
    """mDNS Service-Listener für AirPlay-Geräte"""
    
    def __init__(self, device_manager):
        self.device_manager = device_manager
        self.loop = None
        
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Neuer Service entdeckt"""
        logger.info(f"AirPlay-Gerät entdeckt: {name} ({type_})")
        
        # Service-Informationen abrufen
        service_info = zc.get_service_info(type_, name)
        if service_info:
            # Sicherstellen dass wir im richtigen Event-Loop sind
            if self.loop is None:
                self.loop = self.device_manager._get_event_loop()
            
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.device_manager._handle_service_added(service_info),
                    self.loop
                )
            
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Service entfernt"""
        logger.info(f"AirPlay-Gerät entfernt: {name} ({type_})")
        
        if self.loop is None:
            self.loop = self.device_manager._get_event_loop()
            
        if self.loop:
            asyncio.run_coroutine_threadsafe(
                self.device_manager._handle_service_removed(name),
                self.loop
            )
        
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Service aktualisiert"""
        logger.debug(f"AirPlay-Gerät aktualisiert: {name} ({type_})")
        
        service_info = zc.get_service_info(type_, name)
        if service_info:
            if self.loop is None:
                self.loop = self.device_manager._get_event_loop()
                
            if self.loop:
                asyncio.run_coroutine_threadsafe(
                    self.device_manager._handle_service_updated(service_info),
                    self.loop
                )


class DeviceManager:
    """Manager für AirPlay-Geräte"""
    
    def __init__(self, config):
        self.config = config
        
        # Geräte
        self.devices = {}  # device_id -> AirPlayDevice
        self.service_name_to_device = {}  # service_name -> device_id
        
        # mDNS/Zeroconf
        self.zeroconf = None
        self.service_browser = None
        self.service_listener = None
        
        # Event Loop Referenz
        self.event_loop = None
        
        # Discovery-Einstellungen
        self.auto_discovery = config.get('devices.auto_discovery', True)
        self.discovery_timeout = config.get('devices.discovery_timeout', 30)
        
        # Callbacks
        self.device_callbacks = {
            'added': [],
            'removed': [],
            'updated': [],
            'status_changed': []
        }
        
        # Manual konfigurierte Geräte
        self.manual_devices = config.get('devices.manual_devices', [])
        
        # Discovery-Task
        self.discovery_task = None
        self.monitoring_task = None
        
    def _get_event_loop(self):
        """Gibt den Event-Loop zurück"""
        if self.event_loop is None:
            try:
                self.event_loop = asyncio.get_running_loop()
            except RuntimeError:
                pass
        return self.event_loop
        
    async def initialize(self):
        """Initialisiert den Device Manager"""
        logger.info("Initialisiere Device Manager...")
        
        # Event Loop speichern
        self.event_loop = asyncio.get_running_loop()
        
        # Zeroconf initialisieren mit IPv4-only für bessere Kompatibilität
        if self.auto_discovery:
            try:
                # IPv4-only Modus für LXC/Container Kompatibilität
                self.zeroconf = Zeroconf(interfaces=["0.0.0.0"])
                self.service_listener = AirPlayServiceListener(self)
                logger.info("Zeroconf initialisiert (IPv4-only Modus)")
            except Exception as e:
                logger.error(f"Fehler beim Initialisieren von Zeroconf: {e}")
                logger.info("Versuche Zeroconf ohne spezifisches Interface...")
                try:
                    self.zeroconf = Zeroconf()
                    self.service_listener = AirPlayServiceListener(self)
                    logger.info("Zeroconf initialisiert (Auto-Modus)")
                except Exception as e2:
                    logger.error(f"Zeroconf Initialisierung fehlgeschlagen: {e2}")
                    self.auto_discovery = False
            
        # Manuell konfigurierte Geräte hinzufügen
        await self._load_manual_devices()
        
        logger.info(f"Device Manager initialisiert - Auto-Discovery: {self.auto_discovery}")
        
    async def start(self):
        """Startet den Device Manager"""
        logger.info("Starte Device Manager...")
        
        # mDNS Discovery starten
        if self.auto_discovery and self.zeroconf:
            await self._start_discovery()
            
        # Monitoring-Task starten
        self.monitoring_task = asyncio.create_task(self._monitoring_loop())
        
        logger.info("Device Manager gestartet")
        
    async def stop(self):
        """Stoppt den Device Manager"""
        logger.info("Stoppe Device Manager...")
        
        # Discovery stoppen
        if self.service_browser:
            self.service_browser.cancel()
            
        # Zeroconf schließen
        if self.zeroconf:
            self.zeroconf.close()
            
        # Tasks stoppen
        if self.discovery_task:
            self.discovery_task.cancel()
            try:
                await self.discovery_task
            except asyncio.CancelledError:
                pass
                
        if self.monitoring_task:
            self.monitoring_task.cancel()
            try:
                await self.monitoring_task
            except asyncio.CancelledError:
                pass
                
        logger.info("Device Manager gestoppt")
        
    async def get_devices(self, filter_available: bool = True) -> List[AirPlayDevice]:
        """Gibt alle Geräte zurück"""
        devices = list(self.devices.values())
        
        if filter_available:
            devices = [device for device in devices if device.is_available()]
            
        return devices
        
    async def get_device(self, device_id: str) -> Optional[AirPlayDevice]:
        """Gibt ein spezifisches Gerät zurück"""
        return self.devices.get(device_id)
        
    async def add_manual_device(self, device_info: Dict) -> Optional[AirPlayDevice]:
        """Fügt ein manuell konfiguriertes Gerät hinzu"""
        try:
            device_id = f"manual_{device_info['host']}_{device_info.get('port', 7000)}"
            
            device = AirPlayDevice(
                device_id=device_id,
                name=device_info['name'],
                host=device_info['host'],
                port=device_info.get('port', 7000),
                device_type=DeviceType.UNKNOWN
            )
            
            # Gerät testen
            if await self._test_device_connection(device):
                self.devices[device_id] = device
                await self._notify_device_callbacks('added', device)
                
                logger.info(f"Manuelles Gerät hinzugefügt: {device.name}")
                return device
            else:
                logger.warning(f"Manuelles Gerät nicht erreichbar: {device.name}")
                return None
                
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen des manuellen Geräts: {e}")
            return None
            
    async def remove_device(self, device_id: str):
        """Entfernt ein Gerät"""
        if device_id not in self.devices:
            return
            
        device = self.devices[device_id]
        del self.devices[device_id]
        
        # Service-Name-Mapping entfernen
        service_name_to_remove = None
        for service_name, mapped_device_id in self.service_name_to_device.items():
            if mapped_device_id == device_id:
                service_name_to_remove = service_name
                break
                
        if service_name_to_remove:
            del self.service_name_to_device[service_name_to_remove]
            
        # Callbacks benachrichtigen
        await self._notify_device_callbacks('removed', device)
        
        logger.info(f"Gerät entfernt: {device.name}")
        
    async def refresh_devices(self):
        """Aktualisiert alle Geräte"""
        logger.info("Aktualisiere alle Geräte...")
        
        # Verfügbarkeit aller Geräte prüfen
        for device in self.devices.values():
            await self._update_device_status(device)
            
    def register_callback(self, event_type: str, callback: Callable[[AirPlayDevice], None]):
        """Registriert einen Callback für Geräteereignisse"""
        if event_type in self.device_callbacks:
            self.device_callbacks[event_type].append(callback)
            logger.debug(f"Callback für {event_type} registriert")
            
    def unregister_callback(self, event_type: str, callback: Callable[[AirPlayDevice], None]):
        """Deregistriert einen Callback"""
        if event_type in self.device_callbacks and callback in self.device_callbacks[event_type]:
            self.device_callbacks[event_type].remove(callback)
            logger.debug(f"Callback für {event_type} deregistriert")
            
    async def _start_discovery(self):
        """Startet mDNS Discovery"""
        logger.info("Starte AirPlay-Geräteerkennung...")
        
        try:
            # AirPlay-Services nach denen gesucht werden soll
            service_types = [
                "_airplay._tcp.local.",
                "_raop._tcp.local.",
                "_airport._tcp.local."
            ]
            
            # Service-Browser für jeden Typ starten
            browsers = []
            for service_type in service_types:
                browser = ServiceBrowser(
                    self.zeroconf,
                    service_type,
                    self.service_listener
                )
                browsers.append(browser)
                
            self.service_browser = browsers  # Liste von Browsern speichern
            
            logger.info(f"mDNS Discovery gestartet für {len(service_types)} Service-Typen")
            
        except Exception as e:
            logger.error(f"Fehler beim Starten der Geräteerkennung: {e}")
            raise
            
    async def _load_manual_devices(self):
        """Lädt manuell konfigurierte Geräte"""
        if not self.manual_devices:
            return
            
        logger.info(f"Lade {len(self.manual_devices)} manuell konfigurierte Geräte...")
        
        for device_info in self.manual_devices:
            if device_info.get('enabled', True):
                device = await self.add_manual_device(device_info)
                if device:
                    logger.info(f"Manuelles Gerät geladen: {device.name}")
                    
    async def _handle_service_added(self, service_info: ServiceInfo):
        """Behandelt neu entdeckte Services"""
        try:
            device = await self._create_device_from_service(service_info)
            if device:
                self.devices[device.device_id] = device
                self.service_name_to_device[service_info.name] = device.device_id
                
                await self._notify_device_callbacks('added', device)
                
                logger.info(f"Neues AirPlay-Gerät entdeckt: {device.name} ({device.host})")
                
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten des neuen Services: {e}")
            
    async def _handle_service_removed(self, service_name: str):
        """Behandelt entfernte Services"""
        try:
            if service_name in self.service_name_to_device:
                device_id = self.service_name_to_device[service_name]
                await self.remove_device(device_id)
                
        except Exception as e:
            logger.error(f"Fehler beim Entfernen des Services: {e}")
            
    async def _handle_service_updated(self, service_info: ServiceInfo):
        """Behandelt aktualisierte Services"""
        try:
            if service_info.name in self.service_name_to_device:
                device_id = self.service_name_to_device[service_info.name]
                device = self.devices.get(device_id)
                
                if device:
                    device.update_from_service_info(service_info)
                    await self._notify_device_callbacks('updated', device)
                    
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren des Services: {e}")
            
    async def _create_device_from_service(self, service_info: ServiceInfo) -> Optional[AirPlayDevice]:
        """Erstellt ein AirPlayDevice aus ServiceInfo"""
        try:
            # Grundlegende Informationen extrahieren
            if not service_info.addresses:
                logger.warning(f"Service {service_info.name} hat keine IP-Adressen")
                return None
                
            host = socket.inet_ntoa(service_info.addresses[0])
            port = service_info.port or 7000
            name = service_info.name.split('.')[0]  # Service-Name ohne Domain
            
            # Device-ID generieren
            device_id = f"mdns_{host}_{port}"
            
            # Gerätetyp ermitteln
            device_type = self._determine_device_type(service_info)
            
            # Gerät erstellen
            device = AirPlayDevice(
                device_id=device_id,
                name=name,
                host=host,
                port=port,
                device_type=device_type
            )
            
            # ServiceInfo-Daten hinzufügen
            device.update_from_service_info(service_info)
            
            # Gerät als entdeckt markieren (auch ohne Connection-Test)
            # Viele AirPlay-Geräte antworten nicht auf direkte TCP-Verbindungen
            device.status = DeviceStatus.DISCOVERED
            logger.info(f"Gerät erstellt: {name} ({host}:{port}) - Typ: {device_type.value}")
            
            return device
                
        except Exception as e:
            logger.error(f"Fehler beim Erstellen des Geräts aus Service: {e}")
            return None
            
    def _determine_device_type(self, service_info: ServiceInfo) -> DeviceType:
        """Ermittelt den Gerätetyp aus ServiceInfo"""
        service_type = service_info.type
        
        if "_airplay._tcp" in service_type:
            # Prüfen ob Video unterstützt wird
            if service_info.properties:
                features = service_info.properties.get(b'ft', b'0')
                try:
                    features_int = int(features.decode('utf-8'), 16)
                    if features_int & 0x02:  # Video-Flag
                        return DeviceType.AIRPLAY_VIDEO
                except:
                    pass
            return DeviceType.AIRPLAY_AUDIO
            
        elif "_raop._tcp" in service_type:
            return DeviceType.AIRPLAY_AUDIO
            
        elif "_airport._tcp" in service_type:
            return DeviceType.AIRPORT_EXPRESS
            
        return DeviceType.UNKNOWN
        
    async def _test_device_connection(self, device: AirPlayDevice) -> bool:
        """Testet die Verbindung zu einem Gerät"""
        try:
            # Einfacher TCP-Verbindungstest
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(device.host, device.port),
                timeout=5.0
            )
            
            writer.close()
            await writer.wait_closed()
            
            return True
            
        except Exception as e:
            logger.debug(f"Verbindungstest fehlgeschlagen für {device.name}: {e}")
            return False
            
    async def _update_device_status(self, device: AirPlayDevice):
        """Aktualisiert den Status eines Geräts"""
        old_status = device.status
        
        if await self._test_device_connection(device):
            if device.status == DeviceStatus.DISCONNECTED:
                device.status = DeviceStatus.DISCOVERED
                device.last_seen = time.time()
        else:
            if device.status != DeviceStatus.ERROR:
                device.status = DeviceStatus.DISCONNECTED
                
        # Status-Change-Callback falls sich Status geändert hat
        if old_status != device.status:
            await self._notify_device_callbacks('status_changed', device)
            
    async def _monitoring_loop(self):
        """Überwachungsschleife für Geräte"""
        logger.info("Device-Monitoring gestartet")
        
        while True:
            try:
                await asyncio.sleep(30.0)  # Alle 30 Sekunden
                
                # Status aller Geräte überprüfen
                for device in list(self.devices.values()):
                    await self._update_device_status(device)
                    
                    # Veraltete Geräte entfernen (nicht gesehen seit 300 Sekunden)
                    if (device.last_seen and 
                        (time.time() - device.last_seen) > 300.0 and
                        device.device_id.startswith('mdns_')):
                        await self.remove_device(device.device_id)
                        
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Fehler im Device-Monitoring: {e}")
                await asyncio.sleep(5.0)
                
        logger.info("Device-Monitoring beendet")
        
    async def _notify_device_callbacks(self, event_type: str, device: AirPlayDevice):
        """Benachrichtigt alle registrierten Callbacks"""
        callbacks = self.device_callbacks.get(event_type, [])
        
        for callback in callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(device)
                else:
                    callback(device)
            except Exception as e:
                logger.error(f"Fehler in Device-Callback ({event_type}): {e}")
                
    def get_stats(self) -> Dict:
        """Gibt Statistiken zurück"""
        available_devices = [d for d in self.devices.values() if d.is_available()]
        
        return {
            'total_devices': len(self.devices),
            'available_devices': len(available_devices),
            'auto_discovery': self.auto_discovery,
            'manual_devices': len([d for d in self.devices.values() 
                                 if d.device_id.startswith('manual_')]),
            'mdns_devices': len([d for d in self.devices.values() 
                               if d.device_id.startswith('mdns_')]),
            'device_types': {
                device_type.value: len([d for d in available_devices 
                                      if d.device_type == device_type])
                for device_type in DeviceType
            }
        }