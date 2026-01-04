import io
import json
import time
from PIL import Image, ImageDraw, ImageFont
import requests

WEBHOOK_URL = "https://discord.com/api/webhooks/1385747037022064814/xq0b2GRuF39oQAQHsKw4ZZz2fQqfYQkgZ2yC2DijtcyXRbRCyptgwec05_DLnHqtDqB4"
USER_ID = "1175202749592379476"
ITEM_NAME = "TestItem"

# Create a simple PNG screenshot-like image in-memory
w, h = 800, 200
img = Image.new("RGBA", (w, h), (30, 30, 30, 255))
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("arial.ttf", 20)
except Exception:
    font = ImageFont.load_default()
text = f"SimpleMacro item screenshot - {time.strftime('%Y-%m-%d %H:%M:%S')}"
d.text((20, 80), text, fill=(230,230,230), font=font)

buf = io.BytesIO()
img.save(buf, format="PNG")
buf.seek(0)

# Build content and embed matching the item webhook format
content = f"<@{USER_ID}> Item ({ITEM_NAME}) obtained!"
embed = {
    "title": f"Item ({ITEM_NAME}) obtained!",
    "description": f"Item: {ITEM_NAME}",
    "image": {"url": "attachment://screenshot.png"}
}

payload = {
    "content": content,
    "embeds": [embed],
    "allowed_mentions": {"users": [USER_ID]}
}

files = {
    "file": ("screenshot.png", buf.getvalue(), "image/png")
}

try:
    resp = requests.post(WEBHOOK_URL, data={"payload_json": json.dumps(payload)}, files=files, timeout=15)
    print("HTTP", resp.status_code)
    print(resp.text)
    resp.raise_for_status()
except Exception as e:
    print("Error sending webhook:", e)
    raise
