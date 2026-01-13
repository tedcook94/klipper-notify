#!/usr/bin/env bash
set -e

SERVICE_NAME="klipper-notify"
SYSTEMD_PATH="/etc/systemd/system/$SERVICE_NAME.service"
MOONRAKER_CONF_PATH="$HOME/printer_data/config/moonraker.conf"

echo "=== Klipper Notify Uninstaller ==="

# Stop service
if systemctl is-active --quiet "$SERVICE_NAME"; then
    sudo systemctl stop "$SERVICE_NAME"
fi

if systemctl is-enabled --quiet "$SERVICE_NAME"; then
    sudo systemctl disable "$SERVICE_NAME"
fi

# Remove systemd unit
if [ -f "$SYSTEMD_PATH" ]; then
    echo "Removing systemd service"
    sudo rm "$SYSTEMD_PATH"
    sudo systemctl daemon-reload
fi

# Remove Update Manager block
if grep -q "\[update_manager $SERVICE_NAME\]" "$MOONRAKER_CONF_PATH"; then
    echo "Removing Update Manager entry"
    sed -i "/\[update_manager $SERVICE_NAME\]/,/^$/d" "$MOONRAKER_CONF_PATH"
fi

# Restart Moonraker
echo "Restarting Moonraker"
sudo systemctl restart moonraker

echo ""
echo "Uninstall complete!"
echo ""
echo "NOTE:"
echo " - Repo files were not deleted"
echo " - config.yaml was preserved"
