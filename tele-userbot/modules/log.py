"""
modules/log.py
Command .log / .logs - Cek log sistem & debug userbot.
"""

import os
import subprocess
from collections import deque

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOG_FILE = os.path.join(BASE_DIR, "userbot.log")


async def handle(event, client, txt, t_l):
    """Command .log dan .logs. Return True kalau ditangani."""
    if not (t_l in [".log", ".logs"] or t_l.startswith((".log ", ".logs "))):
        return False

    parts = txt.split(maxsplit=1)
    sub = parts[1].strip().lower() if len(parts) > 1 else ""

    # 1. Option: .log clear
    if sub in ["clear", "clean", "reset"]:
        try:
            with open(LOG_FILE, "w") as f:
                f.truncate(0)
            await event.edit("🗑️ **Log userbot berhasil dibersihkan!**")
        except Exception as e:
            await event.edit(f"❌ Gagal membersihkan file log: `{e}`")
        return True

    # 2. Option: .log file
    if sub == "file":
        if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
            await event.edit("ℹ️ File log belum ada atau masih kosong.")
            return True

        await event.edit("📤 `Mengirim file log...`")
        try:
            await client.send_file(
                event.chat_id,
                LOG_FILE,
                caption="📋 **File Log Akasha Userbot**",
                reply_to=event.reply_to_msg_id
            )
            await event.delete()
        except Exception as e:
            await event.edit(f"❌ Gagal mengirim file log: `{e}`")
        return True

    # 3. Option: .log tmux (capture pane tmux jika dijalankan di tmux)
    if sub.startswith("tmux"):
        try:
            tmux_lines = "50"
            t_parts = sub.split()
            if len(t_parts) > 1 and t_parts[1].isdigit():
                tmux_lines = t_parts[1]
            out = subprocess.check_output(
                ["tmux", "capture-pane", "-pt", "tele", "-S", f"-{tmux_lines}"],
                stderr=subprocess.STDOUT
            ).decode("utf-8", errors="replace").strip()

            if not out:
                await event.edit("ℹ️ Output tmux kosong.")
                return True

            if len(out) > 3500:
                temp_file = os.path.join(BASE_DIR, "tmux_log.txt")
                with open(temp_file, "w", encoding="utf-8") as tf:
                    tf.write(out)
                await client.send_file(
                    event.chat_id,
                    temp_file,
                    caption=f"📋 **Tmux Logs (Last {tmux_lines} lines)**"
                )
                if os.path.exists(temp_file):
                    os.remove(temp_file)
                await event.delete()
            else:
                await event.edit(f"📋 **TMUX LOGS** (`tele`):\n```{out}```")
        except Exception as e:
            await event.edit(f"❌ Gagal membaca output tmux: `{e}`")
        return True

    # 4. Default: .log [jumlah_baris]
    num_lines = 25
    if sub.isdigit():
        num_lines = max(1, min(int(sub), 500))

    if not os.path.exists(LOG_FILE) or os.path.getsize(LOG_FILE) == 0:
        await event.edit("ℹ️ Belum ada log tercatat di file `userbot.log`.\n💡 _Log akan otomatis terisi saat bot berjalan atau terjadi error._")
        return True

    try:
        with open(LOG_FILE, "r", encoding="utf-8", errors="replace") as f:
            last_lines = list(deque(f, maxlen=num_lines))

        if not last_lines:
            await event.edit("ℹ️ File log masih kosong.")
            return True

        content = "".join(last_lines).strip()

        # Jika teks melebihi limit pesan Telegram (~4096 char), kirim sebagai file
        if len(content) > 3500:
            temp_file = os.path.join(BASE_DIR, "recent_logs.txt")
            with open(temp_file, "w", encoding="utf-8") as tf:
                tf.write(content)
            await client.send_file(
                event.chat_id,
                temp_file,
                caption=f"📋 **Userbot Logs** ({len(last_lines)} baris terakhir)"
            )
            if os.path.exists(temp_file):
                os.remove(temp_file)
            await event.delete()
        else:
            await event.edit(f"📋 **USERBOT LOGS** ({len(last_lines)} baris terakhir):\n```{content}```")

    except Exception as e:
        await event.edit(f"❌ Gagal membaca log: `{e}`")

    return True
