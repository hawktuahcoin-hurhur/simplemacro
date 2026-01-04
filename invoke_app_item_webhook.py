import io
import time
from PIL import Image, ImageDraw, ImageFont
import SimpleMacro_Testing.simple_macro as app_mod

# Configure test parameters
WEBHOOK_URL = "https://discord.com/api/webhooks/1385747037022064814/xq0b2GRuF39oQAQHsKw4ZZz2fQqfYQkgZ2yC2DijtcyXRbRCyptgwec05_DLnHqtDqB4"
USER_ID = "1175202749592379476"
ITEM_NAME = "AppMethodTestItem"

# Create a simple image
w, h = 800, 200
img = Image.new("RGBA", (w, h), (40, 40, 40, 255))
d = ImageDraw.Draw(img)
try:
    font = ImageFont.truetype("arial.ttf", 20)
except Exception:
    font = ImageFont.load_default()
text = f"App method screenshot - {time.strftime('%Y-%m-%d %H:%M:%S')}"
d.text((20, 80), text, fill=(230,230,230), font=font)

# Build a dummy `self` object with expected attributes used by the method
class DummySelf:
    pass

self_obj = DummySelf()
self_obj.item_webhook_url = WEBHOOK_URL
self_obj.item_webhook_enabled = True
self_obj.item_webhook_mention_enabled = True
# The app's method prepends an '@' to the value; to actually ping we will set the raw user id without angle brackets
self_obj.item_webhook_mention_user = USER_ID

# Call the unbound method defined in the testing module
method = app_mod.SimpleMacroGUI._send_item_webhook
print("Calling app method _send_item_webhook (it will spawn a background thread)...")
method(self_obj, ITEM_NAME, img)
# Wait a short time for the background thread to finish sending
print("Waiting 3 seconds for background thread to complete...")
time.sleep(3)
print("Done.")
