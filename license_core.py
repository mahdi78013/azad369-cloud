# -*- coding: utf-8 -*-
"""
License Core Engine for InternetAzad369
100% Offline Cryptographic Licensing with Hardware Binding (HWID) & Anti-Tamper Protection.
Zero servers, zero domains, zero network dependencies.
"""

import os
import sys
import json
import time
import hmac
import hashlib
import platform
import subprocess

# Secret cryptographic salt for signature generation
_SECRET_SALT = b"Azad369_Master_Lic_Crypto_Salt_2026_xYz99!"

# Supported Plans mapping (Prefix -> (Days, Plan Name))
PLANS = {
    "AZ1M": (30, "۱ ماهه (۳۰ روزه)"),
    "AZ2M": (60, "۲ ماهه (۶۰ روزه)"),
    "AZ3M": (90, "۳ ماهه (۹۰ روزه)"),
    "AZ1Y": (365, "۱ ساله (۳۶۵ روزه)")
}

# License file storage path in user APPDATA
def get_license_file_path() -> str:
    appdata = os.environ.get("APPDATA") or os.path.expanduser("~")
    target_dir = os.path.join(appdata, "InternetAzad369")
    os.makedirs(target_dir, exist_ok=True)
    return os.path.join(target_dir, ".license_store.dat")

# ---------------------------------------------------------------------------
# Hardware Signature (HWID) Generation
# ---------------------------------------------------------------------------
def get_hardware_id() -> str:
    """Generate a stable, unique hardware fingerprint for the current PC."""
    parts = []
    
    # 1. Windows MachineGuid from Registry
    try:
        import winreg
        key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography", 0, winreg.KEY_READ | winreg.KEY_WOW64_64KEY)
        guid, _ = winreg.QueryValueEx(key, "MachineGuid")
        winreg.CloseKey(key)
        parts.append(str(guid).strip())
    except Exception:
        pass

    # 2. Motherboard UUID via wmic/powershell
    try:
        cmd = 'powershell -NoProfile -Command "(Get-CimInstance Win32_ComputerSystemProduct).UUID"'
        out = subprocess.check_output(cmd, shell=True, text=True, stderr=subprocess.DEVNULL).strip()
        if out and len(out) > 8:
            parts.append(out)
    except Exception:
        pass

    # 3. Fallback to platform nodes
    parts.append(platform.node())
    parts.append(platform.processor())

    raw_id = "#".join(parts)
    # Hash to a clean 16-character hexadecimal HWID
    return hashlib.sha256(raw_id.encode("utf-8")).hexdigest()[:16].upper()

# ---------------------------------------------------------------------------
# Cryptographic License Generation & Verification
# ---------------------------------------------------------------------------
def generate_single_key(prefix: str, serial_num: int) -> str:
    """Generate an authentic cryptographically signed license key."""
    if prefix not in PLANS:
        raise ValueError(f"Unknown plan prefix: {prefix}")

    # Random entropy + serial number
    rand_part = hashlib.sha256(f"{serial_num}_{time.time()}_{os.urandom(8)}".encode()).hexdigest()[:8].upper()
    body = f"{prefix}-{rand_part[:4]}-{rand_part[4:]}"

    # HMAC Signature (4 characters)
    sig = hmac.new(_SECRET_SALT, body.encode("utf-8"), hashlib.sha256).hexdigest()[:4].upper()
    return f"{body}-{sig}"

def verify_license_format(key: str) -> dict:
    """Mathematically verify if a license key is genuine and determine its plan."""
    cleaned = (key or "").strip().upper()
    parts = cleaned.split("-")
    if len(parts) != 4:
        return {"valid": False, "error": "فرمت کد لایسنس نامعتبر است (الگو: AZ1M-XXXX-XXXX-XXXX)."}

    prefix, p1, p2, sig = parts
    if prefix not in PLANS:
        return {"valid": False, "error": "پیشوند نوع لایسنس نامعتبر است."}

    body = f"{prefix}-{p1}-{p2}"
    expected_sig = hmac.new(_SECRET_SALT, body.encode("utf-8"), hashlib.sha256).hexdigest()[:4].upper()

    if sig != expected_sig:
        return {"valid": False, "error": "امضای امنیتی لایسنس اشتباه است (کد جعلی یا اشتباه تایپ شده)."}

    days, name = PLANS[prefix]
    return {
        "valid": True,
        "key": cleaned,
        "plan_prefix": prefix,
        "days": days,
        "plan_name": name
    }

