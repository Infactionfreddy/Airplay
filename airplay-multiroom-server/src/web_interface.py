"""
Web-Interface für den AirPlay Multiroom Server
"""
import asyncio
import logging
import json
from typing import Dict, Optional
from pathlib import Path
from aiohttp import web, web_ws
from aiohttp.web_request import Request
from aiohttp.web_response import Response
import aiohttp_cors

logger = logging.getLogger(__name__)


class WebInterface:
    """Web-Interface für Konfiguration und Monitoring"""
    
    def __init__(self, config, device_manager, multiroom_coordinator):
        self.config = config
        self.device_manager = device_manager
        self.coordinator = multiroom_coordinator
        
        # Web-Server-Einstellungen
        self.host = config.get('web.host', '0.0.0.0')
        self.port = config.get('web.port', 5000)
        self.enabled = config.get('web.enabled', True)
        
        # Authentifizierung
        self.auth_enabled = config.get('web.security.auth_enabled', False)
        self.username = config.get('web.security.username', 'admin')
        self.password = config.get('web.security.password', 'airplay123')
        
        # aiohttp App
        self.app = None
        self.runner = None
        self.site = None
        
        # WebSocket-Verbindungen
        self.websockets = set()
        
        # Pfade
        self.static_path = Path(__file__).parent.parent / 'web' / 'static'
        self.template_path = Path(__file__).parent.parent / 'web' / 'templates'
        
    async def initialize(self):
        """Initialisiert das Web-Interface"""
        if not self.enabled:
            logger.info("Web-Interface deaktiviert")
            return
            
        logger.info("Initialisiere Web-Interface...")
        
        # aiohttp App erstellen
        self.app = web.Application()
        
        # CORS konfigurieren
        cors = aiohttp_cors.setup(self.app, defaults={
            "*": aiohttp_cors.ResourceOptions(
                allow_credentials=True,
                expose_headers="*",
                allow_headers="*",
                allow_methods="*"
            )
        })
        
        # Routes hinzufügen
        self._setup_routes()
        
        # CORS für alle Routes aktivieren
        for route in list(self.app.router.routes()):
            cors.add(route)
            
        # Device-Manager-Callbacks registrieren
        self.device_manager.register_callback('added', self._on_device_added)
        self.device_manager.register_callback('removed', self._on_device_removed)
        self.device_manager.register_callback('updated', self._on_device_updated)
        
        logger.info("Web-Interface initialisiert")
        
    async def start(self):
        """Startet das Web-Interface"""
        if not self.enabled:
            return
            
        logger.info(f"Starte Web-Interface auf {self.host}:{self.port}...")
        
        try:
            self.runner = web.AppRunner(self.app)
            await self.runner.setup()
            
            self.site = web.TCPSite(self.runner, self.host, self.port)
            await self.site.start()
            
            logger.info(f"Web-Interface gestartet - http://{self.host}:{self.port}")
            
        except Exception as e:
            logger.error(f"Fehler beim Starten des Web-Interfaces: {e}")
            raise
            
    async def stop(self):
        """Stoppt das Web-Interface"""
        if not self.enabled:
            return
            
        logger.info("Stoppe Web-Interface...")
        
        # WebSocket-Verbindungen schließen
        for ws in list(self.websockets):
            await ws.close()
            
        # Server stoppen
        if self.site:
            await self.site.stop()
            
        if self.runner:
            await self.runner.cleanup()
            
        logger.info("Web-Interface gestoppt")
        
    def _setup_routes(self):
        """Konfiguriert die Web-Routes"""
        # Statische Dateien
        if self.static_path.exists():
            self.app.router.add_static('/static/', self.static_path)
            
        # API Routes
        self.app.router.add_get('/', self._handle_index)
        self.app.router.add_get('/api/status', self._handle_api_status)
        self.app.router.add_get('/api/devices', self._handle_api_devices)
        self.app.router.add_post('/api/devices/{device_id}/connect', self._handle_api_connect_device)
        self.app.router.add_post('/api/devices/{device_id}/disconnect', self._handle_api_disconnect_device)
        self.app.router.add_get('/api/stats', self._handle_api_stats)
        self.app.router.add_post('/api/playback/start', self._handle_api_start_playback)
        self.app.router.add_post('/api/playback/stop', self._handle_api_stop_playback)
        self.app.router.add_get('/api/config', self._handle_api_config)
        self.app.router.add_post('/api/config', self._handle_api_update_config)
        
        # WebSocket für Live-Updates
        self.app.router.add_get('/ws', self._handle_websocket)
        
    async def _handle_index(self, request: Request) -> Response:
        """Hauptseite"""
        html = """
<!DOCTYPE html>
<html lang="de">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>AirPlay Multiroom Server</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 20px; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; }
        .card { background: white; border-radius: 8px; padding: 20px; margin: 20px 0; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
        .header { text-align: center; color: #333; }
        .status { display: inline-block; padding: 4px 8px; border-radius: 4px; color: white; font-size: 12px; }
        .status.playing { background: #4CAF50; }
        .status.stopped { background: #f44336; }
        .status.connected { background: #2196F3; }
        .status.disconnected { background: #ff9800; }
        .device { border: 1px solid #ddd; border-radius: 4px; padding: 10px; margin: 10px 0; }
        .device.active { border-color: #4CAF50; background: #f9fff9; }
        .btn { background: #2196F3; color: white; border: none; padding: 8px 16px; border-radius: 4px; cursor: pointer; }
        .btn:hover { background: #1976D2; }
        .btn.danger { background: #f44336; }
        .btn.danger:hover { background: #d32f2f; }
        .stats { display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 15px; }
        .stat { text-align: center; }
        .stat-value { font-size: 24px; font-weight: bold; color: #2196F3; }
        .stat-label { color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🎵 AirPlay Multiroom Server</h1>
            <div id="server-status" class="status">Lädt...</div>
        </div>
        
        <div class="card">
            <h2>Statistiken</h2>
            <div class="stats" id="stats-container">
                <div class="stat">
                    <div class="stat-value" id="devices-count">-</div>
                    <div class="stat-label">Verfügbare Geräte</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="streams-processed">-</div>
                    <div class="stat-label">Streams verarbeitet</div>
                </div>
                <div class="stat">
                    <div class="stat-value" id="uptime">-</div>
                    <div class="stat-label">Laufzeit (min)</div>
                </div>
            </div>
        </div>
        
        <div class="card">
            <h2>Wiedergabe-Kontrolle</h2>
            <div style="text-align: center;">
                <button class="btn" onclick="startPlayback()">▶️ Wiedergabe starten</button>
                <button class="btn danger" onclick="stopPlayback()">⏹️ Wiedergabe stoppen</button>
            </div>
        </div>
        
        <div class="card">
            <h2>AirPlay-Geräte</h2>
            <div id="devices-container">
                <p>Lade Geräte...</p>
            </div>
            <button class="btn" onclick="refreshDevices()">🔄 Aktualisieren</button>
        </div>
    </div>
    
    <script>
        let ws = null;
        
        // WebSocket-Verbindung
        function connectWebSocket() {
            const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
            ws = new WebSocket(`${protocol}//${window.location.host}/ws`);
            
            ws.onopen = () => console.log('WebSocket verbunden');
            ws.onclose = () => {
                console.log('WebSocket getrennt - Reconnect in 5s');
                setTimeout(connectWebSocket, 5000);
            };
            ws.onmessage = (event) => {
                const data = JSON.parse(event.data);
                handleWebSocketMessage(data);
            };
        }
        
        // WebSocket-Nachrichten verarbeiten
        function handleWebSocketMessage(data) {
            if (data.type === 'device_update') {
                loadDevices();
            } else if (data.type === 'status_update') {
                updateStatus(data.status);
            } else if (data.type === 'stats_update') {
                updateStats(data.stats);
            }
        }
        
        // Status laden und anzeigen
        async function loadStatus() {
            try {
                const response = await fetch('/api/status');
                const data = await response.json();
                updateStatus(data);
            } catch (error) {
                console.error('Fehler beim Laden des Status:', error);
            }
        }
        
        function updateStatus(status) {
            const statusEl = document.getElementById('server-status');
            statusEl.textContent = status.playback_state || 'Unbekannt';
            statusEl.className = `status ${status.playback_state || 'stopped'}`;
        }
        
        // Statistiken laden und anzeigen
        async function loadStats() {
            try {
                const response = await fetch('/api/stats');
                const data = await response.json();
                updateStats(data);
            } catch (error) {
                console.error('Fehler beim Laden der Statistiken:', error);
            }
        }
        
        function updateStats(stats) {
            document.getElementById('devices-count').textContent = stats.available_devices || 0;
            document.getElementById('streams-processed').textContent = stats.streams_processed || 0;
            document.getElementById('uptime').textContent = Math.round((stats.uptime || 0) / 60);
        }
        
        // Geräte laden und anzeigen
        async function loadDevices() {
            try {
                const response = await fetch('/api/devices');
                const devices = await response.json();
                displayDevices(devices);
            } catch (error) {
                console.error('Fehler beim Laden der Geräte:', error);
            }
        }
        
        function displayDevices(devices) {
            const container = document.getElementById('devices-container');
            
            if (devices.length === 0) {
                container.innerHTML = '<p>Keine AirPlay-Geräte gefunden.</p>';
                return;
            }
            
            container.innerHTML = devices.map(device => `
                <div class="device ${device.status === 'connected' ? 'active' : ''}">
                    <h3>${device.name}</h3>
                    <p>
                        <strong>Host:</strong> ${device.host}:${device.port}<br>
                        <strong>Typ:</strong> ${device.device_type}<br>
                        <strong>Status:</strong> <span class="status ${device.status}">${device.status}</span>
                    </p>
                    ${device.status === 'connected' ? 
                        `<button class="btn danger" onclick="disconnectDevice('${device.device_id}')">Trennen</button>` :
                        `<button class="btn" onclick="connectDevice('${device.device_id}')">Verbinden</button>`
                    }
                </div>
            `).join('');
        }
        
        // Geräte-Aktionen
        async function connectDevice(deviceId) {
            try {
                await fetch(`/api/devices/${deviceId}/connect`, { method: 'POST' });
                loadDevices();
            } catch (error) {
                alert('Fehler beim Verbinden mit Gerät');
            }
        }
        
        async function disconnectDevice(deviceId) {
            try {
                await fetch(`/api/devices/${deviceId}/disconnect`, { method: 'POST' });
                loadDevices();
            } catch (error) {
                alert('Fehler beim Trennen vom Gerät');
            }
        }
        
        // Wiedergabe-Aktionen
        async function startPlayback() {
            try {
                await fetch('/api/playback/start', { method: 'POST' });
                loadStatus();
            } catch (error) {
                alert('Fehler beim Starten der Wiedergabe');
            }
        }
        
        async function stopPlayback() {
            try {
                await fetch('/api/playback/stop', { method: 'POST' });
                loadStatus();
            } catch (error) {
                alert('Fehler beim Stoppen der Wiedergabe');
            }
        }
        
        // Geräte aktualisieren
        async function refreshDevices() {
            await loadDevices();
        }
        
        // Initialisierung
        document.addEventListener('DOMContentLoaded', () => {
            connectWebSocket();
            loadStatus();
            loadStats();
            loadDevices();
            
            // Regelmäßige Updates
            setInterval(loadStats, 5000);
            setInterval(loadStatus, 2000);
        });
    </script>
</body>
</html>
        """
        return web.Response(text=html, content_type='text/html')
        
    async def _handle_api_status(self, request: Request) -> Response:
        """API: Server-Status"""
        stats = self.coordinator.get_stats()
        return web.json_response(stats)
        
    async def _handle_api_devices(self, request: Request) -> Response:
        """API: Liste aller Geräte"""
        devices = await self.device_manager.get_devices()
        device_list = []
        
        for device in devices:
            device_list.append({
                'device_id': device.device_id,
                'name': device.name,
                'host': device.host,
                'port': device.port,
                'device_type': device.device_type.value,
                'status': device.status.value,
                'last_seen': device.last_seen,
                'features': device.features,
                'model': device.model
            })
            
        return web.json_response(device_list)
        
    async def _handle_api_connect_device(self, request: Request) -> Response:
        """API: Gerät verbinden"""
        device_id = request.match_info['device_id']
        
        try:
            device = await self.device_manager.get_device(device_id)
            if not device:
                return web.json_response({'error': 'Gerät nicht gefunden'}, status=404)
                
            # Gerät zum Koordinator hinzufügen
            await self.coordinator.add_device(device_id, {
                'host': device.host,
                'port': device.port,
                'name': device.name
            })
            
            return web.json_response({'success': True})
            
        except Exception as e:
            logger.error(f"Fehler beim Verbinden mit Gerät {device_id}: {e}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def _handle_api_disconnect_device(self, request: Request) -> Response:
        """API: Gerät trennen"""
        device_id = request.match_info['device_id']
        
        try:
            await self.coordinator.remove_device(device_id)
            return web.json_response({'success': True})
            
        except Exception as e:
            logger.error(f"Fehler beim Trennen von Gerät {device_id}: {e}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def _handle_api_stats(self, request: Request) -> Response:
        """API: Statistiken"""
        coordinator_stats = self.coordinator.get_stats()
        device_stats = self.device_manager.get_stats()
        
        combined_stats = {
            **coordinator_stats,
            **device_stats
        }
        
        return web.json_response(combined_stats)
        
    async def _handle_api_start_playback(self, request: Request) -> Response:
        """API: Wiedergabe starten"""
        try:
            await self.coordinator.start_playback()
            return web.json_response({'success': True})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
            
    async def _handle_api_stop_playback(self, request: Request) -> Response:
        """API: Wiedergabe stoppen"""
        try:
            await self.coordinator.stop_playback()
            return web.json_response({'success': True})
        except Exception as e:
            return web.json_response({'error': str(e)}, status=500)
            
    async def _handle_api_config(self, request: Request) -> Response:
        """API: Konfiguration abrufen"""
        # Sensible Daten ausblenden
        config_copy = {}
        for key, value in self.config._config.items():
            if key != 'web' or not isinstance(value, dict):
                config_copy[key] = value
            else:
                # Web-Konfiguration ohne Passwort
                web_config = value.copy()
                if 'security' in web_config and isinstance(web_config['security'], dict):
                    security = web_config['security'].copy()
                    if 'password' in security:
                        security['password'] = '***'
                    web_config['security'] = security
                config_copy[key] = web_config
                
        return web.json_response(config_copy)
        
    async def _handle_api_update_config(self, request: Request) -> Response:
        """API: Konfiguration aktualisieren"""
        try:
            data = await request.json()
            
            # TODO: Konfiguration validieren und aktualisieren
            # Sicherheitshalber nur bestimmte Werte erlauben
            
            return web.json_response({'success': True})
            
        except Exception as e:
            logger.error(f"Fehler beim Aktualisieren der Konfiguration: {e}")
            return web.json_response({'error': str(e)}, status=500)
            
    async def _handle_websocket(self, request: Request) -> web.WebSocketResponse:
        """WebSocket-Handler für Live-Updates"""
        ws = web.WebSocketResponse()
        await ws.prepare(request)
        
        self.websockets.add(ws)
        logger.debug("WebSocket-Verbindung hinzugefügt")
        
        try:
            async for msg in ws:
                if msg.type == web_ws.WSMsgType.TEXT:
                    # Echo oder spezifische Nachrichten verarbeiten
                    data = json.loads(msg.data)
                    await self._handle_websocket_message(ws, data)
                elif msg.type == web_ws.WSMsgType.ERROR:
                    logger.error(f"WebSocket-Fehler: {ws.exception()}")
                    
        except Exception as e:
            logger.error(f"WebSocket-Verbindung unterbrochen: {e}")
        finally:
            self.websockets.discard(ws)
            logger.debug("WebSocket-Verbindung entfernt")
            
        return ws
        
    async def _handle_websocket_message(self, ws: web.WebSocketResponse, data: Dict):
        """Verarbeitet WebSocket-Nachrichten"""
        message_type = data.get('type')
        
        if message_type == 'ping':
            await ws.send_str(json.dumps({'type': 'pong'}))
        elif message_type == 'subscribe':
            # Client möchte Updates erhalten
            await ws.send_str(json.dumps({
                'type': 'subscribed',
                'message': 'Successfully subscribed to updates'
            }))
            
    async def _broadcast_to_websockets(self, message: Dict):
        """Sendet eine Nachricht an alle WebSocket-Verbindungen"""
        if not self.websockets:
            return
            
        message_str = json.dumps(message)
        disconnected = set()
        
        for ws in self.websockets:
            try:
                await ws.send_str(message_str)
            except Exception as e:
                logger.debug(f"Fehler beim Senden an WebSocket: {e}")
                disconnected.add(ws)
                
        # Getrennte Verbindungen entfernen
        self.websockets -= disconnected
        
    async def _on_device_added(self, device):
        """Callback: Gerät hinzugefügt"""
        await self._broadcast_to_websockets({
            'type': 'device_update',
            'action': 'added',
            'device': {
                'device_id': device.device_id,
                'name': device.name,
                'host': device.host
            }
        })
        
    async def _on_device_removed(self, device):
        """Callback: Gerät entfernt"""
        await self._broadcast_to_websockets({
            'type': 'device_update',
            'action': 'removed',
            'device': {
                'device_id': device.device_id,
                'name': device.name
            }
        })
        
    async def _on_device_updated(self, device):
        """Callback: Gerät aktualisiert"""
        await self._broadcast_to_websockets({
            'type': 'device_update',
            'action': 'updated',
            'device': {
                'device_id': device.device_id,
                'name': device.name,
                'status': device.status.value
            }
        })