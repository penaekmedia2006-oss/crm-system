import os
import json
import requests
from flask import Flask, request
from dotenv import load_dotenv

load_dotenv()

DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

if not DISCORD_WEBHOOK_URL:
    print("ไม่พบ DISCORD_WEBHOOK_URL ในไฟล์ .env")
    raise SystemExit

app = Flask(__name__)


@app.route("/", methods=["GET"])
def home():
    return "LINE Discord Webhook is running", 200


@app.route("/webhook", methods=["GET", "POST"])
def webhook():
    if request.method == "GET":
        return "Webhook endpoint ready", 200

    data = request.get_json(silent=True) or {}

    print("\n====== LINE WEBHOOK ======")
    print(json.dumps(data, ensure_ascii=False, indent=2))
    print("==========================\n")

    events = data.get("events", [])

    if not events:
        return "OK", 200

    for event in events:
        if event.get("type") == "message":
            msg = event.get("message", {})
            msg_type = msg.get("type", "")

            if msg_type == "text":
                text = msg.get("text", "")
            else:
                text = f"[ข้อความประเภท {msg_type}]"

            payload = {
                "content": f"📩 LINE OA\nข้อความ: {text}"
            }

            r = requests.post(DISCORD_WEBHOOK_URL, json=payload, timeout=10)
            print("Discord status:", r.status_code)

    return "OK", 200


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)