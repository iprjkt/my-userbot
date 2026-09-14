"""
helpers/uploader.py
Upload file ke Pixeldrain (utama) dengan fallback ke Gofile, lengkap progress bar live.
"""

import os
import re
import json
import time
import asyncio

from .sys_info import make_progress_bar, run_shell


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
