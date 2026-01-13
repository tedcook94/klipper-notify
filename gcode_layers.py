import logging
import os

def get_second_layer_offset(gcode_path):
    log = logging.getLogger("klipper-notify")
    gcode_path = os.path.expanduser(gcode_path)
    layer_count = 0
    byte_offset = 0

    if not os.path.exists(gcode_path):
        log.warning("G-code file not found: %s", gcode_path)
        return []

    with open(gcode_path, "r", errors="ignore") as f:
        for line in f:
            if line.startswith(";AFTER_LAYER_CHANGE"):
                layer_count += 1
            if layer_count >= 2:
                log.info("Found second layer offset of %d", byte_offset)
                return byte_offset

            byte_offset += len(line)

    return byte_offset

