"""
modules/towa.py
Command .towa & .towapack - Convert stiker/media Telegram ke format stiker WhatsApp (.webp).
Mendukung stiker statis (WebP/Foto) dan stiker animasi (Video/GIF -> Animated WebP 512x512)
lengkap dengan inject EXIF metadata khusus WhatsApp (Pack Name, Author/Publisher, Emoji).
"""

import os
import io
import json
import shutil
import struct
import asyncio
import zipfile
from PIL import Image

from telethon.tl.functions.messages import GetStickerSetRequest
from telethon.tl.types import (
    InputStickerSetShortName,
    InputStickerSetEmpty,
    DocumentAttributeSticker,
)


def build_whatsapp_exif(pack_name="Akasha Pack", author="Akasha Userbot", emojis=None):
    """Membuat payload binary EXIF standar WhatsApp sticker."""
    meta = {
        "sticker-pack-id": "com.akasha.userbot",
        "sticker-pack-name": pack_name,
        "sticker-pack-publisher": author,
        "emojis": emojis or ["🤔"]
    }
    json_bytes = json.dumps(meta, ensure_ascii=False).encode("utf-8")
    header = bytes([
        0x49, 0x49, 0x2A, 0x00,  # TIFF little-endian
        0x08, 0x00, 0x00, 0x00,  # IFD offset (8)
        0x01, 0x00,              # 1 directory entry
        0x41, 0x57,              # Tag 0x5741 ('WA' WhatsApp)
        0x07, 0x00               # Type 7 (UNDEFINED)
    ])
    length_bytes = struct.pack("<I", len(json_bytes))
    offset_bytes = bytes([0x16, 0x00, 0x00, 0x00])  # offset 22
    return header + length_bytes + offset_bytes + json_bytes


def inject_webp_exif(webp_data: bytes, exif_data: bytes) -> bytes:
    """Menyisipkan atau mengganti chunk EXIF ke dalam container RIFF WebP."""
    if len(webp_data) < 12 or webp_data[:4] != b"RIFF" or webp_data[8:12] != b"WEBP":
        raise ValueError("File bukan format RIFF WEBP yang valid")

    chunks = []
    vp8x_index = -1
    pos = 12

    while pos + 8 <= len(webp_data):
        tag = webp_data[pos:pos+4]
        size = struct.unpack("<I", webp_data[pos+4:pos+8])[0]
        data_end = pos + 8 + size
        if data_end > len(webp_data):
            break
        pad = size % 2
        chunk_full = webp_data[pos:data_end + pad]
        if tag == b"VP8X" and size >= 10:
            vp8x_index = len(chunks)
        if tag != b"EXIF":
            chunks.append(bytearray(chunk_full))
        pos = data_end + pad

    if vp8x_index >= 0:
        # Set bit EXIF (0x08) pada VP8X flags (byte ke-8 dari chunk)
        chunks[vp8x_index][8] |= 0x08
    else:
        # Jika belum ada VP8X, tambahkan chunk VP8X 512x512
        vp8x_payload = bytearray(10)
        vp8x_payload[0] = 0x08 | 0x10  # EXIF flag + Alpha flag
        w_val = 511  # 512 - 1
        h_val = 511  # 512 - 1
        vp8x_payload[4] = w_val & 0xFF
        vp8x_payload[5] = (w_val >> 8) & 0xFF
        vp8x_payload[6] = (w_val >> 16) & 0xFF
        vp8x_payload[7] = h_val & 0xFF
        vp8x_payload[8] = (h_val >> 8) & 0xFF
        vp8x_payload[9] = (h_val >> 16) & 0xFF
        vp8x_chunk = b"VP8X" + struct.pack("<I", 10) + bytes(vp8x_payload)
        chunks.insert(0, bytearray(vp8x_chunk))

    out = bytearray(b"RIFF\x00\x00\x00\x00WEBP")
    for c in chunks:
        out.extend(c)

    exif_size = len(exif_data)
    out.extend(b"EXIF" + struct.pack("<I", exif_size) + exif_data)
    if exif_size % 2:
        out.extend(b"\x00")

    riff_size = len(out) - 8
    out[4:8] = struct.pack("<I", riff_size)
    return bytes(out)


async def convert_static_to_wa_webp(in_path: str, out_path: str, pack_name: str, author: str, emoji: str):
    """Konversi gambar statis ke WebP 512x512 transparan + EXIF WhatsApp (<= 100KB)."""
    img = Image.open(in_path).convert("RGBA")
    img.thumbnail((512, 512), Image.Resampling.LANCZOS)
    canvas = Image.new("RGBA", (512, 512), (0, 0, 0, 0))
    x = (512 - img.width) // 2
    y = (512 - img.height) // 2
    canvas.paste(img, (x, y), mask=img)

    bio = io.BytesIO()
    canvas.save(bio, format="WEBP", quality=85, method=6)
    if len(bio.getvalue()) > 100 * 1024:
        bio = io.BytesIO()
        canvas.save(bio, format="WEBP", quality=60, method=6)

    exif = build_whatsapp_exif(pack_name, author, [emoji])
    final_data = inject_webp_exif(bio.getvalue(), exif)
    with open(out_path, "wb") as f:
        f.write(final_data)


