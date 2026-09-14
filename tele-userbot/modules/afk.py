"""
modules/afk.py
Mode AFK: command .afk & .unafk (outgoing) & auto-reply otomatis untuk PM/mention (incoming).
"""

import time
from telethon import functions

from helpers.db import (
    afk_data, whitelist_pm, spam_tracker, TEMP_MUTE,
    DB_AFK, DB_SPAM, save_db
)
from helpers.sys_info import get_afk_time

# Cache timestamp balasan AFK terakhir agar tidak spam balasan berulang kali
# Format: {target_id: timestamp}
AFK_REPLIED = {}
AFK_COOLDOWN = 60  # Cooldown balasan dalam detik


async def handle_incoming(event, client):
    """Dipanggil dari handler_incoming di main.py untuk cek status AFK & auto-reply.
    Return True kalau event sudah ditangani (supaya main.py tidak lanjut proses lain)."""

    if not event.sender_id or event.action:
        return False

    me = await client.get_me()
    sid = int(event.sender_id)
    sid_s = str(sid)
    mid_s = str(me.id)

    # Abaikan pesan dari diri sendiri atau service account resmi Telegram
    if sid in (me.id, 777000, 42777):
        return False

    # Abaikan jika pengirim adalah bot
    try:
        sender = await event.get_sender()
        if getattr(sender, 'bot', False):
            return False
    except Exception:
        pass

    now = time.time()
    is_white = (sid in whitelist_pm)
    is_muted = (sid in TEMP_MUTE and now < TEMP_MUTE[sid])

    # ── JIKA OWNER SEDANG AFK ─────────────────────────────────────────
    if mid_s in afk_data:
        reason = afk_data[mid_s].get('reason', 'KAMNTB')
        since_time = afk_data[mid_s].get('since', now)
        afk_duration = get_afk_time(since_time)

        if event.is_private:
            if is_white:
                # Whitelisted: Berikan info AFK dengan cooldown agar tidak spam
                if now - AFK_REPLIED.get(sid, 0) > AFK_COOLDOWN:
                    AFK_REPLIED[sid] = now
                    await event.reply(
                        f"💤 **Bentar yaa lagi AFK alasan : {reason}**\n"
                        f"⏳ `(Sejak {afk_duration} yang lalu)`"
                    )
                return True
            else:
                # Bukan whitelisted, tetapi sedang di-temp mute (owner baru saja chat)
                if is_muted:
                    if now - AFK_REPLIED.get(sid, 0) > AFK_COOLDOWN:
                        AFK_REPLIED[sid] = now
                        await event.reply(
                            f"💤 **Bentar yaa lagi AFK alasan : {reason}**\n"
                            f"⏳ `(Sejak {afk_duration} yang lalu)`"
                        )
                    return True

                # PM Security / Spam tracker
                c = spam_tracker.get(sid_s, 0) + 1
                spam_tracker[sid_s] = c
                save_db(DB_SPAM, spam_tracker)

                if c >= 5:
                    await event.reply("🚫 **Limit chat PM tercapai. Lo diblock.**")
                    await client(functions.contacts.BlockRequest(id=sid))
                    return True

                if now - AFK_REPLIED.get(sid, 0) > 10:
                    AFK_REPLIED[sid] = now
                    await event.reply(
                        f"🙏 **PM belum di-approve, jangan spam atau di blok tunggu di bales.**\n"
                        f"⏳ **AFK: {reason}** `(Sejak {afk_duration} yang lalu)` **({c}/5)**"
                    )
                return True
        else:
            # Di Grup: Cek mention atau reply ke pesan owner
            is_reply_to_me = False
            if not event.mentioned and event.is_reply:
                try:
                    rep_msg = await event.get_reply_message()
                    if rep_msg and rep_msg.sender_id == me.id:
                        is_reply_to_me = True
                except Exception:
                    pass

            if event.mentioned or is_reply_to_me:
                # Cooldown per grup agar tidak spamming grup
                grp_key = f"grp_{event.chat_id}"
                if now - AFK_REPLIED.get(grp_key, 0) > AFK_COOLDOWN:
                    AFK_REPLIED[grp_key] = now
                    await event.reply(
                        f"💤 **Bentar yaa lagi AFK alasan : {reason}**\n"
                        f"⏳ `(Sejak {afk_duration} yang lalu)`"
                    )
                return True

    # ── JIKA OWNER TIDAK AFK (PM SECURITY BIASA) ─────────────────────
    elif event.is_private and not is_white:
        # Jika owner baru saja chat dengan user ini (temp mute aktif), jangan hitung spam / block
        if is_muted:
            return False

        c = spam_tracker.get(sid_s, 0) + 1
        spam_tracker[sid_s] = c
        save_db(DB_SPAM, spam_tracker)

        if c >= 5:
            await event.reply("🚫 **Limit chat PM tercapai. Lo diblock.**")
            await client(functions.contacts.BlockRequest(id=sid))
            return True

        if now - AFK_REPLIED.get(sid, 0) > 10:
            AFK_REPLIED[sid] = now
            await event.reply(
                f"🙏 **PM belum di-approve owner.**\n"
                f"⏳ **Status: {c}/5 chat sebelum block.**"
            )
        return True

    return False


