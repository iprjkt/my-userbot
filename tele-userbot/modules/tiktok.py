"""
modules/tiktok.py
Command .tt / .tiktok - Scraper & Downloader TikTok tanpa watermark (Video, Audio/MP3, Slide Foto).
"""

import os
import re
import time
import shutil
import asyncio
import logging
import requests
from io import BytesIO
from PIL import Image

from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo
from helpers.sys_info import make_progress_bar, format_duration

logger = logging.getLogger("AkashaUserbot.TikTok")

TEMP_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_media")

TIKTOK_REGEX = re.compile(
    r'(https?://(?:(?:www|vt|vm|m|t)\.)?tiktok\.com/[^\s]+|https?://[a-zA-Z0-9.-]+\.tiktok\.com/[^\s]+)',
    re.IGNORECASE
)

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.tikwm.com/"
}


async def fetch_tiktok_data(url: str) -> dict:
    """Ambil data video/audio/slide TikTok dari TikWM API dengan async wrapper."""
    def _req():
        api_url = "https://www.tikwm.com/api/"
        payload = {
            "url": url,
            "count": 12,
            "cursor": 0,
            "web": 1,
            "hd": 1
        }
        res = requests.post(api_url, data=payload, headers=HEADERS, timeout=20)
        return res.json()

    data = await asyncio.to_thread(_req)
    if data.get("code") == 0 and data.get("data"):
        return data["data"]

    # Fallback coba GET query
    def _req_get():
        api_url = f"https://www.tikwm.com/api/?url={url}&hd=1"
        res = requests.get(api_url, headers=HEADERS, timeout=20)
        return res.json()

    data_get = await asyncio.to_thread(_req_get)
    if data_get.get("code") == 0 and data_get.get("data"):
        return data_get["data"]

    msg = data.get("msg") or data_get.get("msg") or "Gagal mengambil data dari TikTok"
    raise Exception(f"TikWM Error: {msg}")


def make_upload_progress(event, prefix="📤 **Mengunggah ke Telegram...**"):
    """Buat callback progress bar saat mengunggah file ke Telegram."""
    last_update = [0]

    async def callback(current, total):
        now = time.time()
        if now - last_update[0] >= 3 or current >= total:
            last_update[0] = now
            pct = (current / total) * 100 if total > 0 else 0
            p_bar = make_progress_bar(pct)
            curr_mb = current / (1024 * 1024)
            tot_mb = total / (1024 * 1024)
            try:
                await event.edit(
                    f"{prefix}\n"
                    f"`{p_bar}` ({curr_mb:.1f} / {tot_mb:.1f} MB)"
                )
            except Exception:
                pass

    return callback


