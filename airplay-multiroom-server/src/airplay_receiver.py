"""
AirPlay Empfänger für den Multiroom Server
"""
import asyncio
import logging
import socket
import struct
import base64
from typing import Optional, Callable, Dict, Any
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
import netifaces

logger = logging.getLogger(__name__)


class AirPlayReceiver:
    """AirPlay RAOP (Remote Audio Output Protocol) Empfänger"""
    
    def __init__(self, config, multiroom_coordinator):
        self.config = config
        self.coordinator = multiroom_coordinator
        
        # Server-Konfiguration
        self.service_name = config.get('airplay.service_name', 'Multiroom Audio')
        self.port = config.get('airplay.port', 5001)
        
        # Netzwerk
        self.server = None
        self.clients = {}
        
        # Audio-Parameter
        self.sample_rate = config.get('airplay.sample_rate', 44100)
        self.channels = config.get('airplay.channels', 2)
        self.bit_depth = config.get('airplay.bit_depth', 16)
        
        # Verschlüsselung
        self.rsa_key = None
        self.aes_key = None
        self.aes_iv = None
        
        # Status
        self.running = False
        
    async def initialize(self):
        """Initialisiert den AirPlay Empfänger"""
        logger.info("Initialisiere AirPlay Empfänger...")
        
        # RSA-Schlüssel generieren für Verschlüsselung
        await self._generate_rsa_key()
        
        # mDNS Service vorbereiten
        await self._setup_mdns()
        
        logger.info(f"AirPlay Empfänger initialisiert - Service: {self.service_name}")
        
    async def start(self):
        """Startet den AirPlay Server"""
        if self.running:
            return
            
        logger.info(f"Starte AirPlay Empfänger auf Port {self.port}...")
        
        try:
            # TCP Server erstellen
            self.server = await asyncio.start_server(
                self._handle_client,
                '0.0.0.0',
                self.port
            )
            
            self.running = True
            
            # mDNS Service registrieren
            await self._register_mdns_service()
            
            logger.info(f"AirPlay Empfänger gestartet - verfügbar als '{self.service_name}'")
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des AirPlay Empfängers: {e}")
            raise
            
    async def stop(self):
        """Stoppt den AirPlay Server"""
        if not self.running:
            return
            
        logger.info("Stoppe AirPlay Empfänger...")
        
        self.running = False
        
        # Alle Clients trennen
        for client_id in list(self.clients.keys()):
            await self._disconnect_client(client_id)
            
        # Server schließen
        if self.server:
            self.server.close()
            await self.server.wait_closed()
            
        # mDNS Service deregistrieren
        await self._unregister_mdns_service()
        
        logger.info("AirPlay Empfänger gestoppt")
        
    async def _handle_client(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter):
        """Behandelt eingehende Client-Verbindungen"""
        client_addr = writer.get_extra_info('peername')
        client_id = f"{client_addr[0]}:{client_addr[1]}"
        
        logger.info(f"Neue AirPlay Verbindung von {client_id}")
        
        try:
            # Client registrieren
            self.clients[client_id] = {
                'reader': reader,
                'writer': writer,
                'addr': client_addr,
                'authenticated': False,
                'session': {}
            }
            
            # RTSP-Kommunikation verarbeiten
            await self._handle_rtsp_session(client_id)
            
        except Exception as e:
            logger.error(f"Fehler bei Client {client_id}: {e}")
        finally:
            await self._disconnect_client(client_id)
            
    async def _handle_rtsp_session(self, client_id: str):
        """Verarbeitet eine RTSP-Session mit einem Client"""
        client = self.clients[client_id]
        reader = client['reader']
        writer = client['writer']
        
        try:
            while self.running and client_id in self.clients:
                # RTSP Request lesen
                request_line = await reader.readline()
                if not request_line:
                    break
                    
                request = request_line.decode('utf-8').strip()
                logger.debug(f"RTSP Request von {client_id}: {request}")
                
                # Headers lesen
                headers = {}
                while True:
                    line = await reader.readline()
                    if not line or line == b'\r\n':
                        break
                    header_line = line.decode('utf-8').strip()
                    if ':' in header_line:
                        key, value = header_line.split(':', 1)
                        headers[key.strip()] = value.strip()
                
                # Request verarbeiten
                await self._process_rtsp_request(client_id, request, headers)
                
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"Fehler in RTSP Session {client_id}: {e}")
            
    async def _process_rtsp_request(self, client_id: str, request: str, headers: Dict[str, str]):
        """Verarbeitet eine RTSP-Anfrage"""
        client = self.clients[client_id]
        writer = client['writer']
        
        try:
            # Request-Typ ermitteln
            parts = request.split()
            if len(parts) < 2:
                return
                
            method = parts[0]
            path = parts[1]
            
            # CSeq für Response
            cseq = headers.get('CSeq', '0')
            
            if method == 'OPTIONS':
                response = self._create_options_response(cseq)
            elif method == 'ANNOUNCE':
                response = await self._handle_announce(client_id, headers, cseq)
            elif method == 'SETUP':
                response = await self._handle_setup(client_id, headers, cseq)
            elif method == 'RECORD':
                response = await self._handle_record(client_id, headers, cseq)
            elif method == 'FLUSH':
                response = await self._handle_flush(client_id, headers, cseq)
            elif method == 'TEARDOWN':
                response = await self._handle_teardown(client_id, headers, cseq)
            else:
                response = self._create_error_response(501, 'Not Implemented', cseq)
            
            # Response senden
            writer.write(response.encode('utf-8'))
            await writer.drain()
            
        except Exception as e:
            logger.error(f"Fehler beim Verarbeiten der RTSP-Anfrage: {e}")
            
    def _create_options_response(self, cseq: str) -> str:
        """Erstellt OPTIONS Response"""
        return (
            "RTSP/1.0 200 OK\r\n"
            f"CSeq: {cseq}\r\n"
            "Public: ANNOUNCE, SETUP, RECORD, PAUSE, FLUSH, TEARDOWN, OPTIONS, GET_PARAMETER, SET_PARAMETER\r\n"
            "Server: AirPlay-Multiroom-Server/1.0\r\n"
            "\r\n"
        )
        
    async def _handle_announce(self, client_id: str, headers: Dict[str, str], cseq: str) -> str:
        """Behandelt ANNOUNCE Request (Session-Parameter)"""
        try:
            # Content-Type prüfen
            content_type = headers.get('Content-Type', '')
            if 'application/sdp' not in content_type:
                return self._create_error_response(400, 'Bad Request', cseq)
            
            # TODO: SDP-Content parsen für Audio-Parameter
            client = self.clients[client_id]
            client['session']['announced'] = True
            
            logger.info(f"ANNOUNCE verarbeitet für {client_id}")
            
            return (
                "RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                "Server: AirPlay-Multiroom-Server/1.0\r\n"
                "\r\n"
            )
            
        except Exception as e:
            logger.error(f"Fehler bei ANNOUNCE: {e}")
            return self._create_error_response(500, 'Internal Server Error', cseq)
            
    async def _handle_setup(self, client_id: str, headers: Dict[str, str], cseq: str) -> str:
        """Behandelt SETUP Request (Transport-Parameter)"""
        try:
            transport = headers.get('Transport', '')
            
            # RTP-Ports aus Transport-Header extrahieren
            server_port = 6000  # Standard-Port
            control_port = 6001
            
            if 'server_port=' in transport:
                # Port-Range parsen
                port_part = transport.split('server_port=')[1].split(';')[0]
                if '-' in port_part:
                    server_port, control_port = map(int, port_part.split('-'))
            
            # Session-ID generieren
            import time
            session_id = str(int(time.time()))
            
            client = self.clients[client_id]
            client['session'].update({
                'session_id': session_id,
                'server_port': server_port,
                'control_port': control_port,
                'setup_complete': True
            })
            
            logger.info(f"SETUP verarbeitet für {client_id} - Session: {session_id}")
            
            return (
                "RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                f"Session: {session_id}\r\n"
                f"Transport: RTP/AVP/UDP;unicast;server_port={server_port}-{control_port}\r\n"
                "Server: AirPlay-Multiroom-Server/1.0\r\n"
                "\r\n"
            )
            
        except Exception as e:
            logger.error(f"Fehler bei SETUP: {e}")
            return self._create_error_response(500, 'Internal Server Error', cseq)
            
    async def _handle_record(self, client_id: str, headers: Dict[str, str], cseq: str) -> str:
        """Behandelt RECORD Request (Streaming starten)"""
        try:
            client = self.clients[client_id]
            
            # Audio-Stream an Koordinator weiterleiten
            await self.coordinator.start_audio_stream(
                client_id,
                client['session']
            )
            
            client['session']['recording'] = True
            
            logger.info(f"Audio-Streaming gestartet für {client_id}")
            
            return (
                "RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                "Server: AirPlay-Multiroom-Server/1.0\r\n"
                "\r\n"
            )
            
        except Exception as e:
            logger.error(f"Fehler bei RECORD: {e}")
            return self._create_error_response(500, 'Internal Server Error', cseq)
            
    async def _handle_flush(self, client_id: str, headers: Dict[str, str], cseq: str) -> str:
        """Behandelt FLUSH Request (Buffer leeren)"""
        try:
            await self.coordinator.flush_audio_buffer(client_id)
            
            logger.debug(f"Audio-Buffer geleert für {client_id}")
            
            return (
                "RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                "Server: AirPlay-Multiroom-Server/1.0\r\n"
                "\r\n"
            )
            
        except Exception as e:
            logger.error(f"Fehler bei FLUSH: {e}")
            return self._create_error_response(500, 'Internal Server Error', cseq)
            
    async def _handle_teardown(self, client_id: str, headers: Dict[str, str], cseq: str) -> str:
        """Behandelt TEARDOWN Request (Session beenden)"""
        try:
            await self.coordinator.stop_audio_stream(client_id)
            
            logger.info(f"Audio-Session beendet für {client_id}")
            
            # Client für Disconnect markieren
            asyncio.create_task(self._disconnect_client(client_id))
            
            return (
                "RTSP/1.0 200 OK\r\n"
                f"CSeq: {cseq}\r\n"
                "Server: AirPlay-Multiroom-Server/1.0\r\n"
                "\r\n"
            )
            
        except Exception as e:
            logger.error(f"Fehler bei TEARDOWN: {e}")
            return self._create_error_response(500, 'Internal Server Error', cseq)
            
    def _create_error_response(self, status_code: int, reason: str, cseq: str) -> str:
        """Erstellt eine Fehler-Response"""
        return (
            f"RTSP/1.0 {status_code} {reason}\r\n"
            f"CSeq: {cseq}\r\n"
            "Server: AirPlay-Multiroom-Server/1.0\r\n"
            "\r\n"
        )
        
    async def _disconnect_client(self, client_id: str):
        """Trennt einen Client"""
        if client_id not in self.clients:
            return
            
        try:
            client = self.clients[client_id]
            writer = client['writer']
            
            # Verbindung schließen
            writer.close()
            await writer.wait_closed()
            
            # Aus Liste entfernen
            del self.clients[client_id]
            
            logger.info(f"Client {client_id} getrennt")
            
        except Exception as e:
            logger.error(f"Fehler beim Trennen von Client {client_id}: {e}")
            
    async def _generate_rsa_key(self):
        """Generiert RSA-Schlüssel für Verschlüsselung"""
        # Für AirPlay wird ein spezifischer RSA-Schlüssel verwendet
        # Hier würde normalerweise der Apple AirPlay RSA-Schlüssel verwendet
        self.rsa_key = "dummy_rsa_key"  # Placeholder
        
    async def _setup_mdns(self):
        """Bereitet mDNS-Service vor"""
        # mDNS-Service wird später registriert
        pass
        
    async def _register_mdns_service(self):
        """Registriert den mDNS-Service"""
        # TODO: Zeroconf/Bonjour Service registrieren
        logger.info(f"mDNS-Service registriert: {self.service_name}")
        
    async def _unregister_mdns_service(self):
        """Deregistriert den mDNS-Service"""
        logger.info("mDNS-Service deregistriert")