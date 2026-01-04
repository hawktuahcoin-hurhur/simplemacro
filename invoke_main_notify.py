import time
from PIL import Image, ImageDraw, ImageFont
import simple_macro as app_mod

WEBHOOK_URL = "https://discord.com/api/webhooks/1385747037022064814/xq0b2GRuF39oQAQHsKw4ZZz2fQqfYQkgZ2yC2DijtcyXRbRCyptgwec05_DLnHqtDqB4"

class Dummy:
    pass

self_obj = Dummy()
# minimal attributes expected by _notify_loop_complete
self_obj.discord_webhook_url = WEBHOOK_URL
self_obj.discord_webhook_enabled = True
self_obj.loop_count = 1

# Bind the method and call
method = app_mod.SimpleMacroGUI._notify_loop_complete
print('Calling _notify_loop_complete on main app...')
method(self_obj, 1)
print('Waiting 3s for background thread...')
time.sleep(3)
print('Done')
