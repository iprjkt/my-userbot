"""
helpers/sys_info.py
Helper untuk menjalankan shell command dan mengambil info spek VPS/device.
"""

import asyncio
import subprocess
import platform
import time
import psutil


async def run_shell(cmd):
    """Jalankan command shell secara async, raise Exception kalau gagal."""
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


def make_progress_bar(percent, length=10):
    """Buat progress bar berbasis karakter blok Unicode."""
    percent = max(0.0, min(100.0, percent))
    filled = int(length * percent / 100)
    bar = "█" * filled + "░" * (length - filled)
    return f"[{bar}] {percent:.1f}%"


def get_afk_time(since):
    """Format durasi AFK jadi teks bahasa Indonesia (detik/menit/jam/hari)."""
    diff = int(time.time() - since)
    if diff < 60:
        return f"{diff} detik"
    m = diff // 60
    if m < 60:
        return f"{m} menit"
    h = m // 60
    m = m % 60
    if h < 24:
        return f"{h} jam {m} menit"
    d = h // 24
    h = h % 24
    return f"{d} hari {h} jam"


async def get_stats_text(user_name):
    """Kumpulkan info RAM, disk, network, OS, kernel, uptime -> format string."""
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
        os_ver = subprocess.check_output(
            "/system/bin/getprop ro.build.version.release 2>/dev/null", shell=True
        ).decode().strip()
        if not os_ver:
            os_ver = subprocess.check_output(
                "grep -m1 'ro.build.version.release=' /system/build.prop 2>/dev/null | cut -d= -f2",
                shell=True
            ).decode().strip()
        if not os_ver:
            raise Exception
        distro = f"Android {os_ver}"
    except Exception:
        try:
            ubuntu_name = subprocess.check_output(
                "lsb_release -ds 2>/dev/null", shell=True
            ).decode().strip().replace('"', '')
            raw_kernel = platform.release()
            distro = f"{ubuntu_name}"
            kernel_ver = "-".join(raw_kernel.split("-")[:3])
        except Exception:
            distro = f"{platform.system()} {platform.release()}"

    try:
        p = await asyncio.create_subprocess_shell("uptime -p", stdout=asyncio.subprocess.PIPE)
        out, _ = await p.communicate()
        up = out.decode().replace("up ", "").strip()
    except Exception:
        up = "Unknown"

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
