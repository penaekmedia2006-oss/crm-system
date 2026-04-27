from flask import Flask, request, redirect
import requests
import os
from dotenv import load_dotenv
from datetime import datetime, timedelta
import json
import threading
import time

load_dotenv()

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")

DATA_FILE = "customers_no_ai.json"

customers = {}

# =========================
# UTIL
# =========================
def now():
    return datetime.now()

def dt_to_str(dt):
    return dt.strftime("%Y-%m-%d %H:%M:%S")

def str_to_dt(text):
    return datetime.strptime(text, "%Y-%m-%d %H:%M:%S")

# =========================
# LOAD / SAVE
# =========================
def load_customers():
    global customers
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            customers = json.load(f)
    else:
        customers = {}

def save_customers():
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(customers, f, ensure_ascii=False, indent=2)

# =========================
# LINE
# =========================
def line_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }

def get_line_profile(user_id):
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    res = requests.get(url, headers=line_headers())

    if res.status_code == 200:
        return res.json().get("displayName", "ไม่ทราบชื่อ")
    return "ไม่ทราบชื่อ"

def line_reply(reply_token, text):
    url = "https://api.line.me/v2/bot/message/reply"

    body = {
        "replyToken": reply_token,
        "messages": [{"type": "text", "text": text}]
    }

    requests.post(url, headers=line_headers(), json=body)

def line_push(user_id, text):
    url = "https://api.line.me/v2/bot/message/push"

    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}]
    }

    res = requests.post(url, headers=line_headers(), json=body)
    return res.status_code == 200

# =========================
# DISCORD
# =========================
def discord_send(text):
    if not DISCORD_WEBHOOK_URL:
        return
    requests.post(DISCORD_WEBHOOK_URL, json={"content": text})

# =========================
# CRM
# =========================
def create_customer(user_id):
    if user_id not in customers:
        customers[user_id] = {
            "name": get_line_profile(user_id),
            "messages": [],
            "last_contact": dt_to_str(now()),
            "status": "กำลังคุย"
        }

def update_customer(user_id, text):
    create_customer(user_id)

    customers[user_id]["messages"].append({
        "text": text,
        "time": dt_to_str(now()),
        "sender": "ลูกค้า"
    })

    customers[user_id]["last_contact"] = dt_to_str(now())
    customers[user_id]["status"] = "กำลังคุย"

    save_customers()

def save_admin_message(user_id, text):
    customers[user_id]["messages"].append({
        "text": text,
        "time": dt_to_str(now()),
        "sender": "แอดมิน"
    })

    customers[user_id]["status"] = "กำลังคุย"
    save_customers()

def get_last_message(data):
    if not data["messages"]:
        return "-"
    return data["messages"][-1]["text"]

# =========================
# แจ้งเตือนลูกค้าเงียบ
# =========================
def check_idle():
    while True:
        for user_id, data in customers.items():
            last = str_to_dt(data["last_contact"])

            if now() - last > timedelta(minutes=20):
                if data["status"] != "ลูกค้าเงียบ":

                    msg = f"""⚠️ ลูกค้าเงียบ

ชื่อ: {data.get('name','-')}
ข้อความล่าสุด: {get_last_message(data)}
เวลา: {data['last_contact']}
"""

                    discord_send(msg)

                    data["status"] = "ลูกค้าเงียบ"
                    save_customers()

        time.sleep(60)

# =========================
# DASHBOARD
# =========================
@app.route("/")
def home():
    return redirect("/dashboard")

@app.route("/dashboard")
def dashboard():
    rows = ""

    for user_id, data in customers.items():
        rows += f"""
        <tr>
            <td>{data.get('name','-')}</td>
            <td>{data.get('status','-')}</td>
            <td>{get_last_message(data)}</td>
            <td>{data.get('last_contact','-')}</td>
            <td><a href="/chat/{user_id}">แชท</a></td>
        </tr>
        """

    return f"""
    <html>
    <body style="background:#111;color:white;font-family:Arial;">
    <h1 style="color:#ff6600;">CRM (ไม่มี AI)</h1>
    <table width="100%">
    <tr style="background:#ff6600;">
    <th>ชื่อ</th><th>สถานะ</th><th>ล่าสุด</th><th>เวลา</th><th></th>
    </tr>
    {rows}
    </table>
    </body>
    </html>
    """

@app.route("/chat/<user_id>")
def chat(user_id):
    data = customers[user_id]

    messages_html = ""

    for msg in data["messages"]:
        messages_html += f"<div>{msg['text']} ({msg['time']})</div>"

    return f"""
    <html>
    <body style="background:#111;color:white;">
    <a href="/dashboard">← กลับ</a>
    <h2>{data.get('name','-')}</h2>

    {messages_html}

    <form method="POST" action="/send">
    <input type="hidden" name="user_id" value="{user_id}">
    <textarea name="msg"></textarea>
    <button>ส่ง</button>
    </form>

    </body>
    </html>
    """

@app.route("/send", methods=["POST"])
def send():
    user_id = request.form["user_id"]
    msg = request.form["msg"]

    if line_push(user_id, msg):
        save_admin_message(user_id, msg)

    return redirect(f"/chat/{user_id}")

# =========================
# WEBHOOK
# =========================
@app.route("/webhook/line", methods=["POST"])
def webhook():
    data = request.json

    for e in data["events"]:
        if e["type"] == "message":
            user_id = e["source"]["userId"]
            text = e["message"]["text"]
            token = e["replyToken"]

            update_customer(user_id, text)
            line_reply(token, "รับข้อความแล้วค่ะ")

    return "OK"

# =========================
# RUN
# =========================
if __name__ == "__main__":
    load_customers()
    threading.Thread(target=check_idle, daemon=True).start()
    app.run(port=5001)