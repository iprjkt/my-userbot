"""
modules/kang.py
Command .kang - Curi stiker (gambar/video/GIF) dari pesan yang di-reply, buat/tambah ke sticker pack sendiri.
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

    await event.edit("⏳ **Memproses & mencuri stiker...**")
    me = await client.get_me()

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

    # 2. Cek Jenis Media (Video/GIF vs Gambar Statis)
    is_video = False
    if reply_msg.video or reply_msg.gif or (reply_msg.document and reply_msg.document.mime_type.startswith("video/")):
        is_video = True
    elif reply_msg.sticker:
        for attr in reply_msg.sticker.attributes:
            if hasattr(attr, 'video') and attr.video:
                is_video = True
                break

    try:
        # 3. Download media ke memori
        bio = BytesIO()
        await client.download_media(reply_msg, file=bio)
        bio.seek(0)

        output_bio = BytesIO()

        # 4. Processing Media Sesuai Jenisnya
        if is_video:
            # CONVERT TO WEBM (VP9, max 3s, 512x512, <=256KB)
            output_bio.name = "sticker.webm"
            mime_type = "video/webm"

            temp_in = os.path.join("./", f"temp_kang_{event.id}.mp4")
            temp_out = os.path.join("./", f"temp_kang_{event.id}.webm")

            with open(temp_in, "wb") as f:
                f.write(bio.getvalue())

            # ffmpeg: potong max 3s, resize 512x512, encode VP9 tanpa audio
            ffmpeg_cmd = (
                f"ffmpeg -y -i '{temp_in}' -t 3 "
                f"-vf 'scale=512:512:force_original_aspect_ratio=decrease' "
                f"-c:v libvpx-vp9 -crf 30 -b:v 256k -an '{temp_out}'"
            )
            proc = await asyncio.create_subprocess_shell(
                ffmpeg_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            await proc.communicate()

            if os.path.exists(temp_out):
                with open(temp_out, "rb") as f:
                    output_bio.write(f.read())
                output_bio.seek(0)
                os.remove(temp_out)
            else:
                raise Exception("Gagal mengonversi video/GIF ke format WEBM stiker.")

            if os.path.exists(temp_in):
                os.remove(temp_in)
        else:
            # CONVERT TO PNG (Gambar Statis)
            output_bio.name = "sticker.png"
            mime_type = "image/png"
            img = Image.open(bio)
            img.seek(0)
            img.thumbnail((512, 512))
            img.save(output_bio, format="PNG")
            output_bio.seek(0)

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

        pack_num = 1
        added = False
        username_str = f"_by_{me.username}" if me.username else f"_by_id{me.id}"
        prefix = "kang_vid" if is_video else "kang"
        title_prefix = "Video Kang" if is_video else "Kang"

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
                    # Buat pack baru dengan fallback kompatibilitas versi Telethon
                    if is_video:
                        try:
                            await client(CreateStickerSetRequest(
                                user_id=me.id, title=pack_title, short_name=pack_short_name,
                                stickers=[sticker_item], videos=True
                            ))
                        except TypeError:
                            try:
                                await client(CreateStickerSetRequest(
                                    user_id=me.id, title=pack_title, short_name=pack_short_name,
                                    stickers=[sticker_item], video=True
                                ))
                            except TypeError:
                                await client(CreateStickerSetRequest(
                                    user_id=me.id, title=pack_title, short_name=pack_short_name,
                                    stickers=[sticker_item]
                                ))
                    else:
                        await client(CreateStickerSetRequest(
                            user_id=me.id, title=pack_title, short_name=pack_short_name,
                            stickers=[sticker_item]
                        ))
                    added = True
                elif "too much" in err_msg or "full" in err_msg:
                    pack_num += 1
                else:
                    raise e

        await event.edit(
            f"✅ **Stiker ({'Video' if is_video else 'Gambar'}) berhasil dicuri!** {sticker_emoji}\n"
            f"🔗 **Pack:** [Klik Untuk Buka Sticker Pack](https://t.me/addstickers/{pack_short_name})",
            link_preview=False
        )

    except Exception as e:
        await event.edit(f"❌ **Gagal mencuri stiker:**\n```{str(e)}```")

    return True
