"""
Multiroom-Koordinator für synchronisierte AirPlay-Wiedergabe
"""
import asyncio
import logging
import time
import struct
from typing import Dict, List, Optional, Set
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class PlaybackState(Enum):
    """Status der Wiedergabe"""
    STOPPED = "stopped"
    PLAYING = "playing" 
    PAUSED = "paused"
    BUFFERING = "buffering"


@dataclass
class DeviceDelay:
    """Gerätespezifische Verzögerungseinstellungen"""
    device_id: str
    base_delay: float  # Basis-Verzögerung in Sekunden
    network_delay: float  # Geschätzte Netzwerk-Verzögerung
    calibration_offset: float  # Kalibrierungs-Offset
    
    @property
    def total_delay(self) -> float:
        return self.base_delay + self.network_delay + self.calibration_offset


@dataclass
class SyncFrame:
    """Synchronisations-Frame für Multiroom-Wiedergabe"""
    timestamp: float
    sequence_number: int
    audio_data: bytes
    sample_count: int
    
    def to_bytes(self) -> bytes:
        """Konvertiert zu Binärdaten für Übertragung"""
        header = struct.pack(
            '!dII',  # ! = network byte order, d = double, I = uint32
            self.timestamp,
            self.sequence_number,
            len(self.audio_data)
        )
        return header + self.audio_data
        
    @classmethod
    def from_bytes(cls, data: bytes) -> 'SyncFrame':
        """Erstellt SyncFrame aus Binärdaten"""
        if len(data) < 16:  # Header-Größe
            raise ValueError("Unvollständige SyncFrame-Daten")
            
        timestamp, seq_num, audio_len = struct.unpack('!dII', data[:16])
        audio_data = data[16:16+audio_len]
        
        return cls(
            timestamp=timestamp,
            sequence_number=seq_num,
            audio_data=audio_data,
            sample_count=audio_len // 4  # Annahme: 16-bit Stereo
        )


