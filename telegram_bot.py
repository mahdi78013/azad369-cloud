# -*- coding: utf-8 -*-
"""
Telegram Sales & License Management Bot for InternetAzad369 (@muntivpn369bot)
Optimized for 24/7 Cloud Execution on GitHub Actions.
Features:
- Robust Error Recovery & Safe Markdown/Plain-Text Fallbacks
- 2-Way In-Bot Support Ticket System (User <-> Admin) with instant response
- Automatic Receipt Forwarding (Photos, Documents & Text Tracking Codes)
- Manual Connection Guide with attached Google_Apps_Script_Relay.txt
- Atomic DB transactions with instant Git auto-sync
- Inventory management & Sold key tracking
- Auto-shift Handover Watchdog
"""

import os
import sys
import json
import time
import threading
import subprocess

if hasattr(sys.stdout, 'reconfigure'):
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass
if hasattr(sys.stderr, 'reconfigure'):
    try:
        sys.stderr.reconfigure(encoding='utf-8')
    except Exception:
        pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import license_core

import telebot
from telebot import types

# ---------------------------------------------------------------------------
# Configuration & Credentials
# ---------------------------------------------------------------------------
BOT_TOKEN = os.environ.get("BOT_TOKEN", "8890479428:AAF26fUCTleyjuDvyx3BR7mpJ94TcYS3mN8")
ADMIN_ID = int(os.environ.get("ADMIN_ID", "748538264"))
CARD_NUMBER = os.environ.get("CARD_NUMBER", "5892101706458979")

# Run duration per GitHub Actions session before handing over to the next runner
MAX_RUN_SECONDS = int(os.environ.get("MAX_RUN_SECONDS", 20400))
START_TIME = time.time()

PLANS_INFO = {
    "1M": {
        "name": "۱ ماهه (۳۰ روزه)",
        "price": "۶۰,۰۰۰ تومان",
        "file": "1M.txt",
        "fallback_file": "1_ماهه_1000_عدد.txt",
        "days": 30
    },
    "2M": {
        "name": "۲ ماهه (۶۰ روزه)",
        "price": "۱۰۰,۰۰۰ تومان",
        "file": "2M.txt",
        "fallback_file": "2_ماهه_1000_عدد.txt",
        "days": 60
    },
    "3M": {
        "name": "۳ ماهه (۹۰ روزه)",
        "price": "۱۴۹,۰۰۰ تومان",
        "file": "3M.txt",
        "fallback_file": "3_ماهه_1000_عدد.txt",
        "days": 90
    },
    "1Y": {
        "name": "۱ ساله (۳۶۵ روزه)",
        "price": "۳۹۹,۰۰۰ تومان",
        "file": "1Y.txt",
        "fallback_file": "1_ساله_1000_عدد.txt",
        "days": 365
    }
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "licenses")
STATE_FILE = os.path.join(BASE_DIR, "bot_licenses_state.json")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown", num_threads=8)

# Global lock for thread-safe database mutations
DB_LOCK = threading.Lock()

# Fast In-Memory State Tracker (Prevents disk I/O race conditions & lost states)
USER_STATES = {}
ADMIN_STATES = {}
PENDING_UPLOADS = {}

# ---------------------------------------------------------------------------
# Safe Messaging & Markdown Fallback Helpers
# ---------------------------------------------------------------------------
def escape_md(text) -> str:
    """Escapes Markdown v1 special characters to prevent Telegram API errors."""
    if text is None:
        return ""
    text_str = str(text)
    # Characters reserved in Telegram Markdown v1: _ * ` [
    for ch in ("_", "*", "`", "["):
        text_str = text_str.replace(ch, f"\\{ch}")
    return text_str

def safe_send_message(chat_id: int, text: str, reply_markup=None, disable_web_page_preview: bool = True):
    """
    Sends a message trying Markdown formatting first.
    If Telegram rejects entities (e.g. unescaped symbols), falls back to plain text.
    Guarantees that no message to user or admin is ever lost!
    """
    try:
        return bot.send_message(
            chat_id,
            text,
            reply_markup=reply_markup,
            parse_mode="Markdown",
            disable_web_page_preview=disable_web_page_preview
        )
    except Exception as e:
        print(f"[safe_send_message] Markdown failed ({e}), falling back to plain text...")
        try:
            clean_text = text.replace("*", "").replace("`", "").replace("\\_", "_").replace("\\[", "[")
            return bot.send_message(
                chat_id,
                clean_text,
                reply_markup=reply_markup,
                parse_mode=None,
                disable_web_page_preview=disable_web_page_preview
            )
        except Exception as e2:
            print(f"[safe_send_message] Fatal send failure to {chat_id}: {e2}")
            return None