async def handle_outgoing_return(event, client):
    """Dipanggil dari handler_outgoing di main.py: cek apakah owner baru saja
    balik dari AFK (kirim pesan chat normal saat status AFK masih aktif),
    dan auto-mute sementara notifikasi spam-tracker saat owner balas PM manual."""
    txt = event.raw_text
    if not txt:
        return

    now = time.time()

    # Jika owner chat di PM secara normal (bukan command), aktifkan TEMP_MUTE 5 menit
    if event.is_private and not txt.startswith("."):
        TEMP_MUTE[event.chat_id] = now + 300
        cid_s = str(event.chat_id)
        if cid_s in spam_tracker:
            spam_tracker[cid_s] = 0
            save_db(DB_SPAM, spam_tracker)

    # JANGAN cancel AFK kalau pesan ini adalah command bot (diawali titik)
    if txt.startswith("."):
        return

    me = await client.get_me()
    mid_s = str(me.id)

    if mid_s in afk_data:
        since_time = afk_data[mid_s].get('since', now)
        # Cegah pembatalan instan jika owner baru saja mengetik .afk kurang dari 3 detik lalu
        if now - since_time < 3:
            return

        reason = afk_data[mid_s].get('reason', 'KAMNTB')
        afk_duration = get_afk_time(since_time)

        del afk_data[mid_s]
        save_db(DB_AFK, afk_data)
        AFK_REPLIED.clear()

        try:
            await event.respond(
                f"✨ **I'M BACK!**\n"
                f"⏳ `(Kembali setelah {afk_duration} AFK - Alasan: {reason})`"
            )
        except Exception:
            pass


async def handle(event, client, txt, t_l):
    """Command .afk dan .unafk. Return True kalau ditangani."""
    is_afk = t_l == ".afk" or t_l.startswith(".afk ")
    is_unafk = t_l in [".unafk", "/unafk"]

    if not (is_afk or is_unafk):
        return False

    me = await client.get_me()
    mid_s = str(me.id)
    now = time.time()

    if is_unafk:
        if mid_s in afk_data:
            reason = afk_data[mid_s].get('reason', 'KAMNTB')
            since_time = afk_data[mid_s].get('since', now)
            afk_duration = get_afk_time(since_time)

            del afk_data[mid_s]
            save_db(DB_AFK, afk_data)
            AFK_REPLIED.clear()

            await event.edit(
                f"✨ **Mode AFK dinonaktifkan.**\n"
                f"⏳ `(Kembali setelah {afk_duration} AFK - Alasan: {reason})`"
            )
        else:
            await event.edit("ℹ️ Anda sedang tidak dalam mode AFK.")
        return True

    if is_afk:
        parts = txt.split(None, 1)
        reason = parts[1].strip() if len(parts) > 1 else "KAMNTB"

        afk_data[mid_s] = {'reason': reason, 'since': now}
        save_db(DB_AFK, afk_data)
        AFK_REPLIED.clear()

        await event.edit(
            f"💤 **BYE gaiss AFK duluuu**\n"
            f"📝 **Alasan:** `{reason}`"
        )
        return True

    return False
