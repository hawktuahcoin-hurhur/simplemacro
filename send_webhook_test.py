import requests
import sys

WEBHOOK_URL = "https://discord.com/api/webhooks/1385747037022064814/xq0b2GRuF39oQAQHsKw4ZZz2fQqfYQkgZ2yC2DijtcyXRbRCyptgwec05_DLnHqtDqB4"
MENTION_USER = "prince_harry_"

content = f"@{MENTION_USER} Test message from SimpleMacro webhook test."

try:
    resp = requests.post(WEBHOOK_URL, json={"content": content}, timeout=10)
    print(f"HTTP {resp.status_code}")
    try:
        print(resp.text)
    except Exception:
        pass
    if resp.status_code >= 400:
        sys.exit(1)
except Exception as e:
    print(f"Error sending webhook: {e}")
    sys.exit(2)
