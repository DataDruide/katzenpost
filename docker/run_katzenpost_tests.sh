#!/usr/bin/env bash
set -euo pipefail

# --- Konfiguration ---
KATZENPOST_DIR="/Users/marcelzimmermann/Projects/erebos-network/nym/katzenpost"
DOCKER_DIR="${KATZENPOST_DIR}/docker"
VENV_DIR="${KATZENPOST_DIR}/.venv"
PIGEONHOLE_SCRIPT="${DOCKER_DIR}/test_pigeonhole.py"
GNU_SED_PATH="/opt/homebrew/opt/gnu-sed/libexec/gnubin"
BOOTSTRAP_TIMEOUT=900
CONSENSUS_WAIT_MAX=900
PING_RETRIES=5
PING_RETRY_DELAY=60

GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $*"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

cd "${DOCKER_DIR}"
export PATH="${GNU_SED_PATH}:$PATH"

log_info "Stoppe laufendes Testnetzwerk (make stop)..."
make stop 2>/dev/null || true

log_info "Überspringe 'make clean' (Container und Daten bleiben erhalten)."

log_info "Starte Testnetzwerk (make start wait, Timeout ${BOOTSTRAP_TIMEOUT}s)..."
if ! timeout "${BOOTSTRAP_TIMEOUT}" make start wait; then
    log_error "Bootstrap innerhalb von ${BOOTSTRAP_TIMEOUT}s nicht abgeschlossen."
    log_error "Prüfe den Status mit: make status"
    exit 1
fi

log_info "Warte auf Consensus (max. ${CONSENSUS_WAIT_MAX}s)..."
elapsed=0
while ! make status 2>&1 | grep -q "Consensus made for epoch"; do
    if (( elapsed >= CONSENSUS_WAIT_MAX )); then
        log_error "Consensus innerhalb von ${CONSENSUS_WAIT_MAX}s nicht erreicht."
        make status || true
        exit 1
    fi
    sleep 15
    elapsed=$(( elapsed + 15 ))
    log_info "  ... noch kein Consensus (${elapsed}s vergangen)"
done
log_info "Consensus erreicht."

log_info "Führe Ping-Test aus (max. ${PING_RETRIES} Versuche)..."
ping_ok=0
for (( i=1; i<=PING_RETRIES; i++ )); do
    log_info "Ping-Versuch ${i}/${PING_RETRIES}..."
    if make run-ping 2>&1 | tee "/tmp/ping_attempt_${i}.log" | grep -q "Success rate is 100 percent"; then
        ping_ok=1
        log_info "Ping erfolgreich (100%)."
        break
    fi
    log_warn "Ping-Versuch ${i} fehlgeschlagen."
    if (( i < PING_RETRIES )); then
        log_info "Warte ${PING_RETRY_DELAY}s vor nächstem Versuch..."
        sleep "${PING_RETRY_DELAY}"
    fi
done

if (( ping_ok == 0 )); then
    log_error "Ping-Test nach ${PING_RETRIES} Versuchen fehlgeschlagen."
    log_error "Prüfe die Daemon-Verbindung mit:"
    log_error "  docker ps --format '{{.Names}}' | grep kpclientd"
    log_error "  docker exec <kpclientd-name> cat /mixnet-alpine/client/kpclientd.log | tail -20"
    exit 1
fi

log_info "Starte Pigeonhole-Test..."
if [[ ! -f "${PIGEONHOLE_SCRIPT}" ]]; then
    log_error "Pigeonhole-Skript nicht gefunden: ${PIGEONHOLE_SCRIPT}"
    exit 1
fi

if [[ -d "${VENV_DIR}" ]]; then
    source "${VENV_DIR}/bin/activate"
    log_info "Virtuelle Umgebung aktiviert: ${VENV_DIR}"
else
    log_warn "Keine virtuelle Umgebung gefunden (${VENV_DIR}), nutze System-Python."
fi

python3 "${PIGEONHOLE_SCRIPT}"
log_info "Pigeonhole-Test abgeschlossen."
