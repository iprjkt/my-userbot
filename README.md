## 🛠️ Installation & Setup

### 1. Prasyarat Sistem

#### Ubuntu / Debian
```bash
sudo apt update && sudo apt install -y \
    python3 python3-pip python3-venv \
    ffmpeg p7zip-full aria2 unzip curl \
    erofs-utils android-sdk-libsparse-utils golang-go

# Install payload-dumper-go (untuk fitur .dump)
go install github.com/ssut/payload-dumper-go@latest
sudo cp ~/go/bin/payload-dumper-go /usr/local/bin/
```

#### Arch Linux
```bash
sudo pacman -S --needed \
    python python-pip \
    ffmpeg 7zip aria2 unzip curl \
    erofs-utils android-tools go

# Install payload-dumper-go
go install github.com/ssut/payload-dumper-go@latest
sudo cp ~/go/bin/payload-dumper-go /usr/local/bin/
```

---

### 2. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

## 📁 Struktur Direktori

```text
my-userbot/
├── README.md
└── tele-userbot/
    ├── main.py                  # Entry point & event dispatcher
    ├── requirements.txt         # Daftar dependency Python
    ├── .env                     # Kredensial API Telegram
    ├── helpers/
    │   ├── db.py                # Database JSON & dotenv loader
    │   ├── sys_info.py          # VPS stats & command runner
    │   └── uploader.py          # Uploader Pixeldrain & Gofile
    └── modules/
        ├── admin.py             # Admin tools (ban, unban, pin, unpin)
        ├── afk.py               # Sistem AFK & auto-logger
        ├── approve.py           # Whitelist PM & anti-spam
        ├── ascii.py             # ASCII art generator (pyfiglet)
        ├── dumper.py            # Android payload.bin dumper
        ├── info.py              # VPS info, speedtest, & help menu
        ├── kang.py              # Kang stiker (foto + video unified)
        ├── log.py               # System logger & log viewer
        ├── towa.py              # Telegram to WhatsApp sticker converter
        └── unpack.py            # Online partition image unpacker
```

---

## 📜 Lisensi
Proyek ini dibuat untuk penggunaan pribadi dan edukasi. Bebas dimodifikasi sesuai kebutuhan Anda.
