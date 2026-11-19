/* Analisa Teknikal — format angka, ikon, dan tampilan Portofolio.
   Dipakai panel lokal (mode "panel": klik baris membuka aset di Cek aset)
   dan laporan teknikal.html (mode "statis": klik baris membuka chart PNG).

   Aturan angka (satu gaya di semua tempat):
   - harga mengikuti pasarnya: IDX 5.075 · AS/kripto $181.60 (≥ $1.000 tanpa sen: $64,828; < $1 empat angka penting)
   - persen, skor, rasio, indikator: desimal koma, tanda minus "−" (U+2212) */
(function (root) {
  "use strict";
  const MINUS = "−";
  // Bahasa tampilan (web/bahasa.js). Tanpa berkas itu, semuanya tetap bahasa Indonesia.
  const B = root.ATB || { t: (x, v) => (v ? x.replace(/\{(\w+)\}/g, (_, k) => (v[k] == null ? "" : String(v[k]))) : x), en: false, lokal: "id-ID", lokalTanggal: "id-ID" };
  const t = B.t;
  const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  const kosong = (x) => x === null || x === undefined || Number.isNaN(x);

  function num(x, d = 1, sign = false) {
    if (kosong(x)) return "—";
    const nol = Number(Math.abs(x).toFixed(d)) === 0;
    const s = Math.abs(x).toLocaleString(B.lokal, { minimumFractionDigits: d, maximumFractionDigits: d });
    return (x < 0 && !nol ? MINUS : sign && x > 0 && !nol ? "+" : "") + s;
  }
  const pct = (x, sign = true) => (kosong(x) ? "—" : num(x, 1, sign) + "%");
  const skorTxt = (s) => (kosong(s) ? "—" : num(Math.round(s), 0, true));

  const idxTick = (p) => (p < 200 ? 1 : p < 500 ? 2 : p < 2000 ? 5 : p < 5000 ? 10 : 25);
  function dec(p, mk) {
    if (mk === "idx") return 0;
    if (mk === "lain") return Math.abs(p) >= 100 ? 2 : Math.abs(p) >= 1 ? 4 : 6;
    // dolar (saham AS & kripto), sama dengan ta_engine.desimal_dolar
    const a = Math.abs(p);
    if (a >= 1000) return 0;
    if (a >= 1 || !a) return 2;
    return Math.min(10, 3 - Math.floor(Math.log10(a)));
  }
  function fp(p, mk) {
    if (kosong(p)) return "—";
    const tanda = p < 0 ? MINUS : "";
    const a = Math.abs(p);
    if (mk === "idx") { const fraksi = idxTick(a); return tanda + (Math.round(a / fraksi) * fraksi).toLocaleString(B.lokal); }
    const d = dec(a, mk);
    const s = a.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
    return tanda + (mk === "lain" ? s : "$" + s);
  }
  // Indonesia: M = miliar, jt = juta. Inggris: B = billion, M = million.
  const rp = (x) => (kosong(x) ? "—" : Math.abs(x) >= 1e9 ? "Rp " + num(x / 1e9, 2) + (B.en ? " B" : " M") : "Rp " + num(x / 1e6, 1) + (B.en ? " M" : " jt"));
  const cls = (s) => (s >= 20 ? "up" : s <= -20 ? "down" : "flat");
  const BOBOT = { merah: 3, oranye: 2, hijau: 0, info: 0 };
  // Tanda baru = belum ada di pindai hari bursa sebelumnya. Data lama tanpa kolom "baru" dianggap baru.
  const baru = (f) => f.baru !== false;
  const nilaiTanda = (f) => (BOBOT[f.level] || 0) * (baru(f) ? 4 : 1) + (baru(f) ? 0.5 : 0);
  const urutTanda = (fl) => (fl || []).slice().sort((x, y) => nilaiTanda(y) - nilaiTanda(x));
  const perhatian = (a) => (a.bendera || []).reduce((s, f) => s + nilaiTanda(f), 0);
  const pentingBaru = (a) => (a.bendera || []).some((f) => baru(f) && (f.level === "merah" || f.level === "oranye"));
  const tglPendek = (s) => { const d = new Date(String(s) + "T00:00:00"); return Number.isNaN(d.getTime()) ? String(s) : d.toLocaleDateString(B.lokalTanggal, { day: "numeric", month: "short" }); };
  const tagTanda = (f) => (f.baru === true ? `<span class="tbaru">${t("Baru")}</span>` : "");
  const sejakTanda = (f) => (f.baru === false && f.sejak ? `<span class="sejak">${t("sejak")} ${esc(tglPendek(f.sejak))}</span>` : "");
  const PASAR_NAMA = { idx: "IDX", us: t("AS"), crypto: t("kripto"), lain: t("indeks/forex") };

  // Garis kecil skor (−100…+100). titik = [[waktu, skor], ...]
  function sparkline(titik, { w = 72, h = 22, label = "" } = {}) {
    if (!titik || titik.length < 2) return `<span class="faint">—</span>`;
    const pad = 2, n = titik.length;
    const xs = (i) => pad + (i * (w - 2 * pad)) / (n - 1);
    const ys = (v) => pad + ((100 - Math.max(-100, Math.min(100, v))) * (h - 2 * pad)) / 200;
    const d = titik.map((p, i) => `${i ? "L" : "M"}${xs(i).toFixed(1)},${ys(p[1]).toFixed(1)}`).join("");
    const akhir = titik[n - 1][1], awal = titik[0][1];
    const warna = akhir >= 20 ? "var(--bull)" : akhir <= -20 ? "var(--bear)" : "var(--neutral)";
    const lbl = label || t("Skor {n} bar: dari {a} ke {b}", { n, a: skorTxt(awal), b: skorTxt(akhir) });
    return `<svg class="spark" viewBox="0 0 ${w} ${h}" width="${w}" height="${h}" role="img" aria-label="${esc(lbl)}"><title>${esc(lbl)}</title><line x1="0" x2="${w}" y1="${ys(0).toFixed(1)}" y2="${ys(0).toFixed(1)}" class="nol"/><path d="${d}" fill="none" stroke="${warna}" stroke-width="1.5" stroke-linejoin="round"/><circle cx="${xs(n - 1).toFixed(1)}" cy="${ys(akhir).toFixed(1)}" r="2.2" fill="${warna}"/></svg>`;
  }
  const sebutRs = (x) => t(x >= 2 ? "lebih kuat" : x <= -2 ? "lebih lemah" : "sejalan");
  // Arah kekuatan relatif ditulis sebagai akibatnya ("unggulnya menyusut"), bukan "lebih kuat · melemah" yang terbaca bertentangan.
  const RS_FRASA = { kuat: { naik: "unggulnya melebar", turun: "unggulnya menyusut" }, lemah: { naik: "mulai mengejar", turun: "makin tertinggal" }, sejalan: { naik: "mulai unggul", turun: "mulai tertinggal" } };
  function arahRs(rs) {
    const a = { menguat: "naik", strengthening: "naik", melemah: "turun", weakening: "turun" }[rs.tren];
    return a ? t(RS_FRASA[rs.rs20 >= 2 ? "kuat" : rs.rs20 <= -2 ? "lemah" : "sejalan"][a]) : "";
  }
  function rsHtml(rs, ringkas = false) {
    if (!rs || rs.rs20 == null) return ringkas ? `<span class="faint">—</span>` : "";
    const c = rs.rs20 >= 2 ? "up" : rs.rs20 <= -2 ? "down" : "flat";
    if (ringkas) return `<span class="num ${c}" title="20 ${esc(rs.satuan || t("hari"))}: ${esc(rs.acuan)} ${pct(rs.acuan20)}, ${t("aset")} ${pct(rs.aset20)}">${pct(rs.rs20)}</span><span class="delta faint">vs ${esc(rs.acuan)}</span>`;
    return `<p class="rsline"><span>vs ${esc(rs.acuan)} · 20 ${esc(rs.satuan || t("hari"))}</span><b class="num ${c}">${pct(rs.rs20)}</b><span class="${c}">${sebutRs(rs.rs20)}</span>${arahRs(rs) ? `<span class="faint">· ${esc(arahRs(rs))}</span>` : ""}</p>`;
  }
  // ---------- istilah teknis: arti awam muncul saat disorot / diklik ----------
  // [pola, arti Indonesia, arti Inggris]. Istilahnya sendiri tetap (sama dengan yang dipakai TradingView).
  const ISTILAH = [
    [/higher highs?\b/i, "Puncak harga makin tinggi dari puncak sebelumnya.", "Each price peak is higher than the one before."],
    [/higher lows?\b/i, "Dasar harga makin tinggi dari dasar sebelumnya: penjual makin lemah.", "Each price trough is higher than the one before: sellers are weakening."],
    [/lower highs?\b/i, "Puncak harga makin rendah dari puncak sebelumnya: pembeli makin lemah.", "Each price peak is lower than the one before: buyers are weakening."],
    [/lower lows?\b/i, "Dasar harga makin rendah dari dasar sebelumnya.", "Each price trough is lower than the one before."],
    [/\b(?:Downtrend kuat|Strong downtrend|Downtrend)\b/, "Arah harga 50 bar terakhir turun. “Kuat” = turunnya curam, strukturnya searah, dan ADX ≥ 25.", "Price direction over the last 50 bars is down. “Strong” = steep, with matching structure and ADX ≥ 25."],
    [/\b(?:Uptrend kuat|Strong uptrend|Uptrend)\b/, "Arah harga 50 bar terakhir naik. “Kuat” = naiknya curam, strukturnya searah, dan ADX ≥ 25.", "Price direction over the last 50 bars is up. “Strong” = steep, with matching structure and ADX ≥ 25."],
    [/\bSideways\b/, "Harga bergerak mendatar: belum ada arah yang jelas dalam 50 bar terakhir.", "Price is moving flat: no clear direction over the last 50 bars."],
    [/\b(?:konfluensi|confluence)\b/i, "Apakah timeframe lain (mis. mingguan) searah. Searah = sinyal lebih bisa dipercaya.", "Whether other timeframes (e.g. weekly) agree. Agreement makes the signal more reliable."],
    [/\bGolden cross\b/i, "MA50 memotong MA200 ke atas: tanda tren jangka panjang berbalik naik.", "MA50 crosses above MA200: a sign the long-term trend is turning up."],
    [/\bDeath cross\b/i, "MA50 memotong MA200 ke bawah: tanda tren jangka panjang berbalik turun.", "MA50 crosses below MA200: a sign the long-term trend is turning down."],
    [/\bMA ?200\b/, "Rata-rata harga 200 bar terakhir: garis tren jangka panjang. Harga di atasnya = tren besar naik.", "Average price of the last 200 bars: the long-term trend line. Price above it = bigger trend is up."],
    [/\bMA ?50\b/, "Rata-rata harga 50 bar terakhir: garis tren jangka menengah.", "Average price of the last 50 bars: the medium-term trend line."],
    [/\bRSI\b/, "Pengukur kecepatan gerak harga, 0–100. Di bawah 30 = jenuh jual (oversold), di atas 70 = jenuh beli (overbought).", "Speed-of-move gauge, 0–100. Below 30 = oversold, above 70 = overbought."],
    [/\boversold\b/i, "Jenuh jual: harga sudah turun cepat, sering diikuti pantulan (belum tentu berbalik).", "Price has fallen fast; often followed by a bounce (not necessarily a reversal)."],
    [/\boverbought\b/i, "Jenuh beli: harga sudah naik cepat, rawan koreksi.", "Price has risen fast; prone to a pullback."],
    [/\bMACD\b/, "Selisih dua rata-rata harga (cepat dan lambat). Di atas garis signal = dorongan naik menguat; di atas nol = tren naik.", "Difference between a fast and a slow price average. Above the signal line = upside momentum building; above zero = uptrend."],
    [/\bhistogram\b/i, "Selisih MACD dan garis signal. Membesar = dorongannya menguat.", "Gap between MACD and its signal line. Growing = momentum building."],
    [/\bStochastic\b/i, "Posisi harga di dalam rentang 14 bar terakhir. “Cross” = dua garisnya berpotongan, tanda momentum berbalik.", "Where price sits inside its 14-bar range. A “cross” of its two lines signals a momentum turn."],
    [/\bADX\b/, "Kekuatan tren, 0–100 (bukan arahnya). ≥ 25 tren kuat, < 18 cenderung mendatar.", "Trend strength, 0–100 (not direction). ≥ 25 strong trend, < 18 mostly flat."],
    [/\b(?:arah DI (?:naik|turun)|DI pointing (?:up|down))\b/, "Arah tren menurut ADX: naik = pembeli lebih kuat, turun = penjual lebih kuat.", "Trend direction per ADX: up = buyers stronger, down = sellers stronger."],
    [/\bOBV\b/, "Akumulasi volume. Naik = volume lebih besar di hari harga naik (ada yang mengumpulkan).", "Running volume total. Rising = more volume on up days (accumulation)."],
    [/\bATR\b/, "Rata-rata rentang gerak harga per bar: ukuran seberapa bergejolak.", "Average price range per bar: a measure of volatility."],
    [/\bBollinger\b/i, "Pita di atas dan bawah rata-rata 20 bar. Harga di luar pita = sudah meregang; pita menyempit (squeeze) = sering mendahului gerakan besar.", "Bands above and below the 20-bar average. Price outside = stretched; narrow bands (squeeze) often precede a big move."],
    [/\bdivergence\b/i, "Harga dan indikator bergerak berlawanan arah (mis. harga turun lebih dalam, RSI tidak): sering mendahului pembalikan.", "Price and an indicator move in opposite directions (e.g. lower price low, higher RSI low): often precedes a reversal."],
    [/\bneckline\b/i, "Garis leher pola: batas yang harus ditembus dengan close supaya polanya sah.", "The pattern’s trigger line: a close beyond it confirms the pattern."],
    [/\bbreakout\b/i, "Harga menembus batas atas (resistance / pola).", "Price breaks above a ceiling (resistance / pattern boundary)."],
    [/\bbreakdown\b/i, "Harga jebol batas bawah (support / pola).", "Price breaks below a floor (support / pattern boundary)."],
    [/\bpullback\b/i, "Koreksi sementara di dalam tren naik.", "A temporary dip within an uptrend."],
    [/\bR:R\b/, "Perbandingan potensi untung dengan risiko. Di bawah 1 = potensi untungnya lebih kecil daripada risikonya.", "Reward-to-risk ratio. Below 1 = the potential gain is smaller than the risk."],
    [/\b(?:candle pembalikan|reversal candle)\b/i, "Candle dengan ekor bawah panjang atau badan hijau besar di dekat support: tanda pembeli mulai masuk.", "A candle with a long lower wick or a big green body near support: a sign buyers are stepping in."],
  ];
  // ist(teks mentah) -> HTML aman; tiap istilah ditandai sekali per teks.
  function ist(s) {
    s = String(s ?? "");
    const kena = [];
    ISTILAH.forEach(([re, id, en]) => {
      const m = re.exec(s);
      if (!m) return;
      const a = m.index, b = a + m[0].length;
      if (!kena.some((x) => a < x.b && b > x.a)) kena.push({ a, b, tip: B.en ? en : id });
    });
    if (!kena.length) return esc(s);
    kena.sort((x, y) => x.a - y.a);
    let out = "", i = 0;
    kena.forEach((x) => { out += esc(s.slice(i, x.a)) + `<span class="ist" data-tip="${esc(x.tip)}">${esc(s.slice(x.a, x.b))}</span>`; i = x.b; });
    return out + esc(s.slice(i));
  }
  if (root.document && !root.__atIst) {
    root.__atIst = true;
    let tip = null, aktif = null;
    const tutup = () => { if (tip) tip.hidden = true; aktif = null; };
    const buka = (el) => {
      if (!tip) { tip = document.createElement("div"); tip.className = "ist-tip"; tip.setAttribute("role", "tooltip"); document.body.appendChild(tip); }
      tip.textContent = el.dataset.tip; tip.hidden = false; aktif = el;
      const r = el.getBoundingClientRect(), lebar = Math.min(300, window.innerWidth - 16);
      tip.style.maxWidth = lebar + "px";
      const tr = tip.getBoundingClientRect();
      const x = Math.max(8, Math.min(window.innerWidth - tr.width - 8, r.left + r.width / 2 - tr.width / 2));
      const y = r.bottom + 6 + tr.height > window.innerHeight - 8 ? r.top - tr.height - 6 : r.bottom + 6;
      tip.style.left = x + "px"; tip.style.top = Math.max(8, y) + "px";
    };
    document.addEventListener("mouseover", (e) => { const el = e.target.closest && e.target.closest(".ist"); if (el) buka(el); else if (aktif) tutup(); });
    document.addEventListener("click", (e) => { const el = e.target.closest && e.target.closest(".ist"); if (el) { if (aktif === el && !tip.hidden && e.pointerType !== "mouse") tutup(); else buka(el); } else tutup(); }, true);
    document.addEventListener("scroll", tutup, true);
    document.addEventListener("keydown", (e) => { if (e.key === "Escape") tutup(); });
  }
  function narasiHtml(n) {
    if (!n || !n.paragraf) return "";
    return (n.inti ? `<p class="inti">${ist(n.inti)}</p>` : "") + n.paragraf.filter(Boolean).map((x) => `<p>${ist(x)}</p>`).join("");
  }
  // Rencana tindakan (dari wawasan.rencana_aksi): judul + langkah "jika … maka …". posisi = catatan posisi (Portofolio saja).
  // hindari: "Jangan tambah dulu" hanya bila rencana dihitung dengan data posisi (tab Portofolio); selain itu "Belum saatnya beli".
  const SIKAP = { hindari: ["short", "Jangan tambah dulu"], beli: ["long", "Di area beli"], tunggu_koreksi: ["wait", "Tunggu koreksi"], tunggu: ["wait", "Tunggu arah"] };
  const ARAH_IKON = { naik: ["trend-up", "up"], turun: ["trend-down", "down"], tahan: ["flat", "faint"] };
  function aksiHtml(ra, { posisi = true } = {}) {
    if (!ra || !ra.langkah) return "";
    const langkah = ra.langkah.map((x) => { const [id, c] = ARAH_IKON[x.arah] || ARAH_IKON.tahan;
      return `<li><span class="ar ${c}">${icon(id)}</span><div><div class="kond">${t("Jika")} ${ist(x.kondisi.charAt(0).toLowerCase() + x.kondisi.slice(1))}${x.jarak_pct != null ? ` <span class="jarak num">${pct(x.jarak_pct)}</span>` : ""}</div><div class="tind">${ist(x.tindakan)}</div></div></li>`; }).join("");
    return `<p class="aksi-judul">${ist(ra.judul)}</p><ol class="langkah">${langkah}</ol>${posisi && ra.posisi ? `<p class="aksi-pos">${icon("info", "sm")}<span>${esc(ra.posisi)}</span></p>` : ""}`;
  }
  function sikapPill(ra) {
    ra = ra || {};
    let [c, teks] = SIKAP[ra.sikap] || SIKAP.tunggu;
    if (ra.sikap === "hindari" && !ra.punya) teks = "Belum saatnya beli";
    if (ra.sikap === "beli" && ra.rr_rendah) { c = "wait"; teks = "Area beli · R:R rendah"; }  // target lebih dekat daripada stop: bukan ajakan beli
    return `<span class="pill ${c}">${t(teks)}</span>`;
  }
  const ringkasAksi = (ra) => (ra && (ra.ringkas || ra.judul)) || "";
  // Daftar sinyal. Kontribusi ditulis dalam poin skor (jumlahnya = skor), bukan angka mentah mesin; sinyal yang
  // tidak mengubah skor (keterangan saja) diredupkan dan dilipat.
  function poinSkor(sinyal, skor) {
    const total = (sinyal || []).reduce((s, x) => s + (x.score || 0), 0);
    return Math.abs(total) < 0.05 ? () => 0 : (v) => (v * skor) / total;
  }
  function sinyalHtml(sinyal, skor) {
    const ke = poinSkor(sinyal, skor);
    const urut = (sinyal || []).slice().sort((x, y) => Math.abs(y.score) - Math.abs(x.score));
    const li = (s) => `<li>${biasIcon(s.score)}<span>${ist(s.text)}<span class="sub">${esc(s.cat)}</span></span><span class="sc ${s.score > 0 ? "up" : s.score < 0 ? "down" : ""}">${s.score ? num(ke(s.score), 0, true) : ""}</span></li>`;
    const ada = urut.filter((s) => s.score), nol = urut.filter((s) => !s.score);
    return `<ul class="items">${ada.map(li).join("")}</ul>` + (nol.length ? `<details class="sig-nol"><summary>${t("{n} keterangan lain (tidak mengubah skor)", { n: nol.length })}</summary><ul class="items">${nol.map(li).join("")}</ul></details>` : "");
  }
  const dekatTag = (x) => (x && x.dekat ? `<span class="dekat" title="${t("Harga sangat dekat level ini")}">${t("dekat")}</span>` : "");
  const KELAS = { idx: t("Saham IDX"), us: t("Saham/ETF AS"), crypto: t("Kripto") };

  // Ikon dekoratif disembunyikan dari pembaca layar; ikon bermakna diberi label.
  function icon(id, c = "", label = "") {
    return label
      ? `<svg class="ico ${c}" role="img" aria-label="${esc(label)}"><use href="#i-${id}"/></svg>`
      : `<svg class="ico ${c}" aria-hidden="true" focusable="false"><use href="#i-${id}"/></svg>`;
  }
  // Tingkat tanda: bentuk + warna + label, jadi tidak bergantung pada warna saja.
  const SEV = { merah: ["alert", "down", t("Penting")], oranye: ["warn", "flat", t("Waspada")], hijau: ["ok", "up", t("Positif")], info: ["info", "faint", "Info"] };
  const sevIcon = (level) => { const [id, c, lbl] = SEV[level] || SEV.info; return icon(id, c, lbl); };
  const biasIcon = (b) => (b > 0 ? icon("trend-up", "up", "Bullish") : b < 0 ? icon("trend-down", "down", "Bearish") : icon("flat", "faint", t("Netral")));

  function namaFile(t) { return String(t).replace(/[^A-Za-z0-9_.-]/g, "_"); }
  function waktu(iso) {
    try { const d = new Date(iso); if (Number.isNaN(d.getTime())) return iso; return d.toLocaleString(B.lokalTanggal, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); } catch { return iso; }
  }
  const skorTf = (a, tf) => { const m = (a.mtf || []).find((x) => x.tf === tf); return m ? m.score : null; };

  const KOLOM = [
    ["simbol", t("Aset"), ""], ["harga", t("Harga"), "r"], ["pl_pct", "P/L", "r"], ["bobot", t("Bobot"), "r"],
    ["skor", t("Skor"), "r"], ["w1", "1W", "r"], ["", t("30 hari"), "r"], ["rs", t("vs pasar"), "r"], ["s1", "S1 · R1", "r"], ["perhatian", t("Sinyal & langkah"), ""],
  ];

  function renderPortofolio(el, data, opts = {}) {
    const mode = opts.mode || "statis";
    // Daftar pantau saja (tanpa folder portofolio, mis. paket untuk orang lain): tanpa kolom P/L, bobot, dan nilai.
    const pantauSaja = !(data.aset || []).length && (data.pantauan || []).length > 0;
    const aset = (pantauSaja ? data.pantauan : data.aset || []).slice();
    const kolom = pantauSaja ? KOLOM.filter(([kk]) => kk !== "pl_pct" && kk !== "bobot") : KOLOM;
    const nKol = kolom.length + 1;
    const rataSkor = aset.length ? Math.round(aset.reduce((s, a) => s + (a.skor || 0), 0) / aset.length) : 0;
    const R = data.ringkasan || {};
    const lalu = el._atState || {};  // dipertahankan saat data diperbarui (mis. selesai pindai)
    const filter = lalu.filter || { kelas: "all", hanyaPerlu: false };
    let sortKey = lalu.sortKey || "perhatian", sortDir = lalu.sortDir || -1;
    const ingat = () => { el._atState = { filter, sortKey, sortDir }; };

    const total = (pantauSaja ? aset.length : aset.reduce((s, a) => s + (a.nilai_idr || 0), 0)) || 1;
    const k = { up: 0, flat: 0, down: 0 }, n = { up: 0, flat: 0, down: 0 };
    aset.forEach((a) => { k[cls(a.skor)] += pantauSaja ? 1 : a.nilai_idr || 0; n[cls(a.skor)] += 1; });
    const perlu = aset.filter(pentingBaru);
    const nBaru = R.tanda_baru ?? perlu.length;
    const dasar = R.tanggal_dasar ? ` ${t("dibanding")} ${esc(tglPendek(R.tanggal_dasar))}` : "";
    const berjalan = (R.berjalan || []).map((m) => PASAR_NAMA[m] || m);
    const tt = R.skor_tertimbang ?? 0;
    const warna = { up: "var(--bull)", flat: "var(--neutral)", down: "var(--bear)" };
    const nama = { up: "bullish", flat: t("netral"), down: "bearish" };
    const kelasAda = Object.keys(KELAS).filter((kk) => aset.some((a) => a.pasar === kk));
    const satuan = pantauSaja ? t("ticker") : t("nilai");
    const distLabel = ["up", "flat", "down"].map((c) => `${n[c]} ${nama[c]} (${pct(k[c] / total * 100, false)} ${satuan})`).join(", ");

    el.innerHTML = `
      <div class="porto-head">
        <div><h1>${t(pantauSaja ? "Daftar pantau" : "Portofolio")}</h1>
          <div class="meta">${aset.length} ${t(pantauSaja ? "ticker" : "posisi")} · ${t("dipindai")} ${esc(waktu(data.waktu))}${pantauSaja ? "" : ` · ${t("posisi dari")} ${esc(R.sumber_posisi || "folder portofolio")}`}${R.jumlah_cache ? ` · <span class="flat">${t("{n} aset memakai harga cache", { n: R.jumlah_cache })}</span>` : ""}</div>
          ${berjalan.length ? `<div class="meta">${icon("info", "faint sm")} ${esc(t("Candle hari ini belum selesai untuk {pasar} — volume diproyeksikan, pola candle hari ini belum dihitung.", { pasar: berjalan.join(" & ") }))}</div>` : ""}</div>
        <div class="act">${mode === "panel" ? `<span class="muted" id="pindaiInfo" role="status"></span><button type="button" class="btn" id="btnPindai">${icon("refresh")}${t("Pindai ulang")}</button>` : ""}</div>
      </div>
      <div class="summary">
        ${pantauSaja ? `<div><div class="big ${cls(rataSkor)}">${skorTxt(rataSkor)}</div><div class="cap">${t("skor rata-rata")}</div></div>
        <div><div class="big">${aset.length}</div><div class="cap">${t("ticker dipantau")}</div></div>` : `<div><div class="big ${cls(tt)}">${skorTxt(tt)}</div><div class="cap">${t("skor rata-rata, ditimbang nilai")}</div></div>
        <div><div class="big">${rp(R.total_nilai)}</div><div class="cap">${esc(t("nilai saham, ETF & kripto"))}</div></div>`}
        <div class="dist">
          <div class="barline" role="img" aria-label="${t("Sebaran")}: ${esc(distLabel)}">${["up", "flat", "down"].filter((c) => k[c] > 0).map((c) => `<span style="width:${(k[c] / total * 100).toFixed(2)}%;background:${warna[c]}"></span>`).join("")}</div>
          <div class="lg">${["up", "flat", "down"].map((c) => `<span><i class="sw" style="background:${warna[c]}"></i><b>${n[c]}</b>${nama[c]} · ${pct(k[c] / total * 100, false)} ${satuan}</span>`).join("")}<span>${icon("alert", "down sm")}<b>${nBaru}</b>${t("aset dengan tanda baru")}${dasar}</span></div>
          ${R.ada_rs || R.dekat_support ? `<div class="lg">${R.ada_rs ? `<span><b>${R.lebih_lemah}</b>${t("dari {n} posisi lebih lemah dari pasarnya (20 hari)", { n: R.ada_rs })}</span>` : ""}${R.dekat_support ? `<span><b>${R.dekat_support}</b>${t("posisi dekat support")}</span>` : ""}</div>` : ""}
        </div>
      </div>
      ${R.gagal && R.gagal.length ? `<p class="flat" style="font-size:13px">${t("Tanpa data harga:")} ${esc(R.gagal.join(", "))}</p>` : ""}
      ${hariIniHtml(aset, pantauSaja)}
      <h2>${t(pantauSaja ? "Semua ticker" : "Semua posisi")} <span class="muted">${t(mode === "panel" ? "klik baris untuk membuka chart interaktif" : "klik baris untuk chart dan detail")}</span></h2>
      <div class="filters" role="group" aria-label="${t("Saring posisi")}">
        <button type="button" class="chip sans" data-kelas="all" aria-pressed="true">${t("Semua")} ${aset.length}</button>
        ${kelasAda.map((kk) => `<button type="button" class="chip sans" data-kelas="${kk}" aria-pressed="false">${KELAS[kk]} ${aset.filter((a) => a.pasar === kk).length}</button>`).join("")}
        <label><input type="checkbox" id="fPerlu"> ${t("Hanya yang ada tanda baru")} (${perlu.length})</label>
      </div>
      <div class="tblwrap"><table class="tbl" id="tblPorto">
        <thead><tr>${kolom.map(([kk, lbl, c]) => kk ? `<th class="${c}"${kk === sortKey ? ` aria-sort="descending"` : ""}><button type="button" class="sort" data-k="${kk}">${lbl}${icon("sort", "ar")}</button></th>` : `<th class="${c}"><span>${lbl}</span></th>`).join("")}<th><span class="sr-only">${t("Buka")}</span></th></tr></thead>
        <tbody></tbody></table></div>
      <details class="bacakolom"><summary>${t("Cara membaca kolom")}</summary><dl>
        ${pantauSaja ? "" : `<dt>P/L</dt><dd>${t("Untung/rugi dari harga rata-rata (avg, di bawahnya).")}</dd>`}
        <dt>${t("Skor")}</dt><dd>${t("−100 (sangat bearish) sampai +100 (sangat bullish). Angka kecil di bawahnya = perubahan sejak pindai hari bursa sebelumnya.")}</dd>
        <dt>1W</dt><dd>${t("Skor di timeframe mingguan: gambaran tren yang lebih besar.")}</dd>
        <dt>${t("30 hari")}</dt><dd>${t("Garis skor 30 hari terakhir: membaik atau memburuk.")}</dd>
        <dt>${t("vs pasar")}</dt><dd>${t("Kenaikan/penurunan 20 hari dibanding IHSG / S&P 500 / BTC. Positif = lebih kuat dari pasarnya.")}</dd>
        <dt>S1 · R1</dt><dd>${t("Support (lantai) dan resistance (atap) terdekat, dengan jaraknya dari harga. Label dekat = dalam 0,6 ATR.")}</dd>
        <dt>${t("Sinyal & langkah")}</dt><dd>${t("Tanda terpenting (Baru = belum ada di pindai sebelumnya) dan rencana tindakan singkat (→).")}</dd>
      </dl></details>
      ${ujiSkorHtml(data.uji_skor)}
      ${pantauSaja ? "" : `<h2>${t("Skor per sektor")} <span class="muted">${t("ditimbang nilai posisi")}</span></h2>
      <div class="tblwrap"><table class="tbl" id="tblSektor"><thead><tr><th><span>${t("Sektor")}</span></th><th class="r"><span>${t("Posisi")}</span></th><th class="r"><span>${t("Nilai")}</span></th><th class="r"><span>${t("Porsi")}</span></th><th style="width:34%"><span>bearish · bullish</span></th><th class="r"><span>${t("Skor")}</span></th></tr></thead><tbody>${sektorRows(aset, total)}</tbody></table></div>`}
      ${!pantauSaja && (data.pantauan || []).length ? `<h2>${t("Pantauan")} <span class="muted">${t("belum dipegang")}</span></h2><div class="tblwrap"><table class="tbl" id="tblPantau"><tbody>${data.pantauan.map((a) => `<tr class="row" data-t="${esc(a.ticker)}" tabindex="0"><td><span class="sym">${esc(a.simbol)}</span><span class="sek">${esc(a.sektor)}</span></td><td class="r num">${esc(fp(a.harga, a.pasar))}</td><td class="r"><span class="badge ${cls(a.skor)}">${skorTxt(a.skor)}</span></td><td>${esc(a.label)}</td><td class="chev">${icon("chev")}</td></tr>`).join("")}</tbody></table></div>` : ""}
      <p class="disclaimer" style="padding-left:0">${pantauSaja ? t("Skor −100…+100 dari tren, momentum, volume, pola, trendline, dan support/resistance (harian; mingguan untuk konfluensi). Bukan rekomendasi investasi.") : t("Skor −100…+100 dari tren MA dan struktur swing, momentum, divergence, volume, breakout, pola chart dan candle, trendline, serta posisi terhadap support/resistance (harian; mingguan untuk konfluensi). Nilai dan P/L untuk konteks saja — angka resmi tetap dari tracker. Bukan rekomendasi investasi.")}</p>`;

    const tbody = el.querySelector("#tblPorto tbody");
    function nilaiSort(a, key) {
      if (key === "perhatian") return perhatian(a) * 1000 - a.skor;
      if (key === "s1") return a.support && a.support[0] ? (a.harga - a.support[0]) / a.harga : 9;
      if (key === "w1") { const w = skorTf(a, "1wk"); return w == null ? -1e9 : w; }
      if (key === "rs") return a.rs && a.rs.rs20 != null ? a.rs.rs20 : -1e9;
      const v = a[key];
      return typeof v === "string" ? v : v ?? -1e18;
    }
    function draw() {
      const rows = aset
        .filter((a) => (filter.kelas === "all" || a.pasar === filter.kelas) && (!filter.hanyaPerlu || pentingBaru(a)))
        .sort((a, b) => { const x = nilaiSort(a, sortKey), y = nilaiSort(b, sortKey); return (x > y ? 1 : x < y ? -1 : 0) * sortDir; });
      ingat();
      tbody.innerHTML = rows.length ? rows.map(barisAset).join("") : `<tr class="empty-row"><td colspan="${nKol}">${t("Tidak ada posisi untuk saringan ini.")}</td></tr>`;
    }
    function barisAset(a) {
      const mk = a.pasar, fl = urutTanda(a.bendera);
      const top = fl[0], d = a.delta_skor, w = skorTf(a, "1wk");
      return `<tr class="row" data-t="${esc(a.ticker)}" tabindex="0">
        <td><span class="sym">${esc(a.simbol)}</span><span class="sek">${esc(a.sektor)}</span></td>
        <td class="r num">${esc(fp(a.harga, mk))}${a.berjalan != null ? `<span class="live-dot" title="${t("Candle hari ini masih berjalan")}"></span><span class="sr-only"> ${t("(candle berjalan)")}</span>` : ""}</td>
        ${pantauSaja ? "" : `<td class="r"><span class="num ${(a.pl_pct || 0) >= 0 ? "up" : "down"}">${pct(a.pl_pct)}</span><span class="delta faint" title="${t("Harga rata-rata")}">avg ${esc(fp(a.avg, mk))}</span></td>
        <td class="r num muted">${pct(a.bobot, false)}</td>`}
        <td class="r"><span class="badge ${cls(a.skor)}">${skorTxt(a.skor)}</span>${d ? `<span class="delta ${d > 0 ? "up" : "down"}" title="${R.tanggal_dasar ? t("Berubah {d} dibanding pindai {tgl}", { d: skorTxt(d), tgl: esc(tglPendek(R.tanggal_dasar)) }) : t("Berubah {d} sejak pindai sebelumnya", { d: skorTxt(d) })}">${skorTxt(d)}</span>` : ""}</td>
        <td class="r num ${w == null ? "faint" : "muted"}">${w == null ? "—" : skorTxt(w)}</td>
        <td class="r">${sparkline(titikRiwayat(a))}</td>
        <td class="r">${rsHtml(a.rs, true)}</td>
        <td class="r num sr2">${(() => { const dk = a.dekat || {}; const baris = (k, x, lv) => `<span class="faint">${k}</span>${esc(x ? fp(x.harga, mk) : "—")}${x ? ` <span class="jarak">${pct(x.jarak_pct)}</span>` : ""}${dekatTag(lv)}`; return a.dekat ? baris("S", dk.s1, dk.s1) + "<br>" + baris("R", dk.r1, dk.r1) : `<span class="faint">S</span>${esc(a.support && a.support[0] ? fp(a.support[0], mk) : "—")}<br><span class="faint">R</span>${esc(a.resistance && a.resistance[0] ? fp(a.resistance[0], mk) : "—")}`; })()}</td>
        <td>${top ? `<div class="sig${baru(top) ? "" : " lama"}">${sevIcon(top.level)}<span class="t" title="${esc(top.teks + (top.baru === false && top.sejak ? " · " + t("sejak") + " " + tglPendek(top.sejak) : ""))}">${tagTanda(top)}${esc(top.teks)}</span>${fl.length > 1 ? `<span class="lagi" title="${esc(fl.slice(1).map((f) => f.teks).join("\n"))}">+${fl.length - 1}</span>` : ""}</div>` : `<div class="sig lama"><span class="t faint">${t("Tidak ada tanda")}</span></div>`}${a.rencana_aksi && a.rencana_aksi.judul ? `<span class="langkah1" title="${esc(a.rencana_aksi.judul)}">→ ${esc(ringkasAksi(a.rencana_aksi))}</span>` : ""}</td>
        <td class="chev">${icon("chev")}</td></tr>`;
    }
    function rencanaHtml(p, mk) {
      if (p.bias === "long") return `<dt>${t("Area beli")}</dt><dd>${esc(fp(p.entry_zone[0], mk))} – ${esc(fp(p.entry_zone[1], mk))}</dd><dt title="${t("Rencana beli batal bila close di bawah level ini")}">${t("Stop (close di bawah)")}</dt><dd class="down">${esc(fp(p.stop_loss, mk))}</dd>` + p.targets.map((x, i) => `<dt>Target ${i + 1}</dt><dd class="up">${esc(fp(x, mk))} <span class="faint">R:R ${num(p.rr[i], 1)}</span></dd>`).join("");
      if (p.bias === "short") return p.targets.map((x, i) => `<dt>${t("Target turun")} ${i + 1}</dt><dd>${esc(fp(x, mk))}</dd>`).join("") + `<dt title="${t("Tren turun dianggap selesai bila close di atas level ini")}">${t("Konfirmasi naik (close di atas)")}</dt><dd>${esc(fp(p.stop_loss, mk))}</dd>`;
      if (p.range) return `<dt>Range</dt><dd>${esc(fp(p.range[0], mk))} – ${esc(fp(p.range[1], mk))}</dd><dt>${t("Menguat bila close di atas")}</dt><dd class="up">${esc(fp(p.buy_trigger, mk))}</dd><dt>${t("Melemah bila close di bawah")}</dt><dd class="down">${esc(fp(p.sell_trigger, mk))}</dd>`;
      return "";
    }
    function titikRiwayat(a) {
      const t = a.riwayat || [];
      return t.length && t[t.length - 1][1] === a.skor ? t : t.concat([[0, a.skor]]);
    }
    function riwayatHtml(a) {
      const t = titikRiwayat(a);
      if (t.length < 3) return "";
      return `<div class="riw"><div class="riw-head"><span>${B.t("Skor {n} hari terakhir", { n: (a.riwayat || []).length || t.length })}</span><span class="num">${skorTxt(t[0][1])} → ${skorTxt(a.skor)}</span></div>${sparkline(t, { w: 320, h: 44 })}</div>`;
    }
    function detailStatis(a) {
      const mk = a.pasar, p = a.rencana || {}, ind = a.indikator || {};
      const fl = urutTanda(a.bendera).map((f) => `<li class="${baru(f) ? "" : "lama"}">${sevIcon(f.level)}<span>${tagTanda(f)}${ist(f.teks)}${sejakTanda(f)}</span><span></span></li>`).join("");
      const sig = sinyalHtml(a.sinyal, a.skor);
      return `<tr class="det"><td colspan="${nKol}"><div class="detail">
        <div>${a.chart ? `<a class="chartlink" href="chart/${esc(namaFile(a.ticker))}.png" target="_blank" rel="noopener" title="${t("Buka gambar ukuran penuh")}"><img loading="lazy" src="chart/${esc(namaFile(a.ticker))}.png" alt="${esc(t("Chart {simbol} harian dengan MA, support/resistance, pola, RSI, MACD dan catatan analisa", { simbol: a.simbol }))}"></a><p class="faint chartcap">${t("Klik gambar untuk ukuran penuh. Catatan analisa tertulis di sisi kanan gambar, jadi tetap terbaca bila gambarnya dibagikan.")}</p>` : `<p class="faint">${t("Chart tidak dibuat (mode --tanpa-chart).")}</p>`}</div>
        <div>
          <div class="verdict"><div class="score ${cls(a.skor)}" style="font-size:34px">${skorTxt(a.skor)}</div><div><div class="label ${cls(a.skor)}">${esc(a.label)}</div><div class="trend">${ist(a.tren)}</div></div></div>
          ${a.konfluensi ? `<p class="konf">${esc(a.konfluensi)}</p>` : ""}
          ${rsHtml(a.rs)}
          ${riwayatHtml(a)}
          ${a.narasi ? `<h3>${B.en ? t("Analisa tertulis") : "Analisa"}</h3><div class="narasi">${narasiHtml(a.narasi)}</div>` : ""}
          ${fl ? `<h3>${t("Perlu diperhatikan")}</h3><ul class="items">${fl}</ul>` : ""}
          ${a.rencana_aksi && a.rencana_aksi.langkah ? `<h3>${t("Rencana tindakan")} ${sikapPill(a.rencana_aksi)}</h3><div class="aksi">${aksiHtml(a.rencana_aksi)}</div>` : ""}
          <h3>${t("Rencana")}</h3><dl class="kv">${rencanaHtml(p, mk)}</dl><p class="note">${ist(p.note || "")}</p>
          <h3>${t("Sinyal")} <span class="muted">${t("poin skor")}</span></h3>${sig}
          <p class="note">RSI ${num(ind.rsi14, 0)} · ADX ${num(ind.adx14, 0)} · MA200 ${esc(fp(ind.sma200, mk))} · ${t("harga per")} ${esc(a.tanggal_harga)} (${esc(a.sumber || "")})</p>
        </div></div></td></tr>`;
    }

    el.querySelectorAll(".filters .chip").forEach((b) => b.addEventListener("click", () => {
      filter.kelas = b.dataset.kelas;
      el.querySelectorAll(".filters .chip").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      draw();
    }));
    el.querySelector("#fPerlu").addEventListener("change", (e) => { filter.hanyaPerlu = e.target.checked; draw(); });
    el.querySelectorAll("#tblPorto .sort").forEach((btn) => btn.addEventListener("click", () => {
      const key = btn.dataset.k;
      sortDir = sortKey === key ? -sortDir : (key === "simbol" ? 1 : -1);
      sortKey = key;
      el.querySelectorAll("#tblPorto th").forEach((x) => x.removeAttribute("aria-sort"));
      btn.parentElement.setAttribute("aria-sort", sortDir > 0 ? "ascending" : "descending");
      draw();
    }));
    function buka(tr) {
      const t = tr.dataset.t;
      if (!t) return;
      if (mode === "panel" && opts.onOpen) return opts.onOpen(t);
      const next = tr.nextElementSibling;
      tr.setAttribute("aria-expanded", "true");
      if (next && next.classList.contains("det")) { next.remove(); tr.setAttribute("aria-expanded", "false"); return; }
      const a = aset.find((x) => x.ticker === t) || (data.pantauan || []).find((x) => x.ticker === t);
      if (a) tr.insertAdjacentHTML("afterend", detailStatis(a));
    }
    el.addEventListener("click", (e) => {
      const hi = e.target.closest("[data-hari]");
      if (hi) {
        if (mode === "panel" && opts.onOpen) return opts.onOpen(hi.dataset.hari);
        const tr = el.querySelector(`#tblPorto tr.row[data-t="${CSS.escape(hi.dataset.hari)}"]`);
        if (tr) { if (tr.getAttribute("aria-expanded") !== "true") buka(tr); tr.scrollIntoView({ block: "start", behavior: "smooth" }); tr.focus({ preventScroll: true }); }
        return;
      }
      const tr = e.target.closest("tr.row"); if (tr) buka(tr);
    });
    el.addEventListener("keydown", (e) => {
      if (e.key !== "Enter" && e.key !== " ") return;
      const tr = e.target.closest("tr.row");
      if (tr && e.target === tr) { e.preventDefault(); buka(tr); }
    });
    // pulihkan tampilan tombol saringan/urutan dari keadaan sebelumnya
    el.querySelectorAll(".filters .chip").forEach((x) => x.setAttribute("aria-pressed", String(x.dataset.kelas === filter.kelas)));
    el.querySelector("#fPerlu").checked = !!filter.hanyaPerlu;
    el.querySelectorAll("#tblPorto th").forEach((x) => x.removeAttribute("aria-sort"));
    const thAktif = el.querySelector(`#tblPorto .sort[data-k="${sortKey}"]`);
    if (thAktif) thAktif.parentElement.setAttribute("aria-sort", sortDir > 0 ? "ascending" : "descending");
    draw();
    return el;
  }

  // Blok "Hari ini": hal yang perlu dilihat sekarang, supaya tabel 40+ baris tidak perlu dibaca satu per satu.
  // 1) tanda merah/oranye yang baru  2) harga ≤ 1 ATR dari level keputusan (atau di area beli). Sisanya: cukup pantau.
  function hariIniHtml(aset, pantauSaja = false) {
    if (!aset.length) return "";
    const item = [];
    aset.forEach((a) => {
      const ra = a.rencana_aksi || {};
      const tb = urutTanda(a.bendera).find((f) => baru(f) && (f.level === "merah" || f.level === "oranye"));
      if (tb) item.push({ a, ra, jenis: "baru", nilai: 3 + (tb.level === "merah" ? 1 : 0), teks: tb.teks, level: tb.level });
      else if (ra.dekat && ra.pantau && ra.sikap === "beli") item.push({ a, ra, jenis: ra.rr_rendah ? "beli_rr" : "beli", nilai: ra.rr_rendah ? 1.8 : 2.5, teks: ra.pantau.teks });
      else if (ra.dekat && ra.pantau) item.push({ a, ra, jenis: "dekat", nilai: 1 + (ra.pantau.arah === "turun" ? 0.5 : 0), teks: ra.pantau.teks });
    });
    // Urutan: tanda baru, lalu yang bisa ditindak (area beli), lalu yang dekat level; di dalamnya bobot terbesar dulu.
    item.sort((x, y) => y.nilai - x.nilai || (y.a.bobot || 0) - (x.a.bobot || 0));
    const MAKS = 8, MAKS_DEKAT = 3;
    const utama = item.filter((x) => x.jenis !== "dekat"), dekat = item.filter((x) => x.jenis === "dekat");
    const tampil = utama.slice(0, MAKS).concat(dekat.slice(0, Math.max(0, Math.min(MAKS_DEKAT, MAKS - utama.length))));
    const ringkas = dekat.slice(Math.max(0, Math.min(MAKS_DEKAT, MAKS - utama.length)));  // sisanya satu baris ringkas, tidak diulang kalimatnya
    const lebih = Math.max(0, utama.length - MAKS);
    const sisa = aset.length - item.length;
    const CHIP = { baru: ["down", t("Tanda baru")], dekat: ["flat", t("Dekat level")], beli: ["up", t("Area beli")], beli_rr: ["flat", t("Area beli · R:R rendah")] };
    const baris = tampil.map(({ a, ra, jenis, teks, level }) => {
      const [c, lbl] = CHIP[jenis];
      return `<li><button type="button" class="hari" data-hari="${esc(a.ticker)}">
        <span class="sym">${esc(a.simbol)}</span><span class="hchip ${c}">${jenis === "baru" ? sevIcon(level) : ""}${lbl}</span>
        <span class="hteks"><span>${esc(teks)}</span>${ringkasAksi(ra) ? `<span class="hlangkah">→ ${esc(ringkasAksi(ra))}</span>` : ""}</span>
        ${pantauSaja ? "" : `<span class="hbobot num faint" title="${t("Bobot di portofolio")}">${pct(a.bobot, false)}<small>${t("bobot")}</small></span>`}${icon("chev", "faint")}</button></li>`;
    }).join("");
    const mini = ringkas.map(({ a, ra }) => `<button type="button" class="hmini" data-hari="${esc(a.ticker)}"><b>${esc(a.simbol)}</b> ${esc(ra.pantau.nama)} ${esc(fp(ra.pantau.harga, a.pasar))} <span class="jarak num">${pct(Math.abs(ra.pantau.jarak_pct), false)}</span></button>`).join("");
    return `<section class="hariini" aria-labelledby="hHari"><h2 id="hHari">${t("Hari ini")} <span class="muted">${t("yang perlu dilihat dulu · klik untuk membuka")}</span></h2>
      ${tampil.length ? `<ul>${baris}</ul>` : `<p class="muted">${t("Tidak ada tanda baru dan tidak ada harga yang dekat level keputusan.")}</p>`}
      ${mini ? `<p class="hminis"><span class="muted">${t("Juga dekat level keputusan:")}</span>${mini}</p>` : ""}
      <p class="hsisa">${lebih > 0 ? esc(t("+{n} lainnya: lihat tabel di bawah (saringan Hanya yang ada tanda baru, kolom S1 · R1).", { n: lebih })) + " " : ""}${sisa > 0 ? esc(t(pantauSaja ? "{n} ticker lain: tidak ada tanda baru dan harganya masih jauh dari level keputusan — cukup pantau, tidak perlu aksi hari ini." : "{n} posisi lain: tidak ada tanda baru dan harganya masih jauh dari level keputusan — cukup pantau, tidak perlu aksi hari ini.", { n: sisa })) : ""}</p></section>`;
  }

  // "Seberapa andal skor ini?" — hasil uji_skor.py: return 20 hari sesudah tiap kelompok skor, per pasar.
  function ujiSkorHtml(U) {
    if (!U || !U.pasar) return "";
    const NAMA = { idx: t("Saham IDX"), us: t("Saham/ETF AS"), crypto: t("Kripto") };
    const kel = ((U.pasar.idx || U.pasar.semua || {}).h20 || {}).kelompok || [];
    const kepala = kel.map((k) => `<th class="r num">${esc(k.kelompok)}</th>`).join("");
    const vonis = (b) => {
      const d = b.h20, sb = d.sebaran;
      if (sb == null) return [t("Sampel terlalu sedikit."), "flat"];
      if (sb >= 1.5) return [t("Searah: skor tinggi diikuti hasil lebih baik daripada skor rendah ({x} poin dalam 20 hari). Skor berguna sebagai penyaring tren.", { x: num(sb, 1) }), "up"];
      if (sb <= -1.5) return [t("Berlawanan: skor rendah justru sering diikuti pantulan ({x} poin). Di pasar ini skor bearish lebih cocok dibaca sebagai jenuh jual, bukan alasan menjual.", { x: num(sb, 1) }), "down"];
      return [t("Lemah: hampir tidak ada beda hasil antara skor tinggi dan rendah. Jangan mengandalkan skor saja."), "flat"];
    };
    const baris = ["idx", "us", "crypto"].filter((k) => U.pasar[k]).map((k) => {
      const b = U.pasar[k], [v, c] = vonis(b);
      const sel = b.h20.kelompok.map((x) => x.n ? `<td class="r num ${x.n < 30 ? "faint" : x.rata > 0.05 ? "up" : x.rata < -0.05 ? "down" : "flat"}" title="${t("{n} hari · naik {p}% dari waktu", { n: x.n, p: num(x.naik_pct, 0) })}">${pct(x.rata)}</td>` : `<td class="r faint">—</td>`).join("");
      return `<tr><th scope="row">${NAMA[k]}<span class="muted"> · ${t("{n} aset", { n: b.aset })}</span></th>${sel}<td class="r num faint">${pct(b.h20.dasar.rata)}</td></tr>
        <tr class="vonis-uji"><td colspan="${kel.length + 2}"><span class="${c}">${c === "up" ? icon("trend-up", "sm") : c === "down" ? icon("trend-down", "sm") : icon("flat", "sm")}</span> ${esc(v)}</td></tr>`;
    }).join("");
    return `<section class="ujiskor"><h2>${t("Seberapa andal skor ini?")} <span class="muted">${t("uji pada data lama · {dari} – {sampai}", { dari: esc(U.dari || ""), sampai: esc(U.sampai || "") })}</span></h2>
      <p class="muted">${t("Rata-rata perubahan harga 20 hari bursa sesudah skor berada di kelompok tertentu. Skor dihitung hanya dari data sampai hari itu.")}</p>
      <div class="tbl-wrap"><table class="uji"><thead><tr><th>${t("Pasar")}</th>${kepala}<th class="r">${t("semua hari")}</th></tr></thead><tbody>${baris}</tbody></table></div>
      ${ujiKategoriHtml(U, NAMA)}${ujiRencanaHtml(U, NAMA)}
      <p class="hsisa">${t("Sampel hanya aset yang pernah dipindai, hari-harinya tumpang tindih, dan tanpa biaya transaksi: gambaran kasar, bukan bukti. Hitung ulang: python3 uji_skor.py")}</p></section>`;
  }

  // Uji per kategori sinyal: return 20 hari saat kategori itu bullish dikurangi saat bearish, per pasar.
  function ujiKategoriHtml(U, NAMA) {
    const pasar = ["idx", "us", "crypto"].filter((k) => U.pasar[k] && U.pasar[k].kategori);
    if (!pasar.length) return "";
    const nama = U.pasar[pasar[0]].kategori.map((x) => x.kategori);
    const sel = (x) => (x && x.beda != null
      ? `<td class="r num ${x.beda >= 1 ? "up" : x.beda <= -1 ? "down" : "flat"}" title="${t("bullish {a} hari · bearish {b} hari", { a: x.n_bull, b: x.n_bear })}">${num(x.beda, 1, true)}</td>`
      : `<td class="r faint" title="${t("Sampel terlalu sedikit.")}">—</td>`);
    const baris = nama.map((n, i) => `<tr><th scope="row">${esc(n)}</th>${pasar.map((k) => sel(U.pasar[k].kategori[i])).join("")}</tr>`).join("");
    return `<h3 class="uji-h">${t("Sinyal mana yang berguna?")}</h3>
      <p class="muted">${t("Perubahan harga 20 hari saat kategori sinyal itu bullish dikurangi saat bearish (poin persen). Positif (hijau) = searah dengan hasil; sekitar nol atau merah = di pasar itu kategori ini tidak membantu.")}</p>
      <div class="tbl-wrap"><table class="uji sempit"><thead><tr><th>${t("Kategori sinyal")}</th>${pasar.map((k) => `<th class="r">${NAMA[k]}</th>`).join("")}</tr></thead><tbody>${baris}</tbody></table></div>`;
  }
  // Uji rencana: mana yang lebih dulu terjadi sesudah rencana muncul.
  function ujiRencanaHtml(U, NAMA) {
    const pasar = ["idx", "us", "crypto"].filter((k) => U.pasar[k] && U.pasar[k].rencana);
    if (!pasar.length) return "";
    const p0 = (x, k) => (x && x.n >= 30 ? num(x[k], 0) + "%" : "—");
    const baris = pasar.map((k) => {
      const r = U.pasar[k].rencana, b = r.beli || {}, h = r.hindari || {};
      return `<tr><th scope="row">${NAMA[k]}</th>
        <td class="r num up" title="${t("{n} hari", { n: b.n || 0 })}">${p0(b, "target")}</td><td class="r num down">${p0(b, "stop")}</td><td class="r num faint">${p0(b, "belum")}</td>
        <td class="r num down gar" title="${t("{n} hari", { n: h.n || 0 })}">${p0(h, "turun")}</td><td class="r num up">${p0(h, "naik")}</td><td class="r num faint">${p0(h, "belum")}</td></tr>`;
    }).join("");
    return `<h3 class="uji-h">${t("Seberapa sering rencananya terjadi?")}</h3>
      <p class="muted">${t("Dari semua hari ketika rencana itu muncul: mana yang lebih dulu terjadi dalam {n} bar sesudahnya.", { n: U.horison_rencana || 40 })}</p>
      <div class="tbl-wrap"><table class="uji"><thead>
        <tr><th rowspan="2">${t("Pasar")}</th><th colspan="3" class="grp">${t("Di area beli")}</th><th colspan="3" class="grp gar">${t("Belum saatnya beli")}</th></tr>
        <tr><th class="r">${t("target 1 dulu")}</th><th class="r">${t("stop dulu")}</th><th class="r">${t("belum keduanya")}</th><th class="r gar">${t("turun ke target turun 1")}</th><th class="r">${t("konfirmasi naik dulu")}</th><th class="r">${t("belum keduanya")}</th></tr>
      </thead><tbody>${baris}</tbody></table></div>`;
  }

  function sektorRows(aset, total) {
    const g = {};
    aset.forEach((a) => { (g[a.sektor] = g[a.sektor] || []).push(a); });
    return Object.entries(g).map(([nama, xs]) => {
      const v = xs.reduce((s, a) => s + (a.nilai_idr || 0), 0);
      const s = v ? xs.reduce((t, a) => t + (a.nilai_idr || 0) * a.skor, 0) / v : xs.reduce((t, a) => t + a.skor, 0) / xs.length;
      return { nama, n: xs.length, v, s };
    }).sort((a, b) => b.v - a.v).map((r) => {
      const w = Math.abs(r.s) / 2, left = r.s >= 0 ? 50 : 50 - w;
      return `<tr><td>${esc(r.nama)}</td><td class="r num">${r.n}</td><td class="r num">${rp(r.v)}</td><td class="r num muted">${pct(r.v / total * 100, false)}</td>
        <td><div class="sekbar" role="img" aria-label="${t("Skor")} ${skorTxt(r.s)}"><span style="left:${left}%;width:${w}%;background:var(--${r.s >= 20 ? "bull" : r.s <= -20 ? "bear" : "neutral"})"></span></div></td>
        <td class="r"><span class="badge ${cls(r.s)}">${skorTxt(r.s)}</span></td></tr>`;
    }).join("");
  }

  root.AT = { esc, fp, num, pct, skorTxt, rp, cls, icon, sevIcon, biasIcon, renderPortofolio, KELAS, MINUS, urutTanda, tagTanda, sejakTanda, baru, tglPendek, sparkline, rsHtml, narasiHtml, dekatTag, aksiHtml, sikapPill, ist, sinyalHtml, poinSkor, ringkasAksi };
})(typeof window !== "undefined" ? window : globalThis);
