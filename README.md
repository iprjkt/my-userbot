## 🛠️ Panduan Instalasi & Setup

### 1. Prasyarat Paket Sistem

Pastikan paket pendukung sistem operasi sudah terpasang:

#### Ubuntu / Debian
```bash
sudo apt update && sudo apt install -y \
    python3 python3-pip python3-venv \
    ffmpeg p7zip-full aria2 unzip curl \
    erofs-utils android-sdk-libsparse-utils golang-go

# Install payload-dumper-go (dibutuhkan untuk fitur .dump payload ROM)
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

### 2. Setup Direktori & Python Environment

Masuk ke folder `tele-userbot`:
```bash
cd my-userbot/tele-userbot
```

*(Opsional tapi disarankan)* Buat dan aktifkan Virtual Environment:
```bash
python3 -m venv venv
source venv/bin/activate
```

Install seluruh dependensi Python:
```bash
pip install -r requirements.txt
```

---

### 3. Konfigurasi Kredensial (.env)

Dapatkan `api_id` dan `api_hash` akun Telegram Anda melalui [my.telegram.org](https://my.telegram.org) (bagian *API development tools*).

Buat file `.env` di dalam folder `tele-userbot/`:
```bash
nano .env
```

Isi dengan kredensial Anda:
```env
api_id=12345678
api_hash=0123456789abcdef0123456789abcdef
```

---

### 4. Bypass Bot Verification YouTube (PO Token & Cookies)

YouTube menerapkan proteksi ketat (*Proof of Origin / PO Token*) terhadap IP VPS / Datacenter:

1. **Auto PO Token (Sudah Terpasang & Otomatis Aktif):**
   - Userbot sudah terintegrasi dengan plugin `yt-dlp-get-pot-rustypipe` dan binary `rustypipe-botguard` di `~/.local/bin`.
   - Plugin ini otomatis menghasilkan PO Token yang valid setiap kali mengambil data video/audio, sehingga IP VPS tidak dicegat verifikasi bot.
   - *(Catatan instalasi baru jika pindah VPS)*:
     ```bash
     curl -sL "https://codeberg.org/ThetaDev/rustypipe-botguard/releases/download/v0.1.2/rustypipe-botguard-v0.1.2-x86_64-unknown-linux-gnu.tar.xz" | tar -xJ -C ~/.local/bin/
     chmod +x ~/.local/bin/rustypipe-botguard
     ```

2. **(Opsional) Cookies YouTube untuk Video Age-Restricted / Login:**
   - Untuk video yang mewajibkan login akun (konten 18+, private, atau channel membership):
   - Buka browser tempat Anda login YouTube, ekspor format Netscape dengan ekstensi seperti **Get cookies.txt LOCALLY**.
   - Simpan file sebagai `cookies.txt` di dalam folder `tele-userbot/`.
   - Userbot akan otomatis mendeteksi cookies tersebut saat dibutuhkan.

---

### 5. Menjalankan Userbot

#### A. Login Pertama Kali (Generate Session)
Jalankan bot secara langsung di terminal untuk melakukan login pertama:
```bash
python3 main.py
```
Masukkan nomor telepon Telegram Anda (format internasional, misal: `+62812xxxxxxx`) dan masukkan kode OTP login yang dikirimkan ke Telegram. Sesi login akan tersimpan otomatis di file `sesi_userbot.session`.

#### B. Menjalankan di Background VPS (via Tmux)
Agar bot tetap berjalan terus meski terminal / SSH ditutup:
```bash
# Buat session tmux baru
tmux new -s tele

# Jalankan userbot
python3 main.py
```
- **Keluar dari tampilan tmux tanpa mematikan bot:** Tekan `Ctrl + B`, lalu tekan tombol `D` (*detach*).
- **Melihat / membuka kembali sesi bot:**
  ```bash
  tmux attach -t tele
  ```
- **Mematikan bot di tmux:**
  Buka kembali sesi (`tmux attach -t tele`), lalu tekan `Ctrl + C`.

---

## 📁 Struktur Direktori

```text
my-userbot/
├── README.md
├── fetch.sh
└── tele-userbot/
    ├── main.py                  # Entry point, loader, & event dispatcher
    ├── requirements.txt         # Daftar dependency Python
    ├── .env                     # Kredensial API Telegram (api_id, api_hash)
    ├── cookies.txt              # (Opsional) Cookies YouTube untuk bypass limit bot
    ├── helpers/
    │   ├── db.py                # Database JSON & dotenv loader
    │   ├── sys_info.py          # VPS stats, progress bar, & command runner
    │   └── uploader.py          # Uploader cloud Pixeldrain & Gofile
    └── modules/
        ├── admin.py             # Admin tools (ban, unban, pin, unpin)
        ├── afk.py               # Sistem AFK & auto-logger mention/PM
        ├── approve.py           # Whitelist PM & anti-spam
        ├── ascii.py             # ASCII art generator (pyfiglet)
        ├── dumper.py            # Android payload.bin dumper
        ├── info.py              # VPS info, speedtest, & help menu
        ├── kang.py              # Kang stiker (foto + video unified)
        ├── log.py               # System logger & log viewer
        ├── tiktok.py            # Scraper & downloader TikTok (no watermark, audio, slide)
        ├── towa.py              # Telegram to WhatsApp sticker converter
        ├── unpack.py            # Online partition image unpacker (.img)
        └── youtube.py           # YouTube video downloader, audio mp3, & search
```

---

## 📋 Ringkasan Perintah Cepat

| Perintah | Fungsi |
| :--- | :--- |
| `.info` | Menampilkan spesifikasi VPS, RAM, Disk, dan Uptime |
| `.speedtest` | Menjalankan uji kecepatan internet VPS |
| `.tt <link>` | Download video TikTok tanpa watermark / slide album foto |
| `.tt -a <link>` / `.ttmp3` | Download audio/musik TikTok (.mp3) |
| `.yt <link> [resolusi]` | Download video YouTube MP4 (default: best up to 1080p) |
| `.yta <link>` / `.ytmp3` | Download audio YouTube (.mp3 192k) + cover art |
| `.yts <query>` | Mencari video di YouTube (menampilkan 5 hasil teratas) |
| `.kang [emoji]` | Curi stiker / ubah media jadi stiker pack Telegram |
| `.towa [pack]` | Konversi stiker Telegram ke stiker WhatsApp (.webp) |
| `.dump <link> [partisi]` | Ekstrak partisi dari link ROM Android (payload.bin) |
| `.unpack <link> <path>` | Unpack partisi `.img` secara online & ambil file target |
| `.afk <alasan>` | Mengaktifkan mode AFK dengan auto-reply |
| `.unafk` | Mematikan mode AFK |
| `.approve` / `.disapprove`| Whitelist / cabut izin chat di PM |
| `.restart` | Muat ulang (*restart*) proses userbot |
| `.log` | Melihat log sistem userbot secara langsung |
| `.help` | Menampilkan seluruh menu bantuan |

---

## 📜 Lisensi
Proyek ini dibuat untuk penggunaan pribadi dan edukasi. Bebas dimodifikasi sesuai kebutuhan Anda.
