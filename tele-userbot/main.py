from telethon import TelegramClient, events, functions, Button
from telethon.tl import types
from dotenv import load_dotenv
import psutil, platform, os, sys, subprocess, asyncio, re, json, requests
import shutil
import warnings
import time
from datetime import datetime
from io import BytesIO
from PIL import Image
from telethon.tl.functions.stickers import AddStickerToSetRequest, CreateStickerSetRequest
from telethon.tl.functions.messages import UploadMediaRequest
from telethon.tl.types import (
    InputStickerSetItem,
    InputStickerSetShortName,
    InputMediaUploadedDocument,
    DocumentAttributeFilename,
    DocumentAttributeSticker,
    InputStickerSetEmpty,
    InputDocument
)

warnings.filterwarnings("ignore", category=DeprecationWarning)

load_dotenv()

api_id = int(os.getenv('api_id'))
api_hash = os.getenv('api_hash')
client = TelegramClient('sesi_userbot', api_id, api_hash)

IMAGE_INFO = "image_banner.png"
DB_AUTH = "authorized_users.json"
DB_AFK = "afk_logs.json"
DB_WHITE = "pm_whitelist.json"
DB_SPAM = "spam_tracker.json"

TEMP_MUTE = {}

import requests

def make_progress_bar(percent, length=10):
    percent = max(0.0, min(100.0, percent))
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percent:.1f}%"