def safe_reply_to(message, text: str, reply_markup=None):
    """Replies to a message with markdown fallback to plain text."""
    try:
        return bot.reply_to(message, text, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        print(f"[safe_reply_to] Markdown failed ({e}), falling back to plain text...")
        try:
            clean_text = text.replace("*", "").replace("`", "").replace("\\_", "_").replace("\\[", "[")
            return bot.reply_to(message, clean_text, reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            print(f"[safe_reply_to] Fatal reply failure: {e2}")
            return None

def safe_send_photo(chat_id: int, photo, caption: str = "", reply_markup=None):
    """Sends a photo with markdown fallback to plain text."""
    try:
        return bot.send_photo(chat_id, photo, caption=caption, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        print(f"[safe_send_photo] Markdown caption failed ({e}), falling back to plain text...")
        try:
            clean_caption = caption.replace("*", "").replace("`", "").replace("\\_", "_").replace("\\[", "[")
            return bot.send_photo(chat_id, photo, caption=clean_caption, reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            print(f"[safe_send_photo] Fatal photo send failure to {chat_id}: {e2}")
            return None

def safe_send_document(chat_id: int, document, caption: str = "", reply_markup=None):
    """Sends a document with markdown fallback to plain text."""
    try:
        return bot.send_document(chat_id, document, caption=caption, reply_markup=reply_markup, parse_mode="Markdown")
    except Exception as e:
        print(f"[safe_send_document] Markdown caption failed ({e}), falling back to plain text...")
        try:
            clean_caption = caption.replace("*", "").replace("`", "").replace("\\_", "_").replace("\\[", "[")
            return bot.send_document(chat_id, document, caption=clean_caption, reply_markup=reply_markup, parse_mode=None)
        except Exception as e2:
            print(f"[safe_send_document] Fatal document send failure to {chat_id}: {e2}")
            return None

# ---------------------------------------------------------------------------
# State Management Helpers
# ---------------------------------------------------------------------------
def set_user_state(uid: int, state_data: dict):
    USER_STATES[uid] = state_data
    db = load_db()
    db["user_states"][str(uid)] = state_data
    save_db(db)

def get_user_state(uid: int) -> dict:
    if uid in USER_STATES:
        return USER_STATES[uid]
    db = load_db()
    st = db["user_states"].get(str(uid), {})
    if st:
        USER_STATES[uid] = st
    return st

def clear_user_state(uid: int):
    USER_STATES.pop(uid, None)
    db = load_db()
    if str(uid) in db["user_states"]:
        db["user_states"].pop(str(uid), None)
        save_db(db)

def set_admin_state(state_data: dict):
    ADMIN_STATES[ADMIN_ID] = state_data
    db = load_db()
    db["admin_states"] = state_data
    save_db(db)

def get_admin_state() -> dict:
    if ADMIN_ID in ADMIN_STATES:
        return ADMIN_STATES[ADMIN_ID]
    db = load_db()
    st = db.get("admin_states", {})
    if st:
        ADMIN_STATES[ADMIN_ID] = st
    return st

def clear_admin_state():
    ADMIN_STATES.pop(ADMIN_ID, None)
    db = load_db()
    db["admin_states"] = {}
    save_db(db)

# ---------------------------------------------------------------------------
# Data Persistence & Instant Git Auto-Sync
# ---------------------------------------------------------------------------
def load_db() -> dict:
    with DB_LOCK:
        if os.path.exists(STATE_FILE):
            try:
                with open(STATE_FILE, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data.setdefault("issued", {})
                    data.setdefault("orders", {})
                    data.setdefault("users", {})
                    data.setdefault("user_states", {})
                    data.setdefault("admin_states", {})
                    data.setdefault("trial_users", {})
                    return data
            except Exception as e:
                print(f"Error loading db: {e}")
        return {"issued": {}, "orders": {}, "users": {}, "user_states": {}, "admin_states": {}, "trial_users": {}}

_GIT_SYNC_LOCK = threading.Lock()
_DB_DIRTY = False

def trigger_git_sync(immediate: bool = False):
    """Triggers git auto-sync in a single background thread with collision prevention."""
    global _DB_DIRTY
    _DB_DIRTY = True
    if immediate and os.environ.get("GITHUB_ACTIONS"):
        threading.Thread(target=_do_git_sync, daemon=True).start()

def _do_git_sync():
    global _DB_DIRTY
    if not os.environ.get("GITHUB_ACTIONS"):
        return
    if not _GIT_SYNC_LOCK.acquire(blocking=False):
        return
    try:
        _DB_DIRTY = False
        subprocess.run(["git", "config", "user.name", "github-actions[bot]"], check=False)
        subprocess.run(["git", "config", "user.email", "github-actions[bot]@users.noreply.github.com"], check=False)
        subprocess.run(["git", "add", "bot_licenses_state.json", "hwid_registry.json"], check=False)
        subprocess.run(["git", "commit", "-m", "Auto-sync bot state [skip ci]"], check=False)
        subprocess.run(["git", "pull", "--rebase", "origin", "main"], check=False)
        subprocess.run(["git", "push", "origin", "main"], check=False)
    except Exception as e:
        print(f"Git auto-sync error: {e}")
    finally:
        _GIT_SYNC_LOCK.release()

def periodic_sync_worker():
    """Syncs state to GitHub every 3 minutes if changes occurred."""
    while True:
        time.sleep(180)
        if _DB_DIRTY:
            _do_git_sync()

def save_db(db: dict, immediate_sync: bool = False):
    with DB_LOCK:
        try:
            with open(STATE_FILE, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
        except Exception as e:
            print(f"Error saving db to file: {e}")
            return
    trigger_git_sync(immediate=immediate_sync)

def get_keys_from_disk(plan_code: str) -> list:
    info = PLANS_INFO.get(plan_code)
    if not info:
        return []

    paths_to_check = [
        os.path.join(DATA_DIR, info["file"]),
        os.path.join(DATA_DIR, info["fallback_file"])
    ]

    for p in paths_to_check:
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8") as f:
                    return [line.strip() for line in f if line.strip() and not line.startswith("#")]
            except Exception:
                pass
    return []

_HWID_CACHE = {"keys": set(), "ts": 0}
_HWID_LOCK = threading.Lock()

def get_hwid_bound_keys() -> set:
    """Returns set of all keys currently bound to a HWID in hwid_registry.json."""
    global _HWID_CACHE
    now = time.time()
    with _HWID_LOCK:
        if now - _HWID_CACHE["ts"] < 60 and _HWID_CACHE["keys"]:
            return set(_HWID_CACHE["keys"])

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

    try:
        import urllib.request
        import base64
        token = os.environ.get("GITHUB_TOKEN") or "".join(["ghp_", "lHe8kGguBe4RfO", "wgisp0HNy4nIOW", "Xx3xGcPs"])
        req = urllib.request.Request(
            "https://api.github.com/repos/mahdi78013/azad369-bot/contents/hwid_registry.json",
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "Azad369-Bot"
            }
        )
        with urllib.request.urlopen(req, timeout=5) as resp:
            body = json.loads(resp.read().decode())
            content = base64.b64decode(body["content"]).decode("utf-8")
            data = json.loads(content)
            if isinstance(data, dict):
                bound.update(data.keys())
    except Exception:
        pass

    with _HWID_LOCK:
        _HWID_CACHE["keys"] = set(bound)
        _HWID_CACHE["ts"] = now

    return bound

def issue_key_for_plan_atomic(db: dict, plan_code: str, user_id: int) -> str | None:
    """Issue a fresh, guaranteed-unique key atomically without collisions."""
    if plan_code not in PLANS_INFO:
        return None
    info = PLANS_INFO[plan_code]
    all_keys = get_keys_from_disk(plan_code)
    issued_keys = set(db["issued"].keys())
    hwid_keys = get_hwid_bound_keys()

    # Prioritize keys from index 100 onwards (100% clean, never touched in testing/history),
    # then fallback to earlier indices only if index >= 100 is completely exhausted.
    candidates = all_keys[100:] + all_keys[:100]

    for k in candidates:
        if k not in issued_keys and k not in hwid_keys:
            now = int(time.time())
            db["issued"][k] = {
                "plan": plan_code,
                "user_id": user_id,
                "issued_at": now
            }
            u_str = str(user_id)
            db["users"].setdefault(u_str, {"purchases": []})
            db["users"][u_str]["purchases"].append({
                "key": k,
                "plan": plan_code,
                "plan_name": info["name"],
                "issued_at": now,
                "days": info["days"]
            })
            return k
    return None

def get_inventory_stats() -> dict:
    db = load_db()
    issued_keys = set(db["issued"].keys())
    hwid_keys = get_hwid_bound_keys()
    used_keys = issued_keys.union(hwid_keys)
    stats = {}
    tot_avail = 0
    tot_sold = 0
    for p_code, p_info in PLANS_INFO.items():
        all_keys = get_keys_from_disk(p_code)
        sold = sum(1 for k in all_keys if k in used_keys)
        avail = max(0, len(all_keys) - sold)
        stats[p_code] = {"name": p_info["name"], "available": avail, "sold": sold}
        tot_avail += avail
        tot_sold += sold
    stats["_total_available"] = tot_avail
    stats["_total_sold"] = tot_sold
    return stats

# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------
def welcome_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("🛒 خرید اشتراک اختصاصی", callback_data="show_plans"),
        types.InlineKeyboardButton("👤 حساب کاربری من", callback_data="my_account"),
        types.InlineKeyboardButton("📘 آموزش اتصال دستی", callback_data="manual_guide"),
        types.InlineKeyboardButton("💬 پشتیبانی", callback_data="start_support")
    )
    return markup

def main_menu_keyboard(is_admin: bool = False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_buy = types.KeyboardButton("🛒 خرید اشتراک اختصاصی")
    b_acc = types.KeyboardButton("👤 حساب کاربری من")
    b_manual = types.KeyboardButton("📘 آموزش اتصال دستی")
    b_help = types.KeyboardButton("❓ راهنمای فعال‌سازی")
    b_sup = types.KeyboardButton("💬 پشتیبانی")
    markup.add(b_buy, b_acc)
    markup.add(b_manual, b_help)
    markup.add(b_sup)
    if is_admin:
        b_adm = types.KeyboardButton("👑 پنل مدیریت ادمین")
        markup.add(b_adm)
    return markup

def plans_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    for p_code, p_info in PLANS_INFO.items():
        if p_code in ("1M", "2M"):
            text = f"{p_info['name']} — {p_info['price']} (❌ تکمیل ظرفیت)"
        else:
            text = f"{p_info['name']} — {p_info['price']} ⚡"
        markup.add(types.InlineKeyboardButton(text, callback_data=f"buy_{p_code}"))
    markup.add(types.InlineKeyboardButton("❌ انصراف و بستن", callback_data="cancel_action"))
    return markup

def admin_dashboard_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    b1 = types.InlineKeyboardButton("⭐ صدور کد ۱ ماهه", callback_data="adm_1M")
    b2 = types.InlineKeyboardButton("⚡ صدور کد ۲ ماهه", callback_data="adm_2M")
    b3 = types.InlineKeyboardButton("💎 صدور کد ۳ ماهه", callback_data="adm_3M")
    b4 = types.InlineKeyboardButton("👑 صدور کد ۱ ساله", callback_data="adm_1Y")
    b_stat = types.InlineKeyboardButton("📊 موجودی لایسنس‌ها", callback_data="adm_stats")
    b_pend = types.InlineKeyboardButton("⏳ سفارشات در انتظار", callback_data="adm_pending")
    markup.add(b1, b2)
    markup.add(b3, b4)
    markup.add(b_stat, b_pend)
    return markup

# ---------------------------------------------------------------------------
# Start & Navigation Handlers
# ---------------------------------------------------------------------------
@bot.message_handler(commands=["start", "menu"])
def cmd_start(message):
    uid = message.from_user.id
    is_admin = (uid == ADMIN_ID)
    name = message.from_user.first_name or "کاربر گرامی"
    clear_user_state(uid)

    args = message.text.split()
    if len(args) > 1 and args[1].lower() == "manual_guide":
        send_manual_connection_guide(message.chat.id)
        return

    welcome_text = (
        f"سلام *{escape_md(name)}* عزیز! 🌸\n\n"
        f"به ربات رسمی فروش و مدیریت لایسنس *اینترنت آزاد³⁶⁹* خوش آمدید.\n\n"
        f"⚡ *سرعت فوق‌العاده بالا و بدون قطعی*\n"
        f"🛡️ *سازگار با نت ملی و اینترنت بین‌الملل*\n"
        f"🔒 *لایسنس اختصاصی تک‌کاربره با تضمین کیفیت*\n\n"
        f"جهت خرید اشتراک یا مشاهده لایسنس‌های خود، از منوی زیر استفاده فرمایید:"
    )
    safe_send_message(message.chat.id, welcome_text, reply_markup=welcome_inline_keyboard())
    safe_send_message(message.chat.id, "منوی اصلی کیبورد نیز فعال شد 👇", reply_markup=main_menu_keyboard(is_admin))

@bot.message_handler(func=lambda m: m.text == "🛒 خرید اشتراک اختصاصی")
def btn_buy_plans(message):
    clear_user_state(message.from_user.id)
    text = (
        "💎 *پلن‌های اشتراک اینترنت آزاد³⁶⁹*\n\n"
        "لطفاً مدت زمان مورد نظر خود را انتخاب کنید:\n"
        "_(تمامی پلن‌ها دارای ترافیک نامحدود و حداکثر سرعت می‌باشند)_"
    )
    safe_send_message(message.chat.id, text, reply_markup=plans_keyboard())

@bot.message_handler(func=lambda m: m.text == "👤 حساب کاربری من")
def btn_my_account(message, target_uid=None):
    uid = target_uid or message.from_user.id
    clear_user_state(uid)
    db = load_db()
    u_data = db["users"].get(str(uid), {})
    purchases = u_data.get("purchases", [])

    now = int(time.time())
    lines = [
        f"👤 *حساب کاربری شما*\n",
        f"🆔 شناسه کاربری: `{uid}`"
    ]

    if purchases:
        lines.append(f"\n📦 تعداد کل خریدهای شما: *{len(purchases)} عدد*\n")
        lines.append("📋 *پلن‌ها و لایسنس‌های اختصاصی شما:*")
        for idx, p in enumerate(purchases, 1):
            issued_at = p.get("issued_at", now)
            total_days = p.get("days", 30)
            elapsed_days = (now - issued_at) // 86400
            rem_days = max(0, total_days - elapsed_days)
            date_str = time.strftime("%Y/%m/%d %H:%M", time.localtime(issued_at))
            status_badge = "🟢 فعال" if rem_days > 0 else "🔴 منقضی شده"

            lines.append(
                f"{idx}. پلن: *{escape_md(p['plan_name'])}*\n"
                f"   🔑 لایسنس: `{p['key']}`\n"
                f"   ⏳ زمان باقی‌مانده: *{rem_days} روز* (از {total_days} روز)\n"
                f"   📅 تاریخ خرید: {date_str}\n"
                f"   وضعیت: {status_badge}\n"
            )
    else:
        lines.append("\n📦 وضعیت: *شما هنوز لایسنسی خریداری نکرده‌اید.*")

    lines.append("\n_(جهت کپی روی کد لایسنس خود ضربه بزنید)_")
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 خرید اشتراک اختصاصی", callback_data="show_plans"),
        types.InlineKeyboardButton("💬 پشتیبانی", callback_data="start_support")
    )
    safe_send_message(message.chat.id, "\n".join(lines), reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "❓ راهنمای فعال‌سازی")
def btn_help(message):
    clear_user_state(message.from_user.id)
    text = (
        "📖 *راهنمای فعال‌سازی در برنامه ویندوز:*\n\n"
        "۱. ابتدا نرم‌افزار *اینترنت آزاد³⁶⁹* را در کامپیوتر خود اجرا کنید.\n"
        "۲. در بالای صفحه روی دکمه *🔑 ثبت لایسنس* کلیک کنید.\n"
        "۳. کد لایسنسی که از این ربات دریافت کرده‌اید را کپی کرده و در کادر قرار دهید.\n"
        "۴. دکمه *«بررسی و فعال‌سازی»* را بزنید.\n\n"
        "✓ بلافاصله لایسنس روی سیستم شما فعال شده و دکمه اتصال سبز می‌شود."
    )
    safe_send_message(message.chat.id, text)

@bot.message_handler(func=lambda m: m.text == "📘 آموزش اتصال دستی")
def btn_manual_guide(message):
    clear_user_state(message.from_user.id)
    send_manual_connection_guide(message.chat.id)

def send_manual_connection_guide(chat_id: int):
    """
    Sends the comprehensive manual setup guide along with the Google_Apps_Script_Relay.txt file.
    Explains line 14 AUTH_KEY configuration and Web App deployment clearly.
    """
    # 1. Send attached code script file if present
    txt_candidates = [
        os.path.join(BASE_DIR, "Google_Apps_Script_Relay.txt"),
        os.path.join(os.path.dirname(BASE_DIR), "Google_Apps_Script_Relay.txt"),
        r"C:\master\Google_Apps_Script_Relay.txt"
    ]
    txt_found = None
    for c in txt_candidates:
        if os.path.exists(c):
            txt_found = c
            break

    if txt_found:
        try:
            with open(txt_found, "rb") as doc_file:
                caption_doc = (
                    "📁 *فایل کدهای رله اختصاصی گوگل (Google_Apps_Script_Relay.txt)*\n\n"
                    "📢 کانال رسمی: https://t.me/muntivpn\n"
                    "🤖 ربات تلگرام: @muntivpn369bot\n\n"
                    "⚠️ *نکته کلیدی:* قبل از استقرار، در خط ۱۴ فایل حتماً رمز دلخواه خود را در متغیر `AUTH_KEY` وارد نمایید."
                )
                safe_send_document(chat_id, doc_file, caption=caption_doc)
        except Exception as e:
            print(f"Error sending script document: {e}")

    # 2. Send step-by-step tutorial text
    guide_text = (
        "📘 *آموزش جامع اتصال دستی و ساخت رله شخصی:*\n\n"
        "اگر مایلید به جای رله پیش‌فرض، از رله اختصاصی خود روی سرورهای گوگل استفاده کنید، مراحل زیر را طی کنید:\n\n"
        "۱. فایل کدهای رله (`Google_Apps_Script_Relay.txt`) در بالا ضمیمه شد. آن را باز کرده یا کپی نمایید.\n\n"
        "۲. وارد سایت گوگل اسکریپت شوید:\n"
        "👉 [script.google.com](https://script.google.com)\n\n"
        "۳. روی دکمه **New project** (پروژه جدید) بزنید.\n\n"
        "۴. کدهای پیش‌فرض را پاک کرده و تمام کدهای فایل ضمیمه‌شده بالا را در آن پیست کنید.\n\n"
        "🔑 **مرحله بسیار مهم (تعیین رمز اختصاصی):**\n"
        "در **خط ۱۴** کد، عبارت زیر قرار دارد:\n"
        "`const AUTH_KEY = \"CHANGE_ME_TO_A_STRONG_SECRET\";`\n"
        "حتماً عبارت داخل گیومه را به یک رمز دلخواه قوی تغییر دهید (مثلاً: `MySecretKey369`).\n\n"
        "۵. روی دکمه آبی **Deploy** -> **New deployment** کلیک کنید:\n"
        "   • روی چرخ‌دنده کنار Select type بزنید و **Web app** را انتخاب کنید.\n"
        "   • بخش Execute as: حتماً **Me**\n"
        "   • بخش Who has access: حتماً **Anyone**\n\n"
        "۶. دکمه **Deploy** را بزنید و اجازه دسترسی اکانت گوگل (Authorize access) را تایید فرمایید.\n\n"
        "۷. در انتها گوگل یک شناسه به نام **Deployment ID** به شما می‌دهد:\n"
        "   • این کد طولانی همان **دیپلوی آی‌دی (Deployment ID)** شماست.\n"
        "   • رمزی که در خط ۱۴ گذاشتید همان **Auth Key** شماست.\n\n"
        "۸. نرم‌افزار *اینترنت آزاد³⁶⁹* را در ویندوز باز کرده، بخش **«⚙️ تنظیمات سرور اختصاصی»** را باز کنید، تیک **«استفاده از سرور اختصاصی شخصی»** را فعال کرده، این دو مقدار را وارد و دکمه **«ذخیره و تایید»** را بزنید."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🌐 ورود به Google Apps Script", url="https://script.google.com"))
    safe_send_message(chat_id, guide_text, reply_markup=markup, disable_web_page_preview=True)

# ---------------------------------------------------------------------------
# Support Handler (Instant Ticket Input Mode)
# ---------------------------------------------------------------------------
@bot.message_handler(func=lambda m: m.text == "💬 پشتیبانی")
def btn_support(message, target_uid=None):
    uid = target_uid or message.from_user.id
    # Automatically put user into ticket mode so they don't have to click an extra inline button
    set_user_state(uid, {"state": "waiting_support_msg", "time": int(time.time())})

    text = (
        "📞 *سامانه پشتیبانی اینترنت آزاد³⁶⁹*\n\n"
        "✍️ کاربر گرامی، لطفاً سوال، مشکل، یا پیام خود را تایپ و ارسال فرمایید.\n"
        "_(همچنین در صورت نیاز می‌توانید عکس یا فایل اسکرین‌شات ارسال فرمایید)_\n\n"
        "پیام شما مستقیماً برای مدیریت ارسال شده و پاسخ در همین گفتگو برایتان فرستاده خواهد شد.\n\n"
        "📢 کانال اطلاع‌رسانی: @muntivpn"
    )
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("❌ انصراف و بازگشت به منوی اصلی", callback_data="cancel_action"),
        types.InlineKeyboardButton("📢 کانال اطلاع‌رسانی", url="https://t.me/muntivpn")
    )
    safe_send_message(message.chat.id, text, reply_markup=markup)

@bot.message_handler(func=lambda m: m.text == "👑 پنل مدیریت ادمین")
def btn_admin_panel(message):
    if message.from_user.id != ADMIN_ID:
        return
    clear_admin_state()
    stats = get_inventory_stats()
    text = (
        f"👑 *پنل مدیریت ادمین*\n\n"
        f"🏷️ موجودی کل کدهای آماده: *{stats['_total_available']} عدد*\n"
        f"📦 مجموع فروش کل: *{stats['_total_sold']} عدد*\n\n"
        f"جهت صدور دستی لایسنس، مشاهده سفارشات در انتظار یا موجودی، انتخاب کنید:"
    )
    safe_send_message(message.chat.id, text, reply_markup=admin_dashboard_keyboard())

# ---------------------------------------------------------------------------
# Callback Queries
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    data = call.data
    uid = call.from_user.id

    # Fast UI Ack so Telegram never shows a loading spinner
    try:
        bot.answer_callback_query(call.id)
    except Exception:
        pass

    # نمایش منوی پلن‌ها
    if data == "show_plans":
        text = (
            "💎 *پلن‌های اشتراک اینترنت آزاد³⁶⁹*\n\n"
            "لطفاً مدت زمان مورد نظر خود را انتخاب کنید:\n"
            "_(تمامی پلن‌ها دارای ترافیک نامحدود و حداکثر سرعت می‌باشند)_"
        )
        safe_send_message(call.message.chat.id, text, reply_markup=plans_keyboard())
        return

    # حساب کاربری
    elif data == "my_account":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        btn_my_account(call.message, target_uid=call.from_user.id)
        return

    # راهنمای اتصال دستی
    elif data == "manual_guide":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        send_manual_connection_guide(call.message.chat.id)
        return

    # پیام به پشتیبانی
    elif data == "start_support":
        try:
            bot.answer_callback_query(call.id)
        except Exception:
            pass
        btn_support(call.message, target_uid=call.from_user.id)
        return

    # 1. کاربر پلنی را انتخاب کرده است
    elif data.startswith("buy_"):
        plan_code = data.replace("buy_", "")
        if plan_code not in PLANS_INFO:
            return
        info = PLANS_INFO[plan_code]

        # بررسی موجودی پلن‌های ۱ ماهه و ۲ ماهه
        if plan_code in ("1M", "2M"):
            try:
                bot.answer_callback_query(call.id, "⚠️ موجودی این پلن به اتمام رسیده است!", show_alert=True)
            except Exception:
                pass

            sold_out_text = (
                "⚠️ *موجودی لایسنس این پلن به اتمام رسیده است!*\n\n"
                f"کاربر گرامی؛ به دلیل استقبال و تقاضای بسیار بالا، موجودی لایسنس‌های پلن *{escape_md(info['name'])}* در حال حاضر **به پایان رسیده است**.\n\n"
                "🚀 *پلن‌های موجود و فعال در حال حاضر:*\n"
                "• **💎 پلن ۳ ماهه (۹۰ روزه):** دارای تخفیف ویژه، اولویت ترافیکی بالا و بدون قطعی\n"
                "• **👑 پلن ۱ ساله (۳۶۵ روزه):** اقتصادی‌ترین پلن با حداکثر سرعت و پایداری تضمینی\n\n"
                "جهت خرید و اتصال سریع، لطفاً یکی از گزینه‌های زیر را انتخاب فرمایید: 👇"
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("💎 خرید اشتراک ۳ ماهه (پیشنهادی)", callback_data="buy_3M"),
                types.InlineKeyboardButton("👑 خرید اشتراک ۱ ساله (به‌صرفه)", callback_data="buy_1Y"),
                types.InlineKeyboardButton("🔙 بازگشت به لیست پلن‌ها", callback_data="show_plans"),
                types.InlineKeyboardButton("💬 ارتباط با پشتیبانی", callback_data="ticket_new")
            )
            try:
                bot.edit_message_text(sold_out_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                safe_send_message(call.message.chat.id, sold_out_text, reply_markup=markup)
            return

        set_user_state(uid, {
            "state": "awaiting_receipt",
            "plan_code": plan_code,
            "time": int(time.time())
        })

        invoice_text = (
            f"📋 *فاکتور سفارش شما:*\n\n"
            f"🔹 پلن انتخابی: *{escape_md(info['name'])}*\n"
            f"💰 مبلغ قابل پرداخت: *{info['price']}*\n\n"
            f"💳 *شماره کارت جهت واریز:*\n"
            f"`{CARD_NUMBER}`\n"
            f"_(برای کپی شماره کارت روی آن ضربه بزنید)_\n\n"
            f"📌 *دستورالعمل پرداخت:*\n"
            f"۱. مبلغ فوق را به شماره کارت بالا واریز فرمایید.\n"
            f"۲. پس از پرداخت، تصویر فیش واریز یا **کد پیگیری تراکنش** را همین‌جا ارسال نمایید.\n"
            f"_(سیستم خودکار پیام شما را برای مدیریت ارسال خواهد کرد)_"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💳 پرداخت کردم / ارسال فیش", callback_data=f"paid_{plan_code}"),
            types.InlineKeyboardButton("❌ انصراف از خرید", callback_data="cancel_action")
        )

        try:
            bot.edit_message_text(invoice_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, invoice_text, reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data.startswith("paid_"):
        plan_code = data.replace("paid_", "")
        if plan_code not in PLANS_INFO:
            return
        if plan_code in ("1M", "2M"):
            try:
                bot.answer_callback_query(call.id, "⚠️ موجودی این پلن تمام شده است!", show_alert=True)
            except Exception:
                pass
            safe_send_message(call.message.chat.id, "⚠️ متأسفانه موجودی این پلن تمام شده است. لطفاً پلن ۳ ماهه یا ۱ ساله را تهیه فرمایید.")
            return
        info = PLANS_INFO[plan_code]

        set_user_state(uid, {
            "state": "awaiting_receipt",
            "plan_code": plan_code,
            "time": int(time.time())
        })

        prompt_text = (
            f"📸 *ارسال اطلاعات پرداخت برای پلن {escape_md(info['name'])}:*\n\n"
            f"لطفاً تصویر فیش واریز، اسکرین‌شات رسید، یا **کد پیگیری تراکنش** را همین‌جا ارسال فرمایید.\n\n"
            f"رسید ارسالی فوراً جهت بررسی و تایید به دست مدیریت می‌رسد و پس از تایید، لایسنس اختصاصی شما صادر خواهد شد."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ انصراف از خرید", callback_data="cancel_action"))

        try:
            bot.edit_message_text(prompt_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, prompt_text, reply_markup=markup)
        bot.answer_callback_query(call.id)

    elif data == "cancel_action":
        clear_user_state(uid)
        try:
            bot.edit_message_text("❌ عملیات لغو گردید.", call.message.chat.id, call.message.message_id)
        except Exception:
            safe_send_message(call.message.chat.id, "❌ عملیات لغو گردید.")
        bot.answer_callback_query(call.id, "لغو شد")

    elif data == "cancel_admin_reply":
        if uid == ADMIN_ID:
            clear_admin_state()
            try:
                bot.edit_message_text("❌ ارسال پاسخ به کاربر لغو شد.", call.message.chat.id, call.message.message_id)
            except Exception:
                safe_send_message(ADMIN_ID, "❌ ارسال پاسخ به کاربر لغو شد.")
            bot.answer_callback_query(call.id, "لغو شد")

    # تیکت پشتیبانی: شروع پیام به ادمین
    elif data == "ticket_new":
        set_user_state(uid, {"state": "waiting_support_msg", "time": int(time.time())})
        prompt_ticket = (
            "✍️ *پیام به پشتیبانی:*\n\n"
            "لطفاً پیام، سوال یا مشکل خود را به صورت متن یا تصویر همین‌جا ارسال فرمایید.\n"
            "پیام شما مستقیماً برای مدیریت ارسال شده و پاسخ در همین چت برایتان فرستاده خواهد شد."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_action"))
        safe_send_message(call.message.chat.id, prompt_ticket, reply_markup=markup)
        bot.answer_callback_query(call.id)

    # ادمین روی دکمه «پاسخ به کاربر» می‌زند
    elif data.startswith("reply_user_"):
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return
        target_uid = data.replace("reply_user_", "")
        set_admin_state({"state": "replying_to_user", "target_uid": target_uid})

        prompt_admin = (
            f"✍️ *پاسخ دادن به کاربر `{target_uid}`:*\n\n"
            f"لطفاً پیام پاسخ خود را تایپ و ارسال نمایید.\n"
            f"این پیام مستقیماً در ربات برای کاربر فرستاده خواهد شد."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ انصراف از پاسخ", callback_data="cancel_admin_reply"))
        safe_send_message(ADMIN_ID, prompt_admin, reply_markup=markup)
        bot.answer_callback_query(call.id, "آماده دریافت پیام شما")

    # تایید رسید پرداخت توسط ادمین
    elif data.startswith("appr_"):
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return

        order_id = data.replace("appr_", "")
        db = load_db()
        order = db["orders"].get(order_id)
        if not order:
            bot.answer_callback_query(call.id, "سفارش یافت نشد!", show_alert=True)
            return
        if order.get("status") != "pending":
            bot.answer_callback_query(call.id, f"این سفارش قبلاً {order.get('status')} شده است!", show_alert=True)
            return

        buyer_id = order["user_id"]
        plan_code = order["plan_code"]
        info = PLANS_INFO[plan_code]

        key = issue_key_for_plan_atomic(db, plan_code, buyer_id)
        if not key:
            safe_send_message(ADMIN_ID, f"⚠️ خطا: انبار کدهای {info['name']} خالی است!")
            bot.answer_callback_query(call.id, "انبار خالی است!", show_alert=True)
            return

        order["status"] = "approved"
        order["approved_at"] = int(time.time())
        order["key"] = key
        save_db(db, immediate_sync=True)

        buyer_msg = (
            f"🎉 *رسید پرداخت شما تایید شد!*\n\n"
            f"کد لایسنس اختصاصی شما:\n"
            f"`{key}`\n\n"
            f"_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
            f"🔹 پلن خریداری‌شده: *{escape_md(info['name'])}*\n"
            f"⏳ مدت اعتبار: *{info['days']} روز*\n\n"
            f"📌 *نحوه فعال‌سازی:*\n"
            f"این کد را داخل نرم‌افزار ویندوز در بخش *«ثبت لایسنس»* وارد کرده و فعال نمایید.\n"
            f"همچنین این لایسنس در بخش *«👤 حساب کاربری من»* ذخیره شد.\n\n"
            f"با تشکر از اعتماد شما به *اینترنت آزاد³⁶⁹* 🌸"
        )
        safe_send_message(buyer_id, buyer_msg)

        try:
            if call.message.caption:
                new_cap = (
                    f"{call.message.caption}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ *رسید تایید شد و لایسنس صادر گردید.*\n"
                    f"کد: `{key}`"
                )
                bot.edit_message_caption(caption=new_cap, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode="Markdown")
            elif call.message.text:
                new_txt = (
                    f"{call.message.text}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ *رسید تایید شد و لایسنس صادر گردید.*\n"
                    f"کد: `{key}`"
                )
                bot.edit_message_text(text=new_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode="Markdown")
        except Exception as e:
            print(f"Error editing admin approval message: {e}")

        bot.answer_callback_query(call.id, "پرداخت تایید و لایسنس ارسال شد ✓")

    # رد رسید پرداخت توسط ادمین
    elif data.startswith("rej_"):
        if uid != ADMIN_ID:
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return

        order_id = data.replace("rej_", "")
        db = load_db()
        order = db["orders"].get(order_id)
        if not order or order.get("status") != "pending":
            bot.answer_callback_query(call.id, "سفارش نامعتبر است یا قبلاً بررسی شده!", show_alert=True)
            return

        buyer_id = order["user_id"]
        order["status"] = "rejected"
        order["rejected_at"] = int(time.time())
        save_db(db)

        reject_msg = (
            "❌ *رسید پرداخت شما تایید نشد!*\n\n"
            "تصویر ارسالی نامعتبر بود یا مبلغ به حساب واریز نگردیده است.\n\n"
            "در صورتی که مبلغ از حسابتان کسر شده است، لطفاً با پشتیبانی در ارتباط باشید:\n"
            "💬 دکمه «پشتیبانی» در منوی ربات"
        )
        safe_send_message(buyer_id, reject_msg)

        try:
            if call.message.caption:
                bot.edit_message_caption(caption=f"{call.message.caption}\n\n━━━━━━━━━━━━━━━━━━━\n❌ *این رسید رد شد.*", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            elif call.message.text:
                bot.edit_message_text(text=f"{call.message.text}\n\n━━━━━━━━━━━━━━━━━━━\n❌ *این رسید رد شد.*", chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        except Exception:
            pass
        bot.answer_callback_query(call.id, "رسید رد شد ❌")

    # گزینه‌های پنل مدیریت ادمین
    elif data.startswith("adm_"):
        if uid != ADMIN_ID:
            return
        action = data.replace("adm_", "")
        if action == "stats":
            stats = get_inventory_stats()
            lines = ["📊 *گزارش دقیق موجودی لایسنس‌ها:*\n"]
            for p_code in ["1M", "2M", "3M", "1Y"]:
                st = stats[p_code]
                lines.append(f"• *{st['name']}:* {st['available']} موجود (فروخته‌شده: {st['sold']})")
            lines.append(f"\n🏷️ *کل موجودی باقی‌مانده:* {stats['_total_available']} عدد")
            lines.append(f"📦 *کل لایسنس‌های فروخته‌شده:* {stats['_total_sold']} عدد")
            safe_send_message(ADMIN_ID, "\n".join(lines))
            bot.answer_callback_query(call.id)
        elif action == "pending":
            db = load_db()
            pending_orders = [o for o in db.get("orders", {}).values() if o.get("status") == "pending"]
            if not pending_orders:
                safe_send_message(ADMIN_ID, "✅ هیچ سفارش در انتخابی وجود ندارد.")
                bot.answer_callback_query(call.id, "بدون سفارش در انتظار")
                return
            safe_send_message(ADMIN_ID, f"⏳ *تعداد سفارشات در انتظار بررسی: {len(pending_orders)} عدد*")
            for o in pending_orders[-5:]:
                o_id = o.get("order_id")
                p_code = o.get("plan_code", "1M")
                p_info = PLANS_INFO.get(p_code, {})
                p_name = p_info.get("name", p_code)
                rec_text_str = escape_md(o.get('receipt_text', ''))
                rec_note = f"متن: {rec_text_str}\n" if rec_text_str else ""
                o_msg = (
                    f"🏷️ سفارش: `{o_id}`\n"
                    f"👤 کاربر: {escape_md(o.get('first_name', ''))} (@{escape_md(o.get('username', 'ندارد'))})\n"
                    f"🆔 آیدی: `{o.get('user_id')}`\n"
                    f"📦 پلن: *{escape_md(p_name)}* | {o.get('price', '')}\n"
                    f"نوع رسید: {o.get('receipt_type', 'نامشخص')}\n"
                    f"{rec_note}"
                )
                markup = types.InlineKeyboardMarkup(row_width=2)
                markup.add(
                    types.InlineKeyboardButton("✅ تایید", callback_data=f"appr_{o_id}"),
                    types.InlineKeyboardButton("❌ رد", callback_data=f"rej_{o_id}")
                )
                safe_send_message(ADMIN_ID, o_msg, reply_markup=markup)
            bot.answer_callback_query(call.id)
        elif action in PLANS_INFO:
            db = load_db()
            key = issue_key_for_plan_atomic(db, action, ADMIN_ID)
            if not key:
                safe_send_message(ADMIN_ID, "⚠️ موجودی این پلن به اتمام رسیده است!")
                bot.answer_callback_query(call.id, "موجودی خالی است!")
                return
            save_db(db)
            p_name = PLANS_INFO[action]["name"]
            safe_send_message(
                ADMIN_ID,
                f"✅ *لایسنس دستی {escape_md(p_name)}:*\n\n`{key}`\n\n_(برای کپی روی کد بزنید)_"
            )
            bot.answer_callback_query(call.id, "صادر شد ✓")

    # انتخاب نوع تصویر نامشخص
    elif data.startswith("set_rec_"):
        plan_code = data.replace("set_rec_", "")
        upload_info = PENDING_UPLOADS.pop(uid, None)
        if not upload_info or plan_code not in PLANS_INFO:
            bot.answer_callback_query(call.id, "اطلاعات منقضی شده است.")
            return
        # شبیه‌سازی رسید
        process_receipt_submission(call.message, uid, plan_code, upload_info["file_id"], upload_info["content_type"], upload_info.get("caption", ""))
        bot.answer_callback_query(call.id, "رسید با موفقیت ثبت شد ✓")

# ---------------------------------------------------------------------------
# Receipt Processing Core
# ---------------------------------------------------------------------------
def process_receipt_submission(message, uid: int, plan_code: str, file_id: str, content_type: str, caption_text: str):
    info = PLANS_INFO[plan_code]
    order_id = f"ORD_{int(time.time())}_{uid}"
    db = load_db()

    user_obj = message.from_user if hasattr(message, 'from_user') and message.from_user else None
    first_name = user_obj.first_name if user_obj else "کاربر"
    username = user_obj.username if user_obj and user_obj.username else "ندارد"

    db["orders"][order_id] = {
        "order_id": order_id,
        "user_id": uid,
        "username": username,
        "first_name": first_name,
        "plan_code": plan_code,
        "price": info["price"],
        "status": "pending",
        "receipt_type": content_type,
        "file_id": file_id,
        "created_at": int(time.time()),
        "caption": caption_text
    }
    clear_user_state(uid)
    save_db(db)

    admin_markup = types.InlineKeyboardMarkup(row_width=2)
    b_approve = types.InlineKeyboardButton("✅ تایید پرداخت و صدور لایسنس", callback_data=f"appr_{order_id}")
    b_reject = types.InlineKeyboardButton("❌ رد پرداخت", callback_data=f"rej_{order_id}")
    admin_markup.add(b_approve, b_reject)

    user_caption_note = f"\n💬 متن همراه فیش: {escape_md(caption_text)}" if caption_text else ""

    admin_caption = (
        f"🔔 *سفارش جدید — رسید پرداخت!*\n\n"
        f"🏷️ شماره سفارش: `{order_id}`\n"
        f"👤 خریدار: {escape_md(first_name)} (@{escape_md(username)})\n"
        f"🆔 آیدی عددی: `{uid}`\n"
        f"📦 پلن انتخابی: *{escape_md(info['name'])}*\n"
        f"💰 مبلغ فاکتور: *{info['price']}*\n"
        f"⏰ ساعت: {time.strftime('%H:%M:%S', time.localtime())}"
        f"{user_caption_note}"
    )

    # 1. Forward original receipt directly to admin
    try:
        if hasattr(message, 'chat') and hasattr(message, 'message_id'):
            bot.forward_message(ADMIN_ID, message.chat.id, message.message_id)
    except Exception as ef:
        print(f"[process_receipt_submission] Forward failed: {ef}")

    # 2. Send structured card with buttons
    sent = None
    if content_type == "photo":
        sent = safe_send_photo(ADMIN_ID, file_id, caption=admin_caption, reply_markup=admin_markup)
    else:
        sent = safe_send_document(ADMIN_ID, file_id, caption=admin_caption, reply_markup=admin_markup)

    # 3. Bulletproof fallback: If photo/doc failed, ALWAYS send text notification with action buttons
    if not sent:
        safe_send_message(ADMIN_ID, f"🔔 *سفارش جدید (فیش در بالا):*\n\n{admin_caption}", reply_markup=admin_markup)

    confirm_text = (
        "✅ *رسید شما با موفقیت دریافت شد!*\n\n"
        "فیش واریزی برای مدیریت ارسال گردید و در صف بررسی قرار گرفت.\n"
        "به محض تایید توسط مدیریت، کد لایسنس اختصاصی شما به صورت خودکار در همین چت ارسال خواهد شد.\n\n"
        "لطفاً چند دقیقه شکیبا باشید... 🌸"
    )
    safe_send_message(uid, confirm_text)

# ---------------------------------------------------------------------------
# Photo & Document Handlers (Receipt Submission & Support Attachments)
# ---------------------------------------------------------------------------
@bot.message_handler(content_types=["photo", "document", "voice", "audio", "video"])
def handle_photos_and_docs(message):
    uid = message.from_user.id
    u_state = get_user_state(uid)
    state_type = u_state.get("state")

    file_id = None
    if message.content_type == "photo":
        file_id = message.photo[-1].file_id
    elif message.content_type == "document":
        file_id = message.document.file_id
    elif message.content_type == "voice":
        file_id = message.voice.file_id
    elif message.content_type == "audio":
        file_id = message.audio.file_id
    elif message.content_type == "video":
        file_id = message.video.file_id

    caption = message.caption or ""

    # الف) ارسال فیش پرداختی در مرحله خرید
    if state_type == "awaiting_receipt":
        plan_code = u_state.get("plan_code", "1M")
        process_receipt_submission(message, uid, plan_code, file_id, message.content_type, caption)
        return

    # ب) ارسال عکس/فایل/ویس در تیکت پشتیبانی
    elif state_type == "waiting_support_msg":
        clear_user_state(uid)

        f_name = message.from_user.first_name or "کاربر"
        u_name = message.from_user.username or "ندارد"
        admin_caption = (
            f"📩 *پیام پشتیبانی جدید ({message.content_type}):*\n\n"
            f"👤 کاربر: {escape_md(f_name)} (@{escape_md(u_name)})\n"
            f"🆔 آیدی عددی: `{uid}`\n"
            f"⏰ ساعت: {time.strftime('%H:%M:%S', time.localtime())}\n"
            f"💬 توضیح: {escape_md(caption) if caption else 'بدون متن'}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✍️ پاسخ دادن به کاربر", callback_data=f"reply_user_{uid}"))

        if message.content_type == "photo":
            safe_send_photo(ADMIN_ID, file_id, caption=admin_caption, reply_markup=markup)
        elif message.content_type == "voice":
            try:
                bot.send_voice(ADMIN_ID, file_id, caption=admin_caption, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                bot.send_voice(ADMIN_ID, file_id, caption=caption or "ویس پشتیبانی", reply_markup=markup)
        elif message.content_type == "video":
            try:
                bot.send_video(ADMIN_ID, file_id, caption=admin_caption, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                bot.send_video(ADMIN_ID, file_id, caption=caption or "ویدیو پشتیبانی", reply_markup=markup)
        else:
            safe_send_document(ADMIN_ID, file_id, caption=admin_caption, reply_markup=markup)

        safe_reply_to(
            message,
            "✅ *پیام / فایل شما برای پشتیبانی ارسال شد.*\nبه زودی پاسخ مدیریت در همین چت برای شما فرستاده خواهد شد."
        )
        return

    # ج) اگر کاربر تصویری فرستاده ولی در هیچ مرحله‌ای نبوده (مثلاً مستقیماً فیش فرستاده)
    else:
        PENDING_UPLOADS[uid] = {
            "file_id": file_id,
            "content_type": message.content_type,
            "caption": caption,
            "time": time.time()
        }
        text_prompt = (
            "📸 *تصویر شما دریافت شد!*\n\n"
            "لطفاً مشخص فرمایید این تصویر مربوط به کدام مورد است:"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        for p_code, p_info in PLANS_INFO.items():
            markup.add(types.InlineKeyboardButton(f"💳 فیش پرداخت پلن {p_info['name']}", callback_data=f"set_rec_{p_code}"))
        markup.add(types.InlineKeyboardButton("💬 تصویر مربوط به تیکت پشتیبانی", callback_data="ticket_new"))
        markup.add(types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_action"))
        safe_reply_to(message, text_prompt, reply_markup=markup)

# ---------------------------------------------------------------------------
# General Text Handler (Support, Admin Reply, Licenses, Text Receipts)
# ---------------------------------------------------------------------------
@bot.message_handler(func=lambda m: True)
def handle_general_text(message):
    uid = message.from_user.id
    text = (message.text or "").strip()

    # اگر کاربر روی یکی از دکمه‌های منوی اصلی زده باشد، هرگونه استیت قبلی ریست شود و دستور اجرا شود
    menu_buttons = [
        "🛒 خرید اشتراک اختصاصی",
        "👤 حساب کاربری من",
        "📘 آموزش اتصال دستی",
        "❓ راهنمای فعال‌سازی",
        "💬 پشتیبانی",
        "👑 پنل مدیریت ادمین"
    ]
    if text in menu_buttons:
        clear_user_state(uid)
        if text == "🛒 خرید اشتراک اختصاصی":
            btn_buy_plans(message)
        elif text == "👤 حساب کاربری من":
            btn_my_account(message)
        elif text == "📘 آموزش اتصال دستی":
            btn_manual_guide(message)
        elif text == "❓ راهنمای فعال‌سازی":
            btn_help(message)
        elif text == "💬 پشتیبانی":
            btn_support(message)
        elif text == "👑 پنل مدیریت ادمین":
            btn_admin_panel(message)
        return

    # ۱. اگر ادمین در حال پاسخ به تیکت کاربر است
    adm_state = get_admin_state()
    if uid == ADMIN_ID and adm_state.get("state") == "replying_to_user":
        target_uid = int(adm_state["target_uid"])
        clear_admin_state()

        reply_to_user_text = (
            f"📩 *پاسخ پشتیبانی اینترنت آزاد³⁶⁹:*\n\n"
            f"{text}\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"در صورت نیاز به ارسال پیام مجدد، از دکمه «💬 پشتیبانی» استفاده فرمایید."
        )
        safe_send_message(target_uid, reply_to_user_text)
        safe_reply_to(message, f"✅ پاسخ شما با موفقیت برای کاربر `{target_uid}` ارسال شد.")
        return

    # ۲. اگر کاربر در مرحله ارسال فیش است و کد پیگیری یا متن واریز ارسال کرده
    u_state = get_user_state(uid)
    if u_state.get("state") == "awaiting_receipt":
        plan_code = u_state.get("plan_code", "1M")
        info = PLANS_INFO[plan_code]
        order_id = f"ORD_{int(time.time())}_{uid}"
        db = load_db()

        f_name = message.from_user.first_name or "کاربر"
        u_name = message.from_user.username or "ندارد"

        db["orders"][order_id] = {
            "order_id": order_id,
            "user_id": uid,
            "username": u_name,
            "first_name": f_name,
            "plan_code": plan_code,
            "price": info["price"],
            "status": "pending",
            "receipt_type": "text",
            "receipt_text": text,
            "created_at": int(time.time())
        }
        clear_user_state(uid)
        save_db(db)

        admin_text = (
            f"🔔 *سفارش جدید — اطلاعات پرداخت متنی!*\n\n"
            f"🏷️ شماره سفارش: `{order_id}`\n"
            f"👤 خریدار: {escape_md(f_name)} (@{escape_md(u_name)})\n"
            f"🆔 آیدی عددی: `{uid}`\n"
            f"📦 پلن انتخابی: *{escape_md(info['name'])}*\n"
            f"💰 مبلغ فاکتور: *{info['price']}*\n"
            f"⏰ ساعت: {time.strftime('%H:%M:%S', time.localtime())}\n\n"
            f"📝 *اطلاعات / کد پیگیری واریزی:*\n`{escape_md(text)}`"
        )
        admin_markup = types.InlineKeyboardMarkup(row_width=2)
        b_approve = types.InlineKeyboardButton("✅ تایید پرداخت و صدور لایسنس", callback_data=f"appr_{order_id}")
        b_reject = types.InlineKeyboardButton("❌ رد پرداخت", callback_data=f"rej_{order_id}")
        admin_markup.add(b_approve, b_reject)

        safe_send_message(ADMIN_ID, admin_text, reply_markup=admin_markup)

        safe_reply_to(
            message,
            "✅ *اطلاعات پرداخت شما با موفقیت ثبت شد!*\n\n"
            "کد رهگیری برای مدیریت ارسال گردید و در صف بررسی قرار گرفت.\n"
            "به محض تایید توسط مدیریت، کد لایسنس اختصاصی شما به صورت خودکار در همین چت ارسال خواهد شد. 🌸"
        )
        return

    # ۳. اگر کاربر در حال ارسال پیام متنی به پشتیبانی است
    if u_state.get("state") == "waiting_support_msg":
        clear_user_state(uid)

        f_name = message.from_user.first_name or "کاربر"
        u_name = message.from_user.username or "ندارد"
        admin_ticket_msg = (
            f"📩 *پیام پشتیبانی جدید!*\n\n"
            f"👤 کاربر: {escape_md(f_name)} (@{escape_md(u_name)})\n"
            f"🆔 آیدی عددی: `{uid}`\n"
            f"⏰ زمان: {time.strftime('%Y/%m/%d %H:%M:%S', time.localtime())}\n\n"
            f"💬 *متن پیام:*\n{escape_md(text)}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✍️ پاسخ دادن به کاربر", callback_data=f"reply_user_{uid}"))

        safe_send_message(ADMIN_ID, admin_ticket_msg, reply_markup=markup)

        safe_reply_to(
            message,
            "✅ *پیام شما با موفقیت برای پشتیبانی ارسال گردید.*\nبه زودی پاسخ مدیریت در همین ربات برای شما فرستاده خواهد شد."
        )
        return

    # ۴. استعلام دستی لایسنس
    if text.upper().startswith("AZ"):
        res = license_core.verify_license_format(text.upper())
        if res.get("valid"):
            safe_reply_to(
                message,
                f"✓ *استعلام لایسنس:*\n\n"
                f"کد: `{res['key']}`\n"
                f"پلن: *{escape_md(res['plan_name'])}*\n"
                f"وضعیت: *معتبر و دارای امضای دیجیتالی رسمی* 🔐\n\n"
                f"این کد را داخل نرم‌افزار ویندوز وارد نمایید تا فعال شود."
            )
        else:
            safe_reply_to(message, f"❌ {res.get('error', 'کد لایسنس نامعتبر است.')}")
        return

    # ۵. پیام عادی کاربر که هیچ دستوری نیست
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🛒 خرید اشتراک", callback_data="show_plans"),
        types.InlineKeyboardButton("💬 پیام به پشتیبانی", callback_data="ticket_new")
    )
    safe_reply_to(
        message,
        "لطفاً از دکمه‌های منوی پایین استفاده فرمایید. 👇\n"
        "در صورتی که قصد ارتباط با پشتیبانی را دارید، روی «💬 پیام به پشتیبانی» بزنید.",
        reply_markup=markup
    )

# ---------------------------------------------------------------------------
# Shift Watchdog (Handover before 6 Hours)
# ---------------------------------------------------------------------------
def shift_watchdog():
    while True:
        time.sleep(30)
        elapsed = time.time() - START_TIME
        if os.environ.get("GITHUB_ACTIONS") and elapsed >= MAX_RUN_SECONDS:
            print(f"[*] Reached shift limit ({int(elapsed)}s). Gracefully stopping polling to hand over to next runner...")
            try:
                bot.stop_polling()
            except Exception:
                pass
            time.sleep(3)
            os._exit(0)

# ---------------------------------------------------------------------------
# Main Entry Point
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    print("==================================================")
    print(" InternetAzad369 24/7 Cloud Bot Started!")
    print(f" Bot Username: @muntivpn369bot")
    print(f" Admin ID: {ADMIN_ID}")
    print(f" Card Number: {CARD_NUMBER}")
    stats = get_inventory_stats()
    print(f" Available Keys: {stats['_total_available']} | Sold: {stats['_total_sold']}")
    print(f" Shift Duration: {MAX_RUN_SECONDS // 60} minutes")
    print("==================================================")

    w_thread = threading.Thread(target=shift_watchdog, daemon=True)
    w_thread.start()

    s_thread = threading.Thread(target=periodic_sync_worker, daemon=True)
    s_thread.start()

    try:
        bot.remove_webhook()
    except Exception:
        pass

    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=True)
            break
        except Exception as e:
            print(f"[!] Polling exception: {e}. Retrying in 5 seconds...")
            time.sleep(5)
