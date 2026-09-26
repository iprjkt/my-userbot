"""
modules/youtube.py
Command .yt / .ytv / .ytdl - Download video YouTube (MP4)
Command .yta / .ytmp3 - Download audio YouTube (MP3)
Command .yts / .ytsearch - Cari video di YouTube
"""

import os
import re
import time
import shutil
import asyncio
import logging
import yt_dlp
from PIL import Image

from telethon.tl.types import DocumentAttributeAudio, DocumentAttributeVideo
from helpers.sys_info import make_progress_bar, format_duration
from helpers.uploader import upload_file_server_with_progress

logger = logging.getLogger("AkashaUserbot.YouTube")

TEMP_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_media")

YOUTUBE_REGEX = re.compile(
    r'(https?://(?:(?:www|m|music)\.)?(?:youtube\.com/(?:watch\?[^\s]+|shorts/[^\s]+|live/[^\s]+|v/[^\s]+)|youtu\.be/[^\s]+))',
    re.IGNORECASE
)


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


def convert_thumbnail_to_jpg(thumb_file: str) -> str:
    """Konversi thumbnail webp/png ke JPEG untuk Telegram preview."""
    if not thumb_file or not os.path.exists(thumb_file):
        return None
    try:
        jpg_path = os.path.splitext(thumb_file)[0] + ".jpg"
        if thumb_file.lower().endswith(".jpg") or thumb_file.lower().endswith(".jpeg"):
            return thumb_file
        with Image.open(thumb_file) as im:
            im = im.convert("RGB")
            im.save(jpg_path, "JPEG", quality=90)
        return jpg_path
    except Exception:
        return None