async def run_shell(cmd):
    proc = await asyncio.create_subprocess_shell(
        cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_msg = stderr.decode().strip() or stdout.decode().strip() or f"Exit code {proc.returncode}"
        raise Exception(f"Shell Failed [{cmd.split()[0]}]: {err_msg}")
    return stdout.decode().strip()

async def upload_file_server_with_progress(file_path, event, idx, total_files, f_name):
    f_size_mb = os.path.getsize(file_path) / (1024 * 1024)

    # A. Coba Upload ke Pixeldrain dulu via cURL
    try:
        cmd = f"curl -# -F 'file=@{file_path}' https://pixeldrain.com/api/file"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        last_update = 0
        while True:
            chunk = await proc.stderr.read(128)
            if not chunk:
                break
            text = chunk.decode('utf-8', errors='ignore')
            matches = re.findall(r'(\d+(?:\.\d+)?)%', text)
            if matches:
                pct = float(matches[-1])
                now = time.time()
                if now - last_update >= 3 or pct >= 100:
                    last_update = now
                    p_bar = make_progress_bar(pct)
                    curr_mb = (pct / 100) * f_size_mb
                    try:
                        await event.edit(
                            f"📤 **Uploading ke Server...** ({idx}/{total_files})\n"
                            f"📦 **File:** `{f_name}` ({f_size_mb:.1f} MB)\n"
                            f"`{p_bar}` ({curr_mb:.1f} / {f_size_mb:.1f} MB)"
                        )
                    except Exception:
                        pass

        stdout, _ = await proc.communicate()
        data = json.loads(stdout.decode().strip())
        if data.get("success"):
            return f"https://pixeldrain.com/u/{data['id']}"
    except Exception:
        pass

    # B. Fallback ke Gofile via cURL jika Pixeldrain gagal
    try:
        srv_out = await run_shell("curl -s https://api.gofile.io/servers")
        srv_data = json.loads(srv_out)
        if srv_data.get("status") == "ok" and srv_data["data"].get("servers"):
            server = srv_data["data"]["servers"][0]["name"]
            cmd = f"curl -# -F 'file=@{file_path}' https://{server}.gofile.io/contents/uploadfile"
            proc = await asyncio.create_subprocess_shell(
                cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            last_update = 0
            while True:
                chunk = await proc.stderr.read(128)
                if not chunk:
                    break
                text = chunk.decode('utf-8', errors='ignore')
                matches = re.findall(r'(\d+(?:\.\d+)?)%', text)
                if matches:
                    pct = float(matches[-1])
                    now = time.time()
                    if now - last_update >= 3 or pct >= 100:
                        last_update = now
                        p_bar = make_progress_bar(pct)
                        curr_mb = (pct / 100) * f_size_mb
                        try:
                            await event.edit(
                                f"📤 **Uploading ke Gofile...** ({idx}/{total_files})\n"
                                f"📦 **File:** `{f_name}` ({f_size_mb:.1f} MB)\n"
                                f"`{p_bar}` ({curr_mb:.1f} / {f_size_mb:.1f} MB)"
                            )
                        except Exception:
                            pass

            stdout, _ = await proc.communicate()
            up_data = json.loads(stdout.decode().strip())
            if up_data.get("status") == "ok":
                return up_data["data"]["downloadPage"]
    except Exception:
        pass

    raise Exception("Gagal mengunggah file ke Pixeldrain maupun Gofile.")

def load_db(p, s=True):
    if os.path.exists(p):
        try:
            with open(p, 'r') as f:
                d = json.load(f)
                return set(map(int, d)) if s else dict(d)
        except: pass
    return set() if s else {}

def save_db(p, d):
    try:
        with open(p, 'w') as f:
            json.dump(list(d) if isinstance(d, set) else d, f)
    except: pass

AVAILABLE_ASCII_FONTS = [
    "banner", "standard", "big", "slant", "small",
    "3-d", "block", "dotmatrix", "digital", "lean",
    "mini", "script", "letters"
]

def get_afk_time(since):
    diff = int(time.time() - since)
    if diff < 60: return f"{diff} detik"
    m = diff // 60
    if m < 60: return f"{m} menit"
    h = m // 60; m = m % 60
    if h < 24: return f"{h} jam {m} menit"
    d = h // 24; h = h % 24
    return f"{d} hari {h} jam"

def text_to_ascii_art(text, font="banner"):
    text = text.strip()
    if not text:
        return "❌ Masukkan teks yang ingin diubah."
    try:
        import pyfiglet
        figlet = pyfiglet.Figlet(font=font)
        return figlet.renderText(text)
    except ModuleNotFoundError:
        if font != "banner":
            return ("❌ Modul pyfiglet belum terpasang sehingga font tidak bisa dipilih.\n"
                    "Install dengan `pip install pyfiglet` lalu coba lagi.")
        return "\n".join(ch * 2 for ch in text.upper())
    except Exception as e:
        return f"❌ Gagal membuat ASCII art: {e}"

auth_u = load_db(DB_AUTH); whitelist_pm = load_db(DB_WHITE)
afk_data = load_db(DB_AFK, False); spam_tracker = load_db(DB_SPAM, False)

HELP_TEXT = """
**DAFTAR COMMAND AKASHA SYSTEM** 🚀

**OWNER COMMANDS:**
• `.info` - Cek spek VPS & Detail Storage
• `.speedtest` - Tes kecepatan internet VPS (MB/s)
• `.dump <link> [partisi]` - Extract payload.bin ROM
  `.dump <link> -all`
• `.ascii [font] <teks>` - Ubah teks jadi ASCII art dengan font pilihan
• `.afk <alasan>` - Mode AFK
• `.approve` - Whitelist PM (Reply/ID)
• `.list` - Cek daftar user & izin
• `.restart` - Muat ulang bot
• `.help` - Munculin menu ini
• `.ban` - Ban member
• `.unban` - Unban member
• `.pin` - Pin sebuah pesan
• `.unpin` - Unpin sebuah pesan
"""

async def get_stats_text(user_name):
    n, t = chr(10), chr(96)

    # Memori & Storage
    svmem = psutil.virtual_memory()
    ram_total = svmem.total / (1024**3)
    ram_used = svmem.used / (1024**3)
    ram_free = svmem.available / (1024**3)
    ram_pct = svmem.percent

    disk = psutil.disk_usage('/')
    disk_total = disk.total / (1024**3)
    disk_used = disk.used / (1024**3)
    disk_free = disk.free / (1024**3)
    disk_pct = disk.percent

    # Network Traffic (Inbound & Outbound)
    net_io = psutil.net_io_counters()
    net_tx = net_io.bytes_sent / (1024**3)  # Outbound / Sent (Pakai kuota AWS)
    net_rx = net_io.bytes_recv / (1024**3)  # Inbound / Recv (Gratis)

    kernel_ver = platform.release() or "Unknown Kernel"

    try:
        os_ver = subprocess.check_output("/system/bin/getprop ro.build.version.release 2>/dev/null", shell=True).decode().strip()
        if not os_ver:
            os_ver = subprocess.check_output("grep -m1 'ro.build.version.release=' /system/build.prop 2>/dev/null | cut -d= -f2", shell=True).decode().strip()
        if not os_ver: raise Exception
        distro = f"Android {os_ver}"
    except:
        try:
            ubuntu_name = subprocess.check_output("lsb_release -ds 2>/dev/null", shell=True).decode().strip().replace('"', '')
            raw_kernel = platform.release()
            distro = f"{ubuntu_name}"
            kernel_ver = "-".join(raw_kernel.split("-")[:3])
        except:
            distro = f"{platform.system()} {platform.release()}"

    try:
        p = await asyncio.create_subprocess_shell("uptime -p", stdout=asyncio.subprocess.PIPE)
        out, _ = await p.communicate(); up = out.decode().replace("up ", "").strip()
    except: up = "Unknown"

    return (f"**AKASHA SYSTEM INFO** 🚀{n}{n}"
            f"👤 **User:** {t}{user_name}{t}{n}"
            f"📱 **CPU:** {t}Mediatek Helio {t}{n}      {t} G99-Ultra{t}{n}"
            f"🐧 **OS:** {t}Windows 11 Pro 24H2{t}{n}"
            f"⚙️ **Kernel:** {t}{kernel_ver}{t}{n}"
            f"⏱️ **Uptime:** {t}{up}{t}{n}{n}"
            f"  • Outbound (TX): {t}{net_tx:.2f} GB{t} *(AWS Limit: 100GB)*{n}"
            f"  • Inbound (RX): {t}{net_rx:.2f} GB{t}{n}{n}"
            f"💾 **RAM Capacity:**{n}"
            f"  • Total: {t}{ram_total:.2f} GB{t}{n}"
            f"  • Used: {t}{ram_used:.2f} GB ({ram_pct}%){t}{n}"
            f"  • Free: {t}{ram_free:.2f} GB{t}{n}{n}"
            f"🗄️ **Disk Storage:**{n}"
            f"  • Total: {t}{disk_total:.2f} GB{t}{n}"
            f"  • Used: {t}{disk_used:.2f} GB ({disk_pct}%){t}{n}"
            f"  • Free: {t}{disk_free:.2f} GB{t}")

@client.on(events.NewMessage(incoming=True))
async def handler_incoming(event):
    if not event.sender_id: return
    me = await client.get_me(); sid = int(event.sender_id); sid_s = str(sid); mid_s = str(me.id)
    txt = event.raw_text; t_l = txt.lower()

    is_white = (sid in whitelist_pm)
    is_muted = sid in TEMP_MUTE and time.time() < TEMP_MUTE[sid]

    if mid_s in afk_data and not (sid == me.id):
        reason = afk_data[mid_s].get('reason', 'KAMNTB')
        since_time = afk_data[mid_s].get('since', time.time())
        afk_duration = get_afk_time(since_time)

        if event.is_private:
            if is_white:
                return await event.reply(f"💤 **Bentar yaa lagi AFK alasan : {reason}**\n⏳ `(Sejak {afk_duration} yang lalu)`")
            else:
                c = spam_tracker.get(sid_s, 0) + 1; spam_tracker[sid_s] = c; save_db(DB_SPAM, spam_tracker)
                if c >= 5:
                    await event.reply("🚫 **Limit chat PM tercapai. Lo diblock.**")
                    return await client(functions.contacts.BlockRequest(id=sid))
                if not is_muted:
                    return await event.reply(f"🙏 **PM belum di-approve, jangan spam atau di blok tunggu di bales.**\n⏳ **AFK: {reason}** `(Sejak {afk_duration} yang lalu)` **({c}/5)**")
        else:
            is_reply_to_me = False
            if event.is_reply:
                rep_msg = await event.get_reply_message()
                if rep_msg and rep_msg.sender_id == me.id: is_reply_to_me = True
            if event.mentioned or is_reply_to_me:
                return await event.reply(f"💤**Bentar yaa lagi AFK alasan : {reason}**\n⏳ `(Sejak {afk_duration} yang lalu)`")

    elif event.is_private and not (sid == me.id or is_white):
        c = spam_tracker.get(sid_s, 0) + 1; spam_tracker[sid_s] = c; save_db(DB_SPAM, spam_tracker)
        if c >= 5:
            await event.reply("🚫 **Limit chat PM tercapai. Lo diblock.**")
            return await client(functions.contacts.BlockRequest(id=sid))
        if not is_muted:
            return await event.reply(f"🙏 **PM belum di-approve owner.**\n⏳ **Status: {c}/5 chat sebelum block.**")

@client.on(events.NewMessage(outgoing=True))
async def handler_outgoing(event):
    txt, me = event.raw_text, await client.get_me()
    mid_s, sid_s, t_l = str(me.id), str(me.id), txt.lower()

    if event.is_private and not txt.startswith("."):
        TEMP_MUTE[event.chat_id] = time.time() + 300
        if str(event.chat_id) in spam_tracker:
            spam_tracker[str(event.chat_id)] = 0; save_db(DB_SPAM, spam_tracker)

    if mid_s in afk_data and not t_l.startswith(".afk"):
        reason = afk_data[mid_s].get('reason', 'KAMNTB')
        since_time = afk_data[mid_s].get('since', time.time())
        afk_duration = get_afk_time(since_time)

        del afk_data[mid_s]
        save_db(DB_AFK, afk_data)

        await event.respond(f" **I'M BACK N1GGA!'**\n⏳ `(Kembali setelah {afk_duration} AFK - Alasan: {reason})`")
    if t_l.startswith(".afk"):
        r = txt[5:].strip()
        afk_data[mid_s] = {'reason': r if r else "KAMNTB", 'since': time.time()}
        save_db(DB_AFK, afk_data)
        await event.edit(f"💤 **BYE gaiss AFK duluuu alasan : {afk_data[mid_s]['reason']}**")
    elif t_l == ".ping":
        start = datetime.now(); await event.edit("`Pinging...` ")
        await event.edit(f"**Pong !!**\n🚀 `Latency: {(datetime.now()-start).total_seconds()*1000:.2f} ms` ")
    elif t_l == ".info":
        await event.edit("`Fetching info & profile photo... 🚀` ")
        res = await get_stats_text(me.first_name)

        pp_path = await client.download_profile_photo("me", file="temp_pp.jpg")

        if pp_path and os.path.exists(pp_path):
            await client.send_file(event.chat_id, pp_path, caption=res)
            await event.delete()
            os.remove(pp_path)
        else:
            await event.edit(res)
    elif t_l == ".speedtest":
        await event.edit("`Running Speedtest... 🚀` ")
        try:
            res = subprocess.check_output([sys.executable, "-m", "speedtest", "--simple", "--bytes", "--secure"]).decode("utf-8")
            await event.edit(f"**🚀 Speedtest Results (MB/s):**\n```{res}```")
        except Exception as e: await event.edit(f"❌ Speedtest Error: `{str(e)}`")
    elif t_l.startswith(".dump"):
        urls = re.findall(r'https?://[^\s]+', txt)

        if not urls:
            await event.edit(
                "❌ **Link ROM tidak ditemukan!**\n\n"
                "**Penggunaan:**\n"
                "• `.dump <link_rom>` *(default: boot, vendor_boot, init_boot)*\n"
                "• `.dump <link_rom> boot,vendor_boot` *(custom partisi)*\n"
                "• `.dump <link_rom> -all` *(extract SEMUA partisi)*"
            )
        else:
            url = urls[0]
            txt_without_url = txt.replace(url, "").strip()
            parts = txt_without_url.split()

            is_all = "-all" in txt_without_url.lower()

            if is_all:
                partitions = "ALL PARTITIONS"
                dump_flag = ""
            elif len(parts) > 1 and not parts[1].startswith("-"):
                partitions = parts[1]
                dump_flag = f"-p '{partitions}'"
            else:
                partitions = "boot,vendor_boot,init_boot"
                dump_flag = f"-p '{partitions}'"

            await event.edit(
                f"⏳ **Memproses ekstraksi ROM...**\n"
                f"🎯 **Target Partisi:** `{partitions}`\n\n"
                f"1️⃣ **Downloading ZIP...**"
            )

            task_id = str(event.id)
            task_dir = os.path.join("./dumper_workspace", task_id)
            out_dir = os.path.join(task_dir, "extracted")
            zip_path = os.path.join(task_dir, "rom.zip")
            payload_path = os.path.join(task_dir, "payload.bin")

            os.makedirs(task_dir, exist_ok=True)

            try:
                # 1. Download ROM (Aria2c + Progress Bar)
                dl_cmd = f"aria2c --summary-interval=2 -x 8 -s 8 -d '{task_dir}' -o rom.zip '{url}'"
                proc = await asyncio.create_subprocess_shell(
                    dl_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                last_update = 0
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    line_str = line.decode('utf-8', errors='ignore')
                    match = re.search(r'\((\d+)%\).*?DL:([^\s\]]+)', line_str)
                    if match:
                        pct = float(match.group(1))
                        speed = match.group(2)
                        now = time.time()
                        if now - last_update >= 3:
                            last_update = now
                            p_bar = make_progress_bar(pct)
                            try:
                                await event.edit(
                                    f"⏳ **Memproses ekstraksi ROM...**\n"
                                    f"🎯 **Target Partisi:** `{partitions}`\n\n"
                                    f"1️⃣ **Downloading ZIP...**\n"
                                    f"`{p_bar}` | ⚡ `{speed}/s`"
                                )
                            except Exception:
                                pass
                await proc.wait()
                if proc.returncode != 0:
                    raise Exception("Gagal mengunduh file ROM ZIP.")

                await event.edit(
                    f"⏳ **Memproses ekstraksi...**\n"
                    f"🎯 **Target Partisi:** `{partitions}`\n\n"
                    f"2️⃣ **Extracting payload.bin...**"
                )

                # 2. Extract payload.bin
                unzip_cmd = f"unzip -p '{zip_path}' payload.bin > '{payload_path}'"
                await run_shell(unzip_cmd)

                if os.path.exists(zip_path):
                    os.remove(zip_path)

                if not os.path.exists(payload_path) or os.path.getsize(payload_path) == 0:
                    raise Exception("payload.bin tidak ditemukan di dalam ZIP ROM ini.")

                await event.edit(
                    f"⏳ **Memproses ekstraksi...**\n"
                    f"🎯 **Target Partisi:** `{partitions}`\n\n"
                    f"3️⃣ **Dumping image ({partitions})...**"
                )

                # 3. Dump Partisi (Payload Dumper + Progress Log)
                dump_cmd = f"payload-dumper-go {dump_flag} -o '{out_dir}' '{payload_path}'"
                proc = await asyncio.create_subprocess_shell(
                    dump_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )

                last_update = 0
                while True:
                    line = await proc.stdout.readline()
                    if not line:
                        break
                    text = line.decode('utf-8', errors='ignore').strip()
                    if text:
                        now = time.time()
                        if now - last_update >= 3:
                            last_update = now
                            try:
                                await event.edit(
                                    f"⏳ **Memproses ekstraksi...**\n"
                                    f"🎯 **Target Partisi:** `{partitions}`\n\n"
                                    f"3️⃣ **Dumping image ({partitions})...**\n"
                                    f"⚙️ `{text[:40]}`"
                                )
                            except Exception:
                                pass
                await proc.wait()

                extracted_files = [f for f in os.listdir(out_dir) if f.endswith(".img")] if os.path.exists(out_dir) else []

                if not extracted_files:
                    await event.edit(f"❌ **Gagal:** Tidak ada file .img yang berhasil diekstrak.")
                else:
                    total_files = len(extracted_files)
                    results_text = f"✅ **Ekstraksi Selesai!** ({total_files} file)\n\n"

                    # 4. Upload ke Server (dengan Progress Bar)
                    for idx, f_name in enumerate(extracted_files, 1):
                        f_path = os.path.join(out_dir, f_name)
                        f_size_mb = os.path.getsize(f_path) / (1024 * 1024)

                        download_link = await upload_file_server_with_progress(
                            f_path, event, idx, total_files, f_name
                        )
                        results_text += f"🔹 **{f_name}** ({f_size_mb:.1f} MB)\n🔗 [Download Link]({download_link})\n\n"

                    await event.edit(results_text, link_preview=False)
            except Exception as e:
                await event.edit(f"❌ **Error Dump:**\n```{str(e)}```")
            finally:
                if os.path.exists(task_dir):
                    shutil.rmtree(task_dir)
    elif t_l.startswith(".ascii"):
        raw = txt[len(".ascii"):].strip()
        if not raw:
            await event.edit("❌ Format: `.ascii [font] <teks>`\nContoh: `.ascii slant Hello World`")
        else:
            parts = raw.split(None, 1)
            font = "banner"
            text = raw
            if parts[0].lower() in AVAILABLE_ASCII_FONTS and len(parts) > 1:
                font = parts[0].lower()
                text = parts[1]
            elif parts[0].lower().startswith("font="):
                font = parts[0].split("=", 1)[1]
                text = parts[1] if len(parts) > 1 else ""
            art = text_to_ascii_art(text, font)
            await event.edit(f"```\n{art}\n```")
        try:
            tid = (await event.get_reply_message()).sender_id if event.is_reply else int(txt.split(" ", 1)[1])
            whitelist_pm.add(tid); save_db(DB_WHITE, whitelist_pm)
            if str(tid) in spam_tracker: del spam_tracker[str(tid)]; save_db(DB_SPAM, spam_tracker)
            if tid in TEMP_MUTE: del TEMP_MUTE[tid]
            await event.edit(f"✅ User `{tid}` Whitelisted PM!")
        except: await event.edit("❌ Gagal.")
    elif t_l == ".list":
        msg = "**📜 DAFTAR IZIN AKTIF**\n\n**Whitelist PM:** " + (", ".join([f"`{u}`" for u in whitelist_pm]) or "-")
        await event.edit(msg)
    elif t_l == ".help": await event.edit(HELP_TEXT)
    elif t_l.startswith(".ban"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (txt.split()[1] if len(txt.split()) > 1 else None)
        user = int(target) if str(target).isdigit() else target
        if user:
            try:
                await client.edit_permissions(event.chat_id, user, view_messages=False)
                await event.edit(f"🔨 **Berhasil nge-ban {user}!** Mampus lu dikeluarin.")
            except Exception as e: await event.edit(f"❌ **Gagal nge-ban:** `{e}`")
        else: await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
    elif t_l.startswith(".kick"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (txt.split()[1] if len(txt.split()) > 1 else None)
        user = int(target) if str(target).isdigit() else target
        if user:
            try:
                await client.kick_participant(event.chat_id, user)
                await event.edit(f"🥾 **Berhasil nge-kick {user}!** Hush sana main jauh-jauh.")
            except Exception as e: await event.edit(f"❌ **Gagal nge-kick:** `{e}`")
        else: await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
    elif t_l.startswith(".unban"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (txt.split()[1] if len(txt.split()) > 1 else None)
        user = int(target) if str(target).isdigit() else target
        if user:
            try:
                await client.edit_permissions(event.chat_id, user, view_messages=True)
                await event.edit(f"🕊️ **Berhasil unban {user}!** Bebas dari penjara grup.")
            except Exception as e: await event.edit(f"❌ **Gagal unban:** `{e}`")
        else: await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
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
    elif t_l.startswith(".promote"):
        try:
            parts = event.raw_text.split(maxsplit=1)
            target = None
            custom_title = "Admin"
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
    elif t_l.startswith(".demote"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (txt.split()[1] if len(txt.split()) > 1 else None)
        user = int(target) if str(target).isdigit() else target
        if user:
            try:
                await client.edit_admin(
                    event.chat_id, user,
                    change_info=False, delete_messages=False, ban_users=False,
                    invite_users=False, pin_messages=False, manage_call=False
                )
                await event.edit(f"📉 **Pangkat {user} berhasil dicabut!** Balik jadi kroco.")
            except Exception as e: await event.edit(f"❌ **Gagal demote:** `{e}`")
        else: await event.edit("❌ **Reply chat atau tag username/ID orangnya Ngab!**")
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
    elif t_l.startswith(".add"):
        target = (await event.get_reply_message()).sender_id if event.is_reply else (txt.split()[1] if len(txt.split()) > 1 else None)
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
    elif t_l == ".restart":
        for i in range(3, 0, -1): await event.edit(f"`♻️ Restarting in {i}s...` "); await asyncio.sleep(1)
        await event.edit("`♻️ Restarting now...` "); await client.disconnect()
        subprocess.Popen([sys.executable, sys.argv[0]], start_new_session=True); os._exit(0)
    elif t_l.startswith(".kang"):
        if not event.is_reply:
            return await event.edit("❌ **Reply ke stiker, foto, atau GIF yang mau dicuri Ngab!**")

        reply_msg = await event.get_reply_message()
        if not reply_msg.media:
            return await event.edit("❌ **Pesan yang di-reply tidak mengandung media/gambar/GIF!**")

        await event.edit("⏳ **Mencuri stiker ke pack kamu...**")

        # 1. Tentukan Emoji
        args = txt.split(maxsplit=1)
        sticker_emoji = "🤔"
        if len(args) > 1:
            sticker_emoji = args[1].strip()
        elif reply_msg.sticker:
            for attr in reply_msg.sticker.attributes:
                if hasattr(attr, 'alt') and attr.alt:
                    sticker_emoji = attr.alt
                    break

        try:
            # 2. Download media ke memori
            bio = BytesIO()
            await client.download_media(reply_msg, file=bio)
            bio.seek(0)

            # 3. Process & Resize ke 512x512 PNG
            output_bio = BytesIO()
            output_bio.name = "sticker.png"

            try:
                img = Image.open(bio)
                img.seek(0)
                img.thumbnail((512, 512))
                img.save(output_bio, format="PNG")
                output_bio.seek(0)
            except Exception:
                temp_in = os.path.join("./", f"temp_kang_{event.id}")
                temp_out = os.path.join("./", f"temp_kang_{event.id}.png")

                with open(temp_in, "wb") as f:
                    f.write(bio.getvalue())

                ffmpeg_cmd = f"ffmpeg -y -i '{temp_in}' -vframes 1 -vf 'scale=512:512:force_original_aspect_ratio=decrease' '{temp_out}'"
                proc = await asyncio.create_subprocess_shell(
                    ffmpeg_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc.communicate()

                if os.path.exists(temp_out):
                    img = Image.open(temp_out)
                    img.save(output_bio, format="PNG")
                    output_bio.seek(0)
                    os.remove(temp_out)
                else:
                    raise Exception("Gagal mengonversi GIF/video ke frame PNG stiker.")

                if os.path.exists(temp_in):
                    os.remove(temp_in)

            # 4. Upload sebagai dokumen STIKER RESMI (Ditambah DocumentAttributeSticker)
            uploaded_file = await client.upload_file(output_bio)
            uploaded_media = await client(UploadMediaRequest(
                peer="me",
                media=InputMediaUploadedDocument(
                    file=uploaded_file,
                    mime_type="image/png",
                    attributes=[
                        DocumentAttributeFilename(file_name="sticker.png"),
                        DocumentAttributeSticker(alt=sticker_emoji, stickerset=InputStickerSetEmpty())
                    ]
                )
            ))

            doc = uploaded_media.document
            input_doc = InputDocument(id=doc.id, access_hash=doc.access_hash, file_reference=doc.file_reference)
            sticker_item = InputStickerSetItem(document=input_doc, emoji=sticker_emoji)

            # 5. Tambahkan ke Sticker Pack
            pack_num = 1
            added = False
            username_str = f"_by_{me.username}" if me.username else f"_by_id{me.id}"

            while not added:
                pack_short_name = f"kang_{me.id}_v{pack_num}{username_str}"
                pack_title = f"@{me.username or me.first_name}'s Kang Pack v{pack_num}"

                try:
                    await client(AddStickerToSetRequest(
                        stickerset=InputStickerSetShortName(short_name=pack_short_name),
                        sticker=sticker_item
                    ))
                    added = True
                except Exception as e:
                    err_msg = str(e).lower()
                    if "invalid" in err_msg or "stickerset" in err_msg or "does not exist" in err_msg:
                        await client(CreateStickerSetRequest(
                            user_id=me.id,
                            title=pack_title,
                            short_name=pack_short_name,
                            stickers=[sticker_item]
                        ))
                        added = True
                    elif "too much" in err_msg or "full" in err_msg:
                        pack_num += 1
                    else:
                        raise e

            await event.edit(
                f"✅ **Stiker berhasil dicuri!** {sticker_emoji}\n"
                f"🔗 **Pack:** [Klik Untuk Buka Sticker Pack](https://t.me/addstickers/{pack_short_name})",
                link_preview=False
            )

        except Exception as e:
            await event.edit(f"❌ **Gagal mencuri stiker:**\n```{str(e)}```")

print("------------------------------------------------")
print("------ AKASHA USERBOT IS READY TO USE SAR ------")
print("------------------------------------------------")
client.start(); client.run_until_disconnected()
