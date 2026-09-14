"""
main.py
Entry point Akasha Userbot. Cuma loader: setup client Telethon,
daftar handler incoming/outgoing, dan dispatch ke masing-masing module.
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
import warnings
from telethon import TelegramClient, events

from helpers.db import api_id, api_hash
from modules import admin, afk, ascii as ascii_mod, dumper, info, kang, approve, log as log_mod

warnings.filterwarnings("ignore", category=DeprecationWarning)

# ── Konfigurasi Logging ──────────────────────────────────────────────
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.join(BASE_DIR, "userbot.log")
LOG_FORMAT = "[%(asctime)s] [%(levelname)s] [%(name)s]: %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

file_handler = RotatingFileHandler(
    LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=2, encoding="utf-8"
)
file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

stream_handler = logging.StreamHandler(sys.stdout)
stream_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

logging.basicConfig(
    level=logging.INFO,
    handlers=[file_handler, stream_handler]
)

logger = logging.getLogger("AkashaUserbot")

client = TelegramClient('sesi_userbot', api_id, api_hash)

# Urutan module dicoba untuk command outgoing (diawali titik).
# Setiap handle() return True kalau command sudah match & ditangani -> stop di situ.
OUTGOING_MODULES = [afk, log_mod, info, dumper, ascii_mod, approve, admin, kang]


@client.on(events.NewMessage(incoming=True))
async def handler_incoming(event):
    try:
        # Cek status AFK & auto-reply PM/mention terlebih dahulu
        await afk.handle_incoming(event, client)
    except Exception as e:
        logger.exception("Exception di handler_incoming: %s", e)


@client.on(events.NewMessage(outgoing=True))
async def handler_outgoing(event):
    try:
        txt = event.raw_text
        if not txt:
            return
        t_l = txt.lower()

        # Cek apakah owner baru balik dari AFK
        await afk.handle_outgoing_return(event, client)

        # Dispatch ke module yang sesuai berdasarkan command
        for module in OUTGOING_MODULES:
            try:
                handled = await module.handle(event, client, txt, t_l)
                if handled:
                    break
            except Exception as e:
                logger.exception("Exception di module %s saat menjalankan '%s': %s", module.__name__, txt, e)
                try:
                    await event.edit(
                        f"❌ **Error di module `{module.__name__}`:**\n"
                        f"`{e}`\n\n"
                        f"💡 _Ketik `.log` untuk melihat detail traceback._"
                    )
                except Exception:
                    pass
                break
    except Exception as e:
        logger.exception("Exception di handler_outgoing: %s", e)


if __name__ == "__main__":
    logger.info("Starting Akasha Userbot...")
    print("------------------------------------------------")
    print("------ AKASHA USERBOT IS READY TO USE SAR ------")
    print("------------------------------------------------")
    client.start()
    logger.info("Akasha Userbot is connected and listening to events.")
    client.run_until_disconnected()
