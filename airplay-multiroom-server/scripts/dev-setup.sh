#!/bin/bash

# AirPlay Multiroom Server - Entwicklungs-Hilfsskript
# Verwendung: ./dev-setup.sh

set -e

# Farben für Output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Prüfe ob im Projektverzeichnis
check_project_dir() {
    if [[ ! -f "requirements.txt" ]] || [[ ! -d "src" ]]; then
        log_error "Bitte aus dem Projektverzeichnis ausführen"
        exit 1
    fi
}

# Python-Umgebung einrichten
setup_python_env() {
    log_info "Richte Python-Entwicklungsumgebung ein..."
    
    # Virtual Environment erstellen falls nicht vorhanden
    if [[ ! -d "venv" ]]; then
        log_info "Erstelle Virtual Environment..."
        python3 -m venv venv
    fi
    
    # Virtual Environment aktivieren
    source venv/bin/activate
    
    # Pip aktualisieren
    pip install --upgrade pip
    
    # Dependencies installieren
    log_info "Installiere Python-Dependencies..."
    pip install -r requirements.txt
    
    # Entwicklungs-Dependencies
    log_info "Installiere Entwicklungs-Dependencies..."
    pip install \
        pytest \
        pytest-asyncio \
        pytest-cov \
        black \
        flake8 \
        mypy \
        pre-commit
    
    log_success "Python-Umgebung eingerichtet"
}

