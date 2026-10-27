#!/usr/bin/env bash
set -euo pipefail

VENV_DIR="${1:-/Users/marcelzimmermann/Projects/erebos-network/nym/katzenpost/.venv}"
TCP_PY="${VENV_DIR}/lib/python3.15/site-packages/katzenpost_thinclient/transport/tcp.py"

if [[ ! -f "${TCP_PY}" ]]; then
    echo "[ERROR] tcp.py nicht gefunden: ${TCP_PY}" >&2
    exit 1
fi

if [[ ! -f "${TCP_PY}.orig" ]]; then
    cp "${TCP_PY}" "${TCP_PY}.orig"
    echo "[INFO] Backup angelegt: ${TCP_PY}.orig"
fi

if grep -q "socket.TCP_KEEPIDLE" "${TCP_PY}"; then
    sed -i '' -e 's/socket\.TCP_KEEPIDLE/getattr(socket, "TCP_KEEPIDLE", getattr(socket, "TCP_KEEPALIVE", 0x10))/g' "${TCP_PY}"
    echo "[INFO] Patch 1 angewendet: TCP_KEEPIDLE -> getattr(...)"
else
    echo "[INFO] Patch 1 bereits vorhanden oder nicht nötig."
fi

if grep -q "sock.connect((host, port))" "${TCP_PY}"; then
    sed -i '' -e '/sock\.connect((host, port))/d' "${TCP_PY}"
    echo "[INFO] Patch 2 angewendet: doppeltes sock.connect() entfernt."
else
    echo "[INFO] Patch 2 bereits vorhanden oder nicht nötig."
fi

python3 -c "import ast; ast.parse(open('${TCP_PY}').read())"
echo "[INFO] Syntax-Check OK. Patch abgeschlossen."