async def convert_anim_to_wa_webp(in_path: str, out_path: str, pack_name: str, author: str, emoji: str):
    """Konversi video/GIF ke Animated WebP 512x512 transparan + EXIF WhatsApp (<= 500KB)."""
    temp_raw = out_path + ".raw.webp"
    cmd = [
        "ffmpeg", "-y",
        "-i", in_path,
        "-t", "3",
        "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000",
        "-r", "20",
        "-vcodec", "libwebp",
        "-lossless", "0",
        "-q:v", "65",
        "-loop", "0",
        "-an",
        temp_raw
    ]
    proc = await asyncio.create_subprocess_exec(*cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
    _, stderr = await proc.communicate()

    if not os.path.exists(temp_raw) or os.path.getsize(temp_raw) == 0:
        err_msg = stderr.decode("utf-8", errors="ignore") if stderr else "Unknown error"
        raise Exception(f"Gagal mengonversi animasi ke WebP: {err_msg[-150:]}")

    # Kompresi ulang jika > 500 KB (batas stiker animasi WhatsApp)
    if os.path.getsize(temp_raw) > 500 * 1024:
        cmd2 = [
            "ffmpeg", "-y",
            "-i", in_path,
            "-t", "2.5",
            "-vf", "scale=512:512:force_original_aspect_ratio=decrease,pad=512:512:(ow-iw)/2:(oh-ih)/2:color=0x00000000",
            "-r", "15",
            "-vcodec", "libwebp",
            "-lossless", "0",
            "-q:v", "45",
            "-loop", "0",
            "-an",
            temp_raw
        ]
        proc2 = await asyncio.create_subprocess_exec(*cmd2, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE)
        await proc2.communicate()

    with open(temp_raw, "rb") as f:
        raw_data = f.read()
    if os.path.exists(temp_raw):
        os.remove(temp_raw)

    exif = build_whatsapp_exif(pack_name, author, [emoji])
    final_data = inject_webp_exif(raw_data, exif)
    with open(out_path, "wb") as f:
        f.write(final_data)


def extract_short_name(text: str) -> str:
    """Ekstrak short_name dari link t.me/addstickers atau string biasa."""
    text = text.strip()
    if "t.me/addstickers/" in text:
        text = text.split("t.me/addstickers/")[-1].split("?")[0].split("/")[0].strip()
    elif "addstickers/" in text:
        text = text.split("addstickers/")[-1].split("?")[0].split("/")[0].strip()
    return text.strip()


async def handle(event, client, txt, t_l):
    """Handler command .towa & .towapack. Return True jika ditangani."""
    is_pack_cmd = t_l.startswith(".towapack") or t_l.startswith(".wapack") or t_l.startswith(".towa pack")
    is_single_cmd = t_l.startswith(".towa") or t_l.startswith(".wasticker") or t_l.startswith(".wa ") or t_l == ".wa"

    if not (is_pack_cmd or is_single_cmd):
        return False

    me = await client.get_me()

    # ═══════════════════════════════════════════════════════════════════
    # 1. FITUR CONVERT SELURUH STICKER PACK (.towapack / .towa pack)
    # ═══════════════════════════════════════════════════════════════════
    if is_pack_cmd:
        if t_l.startswith(".towa pack"):
            parts = txt.split(maxsplit=2)
            query = parts[2].strip() if len(parts) > 2 else ""
        else:
            parts = txt.split(maxsplit=1)
            query = parts[1].strip() if len(parts) > 1 else ""

        stickerset_input = None

        if query:
            short_name = extract_short_name(query)
            stickerset_input = InputStickerSetShortName(short_name=short_name)
        else:
            if not event.is_reply:
                await event.edit(
                    "❌ **Reply ke salah satu stiker Telegram dalam pack,**\n"
                    "atau ketik `.towapack <link_atau_nama_pack>` Ngab!"
                )
                return True

            reply_msg = await event.get_reply_message()
            if not reply_msg or not reply_msg.sticker:
                await event.edit("❌ **Pesan yang di-reply bukan stiker Telegram!**")
                return True

            for attr in reply_msg.sticker.attributes:
                if isinstance(attr, DocumentAttributeSticker) and attr.stickerset:
                    if not isinstance(attr.stickerset, InputStickerSetEmpty):
                        stickerset_input = attr.stickerset
                        break

            if not stickerset_input:
                await event.edit("❌ **Tidak dapat mendeteksi sticker pack dari stiker tersebut!**")
                return True

        await event.edit("⏳ **Mengambil informasi sticker pack Telegram...**")

        temp_dir = os.path.abspath(f"temp_wapack_{event.id}")
        zip_path = os.path.abspath(f"temp_wapack_{event.id}.zip")

        try:
            try:
                sticker_set = await client(GetStickerSetRequest(stickerset=stickerset_input, hash=0))
            except Exception as e:
                await event.edit(f"❌ **Gagal mengambil sticker pack Telegram:**\n`{str(e)}`")
                return True

            pack_title = sticker_set.set.title
            pack_short_name = sticker_set.set.short_name
            documents = sticker_set.documents
            total_count = len(documents)

            if total_count == 0:
                await event.edit("❌ **Sticker pack ini tidak memiliki stiker di dalamnya!**")
                return True

            # Petakan emoji untuk masing-masing stiker
            doc_emojis = {}
            for pack in sticker_set.packs:
                for doc_id in pack.documents:
                    doc_emojis[doc_id] = pack.emoticon

            os.makedirs(temp_dir, exist_ok=True)
            converted_files = []

            # Batasi maksimal 60 stiker per proses agar tidak kehabisan memori / waktu
            limit = min(total_count, 60)
            await event.edit(
                f"📦 **Memproses Pack:** `{pack_title}`\n"
                f"⏳ **Mengonversi 0/{limit} stiker ke format WhatsApp...**"
            )

            author_name = f"@{me.username}" if me.username else (me.first_name or "Akasha")

            for idx, doc in enumerate(documents[:limit], 1):
                doc_emoji = doc_emojis.get(doc.id, "🤔")
                doc_in = os.path.join(temp_dir, f"raw_{idx}")
                downloaded = await client.download_media(doc, file=doc_in)
                if not downloaded or not os.path.exists(downloaded):
                    continue

                # Cek apakah video sticker
                is_video_doc = False
                mime = (doc.mime_type or "").lower()
                if mime.startswith("video/"):
                    is_video_doc = True
                for attr in doc.attributes:
                    if getattr(attr, 'video', False):
                        is_video_doc = True
                        break

                out_webp = os.path.join(temp_dir, f"sticker_{idx:02d}.webp")

                try:
                    if is_video_doc:
                        await convert_anim_to_wa_webp(downloaded, out_webp, pack_title, author_name, doc_emoji)
                    else:
                        await convert_static_to_wa_webp(downloaded, out_webp, pack_title, author_name, doc_emoji)

                    if os.path.exists(out_webp):
                        converted_files.append((out_webp, f"sticker_{idx:02d}.webp"))
                except Exception:
                    pass
                finally:
                    if downloaded and os.path.exists(downloaded):
                        try:
                            os.remove(downloaded)
                        except Exception:
                            pass

                # Update progress setiap 5 stiker
                if idx % 5 == 0 or idx == limit:
                    try:
                        await event.edit(
                            f"📦 **Pack:** `{pack_title}`\n"
                            f"⏳ **Mengonversi {idx}/{limit} stiker ke WhatsApp WebP...**"
                        )
                    except Exception:
                        pass

            if not converted_files:
                await event.edit("❌ **Gagal mengonversi stiker dalam pack ini.**")
                return True

            # Buat file ZIP
            clean_pack_name = "".join(c for c in pack_short_name if c.isalnum() or c in ("-", "_"))
            final_zip_name = f"{clean_pack_name}_WhatsApp_Stickers.zip"

            with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for file_path, arc_name in converted_files:
                    zipf.write(file_path, arcname=arc_name)

            zip_size_mb = os.path.getsize(zip_path) / (1024 * 1024)

            caption = (
                f"✅ **Berhasil convert {len(converted_files)}/{limit} stiker ke WhatsApp!** 🟢\n\n"
                f"📦 **Pack:** `{pack_title}`\n"
                f"📁 **File:** `{final_zip_name}` (`{zip_size_mb:.2f} MB`)\n"
                f"👤 **Author:** `{author_name}`\n\n"
                f"💡 _Ekstrak file zip ini dan import ke WhatsApp melalui aplikasi seperti **Sticker.ly** atau **Personal Stickers for WhatsApp**._"
            )

            await event.edit("📤 **Mengunggah file ZIP stiker WhatsApp...**")
            await client.send_file(
                event.chat_id,
                file=zip_path,
                force_document=True,
                caption=caption
            )
            await event.delete()

        except Exception as e:
            await event.edit(f"❌ **Error saat convert pack stiker WhatsApp:**\n```{str(e)}```")

        finally:
            if os.path.exists(temp_dir):
                shutil.rmtree(temp_dir, ignore_errors=True)
            if os.path.exists(zip_path):
                try:
                    os.remove(zip_path)
                except Exception:
                    pass

        return True

    # ═══════════════════════════════════════════════════════════════════
    # 2. FITUR CONVERT SINGLE STICKER / MEDIA (.towa / .wasticker)
    # ═══════════════════════════════════════════════════════════════════
    if not event.is_reply:
        await event.edit(
            "❌ **Reply ke stiker, foto, GIF, atau video yang mau di-convert ke stiker WhatsApp Ngab!**\n"
            "💡 _Bisa juga kustomisasi: `.towa [Nama Pack] | [Author]`_"
        )
        return True

    reply_msg = await event.get_reply_message()
    if not reply_msg.media:
        await event.edit("❌ **Pesan yang di-reply tidak mengandung media!**")
        return True

    # Cek stiker animasi vektor TGS (Lottie)
    if reply_msg.sticker:
        for attr in reply_msg.sticker.attributes:
            if getattr(attr, 'animated', False) and not getattr(attr, 'video', False):
                await event.edit(
                    "❌ **Stiker animasi vektor TGS (.tgs Lottie) belum didukung.**\n"
                    "💡 _Gunakan stiker video Telegram (WebM), GIF, atau foto/stiker gambar biasa._"
                )
                return True

    await event.edit("⏳ **Mengonversi media ke stiker WhatsApp...**")

    # Parse argument custom [pack_name] | [author]
    raw_args = ""
    parts = txt.split(maxsplit=1)
    if len(parts) > 1:
        raw_args = parts[1].strip()

    pack_name = "Akasha WA Pack"
    author_name = f"@{me.username}" if me.username else (me.first_name or "Akasha")

    if "|" in raw_args:
        p = raw_args.split("|", 1)
        if p[0].strip():
            pack_name = p[0].strip()
        if p[1].strip():
            author_name = p[1].strip()
    elif raw_args:
        pack_name = raw_args.strip()
    elif reply_msg.sticker:
        # Gunakan nama sticker pack asli jika tersedia
        for attr in reply_msg.sticker.attributes:
            if isinstance(attr, DocumentAttributeSticker) and attr.stickerset:
                if isinstance(attr.stickerset, InputStickerSetShortName):
                    pack_name = attr.stickerset.short_name.replace("_", " ").title()
                    break

    # Emoji stiker
    sticker_emoji = "🤔"
    if reply_msg.sticker:
        for attr in reply_msg.sticker.attributes:
            if hasattr(attr, 'alt') and attr.alt:
                sticker_emoji = attr.alt
                break

    # Cek apakah media animasi (video/GIF) atau statis
    is_anim_or_video = False
    if reply_msg.video or reply_msg.gif:
        is_anim_or_video = True
    elif reply_msg.sticker:
        for attr in reply_msg.sticker.attributes:
            if getattr(attr, 'video', False):
                is_anim_or_video = True
                break
    elif reply_msg.document:
        mime = (reply_msg.document.mime_type or "").lower()
        if mime.startswith("video/") or mime == "image/gif":
            is_anim_or_video = True

    temp_in = None
    temp_out = os.path.abspath(f"temp_wa_{event.id}.webp")

    try:
        temp_prefix = os.path.abspath(f"temp_wa_raw_{event.id}")
        temp_in = await client.download_media(reply_msg, file=temp_prefix)
        if not temp_in or not os.path.exists(temp_in):
            raise Exception("Gagal mengunduh media.")

        if is_anim_or_video:
            await convert_anim_to_wa_webp(temp_in, temp_out, pack_name, author_name, sticker_emoji)
        else:
            await convert_static_to_wa_webp(temp_in, temp_out, pack_name, author_name, sticker_emoji)

        if not os.path.exists(temp_out) or os.path.getsize(temp_out) == 0:
            raise Exception("Gagal membuat file stiker WebP WhatsApp.")

        file_size_kb = os.path.getsize(temp_out) / 1024
        tipe_label = "Animasi" if is_anim_or_video else "Statis"

        caption = (
            f"✅ **Stiker WhatsApp ({tipe_label})** {sticker_emoji}\n"
            f"📦 **Pack:** `{pack_name}`\n"
            f"👤 **Author:** `{author_name}`\n"
            f"💾 **Ukuran:** `{file_size_kb:.1f} KB` (512x512)\n\n"
            f"💡 _Kirim file .webp ini ke WhatsApp untuk langsung digunakan sebagai stiker._"
        )

        await client.send_file(
            event.chat_id,
            file=temp_out,
            force_document=True,
            caption=caption,
            reply_to=reply_msg.id
        )
        await event.delete()

    except Exception as e:
        await event.edit(f"❌ **Gagal convert stiker ke WhatsApp:**\n```{str(e)}```")

    finally:
        for f_path in (temp_in, temp_out):
            if f_path and os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except Exception:
                    pass

    return True
