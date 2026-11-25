/* Analisa Teknikal — bahasa tampilan (Indonesia / Inggris).
   Dimuat sebelum portofolio.js dan panel.js. Teks asli ditulis dalam bahasa Indonesia; ATB.t("teks") mengembalikan
   padanan Inggrisnya bila bahasa = "en" (kamus EN di bawah), atau teks itu sendiri bila tidak ada padanannya.
   Bahasa ditentukan sekali saat halaman dimuat (ganti bahasa = muat ulang halaman):
     window.AT_BAHASA (laporan statis)  →  ?bahasa= di alamat  →  localStorage "at.bahasa"  →  "id"
   Sumber kebenarannya ada di server (pengaturan.json); panel.js menyamakannya lewat /api/status.
   Teks hasil analisa (sinyal, analisa tertulis, nama pola, catatan rencana) diterjemahkan di server (bahasa.py). */
(function (root) {
  "use strict";
  const EN = {
    // ---------- kepala & navigasi ----------
    "Cek aset": "Check asset", "Portofolio": "Portfolio", "Halaman": "Pages", "Ikuti chart": "Follow chart", "Ikuti lagi": "Follow again",
    "Sinyal mana yang berguna?": "Which signals are useful?", "Perubahan harga 20 hari saat kategori sinyal itu bullish dikurangi saat bearish (poin persen). Positif (hijau) = searah dengan hasil; sekitar nol atau merah = di pasar itu kategori ini tidak membantu.": "20-day price change when that signal category is bullish minus when it is bearish (percentage points). Positive (green) = in line with the outcome; near zero or red = the category does not help in that market.", "Kategori sinyal": "Signal category", "bullish {a} hari · bearish {b} hari": "bullish {a} days · bearish {b} days", "Seberapa sering rencananya terjadi?": "How often does the plan play out?", "Dari semua hari ketika rencana itu muncul: mana yang lebih dulu terjadi dalam {n} bar sesudahnya.": "Of all the days that plan appeared: which happened first within the next {n} bars.", "{n} hari": "{n} days", "target 1 dulu": "target 1 first", "stop dulu": "stop first", "belum keduanya": "neither yet", "turun ke target turun 1": "fell to target down 1", "konfirmasi naik dulu": "reversal up first",
    "Belum saatnya beli": "Not time to buy yet", "Area beli · R:R rendah": "Buy zone · low R:R", "Target turun": "Target down", "poin skor": "score points", "poin skor · kiri bearish, kanan bullish": "score points · bearish left, bullish right", "{n} keterangan lain (tidak mengubah skor)": "{n} other notes (no effect on the score)", "bobot": "weight", "Juga dekat level keputusan:": "Also near a decision level:", "unggulnya melebar": "lead widening", "unggulnya menyusut": "lead narrowing", "mulai mengejar": "catching up", "makin tertinggal": "falling further behind", "mulai unggul": "starting to outperform", "mulai tertinggal": "starting to lag", "Perkiraan tujuan harga bila tekanan turun berlanjut": "Estimated price objective if selling continues", "Jarak": "Distance", "Disentuh": "Touched", "Berapa kali harga berbalik di level ini": "How many times price turned at this level", "sudah tercapai": "already reached", "Skor dibatasi ±49 selama tren 50 bar masih berlawanan arah.": "The score is capped at ±49 while the 50-bar trend still points the other way.", "Analisa otomatis, bukan rekomendasi investasi. Harga: Yahoo Finance / Binance. Chart:": "Automated analysis, not investment advice. Prices: Yahoo Finance / Binance. Chart:", "Di atas harga, saat tren turun: close di atasnya = tren turun dianggap selesai. Sebelum itu, belum saatnya beli atau menambah.": "Above price, in a downtrend: a close above it = the downtrend is considered over. Until then it is not time to buy or add.", "Terakhir dilihat": "Recently viewed", "Contoh": "Examples",
    "Daftar pantau": "Watchlist", "Ticker yang dipantau": "Tickers to watch", "pisahkan dengan koma, mis. BBCA, TLKM, NVDA, BTC": "separate with commas, e.g. BBCA, TLKM, NVDA, BTC", "Simpan & pindai": "Save & scan", "Mengecek ticker…": "Checking tickers…", "Tidak ditemukan: {daftar}": "Not found: {daftar}", "Daftar pantau kosong.": "The watchlist is empty.", "Tersimpan {n} ticker.": "Saved {n} tickers.", "Belum ada ticker yang dipantau.": "No tickers on the watchlist yet.", "Tulis ticker di atas lalu klik Simpan & pindai. Hasilnya tampil di sini: skor, sinyal, support/resistance, dan rencana tindakan tiap ticker. Daftar ini hanya untuk analisa; tidak ada data portofolio yang dibaca.": "Type tickers above and click Save & scan. The results appear here: score, signals, support/resistance and an action plan for each ticker. This list is for analysis only; no portfolio data is read.", "ticker": "tickers", "skor rata-rata": "average score", "ticker dipantau": "tickers watched", "Semua ticker": "All tickers", "Skor −100…+100 dari tren, momentum, volume, pola, trendline, dan support/resistance (harian; mingguan untuk konfluensi). Bukan rekomendasi investasi.": "Score −100…+100 from trend, momentum, volume, patterns, trendlines and support/resistance (daily; weekly for confluence). Not investment advice.", "{n} ticker lain: tidak ada tanda baru dan harganya masih jauh dari level keputusan — cukup pantau, tidak perlu aksi hari ini.": "{n} other tickers: no new flags and the price is still far from a decision level — just keep watching, no action needed today.", "Buka analisa ini di tab layar penuh": "Open this analysis in a full-screen tab",
    "Ikuti simbol (dan timeframe, bila situsnya memberi) dari chart yang sedang dibuka: TradingView, Stockbit, Binance, Yahoo Finance, dll.":
      "Follow the symbol (and timeframe, when the site provides it) of the chart you have open: TradingView, Stockbit, Binance, Yahoo Finance, etc.",
    "Menghubungkan…": "Connecting…", "Terhubung": "Connected", "Mode offline (cache)": "Offline mode (cache)", "Panel lokal mati": "Local panel is off",
    "Bahasa": "Language", "Ganti bahasa ke Inggris": "Switch language to English", "Ganti bahasa ke Indonesia": "Switch language to Indonesian",
    "Cari aset": "Search asset", "Ticker: BBCA, NVDA, BTC, IHSG, IDX:TLKM": "Ticker: BBCA, NVDA, BTC, IHSG, IDX:TLKM",
    "Pasar": "Market", "Pasar otomatis": "Auto market", "Saham IDX": "IDX stocks", "Saham/ETF AS": "US stocks/ETFs", "Kripto": "Crypto",
    "Indeks/forex": "Index/forex", "Analisa": "Analyse", "Terakhir": "Recent",
    // ---------- kepala aset & chart ----------
    "Berjalan": "Live", "Candle terakhir belum selesai": "The latest candle is not finished", "Lapisan chart": "Chart layers",
    "Garis support (S) dan resistance (R)": "Support (S) and resistance (R) lines",
    "Garis rencana: area masuk, batal, target": "Plan lines: entry zone, stop / invalid level, targets",
    "Rencana": "Plan", "Pola": "Patterns", "Kontrol chart": "Chart controls",
    "Perkecil (lihat lebih banyak bar)": "Zoom out (show more bars)", "Perkecil": "Zoom out",
    "Perbesar (lihat lebih sedikit bar)": "Zoom in (show fewer bars)", "Perbesar": "Zoom in",
    "Kembali ke tampilan awal": "Back to the default view", "Tampilan awal": "Default view",
    "Tinggikan chart": "Make the chart taller", "Kecilkan chart": "Make the chart shorter",
    "Perubahan dari bar sebelumnya": "Change from the previous bar", "berjalan": "live", "Memuat": "Loading",
    // ---------- hasil ----------
    "Hasil analisa": "Analysis result", "Ringkasan skor": "Score summary", "Bagian analisa": "Analysis sections",
    "Ringkasan": "Summary", "Level & pola": "Levels & patterns", "Sinyal": "Signals",
    "Analisa tertulis": "Written analysis", "Perlu diperhatikan": "Worth watching", "Per timeframe": "By timeframe", "Skor per timeframe": "Score by timeframe",
    "Support & resistance": "Support & resistance", "jarak dari harga": "distance from price",
    "Tidak ada pola chart atau candlestick yang menonjol saat ini.": "No notable chart or candlestick pattern right now.",
    "Komposisi skor": "Score breakdown", "bearish · bullish": "bearish · bullish", "kontribusi ke skor": "contribution to the score", "Indikator": "Indicators",
    "Analisa teknikal otomatis, bukan rekomendasi investasi. Harga dari Yahoo Finance / Binance, ditarik langsung oleh komputer ini. Chart:":
      "Automated technical analysis, not investment advice. Prices from Yahoo Finance / Binance, fetched directly by this computer. Chart:",
    "Candle {mana} belum selesai (±{persen}% berjalan). Volume dihitung proyeksi, pola candle terakhir belum dihitung.":
      "{mana} candle is not finished (±{persen}% elapsed). Volume is projected and the latest candle's pattern is not counted yet.",
    "hari ini": "Today's", "terakhir": "The latest",
    "Beli saat koreksi": "Buy on pullback", "Lemah": "Weak", "Hindari menambah": "Avoid adding", "Tunggu konfirmasi": "Wait for confirmation",
    "Area masuk": "Entry zone", "Garis rencana: area beli, stop / konfirmasi naik, target": "Plan lines: buy zone, stop / reversal up, targets", "Rentang harga untuk membeli bila tren mendukung (rencana beli).": "Price range to buy in when the trend is supportive (buy plan).", "Area tambah": "Add zone", "Batal bila close di bawah": "Invalid on a close below", "Target {n}": "Target {n}", "Support {n}": "Support {n}",
    "Bearish batal bila close di atas": "Bearish view invalid on a close above", "Range": "Range",
    "Menguat bila close di atas": "Bullish on a close above", "Melemah bila close di bawah": "Bearish on a close below",
    "Harga": "Price", "naik": "rising", "turun": "falling", "ditembus": "broken", "target": "target",
    "High 52 mg": "52-wk high", "Low 52 mg": "52-wk low", "× rata-rata": "× average", " (proyeksi)": " (projected)", "bar": "bars",
    "Skor {n} {satuan} terakhir": "Score, last {n} {satuan}", "hari": "days", "minggu": "weeks", "bulan": "months",
    // ---------- keadaan ----------
    "Cek aset apa saja": "Check any asset",
    "Saham IDX, saham/ETF AS, kripto, indeks, atau forex. Format TradingView seperti": "IDX stocks, US stocks/ETFs, crypto, indices, or forex. TradingView format such as",
    "juga bisa.": "also works.", "Tekan": "Press", "untuk langsung mengetik ticker.": "to type a ticker right away.",
    "Menarik data harga {q}…": "Fetching price data for {q}…", "Menarik {q}…": "Fetching {q}…",
    "Ticker tidak ditemukan": "Ticker not found", "Data tidak bisa diambil": "Couldn't fetch the data",
    "Saham IDX cukup kodenya (BBCA). Kripto: BTC atau BINANCE:BTCUSDT. Indeks: IHSG, SPX.": "For IDX stocks just the code (BBCA). Crypto: BTC or BINANCE:BTCUSDT. Indices: IHSG, SPX.",
    "Coba lagi": "Try again", "Tidak ditemukan": "Not found", "Gagal": "Failed", "Gagal menganalisa.": "Analysis failed.",
    "Panel lokal tidak merespons. Jalankan peluncur Analisa Teknikal, lalu coba lagi.": "The local panel is not responding. Run the Analisa Teknikal launcher, then try again.",
    "skor": "score", "Mulai": "Start", "Ketik ticker di atas, atau pilih contoh.": "Type a ticker above, or pick an example.",
    // ---------- panel samping (ikut chart) ----------
    "Buka chart di TradingView, Stockbit, Binance, Yahoo Finance, dll. Simbolnya terbaca otomatis.": "Open a chart on TradingView, Stockbit, Binance, Yahoo Finance, etc. The symbol is read automatically.",
    "Mengikuti chart di {situs}: {q}": "Following the chart on {situs}: {q}", "Chart di {situs}:": "Chart on {situs}:",
    "Tidak mengikuti chart": "Not following the chart",
    // ---------- portofolio (panel) ----------
    "Memuat portofolio…": "Loading portfolio…", "panel lokal tidak merespons": "the local panel is not responding",
    "Belum pernah dipindai.": "Never scanned yet.", "Pindai portofolio": "Scan portfolio", "Pindai ulang": "Rescan",
    "Pemindaian menarik harga live semua posisi di folder portofolio (baca-saja) lalu menganalisa satu per satu, sekitar satu menit.":
      "A scan fetches live prices for every position in the portfolio folder (read-only) and analyses them one by one; it takes about a minute.",
    "Portofolio tidak bisa dimuat": "Couldn't load the portfolio",
    "Data sudah diperbarui · membuat {n} chart…": "Data updated · drawing {n} charts…", "Menganalisa…": "Analysing…", "Menarik harga…": "Fetching prices…",
    "Pemindaian gagal — lihat output/log.txt": "Scan failed — see output/log.txt", "Pemindaian selesai.": "Scan finished.", "Pemindaian portofolio selesai.": "Portfolio scan finished.",
    // ---------- portofolio (tabel & laporan) ----------
    "Baru": "New", "sejak": "since", "AS": "US", "kripto": "crypto", "indeks/forex": "index/forex",
    "Skor {n} bar: dari {a} ke {b}": "Score over {n} bars: from {a} to {b}",
    "lebih kuat": "stronger", "lebih lemah": "weaker", "sejalan": "in line", "aset": "asset",
    "Harga sangat dekat level ini": "Price is very close to this level", "dekat": "near",
    "Penting": "Important", "Waspada": "Caution", "Positif": "Positive", "Netral": "Neutral",
    "Aset": "Asset", "Bobot": "Weight", "Skor": "Score", "30 hari": "30 days", "vs pasar": "vs market", "Sinyal utama": "Top signal",
    "posisi": "positions", "dipindai": "scanned", "posisi dari": "positions from", "{n} aset memakai harga cache": "{n} assets use cached prices",
    "Candle hari ini belum selesai untuk {pasar} — volume diproyeksikan, pola candle hari ini belum dihitung.":
      "Today's candle is not finished for {pasar} — volume is projected and today's candle patterns are not counted yet.",
    "skor rata-rata, ditimbang nilai": "average score, weighted by value", "nilai saham, ETF & kripto": "value of stocks, ETFs & crypto",
    "Sebaran": "Distribution", "nilai": "of value", "netral": "neutral", "aset dengan tanda baru": "assets with new flags", "dibanding": "vs",
    "dari {n} posisi lebih lemah dari pasarnya (20 hari)": "of {n} positions weaker than their market (20 days)", "posisi dekat support": "positions near support",
    "Tanpa data harga:": "No price data:", "Semua posisi": "All positions",
    "klik baris untuk membuka chart interaktif": "click a row to open the interactive chart", "klik baris untuk chart dan detail": "click a row for the chart and details",
    "Saring posisi": "Filter positions", "Semua": "All", "Hanya yang ada tanda baru": "Only those with new flags", "Buka": "Open",
    "Skor per sektor": "Score by sector", "ditimbang nilai posisi": "weighted by position value", "Sektor": "Sector", "Posisi": "Positions", "Nilai": "Value", "Porsi": "Share",
    "Pantauan": "Watchlist", "belum dipegang": "not held",
    "Skor −100…+100 dari tren MA dan struktur swing, momentum, divergence, volume, breakout, pola chart dan candle, trendline, serta posisi terhadap support/resistance (harian; mingguan untuk konfluensi). Nilai dan P/L untuk konteks saja — angka resmi tetap dari tracker. Bukan rekomendasi investasi.":
      "Score −100…+100 from MA trend and swing structure, momentum, divergence, volume, breakouts, chart and candle patterns, trendlines, and position relative to support/resistance (daily; weekly for confluence). Value and P/L are for context only — the official figures come from the tracker. Not investment advice.",
    "Tidak ada posisi untuk saringan ini.": "No positions match this filter.",
    "Candle hari ini masih berjalan": "Today's candle is still forming", "(candle berjalan)": "(live candle)", "Harga rata-rata": "Average price",
    "Berubah {d} dibanding pindai {tgl}": "Changed {d} vs the {tgl} scan", "Berubah {d} sejak pindai sebelumnya": "Changed {d} since the previous scan",
    "+{n} sinyal lain": "+{n} more signals", "Tidak ada tanda": "No flags",
    "Skor {n} hari terakhir": "Score, last {n} days",
    "Buka gambar ukuran penuh": "Open the full-size image",
    "Chart {simbol} harian dengan MA, support/resistance, pola, RSI, MACD dan catatan analisa": "Daily chart of {simbol} with MAs, support/resistance, patterns, RSI, MACD and analysis notes",
    "Klik gambar untuk ukuran penuh. Catatan analisa tertulis di sisi kanan gambar, jadi tetap terbaca bila gambarnya dibagikan.":
      "Click the image for full size. The analysis notes on the right of the image are in Indonesian.",
    "Chart tidak dibuat (mode --tanpa-chart).": "Chart not generated (--tanpa-chart mode).",
    "harga per": "price as of",
    // ---------- rencana tindakan, Hari ini, arti garis (putaran 7) ----------
    "Jika": "If", "Rencana tindakan": "Action plan", "Jangan tambah dulu": "Don't add yet", "Di area beli": "In buy zone",
    "Tunggu koreksi": "Wait for pullback", "Tunggu arah": "Wait for direction",
    "Stop (close di bawah)": "Stop (close below)", "Konfirmasi naik (close di atas)": "Reversal up (close above)",
    "Rencana beli batal bila close di bawah level ini": "The buy plan is cancelled on a close below this level",
    "Tren turun dianggap selesai bila close di atas level ini": "The downtrend is considered over on a close above this level",
    "Garis rencana: area masuk, stop / konfirmasi naik, target": "Plan lines: entry zone, stop / reversal up, targets",
    "Hari ini": "Today", "yang perlu dilihat dulu · klik untuk membuka": "what to look at first · click to open",
    "Tanda baru": "New flag", "Dekat level": "Near a level", "Area beli": "Buy zone", "Bobot di portofolio": "Weight in the portfolio",
    "Tidak ada tanda baru dan tidak ada harga yang dekat level keputusan.": "No new flags and no price near a decision level.",
    "+{n} lainnya: lihat tabel di bawah (saringan Hanya yang ada tanda baru, kolom S1 · R1).": "+{n} more: see the table below (Only with new flags filter, S1 · R1 column).",
    "{n} posisi lain: tidak ada tanda baru dan harganya masih jauh dari level keputusan — cukup pantau, tidak perlu aksi hari ini.":
      "{n} other positions: no new flags and price still far from a decision level — just monitor, no action needed today.",
    "Sinyal & langkah": "Signal & next step", "Cara membaca kolom": "How to read the columns",
    "Untung/rugi dari harga rata-rata (avg, di bawahnya).": "Profit/loss versus the average price (avg, shown below it).",
    "−100 (sangat bearish) sampai +100 (sangat bullish). Angka kecil di bawahnya = perubahan sejak pindai hari bursa sebelumnya.":
      "−100 (very bearish) to +100 (very bullish). The small number below = change since the previous trading day's scan.",
    "Skor di timeframe mingguan: gambaran tren yang lebih besar.": "Score on the weekly timeframe: the bigger trend picture.",
    "Garis skor 30 hari terakhir: membaik atau memburuk.": "Score line over the last 30 days: improving or deteriorating.",
    "Kenaikan/penurunan 20 hari dibanding IHSG / S&P 500 / BTC. Positif = lebih kuat dari pasarnya.":
      "20-day gain/loss versus IHSG / S&P 500 / BTC. Positive = stronger than its market.",
    "Support (lantai) dan resistance (atap) terdekat, dengan jaraknya dari harga. Label dekat = dalam 0,6 ATR.":
      "Nearest support (floor) and resistance (ceiling), with their distance from price. The near label = within 0.6 ATR.",
    "Tanda terpenting (Baru = belum ada di pindai sebelumnya) dan rencana tindakan singkat (→).":
      "The most important flag (New = not in the previous scan) and a short action plan (→).",
    "Konfluensi = apakah timeframe yang lebih besar searah. Searah berarti sinyalnya lebih bisa dipercaya.":
      "Confluence = whether the higher timeframe agrees. Agreement means the signal is more reliable.",
    "Disentuh {n} kali — makin sering, makin kuat levelnya": "Touched {n} times — the more touches, the stronger the level",
    "terkonfirmasi candle berikutnya": "confirmed by the next candle", "menunggu konfirmasi candle berikutnya": "awaiting confirmation from the next candle",
    "belum terkonfirmasi": "not confirmed yet", "gagal dikonfirmasi": "failed confirmation", "di {jenis}": "at {jenis}",
    "Cara membaca hasil": "How to read the result", "bullish kuat": "strongly bullish", "bearish kuat": "strongly bearish",
    "Bagian Rencana tindakan di tab Ringkasan menulis apa yang ditunggu dan apa yang dilakukan bila harga mencapai level tertentu. Arti garis di chart: tombol ? di atas chart.":
      "The Action plan in the Summary tab says what to wait for and what to do when price reaches a given level. What the chart lines mean: the ? button above the chart.",
    "Arti garis di chart": "What the chart lines mean", "Konfirmasi naik": "Reversal up", "Menguat": "Breakout", "Melemah": "Breakdown",
    "Support (lantai, hijau) dan resistance (atap, merah). Angka 1 = paling dekat dengan harga.": "Support (floor, green) and resistance (ceiling, red). 1 = closest to price.",
    "Zona beli/tambah bila tren mendukung (rencana beli).": "Buy/add zone when the trend is supportive (buy plan).",
    "Di bawah harga, untuk rencana beli: close di bawahnya = rencana beli batal (stop loss).": "Below price, for a buy plan: a close below it = the buy plan is cancelled (stop loss).",
    "Di atas harga, saat tren turun: close di atasnya = tren turun dianggap selesai. Sebelum itu, hindari menambah.": "Above price, in a downtrend: a close above it = the downtrend is considered over. Until then, avoid adding.",
    "Sasaran harga rencana beli; area wajar mengamankan sebagian keuntungan.": "Price objective of the buy plan; a reasonable area to lock in part of the profit.",
    "Saat arah belum jelas: close di atas Menguat = arah naik, close di bawah Melemah = arah turun.": "When direction is unclear: a close above Breakout = up, a close below Breakdown = down.",
    "Garis miring yang menghubungkan titik-titik swing; putus-putus = sudah ditembus.": "Sloped line connecting swing points; dashed = already broken.",
    "Bentuk pola chart (mis. Double Top) dan Target pola: sasaran harga bila pola itu berlaku.": "Chart pattern shape (e.g. Double Top) and Pattern target: the price objective if the pattern plays out.",
    "Semua garis dihitung ulang setiap analisa. \"Close\" = harga penutupan candle di timeframe ini, bukan harga sesaat.": "All lines are recalculated on every analysis. \"Close\" = the candle's closing price on this timeframe, not the momentary price.",
    "Seberapa andal skor ini?": "How reliable is this score?", "uji pada data lama · {dari} – {sampai}": "tested on past data · {dari} – {sampai}",
    "Rata-rata perubahan harga 20 hari bursa sesudah skor berada di kelompok tertentu. Skor dihitung hanya dari data sampai hari itu.":
      "Average price change over the 20 trading days after the score was in a given band. Each score uses only data up to that day.",
    "Pasar": "Market", "semua hari": "all days", "{n} aset": "{n} assets", "{n} hari · naik {p}% dari waktu": "{n} days · up {p}% of the time",
    "Sampel terlalu sedikit.": "Sample too small.",
    "Skor beli: apakah skor tinggi diikuti hasil lebih baik?": "Buy score: are high scores followed by better results?",
    "Perubahan harga 20 hari sesudahnya dikurangi rata-rata semua hari di pasar itu (poin persen), per kelompok skor beli. Arahkan kursor untuk persentase hari naik dan hasil rencana beli.":
      "20-day price change afterwards minus the average of all days in that market (percentage points), per buy-score group. Hover for the share of up days and the buy-plan result.",
    "rencana beli rata-rata {r}R ({n} hari)": "buy plan average {r}R ({n} days)",
    "Dibatasi 59 (Pantau) karena tren 1D+1W rata-rata masih turun.": "Capped at 59 (Watch) because the 1D+1W trend is still down on average.",
    "Pemindai IHSG": "IDX screener", "Pindai IHSG": "Scan IDX", "Belum pernah dipindai.": "Never scanned yet.", "Baru": "New",
    "{n} tanda baru belum dilihat": "{n} new flags not seen yet", "{n} tanda baru di Pemindai IHSG — buka": "{n} new flags in the IDX screener — open",
    "Data {tgl} · dipindai {w} · {lolos} dari {total} saham lolos saringan": "Data {tgl} · scanned {w} · {lolos} of {total} stocks pass the filter",
    "{n} tanda baru dibanding {tgl}": "{n} new flags compared with {tgl}", "tanda baru mulai dihitung pada pindai hari bursa berikutnya": "new flags are counted from the next trading day's scan",
    "Memindai: {fase}": "Scanning: {fase}", "menyiapkan daftar": "preparing the list", "menarik harga": "fetching prices", "menyaring": "filtering", "menganalisa": "analysing", "memulai": "starting", "berjalan": "running",
    "Pindai gagal": "Scan failed", "Hanya tanda baru": "New flags only", "Semua arah": "All directions", "Skor beli ≥ {x}": "Buy score ≥ {x}", "Semua skor beli": "Any buy score",
    "Cari kode, mis. BBRI": "Search code, e.g. BBRI", "Cari kode saham": "Search stock code", "{n} saham": "{n} stocks", "Saham": "Stock", "Nilai transaksi": "Value traded", "Frek": "Freq.",
    "Tanda": "Flags", "Langkah (1D)": "Step (1D)", "rata²": "avg", "Rata-rata nilai transaksi 20 hari": "20-day average value traded", "Selisih bid–offer penutupan": "Closing bid–offer spread",
    "Tidak ada saham untuk saringan ini.": "No stocks for this filter.", "Tampilkan semua ({n})": "Show all ({n})", "Saringan": "Filter", "Tidak lolos": "Filtered out",
    "nilai transaksi rata-rata 20 hari ≥ {x}": "20-day average value traded ≥ {x}", "hari ini ≥ {x}": "today ≥ {x}", "harga ≥ Rp{x}": "price ≥ IDR {x}", "aktif ≥ {x} dari 20 hari": "traded on ≥ {x} of 20 days",
    "frekuensi ≥ {x}×": "frequency ≥ {x}×", "spread ≤ {x}%": "spread ≤ {x}%", "tanpa papan {p}": "excluding the {p} board",
    "riwayat pendek": "short history", "harga rendah": "low price", "jarang diperdagangkan": "rarely traded", "nilai transaksi kecil": "small value traded", "nilai hari ini kecil": "small value today",
    "frekuensi rendah": "low frequency", "spread lebar": "wide spread", "tidak diperdagangkan / suspensi": "not traded / suspended",
    "Frekuensi dan bid/offer dari IDX tidak bisa diambil saat ini, jadi saringan itu dilewati.": "Frequency and bid/offer from IDX can't be fetched right now, so those filters are skipped.",
    "Pindai otomatis sekali tiap hari bursa setelah {jam} WIB selama panel menyala.": "Scans automatically once every trading day after {jam} WIB while the panel is running.",
    "Pindai otomatis mati (pengaturan.json → ihsg_otomatis).": "Automatic scan is off (pengaturan.json → ihsg_otomatis).",
    "Analisa teknikal otomatis, bukan rekomendasi; saham likuiditas rendah tetap berisiko (spread lebar, mudah digerakkan).": "Automatic technical analysis, not a recommendation; low-liquidity stocks remain risky (wide spreads, easy to move).",
    "Klik Pindai IHSG untuk memindai semua saham IHSG. Pindai pertama menarik riwayat harga ±900 saham (beberapa menit); sesudahnya jauh lebih cepat.": "Click Scan IDX to scan every IDX stock. The first scan fetches the price history of ±900 stocks (a few minutes); after that it is much faster.",
    "Volatil": "Volatile", "ATR ≥ 8% harga: gerakan harian besar, risiko tinggi": "ATR ≥ 8% of price: large daily moves, high risk", "Baru lolos": "Newly passes",
    "Baru masuk saringan likuiditas dibanding pindai sebelumnya": "Newly passes the liquidity filter compared with the previous scan", "Panel lokal tidak merespons.": "The local panel is not responding.",
    "Skor beli": "Buy score", "Beli": "Buy", "Rincian": "Breakdown", "Skor beli {x}/100 · {label}": "Buy score {x}/100 · {label}",
    "Tren 1D+1W": "Trend 1D+1W", "Lokasi harga": "Price location", "Imbal hasil vs risiko": "Reward vs risk", "Momentum & volume": "Momentum & volume",
    "Dari data harian (1D + 1W), sama di semua tampilan. Teknikal saja: valuasi, laporan keuangan, dan berita tidak dihitung. 0–39 belum layak · 40–69 pantau · 70–79 layak dicicil (tren rata-rata ≥ +20) · 80–100 menarik (tren ≥ +40, R:R ≥ 1,5, saham IDX nilai transaksi ≥ Rp5 M).":
      "From daily data (1D + 1W), the same in every view. Technical only: valuation, financial reports and news are not included. 0–39 not yet · 40–69 watch · 70–79 worth accumulating (average trend ≥ +20) · 80–100 attractive (trend ≥ +40, R:R ≥ 1.5, IDX stocks value traded ≥ IDR 5B).",
    "tren 1D+1W rata-rata {x} (perlu ≥ {m})": "average 1D+1W trend {x} (needs ≥ {m})", "belum ada rencana beli (R:R)": "no buy plan yet (R:R)",
    "R:R {x} (perlu ≥ {m})": "R:R {x} (needs ≥ {m})", "nilai transaksi rata-rata Rp{x} M (perlu ≥ Rp{m} M)": "average value traded IDR {x}B (needs ≥ IDR {m}B)",
    "Dibatasi {ke}: {alasan}.": "Capped at {ke}: {alasan}.",
    "Kesimpulan semua timeframe": "All-timeframe conclusion", "Menghitung semua timeframe…": "Calculating all timeframes…",
    "Skor semua timeframe": "All-timeframe score", "Rata-rata tertimbang skor 1H, 4H, 1D, 1W, dan 1M": "Weighted average of the 1H, 4H, 1D, 1W and 1M scores",
    "Skor dan rencana per timeframe": "Score and plan per timeframe", "Saran": "Suggestions",
    "Skor gabungan = rata-rata tertimbang ({ket}). Level saran dari timeframe 1D. Rencana otomatis adalah peta level, bukan sinyal pasti: di uji data lama hasil rata-ratanya belum positif.":
      "Combined score = weighted average ({ket}). Suggestion levels come from the 1D timeframe. The automatic plan is a map of levels, not a sure signal: in the back-test its average result is not yet positive.",
    "Sampel kecil ({n} aset), anggap petunjuk saja:": "Small sample ({n} assets), treat as a hint only:",
    "Uji ini dibuat dengan mesin {a}, sedangkan mesin sekarang {b}. Hitung ulang: python3 uji_skor.py": "This test was made with engine {a}, the current engine is {b}. Recalculate: python3 uji_skor.py",
    "rata-rata R": "average R", "rugi kena stop": "loss at stop",
    "Hasil rata-rata per rencana dalam R (1R = jarak ke Stop), sebelum biaya. Di bawah 0 = rencana ini rugi rata-rata.": "Average result per plan in R (1R = distance to the Stop), before costs. Below 0 = this plan loses on average.",
    "Rata-rata rugi saat kena Stop. Lebih dalam dari −1R karena keluar di close/gap, bukan tepat di Stop.": "Average loss when the Stop is hit. Deeper than −1R because the exit is at the close/gap, not exactly at the Stop.",
    "Tren": "Trend", "Pola chart": "Chart pattern", "Lokasi": "Location", "Volatilitas": "Volatility",
    "Searah: skor tinggi diikuti hasil lebih baik daripada skor rendah ({x} poin dalam 20 hari). Skor berguna sebagai penyaring tren.":
      "Consistent: high scores were followed by better results than low scores ({x} points over 20 days). Useful as a trend filter.",
    "Berlawanan: skor rendah justru sering diikuti pantulan ({x} poin). Di pasar ini skor bearish lebih cocok dibaca sebagai jenuh jual, bukan alasan menjual.":
      "Inverse: low scores were often followed by a rebound ({x} points). In this market a bearish score reads better as oversold, not a reason to sell.",
    "Lemah: hampir tidak ada beda hasil antara skor tinggi dan rendah. Jangan mengandalkan skor saja.":
      "Weak: almost no difference between high and low scores. Don't rely on the score alone.",
    "Sampel hanya aset yang pernah dipindai, hari-harinya tumpang tindih, dan tanpa biaya transaksi: gambaran kasar, bukan bukti. Hitung ulang: python3 uji_skor.py":
      "Sample is only the scanned assets, days overlap, and no transaction costs: a rough picture, not proof. Recalculate: python3 uji_skor.py",
    // ---------- lain-lain ----------
    "Timeframe {catatan}.": "Timeframe {catatan}.", "Tidak ada": "None", "Volume": "Volume", "Trendline": "Trendline",
    "Bahasa diganti. Memuat ulang…": "Language changed. Reloading…", "Bahasa tidak bisa diganti: panel lokal tidak merespons.": "Couldn't change the language: the local panel is not responding.",
  };

  let lang = "id";
  let dariUrl = "";
  try { dariUrl = new URLSearchParams(root.location ? root.location.search : "").get("bahasa") || ""; } catch { dariUrl = ""; }
  try { lang = root.AT_BAHASA || dariUrl || localStorage.getItem("at.bahasa") || "id"; } catch { lang = root.AT_BAHASA || dariUrl || "id"; }
  if (lang !== "en") lang = "id";
  const hilang = new Set();  // teks yang belum ada padanan Inggrisnya (untuk uji)

  function t(s, v) {
    let o = s;
    if (lang === "en") { if (EN[s] != null) o = EN[s]; else hilang.add(s); }
    return v ? o.replace(/\{(\w+)\}/g, (_, k) => (v[k] == null ? "" : String(v[k]))) : o;
  }

  // Teks statis di HTML: data-i18n (isi elemen) dan data-i18n-attr="title,aria-label,placeholder" (atribut).
  function terapkan(akar) {
    if (lang !== "en" || typeof document === "undefined") return;
    (akar || document).querySelectorAll("[data-i18n]").forEach((el) => {
      const kunci = el.getAttribute("data-i18n") || el.textContent.trim();
      el.textContent = t(kunci);
    });
    (akar || document).querySelectorAll("[data-i18n-attr]").forEach((el) => {
      el.getAttribute("data-i18n-attr").split(",").forEach((a) => { const v = el.getAttribute(a.trim()); if (v) el.setAttribute(a.trim(), t(v)); });
    });
    document.documentElement.lang = "en";
  }

  root.ATB = { lang, en: lang === "en", t, terapkan, hilang,
    lokal: lang === "en" ? "en-US" : "id-ID",        // angka: 5,300.5 vs 5.300,5
    lokalTanggal: lang === "en" ? "en-GB" : "id-ID" };  // tanggal: 13 Nov 2026
  terapkan();
})(typeof window !== "undefined" ? window : globalThis);
