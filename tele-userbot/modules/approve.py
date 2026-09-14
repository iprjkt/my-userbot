"""
modules/approve.py
Command .approve - Whitelist PM (Reply atau kirim ID user).

Catatan migrasi: di script asli, blok kode approve ini menempel tanpa `elif`
terpisah di bawah handler `.ascii` (jadi selalu tereksekusi setiap kali
`.ascii` dipanggil, alih-alih saat `.approve` dipanggil). Di sini dipisah
jadi command `.approve` yang berdiri sendiri sesuai yang tertulis di HELP_TEXT.
"""

from helpers.db import whitelist_pm, spam_tracker, TEMP_MUTE, DB_WHITE, DB_SPAM, save_db


async def handle(event, client, txt, t_l):
    """Command .approve. Return True kalau ditangani."""
    if not t_l.startswith(".approve"):
        return False

    try:
        tid = (await event.get_reply_message()).sender_id if event.is_reply else int(txt.split(" ", 1)[1])
        whitelist_pm.add(tid)
        save_db(DB_WHITE, whitelist_pm)
        if str(tid) in spam_tracker:
            del spam_tracker[str(tid)]
            save_db(DB_SPAM, spam_tracker)
        if tid in TEMP_MUTE:
            del TEMP_MUTE[tid]
        await event.edit(f"✅ User `{tid}` Whitelisted PM!")
    except Exception:
        await event.edit("❌ Gagal.")

    return True
