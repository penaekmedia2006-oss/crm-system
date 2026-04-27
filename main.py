from flask import Flask, request, redirect
import requests
import os
from dotenv import load_dotenv
from datetime import datetime
import json
from urllib.parse import quote

load_dotenv()

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
DISCORD_WEBHOOK_URL = os.getenv("DISCORD_WEBHOOK_URL")
FACEBOOK_VERIFY_TOKEN = os.getenv("FACEBOOK_VERIFY_TOKEN")
FACEBOOK_PAGE_ACCESS_TOKEN = os.getenv("FACEBOOK_PAGE_ACCESS_TOKEN")

DATA_FILE = "customers.json"
customers = {}


def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


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


def normalize_status(status):
    if status in ["Idle", "idle", "ลูกค้าเงียบ"]:
        return "ลูกค้าเงียบ"
    if status in ["กำลังคุย"]:
        return "กำลังคุย"
    if status in ["รอตัดสินใจ"]:
        return "รอตัดสินใจ"
    if status in ["ปิดการขาย", "ปิดการขายแล้ว"]:
        return "ปิดการขายแล้ว"
    if status in ["ไม่สนใจ"]:
        return "ไม่สนใจ"
    return "กำลังคุย"


def status_color(status):
    status = normalize_status(status)

    if status == "กำลังคุย":
        return "#00ff99"
    if status == "ลูกค้าเงียบ":
        return "#ff4444"
    if status == "รอตัดสินใจ":
        return "#ff9900"
    if status == "ปิดการขายแล้ว":
        return "#3399ff"
    if status == "ไม่สนใจ":
        return "#999999"

    return "white"


def platform_badge(platform):
    if platform == "LINE":
        return '<span class="line-badge">LINE</span>'
    if platform == "Facebook":
        return '<span class="fb-badge">Facebook</span>'
    return '<span class="unknown-badge">-</span>'


def line_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_CHANNEL_ACCESS_TOKEN}"
    }


def get_line_name(user_id):
    url = f"https://api.line.me/v2/bot/profile/{user_id}"
    res = requests.get(url, headers=line_headers())

    print("LINE PROFILE:", res.status_code, res.text)

    if res.status_code == 200:
        return res.json().get("displayName", "ไม่ทราบชื่อ")

    return "ไม่ทราบชื่อ"


def get_facebook_name(sender_id):
    if not FACEBOOK_PAGE_ACCESS_TOKEN:
        return "ลูกค้า Facebook"

    url = f"https://graph.facebook.com/{sender_id}"
    params = {
        "fields": "first_name,last_name,name",
        "access_token": FACEBOOK_PAGE_ACCESS_TOKEN
    }

    try:
        res = requests.get(url, params=params)
        print("FACEBOOK PROFILE:", res.status_code, res.text)

        if res.status_code == 200:
            data = res.json()
            return data.get("name", "ลูกค้า Facebook")
    except Exception as e:
        print("FACEBOOK PROFILE ERROR:", e)

    return "ลูกค้า Facebook"


def line_push(user_id, text):
    url = "https://api.line.me/v2/bot/message/push"

    body = {
        "to": user_id,
        "messages": [{"type": "text", "text": text}]
    }

    res = requests.post(url, headers=line_headers(), json=body)
    print("LINE PUSH:", res.status_code, res.text)

    return res.status_code == 200


def discord_send(text):
    if DISCORD_WEBHOOK_URL:
        requests.post(DISCORD_WEBHOOK_URL, json={"content": text})


def create_customer(user_id, platform="LINE"):
    if user_id not in customers:
        if platform == "LINE":
            name = get_line_name(user_id)
        elif platform == "Facebook":
            name = get_facebook_name(user_id)
        else:
            name = "ไม่ทราบชื่อ"

        customers[user_id] = {
            "name": name,
            "platform": platform,
            "phone": "",
            "job_interest": "",
            "status": "กำลังคุย",
            "messages": [],
            "last_contact": now()
        }


def update_customer(user_id, text, platform="LINE"):
    create_customer(user_id, platform)

    # 🔥 ดึงชื่อแบบ retry กันพลาด
    name = ""

    if platform == "LINE":
        for _ in range(3):
            name = get_line_name(user_id)
            if name and name != "ไม่ทราบชื่อ":
                break

    elif platform == "Facebook":
        name = get_facebook_name(user_id)

    # ถ้าได้ชื่อจริงค่อยอัปเดต
    if name and name != "ไม่ทราบชื่อ":
        customers[user_id]["name"] = name

    customers[user_id]["platform"] = platform

    customers[user_id]["messages"].append({
        "sender": "ลูกค้า",
        "text": text,
        "time": now()
    })

    customers[user_id]["last_contact"] = now()

    if normalize_status(customers[user_id].get("status")) == "ลูกค้าเงียบ":
        customers[user_id]["status"] = "กำลังคุย"

    save_customers()


