#!/bin/bash

PI_PATH="$1"

cd "$PI_PATH"|| exit 1
if [ -d ".venv" ]; then
    echo "[INFO] Environnement virtuel existant."
else
    echo "[INFO] Création de l'environnement virtuel. Patientez..."
    python3 -m venv .venv --system-site-packages || exit 1
fi
echo "[INFO] Installation des dépendances. Patientez..."
.venv/bin/pip install -r requirements.in || exit 1

