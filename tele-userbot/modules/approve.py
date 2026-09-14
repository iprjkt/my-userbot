"""
modules/approve.py
Command .approve / .disapprove - Whitelist atau hapus whitelist PM (Reply, username, ID, atau langsung di PM).
"""

from helpers.db import (
    whitelist_pm, spam_tracker, TEMP_MUTE,
    DB_WHITE, DB_SPAM, save_db
)


async def handle(event, client, txt, t_l):
    """Command .approve dan .disapprove. Return True kalau ditangani."""
    is_approve = t_l == ".approve" or t_l.startswith(".approve ")
    is_disapprove = t_l in [".disapprove", ".unapprove"] or t_l.startswith((".disapprove ", ".unapprove "))

    if not (is_approve or is_disapprove):
        return False

    me = await client.get_me()
    tid = None
    target_name = None

    # 1. Cek dari reply pesan
    if event.is_reply:
        try:
            rep = await event.get_reply_message()
            if rep and rep.sender_id:
                tid = rep.sender_id
                target_name = getattr(rep.sender, 'first_name', str(tid))
        except Exception:
            pass

    # 2. Cek dari argumen teks (ID angka atau @username)
    if not tid:
        parts = txt.split(None, 1)
        if len(parts) > 1:
            arg = parts[1].strip()
            if arg.lstrip("-").isdigit():
                tid = int(arg)
            else:
                try:
                    user_entity = await client.get_entity(arg)
                    tid = user_entity.id
                    target_name = getattr(user_entity, 'first_name', str(tid))
                except Exception as e:
                    await event.edit(f"❌ User `{arg}` tidak ditemukan: `{e}`")
                    return True

    # 3. Cek jika command dikirim di PM (chat pribadi langsung)
    if not tid and event.is_private:
        tid = event.chat_id

    # Jika target masih tidak ditemukan
    if not tid:
        cmd = ".approve" if is_approve else ".disapprove"
        await event.edit(
            f"❌ **Format salah!**\n"
            f"Gunakan `{cmd}` dengan cara:\n"
            f"• Reply chat user\n"
            f"• Ketik `{cmd} <ID/username>`\n"
            f"• Atau ketik `{cmd}` langsung di PM user."
        )
        return True

    tid = int(tid)

    if tid == me.id:
        await event.edit("❌ Tidak perlu memproses akun sendiri.")
        return True

    display_target = f"`{tid}`" if not target_name else f"**{target_name}** (`{tid}`)"

    if is_approve:
        if tid in whitelist_pm:
            await event.edit(f"ℹ️ User {display_target} sudah ada di Whitelist PM.")
            return True

        whitelist_pm.add(tid)
        save_db(DB_WHITE, whitelist_pm)

        # Reset spam tracker & TEMP_MUTE
        tid_s = str(tid)
        if tid_s in spam_tracker or tid in spam_tracker:
            spam_tracker.pop(tid_s, None)
            spam_tracker.pop(tid, None)
            save_db(DB_SPAM, spam_tracker)

        TEMP_MUTE.pop(tid, None)
        TEMP_MUTE.pop(tid_s, None)

        await event.edit(f"✅ User {display_target} berhasil di-Whitelist PM!")
    else:
        # Disapprove / unapprove
        if tid not in whitelist_pm:
            await event.edit(f"ℹ️ User {display_target} tidak ada di Whitelist PM.")
            return True

        whitelist_pm.discard(tid)
        save_db(DB_WHITE, whitelist_pm)
        await event.edit(f"🗑️ User {display_target} berhasil dihapus dari Whitelist PM!")

    return True
