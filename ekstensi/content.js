// Analisa Teknikal — membaca simbol (dan timeframe bila ada) dari halaman chart, lalu menampilkan kartu analisa kecil.
// Di TradingView, garis analisa (support/resistance, rencana, trendline, pola) juga digambar di atas chart oleh tv_utama.js.
// Tidak mengubah isi halaman: kartu dipasang di Shadow DOM tertutup dan tidak membawa data posisi/portofolio.
(() => {
  "use strict";
  if (window.__analisaTeknikal) return;
  window.__analisaTeknikal = true;

  // ------------------------------------------------------------------
  // 1. Deteksi simbol per situs
  // ------------------------------------------------------------------
  const ls = (k) => { try { return localStorage.getItem(k) || ""; } catch { return ""; } };
  const teks = (sel) => { const e = document.querySelector(sel); return e ? (e.innerText || e.textContent || "").trim() : ""; };
  const MATA_UANG = new Set(["USD", "EUR", "JPY", "GBP", "AUD", "NZD", "CAD", "CHF", "SGD", "HKD", "CNY", "IDR", "MYR", "KRW", "THB", "INR"]);
  const CATATAN_IDR = "Level dihitung dari pasangan USDT (data Binance), jadi dalam dolar, bukan rupiah.";

  function pasangan(bursa, base, quote) {
    base = String(base).toUpperCase(); quote = String(quote).toUpperCase();
    const d = { q: `${bursa}:${base}${quote}` };
    if (quote === "IDR" || quote === "BIDR") d.catatan = CATATAN_IDR;
    return d;
  }

  // Di TradingView, tv_utama.js (dunia halaman) membaca simbol & interval chart aktif langsung dari API chart
  // dan mengabari lewat event ini begitu berubah, jadi tidak perlu menunggu pemeriksaan berkala.
  const EV_TV = "analisa-teknikal:tv", EV_LAPISAN = "analisa-teknikal:lapisan", EV_MINTA = "analisa-teknikal:minta";
  const LABEL_IV = { D: "1 hari", "1D": "1 hari", W: "1 minggu", "1W": "1 minggu", M: "1 bulan", "1M": "1 bulan" };
  let tvUtama = null;  // { q, iv } dari chart aktif, atau null bila API chart tidak tersedia
  function labelIv(iv) {
    if (LABEL_IV[iv]) return LABEL_IV[iv];
    const m = String(iv).match(/^(\d+)([A-Za-z]?)$/);
    if (!m) return String(iv);
    const n = +m[1], u = m[2];
    if (u === "D") return `${n} hari`;
    if (u === "W") return `${n} minggu`;
    if (u === "M") return `${n} bulan`;
    if (u === "S") return `${n} detik`;
    if (u) return String(iv);
    return n % 60 === 0 ? `${n / 60} jam` : `${n} menit`;
  }

  function tradingView(u) {
    if (tvUtama && tvUtama.q) return { q: tvUtama.q, iv: tvUtama.iv || "D", ivLabel: labelIv(tvUtama.iv || "D"), dariApi: true };
    // Halaman simbol: /symbols/IDX-BBCA/ atau /symbols/NASDAQ-NVDA/
    const adaChart = document.querySelector("#header-toolbar-symbol-search");
    const m = u.pathname.match(/^\/symbols\/([A-Z0-9_]+)-([A-Z0-9._!]+)\/?/i);
    if (m && !adaChart) return { q: `${m[1]}:${m[2]}`.toUpperCase(), iv: "D", ivLabel: "1 hari" };
    // Halaman simbol kripto: /symbols/BTCUSDT/?exchange=BINANCE
    const m2 = u.pathname.match(/^\/symbols\/([A-Z0-9._!]+)\/?/i);
    if (m2 && !adaChart) {
      const ex = (u.searchParams.get("exchange") || "").toUpperCase();
      return { q: (ex ? ex + ":" : "") + m2[1].toUpperCase(), iv: "D", ivLabel: "1 hari" };
    }
    // Chart: tombol simbol (mis. NVDA) + bursa di legenda (mis. NASDAQ)
    const sym = teks("#header-toolbar-symbol-search");
    const bursa = teks('[data-qa-id~="legend-source-exchange"]').toUpperCase().replace(/\s+/g, "");
    // Simbol terakhir di localStorage hanya dipakai di halaman chart (bukan beranda/berita TradingView)
    const diChart = u.pathname.startsWith("/chart") || !!adaChart;
    let q = "";
    if (sym && bursa) q = `${bursa}:${sym}`;
    else if (diChart && ls("tradingview.editchart.model.symbol")) q = ls("tradingview.editchart.model.symbol");
    else if (u.searchParams.get("symbol")) q = u.searchParams.get("symbol");
    else if (sym) q = sym;
    if (!q) return null;
    const tombolIv = document.querySelector("#header-toolbar-intervals button");
    const iv = ls("tradingview.editchart.model.interval") || (tombolIv ? tombolIv.innerText.trim() : "") || u.searchParams.get("interval") || "D";
    const ivLabel = tombolIv ? (tombolIv.getAttribute("aria-label") || tombolIv.innerText.trim()) : iv;
    return { q: q.toUpperCase(), iv, ivLabel };
  }

  const INDEKS_STOCKBIT = { IHSG: "IHSG", COMPOSITE: "IHSG", JKSE: "IHSG", LQ45: "LQ45", IDX30: "IDX30" };
  function stockbit(u) {
    // stockbit.com/symbol/BBCA (juga /symbol/BBCA/chartbit, dan rute lama #/symbol/BBCA)
    const jalur = u.pathname + (u.hash.startsWith("#/") ? u.hash.slice(1) : "");
    const m = jalur.match(/\/(?:symbol|chartbit)\/([A-Za-z0-9]{2,12})(?:[/?#]|$)/);
    const kode = (m ? m[1] : u.searchParams.get("symbol") || "").toUpperCase();
    if (INDEKS_STOCKBIT[kode]) return { q: INDEKS_STOCKBIT[kode] };
    return /^[A-Z]{4}$/.test(kode) ? { q: `IDX:${kode}` } : null;
  }

  function gayaBinance(bursa) {
    return (u) => {
      // /en/trade/BTC_USDT?type=spot · /id/trade/ETH_IDR · /en/futures/BTCUSDT
      let m = u.pathname.match(/\/trade\/([A-Z0-9]{2,15})_([A-Z0-9]{2,10})(?:[/?#]|$)/i);
      if (m) return pasangan(bursa, m[1], m[2]);
      m = u.pathname.match(/\/futures\/([A-Z0-9]{4,20}?)(?:_\d+)?(?:[/?#]|$)/i);
      return m ? { q: `${bursa}:${m[1].toUpperCase()}` } : null;
    };
  }

  function indodax(u) {
    // indodax.com/market/BTCIDR
    const m = u.pathname.match(/\/market\/([A-Z0-9]{2,15}?)(IDR|USDT)(?:[/?#]|$)/i);
    return m ? pasangan("INDODAX", m[1], m[2]) : null;
  }

  function bybit(u) {
    // /en/trade/spot/BTC/USDT · /trade/usdt/BTCUSDT
    let m = u.pathname.match(/\/trade\/spot\/([A-Z0-9]{2,15})\/([A-Z0-9]{2,10})(?:[/?#]|$)/i);
    if (m) return pasangan("BYBIT", m[1], m[2]);
    m = u.pathname.match(/\/trade\/(?:usdt|usdc|futures)\/([A-Z0-9]{4,20})(?:[/?#-]|$)/i);
    return m ? { q: `BYBIT:${m[1].toUpperCase()}` } : null;
  }

  function okx(u) {
    // /trade-spot/btc-usdt · /id/trade-swap/btc-usdt-swap
    const m = u.pathname.match(/\/trade-(?:spot|swap|margin|futures)\/([a-z0-9]{2,15})-([a-z0-9]{2,10})(?:-[a-z0-9]+)?(?:[/?#]|$)/i);
    return m ? pasangan("OKX", m[1], m[2]) : null;
  }

  function yahoo(u) {
    // finance.yahoo.com/quote/BBCA.JK/ · /quote/%5EJKSE/ · /chart/NVDA
    const m = u.pathname.match(/\/(?:quote|chart)\/([^/?#]+)/);
    if (!m) return null;
    let kode = "";
    try { kode = decodeURIComponent(m[1]).toUpperCase(); } catch { return null; }
    if (!/^[A-Z0-9^.=-]{1,20}$/.test(kode)) return null;
    // Ticker Yahoo tanpa akhiran (NVDA, BRK-B) selalu bursa AS; yang berakhiran (.JK, -USD, =X, ^) dikirim apa adanya
    return /^[A-Z]{1,5}(-[A-Z])?$/.test(kode) ? { q: `US:${kode}` } : { q: kode };
  }

  const BURSA_GOOGLE = { LON: "LSE", TYO: "TSE", HKG: "HKEX", ETR: "XETR", FRA: "FWB", TSE: "TSX", KLSE: "MYX", BKK: "SET",
    BOM: "BSE", EPA: "EURONEXT", AMS: "EURONEXT", SWX: "SIX", NYSEAMERICAN: "AMEX" };
  const INDEKS_GOOGLE = { ".INX": "SPX", ".IXIC": "NASDAQ", ".DJI": "DJI", NDX: "NDX", ".JKSE": "IHSG", COMPOSITE: "IHSG", VIX: "VIX" };
  function googleFinance(u) {
    // google.com/finance/quote/NVDA:NASDAQ · BBCA:IDX · BTC-USD · EUR-USD
    const m = u.pathname.match(/^\/finance\/quote\/([^/?#]+)/);
    if (!m) return null;
    let isi = "";
    try { isi = decodeURIComponent(m[1]).toUpperCase(); } catch { return null; }
    const [sym, bursa] = isi.split(":");
    if (!sym) return null;
    if (!bursa) {
      const fx = sym.match(/^([A-Z]{3})-([A-Z]{3})$/);
      if (fx && MATA_UANG.has(fx[1]) && MATA_UANG.has(fx[2])) return { q: fx[1] + fx[2] };
      return /^[A-Z0-9]{2,10}-[A-Z]{3,4}$/.test(sym) ? { q: sym } : null;
    }
    if (bursa.startsWith("INDEX")) return INDEKS_GOOGLE[sym] ? { q: INDEKS_GOOGLE[sym] } : null;
    return { q: `${BURSA_GOOGLE[bursa] || bursa}:${sym}` };
  }

  const SITUS = [
    { nama: "TradingView", host: /(^|\.)tradingview\.com$/, baca: tradingView },
    { nama: "Stockbit", host: /(^|\.)stockbit\.com$/, baca: stockbit },
    { nama: "Binance", host: /(^|\.)binance\.com$/, baca: gayaBinance("BINANCE") },
    { nama: "Tokocrypto", host: /(^|\.)tokocrypto\.com$/, baca: gayaBinance("TOKOCRYPTO") },
    { nama: "Indodax", host: /(^|\.)indodax\.com$/, baca: indodax },
    { nama: "Bybit", host: /(^|\.)bybit\.com$/, baca: bybit },
    { nama: "OKX", host: /(^|\.)okx\.com$/, baca: okx },
    { nama: "Yahoo Finance", host: /(^|\.)finance\.yahoo\.com$/, baca: yahoo },
    { nama: "Google Finance", host: /^www\.google\.com$/, baca: googleFinance },
  ];
  const situs = SITUS.find((s) => s.host.test(location.hostname));
  if (!situs) return;

  function deteksi() {
    let d = null;
    try { d = situs.baca(new URL(location.href)); } catch { d = null; }
    if (!d || !d.q) return { q: "", iv: "", ivLabel: "", situs: situs.nama };
    return { q: d.q, iv: d.iv || "", ivLabel: d.ivLabel || "", catatan: d.catatan || "", situs: situs.nama, dariApi: !!d.dariApi };
  }

  // ------------------------------------------------------------------
  // 2. Kirim ke ekstensi bila berubah
  // ------------------------------------------------------------------
  let terakhir = "", qSekarang = "", ivSekarang = "";
  function kirim(paksa) {
    const d = deteksi();
    const kunci = `${d.q}|${d.iv}`;
    if (!paksa && kunci === terakhir) return;
    terakhir = kunci;
    if (d.q !== qSekarang || d.iv !== ivSekarang) { const ganti = d.q !== qSekarang; qSekarang = d.q; ivSekarang = d.iv; kartu.gantiSimbol(d.q, ganti); }
    try { chrome.runtime.sendMessage({ type: "tv", q: d.q, iv: d.iv, ivLabel: d.ivLabel, catatan: d.catatan, situs: d.situs }); } catch { /* ekstensi dimuat ulang: berhenti diam-diam */ }
  }

  // ------------------------------------------------------------------
  // 3. Kartu analisa di halaman
  // ------------------------------------------------------------------
  const kartu = (() => {
    const HOST = location.hostname;
    const POSISI_AWAL = situs.nama === "TradingView" ? { kiri: 64, bawah: 72 } : { kiri: 20, bawah: 20 };
    const LABEL_TF = { "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1D", "1wk": "1W", "1mo": "1M" };
    const set = { aktif: true, kecil: false, garis: true, pos: { ...POSISI_AWAL } };
    let host = null, akar = null, data = null, ditutup = false, memuat = false, timerMuat = null, siap = false;
    let lapisan = null;  // { untuk: { q, iv }, L } — garis analisa untuk chart TradingView (tanpa data portofolio)
    const BISA_GARIS = situs.nama === "TradingView";

    // Kirim garis analisa ke tv_utama.js (atau kosongkan). Garis hanya digambar bila chart aktif masih simbol & interval yang sama.
    function kirimGaris() {
      if (!BISA_GARIS) return;
      const isi = lapisan ? { untuk: lapisan.untuk, lapisan: lapisan.L, aktif: !!set.garis } : null;
      try { document.dispatchEvent(new CustomEvent(EV_LAPISAN, { detail: JSON.stringify(isi) })); } catch { /* halaman menolak event: abaikan */ }
    }
    const adaGaris = () => BISA_GARIS && !!lapisan && !lapisan.L.kuotasi_lain;

    const IKON = {
      logo: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><rect x="1" y="1" width="22" height="22" rx="6" fill="#1b1b1e" stroke="#34343a"/><path d="M7 15v-3M12 16V9M17 13v-3" stroke="#8e8e96" stroke-width="1.6" stroke-linecap="round"/><path d="M5 14l5-4 4 2 5-5" stroke="#6ea8fe" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      segar: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M20 11a8 8 0 1 0-2.3 5.7M20 5v6h-6" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/></svg>',
      kecil: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M6 12h12" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
      tutup: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M7 7l10 10M17 7L7 17" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg>',
      merah: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M12 3l9.5 17h-19L12 3z" fill="none" stroke="#f26a67" stroke-width="2" stroke-linejoin="round"/><path d="M12 10v4M12 17v.5" stroke="#f26a67" stroke-width="2" stroke-linecap="round"/></svg>',
      oranye: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><circle cx="12" cy="12" r="9" fill="none" stroke="#e0a64b" stroke-width="2"/><path d="M12 7.5v5.5M12 16.2v.3" stroke="#e0a64b" stroke-width="2" stroke-linecap="round"/></svg>',
      buka: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><rect x="3" y="4" width="18" height="16" rx="2" fill="none" stroke="currentColor" stroke-width="1.8"/><path d="M15 4v16" stroke="currentColor" stroke-width="1.8"/></svg>',
      garis: '<svg viewBox="0 0 24 24" width="14" height="14" aria-hidden="true"><path d="M3 7h18M3 17h18" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-dasharray="3 3"/><path d="M4 14l5-4 4 2 7-6" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/></svg>',
    };

    const CSS = `
      :host { all: initial; }
      .wadah { position: fixed; z-index: 2147483000; font: 13px/1.45 -apple-system, BlinkMacSystemFont, "SF Pro Text", "Segoe UI", system-ui, sans-serif;
        color: #f2f2f3; -webkit-font-smoothing: antialiased; letter-spacing: 0; text-align: left; }
      .wadah[hidden], [hidden] { display: none !important; }
      .mono { font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; font-variant-numeric: tabular-nums; font-variant-ligatures: none; }
      .kartu { width: 292px; background: #131315; border: 1px solid #34343a; border-radius: 10px; overflow: hidden;
        box-shadow: 0 12px 32px rgba(0,0,0,.45), 0 2px 6px rgba(0,0,0,.3); }
      .kepala { display: flex; align-items: center; gap: 6px; height: 32px; padding: 0 4px 0 10px; border-bottom: 1px solid #242428;
        cursor: grab; user-select: none; -webkit-user-select: none; touch-action: none; }
      .kepala.geser, .pil.geser { cursor: grabbing; }
      .judul { font-size: 11.5px; font-weight: 600; color: #bcbcc2; white-space: nowrap; }
      .tf { font-size: 10.5px; font-weight: 600; color: #e4e4e7; background: #1b1b1e; border: 1px solid #34343a; border-radius: 4px; padding: 0 4px; line-height: 16px; }
      .tombol { margin-left: auto; display: flex; gap: 2px; }
      .ikon { width: 26px; height: 26px; display: grid; place-items: center; border: 0; border-radius: 6px; background: transparent; color: #a3afc2; cursor: pointer; padding: 0; }
      .ikon:hover { background: #202023; color: #f2f2f3; }
      .ikon[aria-pressed="true"] { background: rgba(255,255,255,.12); color: #f4f4f5; }
      .ikon[aria-pressed="true"]:hover { background: rgba(110,168,254,.26); }
      .ikon:focus-visible, .buka:focus-visible, .pil:focus-visible { outline: 2px solid #ececee; outline-offset: 1px; }
      .isi { padding: 10px 12px 12px; display: grid; gap: 9px; transition: opacity .15s; }
      .memuat .isi, .memuat.pil { opacity: .5; }
      .memuat .ikon.segar svg { animation: putar .8s linear infinite; }
      @keyframes putar { to { transform: rotate(360deg); } }
      .vonis { display: flex; align-items: center; gap: 10px; min-width: 0; }
      .skor { font-size: 27px; font-weight: 600; line-height: 1; letter-spacing: -.02em; min-width: 50px; }
      .vonis > div { min-width: 0; }
      .label { font-size: 13.5px; font-weight: 600; line-height: 1.3; }
      .simbol { font-size: 12px; line-height: 1.4; color: #bcbcc2; display: -webkit-box; -webkit-line-clamp: 2; -webkit-box-orient: vertical; overflow: hidden; }
      .simbol b { color: #f2f2f3; font-weight: 600; }
      .up { color: #2db8aa; } .down { color: #f26a67; } .flat { color: #e0a64b; }
      .level { display: grid; grid-template-columns: 1fr 1fr; gap: 6px; }
      .lv { background: #161618; border: 1px solid #26262a; border-radius: 7px; padding: 5px 8px 6px; min-width: 0; }
      .lv .k { font-size: 10.5px; font-weight: 700; display: flex; align-items: center; gap: 5px; }
      .lv .h { font-size: 13px; color: #f2f2f3; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
      .lv .j { font-size: 11px; color: #a3afc2; }
      .dekat { font: 700 10px/15px -apple-system, BlinkMacSystemFont, system-ui, sans-serif; color: #0b0b0c; background: #e0a64b; border-radius: 3px; padding: 0 4px; }
      ul { list-style: none; margin: 0; padding: 0; display: grid; gap: 5px; }
      .langkah { margin: 8px 0 0; font-size: 11.5px; line-height: 1.45; color: #e4e4e7; }
      .langkah b { color: #f4f4f5; font-weight: 600; }
      li { display: grid; grid-template-columns: 14px 1fr; gap: 7px; align-items: start; font-size: 12px; line-height: 1.4; color: #e4e4e7; }
      li svg { margin-top: 1px; }
      .catatan { margin: 0; font-size: 11.5px; line-height: 1.4; color: #a3afc2; }
      .buka { display: flex; align-items: center; justify-content: center; gap: 7px; height: 30px; border-radius: 7px; border: 1px solid #34343a;
        background: #1b1b1e; color: #f2f2f3; font: 500 12.5px -apple-system, BlinkMacSystemFont, system-ui, sans-serif; cursor: pointer; padding: 0 10px; }
      .buka:hover { background: #242428; border-color: #46464e; }
      .pil { display: inline-flex; align-items: center; gap: 7px; height: 32px; padding: 0 12px 0 9px; border-radius: 16px; background: #131315;
        border: 1px solid #34343a; box-shadow: 0 8px 22px rgba(0,0,0,.45); color: #f2f2f3; cursor: pointer; font: 600 12.5px ui-monospace, "SF Mono", Menlo, monospace;
        user-select: none; -webkit-user-select: none; touch-action: none; transition: opacity .15s; }
      .pil:hover { border-color: #46464e; }
      .pil .nm { font-family: -apple-system, BlinkMacSystemFont, system-ui, sans-serif; font-weight: 500; color: #bcbcc2; }
      .pesan { width: 292px; box-sizing: border-box; background: #131315; border: 1px solid #34343a; border-radius: 10px; padding: 10px 12px;
        font-size: 12px; line-height: 1.45; color: #e4e4e7; box-shadow: 0 12px 32px rgba(0,0,0,.45); }
      @media (prefers-reduced-motion: reduce) { .isi, .pil { transition: none; } .memuat .ikon.segar svg { animation: none; } }
    `;

    // Teks kartu dalam bahasa Inggris (bahasa mengikuti data analisa dari panel: data.bahasa).
    const EN = {
      "skor": "score", "Klik untuk membuka kartu": "Click to open the card", "Klik untuk membuka · seret untuk memindah": "Click to open · drag to move",
      "dekat": "near", "hari ini": "Today's", "terakhir": "The latest",
      "Timeframe chart": "Chart timeframe", "Seret untuk memindah": "Drag to move",
      "Garis analisa di chart": "Analysis lines on the chart", "Sembunyikan": "Hide", "Tampilkan": "Show",
      "garis analisa di chart (support/resistance, rencana, trendline, pola)": "analysis lines on the chart (support/resistance, plan, trendlines, patterns)",
      "Muat ulang analisa": "Reload the analysis", "Muat ulang": "Reload", "Kecilkan kartu": "Minimise the card", "Kecilkan": "Minimise",
      "Sembunyikan kartu": "Hide the card", "Tanda": "Flags", "Rencana tindakan": "Action plan", "Buka analisa lengkap": "Open full analysis",
      "Kartu disembunyikan sampai halaman dimuat ulang. Untuk mematikannya di semua halaman: klik kanan ikon ekstensi Analisa Teknikal.":
        "Card hidden until the page is reloaded. To turn it off on every page: right-click the Analisa Teknikal extension icon.",
      [CATATAN_IDR]: "Levels are computed from the USDT pair (Binance data), so they are in dollars, not rupiah.",
    };
    const en = () => !!(data && data.bahasa === "en");
    const tk = (x) => (en() && EN[x] != null ? EN[x] : x);
    const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
    const kelas = (s) => (s >= 20 ? "up" : s <= -20 ? "down" : "flat");
    const skorTxt = (s) => (s > 0 ? "+" : s < 0 ? "−" : "") + Math.abs(Math.round(s));
    const $ = (sel) => akar.querySelector(sel);

    function pasang() {
      if (host && host.isConnected) return;
      if (!host) {
        host = document.createElement("analisa-teknikal-kartu");
        host.style.cssText = "all: initial !important; position: fixed !important; left: 0 !important; top: 0 !important; width: 0 !important; height: 0 !important; z-index: 2147483000 !important;";
        akar = host.attachShadow({ mode: "closed" });
        akar.innerHTML = `<style>${CSS}</style><div class="wadah" id="wadah" hidden></div>`;
        akar.addEventListener("click", klik);
        akar.addEventListener("pointerdown", mulaiGeser);
      }
      (document.body || document.documentElement).appendChild(host);
    }

    function jepit() {
      const w = $("#wadah"), r = w && !w.hidden ? w.getBoundingClientRect() : { width: 292, height: 160 };
      set.pos.kiri = Math.round(Math.min(Math.max(8, set.pos.kiri), Math.max(8, innerWidth - r.width - 8)));
      set.pos.bawah = Math.round(Math.min(Math.max(8, set.pos.bawah), Math.max(8, innerHeight - r.height - 8)));
    }
    function terapkanPosisi() {
      const w = $("#wadah");
      if (!w) return;
      w.style.left = set.pos.kiri + "px";
      w.style.bottom = set.pos.bawah + "px";
    }

    function render() {
      if (!siap) return;
      const tampil = set.aktif && !ditutup && data && qSekarang;
      if (!tampil) { if (host) $("#wadah").hidden = true; return; }
      pasang();
      const w = $("#wadah"), d = data, k = kelas(d.skor);
      const tf = LABEL_TF[d.tf] || d.tf || "";
      if (set.kecil) {
        w.innerHTML = `<button class="pil ${memuat ? "memuat" : ""}" type="button" data-aksi="besar" aria-label="Analisa Teknikal ${esc(d.simbol)}: ${tk("skor")} ${esc(skorTxt(d.skor))}, ${esc(d.label)}. ${tk("Klik untuk membuka kartu")}" title="${tk("Klik untuk membuka · seret untuk memindah")}">
          <span class="${k}">${esc(skorTxt(d.skor))}</span><span class="nm">${esc(d.simbol)} · ${esc(tf)}</span></button>`;
      } else {
        const lv = (d.level || []).map((x) => `<div class="lv"><div class="k ${x.k.startsWith("S") ? "up" : "down"}">${esc(x.k)}${x.dekat ? `<span class="dekat">${tk("dekat")}</span>` : ""}</div>
          <div class="h mono">${esc(x.harga)}</div><div class="j mono">${esc(x.jarak)}</div></div>`).join("");
        const tanda = (d.tanda || []).map((t) => `<li>${t.level === "merah" ? IKON.merah : IKON.oranye}<span>${esc(t.teks)}</span></li>`).join("");
        const mana = d.tf === "1d" ? "hari ini" : "terakhir";
        const catatan = [d.berjalan ? (en() ? `${tk(mana)} candle is not finished, so the numbers can still change.` : `Candle ${mana} belum selesai, angka masih bisa berubah.`) : "", tk(d.catatan || "")].filter(Boolean);
        const judulTf = d.tanpaTf
          ? (en() ? `${situs.nama} doesn't provide a timeframe, so the analysis uses daily (1D). Other timeframes: open the full analysis.`
                  : `${situs.nama} tidak memberi timeframe, jadi analisa memakai harian (1D). Timeframe lain: buka analisa lengkap.`)
          : tk("Timeframe chart");
        w.innerHTML = `<div class="kartu ${memuat ? "memuat" : ""}" role="region" aria-label="Analisa Teknikal ${esc(d.simbol)}">
          <div class="kepala" title="${tk("Seret untuk memindah")}">${IKON.logo}<span class="judul">Analisa Teknikal</span><span class="tf mono" title="${esc(judulTf)}">${esc(tf)}</span>
            <div class="tombol">
              ${adaGaris() ? `<button class="ikon" type="button" data-aksi="garis" aria-pressed="${set.garis}" aria-label="${tk("Garis analisa di chart")}" title="${tk(set.garis ? "Sembunyikan" : "Tampilkan")} ${tk("garis analisa di chart (support/resistance, rencana, trendline, pola)")}">${IKON.garis}</button>` : ""}
              <button class="ikon segar" type="button" data-aksi="segar" aria-label="${tk("Muat ulang analisa")}" title="${tk("Muat ulang")}">${IKON.segar}</button>
              <button class="ikon" type="button" data-aksi="kecil" aria-label="${tk("Kecilkan kartu")}" title="${tk("Kecilkan")}">${IKON.kecil}</button>
              <button class="ikon" type="button" data-aksi="tutup" aria-label="${tk("Sembunyikan kartu")}" title="${tk("Sembunyikan")}">${IKON.tutup}</button>
            </div></div>
          <div class="isi">
            <div class="vonis"><span class="skor mono ${k}">${esc(skorTxt(d.skor))}</span>
              <div><div class="label ${k}">${esc(d.label)}</div><div class="simbol" title="${esc(d.simbol)} · ${esc(d.singkat)}"><b>${esc(d.simbol)}</b> · ${esc(d.singkat)}</div></div></div>
            ${lv ? `<div class="level">${lv}</div>` : ""}
            ${tanda ? `<ul aria-label="${tk("Tanda")}">${tanda}</ul>` : ""}
            ${d.langkah ? `<p class="langkah" title="${tk("Rencana tindakan")}"><b>→</b> ${esc(d.langkah)}</p>` : ""}
            ${catatan.map((c) => `<p class="catatan">${esc(c)}</p>`).join("")}
            <button class="buka" type="button" data-aksi="buka">${IKON.buka}${tk("Buka analisa lengkap")}</button>
          </div></div>`;
      }
      w.hidden = false;
      jepit(); terapkanPosisi();
    }

    function pesanSingkat(teksPesan) {
      pasang();
      const w = $("#wadah");
      w.innerHTML = `<div class="pesan" role="status">${esc(teksPesan)}</div>`;
      w.hidden = false; jepit(); terapkanPosisi();
      setTimeout(() => { if (ditutup) w.hidden = true; }, 5000);
    }

    function simpan(isi) { try { chrome.storage.local.set(isi); } catch { /* ekstensi dimuat ulang */ } }
    function kirimEkstensi(m) { try { chrome.runtime.sendMessage(m); } catch { /* ekstensi dimuat ulang */ } }

    let barusGeser = false;
    function klik(e) {
      const b = e.target.closest("[data-aksi]");
      if (!b) return;
      if (barusGeser) { barusGeser = false; return; }
      const aksi = b.dataset.aksi;
      if (aksi === "kecil" || aksi === "besar") { set.kecil = aksi === "kecil"; simpan({ kartuKecil: set.kecil }); render(); akar.querySelector(set.kecil ? ".pil" : '[data-aksi="kecil"]')?.focus(); }
      else if (aksi === "tutup") { ditutup = true; const pesanTutup = tk("Kartu disembunyikan sampai halaman dimuat ulang. Untuk mematikannya di semua halaman: klik kanan ikon ekstensi Analisa Teknikal."); pesanSingkat(pesanTutup); }
      else if (aksi === "segar") { tandaiMemuat(); kirimEkstensi({ type: "segarkan" }); }
      else if (aksi === "garis") { set.garis = !set.garis; simpan({ lapisanAktif: set.garis }); kirimGaris(); render(); akar.querySelector('[data-aksi="garis"]')?.focus(); }
      else if (aksi === "buka") { kirimEkstensi({ type: "buka-panel", q: qSekarang, tf: data && data.tf }); }
    }

    function mulaiGeser(e) {
      const pegangan = e.target.closest(".kepala, .pil");
      if (!pegangan || e.button !== 0 || e.target.closest(".ikon")) return;
      const awal = { x: e.clientX, y: e.clientY, kiri: set.pos.kiri, bawah: set.pos.bawah };
      let geser = false;
      try { pegangan.setPointerCapture(e.pointerId); } catch { /* tidak apa-apa */ }
      const gerak = (ev) => {
        const dx = ev.clientX - awal.x, dy = ev.clientY - awal.y;
        if (!geser && Math.hypot(dx, dy) < 4) return;
        geser = true; pegangan.classList.add("geser");
        set.pos.kiri = awal.kiri + dx; set.pos.bawah = awal.bawah - dy;
        jepit(); terapkanPosisi();
      };
      const lepas = () => {
        pegangan.removeEventListener("pointermove", gerak);
        pegangan.removeEventListener("pointerup", lepas);
        pegangan.removeEventListener("pointercancel", lepas);
        pegangan.classList.remove("geser");
        if (geser) { barusGeser = pegangan.classList.contains("pil"); simpan({ ["posisi:" + HOST]: set.pos }); }
      };
      pegangan.addEventListener("pointermove", gerak);
      pegangan.addEventListener("pointerup", lepas);
      pegangan.addEventListener("pointercancel", lepas);
    }

    function tandaiMemuat() {
      memuat = true; render();
      clearTimeout(timerMuat);
      timerMuat = setTimeout(() => { memuat = false; render(); }, 12000);
    }

    // Pengaturan tersimpan
    try {
      chrome.storage.local.get({ kartuAktif: true, kartuKecil: false, lapisanAktif: true, ["posisi:" + HOST]: null }, (v) => {
        set.aktif = v.kartuAktif !== false; set.kecil = !!v.kartuKecil; set.garis = v.lapisanAktif !== false;
        if (v["posisi:" + HOST]) set.pos = { ...POSISI_AWAL, ...v["posisi:" + HOST] };
        siap = true; render(); kirimGaris();
      });
      chrome.storage.onChanged.addListener((ch, area) => {
        if (area !== "local") return;
        if (ch.kartuAktif) { set.aktif = ch.kartuAktif.newValue !== false; render(); }
        if (ch.kartuKecil) { set.kecil = !!ch.kartuKecil.newValue; render(); }
        if (ch.lapisanAktif) { set.garis = ch.lapisanAktif.newValue !== false; kirimGaris(); render(); }
      });
    } catch { siap = true; }
    addEventListener("resize", () => { if (host && !$("#wadah").hidden) { jepit(); terapkanPosisi(); } });

    return {
      gantiSimbol(q) {
        // Garis milik simbol/interval sebelumnya dibuang; garis baru datang bersama analisa barunya.
        if (lapisan) { lapisan = null; kirimGaris(); }
        if (!q) { data = null; render(); } else if (data) tandaiMemuat();
      },
      terima(m) {
        if ((m.q || "") !== qSekarang) return;  // jawaban untuk simbol sebelumnya
        if (m.iv != null && m.iv !== ivSekarang) return;  // jawaban untuk interval sebelumnya
        clearTimeout(timerMuat); memuat = false;
        data = m.data ? { ...m.data, catatan: m.catatan || "", tanpaTf: !!m.tanpaTf } : null;
        lapisan = m.data && m.lapisan ? { untuk: { q: m.q, iv: m.iv || "" }, L: m.lapisan } : null;
        kirimGaris();
        render();
      },
    };
  })();

  chrome.runtime.onMessage.addListener((m, _s, balas) => {
    if (!m) return;
    if (m.type === "minta") balas(deteksi());
    else if (m.type === "kartu") kartu.terima(m);
  });
  if (situs.nama === "TradingView") {
    document.addEventListener(EV_TV, (e) => {
      let d = null;
      try { d = JSON.parse(e.detail); } catch { d = null; }
      tvUtama = d && typeof d.q === "string" && d.q ? { q: d.q.slice(0, 60), iv: String(d.iv || "").slice(0, 8) } : null;
      kirim(false);
    });
    try { document.dispatchEvent(new CustomEvent(EV_MINTA)); } catch { /* abaikan */ }
  }
  setInterval(() => kirim(false), 1000);
  document.addEventListener("visibilitychange", () => { if (!document.hidden) kirim(true); });
  kirim(true);
})();
