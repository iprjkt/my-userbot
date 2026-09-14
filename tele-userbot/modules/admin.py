"""
modules/admin.py
Command administrasi grup: .ban, .kick, .unban, .promote, .demote, .pin, .unpin, .add, .restart
"""

import os
import sys
import asyncio
import subprocess
from telethon import functions


async def handle(event, client, txt, t_l):
    """Coba tangani command admin. Return True kalau ada command yang match & ditangani."""

    if t_l.startswith(".ban"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (
            txt.split()[1] if len(txt.split()) > 1 else None)
        user = int(target) if str(target).isdigit() else target
        if user:
            try:
                await client.edit_permissions(event.chat_id, user, view_messages=False)
                await event.edit(f"🔨 **Berhasil nge-ban {user}!** Mampus lu dikeluarin.")
            except Exception as e:
                await event.edit(f"❌ **Gagal nge-ban:** `{e}`")
        else:
            await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
        return True

    elif t_l.startswith(".kick"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (
            txt.split()[1] if len(txt.split()) > 1 else None)
        user = int(target) if str(target).isdigit() else target
        if user:
            try:
                await client.kick_participant(event.chat_id, user)
                await event.edit(f"🥾 **Berhasil nge-kick {user}!** Hush sana main jauh-jauh.")
            except Exception as e:
                await event.edit(f"❌ **Gagal nge-kick:** `{e}`")
        else:
            await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
        return True

    elif t_l.startswith(".unban"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (
            txt.split()[1] if len(txt.split()) > 1 else None)
        user = int(target) if str(target).isdigit() else target
        if user:
            try:
                await client.edit_permissions(event.chat_id, user, view_messages=True)
                await event.edit(f"🕊️ **Berhasil unban {user}!** Bebas dari penjara grup.")
            except Exception as e:
                await event.edit(f"❌ **Gagal unban:** `{e}`")
        else:
            await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
        return True

    elif t_l.startswith(".pin"):
        args = event.raw_text.split(" ", 1)
        try:
            if event.is_reply:
                rep = await event.get_reply_message()
                await client.pin_message(event.chat_id, rep.id, notify=True)
                await event.edit("📌 **Pinned!**")
            elif len(args) > 1:
                teks_baru = args[1]
                msg = await event.edit(teks_baru)
                await client.pin_message(event.chat_id, msg.id, notify=True)
            else:
                await event.edit("❌ **Reply pesan yang mau di-pin, atau ketik `.pin <teks>` Ngab!**")
        except Exception as e:
            await event.edit(f"❌ **Gagal nge-pin:** `{e}`")
        return True

    elif t_l.startswith(".promote"):
        try:
            parts = event.raw_text.split(maxsplit=1)
            target = None
            custom_title = "Admin"
            me = await client.get_me()
            if event.is_reply:
                target = (await event.get_reply_message()).sender_id
                if len(parts) > 1:
                    custom_title = parts[1]
            else:
                if len(parts) > 1:
                    sub_parts = parts[1].split(maxsplit=1)
                    target = sub_parts[0]
                    target = int(target) if str(target).lstrip('-').isdigit() else target

                    if len(sub_parts) > 1:
                        custom_title = sub_parts[1]
            if target:
                custom_title = custom_title[:16]

                await client.edit_admin(
                    event.chat_id, target,
                    change_info=True, delete_messages=True, ban_users=True,
                    invite_users=True, pin_messages=True, manage_call=True,
                    title=custom_title
                )
                await event.edit(f"👑 **Berhasil promote!** Target dapet pangkat dengan gelar: `{custom_title}`")
            else:
                await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")

        except Exception as e:
            await event.edit(f"❌ **Gagal promote:** `{e}`")
        return True

    elif t_l.startswith(".demote"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (
            txt.split()[1] if len(txt.split()) > 1 else None)
        user = int(target) if str(target).isdigit() else target
        if user:
            try:
                await client.edit_admin(
                    event.chat_id, user,
                    change_info=False, delete_messages=False, ban_users=False,
                    invite_users=False, pin_messages=False, manage_call=False
                )
                await event.edit(f"📉 **Pangkat {user} berhasil dicabut!** Balik jadi kroco.")
            except Exception as e:
                await event.edit(f"❌ **Gagal demote:** `{e}`")
        else:
            await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
        return True

    elif t_l == ".unpin":
        try:
            if event.is_reply:
                rep = await event.get_reply_message()
                await client.unpin_message(event.chat_id, rep.id)
                await event.edit("📌 **Pesan yang di-reply berhasil di-unpin!** Copot dah tuh.")
            else:
                await client.unpin_message(event.chat_id)
                await event.edit("📌 **Pesan sematan terakhir berhasil di-unpin!**")
        except Exception as e:
            await event.edit(f"❌ **Gagal nge-unpin:** `{e}`")
        return True

    elif t_l.startswith(".add"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (
            txt.split()[1] if len(txt.split()) > 1 else None)
        if target:
            try:
                await event.edit("⏳ `Mencoba menyeret target...`")
                user_ent = await client.get_input_entity(target)
                await client(functions.channels.InviteToChannelRequest(
                    channel=event.chat_id,
                    users=[user_ent]
                ))
                await event.edit(f"➕ **Berhasil nyeret target ke dalem grup!** Welcome Ngab.")
            except Exception as e:
                error_msg = str(e).lower()
                if "privacy" in error_msg or "mutual contact" in error_msg:
                    await event.edit("❌ **Gagal nyeret:** Target masang tameng privasi Ngab! (Cuma mutual kontak yang bisa nge-add).")
                else:
                    try:
                        await client(functions.messages.AddChatUserRequest(
                            chat_id=event.chat_id,
                            user_id=user_ent,
                            fwd_limit=0
                        ))
                        await event.edit(f"➕ **Berhasil nyeret target ke grup basic!**")
                    except Exception as ex:
                        await event.edit(f"❌ **Gagal:** `{ex}`")
        else:
            await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
        return True

    elif t_l == ".restart":
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        main_script = os.path.join(base_dir, "main.py")
        restart_file = os.path.join(base_dir, ".restart_msg.json")

        try:
            import json
            with open(restart_file, "w") as f:
                json.dump({"chat_id": event.chat_id, "msg_id": event.id}, f)
        except Exception:
            pass

        for i in range(2, 0, -1):
            await event.edit(f"`♻️ Restarting in {i}s...` ")
            await asyncio.sleep(1)
        await event.edit("`♻️ Restarting now...` ")

        try:
            await asyncio.wait_for(client.disconnect(), timeout=4)
        except Exception:
            pass

        os.chdir(base_dir)
        os.execv(sys.executable, [sys.executable, main_script] + sys.argv[1:])

    return False

