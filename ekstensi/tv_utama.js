// Analisa Teknikal — skrip di "dunia halaman" TradingView (manifest: world MAIN), hanya di tradingview.com.
// 1) Membaca simbol & interval chart aktif langsung dari API chart TradingView dan mengabari content.js begitu berubah.
// 2) Menggambar garis analisa (lapisan.js) di atas chart: satu <canvas> tembus-klik di dalam panel harga,
//    dan satu lagi di sumbu harga untuk label harga garis-garis itu.
// Tidak membuat drawing TradingView, tidak mengubah atau menyimpan apa pun di chart pengguna, tidak memuat data portofolio.
(() => {
  "use strict";
  if (window.__analisaTeknikalUtama) return;
  window.__analisaTeknikalUtama = true;

  const EV_TV = "analisa-teknikal:tv";            // utama -> content.js : { q, iv }
  const EV_LAPISAN = "analisa-teknikal:lapisan";  // content.js -> utama : { untuk: { q, iv }, lapisan, aktif }
  const EV_MINTA = "analisa-teknikal:minta";      // content.js -> utama : kirim ulang simbol sekarang
  const LABEL_TF = { "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1D", "1wk": "1W", "1mo": "1M" };
  const WIB = 7 * 3600;

  let api = null, terakhir = null, data = null, kanvas = null, kanvasSumbu = null, tanda = "", raf = 0, versi = 0;
  const sudahLanggan = new WeakSet();

  const ambilApi = () => { try { const a = window.TradingViewApi; return a && typeof a.activeChart === "function" ? a : null; } catch { return null; } };
  const chartAktif = () => { try { return api ? api.activeChart() : null; } catch { return null; } };

  // ------------------------------------------------------------------
  // 1. Simbol & interval
  // ------------------------------------------------------------------
  function baca() {
    const c = chartAktif();
    if (!c) return null;
    try {
      const s = typeof c.symbolExt === "function" ? c.symbolExt() : null;
      const q = String((s && (s.pro_name || s.full_name)) || c.symbol() || "").toUpperCase();
      return q ? { q, iv: String(c.resolution() || "") } : null;
    } catch { return null; }
  }
  function kabari(paksa) {
    const d = baca();
    const kunci = d ? `${d.q}|${d.iv}` : "";
    if (!paksa && kunci === terakhir) return;
    terakhir = kunci;
    // Garis milik simbol/interval sebelumnya langsung dihapus; garis baru datang bersama analisa barunya.
    if (data && (!d || data.untuk.q !== d.q || data.untuk.iv !== d.iv)) { data = null; bersihkan(); }
    document.dispatchEvent(new CustomEvent(EV_TV, { detail: JSON.stringify(d || { q: "", iv: "" }) }));
  }
  function langgan() {
    const c = chartAktif();
    if (!c || sudahLanggan.has(c)) return;
    sudahLanggan.add(c);
    const berubah = () => { kabari(false); setTimeout(() => kabari(false), 120); };
    try { c.onSymbolChanged().subscribe(null, berubah); } catch { /* API berbeda: pemeriksaan berkala di bawah tetap jalan */ }
    try { c.onIntervalChanged().subscribe(null, berubah); } catch { /* idem */ }
  }
  setInterval(() => {
    if (!api) api = ambilApi();
    if (api) { langgan(); kabari(false); }
  }, 400);
  document.addEventListener(EV_MINTA, () => { if (!api) api = ambilApi(); kabari(true); });

  // ------------------------------------------------------------------
  // 2. Lapisan garis di atas chart
  // ------------------------------------------------------------------
  function bersihkan() {
    if (kanvas && kanvas.isConnected) kanvas.remove();
    if (kanvasSumbu && kanvasSumbu.isConnected) kanvasSumbu.remove();
    tanda = "";
  }

  // Panel harga utama chart aktif (tempat candle digambar).
  function panelUtama(c) {
    let idx = 0;
    try { idx = Math.max(0, c.getPanes().findIndex((p) => p.hasMainSeries())); } catch { idx = 0; }
    const akar = document.querySelector(".chart-container.active") || document;
    const panel = akar.querySelectorAll(".chart-markup-table.pane")[idx];
    if (!panel) return null;
    // Sumbu harga di baris yang sama (kanan bila ada, kalau tidak yang kiri).
    const sumbu = panel.parentElement ? [...panel.parentElement.querySelectorAll(".price-axis-container .price-axis")].filter((e) => e.clientWidth > 0).pop() : null;
    return { el: panel.querySelector(".chart-gui-wrapper") || panel, idx, sumbu: sumbu || null };
  }

  function siapkanKanvas(k, induk, w, h, dpr) {
    if (!k) {
      k = document.createElement("canvas");
      k.setAttribute("data-analisa-teknikal", "lapisan");
      k.setAttribute("aria-hidden", "true");
      k.style.cssText = "position:absolute;left:0;top:0;width:100%;height:100%;pointer-events:none;z-index:2;";
    }
    if (k.parentElement !== induk) induk.appendChild(k);
    const lw = Math.round(w * dpr), lh = Math.round(h * dpr);
    if (k.width !== lw || k.height !== lh) { k.width = lw; k.height = lh; }
    const ctx = k.getContext("2d");
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    return [k, ctx];
  }

  // Bar yang sedang terlihat: [{ t: waktu buka (detik), x: pusat bar (piksel) }], urut dari kiri.
  function barTerlihat(ts, w) {
    const bs = ts.barSpacing();
    if (!(bs > 0)) return [];
    const langkah = Math.max(0.5, bs / 2);
    const tepi = [];
    let lalu;
    for (let x = 0; x <= w; x += langkah) {
      const t = ts.coordinateToTime(x);
      if (t == null) { lalu = undefined; continue; }
      if (t !== lalu) { tepi.push({ t, x }); lalu = t; }
    }
    if (tepi.length < 2 || bs < 2) return tepi.map((e) => ({ t: e.t, x: e.x + bs / 2 }));
    // Satu batas bar diperhalus dengan bagi-dua; pusat bar lain dihitung dari situ (jarak antar bar = barSpacing).
    let lo = tepi[1].x - langkah, hi = tepi[1].x;
    for (let i = 0; i < 12; i++) { const m = (lo + hi) / 2; if (ts.coordinateToTime(m) === tepi[1].t) hi = m; else lo = m; }
    return tepi.map((e, i) => ({ t: e.t, x: hi + (i - 1) * bs + bs / 2 }));
  }

  // Fungsi indeks bar analisa -> piksel x di chart TradingView, dengan mencocokkan waktu bar.
  // Harian/mingguan/bulanan dicocokkan per tanggal/minggu/bulan (WIB), intraday per waktu buka bar.
  function petaX(L, bar, bs) {
    if (!bar.length || !L.waktu || !L.waktu.length) return () => null;
    const kunci = L.tf === "1d" ? (t) => Math.floor((t + WIB) / 86400)
      : L.tf === "1wk" ? (t) => Math.floor(((t + WIB) / 86400 + 3) / 7)
      : L.tf === "1mo" ? (t) => { const d = new Date((t + WIB) * 1000); return d.getUTCFullYear() * 12 + d.getUTCMonth(); }
      : (t) => t;
    const kb = bar.map((b) => kunci(b.t));
    let jarakMin = Infinity;
    for (let i = 1; i < kb.length; i++) if (kb[i] > kb[i - 1]) jarakMin = Math.min(jarakMin, kb[i] - kb[i - 1]);
    if (!isFinite(jarakMin)) jarakMin = 1;
    const xs = L.waktu.map((t) => {
      const k = kunci(t);
      let lo = 0, hi = kb.length - 1, i = -1;
      while (lo <= hi) { const m = (lo + hi) >> 1; if (kb[m] <= k) { i = m; lo = m + 1; } else hi = m - 1; }
      if (i < 0) return null;
      while (i > 0 && kb[i - 1] === kb[i]) i--;
      const batas = i < kb.length - 1 && kb[i + 1] > kb[i] ? kb[i + 1] : kb[i] + jarakMin;
      return k < batas ? bar[i].x : null;
    });
    const cocok = [];
    xs.forEach((x, j) => { if (x != null) cocok.push(j); });
    if (!cocok.length) return () => null;
    const a = cocok[0], z = cocok[cocok.length - 1];
    const langkah = z > a && xs[z] > xs[a] ? (xs[z] - xs[a]) / (z - a) : bs;  // piksel per bar analisa
    const di = (j) => {
      if (j >= a && j <= z) {
        if (xs[j] != null) return xs[j];
        for (let d = 1; d < xs.length; d++) {  // celah (bar yang tidak ada di chart ini): pakai tetangga terdekat
          if (xs[j - d] != null) return xs[j - d] + d * langkah;
          if (xs[j + d] != null) return xs[j + d] - d * langkah;
        }
      }
      const dekat = j < a ? a : z;
      return xs[dekat] + (j - dekat) * langkah;
    };
    return (i) => {
      const j = i - L.awal, f = Math.floor(j), r = j - f, x0 = di(f);
      return r ? x0 + (di(f + 1) - x0) * r : x0;
    };
  }

  function gambar() {
    const c = chartAktif(), d = baca();
    if (!c || !d || d.q !== data.untuk.q || d.iv !== data.untuk.iv) return bersihkan();
    const pu = panelUtama(c);
    if (!pu) return bersihkan();
    let ps, ts, rentang, geser;
    try {
      ps = c.getPanes()[pu.idx].getMainSourcePriceScale();
      ts = c.getTimeScale();
      rentang = ps.getVisiblePriceRange();
      geser = typeof c.getTimeScaleLogicalRange === "function" ? JSON.stringify(c.getTimeScaleLogicalRange()) : `${ts.coordinateToTime(0)}:${performance.now() >> 6}`;
    } catch { return; }
    if (!ps || !ts || !rentang) return;
    const w = pu.el.clientWidth, h = pu.el.clientHeight, dpr = window.devicePixelRatio || 1;
    if (!(w > 0) || !(h > 0)) return;
    const widget = pu.el.closest(".chart-widget");
    const gelap = !!widget && /themed-dark/.test(widget.className);
    const t = [w, h, pu.sumbu ? pu.sumbu.clientWidth : 0, dpr, rentang.from, rentang.to, ps.getMode && ps.getMode(), ps.isInverted && ps.isInverted(), ts.barSpacing(), geser, gelap, data.versi].join("|");
    if (t === tanda && kanvas && kanvas.parentElement === pu.el && (!pu.sumbu || (kanvasSumbu && kanvasSumbu.parentElement === pu.sumbu))) return;  // tidak ada yang berubah
    tanda = t;

    let ctx;
    [kanvas, ctx] = siapkanKanvas(kanvas, pu.el, w, h, dpr);
    const L = data.L;
    const x = petaX(L, barTerlihat(ts, w), ts.barSpacing());
    const y = (p) => ps.priceToCoordinate(p);
    // Harga tiap garis ditulis di sumbu harga (seperti garis bawaan TradingView); di chart cukup namanya.
    const hasil = window.ATLapisan.gambar(ctx, L, { w, h, gelap, x, y },
      { hargaWajib: !pu.sumbu, nSr: 3, keterangan: `Analisa Teknikal · ${LABEL_TF[L.tf] || L.tf}${typeof L.skor === "number" ? ` · ${L.skor > 0 ? "+" : L.skor < 0 ? "−" : ""}${Math.abs(L.skor)} ${L.label || ""}` : ""}` });
    if (pu.sumbu) {
      const sw = pu.sumbu.clientWidth, sh = pu.sumbu.clientHeight;
      let cs;
      [kanvasSumbu, cs] = siapkanKanvas(kanvasSumbu, pu.sumbu, sw, sh, dpr);
      let format = null;  // format angka sumbu TradingView sendiri, supaya label kita seragam dengan angkanya
      try { const f = c.priceFormatter(); if (f && typeof f.format === "function") format = (p) => f.format(p); } catch { format = null; }
      window.ATLapisan.gambarSumbu(cs, hasil.sumbu, { w: sw, h: sh, format, hindariY: y(L.harga) });
    } else if (kanvasSumbu && kanvasSumbu.isConnected) kanvasSumbu.remove();
  }

  function putar() {
    if (raf) return;
    const langkah = () => {
      raf = 0;
      if (!data || !data.aktif || !data.L || data.L.kuotasi_lain || !window.ATLapisan) { bersihkan(); return; }
      try { gambar(); } catch { /* API chart sedang berganti: coba lagi di bingkai berikutnya */ }
      raf = requestAnimationFrame(langkah);
    };
    raf = requestAnimationFrame(langkah);
  }

  document.addEventListener(EV_LAPISAN, (e) => {
    let m = null;
    try { m = JSON.parse(e.detail); } catch { m = null; }
    if (!m || !m.untuk || !m.lapisan) { data = null; bersihkan(); return; }
    data = { untuk: { q: String(m.untuk.q || ""), iv: String(m.untuk.iv || "") }, L: m.lapisan, aktif: m.aktif !== false, versi: ++versi };
    tanda = "";
    if (data.aktif) putar(); else bersihkan();
  });

  if (!api) api = ambilApi();
  if (api) { langgan(); kabari(true); }
})();
