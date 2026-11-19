# Analisa Teknikal: cara pasang

Analisa teknikal otomatis untuk saham IDX, saham AS, kripto, indeks, dan forex. Ada tiga bagian:

- **Panel** di browser (`http://127.0.0.1:8768`): **Cek aset** (ketik ticker, pilih timeframe) dan **Daftar pantau** (ticker pilihanmu sendiri, dianalisa sekaligus).
- **Ekstensi browser**: saat membuka chart di TradingView, Stockbit, Binance, Yahoo Finance, dan lainnya, muncul kartu skor kecil, analisa lengkap di panel samping, dan (di TradingView) garis support/resistance dan rencana langsung di chart.
- Semua tampilan tersedia dalam bahasa Indonesia dan Inggris (tombol **ID | EN**).

Program berjalan di komputermu sendiri. Ia hanya menarik harga dari Yahoo Finance dan Binance, tidak perlu login atau akun apa pun, dan tidak mengirim data ke tempat lain. Hasilnya analisa otomatis, **bukan rekomendasi investasi**.

## 1. Ekstrak folder

Ekstrak `Analisa Teknikal.zip` (dari orang yang membagikan, atau dari tautan unduhan GitHub yang diberikannya), lalu pindahkan foldernya ke tempat tetap dan beri nama **Analisa Teknikal**, misalnya folder Dokumen. Jangan menjalankannya dari dalam zip atau dari folder Unduhan yang sering dibersihkan: ekstensi browser membaca folder ini terus-menerus.

## 2. Pasang Python (sekali saja)

**Mac**

1. Unduh Python dari [python.org/downloads](https://www.python.org/downloads/) dan pasang.
2. Buka **Terminal**, jalankan:

   ```
   pip3 install numpy yfinance matplotlib
   ```

**Windows**

1. Unduh Python dari [python.org/downloads](https://www.python.org/downloads/). Saat memasang, **centang "Add python.exe to PATH"**.
2. Buka **Command Prompt**, jalankan:

   ```
   py -m pip install numpy yfinance matplotlib tzdata
   ```

## 3. Nyalakan panel

**Mac**: klik dua kali **Analisa Teknikal.app** di dalam folder.

Pertama kali, macOS biasanya menolak karena aplikasinya tidak berasal dari App Store ("tidak dapat dibuka" / "tidak dapat diverifikasi"). Caranya:

1. Klik **Selesai** di pesan itu.
2. Buka **Pengaturan Sistem → Privasi & Keamanan**, gulir ke bawah, klik **Tetap Buka** di baris Analisa Teknikal, lalu konfirmasi.
3. Klik dua kali Analisa Teknikal.app lagi.

Kalau tombol itu tidak muncul, buka Terminal dan jalankan (sesuaikan lokasinya):

```
xattr -dr com.apple.quarantine ~/Documents/"Analisa Teknikal"
```

**Windows**: klik dua kali **Analisa Teknikal (Windows).bat**. Kalau muncul "Windows protected your PC", klik **More info → Run anyway**.

Panel terbuka di browser. Panel tetap jalan di latar sampai komputer dimatikan atau logout. Klik peluncurnya lagi kapan saja untuk memulai ulang (misalnya setelah memperbarui program).

## 4. Pasang ekstensi (Chrome, Edge, Brave)

1. Buka halaman ekstensi: `chrome://extensions` (Edge: `edge://extensions`, Brave: `brave://extensions`).
2. Nyalakan **Developer mode**.
3. Klik **Load unpacked**, lalu pilih folder `ekstensi` di dalam folder Analisa Teknikal.
4. Pin ikonnya di toolbar (ikon puzzle → pin "Analisa Teknikal").

Jangan memindah atau menghapus folder Analisa Teknikal setelah ini; kalau dipindah, ulangi Load unpacked. Browser kadang menampilkan peringatan soal ekstensi mode developer saat dibuka: abaikan saja (pilih tetap pakai).

## 5. Pakai

- **Cek aset**: ketik ticker lalu Enter. Contoh: `BBCA`, `IDX:ADRO`, `NVDA`, `BTC`, `IHSG`, `EURUSD`. Pilih timeframe 5m sampai 1M.
- **Daftar pantau**: tulis ticker yang ingin dipantau (pisahkan koma, mis. `BBCA, TLKM, NVDA, BTC`), klik **Simpan & pindai**. Hasilnya: skor, sinyal, support/resistance, rencana tindakan, dan blok **Hari ini** untuk yang perlu dilihat dulu. Klik baris untuk membuka chart. Klik **Pindai ulang** untuk harga terbaru.
- **Ekstensi**: buka chart di TradingView (atau situs lain yang didukung). Kartu kecil muncul di kiri bawah; klik **Buka analisa lengkap** atau ikon ekstensi untuk panel samping. Tombol kotak di kanan atas panel samping membuka analisa di tab layar penuh.

Cara membaca skor: −100 (sangat bearish) sampai +100 (sangat bullish); ≥ 50 bullish kuat, 20…49 bullish, −19…19 netral, −49…−20 bearish, ≤ −50 bearish kuat. Tombol **?** di atas chart menjelaskan arti setiap garis. Penjelasan lengkap ada di `README.md`.

## Kalau ada masalah

- Ikon ekstensi menulis **off**, atau panel samping menulis "Panel lokal belum jalan": jalankan peluncurnya (langkah 3).
- Panel tidak mau menyala: lihat `output/panel.log` (Windows: `output/panel_galat.log`) di folder Analisa Teknikal, lalu kirim isinya ke orang yang membagikan program ini.
- "Belum ada Python dengan numpy": ulangi langkah 2.

## Memperbarui ke versi baru

**Otomatis.** Setiap kali peluncur dibuka (langkah 3), program memeriksa versi terbaru di GitHub. Kalau ada, versi itu langsung dipasang sebelum panel menyala, dan ekstensi browser memuat ulang dirinya sendiri. Kamu tidak perlu melakukan apa-apa. Daftar pantau dan pilihan bahasa tetap aman. Kalau sedang tidak ada internet, program jalan dengan versi yang sudah ada.

- Versi yang terpasang tertulis di `VERSI.txt`. Riwayat pembaruan ada di `output/perbarui.log`.
- Berkas yang tertimpa pada pembaruan terakhir disimpan di folder `_lama/`.
- Setelah ekstensi memuat ulang dirinya, kartu di tab chart yang sudah terbuka baru muncul lagi setelah tab itu dimuat ulang.

**Manual** (hanya kalau GitHub tidak bisa dijangkau): ekstrak zip yang baru, salin isinya ke folder Analisa Teknikal yang lama, pilih **Ganti / Replace** untuk semua berkas, lalu klik dua kali peluncurnya.