def save_admin_message(user_id, text):
    customers[user_id]["messages"].append({
        "sender": "แอดมิน",
        "text": text,
        "time": now()
    })

    customers[user_id]["last_contact"] = now()
    customers[user_id]["status"] = "กำลังคุย"

    save_customers()


@app.route("/")
def home():
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    rows = ""

    for user_id, data in customers.items():
        status = normalize_status(data.get("status", "กำลังคุย"))
        data["status"] = status

        try:
            last = datetime.strptime(data.get("last_contact", ""), "%Y-%m-%d %H:%M:%S")
            diff = datetime.now() - last

            days = diff.days
            hours = diff.seconds // 3600
            idle_time = f"{days} วัน {hours} ชม."

            if diff.days >= 1 and status == "กำลังคุย":
                status = "ลูกค้าเงียบ"
                data["status"] = status

        except:
            idle_time = "-"

        color = status_color(status)
        safe_user_id = quote(user_id, safe="")

        rows += f"""
        <tr>
            <td class="name-col">{data.get("name", "-")}</td>
            <td class="platform-col">{platform_badge(data.get("platform", "-"))}</td>
            <td class="status-col" style="color:{color};">{status}</td>
            <td class="idle-col">เงียบ {idle_time}</td>
            <td class="action-col">
                <a class="btn" href="/chat/{safe_user_id}">เปิดแชท</a>
            </td>
        </tr>
        """

    save_customers()

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
        <title>Dashboard ลูกค้า</title>
        <style>
            body {{
                background:#111;
                color:white;
                font-family:Arial, sans-serif;
                padding:20px;
            }}

            h1 {{
                color:#ff6600;
                margin-bottom:20px;
            }}

            table {{
                width:100%;
                border-collapse:collapse;
                background:#1b1b1b;
                table-layout:fixed;
            }}

            th {{
                background:#ff6600;
                padding:14px 10px;
                text-align:center;
                font-size:16px;
            }}

            td {{
                padding:14px 10px;
                border-bottom:1px solid #333;
                vertical-align:middle;
                font-size:16px;
            }}

            tr:hover {{
                background:#222;
            }}

            .name-col {{
                width:30%;
                text-align:left;
                font-weight:bold;
            }}

            .platform-col {{
                width:18%;
                text-align:center;
            }}

            .status-col {{
                width:18%;
                text-align:center;
                font-weight:bold;
            }}

            .idle-col {{
                width:20%;
                text-align:center;
                color:#ffcc66;
                font-weight:bold;
            }}

            .action-col {{
                width:14%;
                text-align:center;
            }}

            .btn {{
                display:inline-block;
                background:#ff6600;
                color:white;
                padding:8px 14px;
                text-decoration:none;
                border-radius:6px;
                font-weight:bold;
                cursor:pointer;
            }}

            .btn:hover {{
                background:#ff8533;
            }}

            .line-badge {{
                display:inline-block;
                background:#06C755;
                color:white;
                padding:6px 12px;
                border-radius:20px;
                font-weight:bold;
            }}

            .fb-badge {{
                display:inline-block;
                background:#1877F2;
                color:white;
                padding:6px 12px;
                border-radius:20px;
                font-weight:bold;
            }}

            .unknown-badge {{
                display:inline-block;
                background:#666;
                color:white;
                padding:6px 12px;
                border-radius:20px;
            }}
        </style>
    </head>
    <body>

        <h1>📊 Dashboard ลูกค้า</h1>

        <table>
            <tr>
                <th class="name-col">ชื่อ</th>
                <th class="platform-col">ช่องทาง</th>
                <th class="status-col">สถานะ</th>
                <th class="idle-col">เงียบไป</th>
                <th class="action-col">จัดการ</th>
            </tr>
            {rows}
        </table>

    </body>
    </html>
    """


@app.route("/chat/<path:user_id>")
def chat(user_id):
    data = customers.get(user_id)

    if not data:
        return "ไม่พบลูกค้า"

    data["status"] = normalize_status(data.get("status", "กำลังคุย"))

    messages_html = ""

    for msg in data.get("messages", []):
        align = "right" if msg.get("sender") == "แอดมิน" else "left"
        bg = "#ff6600" if msg.get("sender") == "แอดมิน" else "#222"

        messages_html += f"""
        <div style="text-align:{align}; margin:10px 0;">
            <div style="
                background:{bg};
                padding:12px;
                border-radius:10px;
                display:inline-block;
                max-width:70%;
            ">
                <div>{msg.get("text", "")}</div>
                <small>{msg.get("sender", "-")} | {msg.get("time", "")}</small>
            </div>
        </div>
        """

    return f"""
    <html>
    <head>
        <meta charset="utf-8">
    </head>
    <body style="background:#111; color:white; font-family:Arial; padding:20px;">

        <a href="/dashboard" style="color:#ff6600;">← กลับ Dashboard</a>

        <h2>{data.get("name", "-")}</h2>
        <p>ช่องทาง: {platform_badge(data.get("platform", "-"))}</p>

        <form method="POST" action="/update-status">
            <input type="hidden" name="user_id" value="{user_id}">

            <label>สถานะลูกค้า</label><br>
            <select name="status" style="padding:10px; margin:10px 0; width:250px;">
                <option {"selected" if data.get("status") == "กำลังคุย" else ""}>กำลังคุย</option>
                <option {"selected" if data.get("status") == "ลูกค้าเงียบ" else ""}>ลูกค้าเงียบ</option>
                <option {"selected" if data.get("status") == "รอตัดสินใจ" else ""}>รอตัดสินใจ</option>
                <option {"selected" if data.get("status") == "ปิดการขายแล้ว" else ""}>ปิดการขายแล้ว</option>
                <option {"selected" if data.get("status") == "ไม่สนใจ" else ""}>ไม่สนใจ</option>
            </select>

            <button type="submit" style="padding:10px; background:#ff6600; color:white; border:none;">
                บันทึกสถานะ
            </button>
        </form>

        <hr>

        {messages_html}

        <form method="POST" action="/send">
            <input type="hidden" name="user_id" value="{user_id}">
            <textarea name="message" style="width:100%; height:100px;"></textarea>
            <br><br>
            <button type="submit" style="padding:10px; background:#ff6600; color:white; border:none;">
                ส่งข้อความไป LINE
            </button>
        </form>

    </body>
    </html>
    """


@app.route("/update-status", methods=["POST"])
def update_status():
    user_id = request.form.get("user_id")
    status = request.form.get("status")

    if user_id in customers:
        customers[user_id]["status"] = normalize_status(status)
        save_customers()

    return redirect(f"/chat/{quote(user_id, safe='')}")


@app.route("/send", methods=["POST"])
def send():
    user_id = request.form.get("user_id")
    message = request.form.get("message")

    if user_id in customers and message:
        platform = customers[user_id].get("platform", "LINE")

        if platform == "LINE":
            if line_push(user_id, message):
                save_admin_message(user_id, message)
        else:
            save_admin_message(user_id, message)

    return redirect(f"/chat/{quote(user_id, safe='')}")


@app.route("/webhook/line", methods=["POST"])
def webhook_line():
    data = request.json
    print("====== LINE ======")
    print(data)

    for event in data.get("events", []):
        if event.get("type") != "message":
            continue

        msg = event.get("message", {})
        if msg.get("type") != "text":
            continue

        user_id = event.get("source", {}).get("userId")
        text = msg.get("text", "")

        update_customer(user_id, text, "LINE")

        discord_send(
            f"📩 ข้อความใหม่จาก LINE\\n"
            f"ชื่อ: {customers[user_id].get('name', '-')}\\n"
            f"ข้อความ: {text}"
        )

    return "OK"


@app.route("/webhook/facebook", methods=["GET", "POST"])
def webhook_facebook():
    if request.method == "GET":
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == FACEBOOK_VERIFY_TOKEN:
            return challenge, 200

        return "Verify token ไม่ถูกต้อง", 403

    data = request.json
    print("====== FACEBOOK ======")
    print(data)

    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id")
                message_data = messaging_event.get("message", {})
                text = message_data.get("text")

                if sender_id and text:
                    update_customer(sender_id, text, "Facebook")

                    discord_send(
                        f"📩 ข้อความใหม่จาก Facebook\\n"
                        f"ชื่อ: {customers[sender_id].get('name', '-')}\\n"
                        f"ข้อความ: {text}"
                    )

    return "OK", 200


if __name__ == "__main__":
    load_customers()
    app.run(port=5000)