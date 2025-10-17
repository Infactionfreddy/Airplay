# IPv6 für zeroconf deaktivieren - Config anpassen
cat >> /etc/airplay-multiroom/config.yaml << 'EOF'

# Netzwerk-Einstellungen
network:
  ipv6_enabled: false
  bind_address: "0.0.0.0"
EOF

# Prüfen ob IPv6 im Container verfügbar ist
ip -6 addr show

# Falls kein IPv6, auch im System deaktivieren
sysctl net.ipv6.conf.all.disable_ipv6=1

# Service neu starten
systemctl start airplay-multiroom-server
sleep 5
systemctl status airplay-multiroom-server

# Logs prüfen
journalctl -u airplay-multiroom-server -n 30 --no-pager"""
Hauptmodul für den AirPlay Multiroom Server
"""
import asyncio
import logging
import signal
import sys
from pathlib import Path

from .config_manager import ConfigManager
from .airplay_receiver import AirPlayReceiver
from .device_manager import DeviceManager
from .audio_pipeline import AudioPipeline
from .multiroom_coordinator import MultiroomCoordinator
from .web_interface import WebInterface

logger = logging.getLogger(__name__)


class AirPlayMultiroomServer:
    """Hauptklasse für den AirPlay Multiroom Server"""
    
    def __init__(self, config_path: str = None):
        self.config = ConfigManager(config_path)
        self.running = False
        
        # Komponenten
        self.airplay_receiver = None
        self.device_manager = None
        self.audio_pipeline = None
        self.multiroom_coordinator = None
        self.web_interface = None
        
        # Event-Loop
        self.loop = None
        
    async def initialize(self):
        """Initialisiert alle Komponenten"""
        logger.info("Initialisiere AirPlay Multiroom Server...")
        
        # Audio-Pipeline erstellen
        self.audio_pipeline = AudioPipeline(self.config)
        await self.audio_pipeline.initialize()
        
        # Geräte-Manager erstellen
        self.device_manager = DeviceManager(self.config)
        await self.device_manager.initialize()
        
        # Multiroom-Koordinator erstellen
        self.multiroom_coordinator = MultiroomCoordinator(
            self.config,
            self.audio_pipeline,
            self.device_manager
        )
        await self.multiroom_coordinator.initialize()
        
        # AirPlay-Empfänger erstellen
        self.airplay_receiver = AirPlayReceiver(
            self.config,
            self.multiroom_coordinator
        )
        await self.airplay_receiver.initialize()
        
        # Web-Interface (optional)
        if self.config.get('web.enabled', True):
            self.web_interface = WebInterface(
                self.config,
                self.device_manager,
                self.multiroom_coordinator
            )
            await self.web_interface.initialize()
            
        logger.info("Alle Komponenten erfolgreich initialisiert")
        
    async def start(self):
        """Startet den Server"""
        if self.running:
            return
            
        logger.info("Starte AirPlay Multiroom Server...")
        self.running = True
        
        try:
            # Alle Komponenten starten
            await self.device_manager.start()
            await self.audio_pipeline.start()
            await self.multiroom_coordinator.start()
            await self.airplay_receiver.start()
            
            if self.web_interface:
                await self.web_interface.start()
                
            logger.info(f"Server gestartet - AirPlay verfügbar auf Port {self.config.get('airplay.port')}")
            if self.web_interface:
                logger.info(f"Web-Interface verfügbar auf http://0.0.0.0:{self.config.get('web.port')}")
                
        except Exception as e:
            logger.error(f"Fehler beim Starten des Servers: {e}")
            await self.stop()
            raise
            
    async def stop(self):
        """Stoppt den Server"""
        if not self.running:
            return
            
        logger.info("Stoppe AirPlay Multiroom Server...")
        self.running = False
        
        # Alle Komponenten stoppen (in umgekehrter Reihenfolge)
        if self.web_interface:
            await self.web_interface.stop()
            
        if self.airplay_receiver:
            await self.airplay_receiver.stop()
            
        if self.multiroom_coordinator:
            await self.multiroom_coordinator.stop()
            
        if self.audio_pipeline:
            await self.audio_pipeline.stop()
            
        if self.device_manager:
            await self.device_manager.stop()
            
        logger.info("Server gestoppt")
        
    async def run(self):
        """Hauptausführungsschleife"""
        await self.initialize()
        await self.start()
        
        try:
            # Warten bis gestoppt
            while self.running:
                await asyncio.sleep(1)
        except KeyboardInterrupt:
            logger.info("Shutdown durch Benutzer")
        except Exception as e:
            logger.error(f"Unerwarteter Fehler: {e}")
        finally:
            await self.stop()


def setup_logging(config):
    """Konfiguriert das Logging-System"""
    log_level = config.get('logging.level', 'INFO').upper()
    log_file = config.get('logging.file')
    
    # Logging-Format
    formatter = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Root-Logger konfigurieren
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, log_level))
    
    # Console-Handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    root_logger.addHandler(console_handler)
    
    # File-Handler (falls konfiguriert)
    if log_file:
        try:
            # Log-Verzeichnis erstellen falls nötig
            log_path = Path(log_file)
            log_path.parent.mkdir(parents=True, exist_ok=True)
            
            file_handler = logging.FileHandler(log_file)
            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)
        except Exception as e:
            logger.warning(f"Konnte Log-Datei nicht erstellen: {e}")


def signal_handler(server):
    """Signal-Handler für graceful shutdown"""
    def handler(signum, frame):
        logger.info(f"Signal {signum} erhalten - Server wird gestoppt...")
        if server.loop:
            server.loop.create_task(server.stop())
    return handler


async def main():
    """Hauptfunktion"""
    import argparse
    
    parser = argparse.ArgumentParser(description="AirPlay Multiroom Server")
    parser.add_argument(
        '--config', '-c',
        help='Pfad zur Konfigurationsdatei',
        default='/etc/airplay-multiroom/config.yaml'
    )
    parser.add_argument(
        '--debug', '-d',
        action='store_true',
        help='Debug-Modus aktivieren'
    )
    
    args = parser.parse_args()
    
    # Server erstellen
    server = AirPlayMultiroomServer(args.config)
    
    # Debug-Modus
    if args.debug:
        server.config.set('logging.level', 'DEBUG')
        server.config.set('server.debug', True)
    
    # Logging einrichten
    setup_logging(server.config)
    
    # Event-Loop erhalten
    server.loop = asyncio.get_event_loop()
    
    # Signal-Handler registrieren
    for sig in [signal.SIGINT, signal.SIGTERM]:
        signal.signal(sig, signal_handler(server))
    
    try:
        await server.run()
    except Exception as e:
        logger.error(f"Kritischer Fehler: {e}")
        sys.exit(1)


if __name__ == '__main__':
    asyncio.run(main())