# System-Dependencies prüfen
check_system_deps() {
    log_info "Prüfe System-Dependencies..."
    
    local missing_deps=()
    
    # Python-Version prüfen
    if ! python3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 8) else 1)" 2>/dev/null; then
        missing_deps+=("python3 (>= 3.8)")
    fi
    
    # GStreamer prüfen
    if ! pkg-config --exists gstreamer-1.0; then
        missing_deps+=("gstreamer-1.0-dev")
    fi
    
    # Avahi prüfen
    if ! pkg-config --exists avahi-compat-libdns_sd; then
        missing_deps+=("libavahi-compat-libdnssd-dev")
    fi
    
    if [[ ${#missing_deps[@]} -gt 0 ]]; then
        log_error "Fehlende System-Dependencies:"
        for dep in "${missing_deps[@]}"; do
            echo "  - $dep"
        done
        echo
        log_info "Installieren mit:"
        log_info "  sudo apt update"
        log_info "  sudo apt install python3-dev gstreamer1.0-dev libavahi-compat-libdnssd-dev python3-gi python3-gi-cairo"
        exit 1
    fi
    
    log_success "Alle System-Dependencies vorhanden"
}

# Konfiguration für Entwicklung erstellen
setup_dev_config() {
    log_info "Erstelle Entwicklungs-Konfiguration..."
    
    local dev_config="config/dev-config.yaml"
    
    if [[ ! -f "$dev_config" ]]; then
        cp config/config.yaml "$dev_config"
        
        # Entwicklungsspezifische Änderungen
        cat >> "$dev_config" << EOF

# Entwicklungs-Überschreibungen
logging:
  level: "DEBUG"
  file: "./dev-logs/server.log"

server:
  debug: true

web:
  port: 5000
  security:
    auth_enabled: false

devices:
  discovery_timeout: 10
  
performance:
  max_memory_mb: 256
EOF
        
        # Log-Verzeichnis erstellen
        mkdir -p dev-logs
        
        log_success "Entwicklungs-Konfiguration erstellt: $dev_config"
    else
        log_info "Entwicklungs-Konfiguration bereits vorhanden"
    fi
}

# Pre-commit Hooks einrichten
setup_precommit() {
    log_info "Richte Pre-commit Hooks ein..."
    
    # Pre-commit Konfiguration erstellen
    cat > .pre-commit-config.yaml << 'EOF'
repos:
  - repo: https://github.com/pre-commit/pre-commit-hooks
    rev: v4.4.0
    hooks:
      - id: trailing-whitespace
      - id: end-of-file-fixer
      - id: check-yaml
      - id: check-added-large-files

  - repo: https://github.com/psf/black
    rev: 23.3.0
    hooks:
      - id: black
        language_version: python3

  - repo: https://github.com/pycqa/flake8
    rev: 6.0.0
    hooks:
      - id: flake8
        args: [--max-line-length=88, --extend-ignore=E203,W503]

  - repo: https://github.com/pre-commit/mirrors-mypy
    rev: v1.3.0
    hooks:
      - id: mypy
        additional_dependencies: [types-PyYAML]
EOF

    # Pre-commit installieren
    if [[ -f "venv/bin/pre-commit" ]]; then
        venv/bin/pre-commit install
        log_success "Pre-commit Hooks installiert"
    fi
}

# Entwicklungs-Hilfsskripte erstellen
create_dev_scripts() {
    log_info "Erstelle Entwicklungs-Hilfsskripte..."
    
    # Run-Script
    cat > run-dev.sh << 'EOF'
#!/bin/bash
# Entwicklungsserver starten

cd "$(dirname "$0")"
source venv/bin/activate
export PYTHONPATH="$(pwd)"
python -m src --config config/dev-config.yaml --debug
EOF
    chmod +x run-dev.sh
    
    # Test-Script
    cat > run-tests.sh << 'EOF'
#!/bin/bash
# Tests ausführen

cd "$(dirname "$0")"
source venv/bin/activate
export PYTHONPATH="$(pwd)"

# Unit Tests
python -m pytest tests/ -v --cov=src --cov-report=html --cov-report=term

# Code-Qualität
echo -e "\n=== Code Style Check ==="
python -m black --check src/
python -m flake8 src/

echo -e "\n=== Type Check ==="
python -m mypy src/ --ignore-missing-imports
EOF
    chmod +x run-tests.sh
    
    # Format-Script
    cat > format-code.sh << 'EOF'
#!/bin/bash
# Code formatieren

cd "$(dirname "$0")"
source venv/bin/activate

echo "Formatiere Python-Code..."
python -m black src/ tests/

echo "Sortiere Imports..."
python -m isort src/ tests/

echo "Code formatiert!"
EOF
    chmod +x format-code.sh
    
    log_success "Entwicklungs-Scripts erstellt"
}

# Test-Verzeichnis erstellen
create_test_structure() {
    log_info "Erstelle Test-Struktur..."
    
    mkdir -p tests
    
    # Test-Init
    cat > tests/__init__.py << 'EOF'
"""Tests für AirPlay Multiroom Server"""
EOF

    # Beispiel-Test
    cat > tests/test_config_manager.py << 'EOF'
"""Tests für ConfigManager"""
import pytest
import tempfile
from pathlib import Path
import yaml

from src.config_manager import ConfigManager


class TestConfigManager:
    def test_default_config_loading(self):
        """Test laden der Standard-Konfiguration"""
        config = ConfigManager()
        
        # Grundlegende Werte prüfen
        assert config.get('server.name') == 'AirPlay Multiroom Server'
        assert config.get('server.port') == 5000
        assert config.get('airplay.port') == 5001
        
    def test_config_file_loading(self):
        """Test laden einer Konfigurationsdatei"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            test_config = {
                'server': {
                    'name': 'Test Server',
                    'port': 6000
                }
            }
            yaml.dump(test_config, f)
            config_path = f.name
            
        try:
            config = ConfigManager(config_path)
            assert config.get('server.name') == 'Test Server'
            assert config.get('server.port') == 6000
            # Default-Werte sollten erhalten bleiben
            assert config.get('airplay.port') == 5001
        finally:
            Path(config_path).unlink()
            
    def test_config_validation(self):
        """Test Konfigurationsvalidierung"""
        config = ConfigManager()
        assert config.validate() is True
        
        # Ungültigen Wert setzen
        config.set('server.port', 'invalid')
        assert config.validate() is False
        
    def test_get_set_methods(self):
        """Test Get/Set-Methoden"""
        config = ConfigManager()
        
        # Wert setzen und abrufen
        config.set('test.value', 'hello')
        assert config.get('test.value') == 'hello'
        
        # Nested-Werte
        config.set('nested.deep.value', 42)
        assert config.get('nested.deep.value') == 42
EOF

    # pytest-Konfiguration
    cat > pytest.ini << 'EOF'
[tool:pytest]
testpaths = tests
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
filterwarnings =
    ignore::DeprecationWarning
    ignore::PendingDeprecationWarning
EOF

    log_success "Test-Struktur erstellt"
}

# Docker-Unterstützung (optional)
setup_docker() {
    log_info "Erstelle Docker-Konfiguration..."
    
    # Dockerfile
    cat > Dockerfile << 'EOF'
FROM debian:bookworm-slim

# System-Dependencies installieren
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    python3-gi \
    python3-gi-cairo \
    gstreamer1.0-tools \
    gstreamer1.0-plugins-base \
    gstreamer1.0-plugins-good \
    gstreamer1.0-plugins-bad \
    gstreamer1.0-alsa \
    libgstreamer1.0-dev \
    libgstreamer-plugins-base1.0-dev \
    gir1.2-gstreamer-1.0 \
    avahi-daemon \
    avahi-utils \
    libnss-mdns \
    libavahi-compat-libdnssd-dev \
    alsa-utils \
    && rm -rf /var/lib/apt/lists/*

# Benutzer erstellen
RUN useradd --system --shell /bin/false --home-dir /app airplay

# Arbeitsverzeichnis
WORKDIR /app

# Python-Dependencies
COPY requirements.txt .
RUN python3 -m pip install --no-cache-dir -r requirements.txt

# Application kopieren
COPY src/ ./src/
COPY config/ ./config/
COPY web/ ./web/

# Berechtigungen
RUN chown -R airplay:airplay /app
USER airplay

# Ports exponieren
EXPOSE 5000 5001 6000-6010/udp 7000

# Health-Check
HEALTHCHECK --interval=30s --timeout=10s --start-period=30s --retries=3 \
    CMD curl -f http://localhost:5000/ || exit 1

# Startkommando
CMD ["python3", "-m", "src", "--config", "config/config.yaml"]
EOF

    # Docker Compose
    cat > docker-compose.yml << 'EOF'
version: '3.8'

services:
  airplay-multiroom:
    build: .
    container_name: airplay-multiroom-server
    restart: unless-stopped
    
    # Netzwerk für mDNS
    network_mode: host
    
    # Volumes
    volumes:
      - ./config:/app/config:ro
      - airplay-logs:/var/log/airplay-multiroom
      
    # Umgebungsvariablen
    environment:
      - PYTHONUNBUFFERED=1
      
    # Audio-Zugriff
    devices:
      - /dev/snd:/dev/snd
      
    # Capabilities für Audio
    cap_add:
      - SYS_NICE
      
volumes:
  airplay-logs:
EOF

    # .dockerignore
    cat > .dockerignore << 'EOF'
venv/
__pycache__/
*.pyc
.git/
.gitignore
dev-logs/
tests/
*.md
.pre-commit-config.yaml
run-*.sh
format-code.sh
EOF

    log_success "Docker-Konfiguration erstellt"
}

# Hauptfunktion
main() {
    echo "=== AirPlay Multiroom Server - Entwicklungsumgebung Setup ==="
    echo
    
    check_project_dir
    check_system_deps
    setup_python_env
    setup_dev_config
    setup_precommit
    create_dev_scripts
    create_test_structure
    
    # Optional: Docker Setup
    read -p "Docker-Unterstützung einrichten? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        setup_docker
    fi
    
    echo
    log_success "=== Entwicklungsumgebung erfolgreich eingerichtet! ==="
    echo
    log_info "Verfügbare Kommandos:"
    log_info "  ./run-dev.sh          - Entwicklungsserver starten"
    log_info "  ./run-tests.sh        - Tests ausführen"
    log_info "  ./format-code.sh      - Code formatieren"
    echo
    log_info "Nächste Schritte:"
    log_info "  1. Virtual Environment aktivieren: source venv/bin/activate"
    log_info "  2. Entwicklungsserver starten: ./run-dev.sh"
    log_info "  3. Tests ausführen: ./run-tests.sh"
    echo
    log_info "Konfiguration bearbeiten: config/dev-config.yaml"
    log_info "Web-Interface: http://localhost:5000"
}

# Script ausführen
main "$@"