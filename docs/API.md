# API

[← Zurück zur README](../README.md)

> Der Quelltext von `src/web_interface.py` lag der Doku nicht vor. Die REST-Endpunkte sind daher nur aus Skripten abgeleitet und unvollständig.

## HTTP (Web-Interface, Port 5000)

| Methode | Pfad | Beschreibung |
|---|---|---|
| GET | `/api/devices` | Liste der erkannten Geräte (verwendet in Update-Skripten: `curl -s http://localhost:5000/api/devices \| jq`) |
| GET | `/` | Web-Oberfläche (Health-Check im optionalen Dockerfile) |

Authentifizierung ist über `web.security.auth_enabled` konfigurierbar (Standard: aus).

## AirPlay-Empfänger (RTSP, Port `airplay.port`, Standard 5001)

| Methode | Verhalten |
|---|---|
| OPTIONS | Liefert unterstützte Methoden |
| ANNOUNCE | Erwartet `application/sdp`; SDP wird noch nicht geparst (TODO) |
| SETUP | Liest `server_port`, vergibt Session-ID (Zeitstempel), antwortet mit Transport-Header |
| RECORD | Ruft `coordinator.start_audio_stream(client_id, session)` auf |
| FLUSH | Ruft `coordinator.flush_audio_buffer(client_id)` auf |
| TEARDOWN | Ruft `coordinator.stop_audio_stream(client_id)` auf und trennt den Client |
| sonstige | 501 Not Implemented |

## Python-Schnittstellen

**ConfigManager:** `get(key, default)`, `set(key, value)`, `get_section(section)`, `update_section(section, values)`, `load_config()`, `save_config(path)`, `validate()`, `reload()`.

**AudioPipeline:** `add_stream(stream_id, source_info)`, `remove_stream(stream_id)`, `set_active_stream(stream_id)`, `add_audio_data(stream_id, data, timestamp)`, `register_output_callback(output_id, callback)`, `unregister_output_callback(output_id)`, `flush_all_streams()`, `get_stats()`.

**GStreamerPipeline:** `add_output(output_id, sink_element)`, `remove_output(output_id)`, `push_audio_data(data)`.

**AirPlayMultiroomServer:** `initialize()`, `start()`, `stop()`, `run()`.

**CLI:** `python -m src --config <pfad> [--debug]`
