# -*- coding: utf-8 -*-
import os
import sys
import base64
import hashlib
import zipfile
import io
from cryptography.fernet import Fernet

vault_password = os.environ.get("VAULT_PASSWORD")
if not vault_password:
    print("FATAL: VAULT_PASSWORD environment variable is missing!")
    sys.exit(1)

key = base64.urlsafe_b64encode(hashlib.sha256(vault_password.encode('utf-8')).digest())
fernet = Fernet(key)

if not os.path.exists("licenses_vault.enc"):
    print("FATAL: licenses_vault.enc file not found!")
    sys.exit(1)

with open("licenses_vault.enc", "rb") as f:
    encrypted_data = f.read()

try:
    decrypted_zip = fernet.decrypt(encrypted_data)
except Exception as e:
    print(f"FATAL: Decryption failed: {e}")
    sys.exit(1)

os.makedirs("licenses", exist_ok=True)
with zipfile.ZipFile(io.BytesIO(decrypted_zip)) as zf:
    zf.extractall("licenses")

print("[✓] Licenses vault successfully decrypted and loaded into licenses/")
