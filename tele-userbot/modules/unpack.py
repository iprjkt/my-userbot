"""
modules/unpack.py
Command .unpack <link/reply> <target_path> - Unpack online partition image (.img, .img.xz, .img.zst, dll.)
dan ambil hanya file atau folder tertentu yang ada di dalam partisi tersebut.
Mendukung partisi EROFS, EXT4, dan Android Sparse Image.
"""

import os
import re
import time
import shlex
import shutil
import asyncio
import zipfile

from helpers.sys_info import make_progress_bar, run_shell
from helpers.uploader import upload_file_server_with_progress


def parse_unpack_args(txt):
    """Parsing URL dan target path dari command text."""
    urls = re.findall(r'https?://[^\s"\'<>]+', txt)
    url = urls[0] if urls else None

    # Parse token menggunakan shlex agar quote ditangani dengan rapi
    try:
        tokens = shlex.split(txt)
    except Exception:
        tokens = txt.split()

    targets = []
    for token in tokens[1:]:
        if url and token == url:
            continue
        targets.append(token)

    return url, targets


def detect_image_type(file_path: str) -> str:
    """Deteksi tipe partisi: sparse, erofs, ext4, atau unknown."""
    if not os.path.exists(file_path) or os.path.getsize(file_path) < 2048:
        return "unknown"

    with open(file_path, "rb") as f:
        header = f.read(2048)

    # Android sparse image magic: 0xED26FF3A (little-endian: 3a ff 26 ed)
    if len(header) >= 4 and header[:4] == b"\x3a\xff\x26\xed":
        return "sparse"

    # EROFS magic at offset 1024: 0xE0F5E1E2 (little-endian: e2 e1 f5 e0)
    if len(header) >= 1028 and header[1024:1028] == b"\xe2\xe1\xf5\xe0":
        return "erofs"

    # EXT4 magic at offset 1080: 0xEF53 (little-endian: 53 ef)
    if len(header) >= 1082 and header[1080:1082] == b"\x53\xef":
        return "ext4"

    return "unknown"


async def extract_target_erofs(img_path: str, target_path: str, out_dir: str):
    """Extract file atau folder spesifik dari image EROFS."""
    # Variasi path kandidat (dengan / tanpa prefix nama partisi)
    clean = target_path.strip().lstrip('/')
    candidates = [f"/{clean}"]
    parts = clean.split('/', 1)
    if len(parts) > 1:
        candidates.append(f"/{parts[1]}")

    found_path = None
    is_dir = False

    for cand in candidates:
        cmd = f"dump.erofs --path='{cand}' '{img_path}'"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        stdout, stderr = await proc.communicate()
        out_txt = stdout.decode('utf-8', errors='ignore')
        err_txt = stderr.decode('utf-8', errors='ignore')

        if "<E>" not in err_txt and "<E>" not in out_txt and "failed" not in out_txt.lower() and "failed" not in err_txt.lower():
            found_path = cand
            is_dir = "directory" in out_txt.lower()
            break

    if not found_path:
        raise Exception(f"Path `{target_path}` tidak ditemukan di dalam partisi EROFS.")

    basename = os.path.basename(found_path.rstrip('/')) or "extracted"
    target_out = os.path.join(out_dir, basename)

    if is_dir:
        os.makedirs(target_out, exist_ok=True)
        extract_cmd = f"fsck.erofs --overwrite --path='{found_path}' --extract='{target_out}' '{img_path}'"
    else:
        extract_cmd = f"fsck.erofs --overwrite --path='{found_path}' --extract='{target_out}' '{img_path}'"

    proc = await asyncio.create_subprocess_shell(
        extract_cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE
    )
    _, stderr = await proc.communicate()
    if proc.returncode != 0:
        err_msg = stderr.decode('utf-8', errors='ignore')
        raise Exception(f"Gagal mengekstrak EROFS: {err_msg[:200]}")

    return target_out, is_dir


