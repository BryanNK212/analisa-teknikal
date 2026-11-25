# Analisa Teknikal

Analisa teknikal otomatis untuk **saham IDX, saham AS, kripto, indeks, dan forex**, berjalan di komputer sendiri (Mac atau Windows). Tersedia dalam **bahasa Indonesia dan Inggris**.

> Hasilnya analisa otomatis dari data harga, **bukan rekomendasi investasi**. Keputusan jual-beli tetap tanggung jawab masing-masing.

## Isinya

1. **Panel di browser** (`http://127.0.0.1:8768`)
   - **Cek aset**: ketik ticker apa saja, pilih timeframe 5m, 15m, 30m, 1h, 4h, 1D, 1W, atau 1M.
   - **Skor beli 0–100**: seberapa layak dibeli sekarang dari sisi teknikal (tren 1D+1W, lokasi harga, imbal hasil vs risiko, kekuatan vs pasar, momentum & volume). Juga muncul sebagai kolom di Daftar pantau dan di kartu ekstensi. Bukan jaminan dan tidak menghitung valuasi atau berita.
   - **Kesimpulan semua timeframe**: di tab Ringkasan, skor dan rencana 1H, 4H, 1D, 1W, 1M berdampingan, satu **skor gabungan** (rata-rata tertimbang; 1D dan 1W paling berat), kesimpulan arah jangka pendek/menengah/panjang, dan saran langkah dengan level dari timeframe 1D.
   - **Pemindai IHSG**: semua saham BEI yang cukup likuid (nilai transaksi rata-rata 20 hari ≥ Rp1 M, harga ≥ Rp50, aktif ≥ 15 dari 20 hari) dianalisa sekaligus; tanda yang baru muncul dibanding hari bursa sebelumnya diberi label Baru. Jalan saat tombol diklik dan otomatis sekali tiap hari bursa setelah 16:30 WIB selama panel menyala; jumlah tanda baru muncul di tab dan di ikon ekstensi. Pindai pertama butuh beberapa menit. Atur di `pengaturan.json` (`ihsg_otomatis`, `ihsg_jam`, `ihsg_saringan`).
   - **Daftar pantau**: ticker pilihanmu sendiri, dianalisa sekaligus dalam satu tabel.
2. **Ekstensi browser** (Chrome, Edge, Brave, Arc) untuk TradingView, Stockbit, Binance, Tokocrypto, Indodax, Bybit, OKX, Yahoo Finance, dan Google Finance. Saat kamu membuka chart, ekstensi membaca simbolnya, lalu menampilkan kartu skor kecil di halaman itu dan analisa lengkap di panel samping. Di TradingView, garis support/resistance, rencana, trendline, dan pola juga digambar langsung di atas chart.
3. **Tombol ID | EN** untuk mengganti bahasa di semua tampilan sekaligus. Pilihan bahasa diingat.

## Memasang

Langkah lengkapnya ada di **[PANDUAN_PASANG.md](PANDUAN_PASANG.md)**. Ringkasnya:

1. Unduh zip repo ini (**Code → Download ZIP**), ekstrak ke tempat tetap (mis. Documents), lalu beri nama folder **Analisa Teknikal**.
2. Pasang Python dari [python.org](https://www.python.org/downloads/). Di Windows, centang **"Add python.exe to PATH"**. Lalu jalankan sekali:
   - Mac (Terminal): `pip3 install numpy yfinance matplotlib`
   - Windows (Command Prompt): `py -m pip install numpy yfinance matplotlib tzdata`
3. Klik dua kali peluncurnya: **Analisa Teknikal.app** (Mac) atau **Analisa Teknikal (Windows).bat** (Windows). Panel terbuka di browser.
4. Ekstensi (opsional): buka `chrome://extensions`, nyalakan **Developer mode**, klik **Load unpacked**, lalu pilih folder `ekstensi`.

## Pembaruan otomatis

Setiap kali peluncur dibuka, program memeriksa versi terbaru di repo ini. Kalau ada, versi itu langsung dipasang sebelum panel menyala, dan ekstensi memuat ulang dirinya sendiri. Daftar pantau dan pilihan bahasa tetap aman. Kalau tidak ada internet, pemeriksaan dilewati.

- Versi yang terpasang tertulis di `VERSI.txt`, riwayat pembaruan di `output/perbarui.log`.
- Berkas yang tertimpa pada pembaruan terakhir disimpan di folder `_lama/`.
- Pemeriksaan pembaruan hanya saat peluncur dibuka.

## Memakai panel

**Cek aset.** Ketik ticker lalu tekan Enter. Format TradingView juga bisa:

| Pasar | Contoh |
|---|---|
| Saham IDX | `BBCA`, `IDX:ADRO` |
| Saham AS | `NVDA`, `NASDAQ:AAPL` |
| Kripto | `BTC`, `BINANCE:SOLUSDT` |
| Indeks | `IHSG`, `SPX` |
| Forex | `EURUSD` |

Tekan `/` di mana saja untuk langsung mengetik ticker. Arahkan kursor ke candle mana pun untuk melihat O/H/L/C, volume, MA, RSI, dan MACD di candle itu.

Hasil analisa dibagi tiga tab:

- **Ringkasan**: rencana tindakan, analisa tertulis, hal yang perlu diperhatikan, dan skor per timeframe.
- **Level & pola**: rencana, support/resistance, dan pola chart.
- **Sinyal**: komposisi skor, daftar sinyal, dan indikator.

**Daftar pantau.** Tulis ticker yang ingin dipantau (pisahkan dengan koma, mis. `BBCA, TLKM, NVDA, BTC`), lalu klik **Simpan & pindai**. Hasilnya satu tabel berisi skor, perubahan 1 minggu, garis skor 30 hari, kekuatan dibanding pasar, S1/R1, sinyal, dan langkah singkat. Di atasnya ada blok **Hari ini** untuk aset yang perlu dilihat dulu. Klik baris untuk membuka chartnya, dan klik **Pindai ulang** untuk harga terbaru.

**Garis di chart.** Support/resistance (S1–S3, R1–R3), garis rencana (**Area beli**, **Stop**, **Konfirmasi naik**, **Target**), trendline, dan bentuk pola berikut targetnya. Tiap jenis garis bisa dinyalakan/dimatikan lewat tombol MA · S/R · Rencana · Trendline · Pola · Volume. Tombol **?** menjelaskan arti setiap garis.

**Rencana tindakan.** Satu kalimat sikap, lalu 2–3 langkah *jika … maka …* dengan harga dan jaraknya dari harga sekarang. Contohnya:

- **Tren turun**: baru menyusun rencana beli kalau close di atas **Konfirmasi naik**. Sebelum itu, belum saatnya beli.
- **Tren naik**: harga di **Area beli** → beli bertahap; close di bawah **Stop** → rencana batal; mencapai **Target 1** → area mengamankan sebagian keuntungan.
- **Arah belum jelas**: tunggu close di atas pemicu naik atau di bawah pemicu turun.

**Stop** dan **Konfirmasi naik** dihitung dari harga *close* (penutupan candle), bukan harga sesaat.

## Ekstensi browser

1. Buka chart di salah satu situs yang didukung.
2. Kartu kecil muncul di kiri bawah halaman: skor, label, S1/R1, tanda penting, dan satu baris rencana. Kartu bisa diseret, dikecilkan, atau disembunyikan. Untuk mematikannya di semua situs: klik kanan ikon ekstensi → hilangkan centang **Tampilkan kartu analisa di halaman chart**.
3. Klik **Buka analisa lengkap** atau ikon ekstensi untuk membuka panel samping. Tombol kotak di kanan atas panel samping membuka analisa di tab layar penuh.
4. Ganti simbol atau timeframe di situsnya, dan kartu serta panel ikut berganti. Matikan sakelar **Ikuti chart** kalau ingin mengetik ticker sendiri.

| Situs | Dibaca dari | Timeframe |
|---|---|---|
| TradingView | chart dan halaman simbol | ikut chart |
| Stockbit | `stockbit.com/symbol/BBCA` | pilih di panel |
| Binance, Tokocrypto | halaman trade spot/futures | pilih di panel |
| Indodax | `indodax.com/market/BTCIDR` | pilih di panel |
| Bybit, OKX | halaman trade | pilih di panel |
| Yahoo Finance | halaman quote/chart | pilih di panel |
| Google Finance | halaman quote | pilih di panel |

Badge di ikon: angka hijau = bullish, merah = bearish, kuning = netral, **off** = panel belum jalan (jalankan peluncurnya).

Catatan:

- Garis di chart hanya ada di TradingView. Garis itu lapisan gambar milik ekstensi: tidak menjadi drawing TradingView, tidak tersimpan di layout, dan tidak bisa diklik.
- Pasangan rupiah (mis. BTC/IDR di Indodax) dianalisa lewat pasangan USDT, jadi levelnya dalam dolar.
- Timeframe TradingView dibulatkan ke yang terdekat (mis. 3m → 5m, 2h → 1h).

## Cara membaca

**Skor −100 sampai +100**

| Skor | Arti |
|---|---|
| ≥ 50 | bullish kuat |
| 20…49 | bullish |
| −19…19 | netral |
| −49…−20 | bearish |
| ≤ −50 | bearish kuat |

- Label "kuat" butuh tren yang kuat (ADX ≥ 25) atau konfirmasi dari momentum/pola.
- Bila skor bullish tapi tren 50 bar masih turun (atau sebaliknya), labelnya **Bullish awal (tren masih turun)** / **Bearish awal (tren masih naik)** dan skornya dibatasi ±49.
- **Komposisi skor** menunjukkan kategori mana (tren, momentum, volume, pola, breakout, support/resistance) yang menaikkan atau menekan skor. Jumlah semua baris = skor.
- **Konfluensi**: skor di timeframe yang lebih tinggi. Skor yang searah lebih bisa dipercaya.
- **Istilah teknis** bergaris titik-titik: sorot atau klik untuk membaca artinya dalam bahasa awam.

**Tanda**

- Segitiga merah: pola bearish terkonfirmasi, atau trendline naik yang baru jebol.
- Lingkaran oranye (!): jebol low 20 hari, death cross, divergence bearish, atau harga tidak bergerak.
- Centang hijau: sinyal positif.
- Lingkaran abu-abu (i): info.

**Lainnya**

- **Rencana**: area beli, stop, dan target dihitung dari support/resistance dan ATR. Untuk saham IDX, rencana turun berarti belum saatnya beli, bukan short.
- **Pola chart**: target yang sudah terlewati ditulis "sudah tercapai" dan bobotnya dikurangi.
- **Harga dolar**: ≥ $1.000 tanpa sen, $1–$999 dua desimal, di bawah $1 empat angka penting.
- **Candle yang masih berjalan** (bursa masih buka) ditandai **Berjalan**. Volumenya diproyeksikan ke satu sesi penuh, dan pola candlestick di candle itu baru dihitung setelah close.
- **Data intraday** (5m–4h) dari Yahoo Finance: 5m sampai 30 hari, 15m sampai 60 hari, dan 1h/4h sampai 2 tahun. Untuk saham IDX, data intraday kadang tertunda.

**Pola candlestick** (41 pola, bullish dan bearish dihitung terpisah):

- 1 candle: Doji, Dragonfly Doji, Gravestone Doji, Long-legged Doji, Spinning Top, Hammer, Hanging Man, Shooting Star, Inverted Hammer, Marubozu, Belt Hold
- 2 candle: Engulfing, Piercing Line, Dark Cloud Cover, Harami, Harami Cross, Tweezer Top/Bottom, Kicker
- 3 candle: Morning/Evening Star, Morning/Evening Doji Star, Abandoned Baby, Three White Soldiers, Three Black Crows, Three Inside Up/Down, Three Outside Up/Down
- 4–5 candle: Three Line Strike, Rising/Falling Three Methods

Bobot tiap pola melihat konteksnya: lokasi (dekat support/resistance atau MA), volume, dan konfirmasi dari candle berikutnya.

## Privasi

Program berjalan sepenuhnya di komputermu. Yang diambil dari internet hanya data harga (Yahoo Finance dan Binance) dan pemeriksaan versi baru di repo ini. Tidak perlu login atau akun apa pun, dan tidak ada data yang dikirim ke tempat lain. Ekstensi hanya membaca simbol di situs pada tabel di atas, dan hanya bicara dengan panel lokal (`127.0.0.1`).

## Pengaturan (`pengaturan.json`)

Dibuat otomatis saat pertama jalan.

- `tambahan_pantau`: isi daftar pantau, dalam format Yahoo (mis. `["BBCA.JK", "NVDA", "BTC-USD"]`). Biasanya diisi dari panel.
- `periode`: panjang data harga harian (default `2y`).
- `kurs_cadangan`: kurs USD/IDR cadangan bila kurs gagal ditarik.
- `bahasa`: `id` atau `en`. Diisi otomatis saat tombol ID / EN diklik.
- `folder_portfolio`: biarkan kosong.

## Kalau ada masalah

- Ikon ekstensi menulis **off**, atau panel samping menulis "Panel lokal belum jalan": jalankan peluncurnya.
- Panel tidak mau menyala: lihat `output/panel.log` (Windows: `output/panel_galat.log`).
- Komputer yang baru dinyalakan bisa butuh hingga sekitar satu menit sebelum browser terbuka. Bila halaman sempat menulis "Panel lokal mati", tunggu sebentar: halaman tersambung dan memuat ulang sendiri.
- "Belum ada Python dengan numpy": ulangi langkah pemasangan Python.

## Isi folder

| Berkas | Isi |
|---|---|
| `panel.py` | server panel lokal (port 8768) |
| `ta_engine.py` | mesin analisa (indikator, support/resistance, tren, pola, skor, rencana) |
| `wawasan.py` | analisa tertulis, rencana tindakan, kekuatan relatif, riwayat skor |
| `bahasa.py`, `web/bahasa.js` | versi bahasa Inggris |
| `teknikal.py` | pemindai daftar pantau |
| `uji_skor.py` | uji keandalan skor pada data lama (manual) |
| `perbarui.py`, `rilis.json` | pembaruan otomatis dari repo ini |
| `web/` | tampilan panel |
| `ekstensi/` | ekstensi browser |
| `Analisa Teknikal.app` | peluncur Mac |
| `Analisa Teknikal (Windows).bat`, `windows/` | peluncur Windows |

Font Fira Sans/Fira Code memakai lisensi SIL Open Font License (`web/LISENSI-FONT.txt`). Grafik interaktif memakai TradingView Lightweight Charts™ (Apache License 2.0, `web/lw.js`).

---

Analisa teknikal otomatis, bukan rekomendasi investasi.
