"""
modules/afk.py
Mode AFK: command .afk (outgoing) & auto-reply otomatis untuk PM/mention (incoming).
"""

import time
from telethon import functions

from helpers.db import (
    afk_data, whitelist_pm, spam_tracker, TEMP_MUTE,
    DB_AFK, DB_SPAM, save_db
)
from helpers.sys_info import get_afk_time


async def handle_incoming(event, client):
    """Dipanggil dari handler_incoming di main.py untuk cek status AFK & auto-reply.
    Return True kalau event sudah ditangani (supaya main.py tidak lanjut proses lain)."""

    if not event.sender_id:
        return False

    me = await client.get_me()
    sid = int(event.sender_id)
    sid_s = str(sid)
    mid_s = str(me.id)

    is_white = (sid in whitelist_pm)
    is_muted = sid in TEMP_MUTE and time.time() < TEMP_MUTE[sid]

    if mid_s in afk_data and not (sid == me.id):
        reason = afk_data[mid_s].get('reason', 'KAMNTB')
        since_time = afk_data[mid_s].get('since', time.time())
        afk_duration = get_afk_time(since_time)

        if event.is_private:
            if is_white:
                await event.reply(f"💤 **Bentar yaa lagi AFK alasan : {reason}**\n⏳ `(Sejak {afk_duration} yang lalu)`")
                return True
            else:
                c = spam_tracker.get(sid_s, 0) + 1
                spam_tracker[sid_s] = c
                save_db(DB_SPAM, spam_tracker)
                if c >= 5:
                    await event.reply("🚫 **Limit chat PM tercapai. Lo diblock.**")
                    await client(functions.contacts.BlockRequest(id=sid))
                    return True
                if not is_muted:
                    await event.reply(f"🙏 **PM belum di-approve, jangan spam atau di blok tunggu di bales.**\n⏳ **AFK: {reason}** `(Sejak {afk_duration} yang lalu)` **({c}/5)**")
                    return True
        else:
            is_reply_to_me = False
            if event.is_reply:
                rep_msg = await event.get_reply_message()
                if rep_msg and rep_msg.sender_id == me.id:
                    is_reply_to_me = True
            if event.mentioned or is_reply_to_me:
                await event.reply(f"💤**Bentar yaa lagi AFK alasan : {reason}**\n⏳ `(Sejak {afk_duration} yang lalu)`")
                return True

    elif event.is_private and not (sid == me.id or is_white):
        c = spam_tracker.get(sid_s, 0) + 1
        spam_tracker[sid_s] = c
        save_db(DB_SPAM, spam_tracker)
        if c >= 5:
            await event.reply("🚫 **Limit chat PM tercapai. Lo diblock.**")
            await client(functions.contacts.BlockRequest(id=sid))
            return True
        if not is_muted:
            await event.reply(f"🙏 **PM belum di-approve owner.**\n⏳ **Status: {c}/5 chat sebelum block.**")
            return True

    return False


async def handle_outgoing_return(event, client):
    """Dipanggil dari handler_outgoing di main.py: cek apakah owner baru saja
    balik dari AFK (kirim pesan lain selain .afk saat status AFK masih aktif),
    dan auto-mute sementara notifikasi spam-tracker saat owner balas PM manual."""
    me = await client.get_me()
    mid_s = str(me.id)
    txt = event.raw_text
    t_l = txt.lower()

    if event.is_private and not txt.startswith("."):
        TEMP_MUTE[event.chat_id] = time.time() + 300
        if str(event.chat_id) in spam_tracker:
            spam_tracker[str(event.chat_id)] = 0
            save_db(DB_SPAM, spam_tracker)

    if mid_s in afk_data and not t_l.startswith(".afk"):
        reason = afk_data[mid_s].get('reason', 'KAMNTB')
        since_time = afk_data[mid_s].get('since', time.time())
        afk_duration = get_afk_time(since_time)

        del afk_data[mid_s]
        save_db(DB_AFK, afk_data)

        await event.respond(f" **I'M BACK N1GGA!'**\n⏳ `(Kembali setelah {afk_duration} AFK - Alasan: {reason})`")


async def handle(event, client, txt, t_l):
    """Command .afk untuk mengaktifkan mode AFK. Return True kalau ditangani."""
    if t_l.startswith(".afk"):
        me = await client.get_me()
        mid_s = str(me.id)
        r = txt[5:].strip()
        afk_data[mid_s] = {'reason': r if r else "KAMNTB", 'since': time.time()}
        save_db(DB_AFK, afk_data)
        await event.edit(f"💤 **BYE gaiss AFK duluuu alasan : {afk_data[mid_s]['reason']}**")
        return True

    return False
