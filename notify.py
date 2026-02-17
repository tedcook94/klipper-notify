import logging
import sys

def setup_logging(level: str = "INFO"):
    root = logging.getLogger()
    root.setLevel(level)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    formatter = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    )
    handler.setFormatter(formatter)

    # Remove existing handlers (important!)
    root.handlers.clear()
    root.addHandler(handler)

# TEMP default before config is loaded
setup_logging("INFO")
log = logging.getLogger("klipper-notify")

import json
import requests
import threading
import time
import websocket
import yaml
from pathlib import Path

from gcode_layers import get_second_layer_offset
from pushover import send_pushover

MOONRAKER_HTTP = "http://localhost:7125"
MOONRAKER_WS = "ws://localhost:7125/websocket"
CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"

DEFAULT_CONFIG = {
    "pushover": {
        "user_key": "",
        "app_token": "",
        "device": None,
    },
    "notifications": {
        "printer_name": "Printer",
        "progress_interval_minutes": 60,
        "notify_after_first_layer": True,
        "notify_print_start": False,
        "notify_print_end": True,
        "notify_print_cancelled": True,
        "notify_print_error": True,
    },
    "webcam": {
        "snapshot_url": None,
    },
    "logging_level": "INFO",
}


def deep_merge(base, override):
    """Recursively merge override dict into base dict."""
    result = base.copy()
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_config():
    if not CONFIG_PATH.exists():
        log.warning("User config not found, using default")
        user_cfg = {}
    else:
        with open(CONFIG_PATH, "r") as f:
            user_cfg = yaml.safe_load(f) or {}
            log.info("Loaded config.yaml")

    cfg = deep_merge(DEFAULT_CONFIG, user_cfg)

    if not cfg["pushover"]["user_key"] or not cfg["pushover"]["app_token"]:
        raise RuntimeError("Pushover user_key and app_token must be provided")

    return cfg

