#!/usr/bin/env python3
"""
Test-Script für die automatische AirPlay-Geräteerkennung

Dieses Script testet die mDNS-Discovery und zeigt alle gefundenen AirPlay-Geräte an.
Nützlich zum Debuggen von Netzwerk- und Discovery-Problemen.
"""

import sys
import time
import logging
from zeroconf import ServiceBrowser, ServiceListener, Zeroconf, ServiceInfo
import socket

# Logging konfigurieren
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class AirPlayDiscoveryListener(ServiceListener):
    """Listener für AirPlay-Discovery"""
    
    def __init__(self):
        self.devices = {}
        
    def add_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Neues Gerät gefunden"""
        logger.info(f"🔍 Gerät gefunden: {name}")
        
        # Service-Informationen abrufen
        info = zc.get_service_info(type_, name)
        if info:
            self.print_device_info(name, info)
            self.devices[name] = info
            
    def remove_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Gerät entfernt"""
        logger.info(f"❌ Gerät entfernt: {name}")
        if name in self.devices:
            del self.devices[name]
            
    def update_service(self, zc: Zeroconf, type_: str, name: str) -> None:
        """Gerät aktualisiert"""
        logger.debug(f"🔄 Gerät aktualisiert: {name}")
        
    def print_device_info(self, name: str, info: ServiceInfo):
        """Gibt Geräte-Informationen aus"""
        print("\n" + "="*70)
        print(f"📱 Gerät: {name}")
        print("="*70)
        
        # IP-Adressen
        if info.addresses:
            print(f"📍 IP-Adressen:")
            for addr in info.addresses:
                ip = socket.inet_ntoa(addr)
                print(f"   - {ip}")
        else:
            print("   ⚠️  Keine IP-Adressen gefunden")
            
        # Port
        print(f"🔌 Port: {info.port}")
        
        # Server/Hostname
        if info.server:
            print(f"🖥️  Server: {info.server}")
            
        # Eigenschaften
        if info.properties:
            print(f"\n📋 Eigenschaften:")
            for key, value in info.properties.items():
                try:
                    key_str = key.decode('utf-8') if isinstance(key, bytes) else key
                    value_str = value.decode('utf-8') if isinstance(value, bytes) else str(value)
                    print(f"   {key_str}: {value_str}")
                except:
                    print(f"   {key}: {value}")
                    
        # AirPlay-spezifische Infos
        if info.properties:
            # Modell
            if b'am' in info.properties:
                model = info.properties[b'am'].decode('utf-8')
                print(f"\n🎵 Modell: {model}")
                
            # Features
            if b'ft' in info.properties:
                features_hex = info.properties[b'ft'].decode('utf-8')
                try:
                    features = int(features_hex, 16)
                    print(f"✨ Features: 0x{features:X}")
                    print(f"   - Audio: {'✅' if features & 0x01 else '❌'}")
                    print(f"   - Video: {'✅' if features & 0x02 else '❌'}")
                except:
                    pass
                    
            # Firmware
            if b'fv' in info.properties:
                firmware = info.properties[b'fv'].decode('utf-8')
                print(f"💾 Firmware: {firmware}")
                
        print("="*70)


def main():
    """Hauptfunktion"""
    print("""
╔════════════════════════════════════════════════════════════════════╗
║           AirPlay Multiroom Server - Discovery Test               ║
╚════════════════════════════════════════════════════════════════════╝
    """)
    
    logger.info("Starte AirPlay-Geräteerkennung...")
    logger.info("Drücke Ctrl+C zum Beenden\n")
    
    # Service-Typen für AirPlay
    service_types = [
        "_airplay._tcp.local.",
        "_raop._tcp.local.",
        "_airport._tcp.local."
    ]
    
    listener = AirPlayDiscoveryListener()
    
    try:
        # Versuche IPv4-only Modus (für LXC-Container)
        logger.info("Initialisiere Zeroconf (IPv4-only)...")
        zeroconf = Zeroconf(interfaces=["0.0.0.0"])
        mode = "IPv4-only"
    except Exception as e:
        logger.warning(f"IPv4-only Modus fehlgeschlagen: {e}")
        logger.info("Versuche Auto-Modus...")
        try:
            zeroconf = Zeroconf()
            mode = "Auto"
        except Exception as e2:
            logger.error(f"Zeroconf Initialisierung fehlgeschlagen: {e2}")
            logger.error("Stelle sicher dass avahi-daemon läuft: systemctl status avahi-daemon")
            return 1
            
    logger.info(f"Zeroconf initialisiert ({mode} Modus)\n")
    
    # Browser für jeden Service-Typ starten
    browsers = []
    for service_type in service_types:
        logger.info(f"Suche nach: {service_type}")
        browser = ServiceBrowser(zeroconf, service_type, listener)
        browsers.append(browser)
        
    print("\n⏳ Warte auf Geräte (30 Sekunden)...\n")
    
    try:
        # 30 Sekunden warten
        for i in range(30):
            time.sleep(1)
            if i % 10 == 9:
                count = len(listener.devices)
                print(f"   {i+1}s - {count} Gerät(e) gefunden")
                
    except KeyboardInterrupt:
        logger.info("\nAbbruch durch Benutzer")
        
    finally:
        # Zusammenfassung
        print("\n" + "="*70)
        print(f"📊 Zusammenfassung: {len(listener.devices)} Gerät(e) gefunden")
        print("="*70)
        
        if listener.devices:
            print("\n📱 Gefundene Geräte:")
            for name, info in listener.devices.items():
                if info.addresses:
                    ip = socket.inet_ntoa(info.addresses[0])
                    print(f"   • {name.split('.')[0]}: {ip}:{info.port}")
                else:
                    print(f"   • {name.split('.')[0]}: (keine IP)")
                    
            print("\n💡 Diese Geräte sollten automatisch im Web-Interface erscheinen.")
            print("   Falls nicht, prüfe die Logs: journalctl -u airplay-multiroom-server -f")
        else:
            print("\n⚠️  Keine Geräte gefunden. Mögliche Ursachen:")
            print("   1. Keine AirPlay-Geräte im Netzwerk")
            print("   2. Multicast-Routing blockiert (bei LXC/Docker)")
            print("   3. Firewall blockiert mDNS (Port 5353 UDP)")
            print("   4. avahi-daemon läuft nicht")
            print("\n🔧 Debug-Befehle:")
            print("   - avahi-browse -t _raop._tcp")
            print("   - systemctl status avahi-daemon")
            print("   - ip route show (für Multicast-Route)")
            
        print("")
        
        # Cleanup
        for browser in browsers:
            browser.cancel()
        zeroconf.close()
        
    return 0


if __name__ == '__main__':
    sys.exit(main())
