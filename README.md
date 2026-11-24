<p align="center">
  <img src="assets/banner.png" alt="ios-inspect: Debug Safari iPhone langsung dari Linux" width="100%">
</p>

# ios-inspect-linux

Debug website di **Safari iPhone** dan **WKWebView** langsung dari **Linux**, tanpa Mac.
Tampilannya Chrome DevTools biasa: Console, Network, Elements, Sources.

```
iPhone (Safari)  ──USB──▶  ios-inspect  ──▶  Chrome DevTools di Linux
```

> Biasanya Web Inspector untuk iOS hanya ada di Safari macOS. `ios-inspect` memakai
> [pymobiledevice3](https://github.com/doronz88/pymobiledevice3) untuk terhubung ke layanan
> Web Inspector di iPhone lewat USB, lalu menampilkannya di Chrome/Chromium.

## Fitur

- **Console**: lihat `console.log` / error dari iPhone, jalankan JavaScript langsung di halaman.
- **Network**: request, response, header, status, timing.
- **Elements**: inspect DOM dan ubah CSS secara live.
- **Sources**: lihat file JS dan pasang breakpoint.
- **Satu perintah**: menunggu iPhone, menjalankan bridge, dan membuka browser otomatis.
- **Sambung ulang otomatis**: kalau kabel tercabut, cukup colok lagi.
- **`ios-inspect doctor`**: cek setup dan beri tahu apa yang perlu diperbaiki.

Sudah dicoba di iPhone XR dengan iOS 18.7, Pop!_OS (Ubuntu 24.04), dan Python 3.12.

## Kebutuhan

| Kebutuhan | Keterangan |
|---|---|
| Linux | Diuji di Ubuntu/Pop!_OS; distro lain yang punya `usbmuxd` seharusnya bisa |
| Python 3.9+ | |
| `usbmuxd` | Daemon USB untuk iPhone (`sudo apt install usbmuxd`) |
| Chrome / Chromium | Untuk menampilkan DevTools |
| iPhone + kabel data | Kabel yang hanya untuk charging tidak bisa dipakai |
| Internet | UI DevTools diambil dari internet saat dibuka |

## Instalasi

```bash
# 1. Pasang usbmuxd
sudo apt install usbmuxd

# 2. Pasang ios-inspect di virtualenv
python3 -m venv ~/.venvs/ios-inspect
~/.venvs/ios-inspect/bin/pip install git+https://github.com/raisulkhairi/ios-inspect-linux.git

# 3. (Opsional) supaya bisa dipanggil cukup dengan `ios-inspect`
mkdir -p ~/.local/bin
ln -s ~/.venvs/ios-inspect/bin/ios-inspect ~/.local/bin/ios-inspect
```

Atau dengan [pipx](https://pipx.pypa.io/):

```bash
pipx install git+https://github.com/raisulkhairi/ios-inspect-linux.git
```

## Persiapan iPhone (sekali saja)

1. Buka **Settings → Apps → Safari → Advanced**, aktifkan **Web Inspector**.
   (iOS 17 ke bawah: **Settings → Safari → Advanced → Web Inspector**.)
2. Colok iPhone ke laptop, buka kuncinya, lalu tap **Trust** saat muncul *"Trust This Computer?"*.

## Cara pakai

```bash
ios-inspect
```

Lalu:

1. Buka website yang mau di-debug di **Safari iPhone**.
2. Browser terbuka otomatis di `http://127.0.0.1:9222/` dan menampilkan daftar halaman.
3. **Klik judul halaman** (teks biru). DevTools akan terbuka.
4. Selesai: tekan `Ctrl+C` di terminal.

Contoh output:

```
Terhubung: iPhone (iPhone11,8, iOS 18.7.12, USB)
Web Inspector siap: http://127.0.0.1:9222/  (1 halaman bisa di-inspect)
Klik judul halaman untuk membuka DevTools. Ctrl+C untuk berhenti.
```

> **Tips:** di tab **Network**, refresh halaman di iPhone setelah DevTools terbuka
> supaya semua request dari awal ikut tertangkap.

### Perintah lain

| Perintah | Fungsi |
|---|---|
| `ios-inspect` | Jalankan Web Inspector (sama dengan `ios-inspect start`) |
| `ios-inspect doctor` | Cek usbmuxd, iPhone, Web Inspector, dan browser |
| `ios-inspect pages` | Tampilkan tab Safari yang bisa di-inspect |
| `ios-inspect devices` | Tampilkan iPhone yang tercolok |

### Opsi `start`

| Opsi | Fungsi |
|---|---|
| `--port 9333` | Ganti port (default `9222`) |
| `--no-browser` | Jangan buka browser otomatis |
| `--no-reconnect` | Keluar saat iPhone terputus |
| `--pause-new-targets` | Hentikan tiap JSContext baru di statement pertamanya |
| `-v`, `--verbose` | Tampilkan log bridge (untuk melacak masalah) |
| `--udid <UDID>` | Pilih iPhone tertentu jika lebih dari satu (taruh sebelum subcommand) |
| `--browser <nama>` | Pakai browser tertentu, misalnya `--browser chromium` |

### Debug aplikasi (WKWebView)

Halaman WKWebView di aplikasi iOS bisa di-inspect kalau aplikasinya mengaktifkan:

```swift
webView.isInspectable = true   // iOS 16.4+
```

### Pakai dari VS Code

Jalankan `ios-inspect --no-browser`, lalu tambahkan ke `.vscode/launch.json`:

```json
{
  "type": "chrome",
  "request": "attach",
  "name": "iPhone Safari",
  "address": "127.0.0.1",
  "port": 9222,
  "urlFilter": "*",
  "webRoot": "${workspaceFolder}"
}
```

## Troubleshooting

Jalankan `ios-inspect doctor` dulu. Masalah yang umum:

| Gejala | Solusi |
|---|---|
| `Menunggu iPhone dicolok...` terus | Colok ulang atau ganti port/kabel, buka kunci iPhone, tap **Trust**. Cek dengan `lsusb \| grep -i apple`. |
| Daftar halaman kosong | Pastikan Web Inspector aktif, buka website di Safari, iPhone tidak terkunci, lalu refresh daftar. |
| `iPhone terputus` | Kabel sempat lepas. Colok lagi; `ios-inspect` menyambung otomatis. |
| DevTools tampil putih | Periksa koneksi internet (UI DevTools diunduh saat dibuka). |
| Console macet saat log sangat banyak | Buka DevTools dari `http://127.0.0.1:9222/`, bukan dari `chrome://inspect`. |
| Port 9222 sudah dipakai | `ios-inspect start --port 9333` |

## Keterbatasan

- iOS Simulator tidak bisa (butuh Xcode/macOS).
- Hanya mendukung koneksi USB; debug lewat Wi-Fi belum diuji.
- Apple bisa mengubah protokol Web Inspector di versi iOS baru. Kalau ada yang rusak,
  coba perbarui pymobiledevice3: `pip install -U pymobiledevice3`.

## Cara kerja

`ios-inspect` adalah launcher di atas perintah `pymobiledevice3 webinspector cdp`:

1. Menunggu iPhone muncul di `usbmuxd`.
2. Menjalankan bridge yang menerjemahkan protokol WebKit Inspector ke Chrome DevTools Protocol
   di `127.0.0.1:9222`.
3. Membuka browser ke halaman daftar target.
4. Kalau iPhone terputus, menunggu sampai dicolok lagi lalu menjalankan ulang bridge.

## Lisensi

[GPL-3.0-or-later](LICENSE). Proyek ini memakai
[pymobiledevice3](https://github.com/doronz88/pymobiledevice3) (GPL-3.0).