class MultiroomCoordinator:
    """Koordiniert synchronisierte Wiedergabe auf mehreren AirPlay-Geräten"""
    
    def __init__(self, config, audio_pipeline, device_manager):
        self.config = config
        self.audio_pipeline = audio_pipeline
        self.device_manager = device_manager
        
        # Synchronisations-Einstellungen
        self.global_delay = config.get('synchronization.global_delay', 0.5)
        self.sync_tolerance = config.get('synchronization.sync_tolerance', 50) / 1000.0  # ms zu s
        self.sync_algorithm = config.get('synchronization.sync_algorithm', 'advanced')
        
        # Geräteverzögerungen
        self.device_delays = {}  # device_id -> DeviceDelay
        self._load_device_delays()
        
        # Wiedergabe-Status
        self.playback_state = PlaybackState.STOPPED
        self.current_stream = None
        
        # Synchronisation
        self.master_clock = None
        self.sequence_counter = 0
        self.sync_buffer = {}  # device_id -> List[SyncFrame]
        
        # Aktive Geräte
        self.active_devices = set()  # Set[device_id]
        self.device_connections = {}  # device_id -> connection_info
        
        # Timing
        self.playback_start_time = None
        self.last_sync_check = 0
        
        # Statistiken
        self.stats = {
            'frames_sent': 0,
            'sync_corrections': 0,
            'buffer_underruns': 0,
            'devices_connected': 0
        }
        
        # Tasks
        self.sync_task = None
        self.cleanup_task = None
        
    async def initialize(self):
        """Initialisiert den Multiroom-Koordinator"""
        logger.info("Initialisiere Multiroom-Koordinator...")
        
        # Audio-Pipeline-Callback registrieren
        self.audio_pipeline.register_output_callback(
            'multiroom_coordinator',
            self._handle_audio_data
        )
        
        logger.info(f"Multiroom-Koordinator initialisiert - Algorithmus: {self.sync_algorithm}")
        
    async def start(self):
        """Startet den Koordinator"""
        logger.info("Starte Multiroom-Koordinator...")
        
        # Synchronisations-Task starten
        self.sync_task = asyncio.create_task(self._synchronization_loop())
        
        # Cleanup-Task starten
        self.cleanup_task = asyncio.create_task(self._cleanup_loop())
        
        logger.info("Multiroom-Koordinator gestartet")
        
    async def stop(self):
        """Stoppt den Koordinator"""
        logger.info("Stoppe Multiroom-Koordinator...")
        
        # Wiedergabe stoppen
        await self.stop_playback()
        
        # Tasks stoppen
        if self.sync_task:
            self.sync_task.cancel()
            try:
                await self.sync_task
            except asyncio.CancelledError:
                pass
                
        if self.cleanup_task:
            self.cleanup_task.cancel()
            try:
                await self.cleanup_task
            except asyncio.CancelledError:
                pass
                
        # Audio-Pipeline-Callback entfernen
        self.audio_pipeline.unregister_output_callback('multiroom_coordinator')
        
        logger.info("Multiroom-Koordinator gestoppt")
        
    async def start_audio_stream(self, stream_id: str, stream_info: Dict):
        """Startet einen neuen Audio-Stream"""
        logger.info(f"Starte Audio-Stream: {stream_id}")
        
        try:
            # Stream zur Audio-Pipeline hinzufügen
            stream = self.audio_pipeline.add_stream(stream_id, stream_info)
            
            # Als aktiven Stream setzen
            self.audio_pipeline.set_active_stream(stream_id)
            self.current_stream = stream_id
            
            # Wiedergabe vorbereiten
            await self._prepare_playback()
            
            # Wiedergabe starten
            await self.start_playback()
            
            logger.info(f"Audio-Stream {stream_id} gestartet")
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des Audio-Streams {stream_id}: {e}")
            raise
            
    async def stop_audio_stream(self, stream_id: str):
        """Stoppt einen Audio-Stream"""
        logger.info(f"Stoppe Audio-Stream: {stream_id}")
        
        try:
            # Wiedergabe stoppen falls dies der aktive Stream ist
            if self.current_stream == stream_id:
                await self.stop_playback()
                self.current_stream = None
                
            # Stream aus Audio-Pipeline entfernen
            self.audio_pipeline.remove_stream(stream_id)
            
            logger.info(f"Audio-Stream {stream_id} gestoppt")
            
        except Exception as e:
            logger.error(f"Fehler beim Stoppen des Audio-Streams {stream_id}: {e}")
            
    async def flush_audio_buffer(self, stream_id: str):
        """Leert den Audio-Puffer für einen Stream"""
        logger.debug(f"Leere Audio-Puffer für Stream: {stream_id}")
        
        # Stream-Puffer leeren
        self.audio_pipeline.flush_all_streams()
        
        # Sync-Puffer leeren
        for device_id in self.active_devices:
            if device_id in self.sync_buffer:
                self.sync_buffer[device_id].clear()
                
        # Sequence-Counter zurücksetzen
        self.sequence_counter = 0
        
    async def add_device(self, device_id: str, device_info: Dict):
        """Fügt ein Gerät zur Multiroom-Gruppe hinzu"""
        logger.info(f"Füge Gerät hinzu: {device_id}")
        
        try:
            # Geräteverzögerung laden/erstellen
            if device_id not in self.device_delays:
                base_delay = self.config.get(f'synchronization.device_delays.{device_id}', 0.0)
                self.device_delays[device_id] = DeviceDelay(
                    device_id=device_id,
                    base_delay=base_delay,
                    network_delay=0.0,
                    calibration_offset=0.0
                )
                
            # Verbindung zu Gerät herstellen
            connection = await self._connect_to_device(device_id, device_info)
            self.device_connections[device_id] = connection
            
            # Zu aktiven Geräten hinzufügen
            self.active_devices.add(device_id)
            
            # Sync-Puffer initialisieren
            self.sync_buffer[device_id] = []
            
            # Statistiken aktualisieren
            self.stats['devices_connected'] = len(self.active_devices)
            
            logger.info(f"Gerät {device_id} hinzugefügt - {len(self.active_devices)} Geräte aktiv")
            
        except Exception as e:
            logger.error(f"Fehler beim Hinzufügen von Gerät {device_id}: {e}")
            raise
            
    async def remove_device(self, device_id: str):
        """Entfernt ein Gerät aus der Multiroom-Gruppe"""
        logger.info(f"Entferne Gerät: {device_id}")
        
        try:
            # Aus aktiven Geräten entfernen
            self.active_devices.discard(device_id)
            
            # Verbindung schließen
            if device_id in self.device_connections:
                await self._disconnect_from_device(device_id)
                del self.device_connections[device_id]
                
            # Sync-Puffer leeren
            if device_id in self.sync_buffer:
                del self.sync_buffer[device_id]
                
            # Statistiken aktualisieren
            self.stats['devices_connected'] = len(self.active_devices)
            
            logger.info(f"Gerät {device_id} entfernt - {len(self.active_devices)} Geräte verbleibend")
            
        except Exception as e:
            logger.error(f"Fehler beim Entfernen von Gerät {device_id}: {e}")
            
    async def start_playback(self):
        """Startet die synchronisierte Wiedergabe"""
        if self.playback_state == PlaybackState.PLAYING:
            return
            
        logger.info("Starte synchronisierte Wiedergabe...")
        
        # Master-Clock setzen
        self.master_clock = time.time() + self.global_delay
        self.playback_start_time = self.master_clock
        
        # Alle Geräte über Wiedergabe-Start informieren
        await self._broadcast_playback_command('start', self.master_clock)
        
        self.playback_state = PlaybackState.PLAYING
        
        logger.info(f"Synchronisierte Wiedergabe gestartet für {len(self.active_devices)} Geräte")
        
    async def stop_playback(self):
        """Stoppt die synchronisierte Wiedergabe"""
        if self.playback_state == PlaybackState.STOPPED:
            return
            
        logger.info("Stoppe synchronisierte Wiedergabe...")
        
        # Alle Geräte über Wiedergabe-Stopp informieren
        await self._broadcast_playback_command('stop')
        
        self.playback_state = PlaybackState.STOPPED
        self.master_clock = None
        self.playback_start_time = None
        
        # Puffer leeren
        for device_buffers in self.sync_buffer.values():
            device_buffers.clear()
            
        logger.info("Synchronisierte Wiedergabe gestoppt")
        
    def _handle_audio_data(self, audio_data: bytes):
        """Behandelt eingehende Audio-Daten von der Pipeline"""
        if self.playback_state != PlaybackState.PLAYING or not self.active_devices:
            return
            
        try:
            # Aktueller Zeitstempel
            current_time = time.time()
            
            # SyncFrame erstellen
            sync_frame = SyncFrame(
                timestamp=current_time,
                sequence_number=self.sequence_counter,
                audio_data=audio_data,
                sample_count=len(audio_data) // 4  # Annahme: 16-bit Stereo
            )
            
            self.sequence_counter += 1
            
            # An alle aktiven Geräte senden (mit entsprechenden Verzögerungen)
            asyncio.create_task(self._distribute_sync_frame(sync_frame))
            
            self.stats['frames_sent'] += 1
            
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten von Audio-Daten: {e}")
            
    async def _distribute_sync_frame(self, sync_frame: SyncFrame):
        """Verteilt ein SyncFrame an alle aktiven Geräte"""
        tasks = []
        
        for device_id in self.active_devices:
            if device_id in self.device_connections:
                # Gerätespezifische Verzögerung anwenden
                delay = self.device_delays.get(device_id)
                if delay:
                    adjusted_frame = SyncFrame(
                        timestamp=sync_frame.timestamp + delay.total_delay,
                        sequence_number=sync_frame.sequence_number,
                        audio_data=sync_frame.audio_data,
                        sample_count=sync_frame.sample_count
                    )
                else:
                    adjusted_frame = sync_frame
                    
                # Asynchron an Gerät senden
                task = asyncio.create_task(
                    self._send_frame_to_device(device_id, adjusted_frame)
                )
                tasks.append(task)
                
        # Warten auf alle Sendungen
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def _send_frame_to_device(self, device_id: str, sync_frame: SyncFrame):
        """Sendet ein SyncFrame an ein spezifisches Gerät"""
        try:
            connection = self.device_connections.get(device_id)
            if not connection:
                logger.warning(f"Keine Verbindung zu Gerät {device_id}")
                return
                
            # Frame-Daten serialisieren
            frame_data = sync_frame.to_bytes()
            
            # An Gerät senden (Implementation abhängig von Gerätetyp)
            await self._send_data_to_device(device_id, frame_data)
            
        except Exception as e:
            logger.error(f"Fehler beim Senden an Gerät {device_id}: {e}")
            # Gerät als problematisch markieren
            await self._handle_device_error(device_id, e)
            
    async def _synchronization_loop(self):
        """Haupt-Synchronisationsschleife"""
        logger.info("Synchronisations-Loop gestartet")
        
        while True:
            try:
                await asyncio.sleep(0.1)  # 100ms Intervall
                
                if self.playback_state == PlaybackState.PLAYING:
                    await self._check_synchronization()
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Fehler in Synchronisations-Loop: {e}")
                await asyncio.sleep(1.0)
                
        logger.info("Synchronisations-Loop beendet")
        
    async def _check_synchronization(self):
        """Überprüft und korrigiert die Synchronisation"""
        current_time = time.time()
        
        # Nur alle 5 Sekunden prüfen
        if current_time - self.last_sync_check < 5.0:
            return
            
        self.last_sync_check = current_time
        
        if self.sync_algorithm == 'advanced':
            await self._advanced_sync_check()
        else:
            await self._simple_sync_check()
            
    async def _advanced_sync_check(self):
        """Erweiterte Synchronisationsprüfung mit Latenz-Messung"""
        # TODO: Implementiere erweiterte Synchronisation
        # - Ping-Zeiten zu Geräten messen
        # - Buffer-Füllstände abfragen
        # - Dynamische Verzögerungsanpassung
        pass
        
    async def _simple_sync_check(self):
        """Einfache Synchronisationsprüfung"""
        # TODO: Implementiere einfache Synchronisation
        # - Grundlegende Timing-Überprüfung
        # - Grobe Verzögerungskorrektur
        pass
        
    async def _cleanup_loop(self):
        """Cleanup-Schleife für alte Puffer und Verbindungen"""
        logger.info("Cleanup-Loop gestartet")
        
        while True:
            try:
                await asyncio.sleep(30.0)  # Alle 30 Sekunden
                
                # Alte Frames aus Sync-Puffern entfernen
                current_time = time.time()
                for device_id, frames in self.sync_buffer.items():
                    # Frames älter als 10 Sekunden entfernen
                    self.sync_buffer[device_id] = [
                        frame for frame in frames
                        if current_time - frame.timestamp < 10.0
                    ]
                    
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Fehler in Cleanup-Loop: {e}")
                
        logger.info("Cleanup-Loop beendet")
        
    async def _prepare_playback(self):
        """Bereitet die Wiedergabe vor"""
        # Puffer leeren
        for device_buffers in self.sync_buffer.values():
            device_buffers.clear()
            
        # Sequence-Counter zurücksetzen
        self.sequence_counter = 0
        
    async def _broadcast_playback_command(self, command: str, timestamp: Optional[float] = None):
        """Sendet Wiedergabe-Kommando an alle Geräte"""
        tasks = []
        
        for device_id in self.active_devices:
            task = asyncio.create_task(
                self._send_playback_command(device_id, command, timestamp)
            )
            tasks.append(task)
            
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
            
    async def _send_playback_command(self, device_id: str, command: str, timestamp: Optional[float] = None):
        """Sendet Wiedergabe-Kommando an ein Gerät"""
        # TODO: Implementiere gerätespezifische Kommando-Übertragung
        logger.debug(f"Sende {command} an {device_id} (timestamp: {timestamp})")
        
    async def _connect_to_device(self, device_id: str, device_info: Dict):
        """Stellt Verbindung zu einem Gerät her"""
        # TODO: Implementiere gerätespezifische Verbindung
        logger.debug(f"Verbinde mit Gerät {device_id}: {device_info}")
        return {'connected': True, 'device_info': device_info}
        
    async def _disconnect_from_device(self, device_id: str):
        """Trennt Verbindung zu einem Gerät"""
        # TODO: Implementiere gerätespezifische Trennung
        logger.debug(f"Trenne Verbindung zu Gerät {device_id}")
        
    async def _send_data_to_device(self, device_id: str, data: bytes):
        """Sendet Daten an ein Gerät"""
        # TODO: Implementiere gerätespezifische Datenübertragung
        logger.debug(f"Sende {len(data)} Bytes an {device_id}")
        
    async def _handle_device_error(self, device_id: str, error: Exception):
        """Behandelt Gerätefehler"""
        logger.warning(f"Gerätefehler {device_id}: {error}")
        
        # TODO: Implementiere Fehlerbehandlung
        # - Gerät temporär deaktivieren
        # - Wiederverbindung versuchen
        # - Benutzer informieren
        
    def _load_device_delays(self):
        """Lädt Geräteverzögerungen aus der Konfiguration"""
        device_delays_config = self.config.get('synchronization.device_delays', {})
        
        for device_id, delay_value in device_delays_config.items():
            self.device_delays[device_id] = DeviceDelay(
                device_id=device_id,
                base_delay=float(delay_value),
                network_delay=0.0,
                calibration_offset=0.0
            )
            
        logger.info(f"Geräteverzögerungen geladen: {len(self.device_delays)} Geräte")
        
    def get_stats(self) -> Dict:
        """Gibt Statistiken zurück"""
        stats = self.stats.copy()
        stats.update({
            'playback_state': self.playback_state.value,
            'active_devices': len(self.active_devices),
            'current_stream': self.current_stream,
            'master_clock': self.master_clock,
            'uptime': time.time() - self.playback_start_time if self.playback_start_time else 0
        })
        return stats