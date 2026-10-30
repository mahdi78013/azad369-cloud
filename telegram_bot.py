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
import copy
import time
import datetime
import re
import threading
import subprocess
import secrets
import hmac
import hashlib
import urllib.request
import urllib.error
from http.server import HTTPServer, BaseHTTPRequestHandler

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

def _load_bot_secret(key: str, default: str = "") -> str:
    """Load secret from environment variable (GitHub Actions / Cloud) or local .bot_secrets.json."""
    val = os.environ.get(key)
    if val:
        return val.strip()
    sec_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".bot_secrets.json")
    if os.path.exists(sec_path):
        try:
            with open(sec_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if key in data and data[key]:
                    return str(data[key]).strip()
        except Exception:
            pass
    return default

BOT_TOKEN = _load_bot_secret("BOT_TOKEN")

# Multi-Admin Support
# Primary: 748538264 (Mahdi)
# Co-Admin: 6465999269 (Amin @AMIN_4918)
def _load_admin_ids() -> list:
    base_admins = {748538264, 6465999269}
    env_admin = _load_bot_secret("ADMIN_ID", "")
    if env_admin:
        for part in env_admin.replace(";", ",").split(","):
            part = part.strip()
            if part.isdigit():
                base_admins.add(int(part))
    return sorted(list(base_admins))

ADMIN_IDS = _load_admin_ids()
ADMIN_ID = ADMIN_IDS[0]

def is_admin(user_id: int) -> bool:
    """Checks whether user_id is in the authorized admin list."""
    try:
        return int(user_id) in ADMIN_IDS
    except (ValueError, TypeError):
        return False

# Multi-Card Rotation System (Prevents hitting daily bank transfer limits)
DEFAULT_CARDS = ["5892101706458979", "5047061670546072"]
CARD_ROTATION_THRESHOLD = 10

def _load_card_numbers() -> list:
    cards = list(DEFAULT_CARDS)
    raw_env = _load_bot_secret("CARD_NUMBERS", "")
    if raw_env:
        custom_cards = [c.strip() for c in raw_env.replace(";", ",").split(",") if c.strip().isdigit() and len(c.strip()) >= 16]
        if custom_cards:
            return custom_cards
    single = _load_bot_secret("CARD_NUMBER", "")
    if single and single not in cards and single.isdigit() and len(single) >= 16:
        cards.append(single)
    return cards

CARD_NUMBERS = _load_card_numbers()
CARD_NUMBER = CARD_NUMBERS[0]
CARD_TO_CARD_ENABLED = False  # موقتاً غیرفعال طبق دستور کاربر (فقط درگاه آنلاین فعال است)

# Tronado Telegram Payment Gateway Integration
TRONADO_API_KEY = _load_bot_secret("TRONADO_API_KEY", "3fbc62386a2c373f025e299595be4481df481c37b582bb2ed429f2c46e25ce3e")
TRONADO_IPN_KEY = _load_bot_secret("TRONADO_IPN_KEY", "iQjTd0sa6rtmMOQXdiXWmjBbGfmRXn74M0FGCi81Hcw=")
TRONADO_USER_TAG = _load_bot_secret("TRONADO_USER_TAG", "MUNTIVPN")
TRONADO_REQUEST_CODE = _load_bot_secret("TRONADO_REQUEST_CODE", "muntivpn")
TRONADO_WALLET = _load_bot_secret("TRONADO_WALLET", "TQUaW5e18ER176Zi7datF9ttDBRYWGeiad")
TRONADO_CALLBACK_URL = _load_bot_secret("TRONADO_CALLBACK_URL", "https://muntivpn.koyeb.app/tronado/callback")
TRONADO_BASE_URL = "https://bot.tronado.cloud"
TRONADO_ENABLED = bool(TRONADO_API_KEY and TRONADO_WALLET)

if not BOT_TOKEN:
    print("[ERROR] BOT_TOKEN is not configured! Please set BOT_TOKEN env variable or configure .bot_secrets.json.")
    sys.exit(1)

# Run duration per GitHub Actions session before handing over to the next runner
MAX_RUN_SECONDS = int(os.environ.get("MAX_RUN_SECONDS", 20400))
START_TIME = time.time()

PLANS_INFO = {
    # پلن‌های نرم‌افزار ویندوز (کامپیوتر)
    "1M": {
        "name": "۱ ماهه ویندوز (۳۰ روزه)",
        "price": "۶۰,۰۰۰ تومان",
        "price_toman": 60000,
        "prefix": "AZ1M",
        "platform": "windows",
        "file": "1M.txt",
        "fallback_file": "1_ماهه_1000_عدد.txt",
        "days": 30
    },
    "2M": {
        "name": "۲ ماهه ویندوز (۶۰ روزه)",
        "price": "۱۰۰,۰۰۰ تومان",
        "price_toman": 100000,
        "prefix": "AZ2M",
        "platform": "windows",
        "file": "2M.txt",
        "fallback_file": "2_ماهه_1000_عدد.txt",
        "days": 60
    },
    "3M": {
        "name": "۳ ماهه ویندوز (۹۰ روزه)",
        "price": "۱۴۹,۰۰۰ تومان",
        "price_toman": 149000,
        "prefix": "AZ3M",
        "platform": "windows",
        "file": "3M.txt",
        "fallback_file": "3_ماهه_1000_عدد.txt",
        "days": 90
    },
    "1Y": {
        "name": "۱ ساله ویندوز (۳۶۵ روزه)",
        "price": "۳۹۹,۰۰۰ تومان",
        "price_toman": 399000,
        "prefix": "AZ1Y",
        "platform": "windows",
        "file": "1Y.txt",
        "fallback_file": "1_ساله_1000_عدد.txt",
        "days": 365
    },
    # پلن‌های اختصاصی اپلیکیشن اندروید (موبایل)
    "AN1M": {
        "name": "۱ ماهه اندروید (۳۰ روزه)",
        "price": "۶۰,۰۰۰ تومان",
        "price_toman": 60000,
        "prefix": "AN1M",
        "platform": "android",
        "file": "",
        "fallback_file": "",
        "days": 30
    },
    "AN2M": {
        "name": "۲ ماهه اندروید (۶۰ روزه)",
        "price": "۱۰۰,۰۰۰ تومان",
        "price_toman": 100000,
        "prefix": "AN2M",
        "platform": "android",
        "file": "",
        "fallback_file": "",
        "days": 60
    },
    "AN3M": {
        "name": "۳ ماهه اندروید (۹۰ روزه)",
        "price": "۱۴۹,۰۰۰ تومان",
        "price_toman": 149000,
        "prefix": "AN3M",
        "platform": "android",
        "file": "",
        "fallback_file": "",
        "days": 90
    },
    "AN1Y": {
        "name": "۱ ساله اندروید (۳۶۵ روزه)",
        "price": "۳۹۹,۰۰۰ تومان",
        "price_toman": 399000,
        "prefix": "AN1Y",
        "platform": "android",
        "file": "",
        "fallback_file": "",
        "days": 365
    },
    # پلن پکیج دوگانه ویژه (VIP) — همزمان ویندوز + اندروید
    "VIP1Y": {
        "name": "۱ ساله VIP (ویندوز + اندروید)",
        "price": "۴۹۹,۰۰۰ تومان",
        "price_toman": 499000,
        "prefix": "VIP1Y",
        "platform": "dual",
        "file": "",
        "fallback_file": "",
        "days": 365
    }
}

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "licenses")
STATE_FILE = os.path.join(BASE_DIR, "bot_licenses_state.json")

bot = telebot.TeleBot(BOT_TOKEN, parse_mode="Markdown", num_threads=8)

# Global lock for thread-safe database mutations (Must be RLock to prevent self-deadlocks on nested calls)
DB_LOCK = threading.RLock()

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
    If message exceeds 3800 characters, automatically chunks it to comply with Telegram limits.
    If Telegram rejects entities (e.g. unescaped symbols), falls back to plain text.
    Guarantees that no message to user or admin is ever lost!
    """
    if len(text) > 3800:
        parts = []
        cur_part = []
        cur_len = 0
        for line in text.split("\n"):
            if cur_len + len(line) + 1 > 3500 and cur_part:
                parts.append("\n".join(cur_part))
                cur_part = [line]
                cur_len = len(line) + 1
            else:
                cur_part.append(line)
                cur_len += len(line) + 1
        if cur_part:
            parts.append("\n".join(cur_part))

        res = None
        for i, part in enumerate(parts):
            rm = reply_markup if i == len(parts) - 1 else None
            res = _do_safe_send(chat_id, part, reply_markup=rm, disable_web_page_preview=disable_web_page_preview)
        return res

    return _do_safe_send(chat_id, text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)

def _do_safe_send(chat_id: int, text: str, reply_markup=None, disable_web_page_preview: bool = True):
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

def safe_answer_callback(call_id: str, text: str = None, show_alert: bool = False):
    """Safely answers a callback query without throwing exceptions if already answered or timed out."""
    try:
        return bot.answer_callback_query(call_id, text=text, show_alert=show_alert)
    except Exception:
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

def notify_admins_message(text: str, reply_markup=None, disable_web_page_preview: bool = True):
    """Sends a message to all registered admins."""
    res = None
    for aid in ADMIN_IDS:
        try:
            r = safe_send_message(aid, text, reply_markup=reply_markup, disable_web_page_preview=disable_web_page_preview)
            if not res:
                res = r
        except Exception as e:
            print(f"[notify_admins_message] Error sending to admin {aid}: {e}")
    return res

def notify_admins_photo(photo, caption: str = "", reply_markup=None):
    """Sends a photo to all registered admins."""
    res = None
    for aid in ADMIN_IDS:
        try:
            r = safe_send_photo(aid, photo, caption=caption, reply_markup=reply_markup)
            if not res:
                res = r
        except Exception as e:
            print(f"[notify_admins_photo] Error sending photo to admin {aid}: {e}")
    return res

def notify_admins_document(document, caption: str = "", reply_markup=None):
    """Sends a document to all registered admins."""
    res = None
    for aid in ADMIN_IDS:
        try:
            r = safe_send_document(aid, document, caption=caption, reply_markup=reply_markup)
            if not res:
                res = r
        except Exception as e:
            print(f"[notify_admins_document] Error sending doc to admin {aid}: {e}")
    return res

def forward_to_admins(from_chat_id: int, message_id: int):
    """Forwards a message to all registered admins."""
    for aid in ADMIN_IDS:
        try:
            bot.forward_message(aid, from_chat_id, message_id)
        except Exception as e:
            print(f"[forward_to_admins] Error forwarding to admin {aid}: {e}")

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

def set_admin_state(state_data: dict, admin_id: int = None):
    aid = admin_id or ADMIN_ID
    ADMIN_STATES[aid] = state_data
    db = load_db()
    ast = db.setdefault("admin_states", {})
    if isinstance(ast, dict):
        ast[str(aid)] = state_data
    save_db(db)

def get_admin_state(admin_id: int = None) -> dict:
    aid = admin_id or ADMIN_ID
    if aid in ADMIN_STATES:
        return ADMIN_STATES[aid]
    db = load_db()
    ast = db.get("admin_states", {})
    if isinstance(ast, dict):
        if str(aid) in ast and isinstance(ast[str(aid)], dict):
            ADMIN_STATES[aid] = ast[str(aid)]
            return ast[str(aid)]
        if "state" in ast:
            return ast
    return {}

def clear_admin_state(admin_id: int = None):
    db = load_db()
    if admin_id:
        ADMIN_STATES.pop(admin_id, None)
        if isinstance(db.get("admin_states"), dict):
            db["admin_states"].pop(str(admin_id), None)
            save_db(db)
    else:
        ADMIN_STATES.clear()
        db["admin_states"] = {}
        save_db(db)

# ---------------------------------------------------------------------------
# Multi-Card Rotation System
# ---------------------------------------------------------------------------
def get_card_state(db: dict = None) -> dict:
    """Returns the card rotation state dict from db, initializing defaults if missing."""
    if db is None:
        db = load_db()
    c_state = db.setdefault("card_state", {})
    c_state.setdefault("current_index", 0)
    c_state.setdefault("count", 0)
    c_state.setdefault("threshold", CARD_ROTATION_THRESHOLD)
    c_state.setdefault("stats", {})
    for c in CARD_NUMBERS:
        c_state["stats"].setdefault(c, 0)
    return c_state

def get_random_card_number() -> str:
    """Returns a truly random bank card number from available cards for each payment/invoice."""
    if not CARD_NUMBERS:
        return "5892101706458979"
    return secrets.choice(CARD_NUMBERS)

def get_active_card_number() -> str:
    """Returns a random bank card number for user payment."""
    return get_random_card_number()

def record_card_deposit_and_rotate(db: dict) -> tuple:
    """
    Called upon every incoming payment receipt.
    Increments current card deposit counter.
    When counter reaches threshold (default 10), rotates to next card.
    Returns: (active_card, did_rotate, next_card)
    """
    c_state = get_card_state(db)
    idx = c_state.get("current_index", 0) % len(CARD_NUMBERS)
    active_card = CARD_NUMBERS[idx]

    c_state["count"] = c_state.get("count", 0) + 1
    c_state["stats"][active_card] = c_state["stats"].get(active_card, 0) + 1

    did_rotate = False
    next_card = active_card
    threshold = c_state.get("threshold", CARD_ROTATION_THRESHOLD)

    if c_state["count"] >= threshold:
        new_idx = (idx + 1) % len(CARD_NUMBERS)
        c_state["current_index"] = new_idx
        c_state["count"] = 0
        next_card = CARD_NUMBERS[new_idx]
        did_rotate = True

    return (active_card, did_rotate, next_card)

# ---------------------------------------------------------------------------
# Data Persistence & Instant Git Auto-Sync
# ---------------------------------------------------------------------------
def migrate_historical_users(data: dict) -> bool:
    """Ensures all users from orders, issued, user_states, and trial_users are indexed in data['users']."""
    changed = False
    now = int(time.time())
    users_dict = data.setdefault("users", {})

    # 1. From orders
    for order in data.get("orders", {}).values():
        if isinstance(order, dict) and "user_id" in order and order["user_id"]:
            uid_str = str(order["user_id"])
            if uid_str not in users_dict:
                users_dict[uid_str] = {
                    "user_id": order["user_id"],
                    "first_name": order.get("first_name", "کاربر"),
                    "username": order.get("username", ""),
                    "first_seen": order.get("created_at", now),
                    "last_seen": order.get("created_at", now),
                    "purchases": []
                }
                changed = True

    # 2. From issued keys
    for rec in data.get("issued", {}).values():
        if isinstance(rec, dict) and "user_id" in rec and rec["user_id"]:
            uid_str = str(rec["user_id"])
            if uid_str not in users_dict:
                users_dict[uid_str] = {
                    "user_id": rec["user_id"],
                    "first_name": "کاربر",
                    "username": "",
                    "first_seen": rec.get("issued_at", now),
                    "last_seen": rec.get("issued_at", now),
                    "purchases": []
                }
                changed = True

    # 3. From user_states
    for uid_str in data.get("user_states", {}).keys():
        if uid_str and uid_str.isdigit() and uid_str not in users_dict:
            users_dict[uid_str] = {
                "user_id": int(uid_str),
                "first_name": "کاربر",
                "username": "",
                "first_seen": now,
                "last_seen": now,
                "purchases": []
            }
            changed = True

    # 4. From trial_users
    trial_data = data.get("trial_users", {})
    trial_list = trial_data.keys() if isinstance(trial_data, dict) else trial_data
    for uid in trial_list:
        uid_str = str(uid)
        if uid_str.isdigit() and uid_str not in users_dict:
            users_dict[uid_str] = {
                "user_id": int(uid_str),
                "first_name": "کاربر",
                "username": "",
                "first_seen": now,
                "last_seen": now,
                "purchases": []
            }
            changed = True

    return changed

def track_user(user):
    """Ensure user is saved/updated in db['users'] so stats are always 100% live and complete."""
    if not user or getattr(user, "is_bot", False):
        return
    uid_str = str(user.id)
    now = int(time.time())
    db = load_db()
    u = db["users"].get(uid_str)
    if not u:
        db["users"][uid_str] = {
            "user_id": user.id,
            "first_name": user.first_name or "",
            "last_name": user.last_name or "",
            "username": user.username or "",
            "first_seen": now,
            "last_seen": now,
            "purchases": []
        }
        save_db(db)
    else:
        changed = False
        if not u.get("user_id"):
            u["user_id"] = user.id
            changed = True
        if user.first_name and u.get("first_name") != user.first_name:
            u["first_name"] = user.first_name
            changed = True
        if user.username and u.get("username") != user.username:
            u["username"] = user.username
            changed = True
        if now - u.get("last_seen", 0) > 300:
            u["last_seen"] = now
            changed = True
        if changed:
            save_db(db)

_LAST_VALID_DB = None

def load_db() -> dict:
    global _LAST_VALID_DB
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
                    pa = data.setdefault("plan_availability", {})
                    for p in ("1M", "2M", "3M", "1Y", "AN1M", "AN2M", "AN3M", "AN1Y", "VIP1Y"):
                        pa.setdefault(p, False)
                    for u_obj in data["users"].values():
                        if isinstance(u_obj, dict):
                            u_obj.setdefault("purchases", [])
                    if migrate_historical_users(data):
                        try:
                            tmp_f = f"{STATE_FILE}.tmp.{os.getpid()}.{secrets.token_hex(4)}"
                            with open(tmp_f, "w", encoding="utf-8") as fw:
                                json.dump(data, fw, ensure_ascii=False, indent=2)
                            os.replace(tmp_f, STATE_FILE)
                        except Exception:
                            pass
                    _LAST_VALID_DB = copy.deepcopy(data)
                    return data
            except Exception as e:
                print(f"Error loading db: {e}")
                if _LAST_VALID_DB:
                    return copy.deepcopy(_LAST_VALID_DB)

        if _LAST_VALID_DB:
            return copy.deepcopy(_LAST_VALID_DB)

        d = {
            "issued": {},
            "orders": {},
            "users": {},
            "user_states": {},
            "admin_states": {},
            "trial_users": {},
            "plan_availability": {"1M": False, "2M": False, "3M": False, "1Y": True, "AN1M": False, "AN2M": False, "AN3M": False, "AN1Y": True}
        }
        _LAST_VALID_DB = copy.deepcopy(d)
        return d

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
        subprocess.run(["git", "rebase", "--abort"], check=False)
        subprocess.run(["git", "add", "bot_licenses_state.json", "hwid_registry.json", "historical_blacklist.json"], check=False)
        subprocess.run(["git", "commit", "-m", "Auto-sync bot state [skip ci]"], check=False)
        subprocess.run(["git", "pull", "--rebase", "-Xours", "--autostash", "origin", "main"], check=False)
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
    global _LAST_VALID_DB
    with DB_LOCK:
        try:
            _LAST_VALID_DB = copy.deepcopy(db)
            tmp_file = f"{STATE_FILE}.tmp.{os.getpid()}.{secrets.token_hex(4)}"
            with open(tmp_file, "w", encoding="utf-8") as f:
                json.dump(db, f, ensure_ascii=False, indent=2)
            os.replace(tmp_file, STATE_FILE)
        except Exception as e:
            print(f"Error saving db to file: {e}")
            return
    trigger_git_sync(immediate=immediate_sync)

# ---------------------------------------------------------------------------
# Dynamic Plan Availability Subsystem (موجودی و باز/بستن پلن‌ها توسط ادمین)
# ---------------------------------------------------------------------------
def get_plan_availability() -> dict:
    """
    Returns a dictionary of plan_code -> bool indicating whether each plan is available.
    Persisted in bot_licenses_state.json so toggles are 100% persistent across bot restarts.
    """
    default_avail = {
        "1M": False,
        "2M": False,
        "3M": False,
        "1Y": True,
        "AN1M": False,
        "AN2M": False,
        "AN3M": False,
        "AN1Y": True
    }
    try:
        db = load_db()
        stored = db.get("plan_availability")
        if isinstance(stored, dict):
            default_avail.update(stored)
    except Exception as e:
        print(f"[get_plan_availability] Error: {e}")
    return default_avail

def is_plan_available(plan_code: str) -> bool:
    """Checks whether a specific plan is currently in-stock and open for purchase."""
    avail = get_plan_availability()
    return bool(avail.get(plan_code, False))

def set_plan_availability(plan_code: str, is_available: bool) -> bool:
    """Toggles a plan's availability, saves to DB, and immediately syncs to Git."""
    with DB_LOCK:
        db = load_db()
        avail = db.setdefault("plan_availability", {
            "1M": False,
            "2M": False,
            "3M": False,
            "1Y": False
        })
        avail[plan_code] = bool(is_available)
        save_db(db, immediate_sync=True)
        return avail[plan_code]

# ---------------------------------------------------------------------------
# Live Analytics & Broadcast Core
# ---------------------------------------------------------------------------
def get_live_bot_stats() -> str:
    """Returns a rich, real-time statistics report of users, orders, and bot activity."""
    db = load_db()
    users = db.get("users", {})
    now = int(time.time())

    total_users = len(users)
    active_24h = sum(1 for u in users.values() if isinstance(u, dict) and now - u.get("last_seen", 0) <= 86400)
    new_today = sum(1 for u in users.values() if isinstance(u, dict) and now - u.get("first_seen", 0) <= 86400)
    blocked_count = sum(1 for u in users.values() if isinstance(u, dict) and u.get("blocked", False))

    orders = db.get("orders", {})
    total_orders = len(orders)
    approved_orders = sum(1 for o in orders.values() if isinstance(o, dict) and o.get("status") == "approved")
    pending_orders = sum(1 for o in orders.values() if isinstance(o, dict) and o.get("status") == "pending")

    issued = db.get("issued", {})
    total_sold = len(issued)

    stats = get_inventory_stats()
    c_state = get_card_state(db)
    active_card = get_active_card_number()
    c_cnt = c_state.get("count", 0)
    c_threshold = c_state.get("threshold", CARD_ROTATION_THRESHOLD)
    local_time_str = time.strftime("%Y/%m/%d - %H:%M:%S", time.localtime())

    text = (
        f"📊 *آمار جامع و آنلاین ربات تلگرام (اینترنت آزاد³⁶⁹)*\n\n"
        f"👥 *آمار کاربران:*\n"
        f"• کل کاربران ثبت‌شده تا این لحظه: *{total_users} نفر*\n"
        f"• کاربران فعال در ۲۴ ساعت گذشته: *{active_24h} نفر*\n"
        f"• کاربران جدید امروز: *{new_today} نفر*\n"
        f"• کاربران غیرفعال/بلاک‌کرده: *{blocked_count} نفر*\n"
        f"• وضعیت سرور ربات: *آنلاین و فعال 🟢*\n\n"
        f"💰 *آمار فروش و لایسنس:*\n"
        f"• کل سفارشات ثبت‌شده: *{total_orders} عدد*\n"
        f"• سفارشات موفق (تاییدشده): *{approved_orders} عدد*\n"
        f"• سفارشات در انتظار بررسی: *{pending_orders} عدد*\n"
        f"• مجموع کل لایسنس‌های تحویل‌شده: *{total_sold} عدد*\n\n"
        f"💳 *وضعیت کارت‌های بانکی واریز:*\n"
        f"• شماره کارت فعال فعلی: `{active_card}`\n"
        f"• شمارنده چرخش هوشمند: *{c_cnt} از {c_threshold} واریز*\n"
        f"• تعداد کارت‌های در نوبت: *{len(CARD_NUMBERS)} عدد*\n\n"
        f"📦 *موجودی آماده فروش انبار:*\n"
        f"• پلن ۱ ماهه: *{stats.get('1M', {}).get('clean_on_disk', 0)} عدد*\n"
        f"• پلن ۲ ماهه: *{stats.get('2M', {}).get('clean_on_disk', 0)} عدد*\n"
        f"• پلن ۳ ماهه: *{stats.get('3M', {}).get('clean_on_disk', 0)} عدد*\n"
        f"• پلن ۱ ساله: *{stats.get('1Y', {}).get('clean_on_disk', 0)} عدد*\n"
        f"• مجموع کل موجودی انبار: *{stats.get('_total_available', 0)} عدد*\n\n"
        f"🕒 تاریخ و ساعت گزارش: `{local_time_str}`"
    )
    return text

