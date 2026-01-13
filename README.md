# klipper-notify

Configurable push notifications for Klipper/Moonraker via Pushover. Get notified when prints start, complete, fail, or reach specific milestones during the print process.

## Features

- Print status notifications (start, complete, cancelled, error)
- Webcam snapshots included with notifications
- Periodic progress updates (configurable interval)
- First layer completion notification
- Fully configurable via YAML
- Auto-updates via Moonraker Update Manager

## Requirements

- Klipper/Moonraker setup
- Python 3.7+
- [Pushover](https://pushover.net/) account

## Installation

### 1. Clone the repository

SSH into your Klipper host (Raspberry Pi, etc.) and run:

```bash
cd ~
git clone https://github.com/tedcook94/klipper-notify.git
cd klipper-notify
```

### 2. Run the installer

```bash
./install.sh
```

The installer will:
- Create `config.yaml` from the example
- Install Python dependencies
- Register with Moonraker Update Manager
- Install and start the systemd service

### 3. Configure Pushover credentials

Get your Pushover credentials:
1. Sign up at [pushover.net](https://pushover.net/)
2. Note your **User Key** from the dashboard
3. Create a new application to get an **App Token**

Edit the config file:

```bash
nano ~/klipper-notify/config.yaml
```

Update the Pushover section with your credentials:

```yaml
pushover:
  user_key: "your_user_key_here"
  app_token: "your_app_token_here"
  # device: "optional_device_name"  # Uncomment to send to specific device
```

### 4. Restart the service

```bash
sudo systemctl restart klipper-notify
```

### 5. Verify it's running

Check the service status:

```bash
sudo systemctl status klipper-notify
```

Watch live logs:

```bash
journalctl -u klipper-notify -f
```

## Configuration

All settings are in `~/klipper-notify/config.yaml`. Any omitted fields will use sensible defaults.

### Full Configuration Example

```yaml
pushover:
  user_key: "YOUR_USER_KEY"
  app_token: "YOUR_APP_TOKEN"
  device: "iPhone"  # Optional: specific device name

notifications:
  printer_name: "Voron"
  progress_interval_minutes: 60  # How often to send progress updates (0 = disabled)
  notify_after_first_layer: true
  notify_print_start: false
  notify_print_end: true
  notify_print_cancelled: true
  notify_print_error: true

webcam:
  snapshot_url: "http://localhost:8080/webcam?action=snapshot"
  # Set to null to disable snapshots

logging_level: INFO  # DEBUG, INFO, WARNING, ERROR
```

### Notification Types

| Setting | Description | Default |
|---------|-------------|---------|
| `notify_print_start` | Notification when print starts | `false` |
| `notify_print_end` | Notification when print completes | `true` |
| `notify_print_cancelled` | Notification when print is cancelled | `true` |
| `notify_print_error` | Notification on print error | `true` |
| `notify_after_first_layer` | Notification after first layer completes | `true` |
| `progress_interval_minutes` | Progress notification interval (0 = disabled) | `60` |

### Webcam Snapshots

If you have a webcam configured, snapshots will be attached to notifications. Common URLs:

- **Crowsnest/MJPG-Streamer**: `http://localhost:8080/webcam?action=snapshot`
- **MainsailOS/FluiddPI**: Usually the same as above
- **Obico**: Check your Obico webcam settings

Set `snapshot_url: null` to disable snapshots entirely.

## Updating

Updates are managed through Moonraker's Update Manager. Check for updates in:

- **Mainsail**: Machine tab → Update Manager
- **Fluidd**: Settings → Update Manager
- **Command line**: `cd ~/klipper-notify && git pull && sudo systemctl restart klipper-notify`

## Uninstalling

```bash
cd ~/klipper-notify
bash uninstall.sh
```

This will:
- Stop and remove the systemd service
- Remove the Moonraker Update Manager entry
- Keep the repository folder (delete manually if desired)
