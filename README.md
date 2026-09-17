# 🚀 Akasha Userbot

Modern, powerful, and modular Telegram Userbot berbasis **Python** & **Telethon**. Dilengkapi dengan berbagai fitur otomasi, Android ROM & partition tooling, converter stiker WhatsApp, dan sistem manajemen akun Telegram.

---

## ✨ Fitur Unggulan

* 🖼️ **Kang Sticker (Unified Pack)**: Mencuri stiker foto, video, maupun GIF ke sticker pack Telegram pribadi. Stiker foto otomatis di-convert ke video WebM VP9 agar dapat bersatu dalam **satu pack yang sama**.
* 🟢 **Telegram to WhatsApp Sticker**: Konversi stiker/media Telegram ke stiker WhatsApp (`.webp`) dengan transparent padding 512×512 dan **WhatsApp EXIF Metadata** (Pack Name, Author, Emoji). Mendukung convert 1 pack utuh ke `.zip`.
* 📦 **Online Partition Unpacker (`.unpack`)**: Unpack file partisi Android (`.img`, `.img.xz`, `.img.zst`, dll.) secara online dari link atau reply, lalu mengambil **hanya file atau folder tertentu** tanpa harus mendownload/mengekstrak seluruh partisi. Mendukung **EROFS**, **EXT4**, dan **Android Sparse Image**.
* ⚡ **ROM Payload Dumper (`.dump`)**: Ekstraksi otomatis file `payload.bin` dari link ROM Android (Aria2c + payload-dumper-go) dan upload ke Pixeldrain/Gofile.
* 🛡️ **PM Security & Whitelist**: Otomatis membatasi chat PM dari orang asing dengan sistem whitelist (`.approve` / `.disapprove`).
* 💤 **Smart AFK System**: Otomatis membalas pesan saat Anda sedang AFK dan mencatat siapa saja yang mengirim pesan / mention saat Anda tidak aktif.
* 📊 **VPS System Info & Speedtest**: Monitor penggunaan CPU, RAM, disk storage, dan tes kecepatan bandwidth VPS secara live.
* 🎨 **ASCII Art Generator**: Mengubah teks biasa menjadi teks ASCII banner dengan puluhan pilihan font FIGlet.

---

## 📋 Daftar Command

### 📱 Stiker & Media
| Command | Deskripsi |
| :--- | :--- |
| `.kang [emoji] [pack]` | Curi stiker/foto/video ke sticker pack Telegram (foto di-convert jadi video agar 1 pack). |
| `.kang -s [emoji] [pack]` | Mode khusus untuk menyimpan stiker statis PNG ke pack gambar terpisah. |
| `.towa [pack] \| [author]` | Convert stiker/media Telegram yang di-reply ke stiker WhatsApp (`.webp`). |
| `.towapack [link/reply]` | Convert 1 pack stiker Telegram penuh menjadi file `.zip` stiker WhatsApp. |

### 🔧 Android & Partisi
| Command | Deskripsi |
| :--- | :--- |
| `.dump <link_rom> [partisi]` | Ekstrak partisi dari link ROM Android (default: `boot,vendor_boot,init_boot`). |
| `.dump <link_rom> -all` | Ekstrak seluruh partisi dari `payload.bin` ROM. |
| `.unpack <link> "<path>"` | Unpack file partisi `.img` online dan ambil file/folder tertentu (misal: `"/system/app/EasterEgg/EasterEgg.apk"` atau `"/system/framework/"`). |

### 🛡️ Keamanan & PM
| Command | Deskripsi |
| :--- | :--- |
| `.approve` | Whitelist PM user (bisa via Reply, ID, Username, atau langsung di ruang chat PM). |
| `.disapprove` | Cabut izin Whitelist PM user. |
| `.list` | Menampilkan daftar user yang ada di Whitelist PM. |
| `.afk <alasan>` | Mengaktifkan mode AFK (auto-reply mention & PM). |
| `.unafk` | Mematikan mode AFK dan menampilkan ringkasan pesan masuk. |

### ⚙️ Sistem & Utilitas
| Command | Deskripsi |
| :--- | :--- |
| `.info` | Menampilkan informasi hardware VPS, storage, OS, kernel, dan foto profil. |
| `.speedtest` | Menjalankan tes kecepatan internet VPS (Download & Upload). |
| `.ascii [font] <teks>` | Mengubah teks menjadi ASCII art dengan font tertentu (contoh: `.ascii slant Halo`). |
| `.restart` | Me-restart proses userbot secara otomatis. |
| `.log [n/file/clear]` | Melihat log sistem bot secara langsung untuk keperluan debugging. |
| `.help` | Menampilkan daftar ringkasan command bantuan. |

### 👥 Grup / Admin
| Command | Deskripsi |
| :--- | :--- |
| `.ban <reply/user>` | Ban member dari grup. |
| `.unban <reply/user>` | Unban member dari grup. |
| `.pin <reply>` | Sematkan (pin) pesan yang di-reply. |
| `.unpin <reply>` | Lepas sematan (unpin) pesan yang di-reply. |

---

## 🛠️ Instalasi & Setup

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

# Install payload-dumper-go (untuk fitur .dump)
go install github.com/ssut/payload-dumper-go@latest
sudo cp ~/go/bin/payload-dumper-go /usr/local/bin/
```

---

### 2. Konfigurasi Environment (`.env`)

Masuk ke folder project `tele-userbot` dan buat file konfigurasi `.env`:
```bash
cd tele-userbot
nano .env
```

Isi file `.env` dengan kredensial API Telegram Anda (didapatkan dari [my.telegram.org](https://my.telegram.org)):
```env
api_id=12345678
api_hash=abcdef0123456789abcdef0123456789
```

---

### 3. Install Python Dependencies

```bash
pip install -r requirements.txt
```

---

### 4. Menjalankan Userbot

Jalankan bot untuk pertama kali:
```bash
python3 main.py
```
> **Catatan:** Pada saat pertama kali dijalankan, Telethon akan meminta nomor telepon dan kode verifikasi Telegram (serta password 2FA jika aktif). Sesi login akan disimpan secara lokal di file `sesi_userbot.session`.

Untuk menjalankan di background server VPS secara permanen, gunakan `tmux`, `screen`, atau `systemd`:
```bash
# Contoh menggunakan tmux
tmux new -s userbot
python3 main.py
# Tekan Ctrl+B lalu D untuk detach
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
