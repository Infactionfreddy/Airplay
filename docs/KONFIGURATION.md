# Konfiguration

[← Zurück zur README](../README.md)

## Konfigurationsdatei

Suchreihenfolge des `ConfigManager` (erster existierender Pfad): `/etc/airplay-multiroom/config.yaml`, `~/.config/airplay-multiroom/config.yaml`, `./config/config.yaml`, `./config.yaml`. Per CLI: `python -m src --config <pfad> [--debug]`. Dateiwerte werden tief mit den Standardwerten zusammengeführt; Werte lassen sich per Punkt-Notation lesen/setzen.

## Umgebungsvariablen

Der Code wertet keine Umgebungsvariablen aus. Die alte README erwähnt `DEBUG=1` per `systemctl edit`; im gezeigten Code ist dafür keine Auswertung erkennbar – nutze stattdessen `--debug`. Die systemd-Unit setzt `PATH` und `PYTHONPATH`.

## Optionen (Standardwerte)

| Schlüssel | Standard | Beschreibung |
|---|---|---|
| `server.name` | AirPlay Multiroom Server | Anzeigename |
| `server.host` / `server.port` | 0.0.0.0 / 5000 | Server-Bindung (validiert 1-65535) |
| `server.debug` | false | Debug-Flag |
| `airplay.service_name` | Multiroom Audio | Name des Empfängers |
| `airplay.port` | 5001 | RTSP-Port |
| `airplay.buffer_time` | 2.0 | Puffer (s), >= 0 |
| `airplay.sample_rate` | 44100 | erlaubt: 44100, 48000, 88200, 96000 |
| `airplay.bit_depth` / `channels` | 16 / 2 | Audioformat |
| `devices.auto_discovery` | true | mDNS-Erkennung |
| `devices.discovery_timeout` | 30 | Timeout (s) |
| `devices.max_connections` | 10 | max. Verbindungen |
| `devices.manual_devices` | [] | Liste mit name, host, port, enabled |
| `synchronization.global_delay` | 0.5 | globale Verzögerung (s), >= 0 |
| `synchronization.device_delays` | {} | Verzögerung je Gerätename |
| `synchronization.sync_algorithm` | advanced | Algorithmus |
| `synchronization.sync_tolerance` | 50 | Toleranz (Annahme: ms) |
| `audio.gstreamer.buffer_size` / `latency` | 8192 / low | GStreamer |
| `audio.quality.bitrate` / `compression` | 256 / lossless | Qualität |
| `network.mdns.enabled` / `domain` | true / local | mDNS |
| `network.timeouts.connection/read/write` | 10 / 30 / 30 | Timeouts (s) |
| `logging.level` | INFO | Log-Level |
| `logging.file` | null | optionale Logdatei |
| `logging.max_size` / `backup_count` | 10MB / 5 | Rotation (im gezeigten Code nicht genutzt) |
| `web.enabled` | true | Web-Interface an/aus |
| `web.host` / `web.port` | 0.0.0.0 / 5000 | Bindung |
| `web.security.auth_enabled` | false | Authentifizierung |
| `web.security.username` / `password` | – | Zugangsdaten; Standardwerte stehen im Code, unbedingt ändern und Auth aktivieren |
| `system.user` / `group` | airplay | Dienstbenutzer |
| `system.pid_file`, `working_directory` | – | Systempfade |
| `performance.thread_pool_size`, `max_memory_mb` | 4 / 512 | Ressourcen |
| `performance.audio_buffer.buffer_count/buffer_size` | 4 / 4096 | Audio-Puffer |

`network.ipv6_enabled` und `network.bind_address` tauchen nur als Shell-Snippet in `src/__init__.py` auf (für LXC ohne IPv6); ob sie ausgewertet werden, ist aus dem Code nicht ersichtlich.

## Beispiele

Manuelle Geräte:
```yaml
devices:
  auto_discovery: true
  manual_devices:
    - name: Wohnzimmer
      host: 192.168.1.100
      port: 7000
      enabled: true
```

Synchronisation:
```yaml
airplay:
  buffer_time: 2.0
synchronization:
  global_delay: 0.5
  device_delays:
    Küche: 0.1
```

Geräte-IPs ermitteln: `avahi-browse -t _raop._tcp -r` oder `avahi-browse -t _airplay._tcp -r`.

## Ports

| Port | Protokoll | Zweck |
|---|---|---|
| 5000 | TCP | Web-Interface |
| 5001 | TCP | AirPlay RTSP |
| 6000-6010 | UDP | RTP-Audio |
| 7000 | TCP | Ausgabe an AirPlay-Geräte |
| 5353 | UDP | mDNS |

## Hooks/Filter

Keine vorhanden. Intern können Output-Callbacks über `AudioPipeline.register_output_callback` registriert werden.
