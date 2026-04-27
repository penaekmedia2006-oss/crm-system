from flask import Flask, request, render_template, redirect
import requests
import os
from dotenv import load_dotenv
from datetime import datetime

from database import connect_db, create_table  # 🔥 สำคัญ

load_dotenv()

app = Flask(__name__)

TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")


# =========================
# UTIL
# =========================
def now():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


# =========================
# LINE
# =========================
def line_headers():
    return {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {TOKEN}"
    }


def get_name(uid):
    url = f"https://api.line.me/v2/bot/profile/{uid}"
    res = requests.get(url, headers=line_headers())

    if res.status_code == 200:
        return res.json().get("displayName", "ไม่ทราบชื่อ")

    return "ไม่ทราบชื่อ"


def line_push(uid, msg):
    url = "https://api.line.me/v2/bot/message/push"

    body = {
        "to": uid,
        "messages": [
            {"type": "text", "text": msg}
        ]
    }

    requests.post(url, headers=line_headers(), json=body)


# =========================
# ROUTE
# =========================
@app.route("/")
def home():
    return redirect("/dashboard")


@app.route("/dashboard")
def dashboard():
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM customers")
    data = cur.fetchall()

    conn.close()

    return render_template("dashboard.html", data=data)


@app.route("/chat/<uid>")
def chat(uid):
    conn = connect_db()
    cur = conn.cursor()

    cur.execute("SELECT * FROM messages WHERE user_id=?", (uid,))
    messages = cur.fetchall()

    cur.execute("SELECT * FROM customers WHERE id=?", (uid,))
    user = cur.fetchone()

    conn.close()

    return render_template("chat.html", messages=messages, user=user)


@app.route("/send", methods=["POST"])
def send():
    uid = request.form["uid"]
    msg = request.form["msg"]

    # ส่งไป LINE
    line_push(uid, msg)

    conn = connect_db()
    cur = conn.cursor()

    cur.execute(
        "INSERT INTO messages(user_id,sender,text,time) VALUES(?,?,?,?)",
        (uid, "admin", msg, now())
    )

    conn.commit()
    conn.close()

    return redirect(f"/chat/{uid}")


# =========================
# WEBHOOK LINE
# =========================
@app.route("/webhook/line", methods=["POST"])
def webhook():
    data = request.json

    conn = connect_db()
    cur = conn.cursor()

    for e in data["events"]:
        if e["type"] != "message":
            continue

        uid = e["source"]["userId"]
        text = e["message"]["text"]

        # เช็คว่ามีลูกค้าหรือยัง
        cur.execute("SELECT * FROM customers WHERE id=?", (uid,))
        if not cur.fetchone():
            cur.execute(
                "INSERT INTO customers VALUES(?,?,?,?,?,?)",
                (uid, get_name(uid), "", "", "กำลังคุย", now())
            )

        # บันทึกข้อความ
        cur.execute(
            "INSERT INTO messages(user_id,sender,text,time) VALUES(?,?,?,?)",
            (uid, "customer", text, now())
        )

    conn.commit()
    conn.close()

    return "OK"


# =========================
# RUN SERVER
# =========================
if __name__ == "__main__":
    create_table()  # 🔥 สร้าง database
    app.run(port=5000, debug=True)