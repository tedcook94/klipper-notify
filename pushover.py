import os
import requests
import tempfile

PUSHOVER_ENDPOINT = "https://api.pushover.net/1/messages.json"

def send_pushover(user_key, app_token, message, title=None, image_bytes=None, device=None):
    payload = {
        "user": user_key,
        "token": app_token,
        "message": message,
    }
    if title:
        payload["title"] = title
    if device:
        payload["device"] = device

    image = None
    if image_bytes:
        tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".jpg")
        tmp.write(image_bytes)
        tmp.close()
        image = open(tmp.name, "rb")

    r = requests.post(PUSHOVER_ENDPOINT, data=payload, files={"attachment": image}, timeout=10)
    r.raise_for_status()

    if image:
        image.close()
        os.remove(tmp.name)