def get_all_broadcast_targets(db: dict = None) -> list[int]:
    """
    Returns a comprehensive, deduplicated list of ALL telegram user IDs
    who have ever started, ordered, or interacted with the bot.
    Collects from: users, orders, issued, user_states, and trial_users.
    """
    if db is None:
        db = load_db()
    else:
        migrate_historical_users(db)

    uids_set = set()

    # 1. db['users']
    for uid_k in db.get("users", {}).keys():
        s = str(uid_k).strip()
        if s.isdigit() and int(s) > 0:
            uids_set.add(int(s))

    # 2. db['orders']
    for order in db.get("orders", {}).values():
        if isinstance(order, dict) and order.get("user_id"):
            try:
                val = int(order["user_id"])
                if val > 0:
                    uids_set.add(val)
            except Exception:
                pass

    # 3. db['issued']
    for iss in db.get("issued", {}).values():
        if isinstance(iss, dict) and iss.get("user_id"):
            try:
                val = int(iss["user_id"])
                if val > 0:
                    uids_set.add(val)
            except Exception:
                pass

    # 4. db['user_states']
    for uid_k in db.get("user_states", {}).keys():
        s = str(uid_k).strip()
        if s.isdigit() and int(s) > 0:
            uids_set.add(int(s))

    # 5. db['trial_users']
    tu = db.get("trial_users", {})
    t_items = tu.keys() if isinstance(tu, dict) else tu
    for uid_k in t_items:
        s = str(uid_k).strip()
        if s.isdigit() and int(s) > 0:
            uids_set.add(int(s))

    return sorted(list(uids_set))

BROADCAST_ACTIVE = False
BROADCAST_CANCELLED = False

def get_broadcast_reply_markup(button_type: str):
    """Returns (InlineKeyboardMarkup, title) for the chosen broadcast button type."""
    if not button_type or button_type == "none":
        return None, "بدون دکمه شیشه‌ای"

    markup = types.InlineKeyboardMarkup()
    if button_type == "plans":
        markup.add(types.InlineKeyboardButton("🛒 خرید اشتراک اختصاصی", callback_data="show_plans"))
        return markup, "🛒 خرید اشتراک اختصاصی"

    elif button_type == "android":
        markup.add(types.InlineKeyboardButton("📱 خرید اشتراک اندروید (موبایل)", callback_data="show_plans_android"))
        return markup, "📱 خرید اشتراک اندروید"

    elif button_type == "windows":
        markup.add(types.InlineKeyboardButton("💻 خرید اشتراک ویندوز (کامپیوتر)", callback_data="show_plans_windows"))
        return markup, "💻 خرید اشتراک ویندوز"

    elif button_type == "both":
        markup.row_width = 2
        markup.add(
            types.InlineKeyboardButton("📱 خرید اندروید", callback_data="show_plans_android"),
            types.InlineKeyboardButton("💻 خرید ویندوز", callback_data="show_plans_windows")
        )
        return markup, "📱 خرید اندروید + 💻 خرید ویندوز"

    elif button_type == "VIP1Y":
        markup.add(types.InlineKeyboardButton("👑 خرید ۱ ساله VIP (ویندوز + اندروید)", callback_data="buy_VIP1Y"))
        return markup, "👑 ۱ ساله VIP (ویندوز + اندروید)"

    elif button_type == "AN1Y":
        markup.add(types.InlineKeyboardButton("👑 خرید اشتراک ۱ ساله اندروید (۳۶۵ روزه)", callback_data="buy_AN1Y"))
        return markup, "👑 ۱ ساله اندروید (۳۶۵ روزه)"

    elif button_type == "1Y":
        markup.add(types.InlineKeyboardButton("👑 خرید اشتراک ۱ ساله ویندوز (۳۶۵ روزه)", callback_data="buy_1Y"))
        return markup, "👑 ۱ ساله ویندوز (۳۶۵ روزه)"

    elif button_type == "both_1Y":
        markup.row_width = 2
        markup.add(
            types.InlineKeyboardButton("👑 ۱ ساله اندروید", callback_data="buy_AN1Y"),
            types.InlineKeyboardButton("👑 ۱ ساله ویندوز", callback_data="buy_1Y")
        )
        return markup, "👑 ۱ ساله اندروید + 👑 ۱ ساله ویندوز"

    elif button_type == "AN3M":
        markup.add(types.InlineKeyboardButton("💎 خرید اشتراک ۳ ماهه اندروید", callback_data="buy_AN3M"))
        return markup, "💎 ۳ ماهه اندروید"

    elif button_type == "3M":
        markup.add(types.InlineKeyboardButton("💎 خرید اشتراک ۳ ماهه ویندوز", callback_data="buy_3M"))
        return markup, "💎 ۳ ماهه ویندوز"

    elif button_type == "support":
        markup.add(types.InlineKeyboardButton("💬 ارتباط با پشتیبانی", callback_data="start_support"))
        return markup, "💬 ارتباط با پشتیبانی"

    elif button_type == "receipt":
        markup.add(types.InlineKeyboardButton("🧾 ارسال رسید پرداخت", callback_data="submit_receipt"))
        return markup, "🧾 ارسال رسید پرداخت"

    elif button_type == "account":
        markup.add(types.InlineKeyboardButton("👤 حساب کاربری من", callback_data="my_account"))
        return markup, "👤 حساب کاربری من"

    return None, "بدون دکمه شیشه‌ای"

def broadcast_button_options_keyboard():
    """Keyboard for admin to choose which inline button to attach to the broadcast."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("🚫 بدون دکمه شیشه‌ای", callback_data="bc_btn_none"),
        types.InlineKeyboardButton("🛒 خرید اشتراک (منوی کلی)", callback_data="bc_btn_plans")
    )
    markup.add(
        types.InlineKeyboardButton("👑 ۱ ساله VIP دوگانه (ویندوز + اندروید)", callback_data="bc_btn_VIP1Y")
    )
    markup.add(
        types.InlineKeyboardButton("👑 ۱ ساله اندروید", callback_data="bc_btn_AN1Y"),
        types.InlineKeyboardButton("👑 ۱ ساله ویندوز", callback_data="bc_btn_1Y")
    )
    markup.add(
        types.InlineKeyboardButton("👑 هر دو پلن ۱ ساله (کنار هم)", callback_data="bc_btn_both_1Y")
    )
    markup.add(
        types.InlineKeyboardButton("📱 منوی اندروید", callback_data="bc_btn_android"),
        types.InlineKeyboardButton("💻 منوی ویندوز", callback_data="bc_btn_windows")
    )
    markup.add(
        types.InlineKeyboardButton("📱 اندروید + 💻 ویندوز (دو دکمه)", callback_data="bc_btn_both")
    )
    markup.add(
        types.InlineKeyboardButton("💎 ۳ ماهه اندروید", callback_data="bc_btn_AN3M"),
        types.InlineKeyboardButton("💎 ۳ ماهه ویندوز", callback_data="bc_btn_3M")
    )
    markup.add(
        types.InlineKeyboardButton("💬 دکمه پشتیبانی", callback_data="bc_btn_support"),
        types.InlineKeyboardButton("🧾 دکمه ارسال رسید", callback_data="bc_btn_receipt")
    )
    markup.add(types.InlineKeyboardButton("❌ انصراف و لغو ارسال", callback_data="cancel_broadcast"))
    return markup

def _start_broadcast_prompt(chat_id: int):
    """Initiates the broadcast workflow prompting the admin for message."""
    set_admin_state({"state": "waiting_broadcast_msg", "time": int(time.time())}, admin_id=chat_id)
    db = load_db()
    target_uids = get_all_broadcast_targets(db)
    total_users = len(target_uids)
    prompt_text = (
        f"📢 *بخش فوروارد و ارسال همگانی به کاربران*\n\n"
        f"👥 مخاطبان هدف: *{total_users} کاربر ثبت‌شده (۱۰۰٪ اعضایی که تا به حال استارت زده‌اند)*\n\n"
        f"لطفاً پیامی که می‌خواهید برای همه ارسال شود را بفرستید.\n\n"
        f"💡 *امکانات:* \n"
        f"• می‌توانید یک پیام یا پست را از کانال (@muntivpn) فوروارد کنید.\n"
        f"• یا هر نوع متن، عکس، فیلم، وویس، موزیک یا فایل را مستقیماً ارسال فرمایید.\n"
        f"• در مرحله بعد نحوه ارسال (فوروارد با نام کانال یا کپی مستقیم) از شما پرسیده می‌شود."
    )
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="cancel_broadcast"))
    safe_send_message(chat_id, prompt_text, reply_markup=markup)

def _run_broadcast_thread(chat_id: int, msg_id: int, is_forward: bool, button_type: str = "none"):
    """Asynchronously broadcasts/forwards message to all users safely with rate limiting."""
    global BROADCAST_ACTIVE, BROADCAST_CANCELLED
    BROADCAST_ACTIVE = True
    BROADCAST_CANCELLED = False

    try:
        _do_run_broadcast(chat_id, msg_id, is_forward, button_type)
    finally:
        BROADCAST_ACTIVE = False

def _do_run_broadcast(chat_id: int, msg_id: int, is_forward: bool, button_type: str = "none"):
    global BROADCAST_CANCELLED
    db = load_db()
    all_uids = get_all_broadcast_targets(db)
    total = len(all_uids)
    if total == 0:
        safe_send_message(chat_id, "⚠️ هیچ کاربری برای ارسال پیام در دیتابیس یافت نشد!")
        return

    reply_markup, btn_title = get_broadcast_reply_markup(button_type)
    action_label = "فوروارد" if is_forward and not reply_markup else "ارسال مستقیم"
    btn_info = f"\n🔘 دکمه پیوست: *{btn_title}*" if reply_markup else ""

    stop_markup = types.InlineKeyboardMarkup()
    stop_markup.add(types.InlineKeyboardButton("🛑 لغو و توقف ارسال", callback_data="abort_active_broadcast"))

    status_msg = safe_send_message(
        chat_id,
        f"🚀 *عملیات {action_label} همگانی آغاز شد...*\n\n"
        f"👥 کل مخاطبان: {total} نفر (تمام کاربران استارت‌زده)"
        f"{btn_info}\n"
        f"⏳ لطفاً صبور باشید، گزارش درصد پیشرفت به صورت زنده نمایش داده می‌شود...",
        reply_markup=stop_markup
    )
    status_msg_id = status_msg.message_id if status_msg else None

    success_count = 0
    blocked_count = 0
    fail_count = 0
    start_time = time.time()
    last_update_time = time.time()
    users_dict = db.get("users", {})

    for idx, target_id in enumerate(all_uids, start=1):
        if BROADCAST_CANCELLED:
            break
        uid_str = str(target_id)
        try:
            if is_forward and not reply_markup:
                bot.forward_message(chat_id=target_id, from_chat_id=chat_id, message_id=msg_id)
            else:
                bot.copy_message(chat_id=target_id, from_chat_id=chat_id, message_id=msg_id, reply_markup=reply_markup)
            success_count += 1
        except telebot.apihelper.ApiTelegramException as e:
            err_msg = str(e).lower()
            if "blocked by the user" in err_msg or "user is deactivated" in err_msg or "chat not found" in err_msg:
                blocked_count += 1
                try:
                    if uid_str in users_dict:
                        users_dict[uid_str]["blocked"] = True
                except Exception:
                    pass
            elif "flood" in err_msg or "too many requests" in err_msg:
                import re
                m = re.search(r'retry after (\d+)', err_msg)
                wait_sec = int(m.group(1)) if m else 5
                time.sleep(wait_sec + 1)
                try:
                    if is_forward and not reply_markup:
                        bot.forward_message(chat_id=target_id, from_chat_id=chat_id, message_id=msg_id)
                    else:
                        bot.copy_message(chat_id=target_id, from_chat_id=chat_id, message_id=msg_id, reply_markup=reply_markup)
                    success_count += 1
                except Exception:
                    fail_count += 1
            else:
                fail_count += 1
        except Exception:
            fail_count += 1

        # Smooth pacing (~20 messages/sec) prevents Telegram flood throttles
        time.sleep(0.05)

        now = time.time()
        if (idx % 25 == 0 or idx == total) and status_msg_id and (now - last_update_time >= 3 or idx == total):
            last_update_time = now
            percent = int((idx / total) * 100)
            progress_bar = "█" * (percent // 10) + "░" * (10 - (percent // 10))
            prog_text = (
                f"📡 *در حال {action_label} همگانی [{percent}%]*\n\n"
                f"`{progress_bar}` {percent}%\n"
                f"📊 پیشرفت: {idx} از {total}\n"
                f"✅ موفق: {success_count}\n"
                f"🚫 بلاک/غیرفعال: {blocked_count}\n"
                f"⚠️ خطا: {fail_count}"
            )
            try:
                bot.edit_message_text(
                    text=prog_text,
                    chat_id=chat_id,
                    message_id=status_msg_id,
                    reply_markup=stop_markup,
                    parse_mode="Markdown"
                )
            except Exception:
                pass

    elapsed = round(time.time() - start_time, 1)
    if BROADCAST_CANCELLED:
        abort_report = (
            f"🛑 *عملیات {action_label} همگانی توسط ادمین متوقف شد*\n\n"
            f"━━━━━━━━━━━━━━━━━━━\n"
            f"👥 کل مخاطبان: *{total} نفر*\n"
            f"📊 پیشرفت تا لحظه توقف: *{idx} از {total}*\n"
            f"✅ موفق: *{success_count} نفر*\n"
            f"🚫 بلاک/غیرفعال: *{blocked_count} نفر*\n"
            f"⚠️ خطا: *{fail_count} نفر*\n"
            f"⏱️ زمان سپری‌شده: *{elapsed} ثانیه*\n"
            f"━━━━━━━━━━━━━━━━━━━"
        )
        safe_send_message(chat_id, abort_report)
        save_db(db, immediate_sync=True)
        return

    final_report = (
        f"🏁 *پایان عملیات {action_label} همگانی*\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👥 کل مخاطبان هدف: *{total} نفر*\n"
        f"✅ ارسال‌های موفق: *{success_count} نفر*\n"
        f"🚫 بلاک یا غیرفعال: *{blocked_count} نفر*\n"
        f"⚠️ خطاهای متفرقه: *{fail_count} نفر*\n"
        f"⏱️ مدت زمان ارسال: *{elapsed} ثانیه*\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )
    safe_send_message(chat_id, final_report)
    save_db(db, immediate_sync=True)

def get_keys_from_disk(plan_code: str) -> list:
    info = PLANS_INFO.get(plan_code)
    if not info:
        return []

    paths_to_check = []
    if "file" in info and info["file"]:
        paths_to_check.append(os.path.join(DATA_DIR, info["file"]))
    if "fallback_file" in info and info["fallback_file"]:
        paths_to_check.append(os.path.join(DATA_DIR, info["fallback_file"]))

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

    token = os.environ.get("GITHUB_TOKEN")
    if token:
        try:
            import urllib.request
            import base64
            req = urllib.request.Request(
                "https://api.github.com/repos/mahdi78013/azad369-cloud/contents/hwid_registry.json",
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

# ---------------------------------------------------------------------------
# Support Working Hours Configuration (Iran Standard Time UTC+3:30)
# Working window: 12:00 PM (ظهر) to 22:00 PM (شب). Closed outside this window.
# ---------------------------------------------------------------------------
def is_support_working_hours() -> tuple[bool, str]:
    """Support is currently offline (sleep mode)."""
    return False, "استراحت شبانه"

SUPPORT_CLOSED_MESSAGE = """💤 *کاربر گرامی، پشتیبانی در حال حاضر در دسترس نیست.*

همکاران ما در بخش پشتیبانی در حال حاضر در دسترس نیستند (ساعات استراحت شبانه).
لطفاً پیام، سوال یا مشکل خود را فردا صبح ارسال فرمایید تا در اسرع وقت پاسخگوی شما باشیم. 🌸

▫️ بخش خرید لایسنس و تحویل آنی اشتراک به صورت کاملاً خودکار و ۲۴ ساعته فعال است.

