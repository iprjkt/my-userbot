"""
modules/ascii.py
Command .ascii - Ubah teks jadi ASCII art dengan pilihan font (pyfiglet).
"""

AVAILABLE_ASCII_FONTS = [
    "banner", "standard", "big", "slant", "small",
    "3-d", "block", "dotmatrix", "digital", "lean",
    "mini", "script", "letters"
]


def text_to_ascii_art(text, font="banner"):
    text = text.strip()
    if not text:
        return "❌ Masukkan teks yang ingin diubah."
    try:
        import pyfiglet
        figlet = pyfiglet.Figlet(font=font)
        return figlet.renderText(text)
    except ModuleNotFoundError:
        if font != "banner":
            return ("❌ Modul pyfiglet belum terpasang sehingga font tidak bisa dipilih.\n"
                    "Install dengan `pip install pyfiglet` lalu coba lagi.")
        return "\n".join(ch * 2 for ch in text.upper())
    except Exception as e:
        return f"❌ Gagal membuat ASCII art: {e}"


async def handle(event, client, txt, t_l):
    """Command .ascii [font] <teks>. Return True kalau ditangani."""
    if t_l.startswith(".ascii"):
        raw = txt[len(".ascii"):].strip()
        if not raw:
            await event.edit("❌ Format: `.ascii [font] <teks>`\nContoh: `.ascii slant Hello World`")
        else:
            parts = raw.split(None, 1)
            font = "banner"
            text = raw
            if parts[0].lower() in AVAILABLE_ASCII_FONTS and len(parts) > 1:
                font = parts[0].lower()
                text = parts[1]
            elif parts[0].lower().startswith("font="):
                font = parts[0].split("=", 1)[1]
                text = parts[1] if len(parts) > 1 else ""
            art = text_to_ascii_art(text, font)
            await event.edit(f"```\n{art}\n```")
        return True

    return False