async def extract_target_ext4(img_path: str, target_path: str, out_dir: str):
    """Extract file atau folder spesifik dari image EXT4 menggunakan 7z."""
    clean = target_path.strip().lstrip('/')
    candidates = [clean, clean.rstrip('/') + '/*']
    parts = clean.split('/', 1)
    if len(parts) > 1:
        candidates.append(parts[1])
        candidates.append(parts[1].rstrip('/') + '/*')

    temp_extract = os.path.join(out_dir, "temp_7z")
    os.makedirs(temp_extract, exist_ok=True)

    extracted_files = []

    for cand in candidates:
        cmd = f"7z x -y -o'{temp_extract}' '{img_path}' '{cand}'"
        proc = await asyncio.create_subprocess_shell(
            cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )
        await proc.communicate()

        found = []
        for root, dirs, files in os.walk(temp_extract):
            for f in files:
                found.append(os.path.join(root, f))
        if found:
            extracted_files = found
            break

    if not extracted_files:
        raise Exception(f"Path `{target_path}` tidak ditemukan di dalam partisi EXT4.")

    # Cek apakah target merupakan file tunggal atau direktori
    if len(extracted_files) == 1 and not target_path.endswith('/'):
        single_file = extracted_files[0]
        final_file = os.path.join(out_dir, os.path.basename(single_file))
        shutil.move(single_file, final_file)
        shutil.rmtree(temp_extract, ignore_errors=True)
        return final_file, False
    else:
        # Pindahkan isi yang diekstrak ke out_dir langsung
        basename = os.path.basename(clean.rstrip('/')) or "extracted"
        target_dir = os.path.join(out_dir, basename)
        os.makedirs(target_dir, exist_ok=True)

        for root, dirs, files in os.walk(temp_extract):
            for f in files:
                src = os.path.join(root, f)
                rel = os.path.relpath(src, temp_extract)
                dst = os.path.join(target_dir, rel)
                os.makedirs(os.path.dirname(dst), exist_ok=True)
                shutil.move(src, dst)

        shutil.rmtree(temp_extract, ignore_errors=True)
        return target_dir, True


