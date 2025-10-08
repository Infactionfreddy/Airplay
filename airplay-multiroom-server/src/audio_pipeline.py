"""
Audio-Pipeline für den AirPlay Multiroom Server
Verwendet GStreamer für Audio-Verarbeitung und Synchronisation
"""
import asyncio
import logging
import threading
import time
from typing import Dict, List, Optional, Callable
from collections import deque
import gi

# GStreamer Imports
gi.require_version('Gst', '1.0')
gi.require_version('GstApp', '1.0')
from gi import pygobject
import gi.repository.Gst as Gst
import gi.repository.GstApp as GstApp
import gi.repository.GLib as GLib

logger = logging.getLogger(__name__)


class AudioBuffer:
    """Thread-sicherer Audio-Puffer"""
    
    def __init__(self, max_size: int = 1024):
        self.buffer = deque(maxlen=max_size)
        self.lock = threading.RLock()
        self.condition = threading.Condition(self.lock)
        
    def put(self, data: bytes):
        """Fügt Audio-Daten zum Puffer hinzu"""
        with self.condition:
            self.buffer.append(data)
            self.condition.notify_all()
            
    def get(self, timeout: float = None) -> Optional[bytes]:
        """Holt Audio-Daten aus dem Puffer"""
        with self.condition:
            if not self.buffer:
                self.condition.wait(timeout)
            
            if self.buffer:
                return self.buffer.popleft()
            return None
            
    def clear(self):
        """Leert den Puffer"""
        with self.condition:
            self.buffer.clear()
            self.condition.notify_all()
            
    def size(self) -> int:
        """Gibt die aktuelle Puffergröße zurück"""
        with self.lock:
            return len(self.buffer)


class AudioStream:
    """Repräsentiert einen Audio-Stream mit Metadaten"""
    
    def __init__(self, stream_id: str, source_info: Dict):
        self.stream_id = stream_id
        self.source_info = source_info
        self.buffer = AudioBuffer()
        
        # Audio-Parameter
        self.sample_rate = source_info.get('sample_rate', 44100)
        self.channels = source_info.get('channels', 2)
        self.bit_depth = source_info.get('bit_depth', 16)
        
        # Timing
        self.start_time = None
        self.last_timestamp = None
        
        # Status
        self.active = False
        
    def add_audio_data(self, data: bytes, timestamp: Optional[float] = None):
        """Fügt Audio-Daten zum Stream hinzu"""
        if not self.active:
            return
            
        current_time = timestamp or time.time()
        
        if self.start_time is None:
            self.start_time = current_time
            
        self.last_timestamp = current_time
        self.buffer.put(data)
        
    def get_audio_data(self, timeout: float = 0.1) -> Optional[bytes]:
        """Holt Audio-Daten aus dem Stream"""
        return self.buffer.get(timeout)
        
    def flush(self):
        """Leert den Stream-Puffer"""
        self.buffer.clear()
        
    def is_active(self) -> bool:
        """Prüft ob der Stream aktiv ist"""
        if not self.active:
            return False
            
        # Timeout-Prüfung (Stream als inaktiv betrachten nach 5 Sekunden ohne Daten)
        if self.last_timestamp and (time.time() - self.last_timestamp) > 5.0:
            return False
            
        return True