📢 کانال اطلاع‌رسانی: @muntivpn"""

# ---------------------------------------------------------------------------
# Account & License Inventory Reconciliation
# ---------------------------------------------------------------------------
_RESERVED_KEYS = set()

def reconcile_all_user_purchases(db: dict) -> int:
    """
    Backfills and synchronizes all past purchases from db['orders'] and db['issued']
    into db['users'][uid]['purchases'] so every user's 'My Account' displays
    every single license ever acquired.
    """
    reconciled_count = 0
    db.setdefault("users", {})
    db.setdefault("issued", {})
    db.setdefault("orders", {})

    # 1. Reconcile from issued records
    for key, meta in db["issued"].items():
        uid_str = str(meta.get("user_id"))
        if not uid_str or uid_str == "None":
            continue
        db["users"].setdefault(uid_str, {"purchases": []})
        user_keys = {p.get("key") for p in db["users"][uid_str].get("purchases", []) if p.get("key")}
        if key not in user_keys:
            plan_code = meta.get("plan", "1M")
            info = PLANS_INFO.get(plan_code, {"name": plan_code, "days": 30})
            db["users"][uid_str]["purchases"].append({
                "key": key,
                "plan": plan_code,
                "plan_name": info["name"],
                "issued_at": meta.get("issued_at", int(time.time())),
                "days": info["days"]
            })
            reconciled_count += 1

    # 2. Reconcile from approved orders
    for oid, o in db["orders"].items():
        if o.get("status") == "approved":
            uid_str = str(o.get("user_id"))
            if not uid_str or uid_str == "None":
                continue
            key = o.get("key") or o.get("license") or o.get("code")
            if not key:
                continue
            db["users"].setdefault(uid_str, {"purchases": []})
            user_keys = {p.get("key") for p in db["users"][uid_str].get("purchases", []) if p.get("key")}
            if key not in user_keys:
                plan_code = o.get("plan_code") or o.get("plan", "1M")
                info = PLANS_INFO.get(plan_code, {"name": plan_code, "days": 30})
                db["users"][uid_str]["purchases"].append({
                    "key": key,
                    "plan": plan_code,
                    "plan_name": info["name"],
                    "issued_at": o.get("approved_at") or o.get("created_at", int(time.time())),
                    "days": info["days"]
                })
                reconciled_count += 1

    return reconciled_count

_HISTORICAL_BLACKLIST_CACHE = None

def get_historical_blacklist() -> set:
    """Returns set of all historical keys from blacklist file and legacy disk stores."""
    global _HISTORICAL_BLACKLIST_CACHE
    if _HISTORICAL_BLACKLIST_CACHE is not None:
        return set(_HISTORICAL_BLACKLIST_CACHE)

    b_set = set()
    b_file = os.path.join(BASE_DIR, "historical_blacklist.json")
    if os.path.exists(b_file):
        try:
            with open(b_file, "r", encoding="utf-8") as f:
                b_set.update(json.load(f))
        except Exception:
            pass

    for p_code in PLANS_INFO:
        b_set.update(get_keys_from_disk(p_code))

    _HISTORICAL_BLACKLIST_CACHE = frozenset(b_set)
    return set(_HISTORICAL_BLACKLIST_CACHE)

def get_all_used_keys(db: dict) -> set:
    """
    Returns the comprehensive, all-inclusive set of every license key
    that has ever existed, been issued, bound to HWID, or registered.
    Guarantees absolute ZERO duplicate risk.
    """
    all_used = set()
    # 1. Historical blacklist (4,000+ pre-existing legacy & disk keys)
    all_used.update(get_historical_blacklist())

    # 2. Bound hardware keys (hwid_registry.json)
    all_used.update(get_hwid_bound_keys())

    # 3. All keys issued in current and past database states
    all_used.update(db.get("issued", {}).keys())

    # 4. All keys in orders
    for o in db.get("orders", {}).values():
        k = o.get("key") or o.get("license") or o.get("code")
        if k:
            all_used.add(k)

    # 5. All keys in user purchase histories
    for u in db.get("users", {}).values():
        for p in u.get("purchases", []):
            k = p.get("key")
            if k:
                all_used.add(k)

    # 6. Any key reserved in memory for pending operations
    all_used.update(_RESERVED_KEYS)
    return all_used

def generate_unique_crypto_license(plan_code: str, used_keys: set, hwid: str = None) -> str | None:
    """
    Generates a guaranteed-unique, mathematically authentic cryptographic license.
    Entropy: 32 bits of cryptographic OS entropy (secrets.token_hex) + HMAC-SHA256 signature.
    Guaranteed NEVER to collide with any historical, issued, bound, or reserved key.
    If hwid is provided (8 hex chars), locks license directly to hardware.
    """
    info = PLANS_INFO.get(plan_code)
    if not info:
        return None
    prefix = info.get("prefix") or f"AZ{plan_code}"
    salt = getattr(license_core, "_SECRET_SALT", b"Azad369_Master_Lic_Crypto_Salt_2026_xYz99!")

    for _ in range(2000):
        if hwid and len(hwid.strip()) == 8:
            p1 = hwid.strip().upper()
            serial = secrets.token_hex(2).upper()
            body = f"{prefix}-{p1}-{serial}"
            sig = hmac.new(salt, body.encode("utf-8"), hashlib.sha256).hexdigest()[:6].upper()
            candidate = f"{body}-{sig}"
        else:
            rand_hex = secrets.token_hex(4).upper()
            p1 = rand_hex[:4]
            p2 = rand_hex[4:]
            body = f"{prefix}-{p1}-{p2}"
            sig = hmac.new(salt, body.encode("utf-8"), hashlib.sha256).hexdigest()[:4].upper()
            candidate = f"{body}-{sig}"

        if candidate not in used_keys and candidate not in _RESERVED_KEYS:
            v = license_core.verify_license_format(candidate)
            if v.get("valid") and v.get("days") == info["days"]:
                return candidate
    return None

def issue_keys_for_vip_plan(db: dict, user_id: int) -> tuple[str, str] | None:
    """
    Atomically issues both a 1-year Windows license and a 1-year Android license for VIP combo.
    Guaranteed unique and cryptographically authenticated.
    """
    key_win = issue_key_for_plan_atomic(db, "1Y", user_id)
    if not key_win:
        return None
    key_and = issue_key_for_plan_atomic(db, "AN1Y", user_id)
    if not key_and:
        return None
    return key_win, key_and

def issue_key_for_plan_atomic(db: dict, plan_code: str, user_id: int) -> str | None:
    """
    Issue a guaranteed 100% unique, fresh cryptographic license key atomically.
    Absolute zero chance of duplicate across admin, users, or hardware bindings.
    """
    if plan_code == "VIP1Y":
        res_vip = issue_keys_for_vip_plan(db, user_id)
        if not res_vip:
            return None
        return f"ویندوز: {res_vip[0]} | اندروید: {res_vip[1]}"
    if plan_code not in PLANS_INFO:
        return None
    info = PLANS_INFO[plan_code]

    used_keys = get_all_used_keys(db)

    # Primary: Generate mathematically unique cryptographic license
    u_state = USER_STATES.get(user_id, {}) if isinstance(USER_STATES, dict) else {}
    hwid = u_state.get("hwid")
    chosen_key = generate_unique_crypto_license(plan_code, used_keys, hwid=hwid)

    # Secondary fallback (if crypto generation somehow failed): pick clean disk key
    if not chosen_key:
        all_disk = get_keys_from_disk(plan_code)
        for k in all_disk:
            if k not in used_keys:
                chosen_key = k
                break

    if not chosen_key:
        return None

    _RESERVED_KEYS.add(chosen_key)
    now = int(time.time())
    db.setdefault("issued", {})
    db["issued"][chosen_key] = {
        "plan": plan_code,
        "user_id": user_id,
        "issued_at": now,
        "method": "crypto_unique"
    }
    u_str = str(user_id)
    db.setdefault("users", {})
    if u_str not in db["users"] or not isinstance(db["users"][u_str], dict):
        db["users"][u_str] = {}
    db["users"][u_str].setdefault("purchases", [])
    if not isinstance(db["users"][u_str]["purchases"], list):
        db["users"][u_str]["purchases"] = []
    db["users"][u_str]["purchases"].append({
        "key": chosen_key,
        "plan": plan_code,
        "plan_name": info["name"],
        "issued_at": now,
        "days": info["days"]
    })
    return chosen_key

def get_inventory_stats() -> dict:
    db = load_db()
    all_used = get_all_used_keys(db)
    stats = {}
    tot_sold = len(db.get("issued", {}))
    for p_code, p_info in PLANS_INFO.items():
        all_keys = get_keys_from_disk(p_code)
        sold_plan = sum(1 for k in all_keys if k in all_used)
        clean_on_disk = max(0, len(all_keys) - sold_plan)
        stats[p_code] = {
            "name": p_info["name"],
            "clean_on_disk": clean_on_disk,
            "sold": sold_plan,
            "status": "موجود (تولید یکتای کریپتوگرافیک فعال)"
        }
    tot_clean = sum(st["clean_on_disk"] for st in stats.values() if isinstance(st, dict) and "clean_on_disk" in st)
    stats["_total_available"] = tot_clean
    stats["_total_sold"] = tot_sold
    stats["_generator_status"] = "فعال و بدون محدودیت (ضد تکرار ۱۰۰٪)"
    return stats

# ---------------------------------------------------------------------------
# Tronado Telegram Payment Gateway Engine (Triple-Delivery Fail-Safe)
# ---------------------------------------------------------------------------
def tronado_convert_toman_to_tron(toman_amount: int) -> float | None:
    """Queries Tronado API to convert Toman amount to equivalent TRX amount."""
    try:
        url = f"{TRONADO_BASE_URL}/Toman/ConvertToTronWageSubtracted"
        payload = json.dumps({"Toman": int(toman_amount), "Wallet": TRONADO_WALLET}).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "InternetAzad369Bot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            tron_amt = data.get("TronAmount")
            if tron_amt is not None:
                return float(tron_amt)
    except Exception as e:
        print(f"[Tronado] Error converting Toman to Tron: {e}")

    try:
        url = f"{TRONADO_BASE_URL}/Tron/GetPriceToToman"
        payload = b"{}"
        req = urllib.request.Request(
            url,
            data=payload,
            headers={"Content-Type": "application/json", "User-Agent": "InternetAzad369Bot/1.0"}
        )
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            price = data.get("TronPriceToman")
            if price and price > 0:
                return round(float(toman_amount) / float(price), 6)
    except Exception as e:
        print(f"[Tronado] Error getting Tron price: {e}")
    return None

def tronado_create_order(plan_code: str, user_id: int, user_obj=None) -> dict | None:
    """
    Creates a new payment order via Tronado API v5.
    Returns dict with payment_id, token, full_payment_url, miniapp_url, etc.
    """
    info = PLANS_INFO.get(plan_code)
    if not info:
        return None
    price_toman = info.get("price_toman", 399000)
    tron_amount = tronado_convert_toman_to_tron(price_toman)
    if not tron_amount:
        tron_amount = round(price_toman / 90000.0, 4)

    now_ts = int(time.time())
    rand_token = secrets.token_hex(3)
    payment_id = f"TRND-{plan_code}-{user_id}-{now_ts}-{rand_token}"

    first_name = user_obj.first_name if user_obj and getattr(user_obj, "first_name", None) else "کاربر"
    username = user_obj.username if user_obj and getattr(user_obj, "username", None) else "ندارد"

    url = f"{TRONADO_BASE_URL}/api/v5/GetOrderToken"
    body = {
        "PaymentID": payment_id,
        "WalletAddress": TRONADO_WALLET,
        "TronAmount": float(tron_amount),
        "CallbackUrl": TRONADO_CALLBACK_URL
    }
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "x-api-key": TRONADO_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "InternetAzad369Bot/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            res = json.loads(resp.read().decode("utf-8"))
            data = res.get("Data") if isinstance(res.get("Data"), dict) else res
            token = data.get("Token")
            if not token:
                print(f"[Tronado] GetOrderToken failed: {res}")
                return None
            full_url = data.get("FullPaymentUrl") or f"https://t.me/tronado_robot/customerpayment?startapp={token}"
            miniapp_url = f"https://t.me/tronado_robot/customerpayment?startapp={token}"

            order_data = {
                "order_id": payment_id,
                "token": token,
                "user_id": user_id,
                "first_name": first_name,
                "username": username,
                "plan_code": plan_code,
                "price": info["price"],
                "price_toman": price_toman,
                "tron_amount": float(tron_amount),
                "full_payment_url": full_url,
                "miniapp_url": miniapp_url,
                "status": "pending_tronado",
                "method": "tronado_gateway",
                "created_at": now_ts
            }
            return order_data
    except Exception as e:
        print(f"[Tronado] Error creating order via API: {e}")
        return None

def tronado_check_order_status(payment_id: str) -> dict | None:
    """
    Calls POST /Order/GetStatusByPaymentID to query real-time order status from Tronado.
    """
    url = f"{TRONADO_BASE_URL}/Order/GetStatusByPaymentID"
    body = {"Id": payment_id}
    payload = json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=payload,
        headers={
            "x-api-key": TRONADO_API_KEY,
            "Content-Type": "application/json",
            "User-Agent": "InternetAzad369Bot/1.0"
        }
    )
    try:
        with urllib.request.urlopen(req, timeout=12) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            return data
    except Exception as e:
        print(f"[Tronado] Error checking status for {payment_id}: {e}")
        return None

def fulfill_tronado_order(payment_id: str, ipn_data: dict = None) -> tuple[bool, str]:
    """
    Atomically fulfills an order paid through Tronado:
    - Issues guaranteed-unique crypto license
    - Sends license and instructions to buyer in Telegram
    - Alerts admin
    - Marks order as approved and syncs DB
    """
    with DB_LOCK:
        db = load_db()
        orders = db.setdefault("orders", {})
        order = orders.get(payment_id)
        if not order:
            for oid, od in orders.items():
                if oid == payment_id or od.get("token") == payment_id or od.get("order_id") == payment_id:
                    order = od
                    payment_id = oid
                    break

        if not order and isinstance(ipn_data, dict):
            for k in ("PaymentID", "PaymentId", "payment_id", "Token", "token", "FactorNumber", "Id", "id", "OrderId", "order_id"):
                val = str(ipn_data.get(k, "")).strip()
                if not val:
                    continue
                for oid, od in orders.items():
                    if (
                        oid == val
                        or str(od.get("token", "")).strip() == val
                        or str(od.get("payment_id", "")).strip() == val
                        or str(od.get("order_id", "")).strip() == val
                    ):
                        order = od
                        payment_id = oid
                        break
                if order:
                    break

        if not order:
            return False, "Order not found in database"

        if order.get("status") == "approved":
            return True, f"Already fulfilled: {order.get('key')}"

        buyer_id = order.get("user_id")
        plan_code = order.get("plan_code", "1Y")
        info = PLANS_INFO.get(plan_code, {"name": plan_code, "days": 365})

        if plan_code == "VIP1Y":
            res_vip = issue_keys_for_vip_plan(db, buyer_id)
            if not res_vip:
                return False, "Failed to issue VIP combo license keys"
            key_win, key_and = res_vip
            key = f"ویندوز: {key_win}\nاندروید: {key_and}"
            order["key_win"] = key_win
            order["key_and"] = key_and
        else:
            key = issue_key_for_plan_atomic(db, plan_code, buyer_id)
            if not key:
                return False, "Failed to issue unique license key"

        order["status"] = "approved"
        order["approved_at"] = int(time.time())
        order["approved_by"] = "TRONADO_AUTOMATED"
        order["key"] = key
        if ipn_data:
            order["tronado_ipn"] = {
                "hash": ipn_data.get("Hash"),
                "tron_amount": ipn_data.get("TronAmount"),
                "user_paid_toman": ipn_data.get("UserPaidTomanAmount"),
                "date": ipn_data.get("PaymentDate")
            }
        save_db(db, immediate_sync=True)

    # Deliver license to buyer
    is_android = info.get("platform") == "android" or str(plan_code).startswith("AN")
    if is_android:
        activation_guide = (
            "📌 *نحوه فعال‌سازی در گوشی (اندروید):*\n"
            "۱. اپلیکیشن اندروید را باز کنید.\n"
            "۲. روی کلید *«اتصال»* یا نشان لایسنس بالای صفحه بزنید.\n"
            "۳. کد بالا را در کادر Paste کرده و *فعال‌سازی* را لمس کنید.\n\n"
            "همچنین این لایسنس در بخش *«👤 حساب کاربری من»* ذخیره شد.\n\n"
            "با تشکر از اعتماد شما به *اینترنت آزاد³⁶⁹* 🌸"
        )
    else:
        activation_guide = (
            "📌 *نحوه فعال‌سازی در ویندوز:*\n"
            "این کد را داخل نرم‌افزار ویندوز در بخش *«ثبت لایسنس»* وارد کرده و فعال نمایید.\n"
            "همچنین این لایسنس در بخش *«👤 حساب کاربری من»* ذخیره شد.\n\n"
            "با تشکر از اعتماد شما به *اینترنت آزاد³⁶⁹* 🌸"
        )

    # Deliver license to buyer & alert admins in background thread to prevent gateway timeout
    def _deliver_notifications():
        if plan_code == "VIP1Y":
            k_win = order.get("key_win", "")
            k_and = order.get("key_and", "")
            buyer_msg = (
                "⚡🎉 *پرداخت آنلاین شما با موفقیت تایید شد!*\n\n"
                "👑 *پکیج اشتراک ۱ ساله VIP (ویندوز + اندروید)*\n"
                "⏳ مدت اعتبار: *۳۶۵ روز کامل (هر دو سیستم‌عامل)*\n"
                "💳 روش پرداخت: *درگاه آنلاین شتابی (ترونادو)*\n\n"
                "💻 *کد لایسنس اختصاصی نرم‌افزار ویندوز (کامپیوتر):*\n"
                f"`{k_win}`\n"
                "_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
                "📱 *کد لایسنس اختصاصی اپلیکیشن اندروید (موبایل):*\n"
                f"`{k_and}`\n"
                "_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "📌 *دستورالعمل فعال‌سازی:*\n"
                "۱. **در کامپیوتر:** کد اول را داخل نرم‌افزار ویندوز در بخش «ثبت لایسنس» وارد و فعال نمایید.\n"
                "۲. **در گوشی:** اپلیکیشن اندروید را باز کرده، روی کلید «اتصال» یا نشان لایسنس بالای صفحه زده و کد دوم را Paste و فعال نمایید.\n\n"
                "همچنین هر دو لایسنس در بخش *«👤 حساب کاربری من»* ذخیره شدند.\n\n"
                "با تشکر از اعتماد شما به *اینترنت آزاد³⁶⁹* 🌸"
            )
        else:
            buyer_msg = (
                "⚡🎉 *پرداخت آنلاین شما با موفقیت تایید شد!*\n\n"
                f"کد لایسنس اختصاصی شما صادر گردید:\n"
                f"`{key}`\n\n"
                "_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
                f"🔹 پلن خریداری‌شده: *{escape_md(info['name'])}*\n"
                f"⏳ مدت اعتبار: *{info['days']} روز*\n"
                "💳 روش پرداخت: *درگاه آنلاین شتابی (ترونادو)*\n\n"
                f"{activation_guide}"
            )
        safe_send_message(buyer_id, buyer_msg)

        tx_hash = ipn_data.get("Hash", "—") if ipn_data else "—"
        admin_alert = (
            "⚡ *خرید موفق از درگاه آنلاین ترونادو:*\n\n"
            f"👤 خریدار: `{buyer_id}` (@{escape_md(order.get('username', 'ندارد'))})\n"
            f"📦 پلن: *{escape_md(info['name'])}*\n"
            f"🔑 لایسنس صادرشده:\n`{key}`\n"
            f"🆔 شناسه سفارش: `{payment_id}`\n"
            f"🔗 شناسه تراکنش/TXID: `{tx_hash}`\n"
            "💰 وضعیت: پرداخت قطعی و لایسنس خودکار تحویل شد ✓"
        )
        for aid in ADMIN_IDS:
            safe_send_message(aid, admin_alert)

    threading.Thread(target=_deliver_notifications, daemon=True, name=f"FulfillNotify-{payment_id}").start()
    return True, f"Fulfilled with license {key}"


def check_user_tronado_authenticity(uid: int, plan_code: str = None, caption_text: str = "") -> dict:
    """
    Checks database orders and Tronado API real-time to determine if the user
    actually completed a purchase on Tronado gateway or if this receipt is fake/unpaid.
    """
    try:
        db = load_db()
        orders = db.get("orders", {})

        # 1. Search for Tronado orders matching this uid or referenced in caption
        matching_orders = []
        cap_tokens = []
        if caption_text:
            cap_tokens = re.findall(r"(?:TRND-[A-Za-z0-9\-]+|\b\d{5,10}\b)", str(caption_text))

        for oid, od in orders.items():
            if not isinstance(od, dict):
                continue
            is_match = False
            # Match by user id
            if od.get("user_id") == uid:
                is_match = True
            # Match by token / order id in caption
            for ct in cap_tokens:
                if (
                    oid == ct
                    or str(od.get("token", "")).strip() == ct
                    or str(od.get("payment_id", "")).strip() == ct
                    or ct in str(od.get("tronado_ipn", {}))
                ):
                    is_match = True
                    break

            if is_match and (
                "tronado" in str(od.get("method", ""))
                or "TRND" in str(oid)
                or od.get("status") in ("pending_tronado", "cancelled_tronado", "approved", "fulfilled")
            ):
                matching_orders.append((oid, od))

        # Sort matching orders by created_at descending (most recent first)
        matching_orders.sort(key=lambda x: x[1].get("created_at", 0), reverse=True)

        if not matching_orders:
            return {
                "has_tronado": False,
                "is_fake": None,
                "summary": (
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🛡️ *استعلام اصالت درگاه تورنادو:*\n"
                    "ℹ️ *هیچ فاکتور خریدی در درگاه تورنادو برای این کاربر ثبت نشده است.*\n"
                    "💳 اگر رسید کارت‌به‌کارت بانکی است، تصویر فیش را دستی بررسی فرمایید.\n"
                    "⚠️ اگر ادعای پرداخت ارزی/درگاهی دارد، **رسید ۱۰۰٪ فیک است**."
                )
            }

        target_oid, target_od = matching_orders[0]
        payment_id = target_od.get("payment_id") or target_oid

        # If already fulfilled in our system
        if target_od.get("status") == "approved" and target_od.get("key"):
            return {
                "has_tronado": True,
                "is_fake": False,
                "summary": (
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🛡️ *استعلام اصالت درگاه تورنادو:*\n"
                    "✅ *این سفارش قبلاً در سیستم تایید و لایسنس صادر شده است!*\n"
                    f"🔹 لایسنس: `{target_od.get('key')}`\n"
                    f"🔹 شماره سفارش: `{target_oid}`"
                )
            }

        # Query live Tronado API
        api_data = tronado_check_order_status(payment_id)
        if not api_data or not isinstance(api_data, dict):
            loc_status = target_od.get("status", "نامشخص")
            return {
                "has_tronado": True,
                "is_fake": None,
                "summary": (
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🛡️ *استعلام اصالت درگاه تورنادو:*\n"
                    f"🔸 سابقه سفارش در سیستم یافت شد (`{target_oid}` - وضعیت: {loc_status})\n"
                    "⚠️ استعلام آنلاین از API درگاه با خطا مواجه شد. لطفاً دستی بررسی فرمایید."
                )
            }

        if api_data.get("Error"):
            return {
                "has_tronado": True,
                "is_fake": True,
                "summary": (
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🛡️ *استعلام اصالت درگاه تورنادو:*\n"
                    "⚠️ **رسید نامعتبر یا یافت‌نشده در تورنادو!**\n"
                    f"🔸 شناسه سفارش: `{payment_id}`\n"
                    f"🔸 پاسخ سرور تورنادو: `{api_data.get('Error')}`"
                )
            }

        is_paid = bool(api_data.get("IsPaid"))
        status_id = api_data.get("OrderStatusID")
        status_title = str(api_data.get("OrderStatusTitle") or "نامشخص")
        actual_tron = api_data.get("ActualTronAmount") or api_data.get("TronAmount") or "—"
        pay_date = api_data.get("PaymentDate") or "—"
        ref_hash = api_data.get("Hash") or target_oid

        # Case A: Successful payment
        if is_paid or status_id in (30, "30") or status_title.lower() in ("paymentaccepted", "paid", "completed"):
            return {
                "has_tronado": True,
                "is_fake": False,
                "is_paid": True,
                "summary": (
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🛡️ *استعلام اصالت درگاه تورنادو:*\n"
                    "✅ **خرید واقعی تایید شد (تراکنش در تورنادو پرداخت شده است)**\n"
                    f"🔹 شناسه تراکنش تورنادو: `{ref_hash}`\n"
                    f"🔹 وضعیت درگاه: *پرداخت موفق ({status_title})*\n"
                    f"🔹 مبلغ پرداختی: *{actual_tron} ترون*\n"
                    f"🔹 تاریخ پرداخت: *{pay_date}*\n"
                    "💡 _این سفارش در درگاه پرداخت شده و معتبر است (کال‌بک نرسیده بود)._"
                )
            }

        # Case B: Cancelled or Unpaid (Fake)
        elif status_id in (200, "200") or status_title.lower() in ("cancelled", "canceled", "failed"):
            return {
                "has_tronado": True,
                "is_fake": True,
                "is_paid": False,
                "summary": (
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🛡️ *استعلام اصالت درگاه تورنادو:*\n"
                    "⚠️ **هشدار فیک بودن: پرداخت در درگاه تورنادو لغو شده است!**\n"
                    f"🔸 شماره فاکتور: `{ref_hash}`\n"
                    f"🔸 وضعیت درگاه: *{status_title} (کد {status_id})*\n"
                    "🔸 آیا واریز شده؟: ❌ **خیر (IsPaid: False)**\n"
                    "⛔ _کاربر در تورنادو فاکتور باز کرده ولی وجهی واریز نکرده و سفارش لغو شده است._"
                )
            }
        else:
            return {
                "has_tronado": True,
                "is_fake": True,
                "is_paid": False,
                "summary": (
                    "━━━━━━━━━━━━━━━━━━━\n"
                    "🛡️ *استعلام اصالت درگاه تورنادو:*\n"
                    f"⚠️ **سفارش در انتظار و پرداخت‌نشده ({status_title} - کد {status_id})**\n"
                    f"🔸 شماره پیگیری: `{ref_hash}`\n"
                    "🔸 وضعیت پرداخت: ❌ **پرداخت نشده**\n"
                    "⛔ _تراکنش هنوز تایید نشده یا وجهی واریز نگردیده است._"
                )
            }

    except Exception as e:
        print(f"[check_user_tronado_authenticity] Error: {e}")
        return {
            "has_tronado": False,
            "is_fake": None,
            "summary": "━━━━━━━━━━━━━━━━━━━\n🛡️ *بررسی اصالت تورنادو:* خطا در استعلام خودکار."
        }

def tronado_poller_worker():
    """
    Background worker that runs every 25 seconds.
    Finds pending Tronado orders (<24 hours old), checks status via Tronado API,
    and automatically fulfills and delivers licenses upon confirmation (status 20 or 30).
    """
    print("[Tronado Poller] Started background polling worker.")
    while True:
        try:
            time.sleep(25)
            if not TRONADO_ENABLED:
                continue

            db = load_db()
            orders = db.get("orders", {})
            now_ts = int(time.time())
            pending_ids = []

            for oid, od in orders.items():
                if isinstance(od, dict) and od.get("status") == "pending_tronado":
                    created = od.get("created_at", 0)
                    if now_ts - created < 86400:
                        pending_ids.append(oid)
                    else:
                        # Order older than 24 hours without payment: mark cancelled
                        with DB_LOCK:
                            db_fresh = load_db()
                            cur_o = db_fresh.get("orders", {}).get(oid)
                            if cur_o and cur_o.get("status") == "pending_tronado":
                                cur_o["status"] = "cancelled_tronado"
                                cur_o["cancelled_at"] = now_ts
                                save_db(db_fresh)

            for pid in pending_ids:
                try:
                    st = tronado_check_order_status(pid)
                    if not st:
                        continue

                    status_id = st.get("OrderStatusID")
                    is_paid = (
                        st.get("IsPaid") is True
                        or status_id == 30
                        or str(st.get("OrderStatusTitle", "")).lower() in ("paymentaccepted", "paid", "completed", "success")
                    )

                    if is_paid:
                        print(f"[Tronado Poller] Order {pid} confirmed paid (status={status_id})! Auto-fulfilling...")
                        fulfill_tronado_order(pid, st)
                    elif status_id in (40, 200) or str(st.get("OrderStatusTitle", "")).lower() == "cancelled":
                        with DB_LOCK:
                            db_fresh = load_db()
                            cur_o = db_fresh.get("orders", {}).get(pid)
                            if cur_o and cur_o.get("status") == "pending_tronado":
                                cur_o["status"] = "cancelled_tronado"
                                cur_o["cancelled_at"] = int(time.time())
                                save_db(db_fresh)
                    time.sleep(0.3)
                except Exception as ex:
                    print(f"[Tronado Poller] Error checking {pid}: {ex}")

        except Exception as e:
            print(f"[Tronado Poller] Exception in worker loop: {e}")
            time.sleep(5)

class TronadoWebhookHandler(BaseHTTPRequestHandler):
    def do_POST(self):
        clean_path = self.path.split("?")[0]
        if clean_path not in ("/tronado/callback", "/callback", "/tronado/callback/"):
            self.send_response(404)
            self.end_headers()
            return

        try:
            length = int(self.headers.get("Content-Length", 0))
            raw_body = self.rfile.read(length)
            sig_header = self.headers.get("X-Tronado-Sig", "")

            if TRONADO_IPN_KEY:
                expected_sig = hmac.new(
                    TRONADO_IPN_KEY.encode("utf-8"),
                    raw_body,
                    hashlib.sha512
                ).hexdigest().lower()
                if not hmac.compare_digest(expected_sig, sig_header.strip().lower()):
                    print(f"[Tronado Webhook] Signature mismatch! Got {sig_header}, Expected {expected_sig}")
                    self.send_response(401)
                    self.send_header("Content-Type", "application/json")
                    self.end_headers()
                    self.wfile.write(b'{"error": "Invalid signature"}')
                    return

            payload = {}
            if raw_body:
                try:
                    payload = json.loads(raw_body.decode("utf-8"))
                except Exception:
                    try:
                        import urllib.parse
                        p_form = urllib.parse.parse_qs(raw_body.decode("utf-8", errors="ignore"))
                        payload = {k: v[0] if len(v) == 1 else v for k, v in p_form.items()}
                    except Exception:
                        pass
            print(f"[Tronado Webhook] Received valid callback payload: {payload}")

            # Safe extraction of payment_id / order identifier from all possible fields
            payment_id = (
                payload.get("PaymentID")
                or payload.get("PaymentId")
                or payload.get("payment_id")
                or payload.get("OrderId")
                or payload.get("order_id")
                or payload.get("Id")
                or payload.get("id")
                or payload.get("Token")
                or payload.get("token")
                or payload.get("FactorNumber")
            )

            if not payment_id and "?" in self.path:
                try:
                    import urllib.parse
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    payment_id = (
                        qs.get("PaymentID", [None])[0]
                        or qs.get("payment_id", [None])[0]
                        or qs.get("OrderId", [None])[0]
                        or qs.get("id", [None])[0]
                        or qs.get("Token", [None])[0]
                        or qs.get("token", [None])[0]
                    )
                except Exception:
                    pass

            status_id = payload.get("OrderStatusID")
            is_paid = (
                payload.get("IsPaid") is True
                or status_id in (20, 30)
                or str(payload.get("OrderStatusTitle", "")).lower() in ("paymentaccepted", "paid", "completed", "success")
            )

            if is_paid and payment_id:
                payment_id = str(payment_id).strip()
                print(f"[Tronado Webhook] Fulfilling confirmed order: {payment_id}")
                ok, msg = fulfill_tronado_order(payment_id, payload)
                print(f"[Tronado Webhook] Fulfill result: ok={ok}, msg={msg}")
            elif not is_paid:
                print(f"[Tronado Webhook] Order {payment_id} not marked as paid (status={status_id})")

            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status": "ok"}')

        except Exception as e:
            print(f"[Tronado Webhook] Error handling POST: {e}")
            self.send_response(500)
            self.end_headers()

    def do_GET(self):
        clean_path = self.path.split("?")[0]
        if clean_path in ("/tronado/callback", "/callback", "/tronado/callback/"):
            if "?" in self.path:
                try:
                    import urllib.parse
                    qs = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
                    p_id = (
                        qs.get("PaymentID", [None])[0]
                        or qs.get("payment_id", [None])[0]
                        or qs.get("OrderId", [None])[0]
                        or qs.get("id", [None])[0]
                        or qs.get("Token", [None])[0]
                    )
                    if p_id:
                        p_id = str(p_id).strip()
                        st = tronado_check_order_status(p_id)
                        if st:
                            s_id = st.get("OrderStatusID")
                            if st.get("IsPaid") is True or s_id in (20, 30):
                                fulfill_tronado_order(p_id, st)
                except Exception as e:
                    print(f"[Tronado Webhook GET] Error checking query param order: {e}")

        self.send_response(200)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"InternetAzad369 Tronado Gateway Webhook Active\n")

    def log_message(self, format, *args):
        pass

def start_tronado_webhook_server():
    """Starts the embedded webhook listener in a background daemon thread."""
    port_env = os.environ.get("PORT", "8080")
    try:
        port = int(port_env)
    except ValueError:
        port = 8080

    try:
        server = HTTPServer(("0.0.0.0", port), TronadoWebhookHandler)
        print(f"[Tronado Webhook] HTTP Webhook server listening on port {port} (/tronado/callback)")
        t = threading.Thread(target=server.serve_forever, daemon=True)
        t.start()
    except Exception as e:
        print(f"[Tronado Webhook] Notice: Could not bind HTTP server on port {port} ({e}). Background poller and instant check button will handle all fulfillment.")


# ---------------------------------------------------------------------------
# Keyboards
# ---------------------------------------------------------------------------
def welcome_inline_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📱 خرید اشتراک اندروید (موبایل)", callback_data="show_plans_android"),
        types.InlineKeyboardButton("💻 خرید اشتراک ویندوز (کامپیوتر)", callback_data="show_plans_windows"),
        types.InlineKeyboardButton("🧾 ارسال رسید پرداخت", callback_data="submit_receipt"),
        types.InlineKeyboardButton("👤 حساب کاربری من", callback_data="my_account"),
        types.InlineKeyboardButton("📘 آموزش اتصال دستی", callback_data="manual_guide"),
        types.InlineKeyboardButton("💬 پشتیبانی", callback_data="start_support")
    )
    return markup

def receipt_plan_selection_keyboard():
    """Inline keyboard for selecting the purchased plan before submitting a receipt."""
    markup = types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        types.InlineKeyboardButton("👑 ۱ ساله اندروید (۳۶۵ روزه)", callback_data="rec_plan_AN1Y"),
        types.InlineKeyboardButton("👑 ۱ ساله ویندوز (۳۶۵ روزه)", callback_data="rec_plan_1Y")
    )
    markup.add(
        types.InlineKeyboardButton("💎 ۳ ماهه اندروید (۹۰ روزه)", callback_data="rec_plan_AN3M"),
        types.InlineKeyboardButton("💎 ۳ ماهه ویندوز (۹۰ روزه)", callback_data="rec_plan_3M")
    )
    markup.add(
        types.InlineKeyboardButton("⚡ ۲ ماهه اندروید (۶۰ روزه)", callback_data="rec_plan_AN2M"),
        types.InlineKeyboardButton("⚡ ۲ ماهه ویندوز (۶۰ روزه)", callback_data="rec_plan_2M")
    )
    markup.add(
        types.InlineKeyboardButton("⭐ ۱ ماهه اندروید (۳۰ روزه)", callback_data="rec_plan_AN1M"),
        types.InlineKeyboardButton("⭐ ۱ ماهه ویندوز (۳۰ روزه)", callback_data="rec_plan_1M")
    )
    markup.add(types.InlineKeyboardButton("❌ انصراف و بازگشت", callback_data="cancel_action"))
    return markup

def main_menu_keyboard(admin_flag: bool = False):
    markup = types.ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)
    b_and = types.KeyboardButton("📱 خرید اشتراک اندروید")
    b_win = types.KeyboardButton("💻 خرید اشتراک ویندوز")
    b_acc = types.KeyboardButton("👤 حساب کاربری من")
    b_receipt = types.KeyboardButton("🧾 ارسال رسید پرداخت")
    b_manual = types.KeyboardButton("📘 آموزش اتصال دستی")
    b_help = types.KeyboardButton("❓ راهنمای فعال‌سازی")
    b_sup = types.KeyboardButton("💬 پشتیبانی")
    markup.add(b_and, b_win)
    markup.add(b_acc, b_receipt)
    markup.add(b_manual, b_help)
    markup.add(b_sup)
    if admin_flag:
        b_adm = types.KeyboardButton("👑 پنل مدیریت ادمین")
        markup.add(b_adm)
    return markup

def platform_selection_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        types.InlineKeyboardButton("📱 اپلیکیشن اندروید (موبایل)", callback_data="show_plans_android"),
        types.InlineKeyboardButton("💻 نرم‌افزار ویندوز (کامپیوتر)", callback_data="show_plans_windows"),
        types.InlineKeyboardButton("❌ انصراف و بستن", callback_data="cancel_action")
    )
    return markup

def plans_keyboard_android():
    markup = types.InlineKeyboardMarkup(row_width=1)
    avail = get_plan_availability()
    for p_code in ["AN1M", "AN2M", "AN3M", "AN1Y", "VIP1Y"]:
        if p_code not in PLANS_INFO:
            continue
        p_info = PLANS_INFO[p_code]
        is_avail = avail.get(p_code, False)
        status_suffix = "⚡" if is_avail else "(❌ اتمام موجودی)"
        text = f"{p_info['name']} — {p_info['price']} {status_suffix}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f"buy_{p_code}"))
    markup.add(types.InlineKeyboardButton("🔙 بازگشت به انتخاب سیستم‌عامل", callback_data="show_plans"))
    return markup

def plans_keyboard_windows():
    markup = types.InlineKeyboardMarkup(row_width=1)
    avail = get_plan_availability()
    for p_code in ["1M", "2M", "3M", "1Y", "VIP1Y"]:
        if p_code not in PLANS_INFO:
            continue
        p_info = PLANS_INFO[p_code]
        is_avail = avail.get(p_code, False)
        status_suffix = "⚡" if is_avail else "(❌ اتمام موجودی)"
        text = f"{p_info['name']} — {p_info['price']} {status_suffix}"
        markup.add(types.InlineKeyboardButton(text, callback_data=f"buy_{p_code}"))
    markup.add(types.InlineKeyboardButton("🔙 بازگشت به انتخاب سیستم‌عامل", callback_data="show_plans"))
    return markup

def plans_keyboard():
    return platform_selection_keyboard()

def admin_dashboard_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=2)
    # بخش ویندوز
    b_win_hdr = types.InlineKeyboardButton("💻 ── صدور لایسنس ویندوز (رایگان) ── 💻", callback_data="adm_noop")
    b_w1 = types.InlineKeyboardButton("⭐ ویندوز ۱ ماهه", callback_data="adm_1M")
    b_w2 = types.InlineKeyboardButton("⚡ ویندوز ۲ ماهه", callback_data="adm_2M")
    b_w3 = types.InlineKeyboardButton("💎 ویندوز ۳ ماهه", callback_data="adm_3M")
    b_w4 = types.InlineKeyboardButton("👑 ویندوز ۱ ساله", callback_data="adm_1Y")

    # بخش اندروید
    b_and_hdr = types.InlineKeyboardButton("📱 ── صدور لایسنس اندروید (رایگان) ── 📱", callback_data="adm_noop")
    b_a1 = types.InlineKeyboardButton("⭐ اندروید ۱ ماهه", callback_data="adm_AN1M")
    b_a2 = types.InlineKeyboardButton("⚡ اندروید ۲ ماهه", callback_data="adm_AN2M")
    b_a3 = types.InlineKeyboardButton("💎 اندروید ۳ ماهه", callback_data="adm_AN3M")
    b_a4 = types.InlineKeyboardButton("👑 اندروید ۱ ساله", callback_data="adm_AN1Y")

    b_vip_hdr = types.InlineKeyboardButton("👑 ── صدور پکیج ۱ ساله VIP دوگانه ── 👑", callback_data="adm_noop")
    b_vip = types.InlineKeyboardButton("🌟 صدور ۱ ساله VIP (ویندوز + اندروید)", callback_data="adm_VIP1Y")

    db_cache = load_db()
    unapproved_orders = [o for o in db_cache.get("orders", {}).values() if isinstance(o, dict) and o.get("status") == "pending"]
    unapproved_count = len(unapproved_orders)
    if unapproved_count > 0:
        btn_unappr_label = f"🚨 رسیدهای تایید نشده ({unapproved_count} عدد در صف) 🚨"
    else:
        btn_unappr_label = "📋 رسیدهای تایید نشده (همه بررسی شدند ✅)"
    b_unapproved = types.InlineKeyboardButton(btn_unappr_label, callback_data="adm_unapproved_receipts")

    b_plans = types.InlineKeyboardButton("📦 مدیریت موجودی پلن‌ها", callback_data="adm_plans_mgr")
    b_stat = types.InlineKeyboardButton("📊 موجودی لایسنس‌ها", callback_data="adm_stats")
    b_pend = types.InlineKeyboardButton("⏳ سفارشات در انتظار", callback_data="adm_unapproved_receipts")
    b_live = types.InlineKeyboardButton("📈 آمار آنلاین کاربران", callback_data="adm_live_stats")
    b_bc = types.InlineKeyboardButton("📢 فوروارد و پیام همگانی", callback_data="adm_broadcast")
    b_direct_msg = types.InlineKeyboardButton("✉️ ارسال مستقیم پیام به کاربر", callback_data="adm_send_direct_msg")
    b_cards = types.InlineKeyboardButton("💳 مدیریت و چرخش کارت‌ها", callback_data="adm_cards")

    in_maint, _ = is_maintenance_mode()
    maint_label = "🔴 حالت تعمیر: فعال (ربات بسته است)" if in_maint else "🟢 حالت تعمیر: غیرفعال (ربات باز است)"
    b_maint = types.InlineKeyboardButton(maint_label, callback_data="adm_toggle_maint")

    markup.add(b_win_hdr)
    markup.add(b_w1, b_w2)
    markup.add(b_w3, b_w4)
    markup.add(b_and_hdr)
    markup.add(b_a1, b_a2)
    markup.add(b_a3, b_a4)
    markup.add(b_vip_hdr)
    markup.add(b_vip)
    markup.add(b_unapproved)
    markup.add(b_plans)
    markup.add(b_stat, b_pend)
    markup.add(b_live, b_bc)
    markup.add(b_direct_msg)
    markup.add(b_cards)
    markup.add(b_maint)
    return markup

def admin_plans_management_keyboard():
    markup = types.InlineKeyboardMarkup(row_width=1)
    avail = get_plan_availability()
    for p_code, p_info in PLANS_INFO.items():
        is_avail = avail.get(p_code, False)
        status_badge = "🟢 موجود (باز)" if is_avail else "🔴 ناموجود (بسته)"
        action_text = "❌ تغییر به ناموجود" if is_avail else "✅ تغییر به موجود"
        btn_text = f"{p_info['name']}: {status_badge}  ⟵  {action_text}"
        markup.add(types.InlineKeyboardButton(btn_text, callback_data=f"adm_toggle_plan_{p_code}"))
    markup.add(types.InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel"))
    return markup

# ---------------------------------------------------------------------------
# Maintenance Mode (حالت تعمیر و ارتقا)
# ---------------------------------------------------------------------------
def is_maintenance_mode() -> tuple[bool, str]:
    """
    Returns (is_active, maintenance_message).
    Checks DB. Default is completely OFF (bot is active and open for all users).
    """
    default_msg = (
        "🛠 *ربات اینترنت آزاد³⁶۹ موقتاً در دست تعمیر و ارتقا می‌باشد.*\n\n"
        "کاربر گرامی؛ تیم فنی در حال ارتقا و بهینه‌سازی زیرساخت سرورهاست.\n\n"
        "⏳ *زمان بازگشایی و فعالیت مجدد:* به زودی\n\n"
        "از شکیبایی، همراهی و اعتماد شما صمیمانه سپاسگزاریم 🌸"
    )
    db = load_db()
    m_info = db.get("maintenance")
    if not m_info or not isinstance(m_info, dict):
        return False, ""

    if not m_info.get("enabled", False):
        return False, ""

    until_ts = m_info.get("until_ts", 0)
    now = int(time.time())
    if until_ts > 0 and now >= until_ts:
        m_info["enabled"] = False
        save_db(db)
        return False, ""

    return True, m_info.get("message") or default_msg

@bot.message_handler(func=lambda m: is_maintenance_mode()[0] and not is_admin(m.from_user.id), content_types=["text", "audio", "document", "photo", "sticker", "video", "video_note", "voice", "location", "contact"])
def handle_maintenance_message(message):
    track_user(message.from_user)
    _, msg = is_maintenance_mode()
    safe_reply_to(message, msg)

@bot.message_handler(commands=["maint", "maintenance"])
def cmd_maint(message):
    uid = message.from_user.id
    if not is_admin(uid):
        return
    db = load_db()
    in_maint, _ = is_maintenance_mode()
    new_state = not in_maint
    db["maintenance"] = {
        "enabled": new_state,
        "until_ts": 0,
        "updated_by": uid,
        "updated_at": int(time.time())
    }
    save_db(db, immediate_sync=True)
    status_str = "🔴 فعال شد (ربات برای کاربران بسته شد)" if new_state else "🟢 غیرفعال شد (ربات برای همه کاربران باز و فعال است)"
    safe_reply_to(message, f"وضعیت حالت تعمیر: {status_str}")
# ---------------------------------------------------------------------------
# Start & Navigation Handlers
# ---------------------------------------------------------------------------
@bot.message_handler(commands=["start", "menu"])
def cmd_start(message):
    track_user(message.from_user)
    uid = message.from_user.id
    admin_flag = is_admin(uid)
    name = message.from_user.first_name or "کاربر گرامی"
    clear_user_state(uid)

    in_maint, maint_msg = is_maintenance_mode()
    if in_maint:
        if not admin_flag:
            safe_send_message(message.chat.id, maint_msg)
            return
        else:
            admin_maint_text = (
                "🛠 *ربات هم‌اکنون در حالت تعمیر (خاموش) قرار دارد.*\n\n"
                "🔒 *وضعیت برای کاربران عادی:* کاملاً مسدود تا ساعت **۲۱:۰۰ (۹ شب)**\n"
                "تمامی پیام‌ها، دستورات و کلیک‌های کاربران با پاسخ خودکار «در دست تعمیر» مسدود شده است.\n\n"
                "👑 *شما به عنوان مدیر وارد شده‌اید.*\n"
                "جهت مدیریت یا تغییر وضعیت از دکمه‌های زیر استفاده کنید:"
            )
            admin_markup = types.InlineKeyboardMarkup(row_width=1)
            admin_markup.add(
                types.InlineKeyboardButton("👑 ورود به پنل مدیریت ادمین", callback_data="adm_back_panel"),
                types.InlineKeyboardButton("🟢 لغو حالت تعمیر و بازگشایی ربات", callback_data="adm_toggle_maint")
            )
            safe_send_message(message.chat.id, admin_maint_text, reply_markup=admin_markup)
            safe_send_message(message.chat.id, "منوی مدیریت برای شما فعال است 👇", reply_markup=main_menu_keyboard(admin_flag=True))
            return

    args = message.text.split()
    if len(args) > 1:
        param = args[1].strip()
        if param.lower() == "manual_guide":
            send_manual_connection_guide(message.chat.id)
            return
        elif param.lower().startswith("dev_"):
            hwid = param[4:].upper()
            u_state = USER_STATES.setdefault(uid, {})
            u_state["hwid"] = hwid
            dev_welcome = (
                f"سلام *{escape_md(name)}* عزیز! 📱\n\n"
                f"شناسه سخت‌افزاری گوشی شما شناسایی شد: `{hwid}`\n\n"
                f"جهت فعال‌سازی اپلیکیشن روی این تلفن همراه، یکی از پلن‌های اشتراک زیر را انتخاب فرمایید:\n"
                f"_(پرداخت آنلاین از طریق درگاه امن ترونادو انجام و لایسنس آنی صادر می‌شود)_"
            )
            safe_send_message(message.chat.id, dev_welcome, reply_markup=plans_keyboard_android())
            safe_send_message(message.chat.id, "منوی اصلی کیبورد نیز فعال شد 👇", reply_markup=main_menu_keyboard(admin_flag))
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
    safe_send_message(message.chat.id, "منوی اصلی کیبورد نیز فعال شد 👇", reply_markup=main_menu_keyboard(admin_flag))

MAIN_MENU_EXACT_BUTTONS = {
    "🛒 خرید اشتراک اختصاصی",
    "🛒 خرید اشتراک",
    "📱 خرید اشتراک اندروید",
    "💻 خرید اشتراک ویندوز",
    "خرید اشتراک اندروید",
    "خرید اشتراک ویندوز",
    "🧾 ارسال رسید پرداخت",
    "ارسال رسید پرداخت",
    "ارسال رسید",
    "ثبت رسید",
    "رسید",
    "/receipt",
    "/send_receipt",
    "👤 حساب کاربری من",
    "📘 آموزش اتصال دستی",
    "❓ راهنمای فعال‌سازی",
    "💬 پشتیبانی",
    "👑 پنل مدیریت ادمین",
    "❌ انصراف",
    "انصراف",
    "/cancel",
    "/start",
    "/help",
    "/support",
    "/plans",
    "/buy",
    "/account",
    "/admin"
}

def is_menu_button_command(m, exact_commands: list) -> bool:
    """
    Checks if a message is an explicit button click or short command for a menu option.
    Guarantees that:
    1. Replies (message.reply_to_message) are NEVER hijacked as menu clicks.
    2. Admin broadcast messages or ticket replies are NEVER hijacked as menu clicks.
    3. User support tickets or receipt notes are NEVER hijacked as menu clicks.
    """
    if not m.text or m.reply_to_message:
        return False

    clean = m.text.strip()
    uid = m.from_user.id

    # If sender is admin and has an active conversation state (broadcasting or replying)
    if is_admin(uid):
        adm_state = get_admin_state(uid)
        st = adm_state.get("state")
        if st in ("waiting_broadcast_msg", "replying_to_user"):
            # Only exact cancel commands break out of this state via button
            return clean in ["❌ انصراف", "انصراف", "/cancel"]

    # If sender is a regular user in active support composition or receipt submission
    u_state = get_user_state(uid)
    u_st = u_state.get("state")
    if u_st in ("waiting_support_msg", "awaiting_receipt"):
        # If user explicitly taps an exact main menu button or cancel, allow navigation
        if clean in MAIN_MENU_EXACT_BUTTONS:
            return clean in exact_commands
        return False

    # In normal idle state, only exact matches trigger menu handlers
    return clean in exact_commands

@bot.message_handler(func=lambda m: is_menu_button_command(m, ["📱 خرید اشتراک اندروید", "خرید اشتراک اندروید", "اشتراک اندروید", "/android"]))
def btn_buy_android(message):
    clear_user_state(message.from_user.id)
    in_maint, maint_msg = is_maintenance_mode()
    if in_maint and not is_admin(message.from_user.id):
        safe_reply_to(message, maint_msg)
        return
    text = (
        "📱 *پلن‌های اشتراک اپلیکیشن اندروید اینترنت آزاد³⁶⁹*\n\n"
        "لطفاً مدت زمان مورد نظر خود را انتخاب کنید:\n"
        "_(این لایسنس مخصوص اپلیکیشن اندروید است و روی تلفن همراه فعال می‌شود)_"
    )
    safe_send_message(message.chat.id, text, reply_markup=plans_keyboard_android())

@bot.message_handler(func=lambda m: is_menu_button_command(m, ["💻 خرید اشتراک ویندوز", "خرید اشتراک ویندوز", "اشتراک ویندوز", "/windows"]))
def btn_buy_windows(message):
    clear_user_state(message.from_user.id)
    in_maint, maint_msg = is_maintenance_mode()
    if in_maint and not is_admin(message.from_user.id):
        safe_reply_to(message, maint_msg)
        return
    text = (
        "💻 *پلن‌های اشتراک نرم‌افزار ویندوز اینترنت آزاد³⁶⁹*\n\n"
        "لطفاً مدت زمان مورد نظر خود را انتخاب کنید:\n"
        "_(این لایسنس مخصوص نرم‌افزار ویندوز است و روی کامپیوتر یا لپ‌تاپ فعال می‌شود)_"
    )
    safe_send_message(message.chat.id, text, reply_markup=plans_keyboard_windows())

@bot.message_handler(func=lambda m: is_menu_button_command(m, ["🛒 خرید اشتراک اختصاصی", "🛒 خرید اشتراک", "خرید اشتراک", "خرید", "پلن‌ها", "پلن ها", "/buy", "/plans"]))
def btn_buy_plans(message):
    clear_user_state(message.from_user.id)
    in_maint, maint_msg = is_maintenance_mode()
    if in_maint:
        if not is_admin(message.from_user.id):
            safe_reply_to(message, maint_msg)
        else:
            safe_reply_to(
                message,
                "🛠 *ربات در حالت تعمیر (خاموش) است.*\n\n"
                "فروش و ثبت سفارش تا ساعت ۲۱:۰۰ برای همه کاربران غیرفعال است.\n"
                "جهت صدور لایسنس دستی یا مدیریت از «👑 پنل مدیریت ادمین» استفاده کنید."
            )
        return
    text = (
        "💎 *لطفاً سیستم‌عامل مورد نظر خود را جهت خرید اشتراک انتخاب فرمایید:*\n\n"
        "_(لایسنس صادرشده دقیقاً مختص همان سیستم‌عامل فعال خواهد شد)_"
    )
    safe_send_message(message.chat.id, text, reply_markup=platform_selection_keyboard())

@bot.message_handler(commands=["account", "my_account", "profile"])
@bot.message_handler(func=lambda m: is_menu_button_command(m, ["👤 حساب کاربری من", "حساب کاربری من", "حساب کاربری", "اکانت من", "پروفایل"]))
def btn_my_account(message, target_uid=None):
    uid = target_uid or message.from_user.id
    clear_user_state(uid)
    db = load_db()
    u_str = str(uid)
    db.setdefault("users", {})
    if u_str not in db["users"] or not isinstance(db["users"][u_str], dict):
        db["users"][u_str] = {}
    u_data = db["users"][u_str]
    u_data.setdefault("purchases", [])
    if not isinstance(u_data["purchases"], list):
        u_data["purchases"] = []
    purchases = u_data["purchases"]

    # Self-healing reconciliation: ensure any issued key or approved order for this user is recorded
    existing_keys = {p.get("key") for p in purchases if isinstance(p, dict) and p.get("key")}
    updated = False
    for k, meta in db.get("issued", {}).items():
        if str(meta.get("user_id")) == u_str and k not in existing_keys:
            plan_code = meta.get("plan", "1M")
            info = PLANS_INFO.get(plan_code, {"name": plan_code, "days": 30})
            purchases.append({
                "key": k,
                "plan": plan_code,
                "plan_name": info["name"],
                "issued_at": meta.get("issued_at", int(time.time())),
                "days": info["days"]
            })
            existing_keys.add(k)
            updated = True
    for o in db.get("orders", {}).values():
        if str(o.get("user_id")) == u_str and o.get("status") == "approved":
            k = o.get("key") or o.get("license") or o.get("code")
            if k and k not in existing_keys:
                plan_code = o.get("plan_code") or o.get("plan", "1M")
                info = PLANS_INFO.get(plan_code, {"name": plan_code, "days": 30})
                purchases.append({
                    "key": k,
                    "plan": plan_code,
                    "plan_name": info["name"],
                    "issued_at": o.get("approved_at") or o.get("created_at", int(time.time())),
                    "days": info["days"]
                })
                existing_keys.add(k)
                updated = True
    if updated:
        save_db(db)

    # Sort purchases descending by issuance date (newest first)
    purchases.sort(key=lambda p: p.get("issued_at", 0) if isinstance(p, dict) else 0, reverse=True)

    now = int(time.time())
    lines = [
        f"👤 *حساب کاربری شما*\n",
        f"🆔 شناسه کاربری: `{uid}`"
    ]

    max_display = 8
    displayed = purchases[:max_display]
    has_more = len(purchases) > max_display

    if purchases:
        if has_more:
            lines.append(f"\n📦 تعداد کل خریدهای شما: *{len(purchases)} عدد* _({max_display} خرید اخیر در زیر نمایش داده شده است)_\n")
        else:
            lines.append(f"\n📦 تعداد کل خریدهای شما: *{len(purchases)} عدد*\n")

        lines.append("📋 *پلن‌ها و لایسنس‌های اختصاصی شما:*")
        for idx, p in enumerate(displayed, 1):
            issued_at = p.get("issued_at", now)
            total_days = p.get("days", 30)
            elapsed_days = (now - issued_at) // 86400
            rem_days = max(0, total_days - elapsed_days)
            date_str = time.strftime("%Y/%m/%d %H:%M", time.localtime(issued_at))
            status_badge = "🟢 فعال" if rem_days > 0 else "🔴 منقضی شده"

            lines.append(
                f"{idx}. پلن: *{escape_md(p.get('plan_name', 'اشتراک اختصاصی'))}*\n"
                f"   🔑 لایسنس: `{p.get('key', '')}`\n"
                f"   ⏳ زمان باقی‌مانده: *{rem_days} روز* (از {total_days} روز)\n"
                f"   📅 تاریخ خرید: {date_str}\n"
                f"   وضعیت: {status_badge}\n"
            )
    else:
        lines.append("\n📦 وضعیت: *شما هنوز لایسنسی خریداری نکرده‌اید.*")

    lines.append("\n_(جهت کپی روی کد لایسنس خود ضربه بزنید)_")
    markup = types.InlineKeyboardMarkup(row_width=1)
    if has_more:
        markup.add(types.InlineKeyboardButton(f"📜 مشاهده تمام {len(purchases)} لایسنس (آرشیو کامل)", callback_data="show_all_purchases"))
    markup.add(
        types.InlineKeyboardButton("🛒 خرید اشتراک اختصاصی", callback_data="show_plans"),
        types.InlineKeyboardButton("💬 پشتیبانی", callback_data="start_support")
    )
    safe_send_message(message.chat.id, "\n".join(lines), reply_markup=markup)

@bot.message_handler(commands=["receipt", "send_receipt"])
@bot.message_handler(func=lambda m: is_menu_button_command(m, [
    "🧾 ارسال رسید پرداخت",
    "ارسال رسید پرداخت",
    "ارسال رسید",
    "ثبت رسید",
    "رسید",
    "/receipt",
    "/send_receipt"
]))
def btn_send_receipt(message):
    clear_user_state(message.from_user.id)
    text = (
        "🧾 *ثبت و ارسال رسید پرداخت*\n\n"
        "کاربر گرامی؛ چنانچه هزینه اشتراک را پرداخت نموده‌اید (کارت‌به‌کارت یا درگاه) ولی لایسنس خود را دریافت نکرده‌اید، "
        "لطفاً ابتدا **پلن خریداری‌شده‌ی خود** را از گزینه‌های زیر انتخاب فرمایید:\n\n"
        "👇 _روی پلن مربوطه کلیک کنید:_"
    )
    safe_send_message(message.chat.id, text, reply_markup=receipt_plan_selection_keyboard())

@bot.message_handler(commands=["help"])
@bot.message_handler(func=lambda m: is_menu_button_command(m, ["❓ راهنمای فعال‌سازی", "راهنمای فعال‌سازی", "راهنما", "فعال‌سازی", "فعالسازی"]))
def btn_help(message):
    clear_user_state(message.from_user.id)
    text = (
        "📖 *راهنمای جامع فعال‌سازی اینترنت آزاد³⁶⁹*\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "📱 *راهنمای فعال‌سازی در تلفن همراه (اندروید):*\n"
        "۱. ابتدا اپلیکیشن **اینترنت آزاد³⁶⁹** را در گوشی خود باز کنید.\n"
        "۲. روی کلید **اتصال** (یا آیکون کلید بالای صفحه) ضربه بزنید.\n"
        "۳. کد لایسنس دریافتی (با پیشوند `AN`) را در کادر وارد نموده و گزینه **«بررسی و فعال‌سازی»** را بزنید.\n"
        "✓ اشتراک شما بلافاصله فعال شده و برنامه متصل خواهد شد.\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "💻 *راهنمای فعال‌سازی در کامپیوتر (ویندوز):*\n"
        "۱. ابتدا نرم‌افزار **اینترنت آزاد³⁶⁹** را در کامپیوتر اجرا کنید.\n"
        "۲. در بالای صفحه روی دکمه **🔑 ثبت لایسنس** کلیک فرمایید.\n"
        "۳. کد لایسنسی که از ربات دریافت کرده‌اید (با پیشوند `AZ`) را در کادر قرار دهید.\n"
        "۴. دکمه **«بررسی و فعال‌سازی»** را بزنید.\n"
        "✓ لایسنس شما تایید شده و دکمه اتصال سبز می‌شود.\n\n"
        "💬 در صورت نیاز به راهنمایی بیشتر، از دکمه «💬 پشتیبانی» استفاده فرمایید."
    )
    safe_send_message(message.chat.id, text)

@bot.message_handler(commands=["guide", "manual"])
@bot.message_handler(func=lambda m: is_menu_button_command(m, ["📘 آموزش اتصال دستی", "آموزش اتصال دستی", "اتصال دستی"]))
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
@bot.message_handler(commands=["support"])
@bot.message_handler(func=lambda m: is_menu_button_command(m, ["💬 پشتیبانی", "پشتیبانی", "ارتباط با ادمین"]))
def btn_support(message, target_uid=None, *args, **kwargs):
    safe_send_message(message.chat.id, SUPPORT_CLOSED_MESSAGE)
    return


def btn_admin_panel(message):
    if not is_admin(message.from_user.id):
        return
    clear_admin_state(message.from_user.id)
    track_user(message.from_user)
    stats = get_inventory_stats()
    db = load_db()
    total_users = len(db.get("users", {}))
    pending_receipts_cnt = sum(1 for o in db.get("orders", {}).values() if isinstance(o, dict) and o.get("status") == "pending")
    pend_alert = f"\n⚠️ *رسیدهای تایید نشده در انتظار بررسی:* *{pending_receipts_cnt} عدد*\n" if pending_receipts_cnt > 0 else ""
    text = (
        f"👑 *پنل مدیریت ادمین*\n\n"
        f"👥 تعداد کل کاربران ثبت‌شده: *{total_users} نفر*\n"
        f"🏷️ موجودی کل کدهای آماده: *{stats['_total_available']} عدد*\n"
        f"📦 مجموع فروش کل: *{stats['_total_sold']} عدد*\n"
        f"{pend_alert}\n"
        f"جهت صدور لایسنس، ارسال پیام همگانی، مدیریت کارت‌ها یا مشاهده آمار آنلاین انتخاب فرمایید:"
    )
    safe_send_message(message.chat.id, text, reply_markup=admin_dashboard_keyboard())

@bot.message_handler(commands=["stats", "users"])
def cmd_stats(message):
    if not is_admin(message.from_user.id):
        return
    track_user(message.from_user)
    markup = types.InlineKeyboardMarkup()
    markup.add(types.InlineKeyboardButton("🔄 بروزرسانی آمار", callback_data="adm_live_stats"))
    safe_send_message(message.chat.id, get_live_bot_stats(), reply_markup=markup)

@bot.message_handler(commands=["stop_broadcast", "cancel_broadcast", "abort_broadcast"])
def cmd_stop_broadcast(message):
    if not is_admin(message.from_user.id):
        return
    global BROADCAST_CANCELLED
    if not BROADCAST_ACTIVE:
        safe_reply_to(message, "ℹ️ در حال حاضر هیچ عملیات پیام یا فوروارد همگانی در حال اجرا نیست.")
        return
    BROADCAST_CANCELLED = True
    safe_reply_to(message, "🛑 دستور توقف فوروارد/ارسال همگانی با موفقیت صادر شد.")

@bot.message_handler(commands=["broadcast", "fwd", "sendall"])
def cmd_broadcast(message):
    if not is_admin(message.from_user.id):
        return
    track_user(message.from_user)
    _start_broadcast_prompt(message.chat.id)


def resolve_user_id(target_raw: str, db: dict = None) -> int | None:
    """
    Resolves a numeric user ID from either a direct numeric string,
    or a username (e.g. '@khan007khan' or 'khan007khan').
    """
    if not target_raw:
        return None
    raw = str(target_raw).strip()
    if raw.isdigit():
        return int(raw)

    clean_name = raw.lstrip("@").lower().strip()
    if not clean_name:
        return None

    if db is None:
        db = load_db()

    # Search in users
    for uid_str, u_obj in db.get("users", {}).items():
        if isinstance(u_obj, dict):
            un = str(u_obj.get("username", "")).lstrip("@").lower().strip()
            if un == clean_name and uid_str.isdigit():
                return int(uid_str)

    # Search in orders
    for o_obj in db.get("orders", {}).values():
        if isinstance(o_obj, dict):
            un = str(o_obj.get("username", "")).lstrip("@").lower().strip()
            uid = o_obj.get("user_id")
            if un == clean_name and uid:
                try:
                    return int(uid)
                except Exception:
                    pass
    return None

def deliver_admin_message_to_user(admin_id: int, target_uid: int, text_or_msg, orig_msg=None) -> bool:
    """
    Delivers an official admin message to a user (text or media).
    Records the interaction in user history and notifies admin of the result.
    """
    db = load_db()
    users = db.get("users", {})
    u_obj = users.get(str(target_uid), {})
    f_name = u_obj.get("first_name", "کاربر")

    header = "📩 *پیام مدیریت و پشتیبانی اینترنت آزاد³⁶⁹:*\n\n"
    footer = "\n\n━━━━━━━━━━━━━━━━━━━\nدر صورت نیاز به ارسال پاسخ، از دکمه «💬 پشتیبانی» استفاده فرمایید."

    send_success = False
    delivered_text = ""
    try:
        if isinstance(text_or_msg, str):
            delivered_text = text_or_msg
            full_text = f"{header}{text_or_msg}{footer}"
            send_success = safe_send_message(target_uid, full_text)
        elif hasattr(text_or_msg, "content_type"):
            m = text_or_msg
            cap = m.caption or ""
            delivered_text = cap or f"[{m.content_type}]"
            full_cap = f"{header}{cap}{footer}" if cap else f"{header}{footer}"
            if m.content_type == "photo":
                bot.send_photo(target_uid, m.photo[-1].file_id, caption=full_cap, parse_mode="Markdown")
            elif m.content_type == "document":
                bot.send_document(target_uid, m.document.file_id, caption=full_cap, parse_mode="Markdown")
            elif m.content_type == "voice":
                bot.send_voice(target_uid, m.voice.file_id, caption=full_cap, parse_mode="Markdown")
            elif m.content_type == "video":
                bot.send_video(target_uid, m.video.file_id, caption=full_cap, parse_mode="Markdown")
            else:
                bot.copy_message(target_uid, m.chat.id, m.message_id)
            send_success = True
    except Exception as ex:
        print(f"[deliver_admin_message_to_user] Error: {ex}")
        send_success = False

    # Record in db
    if send_success:
        t_str = str(target_uid)
        db.setdefault("users", {})
        if t_str not in db["users"] or not isinstance(db["users"][t_str], dict):
            db["users"][t_str] = {"purchases": []}
        db["users"][t_str]["last_admin_reply"] = {
            "text": delivered_text,
            "time": int(time.time()),
            "by_admin": admin_id
        }
        save_db(db)
        if orig_msg:
            safe_reply_to(orig_msg, f"✅ پیام شما با موفقیت برای کاربر *{escape_md(f_name)}* (`{target_uid}`) ارسال گردید.")
    else:
        if orig_msg:
            safe_reply_to(orig_msg, f"⚠️ ارسال پیام به کاربر `{target_uid}` ناموفق بود (ممکن است ربات توسط کاربر متوقف یا بلاک شده باشد).")

    return send_success

@bot.message_handler(commands=["send", "msg", "pm", "message", "reply"])
def cmd_admin_direct_message(message):
    uid = message.from_user.id
    if not is_admin(uid):
        return
    track_user(message.from_user)

    parts = message.text.strip().split(maxsplit=2)
    # /send -> prompt for target
    if len(parts) == 1:
        set_admin_state({"state": "waiting_target_user_for_msg"}, admin_id=uid)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_admin_reply"))
        safe_reply_to(
            message,
            "✉️ *ارسال مستقیم پیام به کاربر*\n\n"
            "لطفاً **آیدی عددی** یا **یوزرنیم کاربر** را ارسال فرمایید:\n"
            "(مثال: `161957867` یا `@khan007khan`)\n\n"
            "یا می‌توانید دستور را مستقیم ارسال کنید:\n"
            "`/send 161957867 متن پیام شما`",
            reply_markup=markup
        )
        return

    target_raw = parts[1].strip()
    target_uid = resolve_user_id(target_raw)
    if not target_uid:
        safe_reply_to(message, f"❌ کاربر با مشخصه `{target_raw}` در سیستم یافت نشد. لطفاً آیدی عددی کاربر را مستقیماً وارد فرمایید.")
        return

    if len(parts) >= 3:
        msg_body = parts[2].strip()
        deliver_admin_message_to_user(uid, target_uid, msg_body, message)
    else:
        set_admin_state({"state": "replying_to_user", "target_uid": target_uid}, admin_id=uid)
        db_cur = load_db()
        u_info = db_cur.get("users", {}).get(str(target_uid), {})
        f_n = u_info.get("first_name", "کاربر")
        u_n = u_info.get("username", "ندارد")
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_admin_reply"))
        safe_reply_to(
            message,
            f"👤 *کاربر انتخاب‌شده:*\n"
            f"• نام: *{escape_md(f_n)}*\n"
            f"• یوزرنیم: @{escape_md(u_n)}\n"
            f"• آیدی عددی: `{target_uid}`\n\n"
            f"✍️ لطفاً هم‌اکنون پیام، تصویر یا فایل مورد نظر خود را ارسال فرمایید تا بلافاصله به کاربر تحویل داده شود:",
            reply_markup=markup
        )

@bot.message_handler(commands=["fulfill", "checkorder", "order"])
def cmd_admin_fulfill(message):
    if not is_admin(message.from_user.id):
        return
    track_user(message.from_user)
    parts = message.text.strip().split()
    if len(parts) < 2:
        safe_send_message(
            message.chat.id,
            "📌 *راهنمای استعلام و صدور دستی لایسنس:*\n\n"
            "`/fulfill <شناسه سفارش یا آیدی کاربر>`\n\n"
            "مثال‌ها:\n"
            "`/fulfill 6027874814`\n"
            "`/fulfill 2903747`\n"
            "`/fulfill TRND-3M-6027874814-1792219886-aab977`"
        )
        return

    query = parts[1].strip()
    safe_send_message(message.chat.id, f"⏳ در حال جستجو و استعلام سفارش `{query}`...")

    db = load_db()
    orders = db.get("orders", {})
    target_oid = None
    target_order = None

    for oid, od in orders.items():
        if not isinstance(od, dict):
            continue
        if (oid == query or
            str(od.get("user_id")) == query or
            od.get("token") == query or
            query in str(od.get("tronado_ipn", {})) or
            query in oid):
            target_oid = oid
            target_order = od
            if od.get("status") == "pending_tronado":
                break

    if not target_order:
        safe_send_message(message.chat.id, f"❌ سفارشی مرتبط با `{query}` در دیتابیس یافت نشد.")
        return

    if target_order.get("status") == "approved":
        safe_send_message(
            message.chat.id,
            f"✅ این سفارش قبلاً تایید و لایسنس صادر شده است:\n\n"
            f"👤 خریدار: `{target_order.get('user_id')}` (@{escape_md(target_order.get('username', 'ندارد'))})\n"
            f"📦 پلن: *{target_order.get('plan_code')}*\n"
            f"🔑 لایسنس: `{target_order.get('key')}`\n"
            f"🆔 شناسه: `{target_oid}`"
        )
        return

    st = tronado_check_order_status(target_oid)
    status_id = st.get("OrderStatusID") if isinstance(st, dict) else None
    is_paid = (
        st.get("IsPaid") is True
        or status_id == 30
        or str(st.get("OrderStatusTitle", "")).lower() in ("paymentaccepted", "paid", "completed", "success")
    ) if isinstance(st, dict) else False

    if is_paid:
        ok, msg = fulfill_tronado_order(target_oid, st)
        if ok:
            safe_send_message(message.chat.id, f"✅ سفارش `{target_oid}` تایید شد و لایسنس به کاربر ارسال گردید!\n\nجزئیات: {msg}")
        else:
            safe_send_message(message.chat.id, f"⚠️ تایید سفارش با خطا مواجه شد: {msg}")
    else:
        title = st.get("OrderStatusTitle", "نامشخص") if isinstance(st, dict) else "نامشخص"
        safe_send_message(
            message.chat.id,
            f"⚠️ وضعیت درگاه: پرداخت انجام نشده است.\n"
            f"کد وضعیت ترونادو: `{status_id}` ({title})\n"
            f"شناسه سفارش: `{target_oid}`"
        )


# ---------------------------------------------------------------------------
# Callback Queries
# ---------------------------------------------------------------------------
@bot.callback_query_handler(func=lambda call: True)
def handle_callbacks(call):
    track_user(call.from_user)
    data = call.data
    uid = call.from_user.id

    in_maint, maint_msg = is_maintenance_mode()
    if in_maint:
        if is_admin(uid):
            if data.startswith("adm_") or data in ["admin", "stats", "live_stats", "cancel_broadcast", "do_fwd_all", "do_copy_all"]:
                pass
            else:
                try:
                    bot.answer_callback_query(call.id, "🛠 ربات تا ساعت ۹ شب در دست تعمیر است (فروش و خدمات مسدود است)", show_alert=True)
                except Exception:
                    pass
                safe_send_message(call.message.chat.id, "🛠 *ربات در حالت تعمیر (خاموش) است (تا ساعت ۲۱:۰۰).*\nکاربران عادی به این دکمه دسترسی ندارند.")
                return
        else:
            try:
                bot.answer_callback_query(call.id, "🛠 ربات موقتاً در دست تعمیر است (تا ساعت ۹ شب)", show_alert=True)
            except Exception:
                pass
            safe_send_message(call.message.chat.id, maint_msg)
            return

    # انتخاب سیستم‌عامل و پلن‌ها
    if data == "show_plans":
        safe_answer_callback(call.id)
        text = (
            "💎 *لطفاً سیستم‌عامل مورد نظر خود را جهت خرید اشتراک انتخاب فرمایید:*\n\n"
            "_(لایسنس صادرشده دقیقاً مختص همان سیستم‌عامل فعال خواهد شد)_"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=platform_selection_keyboard(), parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, text, reply_markup=platform_selection_keyboard())
        return

    elif data == "show_plans_android":
        safe_answer_callback(call.id)
        text = (
            "📱 *پلن‌های اشتراک اپلیکیشن اندروید اینترنت آزاد³⁶⁹*\n\n"
            "لطفاً مدت زمان مورد نظر خود را انتخاب کنید:\n"
            "_(این لایسنس مخصوص اپلیکیشن اندروید است و روی تلفن همراه فعال می‌شود)_"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=plans_keyboard_android(), parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, text, reply_markup=plans_keyboard_android())
        return

    elif data == "show_plans_windows":
        safe_answer_callback(call.id)
        text = (
            "💻 *پلن‌های اشتراک نرم‌افزار ویندوز اینترنت آزاد³⁶⁹*\n\n"
            "لطفاً مدت زمان مورد نظر خود را انتخاب کنید:\n"
            "_(این لایسنس مخصوص نرم‌افزار ویندوز است و روی کامپیوتر یا لپ‌تاپ فعال می‌شود)_"
        )
        try:
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=plans_keyboard_windows(), parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, text, reply_markup=plans_keyboard_windows())
        return

    elif data == "adm_noop":
        safe_answer_callback(call.id)
        return

    # حساب کاربری
    elif data == "my_account":
        safe_answer_callback(call.id)
        btn_my_account(call.message, target_uid=call.from_user.id)
        return

    # مشاهده کامل تمام لایسنس‌ها (آرشیو کامل)
    elif data == "show_all_purchases":
        safe_answer_callback(call.id)
        db = load_db()
        purchases = db.get("users", {}).get(str(call.from_user.id), {}).get("purchases", [])
        purchases.sort(key=lambda p: p.get("issued_at", 0) if isinstance(p, dict) else 0, reverse=True)
        if not purchases:
            safe_send_message(call.message.chat.id, "هیچ لایسنسی در حساب شما یافت نشد.")
            return

        now = int(time.time())
        lines = [f"📜 *آرشیو کامل تمامی {len(purchases)} لایسنس شما:*\n"]
        for idx, p in enumerate(purchases, 1):
            issued_at = p.get("issued_at", now)
            total_days = p.get("days", 30)
            elapsed_days = (now - issued_at) // 86400
            rem_days = max(0, total_days - elapsed_days)
            date_str = time.strftime("%Y/%m/%d %H:%M", time.localtime(issued_at))
            status_badge = "🟢" if rem_days > 0 else "🔴"
            p_name = p.get("plan_name", "اشتراک اختصاصی")
            k_val = p.get("key", "")
            lines.append(f"{idx}. {escape_md(p_name)} | {status_badge}\n   🔑 `{k_val}`\n   📅 {date_str} (مانده: {rem_days} روز)")

        safe_send_message(call.message.chat.id, "\n".join(lines))
        return

    # راهنمای اتصال دستی
    elif data == "manual_guide":
        safe_answer_callback(call.id)
        send_manual_connection_guide(call.message.chat.id)
        return

    # پیام به پشتیبانی
    elif data == "start_support":
        safe_answer_callback(call.id)
        btn_support(call.message, target_uid=call.from_user.id)
        return

    # 1. کاربر پلنی را انتخاب کرده است
    elif data.startswith("buy_"):
        plan_code = data.replace("buy_", "")
        if plan_code not in PLANS_INFO:
            safe_answer_callback(call.id)
            return
        info = PLANS_INFO[plan_code]

        # بررسی موجودی پلن‌ها (بر اساس تنظیمات زنده دیتابیس)
        if not is_plan_available(plan_code):
            safe_answer_callback(call.id, "⚠️ موجودی این پلن به اتمام رسیده است!", show_alert=True)

            sold_out_text = (
                "⚠️ *اتمام موجودی و توقف موقت فروش!*\n\n"
                f"کاربر گرامی؛ در حال حاضر ظرفیت اشتراک *{escape_md(info['name'])}* **به اتمام رسیده است**.\n\n"
                "📢 به محض افزایش پهنای باند سرورها و شارژ مجدد موجودی لایسنس‌ها، در کانال رسمی اطلاع‌رسانی خواهد شد.\n\n"
                "جهت رزرو لایسنس یا ثبت پیام در لیست انتظار، می‌توانید با پشتیبانی در ارتباط باشید: 👇"
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("💬 ثبت پیام در پشتیبانی / رزرو", callback_data="ticket_new"),
                types.InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="cancel_action")
            )
            try:
                bot.edit_message_text(sold_out_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                safe_send_message(call.message.chat.id, sold_out_text, reply_markup=markup)
            return

        if TRONADO_ENABLED:
            if not CARD_TO_CARD_ENABLED:
                safe_answer_callback(call.id, "⚡ در حال ایجاد فاکتور درگاه آنلاین...")
                order = tronado_create_order(plan_code, uid, call.from_user)
                if not order:
                    safe_send_message(call.message.chat.id, "⚠️ اتصال به درگاه آنلاین موقتاً با وقفه مواجه شد. لطفاً چند لحظه بعد مجدداً تلاش فرمایید.")
                    return
                db = load_db()
                db.setdefault("orders", {})
                db["orders"][order["order_id"]] = order
                save_db(db)

                pay_text = (
                    f"⚡ *فاکتور پرداخت آنلاین (درگاه امن تلگرامی):*\n\n"
                    f"🔹 اشتراک انتخابی: *{escape_md(info['name'])}*\n"
                    f"💰 مبلغ فاکتور: *{info['price']}*\n"
                    f"🆔 شناسه سفارش: `{order['order_id']}`\n\n"
                    f"📌 *دستورالعمل پرداخت:*\n"
                    f"۱. روی دکمه‌ی *«🚀 ورود به درگاه و پرداخت آنلاین»* زیر کلیک کنید.\n"
                    f"۲. در مینی‌اپ پرداخت ترونادو با هر کارت عضو شتاب پرداخت را انجام دهید.\n"
                    f"۳. به محض تایید پرداخت، لایسنس شما **به‌صورت ۱۰۰٪ خودکار و آنی** در همین صفحه ارسال خواهد شد.\n\n"
                    f"_(همچنین بلافاصله پس از پرداخت می‌توانید روی دکمه «🔄 استعلام و دریافت آنی لایسنس» بزنید)_"
                )
                markup = types.InlineKeyboardMarkup(row_width=1)
                markup.add(
                    types.InlineKeyboardButton("🚀 ورود به درگاه و پرداخت آنلاین (شتاب)", url=order["miniapp_url"]),
                    types.InlineKeyboardButton("🔄 استعلام و دریافت آنی لایسنس", callback_data=f"trnd_chk_{order['order_id']}"),
                    types.InlineKeyboardButton("🔙 بازگشت به لیست پلن‌ها", callback_data="show_plans")
                )
                try:
                    bot.edit_message_text(pay_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                except Exception:
                    safe_send_message(call.message.chat.id, pay_text, reply_markup=markup)
                return

            select_text = (
                f"🛒 *انتخاب نحوه پرداخت اشتراک {escape_md(info['name'])}:*\n\n"
                f"💰 مبلغ قابل پرداخت: *{info['price']}*\n"
                f"⏳ مدت اعتبار: *{info['days']} روز*\n\n"
                "لطفاً یکی از روش‌های پرداخت زیر را انتخاب فرمایید:\n\n"
                "⚡ *۱. پرداخت آنلاین شتابی (پیشنهادی - تحویل خودکار و آنی):*\n"
                "پرداخت امن با کلیه کارت‌های بانکی عضو شتاب در محیط تلگرام، و **دریافت خودکار و آنی لایسنس** بلافاصله پس از پرداخت بدون معطلی و بدون نیاز به تایید ادمین.\n\n"
                "💳 *۲. کارت‌به‌کارت سنتی:*\n"
                "واریز مستقیم به شماره کارت بانکی و ارسال تصویر فیش در ربات (نیازمند بررسی و تایید دستی توسط مدیریت)."
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("⚡ پرداخت آنلاین شتابی (تحویل خودکار)", callback_data=f"pay_online_{plan_code}"),
                types.InlineKeyboardButton("💳 کارت‌به‌کارت بانکی (ارسال فیش)", callback_data=f"pay_card_{plan_code}"),
                types.InlineKeyboardButton("🔙 بازگشت به منوی پلن‌ها", callback_data="show_plans")
            )
            try:
                bot.edit_message_text(select_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                safe_send_message(call.message.chat.id, select_text, reply_markup=markup)
            bot.answer_callback_query(call.id)
            return

        if not CARD_TO_CARD_ENABLED:
            bot.answer_callback_query(call.id, "⚠️ روش پرداخت کارت‌به‌کارت موقتاً غیرفعال است.", show_alert=True)
            return

        active_card = get_random_card_number()
        set_user_state(uid, {
            "state": "awaiting_receipt",
            "plan_code": plan_code,
            "card_number": active_card,
            "time": int(time.time())
        })
        invoice_text = (
            f"📋 *فاکتور سفارش شما:*\n\n"
            f"🔹 پلن انتخابی: *{escape_md(info['name'])}*\n"
            f"💰 مبلغ قابل پرداخت: *{info['price']}*\n\n"
            f"💳 *شماره کارت جهت واریز:*\n"
            f"`{active_card}`\n"
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

    # انتخاب پرداخت آنلاین شتابی (درگاه ترونادو)
    elif data.startswith("pay_online_"):
        plan_code = data.replace("pay_online_", "")
        if plan_code not in PLANS_INFO:
            return
        info = PLANS_INFO[plan_code]

        if not is_plan_available(plan_code):
            safe_answer_callback(call.id, "⚠️ این پلن تکمیل ظرفیت است!", show_alert=True)
            return

        safe_answer_callback(call.id, "⚡ در حال ایجاد فاکتور درگاه آنلاین...")
        order = tronado_create_order(plan_code, uid, call.from_user)
        if not order:
            safe_send_message(call.message.chat.id, "⚠️ اتصال به درگاه آنلاین موقتاً با وقفه مواجه شد. لطفاً چند لحظه بعد مجدداً تلاش فرمایید.")
            return

        db = load_db()
        db.setdefault("orders", {})
        db["orders"][order["order_id"]] = order
        save_db(db)

        pay_text = (
            f"⚡ *فاکتور پرداخت آنلاین (درگاه امن تلگرامی):*\n\n"
            f"🔹 اشتراک انتخابی: *{escape_md(info['name'])}*\n"
            f"💰 مبلغ فاکتور: *{info['price']}*\n"
            f"🆔 شناسه سفارش: `{order['order_id']}`\n\n"
            f"📌 *دستورالعمل پرداخت:*\n"
            f"۱. روی دکمه‌ی *«🚀 ورود به درگاه و پرداخت آنلاین»* زیر کلیک کنید.\n"
            f"۲. در مینی‌اپ پرداخت ترونادو با هر کارت عضو شتاب پرداخت را انجام دهید.\n"
            f"۳. به محض تایید پرداخت، لایسنس شما **به‌صورت ۱۰۰٪ خودکار و آنی** در همین صفحه ارسال خواهد شد.\n\n"
            f"_(همچنین بلافاصله پس از پرداخت می‌توانید روی دکمه «🔄 استعلام و دریافت آنی لایسنس» بزنید)_"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🚀 ورود به درگاه و پرداخت آنلاین (شتاب)", url=order["miniapp_url"]),
            types.InlineKeyboardButton("🔄 استعلام و دریافت آنی لایسنس", callback_data=f"trnd_chk_{order['order_id']}"),
        )
        if CARD_TO_CARD_ENABLED:
            markup.add(types.InlineKeyboardButton("💳 تغییر روش پرداخت به کارت‌به‌کارت", callback_data=f"pay_card_{plan_code}"))
        markup.add(types.InlineKeyboardButton("🔙 بازگشت به لیست پلن‌ها", callback_data="show_plans"))
        try:
            bot.edit_message_text(pay_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, pay_text, reply_markup=markup)

    # انتخاب پرداخت کارت‌به‌کارت
    elif data.startswith("pay_card_"):
        if not CARD_TO_CARD_ENABLED:
            safe_answer_callback(call.id, "⚠️ روش پرداخت کارت‌به‌کارت موقتاً غیرفعال است. لطفاً از درگاه آنلاین استفاده فرمایید.", show_alert=True)
            return

        plan_code = data.replace("pay_card_", "")
        if plan_code not in PLANS_INFO:
            safe_answer_callback(call.id)
            return
        info = PLANS_INFO[plan_code]
        if not is_plan_available(plan_code):
            safe_answer_callback(call.id, "⚠️ این پلن تکمیل ظرفیت است!", show_alert=True)
            return

        active_card = get_random_card_number()
        set_user_state(uid, {
            "state": "awaiting_receipt",
            "plan_code": plan_code,
            "card_number": active_card,
            "time": int(time.time())
        })
        invoice_text = (
            f"📋 *فاکتور پرداخت کارت‌به‌کارت:*\n\n"
            f"🔹 پلن انتخابی: *{escape_md(info['name'])}*\n"
            f"💰 مبلغ قابل پرداخت: *{info['price']}*\n\n"
            f"💳 *شماره کارت جهت واریز:*\n"
            f"`{active_card}`\n"
            f"_(برای کپی شماره کارت روی آن ضربه بزنید)_\n\n"
            f"📌 *دستورالعمل پرداخت:*\n"
            f"۱. مبلغ فوق را به شماره کارت بالا واریز فرمایید.\n"
            f"۲. پس از پرداخت، تصویر فیش واریز یا **کد پیگیری تراکنش** را همین‌جا ارسال نمایید.\n"
            f"_(سیستم خودکار پیام شما را برای مدیریت ارسال خواهد کرد)_"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("💳 پرداخت کردم / ارسال فیش", callback_data=f"paid_{plan_code}"),
            types.InlineKeyboardButton("⚡ تغییر به پرداخت آنلاین شتابی", callback_data=f"pay_online_{plan_code}") if TRONADO_ENABLED else types.InlineKeyboardButton("❌ انصراف از خرید", callback_data="cancel_action"),
            types.InlineKeyboardButton("🔙 بازگشت به لیست پلن‌ها", callback_data="show_plans")
        )
        try:
            bot.edit_message_text(invoice_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, invoice_text, reply_markup=markup)
        bot.answer_callback_query(call.id)

    # دکمه استعلام و دریافت آنی لایسنس
    elif data.startswith("trnd_chk_"):
        payment_id = data.replace("trnd_chk_", "")
        safe_answer_callback(call.id, "⏳ در حال استعلام وضعیت سفارش از درگاه...")
        db = load_db()
        order = db.get("orders", {}).get(payment_id)
        if not order:
            safe_answer_callback(call.id, "سفارش در سیستم یافت نشد!", show_alert=True)
            return

        if order.get("status") == "approved":
            safe_answer_callback(call.id, "✅ این سفارش قبلاً تایید و لایسنس تحویل شده است!", show_alert=True)
            return

        st = tronado_check_order_status(payment_id)
        status_id = st.get("OrderStatusID") if isinstance(st, dict) else None
        is_paid = (
            st.get("IsPaid") is True
            or status_id == 30
            or str(st.get("OrderStatusTitle", "")).lower() in ("paymentaccepted", "paid", "completed", "success")
        ) if isinstance(st, dict) else False

        if is_paid:
            ok, msg = fulfill_tronado_order(payment_id, st)
            if ok:
                try:
                    bot.edit_message_text(
                        "✅ *پرداخت آنلاین شما تایید شد!*\n\nکد لایسنس اختصاصی شما با موفقیت صادر و در پیام زیر ارسال گردید.",
                        call.message.chat.id,
                        call.message.message_id,
                        parse_mode="Markdown"
                    )
                except Exception:
                    pass
                safe_answer_callback(call.id, "✅ پرداخت شما تایید و لایسنس ارسال شد!", show_alert=True)
            else:
                safe_answer_callback(call.id, f"خطا در صدور لایسنس: {msg}", show_alert=True)
        elif status_id in (20, 25, 27):
            safe_answer_callback(call.id, "⏳ فاکتور شما در درگاه در انتظار پرداخت است. چنانچه پرداخت را انجام داده‌اید، لطفاً ۳۰ ثانیه دیگر مجدداً دکمه را لمس نمایید.", show_alert=True)
        elif status_id in (40, 200) or (isinstance(st, dict) and str(st.get("OrderStatusTitle", "")).lower() == "cancelled"):
            safe_answer_callback(call.id, "❌ تراکنش در درگاه لغو یا منقضی شده است.", show_alert=True)
        else:
            safe_answer_callback(call.id, "⏳ هنوز تاییدیه‌ای از درگاه دریافت نشده است. چنانچه پرداخت را انجام داده‌اید، لطفاً ۳۰ ثانیه دیگر مجدداً دکمه را لمس کنید.", show_alert=True)

    elif data.startswith("paid_"):
        if not CARD_TO_CARD_ENABLED:
            safe_answer_callback(call.id, "⚠️ روش پرداخت کارت‌به‌کارت موقتاً غیرفعال است. لطفاً از درگاه آنلاین استفاده فرمایید.", show_alert=True)
            return
        plan_code = data.replace("paid_", "")
        if plan_code not in PLANS_INFO:
            return
        if not is_plan_available(plan_code):
            try:
                bot.answer_callback_query(call.id, "⚠️ ظرفیت این پلن تکمیل شده است!", show_alert=True)
            except Exception:
                pass
            safe_send_message(call.message.chat.id, "⚠️ متأسفانه در حال حاضر ظرفیت این پلن تکمیل شده است و امکان صدور لایسنس جدید وجود ندارد.")
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
        safe_answer_callback(call.id)

    elif data == "submit_receipt":
        clear_user_state(uid)
        receipt_intro = (
            "🧾 *ثبت و ارسال رسید پرداخت*\n\n"
            "کاربر گرامی؛ چنانچه هزینه اشتراک را پرداخت نموده‌اید (کارت‌به‌کارت یا درگاه) ولی لایسنس خود را دریافت نکرده‌اید، "
            "لطفاً ابتدا **پلن خریداری‌شده‌ی خود** را از گزینه‌های زیر انتخاب فرمایید:\n\n"
            "👇 _روی پلن مربوطه کلیک کنید:_"
        )
        try:
            bot.edit_message_text(receipt_intro, call.message.chat.id, call.message.message_id, reply_markup=receipt_plan_selection_keyboard(), parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, receipt_intro, reply_markup=receipt_plan_selection_keyboard())
        safe_answer_callback(call.id)

    elif data.startswith("rec_plan_"):
        plan_code = data.replace("rec_plan_", "")
        if plan_code not in PLANS_INFO:
            safe_answer_callback(call.id, "پلن نامعتبر است!", show_alert=True)
            return
        info = PLANS_INFO[plan_code]

        set_user_state(uid, {
            "state": "awaiting_receipt",
            "plan_code": plan_code,
            "time": int(time.time())
        })

        prompt_text = (
            f"📸 *ارسال تصویر رسید پرداخت برای پلن {escape_md(info['name'])}:*\n\n"
            f"💰 مبلغ پلن: *{info['price']}*\n"
            f"⏳ مدت اعتبار: *{info['days']} روز*\n\n"
            f"لطفاً هم‌اکنون **تصویر (عکس) فیش واریزی یا اسکرین‌شات رسید پرداخت** خود را ارسال فرمایید 📸\n\n"
            f"⚠️ *نکته مهم:* ارسال رسید به صورت متن مجاز نمی‌باشد و حتماً باید تصویر یا اسکرین‌شات فیش را ارسال نمایید.\n\n"
            f"⚡ رسید شما مستقیماً برای مدیریت ارسال خواهد شد و پس از بررسی اصالت، کد لایسنس اختصاصی به صورت آنی ارسال می‌شود."
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🔙 تغییر پلن انتخابی", callback_data="submit_receipt"),
            types.InlineKeyboardButton("❌ انصراف از ثبت رسید", callback_data="cancel_action")
        )

        try:
            bot.edit_message_text(prompt_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, prompt_text, reply_markup=markup)
        safe_answer_callback(call.id)

    elif data == "cancel_action":
        clear_user_state(uid)
        try:
            bot.edit_message_text("❌ عملیات لغو گردید.", call.message.chat.id, call.message.message_id)
        except Exception:
            safe_send_message(call.message.chat.id, "❌ عملیات لغو گردید.")
        safe_answer_callback(call.id, "لغو شد")

    elif data == "cancel_admin_reply":
        if is_admin(uid):
            clear_admin_state(uid)
            try:
                bot.edit_message_text("❌ ارسال پاسخ به کاربر لغو شد.", call.message.chat.id, call.message.message_id)
            except Exception:
                safe_send_message(call.message.chat.id, "❌ ارسال پاسخ به کاربر لغو شد.")
            safe_answer_callback(call.id, "لغو شد")

    # تیکت پشتیبانی: شروع پیام به ادمین
    elif data == "ticket_new":
        safe_answer_callback(call.id)
        safe_send_message(call.message.chat.id, SUPPORT_CLOSED_MESSAGE)
        return

    elif data == "adm_send_direct_msg":
        if not is_admin(uid):
            safe_answer_callback(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return
        set_admin_state({"state": "waiting_target_user_for_msg"}, admin_id=uid)
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_admin_reply"))
        safe_send_message(
            call.message.chat.id,
            "✉️ *ارسال مستقیم پیام به کاربر*\n\n"
            "لطفاً **آیدی عددی** یا **یوزرنیم کاربر** را ارسال فرمایید:\n"
            "(مثال: `161957867` یا `@khan007khan`)\n\n"
            "یا می‌توانید دستور را مستقیم ارسال کنید:\n"
            "`/send 161957867 متن پیام شما`",
            reply_markup=markup
        )
        safe_answer_callback(call.id, "آماده دریافت آیدی")

    # ادمین روی دکمه «پاسخ به کاربر» یا «ارسال پیام به کاربر» می‌زند
    elif data.startswith("reply_user_"):
        if not is_admin(uid):
            safe_answer_callback(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return
        target_uid = data.replace("reply_user_", "")
        set_admin_state({"state": "replying_to_user", "target_uid": target_uid}, admin_id=uid)

        db_cur = load_db()
        u_info = db_cur.get("users", {}).get(str(target_uid), {})
        f_n = u_info.get("first_name", "کاربر")
        u_n = u_info.get("username", "ندارد")

        prompt_admin = (
            f"✍️ *ارسال پیام به کاربر {escape_md(f_n)} (@{escape_md(u_n)}) — `{target_uid}`:*\n\n"
            f"لطفاً پیام، تصویر یا فایل پاسخ خود را تایپ و ارسال نمایید.\n"
            f"این پیام مستقیماً در ربات برای کاربر فرستاده خواهد شد."
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("❌ انصراف از پاسخ", callback_data="cancel_admin_reply"))
        safe_send_message(call.message.chat.id, prompt_admin, reply_markup=markup)
        bot.answer_callback_query(call.id, "آماده دریافت پیام شما")

    # تایید رسید پرداخت توسط ادمین
    elif data.startswith("appr_"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return

        order_id = data.replace("appr_", "")
        db = load_db()
        db.setdefault("orders", {})
        order = db["orders"].get(order_id)
        if not order:
            # Self-healing: Reconstruct order metadata directly from the approval message card
            msg_txt = (call.message.caption or call.message.text or "")
            parts = order_id.split("_")
            parsed_uid = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else None
            if not parsed_uid:
                m_uid = re.search(r"(?:🆔\s*آیدی عددی|آیدی عددی|شناسه)\s*:\s*`?(\d+)`?", msg_txt)
                if m_uid:
                    parsed_uid = int(m_uid.group(1))

            parsed_plan = None
            for p_code, p_info in PLANS_INFO.items():
                if p_info["name"] in msg_txt or f": {p_code}" in msg_txt:
                    parsed_plan = p_code
                    break
            if not parsed_plan:
                if "اندروید" in msg_txt:
                    if "۱ ساله" in msg_txt or "1 ساله" in msg_txt or "۳۶۵" in msg_txt:
                        parsed_plan = "AN1Y"
                    elif "۳ ماهه" in msg_txt or "3 ماهه" in msg_txt:
                        parsed_plan = "AN3M"
                    elif "۲ ماهه" in msg_txt or "2 ماهه" in msg_txt:
                        parsed_plan = "AN2M"
                    elif "۱ ماهه" in msg_txt or "1 ماهه" in msg_txt:
                        parsed_plan = "AN1M"
                elif "ویندوز" in msg_txt:
                    if "۱ ساله" in msg_txt or "1 ساله" in msg_txt or "۳۶۵" in msg_txt:
                        parsed_plan = "1Y"
                    elif "۳ ماهه" in msg_txt or "3 ماهه" in msg_txt:
                        parsed_plan = "3M"
                    elif "۲ ماهه" in msg_txt or "2 ماهه" in msg_txt:
                        parsed_plan = "2M"
                    elif "۱ ماهه" in msg_txt or "1 ماهه" in msg_txt:
                        parsed_plan = "1M"

            if parsed_uid and parsed_plan:
                order = {
                    "order_id": order_id,
                    "user_id": parsed_uid,
                    "plan_code": parsed_plan,
                    "status": "pending",
                    "price": PLANS_INFO.get(parsed_plan, {}).get("price", "—"),
                    "created_at": int(parts[1]) if len(parts) >= 2 and parts[1].isdigit() else int(time.time()),
                    "reconstructed": True
                }
                db["orders"][order_id] = order
            else:
                try:
                    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
                except Exception:
                    pass
                bot.answer_callback_query(call.id, "سفارش نامعتبر است یا مشخصات قابل بازیابی نیست!", show_alert=True)
                return

        if order.get("status") != "pending":
            existing_key = order.get("key", "")
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except Exception:
                pass
            msg = f"این سفارش قبلاً تایید شده و لایسنس ارسال گردیده است.\nکد: {existing_key}" if existing_key else f"این سفارش قبلاً {order.get('status')} شده است!"
            bot.answer_callback_query(call.id, msg, show_alert=True)
            return

        buyer_id = order["user_id"]
        plan_code = order["plan_code"]
        info = PLANS_INFO.get(plan_code, {"name": plan_code, "days": 30})

        if plan_code == "VIP1Y":
            res_vip = issue_keys_for_vip_plan(db, buyer_id)
            if not res_vip:
                safe_send_message(call.message.chat.id, f"⚠️ خطا در تولید خودکار لایسنس‌های {info['name']}!")
                bot.answer_callback_query(call.id, "خطا در تولید لایسنس!", show_alert=True)
                return
            key_win, key_and = res_vip
            key = f"ویندوز: {key_win}\nاندروید: {key_and}"
            order["key_win"] = key_win
            order["key_and"] = key_and
            order["status"] = "approved"
            order["approved_at"] = int(time.time())
            order["approved_by"] = uid
            order["key"] = key
            save_db(db, immediate_sync=True)

            buyer_msg = (
                "🎉 *رسید پرداخت شما تایید شد!*\n\n"
                "👑 *پکیج اشتراک ۱ ساله VIP (ویندوز + اندروید)*\n"
                "⏳ مدت اعتبار: *۳۶۵ روز کامل (هر دو سیستم‌عامل)*\n\n"
                "💻 *کد لایسنس اختصاصی نرم‌افزار ویندوز (کامپیوتر):*\n"
                f"`{key_win}`\n"
                "_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
                "📱 *کد لایسنس اختصاصی اپلیکیشن اندروید (موبایل):*\n"
                f"`{key_and}`\n"
                "_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
                "━━━━━━━━━━━━━━━━━━━\n"
                "📌 *دستورالعمل فعال‌سازی:*\n"
                "۱. **در کامپیوتر:** کد اول را داخل نرم‌افزار ویندوز در بخش «ثبت لایسنس» وارد و فعال نمایید.\n"
                "۲. **در گوشی:** اپلیکیشن اندروید را باز کرده، روی کلید «اتصال» یا نشان لایسنس بالای صفحه زده و کد دوم را Paste و فعال نمایید.\n\n"
                "همچنین هر دو لایسنس در بخش *«👤 حساب کاربری من»* ذخیره شدند.\n\n"
                "با تشکر از اعتماد شما به *اینترنت آزاد³⁶⁹* 🌸"
            )
            safe_send_message(buyer_id, buyer_msg)
        else:
            key = issue_key_for_plan_atomic(db, plan_code, buyer_id)
            if not key:
                safe_send_message(call.message.chat.id, f"⚠️ خطا در تولید خودکار لایسنس برای {info['name']}!")
                bot.answer_callback_query(call.id, "خطا در تولید لایسنس!", show_alert=True)
                return

            order["status"] = "approved"
            order["approved_at"] = int(time.time())
            order["approved_by"] = uid
            order["key"] = key
            save_db(db, immediate_sync=True)

            is_android = info.get("platform") == "android" or str(plan_code).startswith("AN")
            if is_android:
                activation_guide = (
                    "📌 *نحوه فعال‌سازی در گوشی (اندروید):*\n"
                    "۱. اپلیکیشن اندروید را باز کنید.\n"
                    "۲. روی کلید *«اتصال»* یا نشان لایسنس بالای صفحه بزنید.\n"
                    "۳. کد بالا را در کادر Paste کرده و *فعال‌سازی* را لمس کنید.\n\n"
                    "همچنین این لایسنس در بخش *«👤 حساب کاربری من»* ذخیره شد.\n\n"
                    "با تشکر از اعتماد شما به *اینترنت آزاد³⁶⁹* 🌸"
                )
            else:
                activation_guide = (
                    "📌 *نحوه فعال‌سازی در ویندوز:*\n"
                    "این کد را داخل نرم‌افزار ویندوز در بخش *«ثبت لایسنس»* وارد کرده و فعال نمایید.\n"
                    "همچنین این لایسنس در بخش *«👤 حساب کاربری من»* ذخیره شد.\n\n"
                    "با تشکر از اعتماد شما به *اینترنت آزاد³⁶⁹* 🌸"
                )

            buyer_msg = (
                f"🎉 *رسید پرداخت شما تایید شد!*\n\n"
                f"کد لایسنس اختصاصی شما:\n"
                f"`{key}`\n\n"
                f"_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
                f"🔹 پلن خریداری‌شده: *{escape_md(info['name'])}*\n"
                f"⏳ مدت اعتبار: *{info['days']} روز*\n\n"
                f"{activation_guide}"
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
                if len(new_cap) > 1024:
                    new_cap = f"✅ *رسید تایید شد و لایسنس صادر گردید.*\nکد: `{key}`"
                try:
                    bot.edit_message_caption(caption=new_cap, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode="Markdown")
                except Exception:
                    clean_cap = new_cap.replace("*", "").replace("`", "")
                    bot.edit_message_caption(caption=clean_cap, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode=None)
            elif call.message.text:
                new_txt = (
                    f"{call.message.text}\n\n"
                    f"━━━━━━━━━━━━━━━━━━━\n"
                    f"✅ *رسید تایید شد و لایسنس صادر گردید.*\n"
                    f"کد: `{key}`"
                )
                try:
                    bot.edit_message_text(text=new_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode="Markdown")
                except Exception:
                    clean_txt = new_txt.replace("*", "").replace("`", "")
                    bot.edit_message_text(text=clean_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode=None)
            else:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        except Exception as e:
            print(f"Error editing admin approval message: {e}")
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except Exception:
                pass

        bot.answer_callback_query(call.id, "پرداخت تایید و لایسنس ارسال شد ✓")

    # رد رسید پرداخت توسط ادمین
    elif data.startswith("rej_"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return

        order_id = data.replace("rej_", "")
        db = load_db()
        db.setdefault("orders", {})
        order = db["orders"].get(order_id)
        if not order:
            parts = order_id.split("_")
            parsed_uid = int(parts[2]) if len(parts) >= 3 and parts[2].isdigit() else None
            if not parsed_uid:
                msg_txt = (call.message.caption or call.message.text or "")
                m_uid = re.search(r"(?:🆔\s*آیدی عددی|آیدی عددی|شناسه)\s*:\s*`?(\d+)`?", msg_txt)
                if m_uid:
                    parsed_uid = int(m_uid.group(1))
            if parsed_uid:
                order = {
                    "order_id": order_id,
                    "user_id": parsed_uid,
                    "status": "pending",
                    "created_at": int(time.time()),
                    "reconstructed": True
                }
                db["orders"][order_id] = order

        if not order or order.get("status") != "pending":
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except Exception:
                pass
            bot.answer_callback_query(call.id, "سفارش نامعتبر است یا قبلاً بررسی شده!", show_alert=True)
            return

        buyer_id = order["user_id"]
        order["status"] = "rejected"
        order["rejected_at"] = int(time.time())
        order["rejected_by"] = uid
        save_db(db, immediate_sync=True)

        reject_msg = (
            "❌ *رسید پرداخت شما تایید نشد!*\n\n"
            "تصویر ارسالی نامعتبر بود یا مبلغ به حساب واریز نگردیده است.\n\n"
            "در صورتی که مبلغ از حسابتان کسر شده است، لطفاً با پشتیبانی در ارتباط باشید:\n"
            "💬 دکمه «پشتیبانی» در منوی ربات"
        )
        safe_send_message(buyer_id, reject_msg)

        try:
            if call.message.caption:
                new_cap = f"{call.message.caption}\n\n━━━━━━━━━━━━━━━━━━━\n❌ *این رسید رد شد.*"
                if len(new_cap) > 1024:
                    new_cap = "❌ *این رسید رد شد.*"
                try:
                    bot.edit_message_caption(caption=new_cap, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode="Markdown")
                except Exception:
                    clean_cap = new_cap.replace("*", "")
                    bot.edit_message_caption(caption=clean_cap, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode=None)
            elif call.message.text:
                new_txt = f"{call.message.text}\n\n━━━━━━━━━━━━━━━━━━━\n❌ *این رسید رد شد.*"
                try:
                    bot.edit_message_text(text=new_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode="Markdown")
                except Exception:
                    clean_txt = new_txt.replace("*", "")
                    bot.edit_message_text(text=clean_txt, chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None, parse_mode=None)
            else:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
        except Exception as e:
            print(f"Error editing admin rejection message: {e}")
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=None)
            except Exception:
                pass
        bot.answer_callback_query(call.id, "رسید رد شد ❌")

    # گزینه‌های پنل مدیریت ادمین
    elif data.startswith("adm_"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return
        action = data.replace("adm_", "")
        if action == "toggle_maint":
            db = load_db()
            in_maint, _ = is_maintenance_mode()
            new_state = not in_maint
            db["maintenance"] = {
                "enabled": new_state,
                "until_ts": 0,
                "updated_by": uid,
                "updated_at": int(time.time())
            }
            save_db(db, immediate_sync=True)
            status_str = "فعال شد 🔴 (ربات برای کاربران بسته شد)" if new_state else "غیرفعال شد 🟢 (ربات برای کاربران باز شد)"
            bot.answer_callback_query(call.id, f"حالت تعمیر {status_str}", show_alert=True)
            try:
                bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=admin_dashboard_keyboard())
            except Exception:
                pass
            return
        elif action == "plans_mgr":
            text = (
                "📦 *مدیریت موجودی پلن‌های اشتراک*\n\n"
                "در این بخش می‌توانید وضعیت موجودی هر یک از پلن‌ها را برای کاربران مشخص نمایید.\n\n"
                "• با کلیک روی هر دکمه، وضعیت آن پلن بلافاصله بین **موجود 🟢** و **ناموجود 🔴** تغییر می‌کند.\n"
                "• تغییرات بلافاصله در منوی خرید کاربران اعمال می‌شود."
            )
            markup = admin_plans_management_keyboard()
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                safe_send_message(call.message.chat.id, text, reply_markup=markup)
            bot.answer_callback_query(call.id)
            return
        elif action.startswith("toggle_plan_"):
            target_plan = action.replace("toggle_plan_", "")
            if target_plan in PLANS_INFO:
                avail = get_plan_availability()
                cur_state = avail.get(target_plan, False)
                new_state = not cur_state
                set_plan_availability(target_plan, new_state)
                p_name = PLANS_INFO[target_plan]["name"]
                status_word = "موجود شد ✅ (برای کاربران باز شد)" if new_state else "ناموجود شد ❌ (برای کاربران بسته شد)"
                bot.answer_callback_query(call.id, f"پلن {p_name}: {status_word}", show_alert=True)
                
                text = (
                    "📦 *مدیریت موجودی پلن‌های اشتراک*\n\n"
                    "در این بخش می‌توانید وضعیت موجودی هر یک از پلن‌ها را برای کاربران مشخص نمایید.\n\n"
                    "• با کلیک روی هر دکمه، وضعیت آن پلن بلافاصله بین **موجود 🟢** و **ناموجود 🔴** تغییر می‌کند.\n"
                    "• تغییرات بلافاصله در منوی خرید کاربران اعمال می‌شود."
                )
                markup = admin_plans_management_keyboard()
                try:
                    bot.edit_message_reply_markup(chat_id=call.message.chat.id, message_id=call.message.message_id, reply_markup=markup)
                except Exception:
                    try:
                        bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
                    except Exception:
                        pass
            else:
                bot.answer_callback_query(call.id, "پلن نامعتبر است!")
            return
        elif action == "stats":
            stats = get_inventory_stats()
            lines = [
                "📊 *گزارش موجودی و وضعیت لایسنس‌ها:*\n",
                "⚡ *موتور صدور هوشمند:* فعال و بدون محدودیت",
                "🛡️ *ضمانت عدم تکرار:* ۱۰۰٪ تضمین‌شده (Blacklist تطبیقی)\n"
            ]
            for p_code in ["1M", "2M", "3M", "1Y", "VIP1Y"]:
                st = stats[p_code]
                lines.append(f"• *{st['name']}:* {st['clean_on_disk']} عدد در انبار دیسک | صدور کریپتو: فعال")
            lines.append(f"\n📦 *کل لایسنس‌های صادرشده تا کنون:* {stats['_total_sold']} عدد")
            safe_send_message(call.message.chat.id, "\n".join(lines))
            bot.answer_callback_query(call.id)
        elif action in ("unapproved_receipts", "pending"):
            db = load_db()
            all_orders = db.get("orders", {})
            unapproved = [
                o for o in all_orders.values() 
                if isinstance(o, dict) and o.get("status") == "pending"
            ]
            
            if not unapproved:
                safe_answer_callback(call.id, "✅ هیچ رسید تاییدنشده‌ای وجود ندارد.", show_alert=True)
                safe_send_message(
                    call.message.chat.id, 
                    "✅ *تمامی رسیدها و فیش‌های پرداختی بررسی شده‌اند.*\nدر حال حاضر هیچ رسید تاییدنشده‌ای در صف انتظار وجود ندارد."
                )
                return

            # Sort ascending by creation time so oldest pending receipts are reviewed first
            unapproved.sort(key=lambda x: x.get("created_at", 0))
            count_unapproved = len(unapproved)

            safe_answer_callback(call.id, f"در حال ارسال {count_unapproved} رسید تاییدنشده...")
            
            intro_msg = (
                f"📋 *فهرست رسیدهای تایید نشده ({count_unapproved} سفارش)*\n\n"
                f"فیش‌ها و مشخصات هر خریدار در ادامه به همراه عکس و دکمه‌های تایید ارسال می‌شوند.\n"
                f"شما می‌توانید با کلیک روی دکمه‌های زیر هر فیش، لایسنس را فوراً صادر کنید، سفارش را رد کنید یا مستقیماً به خریدار پیام دهید."
            )
            safe_send_message(call.message.chat.id, intro_msg)

            for idx, o in enumerate(unapproved, start=1):
                o_id = o.get("order_id", "—")
                buyer_id = o.get("user_id")
                p_code = o.get("plan_code", "1M")
                p_info = PLANS_INFO.get(p_code, {})
                p_name = p_info.get("name", p_code)
                price_val = o.get("price", p_info.get("price", "—"))
                first_name = o.get("first_name", "کاربر")
                username = o.get("username", "ندارد")
                username_str = f"@{escape_md(username)}" if username and username != "ندارد" else "ندارد"
                card_used = o.get("card_number", "—")
                created_ts = o.get("created_at", time.time())
                try:
                    time_str = time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(created_ts))
                except Exception:
                    time_str = str(created_ts)

                caption_text = o.get("caption") or o.get("receipt_text") or ""
                user_caption_note = f"\n💬 متن همراه فیش: `{escape_md(caption_text)}`" if caption_text else ""

                tronado_auth = check_user_tronado_authenticity(buyer_id, p_code, caption_text)
                tronado_note = f"\n\n{tronado_auth['summary']}" if tronado_auth.get("summary") else ""

                card_caption = (
                    f"🧾 *رسید تایید نشده ({idx} از {count_unapproved})*\n\n"
                    f"🏷️ شماره سفارش: `{o_id}`\n"
                    f"👤 خریدار: {escape_md(first_name)} ({username_str})\n"
                    f"🆔 آیدی عددی: `{buyer_id}`\n"
                    f"📦 پلن درخواستی: *{escape_md(p_name)}*\n"
                    f"💰 مبلغ فاکتور: *{price_val}*\n"
                    f"💳 کارت مقصد: `{card_used}`\n"
                    f"⏰ زمان ثبت: `{time_str}`"
                    f"{user_caption_note}"
                    f"{tronado_note}"
                )
                if len(card_caption) > 1020:
                    card_caption = card_caption[:1015] + "..."

                admin_markup = types.InlineKeyboardMarkup(row_width=2)
                b_approve = types.InlineKeyboardButton("✅ تایید و صدور لایسنس", callback_data=f"appr_{o_id}")
                b_reject = types.InlineKeyboardButton("❌ رد سفارش", callback_data=f"rej_{o_id}")
                b_msg = types.InlineKeyboardButton("✉️ ارسال پیام به کاربر", callback_data=f"reply_user_{buyer_id}")
                admin_markup.add(b_approve, b_reject)
                admin_markup.add(b_msg)

                file_id = o.get("file_id")
                rec_type = o.get("receipt_type", "photo")

                sent_res = None
                if file_id:
                    if rec_type == "document":
                        sent_res = safe_send_document(call.message.chat.id, file_id, caption=card_caption, reply_markup=admin_markup)
                    else:
                        sent_res = safe_send_photo(call.message.chat.id, file_id, caption=card_caption, reply_markup=admin_markup)

                if not sent_res:
                    safe_send_message(call.message.chat.id, card_caption, reply_markup=admin_markup)

                time.sleep(0.35)
            return
        elif action == "VIP1Y":
            try:
                bot.answer_callback_query(call.id, "در حال صدور لایسنس‌های VIP دوگانه...")
            except Exception:
                pass
            try:
                db = load_db()
                res_vip = issue_keys_for_vip_plan(db, uid)
                if not res_vip:
                    safe_send_message(call.message.chat.id, "⚠️ خطا در تولید لایسنس‌های پکیج VIP!")
                    return
                key_win, key_and = res_vip
                save_db(db, immediate_sync=True)
                safe_send_message(
                    call.message.chat.id,
                    f"👑 *لایسنس‌های جدید پکیج ۱ ساله VIP دوگانه (رایگان ادمین):*\n\n"
                    f"💻 *لایسنس اختصاصی ویندوز (۳۶۵ روز):*\n`{key_win}`\n\n"
                    f"📱 *لایسنس اختصاصی اندروید (۳۶۵ روز):*\n`{key_and}`\n\n"
                    f"_(برای کپی روی هر کد ضربه بزنید)_\n\n"
                    f"⏳ مدت اعتبار: *۳۶۵ روز برای هر دو سیستم‌عامل*\n"
                    f"🔒 *تضمین عدم تکرار ۱۰۰٪:* این کلیدها با الگوریتم رمزنگاری یکتا (HMAC-SHA256) تولید شده‌اند ✓"
                )
            except Exception as e:
                safe_send_message(call.message.chat.id, f"⚠️ خطا در فرایند صدور VIP: {e}")
        elif action in PLANS_INFO:
            try:
                bot.answer_callback_query(call.id, "در حال صدور لایسنس یکتا...")
            except Exception:
                pass
            try:
                db = load_db()
                key = issue_key_for_plan_atomic(db, action, uid)
                if not key:
                    safe_send_message(call.message.chat.id, "⚠️ خطا در تولید لایسنس جدید!")
                    return
                save_db(db, immediate_sync=True)
                p_name = PLANS_INFO[action]["name"]
                p_days = PLANS_INFO[action]["days"]
                is_and = PLANS_INFO[action].get("platform") == "android" or action.startswith("AN")
                plat_badge = "📱 *سیستم‌عامل:* اندروید (موبایل)" if is_and else "💻 *سیستم‌عامل:* ویندوز (کامپیوتر)"
                safe_send_message(
                    call.message.chat.id,
                    f"✅ *لایسنس دستی جدید {escape_md(p_name)} (رایگان ادمین):*\n\n"
                    f"`{key}`\n\n"
                    f"_(برای کپی روی کد بالا ضربه بزنید)_\n\n"
                    f"{plat_badge}\n"
                    f"⏳ مدت اعتبار: *{p_days} روز*\n"
                    f"🔒 *تضمین عدم تکرار ۱۰۰٪:* این کلید با الگوریتم رمزنگاری یکتا (HMAC-SHA256) تولید شده و در هیچ سیستم دیگری فعال یا مصرف نشده است ✓"
                )
            except Exception as e:
                safe_send_message(call.message.chat.id, f"⚠️ خطا در فرایند صدور: {e}")
        elif action == "cards":
            db = load_db()
            c_state = get_card_state(db)
            cur_idx = c_state.get("current_index", 0) % len(CARD_NUMBERS)
            active_card = CARD_NUMBERS[cur_idx]
            cnt = c_state.get("count", 0)
            threshold = c_state.get("threshold", CARD_ROTATION_THRESHOLD)
            stats_dict = c_state.get("stats", {})

            card_lines = []
            for i, c in enumerate(CARD_NUMBERS, start=1):
                badge = "🟢 فعال" if (i - 1) == cur_idx else "⏳ در نوبت"
                c_total = stats_dict.get(c, 0)
                card_lines.append(f"{i}. `{c}` ({badge})\n   📊 مجموع واریزی‌های ثبت‌شده: *{c_total} عدد*")

            msg_text = (
                f"💳 *مدیریت و چرخش خودکار شماره کارت‌ها*\n\n"
                f"🎯 *شماره کارت فعال کنونی:*\n`{active_card}`\n\n"
                f"🔄 *وضعیت چرخش هوشمند:*\n"
                f"• تعداد واریزی‌های ثبت‌شده: *{cnt} از {threshold} واریز*\n"
                f"• هر ۱۰ رسید واریز، ربات خودکار به کارت بعدی تغییر می‌کند.\n\n"
                f"📋 *فهرست کارت‌های تعریف‌شده در سیستم:*\n\n" + "\n\n".join(card_lines)
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔄 تعویض دستی به کارت بعدی", callback_data="adm_rotate_card"),
                types.InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")
            )
            try:
                bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                safe_send_message(call.message.chat.id, msg_text, reply_markup=markup)
            bot.answer_callback_query(call.id)
            return
        elif action == "rotate_card":
            db = load_db()
            c_state = get_card_state(db)
            old_idx = c_state.get("current_index", 0) % len(CARD_NUMBERS)
            new_idx = (old_idx + 1) % len(CARD_NUMBERS)
            c_state["current_index"] = new_idx
            c_state["count"] = 0
            save_db(db, immediate_sync=True)
            new_card = CARD_NUMBERS[new_idx]
            bot.answer_callback_query(call.id, f"کارت فعال به {new_card} تغییر یافت ✓", show_alert=True)

            stats_dict = c_state.get("stats", {})
            threshold = c_state.get("threshold", CARD_ROTATION_THRESHOLD)
            card_lines = []
            for i, c in enumerate(CARD_NUMBERS, start=1):
                badge = "🟢 فعال" if (i - 1) == new_idx else "⏳ در نوبت"
                c_total = stats_dict.get(c, 0)
                card_lines.append(f"{i}. `{c}` ({badge})\n   📊 مجموع واریزی‌های ثبت‌شده: *{c_total} عدد*")

            msg_text = (
                f"💳 *مدیریت و چرخش خودکار شماره کارت‌ها*\n\n"
                f"🎯 *شماره کارت فعال کنونی:*\n`{new_card}`\n\n"
                f"🔄 *وضعیت چرخش هوشمند:*\n"
                f"• تعداد واریزی‌های ثبت‌شده: *0 از {threshold} واریز*\n"
                f"• هر ۱۰ رسید واریز، ربات خودکار به کارت بعدی تغییر می‌کند.\n\n"
                f"📋 *فهرست کارت‌های تعریف‌شده در سیستم:*\n\n" + "\n\n".join(card_lines)
            )
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔄 تعویض دستی به کارت بعدی", callback_data="adm_rotate_card"),
                types.InlineKeyboardButton("🔙 بازگشت به پنل مدیریت", callback_data="adm_back_panel")
            )
            try:
                bot.edit_message_text(msg_text, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                safe_send_message(call.message.chat.id, msg_text, reply_markup=markup)
            return
        elif action == "live_stats":
            markup = types.InlineKeyboardMarkup()
            markup.add(
                types.InlineKeyboardButton("🔄 بروزرسانی لحظه‌ای", callback_data="adm_live_stats"),
                types.InlineKeyboardButton("🔙 بازگشت به پنل", callback_data="adm_back_panel")
            )
            try:
                bot.edit_message_text(
                    text=get_live_bot_stats(),
                    chat_id=call.message.chat.id,
                    message_id=call.message.message_id,
                    reply_markup=markup,
                    parse_mode="Markdown"
                )
            except Exception:
                safe_send_message(call.message.chat.id, get_live_bot_stats(), reply_markup=markup)
            bot.answer_callback_query(call.id, "آمار بروزرسانی شد ✓")
            return
        elif action == "broadcast":
            bot.answer_callback_query(call.id)
            _start_broadcast_prompt(call.message.chat.id)
            return
        elif action == "back_panel":
            stats = get_inventory_stats()
            db = load_db()
            total_users = len(db.get("users", {}))
            pending_receipts_cnt = sum(1 for o in db.get("orders", {}).values() if isinstance(o, dict) and o.get("status") == "pending")
            pend_alert = f"\n⚠️ *رسیدهای تایید نشده در انتظار بررسی:* *{pending_receipts_cnt} عدد*\n" if pending_receipts_cnt > 0 else ""
            text = (
                f"👑 *پنل مدیریت ادمین*\n\n"
                f"👥 تعداد کل کاربران ثبت‌شده: *{total_users} نفر*\n"
                f"🏷️ موجودی کل کدهای آماده: *{stats['_total_available']} عدد*\n"
                f"📦 مجموع فروش کل: *{stats['_total_sold']} عدد*\n"
                f"{pend_alert}\n"
                f"جهت صدور لایسنس، ارسال پیام همگانی، مدیریت کارت‌ها یا مشاهده آمار آنلاین انتخاب فرمایید:"
            )
            try:
                bot.edit_message_text(text, call.message.chat.id, call.message.message_id, reply_markup=admin_dashboard_keyboard(), parse_mode="Markdown")
            except Exception:
                safe_send_message(call.message.chat.id, text, reply_markup=admin_dashboard_keyboard())
            bot.answer_callback_query(call.id)
            return

    elif data == "abort_active_broadcast":
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!", show_alert=True)
            return
        global BROADCAST_CANCELLED
        BROADCAST_CANCELLED = True
        bot.answer_callback_query(call.id, "🛑 در حال لغو و توقف ارسال...", show_alert=True)
        return

    elif data == "cancel_broadcast":
        clear_admin_state(uid)
        try:
            bot.edit_message_text(
                "❌ عملیات ارسال همگانی لغو شد.",
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                reply_markup=None
            )
        except Exception:
            safe_send_message(call.message.chat.id, "❌ عملیات ارسال همگانی لغو شد.")
        bot.answer_callback_query(call.id, "لغو شد")

    elif data.startswith("bc_btn_"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!")
            return
        btn_choice = data.replace("bc_btn_", "")
        adm_state = get_admin_state(uid)
        chat_id = adm_state.get("chat_id")
        msg_id = adm_state.get("msg_id")
        if not chat_id or not msg_id:
            bot.answer_callback_query(call.id, "پیام منقضی شده است. لطفاً مجدداً ارسال کنید.", show_alert=True)
            return

        adm_state["button_choice"] = btn_choice
        adm_state["state"] = "confirm_broadcast_final"
        set_admin_state(adm_state, admin_id=uid)

        reply_markup, btn_title = get_broadcast_reply_markup(btn_choice)
        db_now = load_db()
        tot_targets = len(get_all_broadcast_targets(db_now))

        if btn_choice == "none":
            markup = types.InlineKeyboardMarkup(row_width=2)
            markup.add(
                types.InlineKeyboardButton("🔄 فوروارد همگانی (با نقل‌قول منبع)", callback_data="do_fwd_all"),
                types.InlineKeyboardButton("📋 کپی مستقیم (بدون نقل‌قول)", callback_data="do_copy_all")
            )
            markup.add(types.InlineKeyboardButton("🔄 تغییر دکمه شیشه‌ای", callback_data="bc_change_btn"))
            markup.add(types.InlineKeyboardButton("❌ انصراف و لغو", callback_data="cancel_broadcast"))
            text_confirm = (
                f"📢 *تنظیمات ارسال همگانی (بدون دکمه)*\n\n"
                f"👥 کل مخاطبان: *{tot_targets} نفر*\n\n"
                f"لطفاً نحوه ارسال به کاربران را انتخاب کنید:\n"
                f"• *فوروارد:* پیام با نقل‌قول رسمی (Forward) و نام کانال ارسال می‌شود.\n"
                f"• *کپی مستقیم:* پیام عینا و بدون نقل‌قول برای کاربران ارسال می‌شود."
            )
            try:
                bot.edit_message_text(text_confirm, call.message.chat.id, call.message.message_id, reply_markup=markup, parse_mode="Markdown")
            except Exception:
                safe_send_message(call.message.chat.id, text_confirm, reply_markup=markup)
        else:
            # ارسال پیش‌نمایش به خود ادمین
            try:
                bot.copy_message(
                    chat_id=call.message.chat.id,
                    from_chat_id=chat_id,
                    message_id=msg_id,
                    reply_markup=reply_markup
                )
            except Exception as ep:
                print(f"[broadcast_preview] error: {ep}")

            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🚀 تایید نهایی و شروع ارسال همگانی", callback_data="do_broadcast_with_btn"),
                types.InlineKeyboardButton("🔄 تغییر دکمه شیشه‌ای", callback_data="bc_change_btn"),
                types.InlineKeyboardButton("❌ انصراف و لغو", callback_data="cancel_broadcast")
            )
            confirm_card = (
                f"👆 *پیش‌نمایش پیام با دکمه شیشه‌ای در بالا ارسال شد.*\n\n"
                f"📋 *مشخصات ارسال:*\n"
                f"🔘 دکمه انتخابی: *{btn_title}*\n"
                f"👥 کل مخاطبان هدف: *{tot_targets} نفر (۱۰۰٪ کل اعضا)*\n\n"
                f"آیا این پیام جهت ارسال همگانی مورد تایید شماست؟"
            )
            safe_send_message(call.message.chat.id, confirm_card, reply_markup=markup)
        safe_answer_callback(call.id)

    elif data == "bc_change_btn":
        if not is_admin(uid):
            return
        db_now = load_db()
        tot_targets = len(get_all_broadcast_targets(db_now))
        prompt_txt = (
            f"🔘 *انتخاب دکمه شیشه‌ای زیر پیام:*\n"
            f"👥 تعداد کل مخاطبان هدف: *{tot_targets} نفر*\n\n"
            f"لطفاً گزینه‌ی مورد نظر خود را انتخاب فرمایید: 👇"
        )
        try:
            bot.edit_message_text(prompt_txt, call.message.chat.id, call.message.message_id, reply_markup=broadcast_button_options_keyboard(), parse_mode="Markdown")
        except Exception:
            safe_send_message(call.message.chat.id, prompt_txt, reply_markup=broadcast_button_options_keyboard())
        safe_answer_callback(call.id)

    elif data == "do_broadcast_with_btn":
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!")
            return
        adm_state = get_admin_state(uid)
        chat_id = adm_state.get("chat_id")
        msg_id = adm_state.get("msg_id")
        btn_choice = adm_state.get("button_choice", "none")
        if not chat_id or not msg_id:
            bot.answer_callback_query(call.id, "پیام برای ارسال یافت نشد یا منقضی شده است.", show_alert=True)
            return
        clear_admin_state(uid)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.answer_callback_query(call.id, "ارسال همگانی آغاز شد...")
        threading.Thread(
            target=_run_broadcast_thread,
            args=(chat_id, msg_id, False, btn_choice),
            daemon=True
        ).start()

    elif data in ("do_fwd_all", "do_copy_all"):
        if not is_admin(uid):
            bot.answer_callback_query(call.id, "دسترسی غیرمجاز!")
            return
        adm_state = get_admin_state(uid)
        chat_id = adm_state.get("chat_id")
        msg_id = adm_state.get("msg_id")
        if not chat_id or not msg_id:
            bot.answer_callback_query(call.id, "پیام برای ارسال یافت نشد یا منقضی شده است.", show_alert=True)
            return
        is_fwd = (data == "do_fwd_all")
        clear_admin_state(uid)
        try:
            bot.delete_message(call.message.chat.id, call.message.message_id)
        except Exception:
            pass
        bot.answer_callback_query(call.id, "ارسال همگانی آغاز شد...")
        threading.Thread(
            target=_run_broadcast_thread,
            args=(chat_id, msg_id, is_fwd, "none"),
            daemon=True
        ).start()

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

    active_card, did_rotate, next_card = record_card_deposit_and_rotate(db)

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
        "card_number": active_card,
        "created_at": int(time.time()),
        "caption": caption_text
    }
    clear_user_state(uid)
    save_db(db, immediate_sync=True)

    tronado_auth = check_user_tronado_authenticity(uid, plan_code, caption_text)
    tronado_note = f"\n\n{tronado_auth['summary']}" if tronado_auth.get("summary") else ""

    admin_markup = types.InlineKeyboardMarkup(row_width=2)
    b_approve = types.InlineKeyboardButton("✅ تایید پرداخت و صدور لایسنس", callback_data=f"appr_{order_id}")
    b_reject = types.InlineKeyboardButton("❌ رد پرداخت", callback_data=f"rej_{order_id}")
    b_msg = types.InlineKeyboardButton("✉️ ارسال پیام به کاربر", callback_data=f"reply_user_{uid}")
    admin_markup.add(b_approve, b_reject)
    admin_markup.add(b_msg)

    user_caption_note = f"\n💬 متن همراه فیش: {escape_md(caption_text)}" if caption_text else ""

    admin_caption = (
        f"🔔 *سفارش جدید — رسید پرداخت!*\n\n"
        f"🏷️ شماره سفارش: `{order_id}`\n"
        f"👤 خریدار: {escape_md(first_name)} (@{escape_md(username)})\n"
        f"🆔 آیدی عددی: `{uid}`\n"
        f"📦 پلن انتخابی: *{escape_md(info['name'])}*\n"
        f"💰 مبلغ فاکتور: *{info['price']}*\n"
        f"💳 شماره کارت مقصد: `{active_card}`\n"
        f"⏰ ساعت: {time.strftime('%H:%M:%S', time.localtime())}"
        f"{user_caption_note}"
        f"{tronado_note}"
    )

    # 1. Forward original receipt directly to all admins
    try:
        if hasattr(message, 'chat') and hasattr(message, 'message_id'):
            forward_to_admins(message.chat.id, message.message_id)
    except Exception as ef:
        print(f"[process_receipt_submission] Forward failed: {ef}")

    # 2. Send structured card with buttons to all admins
    sent_card = None
    if content_type == "photo":
        sent_card = notify_admins_photo(file_id, caption=admin_caption, reply_markup=admin_markup)
    else:
        sent_card = notify_admins_document(file_id, caption=admin_caption, reply_markup=admin_markup)

    # Fallback to text message with buttons if photo/doc card failed
    if not sent_card:
        notify_admins_message(admin_caption, reply_markup=admin_markup)

    if did_rotate:
        rotate_msg = (
            f"🔄 *تغییر خودکار شماره کارت واریز*\n\n"
            f"شماره کارت قبلی (`{active_card}`) به سقف {CARD_ROTATION_THRESHOLD} واریز رسید.\n"
            f"💳 شماره کارت فعال جدید برای سفارشات بعدی:\n`{next_card}`"
        )
        notify_admins_message(rotate_msg)

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
@bot.message_handler(content_types=["photo", "document", "voice", "audio", "video", "animation", "sticker", "video_note"])
def handle_photos_and_docs(message):
    track_user(message.from_user)
    uid = message.from_user.id

    in_maint, maint_msg = is_maintenance_mode()
    if in_maint and not is_admin(uid):
        safe_reply_to(message, maint_msg)
        return

    # بررسی آیا ادمین در حال ارسال رسانه برای پیام همگانی است
    if is_admin(uid):
        adm_state = get_admin_state(uid)
        if adm_state.get("state") == "waiting_broadcast_msg":
            set_admin_state({
                "state": "select_broadcast_button",
                "chat_id": message.chat.id,
                "msg_id": message.message_id,
                "time": int(time.time())
            }, admin_id=uid)
            db_now = load_db()
            tot_targets = len(get_all_broadcast_targets(db_now))
            safe_reply_to(
                message,
                f"📢 *رسانه / پست شما جهت ارسال همگانی دریافت شد.*\n\n"
                f"👥 تعداد کل مخاطبان هدف: *{tot_targets} نفر (۱۰۰٪ کل اعضا)*\n\n"
                f"🔘 *انتخاب دکمه شیشه‌ای زیر پیام:*\n"
                f"آیا مایلید دکمه شیشه‌ای (دکمه‌های پلن/خرید) در زیر این پیام قرار گیرد؟\n"
                f"لطفاً گزینه‌ی مورد نظر خود را انتخاب فرمایید: 👇",
                reply_markup=broadcast_button_options_keyboard()
            )
            return

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
    elif message.content_type == "animation":
        file_id = message.animation.file_id
    elif message.content_type == "sticker":
        file_id = message.sticker.file_id
    elif message.content_type == "video_note":
        file_id = message.video_note.file_id

    caption = message.caption or ""

    # بررسی آیا ادمین در حال ارسال رسانه برای پاسخ به تیکت کاربر است
    if is_admin(uid):
        adm_state = get_admin_state(uid)
        target_uid = None
        if adm_state.get("state") == "replying_to_user":
            target_uid = int(adm_state["target_uid"])
            clear_admin_state(uid)
        elif message.reply_to_message:
            rep_text = message.reply_to_message.text or message.reply_to_message.caption or ""
            match = re.search(r"(?:🆔\s*آیدی عددی|آیدی عددی|شناسه کاربر|User ID)\s*:\s*`?(\d+)`?", rep_text)
            if match:
                target_uid = int(match.group(1))

        if target_uid:
            deliver_admin_message_to_user(uid, target_uid, message, message)
            return

    u_state = get_user_state(uid)
    state_type = u_state.get("state")

    # الف) ارسال فیش پرداختی در مرحله خرید
    if state_type == "awaiting_receipt":
        plan_code = u_state.get("plan_code", "1M")
        process_receipt_submission(message, uid, plan_code, file_id, message.content_type, caption)
        return

    # ب) ارسال عکس/فایل/ویس در تیکت پشتیبانی
    elif state_type == "waiting_support_msg":
        clear_user_state(uid)

        if not is_admin(uid):
            is_open, _ = is_support_working_hours()
            if not is_open:
                safe_send_message(message.chat.id, SUPPORT_CLOSED_MESSAGE)
                return

        f_name = message.from_user.first_name or "کاربر"
        u_name = message.from_user.username or "ندارد"

        # Determine reply context
        quote_section = ""
        if message.reply_to_message:
            rep = message.reply_to_message
            rep_text = rep.text or rep.caption or "[فایل / تصویر]"
            quote_section = f"↩️ *در پاسخ به پیام:*\n«_{escape_md(rep_text[:300])}_»\n\n"
        else:
            db = load_db()
            last_reply = db.get("users", {}).get(str(uid), {}).get("last_admin_reply")
            if last_reply and (time.time() - last_reply.get("time", 0) < 172800):
                prev_text = last_reply.get("text", "")
                quote_section = f"💬 *در ادامه پاسخ قبلی پشتیبانی:*\n«_{escape_md(prev_text[:300])}_»\n\n"

        admin_caption = (
            f"📩 *پیام پشتیبانی جدید ({message.content_type}):*\n\n"
            f"👤 کاربر: {escape_md(f_name)} (@{escape_md(u_name)})\n"
            f"🆔 آیدی عددی: `{uid}`\n"
            f"⏰ ساعت: {time.strftime('%H:%M:%S', time.localtime())}\n\n"
            f"{quote_section}"
            f"💬 توضیح: {escape_md(caption) if caption else 'بدون متن'}"
        )
        markup = types.InlineKeyboardMarkup()
        markup.add(types.InlineKeyboardButton("✍️ پاسخ دادن به کاربر", callback_data=f"reply_user_{uid}"))

        if message.content_type == "photo":
            notify_admins_photo(file_id, caption=admin_caption, reply_markup=markup)
        elif message.content_type == "voice":
            for aid in ADMIN_IDS:
                try:
                    bot.send_voice(aid, file_id, caption=admin_caption, reply_markup=markup, parse_mode="Markdown")
                except Exception:
                    bot.send_voice(aid, file_id, caption=caption or "ویس پشتیبانی", reply_markup=markup)
        elif message.content_type == "video":
            for aid in ADMIN_IDS:
                try:
                    bot.send_video(aid, file_id, caption=admin_caption, reply_markup=markup, parse_mode="Markdown")
                except Exception:
                    bot.send_video(aid, file_id, caption=caption or "ویدیو پشتیبانی", reply_markup=markup)
        else:
            notify_admins_document(file_id, caption=admin_caption, reply_markup=markup)

        safe_reply_to(
            message,
            "✅ *پیام / فایل شما برای پشتیبانی ارسال شد.*\nبه زودی پاسخ مدیریت در همین چت برای شما فرستاده خواهد شد."
        )
        return

    # ج) اگر کاربر تصویری فرستاده ولی در هیچ مرحله‌ای نبوده (تصویر مستقیم فرستاده)
    else:
        text_prompt = (
            "📸 *تصویر / فایل ارسالی شما دریافت شد.*\n\n"
            "کاربر گرامی؛ جهت ثبت رسمی فیش واریز و صدور خودکار لایسنس، لطفاً از طریق دکمه‌ی زیر اقدام فرمایید "
            "تا ابتدا پلن خریداری‌شده را مشخص کنید و سپس رسید شما مستقیماً برای مدیریت ارسال گردد:"
        )
        markup = types.InlineKeyboardMarkup(row_width=1)
        markup.add(
            types.InlineKeyboardButton("🧾 ارسال رسید پرداخت", callback_data="submit_receipt"),
            types.InlineKeyboardButton("💬 ارتباط با پشتیبانی", callback_data="ticket_new"),
            types.InlineKeyboardButton("❌ بستن", callback_data="cancel_action")
        )
        safe_reply_to(message, text_prompt, reply_markup=markup)

# ---------------------------------------------------------------------------
# General Text Handler (Support, Admin Reply, Licenses, Text Receipts)
# ---------------------------------------------------------------------------
@bot.message_handler(func=lambda m: True)
def handle_general_text(message):
    track_user(message.from_user)
    uid = message.from_user.id
    text = (message.text or "").strip()

    in_maint, maint_msg = is_maintenance_mode()
    if in_maint and not is_admin(uid):
        safe_reply_to(message, maint_msg)
        return

    # بررسی آیا ادمین در حال ارسال متن یا پست برای پیام همگانی است
    if is_admin(uid):
        adm_state = get_admin_state(uid)
        if adm_state.get("state") == "waiting_broadcast_msg":
            menu_buttons_check = [
                "🛒 خرید اشتراک اختصاصی", "👤 حساب کاربری من", "📘 آموزش اتصال دستی",
                "❓ راهنمای فعال‌سازی", "💬 پشتیبانی", "👑 پنل مدیریت ادمین"
            ]
            if text in menu_buttons_check or text in ["❌ انصراف", "انصراف", "/cancel"]:
                clear_admin_state(uid)
                if text not in menu_buttons_check:
                    safe_reply_to(message, "❌ عملیات ارسال همگانی لغو شد.")
                    return
            else:
                set_admin_state({
                    "state": "select_broadcast_button",
                    "chat_id": message.chat.id,
                    "msg_id": message.message_id,
                    "time": int(time.time())
                }, admin_id=uid)
                db_now = load_db()
                tot_targets = len(get_all_broadcast_targets(db_now))
                safe_reply_to(
                    message,
                    f"📢 *پیام شما جهت ارسال همگانی دریافت شد.*\n\n"
                    f"👥 تعداد کل مخاطبان هدف: *{tot_targets} نفر (۱۰۰٪ کل اعضا)*\n\n"
                    f"🔘 *انتخاب دکمه شیشه‌ای زیر پیام:*\n"
                    f"آیا مایلید دکمه شیشه‌ای (دکمه‌های پلن/خرید) در زیر این پیام قرار گیرد؟\n"
                    f"لطفاً گزینه‌ی مورد نظر خود را انتخاب فرمایید: 👇",
                    reply_markup=broadcast_button_options_keyboard()
                )
                return

    # ۱. اگر ادمین در حال پاسخ به کاربر یا ارسال پیام مستقیم است
    if is_admin(uid):
        adm_state = get_admin_state(uid)
        if adm_state.get("state") == "waiting_target_user_for_msg":
            if text in ["❌ انصراف", "انصراف", "/cancel"]:
                clear_admin_state(uid)
                safe_reply_to(message, "❌ عملیات ارسال پیام لغو شد.")
                return
            target_uid = resolve_user_id(text)
            if not target_uid:
                safe_reply_to(message, f"❌ کاربر با مشخصات `{text}` در سیستم یافت نشد.\nلطفاً آیدی عددی را ارسال کنید یا مجدداً بررسی فرمایید:")
                return
            set_admin_state({"state": "replying_to_user", "target_uid": target_uid}, admin_id=uid)
            db_cur = load_db()
            u_info = db_cur.get("users", {}).get(str(target_uid), {})
            f_n = u_info.get("first_name", "کاربر")
            u_n = u_info.get("username", "ندارد")
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("❌ انصراف", callback_data="cancel_admin_reply"))
            safe_reply_to(
                message,
                f"👤 *کاربر انتخاب‌شده:*\n"
                f"• نام: *{escape_md(f_n)}*\n"
                f"• یوزرنیم: @{escape_md(u_n)}\n"
                f"• آیدی عددی: `{target_uid}`\n\n"
                f"✍️ لطفاً هم‌اکنون پیام، تصویر یا فایل مورد نظر خود را ارسال فرمایید تا بلافاصله به کاربر تحویل داده شود:",
                reply_markup=markup
            )
            return

        target_uid = None
        if adm_state.get("state") == "replying_to_user":
            if text in ["❌ انصراف", "انصراف", "/cancel"]:
                clear_admin_state(uid)
                safe_reply_to(message, "❌ عملیات ارسال پیام به کاربر لغو شد.")
                return
            target_uid = int(adm_state["target_uid"])
            clear_admin_state(uid)
            deliver_admin_message_to_user(uid, target_uid, text, message)
            return
        elif message.reply_to_message:
            rep_text = message.reply_to_message.text or message.reply_to_message.caption or ""
            match = re.search(r"(?:🆔\s*آیدی عددی|آیدی عددی|شناسه کاربر|User ID)\s*:\s*`?(\d+)`?", rep_text)
            if match:
                target_uid = int(match.group(1))
                deliver_admin_message_to_user(uid, target_uid, text, message)
                return

    # ۲. اگر کاربر در مرحله ارسال فیش است (فقط عکس و رسید مجاز است، متن رد می‌شود)
    u_state = get_user_state(uid)
    if u_state.get("state") == "awaiting_receipt":
        if text in ["❌ انصراف", "انصراف", "/cancel"]:
            clear_user_state(uid)
            safe_reply_to(message, "❌ عملیات ثبت رسید لغو شد.")
            return
        if text in MAIN_MENU_EXACT_BUTTONS:
            clear_user_state(uid)
            # اجازه به عبور برای اجرای دکمه منو در بخش پایین
        else:
            plan_code = u_state.get("plan_code", "1M")
            info = PLANS_INFO.get(plan_code, {})
            p_name = info.get("name", "انتخاب‌شده")
            markup = types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                types.InlineKeyboardButton("🔙 تغییر پلن انتخابی", callback_data="submit_receipt"),
                types.InlineKeyboardButton("❌ انصراف از ثبت رسید", callback_data="cancel_action")
            )
            safe_reply_to(
                message,
                f"⚠️ *ارسال رسید به صورت متنی مجاز نمی‌باشد!*\n\n"
                f"📦 پلن انتخابی شما: *{escape_md(p_name)}*\n\n"
                f"📸 لطفاً **تنها تصویر (عکس) فیش واریزی یا اسکرین‌شات رسید پرداخت** خود را ارسال فرمایید تا جهت بررسی و صدور لایسنس برای مدیریت ارسال گردد.\n\n"
                f"👇 در صورت تمایل می‌توانید پلن را تغییر دهید یا انصراف دهید:",
                reply_markup=markup
            )
            return

    # ۳. اگر کاربر در حال ارسال پیام متنی به پشتیبانی است
    if u_state.get("state") == "waiting_support_msg":
        if text in ["❌ انصراف", "انصراف", "/cancel"]:
            clear_user_state(uid)
            safe_reply_to(message, "❌ ارسال پیام به پشتیبانی لغو شد.")
            return
        if text in MAIN_MENU_EXACT_BUTTONS:
            clear_user_state(uid)
            # اجازه به عبور برای اجرای دکمه منو در بخش پایین
        else:
            clear_user_state(uid)

            if not is_admin(uid):
                is_open, _ = is_support_working_hours()
                if not is_open:
                    safe_send_message(message.chat.id, SUPPORT_CLOSED_MESSAGE)
                    return

            f_name = message.from_user.first_name or "کاربر"
            u_name = message.from_user.username or "ندارد"

            # Determine reply context
            quote_section = ""
            if message.reply_to_message:
                rep = message.reply_to_message
                rep_text = rep.text or rep.caption or "[فایل / تصویر]"
                quote_section = f"↩️ *در پاسخ به پیام:*\n«_{escape_md(rep_text[:300])}_»\n\n"
            else:
                db = load_db()
                last_reply = db.get("users", {}).get(str(uid), {}).get("last_admin_reply")
                if last_reply and (time.time() - last_reply.get("time", 0) < 172800):  # within 48h
                    prev_text = last_reply.get("text", "")
                    quote_section = f"💬 *در ادامه پاسخ قبلی پشتیبانی:*\n«_{escape_md(prev_text[:300])}_»\n\n"

            admin_ticket_msg = (
                f"📩 *پیام پشتیبانی جدید!*\n\n"
                f"👤 کاربر: {escape_md(f_name)} (@{escape_md(u_name)})\n"
                f"🆔 آیدی عددی: `{uid}`\n"
                f"⏰ زمان: {time.strftime('%Y/%m/%d %H:%M:%S', time.localtime())}\n\n"
                f"{quote_section}"
                f"💬 *متن پیام کاربر:*\n{escape_md(text)}"
            )
            markup = types.InlineKeyboardMarkup()
            markup.add(types.InlineKeyboardButton("✍️ پاسخ دادن به کاربر", callback_data=f"reply_user_{uid}"))

            notify_admins_message(admin_ticket_msg, reply_markup=markup)

            safe_reply_to(
                message,
                "✅ *پیام شما با موفقیت برای پشتیبانی ارسال گردید.*\nبه زودی پاسخ مدیریت در همین ربات برای شما فرستاده خواهد شد."
            )
            return

    # ۴. دکمه‌ها و دستورات منوی اصلی (فقط در صورتی که کاربر در هیچ استیتی نباشد یا روی دکمه کیبورد زده باشد)
    if text in ["🛒 خرید اشتراک اختصاصی", "🛒 خرید اشتراک", "خرید اشتراک", "خرید", "پلن‌ها", "پلن ها", "/buy", "/plans"]:
        clear_user_state(uid)
        btn_buy_plans(message)
        return
    elif text in ["🧾 ارسال رسید پرداخت", "ارسال رسید پرداخت", "ارسال رسید", "ثبت رسید", "رسید", "/receipt", "/send_receipt"]:
        clear_user_state(uid)
        btn_send_receipt(message)
        return
    elif text in ["👤 حساب کاربری من", "حساب کاربری من", "حساب کاربری", "اکانت من", "پروفایل", "/account", "/my_account", "/profile"]:
        clear_user_state(uid)
        btn_my_account(message)
        return
    elif text in ["📘 آموزش اتصال دستی", "آموزش اتصال دستی", "اتصال دستی", "/guide", "/manual"]:
        clear_user_state(uid)
        btn_manual_guide(message)
        return
    elif text in ["❓ راهنمای فعال‌سازی", "راهنمای فعال‌سازی", "راهنما", "فعال‌سازی", "فعالسازی", "/help"]:
        clear_user_state(uid)
        btn_help(message)
        return
    elif text in ["💬 پشتیبانی", "پشتیبانی", "ارتباط با ادمین", "/support"]:
        clear_user_state(uid)
        btn_support(message)
        return
    elif text in ["👑 پنل مدیریت ادمین", "پنل مدیریت ادمین", "پنل مدیریت", "پنل ادمین", "/admin"] and is_admin(uid):
        clear_user_state(uid)
        btn_admin_panel(message)
        return

    # ۵. استعلام دستی لایسنس
    if text.upper().startswith("AZ"):
        res = license_core.verify_license_format(text.upper())
        if res.get("valid"):
            safe_reply_to(
                message,
                f"✓ *استعلام لایسنس:*\n\n"
                f"کد: `{res['key']}`\n"
                f"پلن: *{escape_md(res['plan_name'])}*\n"
                f"سیستم‌عامل: *ویندوز (کامپیوتر)* 💻\n"
                f"وضعیت: *معتبر و دارای امضای دیجیتالی رسمی* 🔐\n\n"
                f"این کد را داخل نرم‌افزار ویندوز وارد نمایید تا فعال شود."
            )
        else:
            safe_reply_to(message, f"❌ {res.get('error', 'کد لایسنس نامعتبر است.')}")
        return
    elif text.upper().startswith("AN"):
        res = license_core.verify_license_format(text.upper())
        if res.get("valid"):
            safe_reply_to(
                message,
                f"✓ *استعلام لایسنس:*\n\n"
                f"کد: `{res['key']}`\n"
                f"پلن: *{escape_md(res['plan_name'])}*\n"
                f"سیستم‌عامل: *اندروید (موبایل)* 📱\n"
                f"وضعیت: *معتبر و دارای امضای دیجیتالی رسمی* 🔐\n\n"
                f"این کد را داخل اپلیکیشن اندروید وارد نمایید تا فعال شود."
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
    print(f" Tronado Gateway: {'ENABLED' if TRONADO_ENABLED else 'DISABLED'}")
    if TRONADO_ENABLED:
        print(f" Tronado Wallet: {TRONADO_WALLET}")
        print(f" Tronado Callback: {TRONADO_CALLBACK_URL}")
    try:
        stats = get_inventory_stats()
        avail_cnt = stats.get("_total_available", 0)
        sold_cnt = stats.get("_total_sold", 0)
        print(f" Available Keys: {avail_cnt} | Sold: {sold_cnt}")
    except Exception as e:
        print(f" Inventory stats warning: {e}")
    print(f" Shift Duration: {MAX_RUN_SECONDS // 60} minutes")
    print("==================================================")

    # Startup reconciliation: backfill all past orders/issued keys into user accounts
    try:
        startup_db = load_db()
        rec_count = reconcile_all_user_purchases(startup_db)
        if rec_count > 0:
            print(f"[✓] Reconciled {rec_count} past purchases into user accounts.")
            save_db(startup_db, immediate_sync=True)
    except Exception as e:
        print(f"[!] Startup reconciliation warning: {e}")

    w_thread = threading.Thread(target=shift_watchdog, daemon=True)
    w_thread.start()

    s_thread = threading.Thread(target=periodic_sync_worker, daemon=True)
    s_thread.start()

    if TRONADO_ENABLED:
        try:
            start_tronado_webhook_server()
            tp_thread = threading.Thread(target=tronado_poller_worker, daemon=True)
            tp_thread.start()
            print("[✓] Tronado background poller started.")
        except Exception as e:
            print(f"[!] Tronado poller start warning: {e}")

    try:
        bot.remove_webhook()
    except Exception:
        pass

    while True:
        try:
            bot.infinity_polling(timeout=10, long_polling_timeout=5, skip_pending=False)
            break
        except Exception as e:
            print(f"[!] Polling exception: {e}. Retrying in 5 seconds...")
            time.sleep(5)

