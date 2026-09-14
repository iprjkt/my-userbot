"""
main.py
Entry point Akasha Userbot. Cuma loader: setup client Telethon,
daftar handler incoming/outgoing, dan dispatch ke masing-masing module.
"""

import warnings
from telethon import TelegramClient, events

from helpers.db import api_id, api_hash

from modules import admin, afk, ascii as ascii_mod, dumper, info, kang, approve

warnings.filterwarnings("ignore", category=DeprecationWarning)

client = TelegramClient('sesi_userbot', api_id, api_hash)

# Urutan module dicoba untuk command outgoing (diawali titik).
# Setiap handle() return True kalau command sudah match & ditangani -> stop di situ.
OUTGOING_MODULES = [afk, info, dumper, ascii_mod, approve, admin, kang]


@client.on(events.NewMessage(incoming=True))
async def handler_incoming(event):
    # Cek status AFK & auto-reply PM/mention terlebih dahulu
    await afk.handle_incoming(event, client)


@client.on(events.NewMessage(outgoing=True))
async def handler_outgoing(event):
    txt = event.raw_text
    t_l = txt.lower()

    # Cek apakah owner baru balik dari AFK
    await afk.handle_outgoing_return(event, client)

    # Dispatch ke module yang sesuai berdasarkan command
    for module in OUTGOING_MODULES:
        handled = await module.handle(event, client, txt, t_l)
        if handled:
            break


if __name__ == "__main__":
    print("------------------------------------------------")
    print("------ AKASHA USERBOT IS READY TO USE SAR ------")
    print("------------------------------------------------")
    client.start()
    client.run_until_disconnected()
