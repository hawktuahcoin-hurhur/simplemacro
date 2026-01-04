import io
import json
import time
from PIL import Image, ImageDraw, ImageFont
import requests

WEBHOOK_URL = "https://discord.com/api/webhooks/1385747037022064814/xq0b2GRuF39oQAQHsKw4ZZz2fQqfYQkgZ2yC2DijtcyXRbRCyptgwec05_DLnHqtDqB4"
MENTION_USER = "prince_harry_"

# Create a simple PNG screenshot-like image in-memory
w, h = 800, 200
img = Image.new("RGBA", (w, h), (30, 30, 30, 255))
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("arial.ttf", 20)
except Exception:
    font = ImageFont.load_default()
text = f"SimpleMacro screenshot test - {time.strftime('%Y-%m-%d %H:%M:%S')}"
d.text((20, 80), text, fill=(230,230,230), font=font)

buf = io.BytesIO()
img.save(buf, format="PNG")
buf.seek(0)

# Build payload: include plaintext @username (won't ping unless you give user ID), embed, and use attachment for image
content = f"@{MENTION_USER} Screenshot + embed test from SimpleMacro."
embed = {
    "title": "SimpleMacro Detection",
    "description": "This is a test embed with an attached screenshot.",
    "color": 0x1ABC9C,
    "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S")
}

payload = {
    "content": content,
    "embeds": [embed],
    # We do not include user IDs, so Discord will not convert the username into a mention ping.
    "allowed_mentions": {"parse": []}
}

files = {
    "file": ("screenshot.png", buf.getvalue(), "image/png")
}

# When sending an attachment that should be shown inside the embed, Discord requires the embed to point to 'attachment://filename'
payload["embeds"][0]["image"] = {"url": "attachment://screenshot.png"}

try:
    resp = requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files, timeout=15)
    print("HTTP", resp.status_code)
    print(resp.text)
    resp.raise_for_status()
except Exception as e:
    print("Error sending webhook:", e)
    raise