async def handle_search(event, txt):
    """Pencarian video di YouTube (.yts / .ytsearch)."""
    parts = txt.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await event.edit(
            "❌ **Format pencarian YouTube salah!**\n\n"
            "**Penggunaan:** `.yts <kata kunci>`\n"
            "**Contoh:** `.yts Alan Walker Faded`"
        )
        return True

    query = parts[1].strip()
    await event.edit(f"🔍 **Mencari `{query}` di YouTube...**")

    def _search():
        ydl_opts = {
            "quiet": True,
            "skip_download": True,
            "extract_flat": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            return ydl.extract_info(f"ytsearch5:{query}", download=False)

    try:
        res = await asyncio.to_thread(_search)
        entries = res.get("entries", []) if res else []
        if not entries:
            await event.edit(f"❌ Tidak ditemukan hasil untuk: `{query}`")
            return True

        result_text = f"🔍 **Hasil Pencarian YouTube:** `{query}`\n\n"
        for i, item in enumerate(entries, 1):
            title = item.get("title", "No Title")
            v_url = item.get("url") or f"https://www.youtube.com/watch?v={item.get('id')}"
            dur = format_duration(item.get("duration", 0))
            channel = item.get("uploader") or item.get("channel") or "Unknown Channel"
            views = item.get("view_count")
            view_str = f" • 👁 `{views:,} views`" if views else ""

            result_text += (
                f"{i}. 🎬 **[{title}]({v_url})**\n"
                f"   ⏱ Durasi: `{dur}` | 👤 `{channel}`{view_str}\n\n"
            )

        result_text += "💡 _Download Video: `.yt <link>` | Audio: `.yta <link>`_"
        await event.edit(result_text, link_preview=False)
    except Exception as e:
        logger.exception("Error searching YouTube: %s", e)
        await event.edit(f"❌ **Error Search YouTube:** `{e}`")

    return True


async def handle(event, client, txt, t_l):
    """Command YouTube (.yt, .ytv, .ytdl, .yta, .ytmp3, .yts, .ytsearch)."""
    # ── 1. Search YouTube (.yts / .ytsearch) ─────────────────────────
    if (
        t_l in [".yts", ".ytsearch"] or
        t_l.startswith((".yts ", ".ytsearch "))
    ):
        return await handle_search(event, txt)

    # ── 2. Cek apakah ini command YouTube Video / Audio ─────────────
    is_video_cmd = (
        t_l in [".yt", ".ytv", ".ytdl"] or
        t_l.startswith((".yt ", ".ytv ", ".ytdl "))
    )
    is_audio_cmd = (
        t_l in [".yta", ".ytmp3"] or
        t_l.startswith((".yta ", ".ytmp3 "))
    )

    if not (is_video_cmd or is_audio_cmd):
        return False

    reply_msg = await event.get_reply_message() if event.is_reply else None
    reply_to_id = reply_msg.id if reply_msg else None

    # Cari URL di teks perintah
    urls = YOUTUBE_REGEX.findall(txt)

    # Jika tidak ada, cek teks pesan reply
    if not urls and reply_msg and reply_msg.raw_text:
        urls = YOUTUBE_REGEX.findall(reply_msg.raw_text)

    if not urls:
        await event.edit(
            "❌ **Link YouTube tidak ditemukan!**\n\n"
            "**Penggunaan:**\n"
            "• `.yt <link> [resolusi]` - Download video YouTube (MP4)\n"
            "• `.yt <link> 720` - Download video maks 720p\n"
            "• `.yta <link>` - Download audio YouTube (.mp3)\n"
            "• `.yts <kata kunci>` - Cari video di YouTube\n"
            "• Reply pesan yang berisi link YouTube dengan `.yt` atau `.yta`"
        )
        return True

    target_url = urls[0].strip()

    # Cek opsi resolusi jika video (e.g. 360, 480, 720, 1080)
    max_height = 1080
    parts = txt.split()
    for p in parts[1:]:
        if p.isdigit() and int(p) in [144, 240, 360, 480, 720, 1080, 1440, 2160]:
            max_height = int(p)
            break

    task_id = f"yt_{event.id}_{int(time.time())}"
    task_dir = os.path.join(TEMP_BASE, task_id)
    os.makedirs(task_dir, exist_ok=True)

    loop = asyncio.get_running_loop()
    last_prog = [0]

    def _progress_hook(d):
        if d.get("status") == "downloading":
            now = time.time()
            if now - last_prog[0] >= 3:
                last_prog[0] = now
                total = d.get("total_bytes") or d.get("total_bytes_estimate") or 0
                downloaded = d.get("downloaded_bytes", 0)
                speed = d.get("speed") or 0
                if total > 0:
                    pct = (downloaded / total) * 100
                    p_bar = make_progress_bar(pct)
                    curr_mb = downloaded / (1024 * 1024)
                    tot_mb = total / (1024 * 1024)
                    speed_mb = f"{speed / (1024 * 1024):.1f} MB/s" if speed else "N/A"
                    asyncio.run_coroutine_threadsafe(
                        event.edit(
                            f"⬇️ **Downloading dari YouTube...**\n"
                            f"`{p_bar}` ({curr_mb:.1f} / {tot_mb:.1f} MB)\n"
                            f"⚡ `{speed_mb}`"
                        ),
                        loop
                    )

    try:
        # ── Opsi A: Audio Only (.yta / .ytmp3) ────────────────────────
        if is_audio_cmd:
            await event.edit("🔍 **Mengambil info audio YouTube...**")

            ydl_opts = {
                "format": "bestaudio/best",
                "outtmpl": os.path.join(task_dir, "%(id)s.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "writethumbnail": True,
                "progress_hooks": [_progress_hook],
                "quiet": True,
                "no_warnings": True,
            }

            def _dl_audio():
                with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                    return ydl.extract_info(target_url, download=True)

            info = await asyncio.to_thread(_dl_audio)

            title = info.get("title", "YouTube Audio")
            channel = info.get("uploader") or info.get("channel") or "Unknown Artist"
            duration = info.get("duration", 0)
            webpage_url = info.get("webpage_url") or target_url

            # Cari file mp3 yang dihasilkan
            mp3_file = None
            raw_thumb = None
            for f in os.listdir(task_dir):
                if f.endswith(".mp3"):
                    mp3_file = os.path.join(task_dir, f)
                elif f.lower().endswith((".webp", ".png", ".jpg", ".jpeg")):
                    raw_thumb = os.path.join(task_dir, f)

            if not mp3_file or not os.path.exists(mp3_file):
                raise Exception("Gagal mengekstrak file audio MP3.")

            thumb_path = convert_thumbnail_to_jpg(raw_thumb) if raw_thumb else None
            f_size_mb = os.path.getsize(mp3_file) / (1024 * 1024)

            # Cek limit ukuran Telegram (2GB)
            if f_size_mb > 2000:
                await event.edit(f"⚠️ Ukuran file ({f_size_mb:.1f} MB) melebihi limit Telegram.\nUploading ke server...")
                down_link = await upload_file_server_with_progress(
                    mp3_file, event, 1, 1, os.path.basename(mp3_file)
                )
                await event.edit(
                    f"🎵 **[{title}]({webpage_url})**\n\n"
                    f"👤 **Artis:** `{channel}`\n"
                    f"📦 **Ukuran:** `{f_size_mb:.1f} MB`\n"
                    f"🔗 [Download MP3 Link]({down_link})",
                    link_preview=False
                )
                return True

            caption = (
                f"🎵 **[{title}]({webpage_url})**\n\n"
                f"👤 **Artis / Channel:** `{channel}`\n"
                f"⏱ **Durasi:** `{format_duration(duration)}`\n"
                f"📦 **Ukuran:** `{f_size_mb:.1f} MB`"
            )

            await event.edit("📤 **Mengunggah audio ke Telegram...**")
            await client.send_file(
                event.chat_id,
                mp3_file,
                caption=caption,
                thumb=thumb_path,
                voice_note=False,
                attributes=[
                    DocumentAttributeAudio(
                        duration=int(duration),
                        voice=False,
                        title=title,
                        performer=channel
                    )
                ],
                reply_to=reply_to_id,
                progress_callback=make_upload_progress(event, "📤 **Mengunggah audio ke Telegram...**")
            )
            await event.delete()
            return True

        # ── Opsi B: Video (.yt / .ytv / .ytdl) ────────────────────────
        await event.edit(f"🔍 **Mengambil info video YouTube ({max_height}p)...**")

        format_str = (
            f"bestvideo[ext=mp4][height<={max_height}]+bestaudio[ext=m4a]/"
            f"best[ext=mp4][height<={max_height}]/"
            f"best[height<={max_height}]/best"
        )

        ydl_opts = {
            "format": format_str,
            "outtmpl": os.path.join(task_dir, "%(id)s.%(ext)s"),
            "merge_output_format": "mp4",
            "writethumbnail": True,
            "progress_hooks": [_progress_hook],
            "quiet": True,
            "no_warnings": True,
        }

        def _dl_video():
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                return ydl.extract_info(target_url, download=True)

        info = await asyncio.to_thread(_dl_video)

        title = info.get("title", "YouTube Video")
        channel = info.get("uploader") or info.get("channel") or "Unknown Channel"
        duration = info.get("duration", 0)
        views = info.get("view_count")
        width = info.get("width") or 1280
        height = info.get("height") or 720
        webpage_url = info.get("webpage_url") or target_url

        # Cari file mp4 yang dihasilkan
        video_file = None
        raw_thumb = None
        for f in os.listdir(task_dir):
            if f.endswith(".mp4"):
                video_file = os.path.join(task_dir, f)
            elif f.lower().endswith((".webp", ".png", ".jpg", ".jpeg")):
                raw_thumb = os.path.join(task_dir, f)

        if not video_file or not os.path.exists(video_file):
            raise Exception("Gagal mengunduh file video MP4.")

        thumb_path = convert_thumbnail_to_jpg(raw_thumb) if raw_thumb else None
        f_size_mb = os.path.getsize(video_file) / (1024 * 1024)

        # Cek limit ukuran Telegram (2GB)
        if f_size_mb > 2000:
            await event.edit(f"⚠️ Ukuran video ({f_size_mb:.1f} MB) melebihi limit Telegram (2GB).\nUploading ke server...")
            down_link = await upload_file_server_with_progress(
                video_file, event, 1, 1, os.path.basename(video_file)
            )
            await event.edit(
                f"🎬 **[{title}]({webpage_url})**\n\n"
                f"👤 **Channel:** `{channel}`\n"
                f"⏱ **Durasi:** `{format_duration(duration)}`\n"
                f"📦 **Ukuran:** `{f_size_mb:.1f} MB`\n"
                f"🔗 [Download Video Link]({down_link})",
                link_preview=False
            )
            return True

        view_str = f" • 👁 `{views:,} views`" if views else ""
        caption = (
            f"🎬 **[{title}]({webpage_url})**\n\n"
            f"👤 **Channel:** `{channel}`\n"
            f"⏱ **Durasi:** `{format_duration(duration)}`{view_str}\n"
            f"📦 **Ukuran:** `{f_size_mb:.1f} MB`"
        )

        await event.edit("📤 **Mengunggah video ke Telegram...**")
        await client.send_file(
            event.chat_id,
            video_file,
            caption=caption,
            thumb=thumb_path,
            supports_streaming=True,
            attributes=[
                DocumentAttributeVideo(
                    duration=int(duration),
                    w=int(width),
                    h=int(height),
                    supports_streaming=True
                )
            ],
            reply_to=reply_to_id,
            progress_callback=make_upload_progress(event, "📤 **Mengunggah video ke Telegram...**")
        )
        await event.delete()
        return True

    except Exception as e:
        logger.exception("Error di modul YouTube: %s", e)
        await event.edit(f"❌ **Error YouTube:**\n`{str(e)}`")
        return True

    finally:
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