class NotifyService:
    def __init__(self, config):
        self.cfg = config
        self.reset_state()

    def reset_state(self):
        self.state = {
            "last_progress_sent": 0,
            "first_layer_complete": False,
            "second_layer_offset": 0,
            "last_print_state": "standby",
        }

    def snapshot(self):
        url = self.cfg["webcam"]["snapshot_url"]
        if url is None:
            log.debug("No snapshot URL configured")
            return None

        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.content

    def query(self, objects):
        r = requests.get(
            f"{MOONRAKER_HTTP}/printer/objects/query",
            params={o: "" for o in objects},
            timeout=5,
        )
        r.raise_for_status()
        return r.json()["result"]["status"]

    def wait_for_klipper_ready(self):
        log.info("Waiting for Klipper to be ready...")
        while True:
            try:
                r = requests.get(f"{MOONRAKER_HTTP}/server/info", timeout=5)
                r.raise_for_status()
                info = r.json()["result"]
                klippy_state = info.get("klippy_state")
                
                if klippy_state == "ready":
                    log.info("Klipper is ready")
                    return
                else:
                    log.info("Klipper state is '%s', waiting...", klippy_state)
                    time.sleep(2)
            except Exception:
                log.exception("Error checking Klipper status, retrying")
                time.sleep(5)

    def initialize_print_state(self):
        try:
            status = self.query(["print_stats"])
            current_state = status.get("print_stats", {}).get("state", "standby")
            self.state["last_print_state"] = current_state
            log.info("Initialized print state: %s", current_state)
        except Exception:
            log.exception("Failed to initialize print state, defaulting to standby")
            self.state["last_print_state"] = "standby"

    def pushover(self, title, message, image=None):
        log.info("Sending notification: %s", title)
        device = self.cfg["pushover"].get("device")
        send_pushover(
            self.cfg["pushover"]["user_key"],
            self.cfg["pushover"]["app_token"],
            message,
            title=title,
            image_bytes=image,
            device=device if device else None,
        )

    def handle_progress(self):
        log.debug("Checking for progress")
        status = self.query(["print_stats", "virtual_sdcard", "toolhead"])
        for key in ("print_stats", "virtual_sdcard", "toolhead"):
            if key not in status:
                log.warning("Missing key '%s' in Moonraker status: %s", key, status)
                return
        ps = status["print_stats"]

        if ps["state"] != "printing":
            return

        elapsed = ps["total_duration"]
        minutes = int(elapsed // 60)
        interval = self.cfg["notifications"]["progress_interval_minutes"]

        if minutes > self.state["last_progress_sent"] and minutes % interval == 0:
            if interval <= 0:
                log.info("Skipping print progress notification")
            else:
                progress = status["virtual_sdcard"]["progress"] * 100
                eta = elapsed * (1 / max(status["virtual_sdcard"]["progress"], 0.01) - 1)

                msg = (
                    f"{minutes // 60}h {minutes % 60}m elapsed\n"
                    f"Progress: {progress:.1f}%\n"
                    f"ETA: {int(eta // 3600)}h {int((eta % 3600) // 60)}m"
                ) 

                self.pushover(
                    f"{self.cfg['notifications']['printer_name']} - Print Progress",
                    msg,
                    image=self.snapshot(),
                )

                self.state["last_progress_sent"] = minutes

        if not self.state["first_layer_complete"]:
            if self.state["second_layer_offset"] and status["virtual_sdcard"].get("file_position") >= self.state["second_layer_offset"]:
                if self.cfg["notifications"]["notify_after_first_layer"]:
                    self.pushover(
                        f"{self.cfg['notifications']['printer_name']} - First Layer Complete",
                        "First layer complete",
                        image=self.snapshot(),
                    )
                else:
                    log.info("Skiping first layer complete notification")

                self.state["first_layer_complete"] = True

    def poll_loop(self):
        while True:
            try:
                self.handle_progress()
            except Exception:
                log.exception("Poll error")
            time.sleep(10)

    def ws_subscribe(self, ws):
        log.info("Websocket connected")

        subscribe_msg = {
            "jsonrpc": "2.0",
            "method": "printer.objects.subscribe",
            "params": {
                "objects": {
                    "print_stats": None,
                    "virtual_sdcard": None,
                    "toolhead": None,
                },
            },
            "id": 1,
        }

        ws.send(json.dumps(subscribe_msg))
        log.info("Subscribed to printer objects")

    def ws_handler(self, ws, message):
        try:
            log.debug("Websocket event: %s", message)
            data = json.loads(message)
            method = data.get("method")

            if method != "notify_status_update" :
                return

            params = data["params"][0]
            if "print_stats" not in params:
                return

            new_print_state = params["print_stats"].get("state")
            if not new_print_state:
                return

            last_print_state = self.state["last_print_state"]
            if new_print_state == last_print_state:
                return

            log.info("Print state has changed: %s -> %s", last_print_state, new_print_state)

            self.state["last_print_state"] = new_print_state

            if new_print_state == "printing":
                gcode = params.get("virtual_sdcard", {}).get("file_path")
                if gcode:
                    self.state["second_layer_offset"] = get_second_layer_offset(gcode)
                else:
                    log.warning("G-code filename not found")
                if self.cfg["notifications"]["notify_print_start"]:
                    self.pushover(
                        f"{self.cfg['notifications']['printer_name']} - Print Started",
                        f"Started: {gcode}",
                        image=self.snapshot(),
                    )
                else:
                    log.info("Skipping print start notification")

            elif new_print_state == "complete":
                if self.cfg["notifications"]["notify_print_end"]:
                    self.pushover(
                        f"{self.cfg['notifications']['printer_name']} - Print Complete",
                        "Print completed successfully",
                        image=self.snapshot(),
                    )
                else:
                    log.info("Skipping print complete notification")
                self.reset_state()
    
            elif new_print_state == "cancelled":
                if self.cfg["notifications"]["notify_print_cancelled"]:
                    self.pushover(
                        f"{self.cfg['notifications']['printer_name']} - Print Cancelled",
                        "Print cancelled by user",
                        image=self.snapshot(),
                    )
                else:
                    log.info("Skipping print cancelled notification")
                self.reset_state()
    
            elif new_print_state == "error":
                if self.cfg["notifications"]["notify_print_error"]:
                    error_msg = params.get("message", "Unknown error")
                    self.pushover(
                        f"{self.cfg['notifications']['printer_name']} - Print Error",
                        error_msg,
                        image=self.snapshot(),
                    )
                else:
                    log.info("Skipping print error notification")
                self.reset_state()
        except Exception:
            log.exception("Websocket handler error")

    def websocket_loop(self):
        self.wait_for_klipper_ready()
        self.initialize_print_state()
        
        while True:
            try:
                log.info("Connecting to Moonraker websocket")
                ws = websocket.WebSocketApp(
                    MOONRAKER_WS,
                    on_open=self.ws_subscribe,
                    on_message=self.ws_handler,
                )
                ws.run_forever()
            except Exception:
                log.exception("Websocket disconnected, retrying")
                time.sleep(5)

def main():
    cfg = load_config()
    log_level = cfg.get("logging_level", "INFO").upper()
    setup_logging(log_level)

    log = logging.getLogger("klipper-notify")
    log.info("Logging initialized at %s level", log_level)

    log.info("Starting klipper-notify")

    service = NotifyService(cfg)

    threading.Thread(target=service.poll_loop, daemon=True).start()
    service.websocket_loop()

if __name__ == "__main__":
    main()