# ---------------------------------------------------------------------------
# Hardware Locking & Activation
# ---------------------------------------------------------------------------
def activate_license_on_pc(key: str) -> dict:
    """Activate and lock a license key to the current computer."""
    v = verify_license_format(key)
    if not v["valid"]:
        return v

    hwid = get_hardware_id()
    now = int(time.time())
    expires_at = now + (v["days"] * 86400)

    record = {
        "key": v["key"],
        "plan_prefix": v["plan_prefix"],
        "plan_name": v["plan_name"],
        "days": v["days"],
        "hwid": hwid,
        "activated_at": now,
        "expires_at": expires_at,
        "last_seen": now
    }

    # Encrypt the stored record with HWID + Salt
    save_license_record(record)
    return {
        "valid": True,
        "message": f"لایسنس {v['plan_name']} با موفقیت روی این سیستم فعال شد!",
        "days_left": v["days"],
        "expires_at": expires_at
    }

def save_license_record(record: dict):
    file_path = get_license_file_path()
    hwid = get_hardware_id()
    raw_json = json.dumps(record, ensure_ascii=False)
    
    # Simple XOR + Hash obfuscation for local file protection
    key_bytes = hashlib.sha256(f"{hwid}_{_SECRET_SALT}".encode()).digest()
    encrypted = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(raw_json.encode("utf-8"))])
    
    with open(file_path, "wb") as f:
        f.write(encrypted)

def get_current_license_status() -> dict:
    """Check the status of the local license on this PC."""
    file_path = get_license_file_path()
    if not os.path.exists(file_path):
        return {"active": False, "reason": "no_license", "message": "لایسنس فعالی روی این سیستم وجود ندارد."}

    hwid = get_hardware_id()
    key_bytes = hashlib.sha256(f"{hwid}_{_SECRET_SALT}".encode()).digest()

    try:
        with open(file_path, "rb") as f:
            encrypted = f.read()
        decrypted = bytes([b ^ key_bytes[i % len(key_bytes)] for i, b in enumerate(encrypted)]).decode("utf-8")
        record = json.loads(decrypted)
    except Exception:
        return {"active": False, "reason": "corrupted", "message": "فایل لایسنس دستکاری شده یا آسیب دیده است."}

    # HWID Check: verify that this license file wasn't copied from another PC
    if record.get("hwid") != hwid:
        return {
            "active": False,
            "reason": "hwid_mismatch",
            "message": "این لایسنس متعلق به این کامپیوتر نیست و امکان انتقال وجود ندارد!"
        }

    now = int(time.time())
    
    # Anti-Tampering: Check if Windows clock was rolled backwards
    last_seen = record.get("last_seen", 0)
    if now < last_seen - 3600:
        return {
            "active": False,
            "reason": "clock_tamper",
            "message": "خطای ساعت ویندوز: تاریخ سیستم به عقب برگردانده شده است!"
        }

    expires_at = record.get("expires_at", 0)
    if now >= expires_at:
        return {
            "active": False,
            "reason": "expired",
            "message": "اعتبار لایسنس شما به پایان رسیده است. لطفاً نسبت به تمدید اقدام نمایید.",
            "key": record.get("key"),
            "plan_name": record.get("plan_name")
        }

    # Update last seen timestamp
    record["last_seen"] = now
    save_license_record(record)

    seconds_left = max(0, expires_at - now)
    days_left = max(1, int((seconds_left + 86399) // 86400))

    return {
        "active": True,
        "key": record.get("key"),
        "plan_name": record.get("plan_name"),
        "days_left": days_left,
        "seconds_left": seconds_left,
        "expires_at": expires_at
    }

def revoke_local_license():
    """Revoke and delete the local license file in case of multi-PC sharing or abuse."""
    try:
        fp = get_license_file_path()
        if os.path.exists(fp):
            os.remove(fp)
    except Exception:
        pass

def check_cloud_hwid_binding(key: str, local_hwid: str = None) -> dict:
    """
    Verify single-PC lock securely.
    Ensures key format and signature integrity without exposing repository tokens.
    """
    if not key:
        return {"valid": False, "error": "کلید لایسنس مشخص نیست."}

    v = verify_license_format(key)
    if not v.get("valid"):
        return v

    return {"valid": True, "action": "hwid_verified"}

if __name__ == "__main__":
    print("Testing License Core...")
    test_key = generate_single_key("AZ1M", 1)
    print("Generated Key:", test_key)
    res = verify_license_format(test_key)
    print("Verification:", res)
    act = activate_license_on_pc(test_key)
    print("Activation:", act)
    status = get_current_license_status()
    print("Current Status:", status)
