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
from telethon.errors import MediaCaptionTooLongError
from helpers.sys_info import make_progress_bar, format_duration
from helpers.uploader import upload_file_server_with_progress

logger = logging.getLogger("AkashaUserbot.YouTube")

TEMP_BASE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "temp_media")


def build_caption(header_title: str, prefix_icon: str, footer_info: str, max_total: int = 1000) -> str:
    """
    Bangun caption Telegram dengan membatasi panjang total <= max_total (default 1000).
    Jika terlalu panjang, judul dipotong rapi dengan tanda '...' agar tidak melebihi limit 1024 karakter Telegram.
    """
    base_overhead = len(prefix_icon) + len(footer_info) + 12
    available_title_len = max(30, max_total - base_overhead)

    clean_title = (header_title or "").strip()
    if len(clean_title) > available_title_len:
        clean_title = clean_title[:available_title_len - 3].strip() + "..."

    caption = f"{prefix_icon} **{clean_title}**\n\n{footer_info}".strip()
    if len(caption) > 1024:
        caption = caption[:1020] + "..."
    return caption

YOUTUBE_REGEX = re.compile(
    r'(https?://(?:(?:www|m|music)\.)?(?:youtube\.com/(?:watch\?[^\s]+|shorts/[^\s]+|live/[^\s]+|v/[^\s]+)|youtu\.be/[^\s]+))',
    re.IGNORECASE
)


def get_cookie_file() -> str | None:
    """Cari file cookies.txt jika disediakan oleh pengguna untuk bypass bot verification."""
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    candidates = [
        os.path.join(base_dir, "cookies.txt"),
        os.path.join(base_dir, "youtube_cookies.txt"),
        os.getenv("YT_COOKIES"),
        os.getenv("YOUTUBE_COOKIES_PATH"),
    ]
    for c in candidates:
        if c and os.path.exists(c) and os.path.getsize(c) > 0:
            return c
    return None


