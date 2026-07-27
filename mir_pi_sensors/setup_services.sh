#!/bin/bash
# Usage:setup_services.sh <service_name> <pi_path>
# Ex:    setup_services.sh camera_server /home/pi/projets/sensors_servers

SERVICE_NAME="$1"
PI_PATH="$2"
SERVICE_FILE="${SERVICE_NAME}.service"
SERVICE_DST="/etc/systemd/system/${SERVICE_FILE}"
SERVICE_SRC="${PI_PATH}/${SERVICE_FILE}"

if systemctl is-enabled "${SERVICE_NAME}" >/dev/null 2>&1; then
    SERVICE_EXISTS=true
else
    SERVICE_EXISTS=false
fi

echo "[INFO] Copie du fichier de service..."
sudo cp "$SERVICE_SRC" "$SERVICE_DST" || exit 10

echo "[INFO] Rechargement de systemd..."
sudo systemctl daemon-reload || exit 11

if [ "$SERVICE_EXISTS" = true ]; then
    echo "[INFO] Redémarrage du service..."
    sudo systemctl restart "${SERVICE_NAME}" || exit 12
else
    echo "[INFO] Activation et démarrage du service..."
    sudo systemctl enable "${SERVICE_NAME}" || exit 13
    sudo systemctl start  "${SERVICE_NAME}" || exit 14
fi