class GStreamerPipeline:
    """GStreamer-Pipeline für Audio-Verarbeitung"""
    
    def __init__(self, config):
        self.config = config
        self.pipeline = None
        self.bus = None
        self.loop = None
        
        # Pipeline-Elemente
        self.appsrc = None
        self.audioconvert = None
        self.audioresample = None
        self.tee = None
        self.outputs = {}
        
        # Status
        self.running = False
        
    async def initialize(self):
        """Initialisiert die GStreamer-Pipeline"""
        # GStreamer initialisieren
        Gst.init(None)
        
        # Hauptpipeline erstellen
        self.pipeline = Gst.Pipeline.new("multiroom-pipeline")
        
        # App-Source (für eingehende Audio-Daten)
        self.appsrc = Gst.ElementFactory.make("appsrc", "audio-source")
        self.appsrc.set_property("is-live", True)
        self.appsrc.set_property("format", Gst.Format.TIME)
        
        # Audio-Konvertierung
        self.audioconvert = Gst.ElementFactory.make("audioconvert", "convert")
        self.audioresample = Gst.ElementFactory.make("audioresample", "resample")
        
        # Tee für Verteilung an mehrere Ausgänge
        self.tee = Gst.ElementFactory.make("tee", "tee")
        
        # Elemente zur Pipeline hinzufügen
        self.pipeline.add(self.appsrc)
        self.pipeline.add(self.audioconvert)
        self.pipeline.add(self.audioresample)
        self.pipeline.add(self.tee)
        
        # Elemente verlinken
        self.appsrc.link(self.audioconvert)
        self.audioconvert.link(self.audioresample)
        self.audioresample.link(self.tee)
        
        # Bus für Nachrichten
        self.bus = self.pipeline.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message", self._on_bus_message)
        
        logger.info("GStreamer-Pipeline initialisiert")
        
    async def start(self):
        """Startet die Pipeline"""
        if self.running:
            return
            
        logger.info("Starte GStreamer-Pipeline...")
        
        # Pipeline starten
        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            raise RuntimeError("Konnte GStreamer-Pipeline nicht starten")
            
        self.running = True
        logger.info("GStreamer-Pipeline gestartet")
        
    async def stop(self):
        """Stoppt die Pipeline"""
        if not self.running:
            return
            
        logger.info("Stoppe GStreamer-Pipeline...")
        
        # Pipeline stoppen
        self.pipeline.set_state(Gst.State.NULL)
        self.running = False
        
        logger.info("GStreamer-Pipeline gestoppt")
        
    def add_output(self, output_id: str, sink_element: Gst.Element):
        """Fügt eine Audio-Ausgabe zur Pipeline hinzu"""
        if output_id in self.outputs:
            logger.warning(f"Output {output_id} bereits vorhanden")
            return
            
        # Queue für den Output
        queue = Gst.ElementFactory.make("queue", f"queue-{output_id}")
        queue.set_property("max-size-time", 2000000000)  # 2 Sekunden
        
        # Zur Pipeline hinzufügen
        self.pipeline.add(queue)
        self.pipeline.add(sink_element)
        
        # Mit Tee verlinken
        tee_pad = self.tee.get_request_pad("src_%u")
        queue_pad = queue.get_static_pad("sink")
        tee_pad.link(queue_pad)
        
        # Queue mit Sink verlinken
        queue.link(sink_element)
        
        # Output registrieren
        self.outputs[output_id] = {
            'queue': queue,
            'sink': sink_element,
            'tee_pad': tee_pad
        }
        
        # Synchronisation falls Pipeline läuft
        if self.running:
            queue.sync_state_with_parent()
            sink_element.sync_state_with_parent()
            
        logger.info(f"Audio-Output {output_id} hinzugefügt")
        
    def remove_output(self, output_id: str):
        """Entfernt eine Audio-Ausgabe von der Pipeline"""
        if output_id not in self.outputs:
            return
            
        output_info = self.outputs[output_id]
        
        # Elemente stoppen
        output_info['queue'].set_state(Gst.State.NULL)
        output_info['sink'].set_state(Gst.State.NULL)
        
        # Tee-Pad freigeben
        self.tee.release_request_pad(output_info['tee_pad'])
        
        # Aus Pipeline entfernen
        self.pipeline.remove(output_info['queue'])
        self.pipeline.remove(output_info['sink'])
        
        # Aus Liste entfernen
        del self.outputs[output_id]
        
        logger.info(f"Audio-Output {output_id} entfernt")
        
    def push_audio_data(self, data: bytes):
        """Schiebt Audio-Daten in die Pipeline"""
        if not self.running or not self.appsrc:
            return
            
        # GstBuffer erstellen
        buffer = Gst.Buffer.new_allocate(None, len(data), None)
        buffer.fill(0, data)
        
        # Buffer zur App-Source senden
        ret = self.appsrc.emit("push-buffer", buffer)
        
        if ret != Gst.FlowReturn.OK:
            logger.warning(f"Fehler beim Push von Audio-Daten: {ret}")
            
    def _on_bus_message(self, bus, message):
        """Behandelt GStreamer-Bus-Nachrichten"""
        msg_type = message.type
        
        if msg_type == Gst.MessageType.ERROR:
            err, debug = message.parse_error()
            logger.error(f"GStreamer Fehler: {err}, Debug: {debug}")
            
        elif msg_type == Gst.MessageType.WARNING:
            err, debug = message.parse_warning()
            logger.warning(f"GStreamer Warnung: {err}, Debug: {debug}")
            
        elif msg_type == Gst.MessageType.EOS:
            logger.info("GStreamer End-Of-Stream")