def get_base_ydl_opts(use_android_only: bool = False) -> dict:
    """Konfigurasi dasar yt-dlp dengan extractor_args untuk bypass bot verification."""
    cookie_file = get_cookie_file()

    # Jika ada cookies, web client aman digunakan untuk kualitas penuh.
    # Jika tidak ada cookies, prioritaskan client android & ios untuk menghindari bot detection.
    if cookie_file:
        clients = ["web", "android", "ios"]
    elif use_android_only:
        clients = ["android"]
    else:
        clients = ["android", "ios", "web"]

    opts = {
        "extractor_args": {
            "youtube": {
                "player_client": clients
            }
        },
        "quiet": True,
        "no_warnings": True,
    }
    if cookie_file:
        opts["cookiefile"] = cookie_file
    return opts


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
        ydl_opts = get_base_ydl_opts()
        ydl_opts.update({
            "skip_download": True,
            "extract_flat": True,
        })
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

            ydl_opts = get_base_ydl_opts()
            ydl_opts.update({
                "format": "bestaudio/best",
                "outtmpl": os.path.join(task_dir, "%(id)s.%(ext)s"),
                "postprocessors": [{
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }],
                "writethumbnail": True,
                "progress_hooks": [_progress_hook],
            })

            def _dl_audio(opts):
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(target_url, download=True)

            try:
                info = await asyncio.to_thread(_dl_audio, ydl_opts)
            except Exception as e:
                err_text = str(e).lower()
                if "sign in" in err_text or "bot" in err_text:
                    await event.edit("⏳ **Mencoba bypass bot verification (Android client)...**")
                    fallback_opts = get_base_ydl_opts(use_android_only=True)
                    fallback_opts.update({
                        "format": "bestaudio/best",
                        "outtmpl": os.path.join(task_dir, "%(id)s.%(ext)s"),
                        "postprocessors": [{
                            "key": "FFmpegExtractAudio",
                            "preferredcodec": "mp3",
                            "preferredquality": "192",
                        }],
                        "writethumbnail": True,
                        "progress_hooks": [_progress_hook],
                    })
                    info = await asyncio.to_thread(_dl_audio, fallback_opts)
                else:
                    raise

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

            footer = (
                f"👤 **Artis / Channel:** `{channel}`\n"
                f"⏱ **Durasi:** `{format_duration(duration)}`\n"
                f"📦 **Ukuran:** `{f_size_mb:.1f} MB`"
            )
            caption = build_caption(f"[{title}]({webpage_url})", "🎵", footer)

            await event.edit("📤 **Mengunggah audio ke Telegram...**")
            try:
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
            except MediaCaptionTooLongError:
                short_cap = caption[:800] + "..."
                await client.send_file(
                    event.chat_id,
                    mp3_file,
                    caption=short_cap,
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
                    reply_to=reply_to_id
                )
            await event.delete()
            return True

        # ── Opsi B: Video (.yt / .ytv / .ytdl) ────────────────────────
        await event.edit(f"🔍 **Mengambil info video YouTube ({max_height}p)...**")

        format_str = (
            f"bestvideo[ext=mp4][height<={max_height}]+bestaudio[ext=m4a]/"
            f"best[ext=mp4][height<={max_height}]/"
            f"bestvideo*[height<={max_height}]+bestaudio/best"
        )

        ydl_opts = get_base_ydl_opts()
        ydl_opts.update({
            "format": format_str,
            "outtmpl": os.path.join(task_dir, "%(id)s.%(ext)s"),
            "merge_output_format": "mp4",
            "writethumbnail": True,
            "progress_hooks": [_progress_hook],
        })

        def _dl_video(opts):
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(target_url, download=True)

        try:
            info = await asyncio.to_thread(_dl_video, ydl_opts)
        except Exception as e:
            err_text = str(e).lower()
            if "sign in" in err_text or "bot" in err_text:
                await event.edit("⏳ **Mencoba bypass bot verification (Android client)...**")
                fallback_opts = get_base_ydl_opts(use_android_only=True)
                fallback_opts.update({
                    "format": f"bestvideo*[height<={max_height}]+bestaudio/best[height<={max_height}]/best",
                    "outtmpl": os.path.join(task_dir, "%(id)s.%(ext)s"),
                    "merge_output_format": "mp4",
                    "writethumbnail": True,
                    "progress_hooks": [_progress_hook],
                })
                info = await asyncio.to_thread(_dl_video, fallback_opts)
            else:
                raise

        title = info.get("title", "YouTube Video")
        channel = info.get("uploader") or info.get("channel") or "Unknown Channel"
        duration = info.get("duration", 0)
        views = info.get("view_count")
        width = info.get("width") or 1280
        height = info.get("height") or 720
        webpage_url = info.get("webpage_url") or target_url

        # Cari file video yang dihasilkan
        video_file = None
        raw_thumb = None
        for f in os.listdir(task_dir):
            if f.endswith(".mp4"):
                video_file = os.path.join(task_dir, f)
            elif f.lower().endswith((".webp", ".png", ".jpg", ".jpeg")):
                raw_thumb = os.path.join(task_dir, f)

        # Fallback jika ekstensi bukan .mp4 (.mkv atau .webm)
        if not video_file:
            for f in os.listdir(task_dir):
                if f.endswith((".mkv", ".webm")):
                    video_file = os.path.join(task_dir, f)
                    break

        if not video_file or not os.path.exists(video_file):
            raise Exception("Gagal mengunduh file video YouTube.")

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
        footer = (
            f"👤 **Channel:** `{channel}`\n"
            f"⏱ **Durasi:** `{format_duration(duration)}`{view_str}\n"
            f"📦 **Ukuran:** `{f_size_mb:.1f} MB`"
        )
        caption = build_caption(f"[{title}]({webpage_url})", "🎬", footer)

        await event.edit("📤 **Mengunggah video ke Telegram...**")
        try:
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
        except MediaCaptionTooLongError:
            short_cap = caption[:800] + "..."
            await client.send_file(
                event.chat_id,
                video_file,
                caption=short_cap,
                thumb=thumb_path,
                supports_streaming=True,
                reply_to=reply_to_id
            )
        await event.delete()
        return True

    except Exception as e:
        err_str = str(e)
        logger.exception("Error di modul YouTube: %s", e)
        if "sign in" in err_str.lower() or "bot" in err_str.lower():
            await event.edit(
                "❌ **YouTube Bot Verification Terdeteksi!**\n\n"
                "YouTube memblokir request dari IP VPS ini untuk video tersebut.\n\n"
                "💡 **Solusi Ampuh:**\n"
                "1. Ekspor cookies YouTube dari browser Anda (format Netscape `cookies.txt`).\n"
                "2. Simpan file tersebut dengan nama `cookies.txt` di folder utama userbot.\n"
                "Bot akan otomatis membaca cookies tersebut dan bebas dari limit bot!"
            )
        else:
            await event.edit(f"❌ **Error YouTube:**\n`{err_str}`")
        return True

    finally:
        if os.path.exists(task_dir):
            shutil.rmtree(task_dir, ignore_errors=True)