async def handle(event, client, txt, t_l):
    """Command .unpack. Return True jika ditangani."""
    if not (t_l.startswith(".unpack") or t_l.startswith(".unimg")):
        return False

    url, targets = parse_unpack_args(txt)

    # Jika URL tidak ada di teks, cek apakah me-reply pesan dengan link atau file
    if not url and event.is_reply:
        reply_msg = await event.get_reply_message()
        if reply_msg:
            rep_text = reply_msg.raw_text or ""
            rep_urls = re.findall(r'https?://[^\s"\'<>]+', rep_text)
            if rep_urls:
                url = rep_urls[0]

    if not targets:
        await event.edit(
            "❌ **Target path tidak ditentukan!**\n\n"
            "**Contoh Penggunaan:**\n"
            "• `.unpack <link_partisi> \"/system/app/EasterEgg/EasterEgg.apk\"`\n"
            "• `.unpack <link_partisi> \"/system/framework/\"`\n"
            "• `.unpack <link_partisi> \"/system/build.prop\" \"/system/etc/\"`\n"
            "• *(Atau reply ke link/file partisi)*: `.unpack \"/system/build.prop\"`"
        )
        return True

    task_id = str(event.id)
    workspace = os.path.abspath(f"./unpack_workspace_{task_id}")
    out_dir = os.path.join(workspace, "output")
    os.makedirs(out_dir, exist_ok=True)

    targets_display = ", ".join(f"`{t}`" for t in targets)
    await event.edit(
        f"⏳ **Menyiapkan proses Unpack Partisi...**\n"
        f"🎯 **Target:** {targets_display}\n\n"
        f"1️⃣ **Mengunduh partisi...**"
    )

    downloaded_img = None

    try:
        # 1. Download File Partisi
        if url:
            # Download via cURL dengan live progress bar
            # Tentukan nama file sementara dari URL atau default
            url_clean = url.split("?")[0]
            ext = os.path.splitext(url_clean)[1] or ".img"
            dl_path = os.path.join(workspace, f"downloaded{ext}")

            cmd = f"curl -# -L -C - -o '{dl_path}' '{url}'"
            proc = await asyncio.create_subprocess_shell(
                cmd,
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
                        try:
                            await event.edit(
                                f"⏳ **Memproses Unpack Partisi...**\n"
                                f"🎯 **Target:** {targets_display}\n\n"
                                f"1️⃣ **Mengunduh Partisi...**\n"
                                f"`{p_bar}`"
                            )
                        except Exception:
                            pass

            await proc.wait()
            if proc.returncode != 0 or not os.path.exists(dl_path):
                raise Exception("Gagal mengunduh file partisi dari link.")

            downloaded_file = dl_path

        elif event.is_reply:
            reply_msg = await event.get_reply_message()
            if not reply_msg.media:
                raise Exception("Pesan yang di-reply tidak memiliki file atau link.")

            await event.edit(
                f"⏳ **Memproses Unpack Partisi...**\n"
                f"🎯 **Target:** {targets_display}\n\n"
                f"1️⃣ **Mengunduh media dari Telegram...**"
            )

            last_tg_update = 0

            async def tg_progress(current, total):
                nonlocal last_tg_update
                now = time.time()
                if now - last_tg_update >= 3 or current == total:
                    last_tg_update = now
                    pct = (current / total) * 100 if total else 0
                    p_bar = make_progress_bar(pct)
                    try:
                        await event.edit(
                            f"⏳ **Memproses Unpack Partisi...**\n"
                            f"🎯 **Target:** {targets_display}\n\n"
                            f"1️⃣ **Mengunduh dari Telegram...**\n"
                            f"`{p_bar}`"
                        )
                    except Exception:
                        pass

            temp_tg = os.path.join(workspace, "downloaded.img")
            downloaded_file = await client.download_media(reply_msg, file=temp_tg, progress_callback=tg_progress)
            if not downloaded_file or not os.path.exists(downloaded_file):
                raise Exception("Gagal mengunduh file dari Telegram.")
        else:
            raise Exception("Link partisi tidak ditemukan. Sertakan link atau reply ke pesan.")

        # 2. Dekompresi jika file terkompresi (.xz, .zst, .gz, .bz2, .zip, .7z)
        await event.edit(
            f"⏳ **Memproses Unpack Partisi...**\n"
            f"🎯 **Target:** {targets_display}\n\n"
            f"2️⃣ **Mengecek format arsip & dekompresi...**"
        )

        img_file = None
        # Cek apakah file adalah arsip kompresi
        with open(downloaded_file, "rb") as f:
            magic_4 = f.read(4)

        is_compressed = False
        if downloaded_file.endswith((".xz", ".zst", ".gz", ".bz2", ".zip", ".7z")):
            is_compressed = True
        elif magic_4 in (b"\xfd7zX", b"\x1f\x8b\x08", b"\x28\xb5\x2f", b"BZh", b"PK\x03\x04", b"7z\xbc\xaf"):
            is_compressed = True

        if is_compressed:
            await event.edit("⚙️ **Mengekstrak file arsip kompresi...**")
            unarchive_cmd = f"7z x -y -o'{workspace}' '{downloaded_file}'"
            await run_shell(unarchive_cmd)
            os.remove(downloaded_file)

            # Cari file .img di dalam workspace
            candidates = [os.path.join(workspace, f) for f in os.listdir(workspace) if f.endswith(".img")]
            if candidates:
                img_file = candidates[0]
            else:
                # Ambil file terbesar jika tidak berekstensi .img
                all_f = [os.path.join(workspace, f) for f in os.listdir(workspace) if os.path.isfile(os.path.join(workspace, f))]
                if all_f:
                    img_file = max(all_f, key=os.path.getsize)
                else:
                    raise Exception("Tidak ada file partisi (.img) ditemukan di dalam arsip.")
        else:
            img_file = downloaded_file

        # 3. Cek Android Sparse Image -> Convert ke Raw Image jika perlu
        fs_type = detect_image_type(img_file)
        if fs_type == "sparse":
            await event.edit(
                f"⏳ **Memproses Unpack Partisi...**\n"
                f"🎯 **Target:** {targets_display}\n\n"
                f"3️⃣ **Mengonversi Android Sparse Image ke Raw Image...**"
            )
            raw_img = os.path.join(workspace, "raw_converted.img")
            await run_shell(f"simg2img '{img_file}' '{raw_img}'")
            if os.path.exists(img_file):
                os.remove(img_file)
            img_file = raw_img
            fs_type = detect_image_type(img_file)

        await event.edit(
            f"⏳ **Mengekstrak target dari partisi (`{fs_type.upper()}`)...**\n"
            f"🎯 **Target:** {targets_display}"
        )

        # 4. Ekstraksi Target (EROFS atau EXT4/Lainnya)
        extracted_results = []
        for target in targets:
            try:
                if fs_type == "erofs":
                    res_path, is_dir = await extract_target_erofs(img_file, target, out_dir)
                elif fs_type == "ext4":
                    res_path, is_dir = await extract_target_ext4(img_file, target, out_dir)
                else:
                    # Coba EROFS terlebih dahulu, jika gagal coba EXT4 via 7z
                    try:
                        res_path, is_dir = await extract_target_erofs(img_file, target, out_dir)
                        fs_type = "erofs"
                    except Exception:
                        res_path, is_dir = await extract_target_ext4(img_file, target, out_dir)
                        fs_type = "ext4"

                extracted_results.append((res_path, is_dir, target))
            except Exception as e:
                extracted_results.append((None, False, f"{target} (Error: {str(e)})"))

        # Hapus file image setelah ekstraksi selesai untuk menghemat disk
        if os.path.exists(img_file):
            try:
                os.remove(img_file)
            except Exception:
                pass

        # Cek hasil ekstraksi
        successful = [r for r in extracted_results if r[0] is not None]
        if not successful:
            failed_info = "\n".join(f"• `{r[2]}`" for r in extracted_results)
            raise Exception(f"Gagal mengekstrak target:\n{failed_info}")

        # 5. Kemas & Kirim Hasil
        await event.edit("📦 **Menyiapkan hasil ekstraksi untuk dikirim...**")

        # Jika hanya 1 target dan berupa file tunggal: kirim langsung file tersebut
        if len(successful) == 1 and not successful[0][1]:
            final_file = successful[0][0]
            target_name = successful[0][2]
            f_size = os.path.getsize(final_file)
            f_size_mb = f_size / (1024 * 1024)
            f_name = os.path.basename(final_file)

            caption = (
                f"✅ **File Berhasil Di-Unpack dari Partisi!** 🚀\n\n"
                f"📄 **File:** `{f_name}` (`{f_size_mb:.2f} MB`)\n"
                f"🎯 **Target:** `{target_name}`\n"
                f"⚙️ **Filesystem:** `{fs_type.upper()}`"
            )

            # Jika ukuran file < 1.9 GB, kirim langsung via Telegram
            if f_size_mb < 1950:
                await event.edit(f"📤 **Mengunggah `{f_name}` ke Telegram...**")
                await client.send_file(
                    event.chat_id,
                    file=final_file,
                    caption=caption,
                    force_document=True
                )
                await event.delete()
            else:
                # Upload ke Pixeldrain/Gofile jika > 1.9 GB
                up_url = await upload_file_server_with_progress(final_file, event, 1, 1, f_name)
                await event.edit(f"{caption}\n\n🔗 **Download Link:** {up_url}")

        else:
            # Jika berupa folder atau banyak file: bungkus ke dalam ZIP
            clean_part_name = "partition"
            if url:
                raw_name = os.path.basename(url.split("?")[0])
                if raw_name:
                    clean_part_name = raw_name.split(".")[0]

            zip_filename = f"{clean_part_name}_extracted.zip"
            final_zip_path = os.path.join(workspace, zip_filename)

            total_items = 0
            with zipfile.ZipFile(final_zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                for res_path, is_dir, target_name in successful:
                    if is_dir:
                        base_folder = os.path.basename(res_path)
                        for root, dirs, files in os.walk(res_path):
                            for f in files:
                                full_f = os.path.join(root, f)
                                rel = os.path.relpath(full_f, res_path)
                                zipf.write(full_f, arcname=os.path.join(base_folder, rel))
                                total_items += 1
                    else:
                        zipf.write(res_path, arcname=os.path.basename(res_path))
                        total_items += 1

            zip_size = os.path.getsize(final_zip_path)
            zip_size_mb = zip_size / (1024 * 1024)

            caption = (
                f"✅ **Partisi Berhasil Di-Unpack & Di-ZIP!** 📦\n\n"
                f"📁 **Archive:** `{zip_filename}` (`{zip_size_mb:.2f} MB`)\n"
                f"📊 **Total File:** `{total_items}` file\n"
                f"🎯 **Target:** {targets_display}\n"
                f"⚙️ **Filesystem:** `{fs_type.upper()}`"
            )

            if zip_size_mb < 1950:
                await event.edit(f"📤 **Mengunggah `{zip_filename}` ke Telegram...**")
                await client.send_file(
                    event.chat_id,
                    file=final_zip_path,
                    caption=caption,
                    force_document=True
                )
                await event.delete()
            else:
                up_url = await upload_file_server_with_progress(final_zip_path, event, 1, 1, zip_filename)
                await event.edit(f"{caption}\n\n🔗 **Download Link:** {up_url}")

    except Exception as e:
        await event.edit(f"❌ **Gagal melakukan unpack partisi:**\n```{str(e)}```")

    finally:
        # Bersihkan direktori workspace
        if os.path.exists(workspace):
            try:
                shutil.rmtree(workspace, ignore_errors=True)
            except Exception:
                pass

    return True
