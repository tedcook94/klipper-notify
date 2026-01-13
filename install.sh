#!/usr/bin/env bash
set -e

SERVICE_NAME="klipper-notify"
INSTALL_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MOONRAKER_CONF_PATH="$HOME/printer_data/config/moonraker.conf"
PYTHON_BIN="$(which python3)"

echo "=== Klipper Notify Installer ==="

# Config file
if [ ! -f "$INSTALL_DIR/config.yaml" ]; then
	echo "Creating config.yaml from config.example.yaml"
	cp "$INSTALL_DIR/config.example.yaml" "$INSTALL_DIR/config.yaml"
else
	echo "config.yaml already exists, skipping"
fi

# Python deps
echo "Installing Python dependencies"
$PYTHON_BIN -m pip install --user -r "$INSTALL_DIR/requirements.txt"

echo "Registering with Moonraker Update Manager"

# Update Manager config
if ! grep -q "\[update_manager $SERVICE_NAME\]" "$MOONRAKER_CONF_PATH"; then
    cat <<EOF >> "$MOONRAKER_CONF_PATH"

[update_manager $SERVICE_NAME]
type: git_repo
path: ~/$SERVICE_NAME
origin: https://github.com/tedcook94/klipper-notify.git
managed_services: $SERVICE_NAME
primary_branch: main
EOF
else
    echo "Update Manager entry already exists"
fi

# systemd service
echo "Installing systemd service"

sudo tee "/etc/systemd/system/$SERVICE_NAME.service" > /dev/null <<EOF
[Unit]
Description=Klipper Notify Service
After=network.target moonraker.service
Requires=moonraker.service

[Service]
Type=simple
User=$(whoami)
WorkingDirectory=$INSTALL_DIR
ExecStart=$PYTHON_BIN $INSTALL_DIR/notify.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl restart "$SERVICE_NAME"

# Restart Moonraker
echo "Restarting Moonraker"
sudo systemctl restart moonraker

echo ""
echo "Installation complete!"
echo ""
echo "Next steps:"
echo "1. Edit config.yaml with your Pushover credentials"
echo "2. Restart klipper-notify with \`sudo systemctl restart $SERVICE_NAME\`"
echo "3. Watch logs with:"
echo "    journalctl -u $SERVICE_NAME -f"