class AudioPipeline:
    """Haupt-Audio-Pipeline für Multiroom-Synchronisation"""
    
    def __init__(self, config):
        self.config = config
        
        # Streams
        self.streams = {}  # stream_id -> AudioStream
        self.active_stream = None
        
        # GStreamer-Pipeline
        self.gstreamer = GStreamerPipeline(config)
        
        # Synchronisation
        self.sync_enabled = True
        self.global_delay = config.get('synchronization.global_delay', 0.5)
        
        # Processing-Thread
        self.processing_thread = None
        self.processing_active = False
        
        # Output-Callbacks
        self.output_callbacks = {}  # output_id -> callback
        
        # Statistiken
        self.stats = {
            'streams_processed': 0,
            'bytes_processed': 0,
            'buffer_underruns': 0,
            'buffer_overruns': 0
        }
        
    async def initialize(self):
        """Initialisiert die Audio-Pipeline"""
        logger.info("Initialisiere Audio-Pipeline...")
        
        await self.gstreamer.initialize()
        
        logger.info("Audio-Pipeline initialisiert")
        
    async def start(self):
        """Startet die Audio-Pipeline"""
        logger.info("Starte Audio-Pipeline...")
        
        await self.gstreamer.start()
        
        # Processing-Thread starten
        self.processing_active = True
        self.processing_thread = threading.Thread(target=self._audio_processing_loop)
        self.processing_thread.daemon = True
        self.processing_thread.start()
        
        logger.info("Audio-Pipeline gestartet")
        
    async def stop(self):
        """Stoppt die Audio-Pipeline"""
        logger.info("Stoppe Audio-Pipeline...")
        
        # Processing stoppen
        self.processing_active = False
        if self.processing_thread:
            self.processing_thread.join(timeout=5.0)
            
        # GStreamer stoppen
        await self.gstreamer.stop()
        
        logger.info("Audio-Pipeline gestoppt")
        
    def add_stream(self, stream_id: str, source_info: Dict) -> AudioStream:
        """Fügt einen neuen Audio-Stream hinzu"""
        if stream_id in self.streams:
            logger.warning(f"Stream {stream_id} bereits vorhanden")
            return self.streams[stream_id]
            
        stream = AudioStream(stream_id, source_info)
        self.streams[stream_id] = stream
        
        logger.info(f"Audio-Stream {stream_id} hinzugefügt")
        return stream
        
    def remove_stream(self, stream_id: str):
        """Entfernt einen Audio-Stream"""
        if stream_id in self.streams:
            stream = self.streams[stream_id]
            stream.active = False
            stream.flush()
            del self.streams[stream_id]
            
            # Falls es der aktive Stream war
            if self.active_stream == stream_id:
                self.active_stream = None
                
            logger.info(f"Audio-Stream {stream_id} entfernt")
            
    def set_active_stream(self, stream_id: str):
        """Setzt den aktiven Audio-Stream"""
        if stream_id not in self.streams:
            logger.error(f"Stream {stream_id} nicht gefunden")
            return
            
        self.active_stream = stream_id
        self.streams[stream_id].active = True
        
        # Andere Streams deaktivieren
        for sid, stream in self.streams.items():
            if sid != stream_id:
                stream.active = False
                
        logger.info(f"Aktiver Audio-Stream: {stream_id}")
        
    def add_audio_data(self, stream_id: str, data: bytes, timestamp: Optional[float] = None):
        """Fügt Audio-Daten zu einem Stream hinzu"""
        if stream_id not in self.streams:
            logger.warning(f"Stream {stream_id} nicht gefunden")
            return
            
        stream = self.streams[stream_id]
        stream.add_audio_data(data, timestamp)
        
        self.stats['bytes_processed'] += len(data)
        
    def register_output_callback(self, output_id: str, callback: Callable[[bytes], None]):
        """Registriert einen Callback für Audio-Ausgabe"""
        self.output_callbacks[output_id] = callback
        logger.info(f"Output-Callback für {output_id} registriert")
        
    def unregister_output_callback(self, output_id: str):
        """Deregistriert einen Output-Callback"""
        if output_id in self.output_callbacks:
            del self.output_callbacks[output_id]
            logger.info(f"Output-Callback für {output_id} entfernt")
            
    def flush_all_streams(self):
        """Leert alle Stream-Puffer"""
        for stream in self.streams.values():
            stream.flush()
        logger.info("Alle Stream-Puffer geleert")
        
    def _audio_processing_loop(self):
        """Haupt-Audio-Verarbeitungsschleife"""
        logger.info("Audio-Processing-Thread gestartet")
        
        while self.processing_active:
            try:
                # Aktiven Stream verarbeiten
                if self.active_stream and self.active_stream in self.streams:
                    stream = self.streams[self.active_stream]
                    
                    if stream.is_active():
                        # Audio-Daten vom Stream holen
                        audio_data = stream.get_audio_data(timeout=0.1)
                        
                        if audio_data:
                            # Durch GStreamer-Pipeline senden
                            self.gstreamer.push_audio_data(audio_data)
                            
                            # An alle Output-Callbacks weiterleiten
                            self._distribute_audio_data(audio_data)
                            
                            self.stats['streams_processed'] += 1
                    else:
                        # Stream als inaktiv markieren
                        stream.active = False
                        
                else:
                    # Keine aktiven Streams - kurz warten
                    time.sleep(0.01)
                    
            except Exception as e:
                logger.error(f"Fehler in Audio-Processing-Loop: {e}")
                time.sleep(0.1)
                
        logger.info("Audio-Processing-Thread beendet")
        
    def _distribute_audio_data(self, audio_data: bytes):
        """Verteilt Audio-Daten an alle registrierten Outputs"""
        for output_id, callback in self.output_callbacks.items():
            try:
                callback(audio_data)
            except Exception as e:
                logger.error(f"Fehler bei Output-Callback {output_id}: {e}")
                
    def get_stats(self) -> Dict:
        """Gibt Statistiken zurück"""
        return self.stats.copy()