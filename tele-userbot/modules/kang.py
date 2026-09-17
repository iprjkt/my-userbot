"""
modules/kang.py
Command .kang - Curi stiker (gambar/video/GIF) dari pesan yang di-reply, buat/tambah ke sticker pack sendiri.
Mendukung penyatuan foto & video ke dalam satu sticker pack dengan mengonversi foto menjadi video sticker (WebM VP9).
"""

import os
import asyncio
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


async def handle(event, client, txt, t_l):
    """Command .kang. Return True kalau ditangani."""
    if not t_l.startswith(".kang"):
        return False

    if not event.is_reply:
        await event.edit("❌ **Reply ke stiker, foto, GIF, atau video yang mau dicuri Ngab!**")
        return True

    reply_msg = await event.get_reply_message()
    if not reply_msg.media:
        await event.edit("❌ **Pesan yang di-reply tidak mengandung media!**")
        return True

    # Cek stiker animasi TGS (Lottie vector) yang tidak kompatibel dengan video sticker
    if reply_msg.sticker:
        for attr in reply_msg.sticker.attributes:
            if getattr(attr, 'animated', False) and not getattr(attr, 'video', False):
                await event.edit(
                    "❌ **Stiker animasi TGS (.tgs Lottie) belum didukung untuk disatukan ke video pack.**\n"
                    "💡 _Gunakan stiker video, GIF, atau foto/gambar biasa._"
                )
                return True

    await event.edit("⏳ **Memproses & mencuri stiker...**")
    me = await client.get_me()

    # 1. Parse Argumen: [emoji] [pack_number] [-s/--static]
    raw_args = txt.split()[1:]
    pack_num = 1
    custom_emoji = None
    force_static = False

    for arg in raw_args:
        if arg in ("-s", "--static"):
            force_static = True
        elif arg.isdigit():
            pack_num = max(1, int(arg))
        else:
            custom_emoji = arg

    # Tentukan Emoji
    sticker_emoji = custom_emoji
    if not sticker_emoji and reply_msg.sticker:
        for attr in reply_msg.sticker.attributes:
            if hasattr(attr, 'alt') and attr.alt:
                sticker_emoji = attr.alt
                break
    if not sticker_emoji:
        sticker_emoji = "🤔"

    # 2. Cek Jenis Media (Video/GIF vs Gambar/Foto)
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

    # Jika force_static dan bukan video asli, buat stiker statis PNG
    is_static_mode = force_static and not is_anim_or_video

    temp_in = None
    temp_out = None
    temp_retry = None

    try:
        # 3. Download media langsung ke file disk
        temp_prefix = os.path.abspath(f"temp_kang_{event.id}")
        temp_in = await client.download_media(reply_msg, file=temp_prefix)
        if not temp_in or not os.path.exists(temp_in):
            raise Exception("Gagal mengunduh media dari pesan yang di-reply.")

        output_bio = BytesIO()

        # 4. Processing Media Sesuai Jenisnya
        if is_static_mode:
            # CONVERT TO PNG (Gambar Statis jika explicitly dipaksa via -s)
            output_bio.name = "sticker.png"
            mime_type = "image/png"
            img = Image.open(temp_in)
            img.seek(0)
            img.thumbnail((512, 512))
            img.save(output_bio, format="PNG")
            output_bio.seek(0)
            is_video_sticker = False
        else:
            # CONVERT TO WEBM (VP9, max 3s / 1s loop, <=256KB)
            # Menyatukan foto & video dalam 1 sticker pack dengan convert foto -> WebM VP9
            output_bio.name = "sticker.webm"
            mime_type = "video/webm"
            temp_out = os.path.abspath(f"temp_kang_out_{event.id}.webm")

            vf_scale = r"scale=if(gte(iw\,ih)\,512\,-2):if(gte(iw\,ih)\,-2\,512)"

            if is_anim_or_video:
                # Video / GIF asli: potong maksimal 3 detik, sesuaikan aspek rasio 512
                cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_in,
                    "-t", "3",
                    "-vf", vf_scale,
                    "-r", "30",
                    "-c:v", "libvpx-vp9",
                    "-pix_fmt", "yuva420p",
                    "-crf", "30",
                    "-b:v", "256k",
                    "-an",
                    temp_out
                ]
            else:
                # Foto / Stiker Statis: jadikan video WebM berdurasi 1 detik loop
                cmd = [
                    "ffmpeg", "-y",
                    "-loop", "1",
                    "-i", temp_in,
                    "-t", "1",
                    "-r", "30",
                    "-vf", vf_scale,
                    "-c:v", "libvpx-vp9",
                    "-pix_fmt", "yuva420p",
                    "-crf", "30",
                    "-b:v", "256k",
                    "-an",
                    temp_out
                ]

            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await proc.communicate()

            if not os.path.exists(temp_out) or os.path.getsize(temp_out) == 0:
                err_text = stderr.decode('utf-8', errors='ignore') if stderr else "Unknown error"
                raise Exception(f"Gagal mengonversi media ke format WEBM stiker: {err_text[-200:]}")

            # Kompresi ulang jika ukuran file melebihi batas Telegram (256 KB)
            if os.path.getsize(temp_out) > 256 * 1024:
                temp_retry = os.path.abspath(f"temp_kang_retry_{event.id}.webm")
                retry_cmd = [
                    "ffmpeg", "-y",
                    "-i", temp_out,
                    "-t", "3",
                    "-c:v", "libvpx-vp9",
                    "-crf", "38",
                    "-b:v", "150k",
                    "-an",
                    temp_retry
                ]
                proc2 = await asyncio.create_subprocess_exec(
                    *retry_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                await proc2.communicate()
                if os.path.exists(temp_retry) and 0 < os.path.getsize(temp_retry) <= 256 * 1024:
                    os.replace(temp_retry, temp_out)

            with open(temp_out, "rb") as f:
                output_bio.write(f.read())
            output_bio.seek(0)
            is_video_sticker = True

        # 5. Upload dokumen stiker
        uploaded_file = await client.upload_file(output_bio)
        uploaded_media = await client(UploadMediaRequest(
            peer="me",
            media=InputMediaUploadedDocument(
                file=uploaded_file,
                mime_type=mime_type,
                attributes=[
                    DocumentAttributeFilename(file_name=output_bio.name),
                    DocumentAttributeSticker(alt=sticker_emoji, stickerset=InputStickerSetEmpty())
                ]
            )
        ))

        doc = uploaded_media.document
        input_doc = InputDocument(id=doc.id, access_hash=doc.access_hash, file_reference=doc.file_reference)
        sticker_item = InputStickerSetItem(document=input_doc, emoji=sticker_emoji)

        added = False
        username_str = f"_by_{me.username}" if me.username else f"_by_id{me.id}"
        prefix = "kang" if is_static_mode else "kang_vid"
        title_prefix = "Kang" if is_static_mode else "Video/Mixed Kang"

        while not added:
            pack_short_name = f"{prefix}_{me.id}_v{pack_num}{username_str}"
            pack_title = f"@{me.username or me.first_name}'s {title_prefix} Pack v{pack_num}"

            try:
                await client(AddStickerToSetRequest(
                    stickerset=InputStickerSetShortName(short_name=pack_short_name),
                    sticker=sticker_item
                ))
                added = True
            except Exception as e:
                err_msg = str(e).lower()
                if "invalid" in err_msg or "stickerset" in err_msg or "does not exist" in err_msg:
                    # Buat pack baru dengan fallback kompatibilitas parameter versi Telethon
                    try:
                        await client(CreateStickerSetRequest(
                            user_id=me.id, title=pack_title, short_name=pack_short_name,
                            stickers=[sticker_item], videos=is_video_sticker
                        ))
                    except TypeError:
                        try:
                            await client(CreateStickerSetRequest(
                                user_id=me.id, title=pack_title, short_name=pack_short_name,
                                stickers=[sticker_item], video=is_video_sticker
                            ))
                        except TypeError:
                            await client(CreateStickerSetRequest(
                                user_id=me.id, title=pack_title, short_name=pack_short_name,
                                stickers=[sticker_item]
                            ))
                    added = True
                elif "too much" in err_msg or "full" in err_msg or "occupy" in err_msg:
                    pack_num += 1
                else:
                    raise e

        # Kategori tipe tampilan
        if is_anim_or_video:
            media_label = "Video"
        elif is_static_mode:
            media_label = "Gambar Statis"
        else:
            media_label = "Foto ➔ Video"

        await event.edit(
            f"✅ **Stiker ({media_label}) berhasil dicuri!** {sticker_emoji}\n"
            f"🔗 **Pack:** [Klik Untuk Buka Sticker Pack](https://t.me/addstickers/{pack_short_name})",
            link_preview=False
        )

    except Exception as e:
        await event.edit(f"❌ **Gagal mencuri stiker:**\n```{str(e)}```")

    finally:
        # Bersihkan file temporary
        for f_path in (temp_in, temp_out, temp_retry):
            if f_path and os.path.exists(f_path):
                try:
                    os.remove(f_path)
                except Exception:
                    pass

    return True
