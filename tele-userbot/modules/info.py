"""
modules/info.py
Command .info, .ping, .speedtest, .help, .list
"""

import os
import sys
import subprocess
from datetime import datetime

from helpers.sys_info import get_stats_text
from helpers.db import whitelist_pm

HELP_TEXT = """
**DAFTAR COMMAND AKASHA SYSTEM** 🚀

**OWNER COMMANDS:**
• `.info` - Cek spek VPS & Detail Storage
• `.speedtest` - Tes kecepatan internet VPS (MB/s)
• `.dump <link> [partisi]` - Extract payload.bin ROM
  `.dump <link> -all`
• `.ascii [font] <teks>` - Ubah teks jadi ASCII art dengan font pilihan
• `.afk <alasan>` - Mode AFK
• `.kang <reply>` - Nyuri sticker
• `.approve` - Whitelist PM (Reply/ID)
• `.restart` - Muat ulang bot
• `.help` - Munculin menu ini
• `.ban` - Ban member
• `.unban` - Unban member
• `.pin` - Pin sebuah pesan
• `.unpin` - Unpin sebuah pesan
"""


async def handle(event, client, txt, t_l):
    """Command info/ping/speedtest/help/list. Return True kalau ditangani."""

    if t_l == ".ping":
        start = datetime.now()
        await event.edit("`Pinging...` ")
        await event.edit(f"**Pong !!**\n🚀 `Latency: {(datetime.now()-start).total_seconds()*1000:.2f} ms` ")
        return True

    elif t_l == ".info":
        await event.edit("`Fetching info & profile photo... 🚀` ")
        me = await client.get_me()
        res = await get_stats_text(me.first_name)

        pp_path = await client.download_profile_photo("me", file="temp_pp.jpg")

        if pp_path and os.path.exists(pp_path):
            await client.send_file(event.chat_id, pp_path, caption=res)
            await event.delete()
            os.remove(pp_path)
        else:
            await event.edit(res)
        return True

    elif t_l == ".speedtest":
        await event.edit("`Running Speedtest... 🚀` ")
        try:
            res = subprocess.check_output(
                [sys.executable, "-m", "speedtest", "--simple", "--bytes", "--secure"]
            ).decode("utf-8")
            await event.edit(f"**🚀 Speedtest Results (MB/s):**\n```{res}```")
        except Exception as e:
            await event.edit(f"❌ Speedtest Error: `{str(e)}`")
        return True

    elif t_l == ".list":
        msg = "**📜 DAFTAR IZIN AKTIF**\n\n**Whitelist PM:** " + (", ".join([f"`{u}`" for u in whitelist_pm]) or "-")
        await event.edit(msg)
        return True

    elif t_l == ".help":
        await event.edit(HELP_TEXT)
        return True

    return False
