# Entwicklung

[← Zurück zur README](../README.md)

## Lokale Umgebung

Voraussetzungen: Python 3.8+, `gstreamer1.0-dev`, `libavahi-compat-libdnssd-dev`, `python3-gi`, `python3-gi-cairo`.

```bash
cd airplay-multiroom-server
./scripts/dev-setup.sh
./start-dev.sh
```

`dev-setup.sh` prüft Systemabhängigkeiten, erstellt `venv`, installiert Abhängigkeiten plus pytest, pytest-cov, black, flake8, mypy, pre-commit, legt `config/dev-config.yaml` (Debug-Logging nach `./dev-logs/server.log`) sowie Hilfsskripte (`run-dev.sh`, `run-tests.sh`, `format-code.sh`), eine Test-Struktur, `.pre-commit-config.yaml` und optional Docker-Dateien an. `start-dev.sh` startet `python -m src --config <config> --debug` auf `http://localhost:5000`.

Discovery testen: `./venv/bin/python scripts/test-discovery.py` (30 s Suche nach `_airplay._tcp`, `_raop._tcp`, `_airport._tcp`).

## Code-Struktur

- `src/__init__.py` – Hauptklasse, Logging, CLI-Logik (`main`)
- `src/config_manager.py`, `airplay_receiver.py`, `audio_pipeline.py`, `device_manager.py`, `multiroom_coordinator.py`, `web_interface.py`
- `scripts/` – Betriebs- und Entwicklungsskripte

Bekannte Probleme: `src/__init__.py` enthält vorangestellte Shell-Befehle (Syntaxfehler) und muss bereinigt werden; ein `src/__main__.py` für `python -m src` fehlt im Repo; `audio_pipeline.py` importiert `from gi import pygobject`, was in aktuellen PyGObject-Versionen vermutlich fehlschlägt (Annahme).

## Tests

```bash
python -m pytest tests/
```

Im Repo ist kein `tests/`-Ordner vorhanden; `dev-setup.sh` erzeugt nur einen Beispieltest für den `ConfigManager`. Hinweis: das generierte `pytest.ini` nutzt den Header `[tool:pytest]` (gilt für setup.cfg; in `pytest.ini` wäre `[pytest]` korrekt). Tests für Empfänger, Pipeline und Koordinator fehlen.

## Coding-Standards

- Formatierung mit `black`, Linting mit `flake8` (Pre-commit: `--max-line-length=88`, `--extend-ignore=E203,W503`), Typprüfung mit `mypy`.
- Kommentare, Logs und Docstrings sind auf Deutsch.
- Asynchrone Komponenten bieten `initialize`, `start`, `stop`.

## Release-Ablauf

Es gibt keinen automatisierten Release-Prozess (keine CI im Repo). Vorschlag (Annahme): Änderungen in `CHANGELOG.md` eintragen, Version taggen (`git tag vX.Y.Z`), pushen; Auslieferung auf Server per `scripts/update-local.sh` oder `scripts/update-server.sh`.
