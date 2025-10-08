"""
Konfigurationsmanager für den AirPlay Multiroom Server
"""
import yaml
import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


class ConfigManager:
    """Manager für die Server-Konfiguration"""
    
    def __init__(self, config_path: Optional[str] = None):
        self.config_path = config_path or self._get_default_config_path()
        self._config = {}
        self._defaults = self._get_defaults()
        
        self.load_config()
        
    def _get_default_config_path(self) -> str:
        """Ermittelt den Standard-Konfigurationspfad"""
        # Verschiedene mögliche Pfade prüfen
        possible_paths = [
            '/etc/airplay-multiroom/config.yaml',
            '~/.config/airplay-multiroom/config.yaml',
            './config/config.yaml',
            './config.yaml'
        ]
        
        for path in possible_paths:
            expanded_path = Path(path).expanduser()
            if expanded_path.exists():
                return str(expanded_path)
                
        # Fallback zum ersten Pfad
        return possible_paths[0]
        
    def _get_defaults(self) -> Dict[str, Any]:
        """Standardkonfiguration"""
        return {
            'server': {
                'name': 'AirPlay Multiroom Server',
                'host': '0.0.0.0',
                'port': 5000,
                'debug': False
            },
            'airplay': {
                'service_name': 'Multiroom Audio',
                'port': 5001,
                'buffer_time': 2.0,
                'sample_rate': 44100,
                'bit_depth': 16,
                'channels': 2
            },
            'devices': {
                'auto_discovery': True,
                'discovery_timeout': 30,
                'max_connections': 10,
                'manual_devices': []
            },
            'synchronization': {
                'global_delay': 0.5,
                'device_delays': {},
                'sync_algorithm': 'advanced',
                'sync_tolerance': 50
            },
            'audio': {
                'gstreamer': {
                    'buffer_size': 8192,
                    'latency': 'low'
                },
                'quality': {
                    'bitrate': 256,
                    'compression': 'lossless'
                }
            },
            'network': {
                'mdns': {
                    'enabled': True,
                    'domain': 'local'
                },
                'timeouts': {
                    'connection': 10,
                    'read': 30,
                    'write': 30
                }
            },
            'logging': {
                'level': 'INFO',
                'file': None,
                'max_size': '10MB',
                'backup_count': 5
            },
            'web': {
                'enabled': True,
                'host': '0.0.0.0',
                'port': 5000,
                'security': {
                    'auth_enabled': False,
                    'username': 'admin',
                    'password': 'airplay123'
                }
            },
            'system': {
                'user': 'airplay',
                'group': 'airplay',
                'pid_file': '/run/airplay-multiroom-server.pid',
                'working_directory': '/opt/airplay-multiroom-server'
            },
            'performance': {
                'thread_pool_size': 4,
                'max_memory_mb': 512,
                'audio_buffer': {
                    'buffer_count': 4,
                    'buffer_size': 4096
                }
            }
        }
        
    def load_config(self):
        """Lädt die Konfiguration aus der Datei"""
        try:
            config_path = Path(self.config_path)
            
            if config_path.exists():
                with open(config_path, 'r', encoding='utf-8') as f:
                    file_config = yaml.safe_load(f) or {}
                    
                # Merge mit Defaults
                self._config = self._deep_merge(self._defaults.copy(), file_config)
                logger.info(f"Konfiguration geladen aus: {config_path}")
            else:
                logger.warning(f"Konfigurationsdatei nicht gefunden: {config_path}")
                logger.info("Verwende Standardkonfiguration")
                self._config = self._defaults.copy()
                
        except Exception as e:
            logger.error(f"Fehler beim Laden der Konfiguration: {e}")
            logger.info("Verwende Standardkonfiguration")
            self._config = self._defaults.copy()
            
    def save_config(self, path: Optional[str] = None):
        """Speichert die aktuelle Konfiguration"""
        save_path = path or self.config_path
        
        try:
            config_path = Path(save_path)
            config_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self._config, f, default_flow_style=False, indent=2)
                
            logger.info(f"Konfiguration gespeichert nach: {config_path}")
            
        except Exception as e:
            logger.error(f"Fehler beim Speichern der Konfiguration: {e}")
            raise
            
    def get(self, key: str, default: Any = None) -> Any:
        """Holt einen Konfigurationswert mit Punkt-Notation"""
        keys = key.split('.')
        value = self._config
        
        try:
            for k in keys:
                value = value[k]
            return value
        except (KeyError, TypeError):
            return default
            
    def set(self, key: str, value: Any):
        """Setzt einen Konfigurationswert mit Punkt-Notation"""
        keys = key.split('.')
        config = self._config
        
        # Navigiere bis zum vorletzten Key
        for k in keys[:-1]:
            if k not in config:
                config[k] = {}
            config = config[k]
            
        # Setze den Wert
        config[keys[-1]] = value
        
    def get_section(self, section: str) -> Dict[str, Any]:
        """Holt eine komplette Konfigurationssektion"""
        return self.get(section, {})
        
    def update_section(self, section: str, values: Dict[str, Any]):
        """Aktualisiert eine Konfigurationssektion"""
        current = self.get_section(section)
        updated = self._deep_merge(current, values)
        self.set(section, updated)
        
    def _deep_merge(self, base: Dict, update: Dict) -> Dict:
        """Führt eine tiefe Zusammenführung von zwei Dictionaries durch"""
        result = base.copy()
        
        for key, value in update.items():
            if (key in result and 
                isinstance(result[key], dict) and 
                isinstance(value, dict)):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
                
        return result
        
    def validate(self) -> bool:
        """Validiert die aktuelle Konfiguration"""
        try:
            # Grundlegende Validierungen
            
            # Server-Konfiguration
            if not isinstance(self.get('server.port'), int):
                raise ValueError("server.port muss eine Zahl sein")
                
            if not (1 <= self.get('server.port') <= 65535):
                raise ValueError("server.port muss zwischen 1 und 65535 liegen")
                
            # AirPlay-Konfiguration  
            if not isinstance(self.get('airplay.port'), int):
                raise ValueError("airplay.port muss eine Zahl sein")
                
            if not (1 <= self.get('airplay.port') <= 65535):
                raise ValueError("airplay.port muss zwischen 1 und 65535 liegen")
                
            # Buffer-Zeit
            buffer_time = self.get('airplay.buffer_time')
            if not isinstance(buffer_time, (int, float)) or buffer_time < 0:
                raise ValueError("airplay.buffer_time muss eine positive Zahl sein")
                
            # Sample-Rate
            sample_rate = self.get('airplay.sample_rate')
            if sample_rate not in [44100, 48000, 88200, 96000]:
                raise ValueError("Ungültige Sample-Rate")
                
            # Synchronisation
            global_delay = self.get('synchronization.global_delay')
            if not isinstance(global_delay, (int, float)) or global_delay < 0:
                raise ValueError("synchronization.global_delay muss eine positive Zahl sein")
                
            logger.info("Konfiguration erfolgreich validiert")
            return True
            
        except Exception as e:
            logger.error(f"Konfigurationsvalidierung fehlgeschlagen: {e}")
            return False
            
    def reload(self):
        """Lädt die Konfiguration neu"""
        self.load_config()
        
    def __repr__(self):
        return f"ConfigManager(config_path='{self.config_path}')"