async def handle(event, client, txt, t_l):
    """Command .tt / .tiktok. Return True kalau ditangani."""
    is_tt_cmd = (
        t_l in [".tt", ".tiktok", ".ttmp3"] or
        t_l.startswith((".tt ", ".tiktok ", ".ttmp3 "))
    )
    if not is_tt_cmd:
        return False

    reply_msg = await event.get_reply_message() if event.is_reply else None
    reply_to_id = reply_msg.id if reply_msg else None

    # Cari link di text perintah terlebih dahulu
    urls = TIKTOK_REGEX.findall(txt)

    # Jika tidak ada link di teks perintah, cari di pesan reply
    if not urls and reply_msg and reply_msg.raw_text:
        urls = TIKTOK_REGEX.findall(reply_msg.raw_text)

    # Cek opsi/flag audio
    parts = txt.split()
    cmd_name = parts[0].lower() if parts else ""
    is_audio = cmd_name == ".ttmp3" or any(arg.lower() in ["-a", "--audio", "audio", "mp3", "music"] for arg in parts[1:])

    if not urls:
        await event.edit(
            "❌ **Link TikTok tidak ditemukan!**\n\n"
            "**Penggunaan:**\n"
            "• `.tt <link>` - Download video TikTok (tanpa watermark)\n"
            "• `.tt -a <link>` - Download audio/musik TikTok (.mp3)\n"
            "• `.ttmp3 <link>` - Shortcut download audio TikTok\n"
            "• Reply ke pesan berisi link TikTok dengan `.tt` atau `.tt -a`"
        )
        return True

    target_url = urls[0].strip()

    task_id = f"tt_{event.id}_{int(time.time())}"
    task_dir = os.path.join(TEMP_BASE, task_id)
    os.makedirs(task_dir, exist_ok=True)

    await event.edit("🔍 **Mengambil informasi TikTok...**")

    try:
        data = await fetch_tiktok_data(target_url)

        title = (data.get("title") or "TikTok Post").strip()
        author = data.get("author") or {}
        nickname = author.get("nickname") or "TikTok User"
        unique_id = author.get("unique_id") or "user"
        likes = data.get("digg_count", 0)
        comments = data.get("comment_count", 0)
        shares = data.get("share_count", 0)
        duration = data.get("duration", 0)

        music_info = data.get("music_info") or {}
        music_title = (music_info.get("title") or "Original Sound").strip()
        music_author = (music_info.get("author") or nickname).strip()

        images = data.get("images") or []
        video_url = data.get("hdplay") or data.get("play") or data.get("wmplay")
        music_url = data.get("music")
        cover_url = data.get("cover")

        # ── Opsi 1: Download Audio Saja ──────────────────────────────
        if is_audio:
            if not music_url:
                raise Exception("Audio untuk postingan ini tidak ditemukan.")

            await event.edit("⬇️ **Mengunduh audio TikTok...**")
            if music_url.startswith("/"):
                music_url = f"https://www.tikwm.com{music_url}"

            audio_path = os.path.join(task_dir, "tiktok_audio.mp3")

            def _download_audio():
                with requests.get(music_url, headers=HEADERS, stream=True, timeout=30) as r:
                    r.raise_for_status()
                    with open(audio_path, "wb") as f:
                        for chunk in r.iter_content(chunk_size=64 * 1024):
                            if chunk:
                                f.write(chunk)

            await asyncio.to_thread(_download_audio)

            # Download cover untuk album art audio
            thumb_path = None
            if cover_url:
                if cover_url.startswith("/"):
                    cover_url = f"https://www.tikwm.com{cover_url}"
                try:
                    def _dl_thumb():
                        r = requests.get(cover_url, headers=HEADERS, timeout=10)
                        if r.status_code == 200:
                            t_path = os.path.join(task_dir, "thumb.jpg")
                            img = Image.open(BytesIO(r.content)).convert("RGB")
                            img.save(t_path, "JPEG")
                            return t_path
                        return None
                    thumb_path = await asyncio.to_thread(_dl_thumb)
                except Exception:
                    thumb_path = None

            caption = (
                f"🎵 **{music_title}**\n\n"
                f"👤 **Artis:** `{music_author}`\n"
                f"⏱ **Durasi:** `{format_duration(duration)}`\n"
                f"🔗 [TikTok Link]({target_url})"
            )

            await event.edit("📤 **Mengunggah audio ke Telegram...**")
            await client.send_file(
                event.chat_id,
                audio_path,
                caption=caption,
                thumb=thumb_path,
                voice_note=False,
                attributes=[
                    DocumentAttributeAudio(
                        duration=int(duration),
                        voice=False,
                        title=music_title,
                        performer=music_author
                    )
                ],
                reply_to=reply_to_id,
                progress_callback=make_upload_progress(event, "📤 **Mengunggah audio ke Telegram...**")
            )
            await event.delete()
            return True

        # ── Opsi 2: Postingan Slide Foto ────────────────────────────
        if images and len(images) > 0:
            total_img = len(images)
            await event.edit(f"⬇️ **Mengunduh {total_img} slide foto TikTok...**")

            downloaded_images = []

            def _dl_images():
                paths = []
                for i, img_url in enumerate(images, 1):
                    if img_url.startswith("/"):
                        img_url = f"https://www.tikwm.com{img_url}"
                    ipath = os.path.join(task_dir, f"slide_{i}.jpg")
                    r = requests.get(img_url, headers=HEADERS, timeout=20)
                    if r.status_code == 200:
                        img = Image.open(BytesIO(r.content)).convert("RGB")
                        img.save(ipath, "JPEG")
                        paths.append(ipath)
                return paths

            downloaded_images = await asyncio.to_thread(_dl_images)

            if not downloaded_images:
                raise Exception("Gagal mengunduh gambar slide TikTok.")

            caption = (
                f"📸 **{title}**\n\n"
                f"👤 **Creator:** `{nickname}` (@{unique_id})\n"
                f"📊 **Statistik:** ❤️ `{likes:,}` • 💬 `{comments:,}` • 🔁 `{shares:,}`\n"
                f"🖼️ **Jumlah Slide:** `{len(downloaded_images)} foto`\n"
                f"🔗 [TikTok Link]({target_url})"
            )

            await event.edit(f"📤 **Mengunggah {len(downloaded_images)} foto ke Telegram...**")

            # Kirim gambar dalam batch (maksimal 10 gambar per album Telegram)
            for i in range(0, len(downloaded_images), 10):
                batch = downloaded_images[i:i + 10]
                cap = caption if i == 0 else None
                await client.send_file(
                    event.chat_id,
                    batch,
                    caption=cap,
                    reply_to=reply_to_id
                )

            # Jika ada musik latar di slide foto, kirimkan juga
            if music_url:
                try:
                    if music_url.startswith("/"):
                        music_url = f"https://www.tikwm.com{music_url}"
                    m_path = os.path.join(task_dir, "slide_audio.mp3")

                    def _dl_slide_music():
                        with requests.get(music_url, headers=HEADERS, stream=True, timeout=20) as r:
                            if r.status_code == 200:
                                with open(m_path, "wb") as f:
                                    for chk in r.iter_content(chunk_size=64 * 1024):
                                        if chk:
                                            f.write(chk)
                                return True
                        return False

                    ok = await asyncio.to_thread(_dl_slide_music)
                    if ok and os.path.exists(m_path):
                        await client.send_file(
                            event.chat_id,
                            m_path,
                            caption=f"🎵 **Musik Slide:** `{music_title}` - `{music_author}`",
                            voice_note=False,
                            attributes=[
                                DocumentAttributeAudio(
                                    duration=int(duration),
                                    voice=False,
                                    title=music_title,
                                    performer=music_author
                                )
                            ],
                            reply_to=reply_to_id
                        )
                except Exception as me:
                    logger.warning("Gagal mengirim musik slide TikTok: %s", me)

            await event.delete()
            return True

        # ── Opsi 3: Postingan Video (No Watermark) ───────────────────
        if not video_url:
            raise Exception("URL video TikTok tanpa watermark tidak ditemukan.")

        await event.edit("⬇️ **Mengunduh video TikTok (No Watermark)...**")
        if video_url.startswith("/"):
            video_url = f"https://www.tikwm.com{video_url}"

        video_path = os.path.join(task_dir, "tiktok_video.mp4")

        def _dl_video():
            with requests.get(video_url, headers=HEADERS, stream=True, timeout=60) as r:
                r.raise_for_status()
                with open(video_path, "wb") as f:
                    for chunk in r.iter_content(chunk_size=128 * 1024):
                        if chunk:
                            f.write(chunk)

        await asyncio.to_thread(_dl_video)

        # Download thumbnail / cover
        thumb_path = None
        if cover_url:
            if cover_url.startswith("/"):
                cover_url = f"https://www.tikwm.com{cover_url}"
            try:
                def _dl_thumb_vid():
                    r = requests.get(cover_url, headers=HEADERS, timeout=10)
                    if r.status_code == 200:
                        t_path = os.path.join(task_dir, "thumb.jpg")
                        img = Image.open(BytesIO(r.content)).convert("RGB")
                        img.save(t_path, "JPEG")
                        return t_path
                    return None
                thumb_path = await asyncio.to_thread(_dl_thumb_vid)
            except Exception:
                thumb_path = None

        caption = (
            f"🎬 **{title}**\n\n"
            f"👤 **Creator:** `{nickname}` (@{unique_id})\n"
            f"🎵 **Musik:** `{music_title}` - `{music_author}`\n"
            f"📊 **Statistik:** ❤️ `{likes:,}` • 💬 `{comments:,}` • 🔁 `{shares:,}`\n"
            f"⏱ **Durasi:** `{format_duration(duration)}`\n"
            f"🔗 [TikTok Link]({target_url})"
        )

        await event.edit("📤 **Mengunggah video ke Telegram...**")
        await client.send_file(
            event.chat_id,
            video_path,
            caption=caption,
            thumb=thumb_path,
            supports_streaming=True,
            reply_to=reply_to_id,
            progress_callback=make_upload_progress(event, "📤 **Mengunggah video ke Telegram...**")
        )
        await event.delete()
        return True

    except Exception as e:
        logger.exception("Error di modul TikTok: %s", e)
        await event.edit(f"❌ **Error TikTok:**\n`{str(e)}`")
        return True

    finally:
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
