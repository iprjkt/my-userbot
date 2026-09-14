"""
helpers/db.py
Konfigurasi environment (.env) & fungsi load/save database JSON sederhana.
"""

import os
import json
from dotenv import load_dotenv

load_dotenv()

# ── Kredensial Telegram ──────────────────────────────────────────────
api_id = int(os.getenv('api_id'))
api_hash = os.getenv('api_hash')

# ── Path File ─────────────────────────────────────────────────────────
IMAGE_INFO = "image_banner.png"
DB_AUTH = "authorized_users.json"
DB_AFK = "afk_logs.json"
DB_WHITE = "pm_whitelist.json"
DB_SPAM = "spam_tracker.json"

# ── State Runtime (shared antar modules) ────────────────────────────
TEMP_MUTE = {}


def load_db(p, s=True):
    """Load database dari file JSON.
    s=True  -> return sebagai set (contoh: daftar user ID)
    s=False -> return sebagai dict (contoh: data AFK / spam tracker)
    """
    if os.path.exists(p):
        try:
            with open(p, 'r') as f:
                d = json.load(f)
                return set(map(int, d)) if s else dict(d)
        except Exception:
            pass
    return set() if s else {}


def save_db(p, d):
    """Simpan database ke file JSON."""
    try:
        with open(p, 'w') as f:
            json.dump(list(d) if isinstance(d, set) else d, f)
    except Exception:
        pass


# ── Load Semua Database Saat Import ─────────────────────────────────
auth_u = load_db(DB_AUTH)
whitelist_pm = load_db(DB_WHITE)
afk_data = load_db(DB_AFK, False)
spam_tracker = load_db(DB_SPAM, False)
