"""
modules/dumper.py
Command .dump <link> [partisi] - Download ROM, extract payload.bin, dump partisi, upload hasil.
"""

import os
import re
import time
import shutil
import asyncio

from helpers.sys_info import make_progress_bar, run_shell
from helpers.uploader import upload_file_server_with_progress


async def handle(event, client, txt, t_l):
    """Command .dump. Return True kalau ditangani."""
    if not t_l.startswith(".dump"):
        return False

    urls = re.findall(r'https?://[^\s]+', txt)

    if not urls:
        await event.edit(
            "❌ **Link ROM tidak ditemukan!**\n\n"
            "**Penggunaan:**\n"
            "• `.dump <link_rom>` *(default: boot, vendor_boot, init_boot)*\n"
            "• `.dump <link_rom> boot,vendor_boot` *(custom partisi)*\n"
            "• `.dump <link_rom> -all` *(extract SEMUA partisi)*"
        )
        return True

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

    return True
