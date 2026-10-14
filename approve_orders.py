# -*- coding: utf-8 -*-
"""
One-time / Idempotent Order Approval Script for Azad369 Bot.
Approves genuine pending orders with verified, fresh, collision-proof keys
and sends delivery messages directly via Telegram Bot API.
"""

import os
import sys
import json
import time
import base64
import urllib.request

BOT_TOKEN = os.environ.get("BOT_TOKEN", "8890479428:AAF26fUCTleyjuDvyx3BR7mpJ94TcYS3mN8")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "748538264"))
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATE_FILE = os.path.join(BASE_DIR, "bot_licenses_state.json")
DATA_DIR = os.path.join(BASE_DIR, "licenses")

PLANS_INFO = {
    "1M": {"name": "۱ ماهه (۳۰ روزه)", "price": "۶۰,۰۰۰ تومان", "file": "1M.txt", "days": 30},
    "2M": {"name": "۲ ماهه (۶۰ روزه)", "price": "۱۰۰,۰۰۰ تومان", "file": "2M.txt", "days": 60},
    "3M": {"name": "۳ ماهه (۹۰ روزه)", "price": "۱۴۹,۰۰۰ تومان", "file": "3M.txt", "days": 90},
    "1Y": {"name": "۱ ساله (۳۶۵ روزه)", "price": "۳۹۹,۰۰۰ تومان", "file": "1Y.txt", "days": 365}
}

def send_telegram_message(chat_id: int, text: str) -> bool:
    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": chat_id,
        "text": text,
        "parse_mode": "Markdown",
        "disable_web_page_preview": True
    }).encode("utf-8")
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status == 200
    except Exception as e:
        print(f"Failed to send TG message to {chat_id}: {e}")
        return False

def get_hwid_keys() -> set:
    bound = set()
    local_hwid = os.path.join(BASE_DIR, "hwid_registry.json")
    if os.path.exists(local_hwid):
        try:
            with open(local_hwid, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    bound.update(data.keys())
        except Exception:
            pass

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        try:
            req = urllib.request.Request(
                "https://api.github.com/repos/mahdi78013/azad369-bot/contents/hwid_registry.json",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Accept": "application/vnd.github.v3+json",
                    "User-Agent": "Azad369-Bot"
                }
            )
            with urllib.request.urlopen(req, timeout=8) as resp:
                body = json.loads(resp.read().decode())
                content = base64.b64decode(body["content"]).decode("utf-8")
                data = json.loads(content)
                if isinstance(data, dict):
                    bound.update(data.keys())
        except Exception as e:
            print(f"HWID fetch error: {e}")
    return bound

def main():
    if not os.path.exists(STATE_FILE):
        print(f"State file {STATE_FILE} not found!")
        return

    with open(STATE_FILE, "r", encoding="utf-8") as f:
        db = json.load(f)

    db.setdefault("issued", {})
    db.setdefault("orders", {})
    db.setdefault("users", {})

    hwid_keys = get_hwid_keys()
    issued_keys = set(db["issued"].keys())

    # Genuine buyers that sent valid payment receipts awaiting fresh keys:
    genuine_orders = [
        "ORD_1791966350_56673858",  # MorteZa
        "ORD_1791969266_7063614062"  # Amiri
    ]

    # Non-receipt items (chat questions / error screenshots from users who already have active keys):
    resolved_orders = [
        "ORD_1791908879_1848995301",
        "ORD_1791911888_1226349567",
        "ORD_1791945808_121908130",
        "ORD_1791946594_121908130",
        "ORD_1791946622_121908130",
        "ORD_1791946723_121908130",
        "ORD_1791967612_433272334"
    ]

    now = int(time.time())

    # 1. Resolve support messages
    for oid in resolved_orders:
        if oid in db["orders"] and db["orders"][oid].get("status") == "pending":
            db["orders"][oid]["status"] = "resolved"
            db["orders"][oid]["resolved_at"] = now
            print(f"Marked {oid} as resolved.")

    # 2. Load clean keys for 1M
    lic_file = os.path.join(DATA_DIR, "1M.txt")
    if not os.path.exists(lic_file):
        print(f"License file {lic_file} not found!")
        return

    with open(lic_file, "r", encoding="utf-8") as f:
        all_1m = [line.strip() for line in f if line.strip() and not line.startswith("#")]

    # Pick only fresh keys from index 100 onwards that never touched HWID or issued
    candidates = [k for k in all_1m[100:] if k not in issued_keys and k not in hwid_keys]
    print(f"Total fresh clean 1M candidates available: {len(candidates)}")

    approved_list = []

    for oid in genuine_orders:
        order = db["orders"].get(oid)
        if not order:
            print(f"Order {oid} not found in DB.")
            continue
        if order.get("status") != "pending":
            print(f"Order {oid} is already {order.get('status')}.")
            continue

        buyer_id = order["user_id"]
        plan_code = order["plan_code"]
        info = PLANS_INFO[plan_code]

        key = candidates.pop(0)
        issued_keys.add(key)

        order["status"] = "approved"
        order["approved_at"] = now
        order["key"] = key

        db["issued"][key] = {
            "plan": plan_code,
            "user_id": buyer_id,
            "issued_at": now
        }

        u_str = str(buyer_id)
        db["users"].setdefault(u_str, {"purchases": []})
        db["users"][u_str]["purchases"].append({
            "key": key,
            "plan": plan_code,
            "plan_name": info["name"],
            "issued_at": now,
            "days": info["days"]
        })

        buyer_msg = (
            "🎉 *رسید پرداخت شما تایید شد!*\n\n"
            "کد لایسنس اختصاصی شما:\n"
            f"`{key}`\n\n"
            "_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
            f"🔹 پلن خریداری‌شده: *{info['name']}*\n"
            f"⏳ مدت اعتبار: *{info['days']} روز*\n\n"
            "📌 *نحوه فعال‌سازی:*\n"
            "این کد را داخل نرم‌افزار ویندوز در بخش *«ثبت لایسنس»* وارد کرده و فعال نمایید.\n"
            "همچنین این لایسنس در بخش *«👤 حساب کاربری من»* ذخیره شد.\n\n"
            "با تشکر از اعتماد شما به *اینترنت آزاد³⁶⁹* 🌸"
        )

        sent = send_telegram_message(buyer_id, buyer_msg)
        print(f"Approved order {oid} for user {buyer_id} with key {key} (sent={sent})")
        approved_list.append((buyer_id, key, sent))

    # Save DB
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(db, f, ensure_ascii=False, indent=2)

    print("State file updated successfully.")

    if approved_list:
        admin_report = "✅ *گزارش تایید خودکار رسیدها:*\n\n"
        for uid, k, s in approved_list:
            admin_report += f"👤 کاربر `{uid}`:\n🔑 کد: `{k}`\nوضعیت ارسال پیام: {'موفق ✓' if s else 'ناموفق ❌'}\n\n"
        send_telegram_message(ADMIN_ID, admin_report)

if __name__ == "__main__":
    main()
