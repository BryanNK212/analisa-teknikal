/* Analisa Teknikal — panel lokal (Cek aset + Portofolio), juga dipakai di side panel ekstensi (?embed=1). */
(function () {
  "use strict";
  const { beliHtml } = window.AT;
  const { esc, fp, num, pct, skorTxt, cls, icon, sevIcon, biasIcon, KELAS, urutTanda, tagTanda, sejakTanda, baru, sparkline, rsHtml, narasiHtml, dekatTag, aksiHtml, sikapPill, ist, sinyalHtml, poinSkor } = window.AT;
  const $ = (s) => document.querySelector(s);
  const ATB = window.ATB, t = ATB.t;  // bahasa tampilan (web/bahasa.js)
  const LC = window.LightweightCharts;
  const params = new URLSearchParams(location.search);
  const EMBED = params.get("embed") === "1";
  // Mode analisa saja: panel samping ekstensi (?embed=1) atau tab cadangan dari ekstensi (?mandiri=1).
  // Di mode ini tab Portofolio tidak ada dan tidak ada permintaan data portofolio sama sekali.
  const MANDIRI = EMBED || params.get("mandiri") === "1";
  if (EMBED) document.body.classList.add("embed");
  if (MANDIRI) document.body.classList.add("mandiri");
  const simpan = { get(k) { try { return localStorage.getItem(k); } catch { return null; } }, set(k, v) { try { localStorage.setItem(k, v); } catch {} } };

  // Warna chart = token di panel.css
  const C = { bull: "#26a69a", bear: "#ef5350", accent: "#6ea8fe", text: "#f2f2f3", text3: "#8e8e96", ground: "#0b0b0c", grid: "#151517", line: "#232327", line2: "#34343a", ma20: "#e0a64b", ma50: "#6ea8fe", ma200: "#b48ef0" };
  const CONTOH = ["BBCA", "NVDA", "BTC", "IHSG", "EURUSD"];
  const WIB = 7 * 3600;  // semua waktu chart ditampilkan dalam WIB

  const state = { q: "", tf: "1d", pasar: "auto", data: null, minta: 0, view: "cek" };
  const overlays = { ma: true, bb: false, sr: true, rencana: true, tl: true, pat: true, vol: true };
  try { Object.assign(overlays, JSON.parse(simpan.get("at.overlays") || "{}")); } catch {}
  const fontSiap = document.fonts && document.fonts.load
    ? Promise.all([document.fonts.load('11px "Fira Code"'), document.fonts.load('14px "Fira Sans"')]).catch(() => {})
    : Promise.resolve();

  // ---------- status, pengumuman, toast ----------
  function setStatus(kind, teks) { $("#statusDot").className = "dot " + (kind || ""); $("#statusText").textContent = teks; $("#status").title = teks; }
  function umumkan(teks) { const s = $("#sr"); s.textContent = ""; setTimeout(() => { s.textContent = teks; }, 40); }
  let toastT;
  function toast(m, ms = 4500) { const el = $("#toast"); el.textContent = m; el.hidden = false; clearTimeout(toastT); toastT = setTimeout(() => (el.hidden = true), ms); }

  // ---------- alamat (#q=..&tf=.. / #portofolio) & tombol Back ----------
  const labelTf = (tf) => ({ "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1h", "4h": "4h", "1d": "1D", "1wk": "1W", "1mo": "1M" }[tf] || tf);
  function urlUntuk(view) { return view === "porto" ? "#portofolio" : view === "ihsg" ? "#ihsg" : view === "gab" ? "#gabungan" : state.q ? `#q=${encodeURIComponent(state.q)}&tf=${state.tf}` : location.pathname + location.search; }
  function catat(view, cara) {
    if (EMBED || !cara) return;
    const u = urlUntuk(view);
    if (u === location.hash || (u.startsWith("/") && !location.hash)) return;
    if (cara === "push") history.pushState(null, "", u); else history.replaceState(null, "", u);
  }

  // ---------- navigasi ----------
  // Saham dari Pemindai IHSG / Gabungan selalu saham IDX: pilihan pasar di Cek aset dikembalikan ke otomatis.
  function pasarOtomatis() { state.pasar = "auto"; const p = $("#pasar"); if (p) p.value = "auto"; }
  function tampil(view, { riwayat = "replace" } = {}) {
    if (MANDIRI) view = "cek";
    state.view = view;
    const cek = view === "cek", porto = view === "porto", ihsg = view === "ihsg", gab = view === "gab";
    [["#tabCek", cek], ["#tabPorto", porto], ["#tabIhsg", ihsg], ["#tabGab", gab]].forEach(([s, on]) => (on ? $(s).setAttribute("aria-current", "page") : $(s).removeAttribute("aria-current")));
    $("#viewCek").hidden = !cek; $("#work").hidden = !cek; $("#viewPorto").hidden = !porto; $("#viewIhsg").hidden = !ihsg; $("#viewGab").hidden = !gab;
    if (gab) $("#tabGab").hidden = false;  // dibuka langsung lewat #gabungan
    if (porto) muatPortofolio();
    // Tab Gabungan: teknikal + fundamental. Cek aset & Pemindai IHSG tetap murni teknikal.
    if (gab) window.ATGabungan.tampil($("#viewGab"), (kode) => { state.q = kode; $("#q").value = kode; pasarOtomatis(); setTf("1d"); tampil("cek", { riwayat: "push" }); analisa(); });
    if (ihsg) window.ATIhsg.tampil($("#viewIhsg"), (kode) => { state.q = kode; $("#q").value = kode; pasarOtomatis(); setTf("1d"); tampil("cek", { riwayat: "push" }); analisa(); });
    catat(view, riwayat);
  }
  document.querySelectorAll(".nav .tab").forEach((a) => a.addEventListener("click", (e) => { e.preventDefault(); tampil(a.dataset.view, { riwayat: "push" }); }));
  function bacaUrl() {
    if (location.hash === "#portofolio") return tampil("porto", { riwayat: null });
    if (location.hash === "#ihsg") return tampil("ihsg", { riwayat: null });
    if (location.hash === "#gabungan") return tampil("gab", { riwayat: null });
    tampil("cek", { riwayat: null });
    const h = new URLSearchParams(location.hash.slice(1));
    const q = h.get("q") || params.get("q");
    if (!q) return;
    const tf = h.get("tf") || params.get("tf") || "1d";
    if (q === state.q && tf === state.tf && state.data) return;
    state.q = q; $("#q").value = q; setTf(tf); analisa();
  }
  window.addEventListener("popstate", bacaUrl);
  window.addEventListener("hashchange", bacaUrl);  // alamat #portofolio diketik/di-bookmark langsung

  // ---------- timeframe & pencarian ----------
  function setTf(tf) {
    state.tf = tf;
    document.querySelectorAll("#tfSeg button").forEach((b) => b.setAttribute("aria-pressed", String(b.dataset.tf === tf)));
  }
  let tfDariSitus = true;  // false bila situs yang diikuti tidak memberi timeframe (Stockbit, Binance, dll.)
  document.querySelectorAll("#tfSeg button").forEach((b) => b.addEventListener("click", () => {
    setTf(b.dataset.tf);
    if (EMBED && tfDariSitus) $("#ikuti").checked = false;  // pilih timeframe sendiri = berhenti mengikuti chart
    if (state.q) analisa({ push: true });
  }));
  $("#pasar").addEventListener("change", (e) => { state.pasar = e.target.value; });
  function cari(q, { pasar } = {}) {
    if (!q) return;
    if (EMBED) $("#ikuti").checked = false;
    if (pasar) { state.pasar = pasar; $("#pasar").value = ["idx", "us", "crypto"].includes(pasar) ? pasar : "auto"; }
    if (state.view !== "cek") tampil("cek", { riwayat: null });
    state.q = q; $("#q").value = q; analisa({ push: true });
  }
  $("#formCari").addEventListener("submit", (e) => {
    e.preventDefault();
    const q = $("#q").value.trim();
    if (!q) return $("#q").focus();
    cari(q);
  });
  document.addEventListener("keydown", (e) => {
    if (e.key !== "/" || e.metaKey || e.ctrlKey || e.altKey) return;
    const el = e.target;
    if (el && (el.tagName === "INPUT" || el.tagName === "TEXTAREA" || el.tagName === "SELECT" || el.isContentEditable)) return;
    e.preventDefault();
    if (state.view !== "cek") tampil("cek", { riwayat: "push" });
    $("#q").focus(); $("#q").select();
  });
  // klik chip/tombol ber-data-q di mana pun (contoh, terakhir, posisi terbesar)
  document.addEventListener("click", (e) => {
    const b = e.target.closest("[data-q]");
    if (!b || b.closest("#viewPorto")) return;
    cari(b.dataset.q, { pasar: b.dataset.pasar });
  });

  function recent(q) {
    let r = []; try { r = JSON.parse(simpan.get("at.recent") || "[]"); } catch {}
    if (q) { r = [q, ...r.filter((x) => x !== q)].slice(0, 6); simpan.set("at.recent", JSON.stringify(r)); }
    $("#recent").innerHTML = r.length ? `<span class="lbl">${t("Terakhir")}</span>` + r.map((x) => `<button type="button" class="chip${x === (state.q || "").toUpperCase() ? " on" : ""}" data-q="${esc(x)}">${esc(x)}</button>`).join("") : "";
  }

  // ---------- ambil analisa ----------
  // Hasil terakhir tiap aset+timeframe diingat sebentar: saat kembali ke aset yang baru saja dilihat, hasilnya
  // langsung tampil lalu diperbarui di latar, jadi berpindah-pindah tidak terasa menunggu.
  const ingatan = new Map(), UMUR_INGATAN = 5 * 60 * 1000;
  const kunciIngatan = () => `${state.q.trim().toUpperCase()}|${state.tf}|${state.pasar}`;
  const polos = (q) => String(q || "").trim().toUpperCase().replace(/^[A-Z0-9_]+:/, "");
  async function analisa({ push = false } = {}) {
    const nomor = ++state.minta;
    const kunci = kunciIngatan(), lama = ingatan.get(kunci);
    $("#work").setAttribute("aria-busy", "true");
    setStatus("warn", t("Menarik {q}…", { q: state.q.toUpperCase() }));
    $("#btnAnalisa").disabled = true;
    if (lama && Date.now() - lama.t < UMUR_INGATAN && state.data !== lama.d) {
      state.data = lama.d; render(lama.d);
    } else if (!state.data) {
      showState("loading"); $("#secStart").hidden = true; $("#hasil").hidden = true; $("#skel").hidden = false;
    } else if (polos(state.q) !== polos(state.data.q)) {
      // Aset berganti dan belum ada hasil tersimpan: kepala langsung menunjukkan aset baru, isi lama diredupkan.
      $("#work").classList.add("ganti");
      $("#aSym").textContent = polos(state.q);
      $("#aPx").textContent = "…"; $("#aChg").textContent = ""; $("#aChg").className = "chg";
      $("#aLive").hidden = true; $("#aName").hidden = true;
      $("#aTag").textContent = t("Memuat") + " · " + labelTf(state.tf);
    }
    try {
      const url = `/api/analisa?q=${encodeURIComponent(state.q)}&tf=${encodeURIComponent(state.tf)}&pasar=${encodeURIComponent(state.pasar)}&bahasa=${ATB.lang}`;
      let d;
      try { d = await (await fetch(url, { headers: { Accept: "application/json" } })).json(); }
      catch { throw new Error(t("Panel lokal tidak merespons. Jalankan peluncur Analisa Teknikal, lalu coba lagi.")); }
      await fontSiap;
      if (nomor !== state.minta) return;  // sudah ada permintaan lebih baru
      if (!d.ok) throw new Error(d.pesan || t("Gagal menganalisa."));
      if (d.tf !== state.tf) setTf(d.tf);
      state.data = d; state.q = d.q;
      $("#q").value = d.q;
      ingatan.delete(kunci); ingatan.set(kunci, { d, t: Date.now() });
      if (ingatan.size > 12) ingatan.delete(ingatan.keys().next().value);
      render(d);
      recent(d.q.toUpperCase());
      setStatus(d.sumber === "cache" ? "warn" : "live", `${d.sumber === "cache" ? "Cache" : "Live"} · ${d.waktu_tarik}`);
      umumkan(`${d.hasil.symbol} ${labelTf(d.tf)}: ${t("skor")} ${skorTxt(d.hasil.score)}, ${d.hasil.label_id}.`);
      if (d.tf_catatan) toast(t("Timeframe {catatan}.", { catatan: d.tf_catatan }));
      catat("cek", push ? "push" : "replace");
    } catch (err) {
      if (nomor !== state.minta) return;
      const pesan = err.message || t("Gagal menganalisa.");
      setStatus("err", TIDAK_ADA.test(pesan) ? t("Tidak ditemukan") : t("Gagal"));
      umumkan(pesan);
      $("#skel").hidden = true;
      if (!state.data) showState("error", pesan);
      else { toast(pesan, 6000); if ($("#work").classList.contains("ganti")) { state.q = state.data.q; $("#q").value = state.q; setTf(state.data.tf); render(state.data); } }
    } finally {
      if (nomor === state.minta) { $("#work").setAttribute("aria-busy", "false"); $("#work").classList.remove("ganti"); $("#btnAnalisa").disabled = false; }
    }
  }

  const TIDAK_ADA = /tidak ditemukan|tidak ada di cache|not found|not in the price cache/i;
  const chipsBaris = (label, daftar) => (daftar.length ? `<p class="start-lbl">${esc(label)}</p><div class="chips">${daftar.map((q) => `<button type="button" class="chip" data-q="${esc(q)}">${esc(q)}</button>`).join("")}</div>` : "");
  const chipsContoh = () => `<div class="chips">${CONTOH.map((q) => `<button type="button" class="chip" data-q="${q}">${q}</button>`).join("")}</div>`;
  // Layar awal: ticker yang terakhir dilihat dan (di mode daftar pantau) isi daftar pantau, lalu contoh.
  function chipsAwal() {
    let r = []; try { r = JSON.parse(simpan.get("at.recent") || "[]"); } catch {}
    const pantau = (typeof daftarPantau !== "undefined" ? daftarPantau : []).map((x) => String(x).replace(/\.JK$/, "").replace(/-USD$/, "")).filter((x) => !r.includes(x)).slice(0, 12);
    return chipsBaris(t("Terakhir dilihat"), r) + chipsBaris(t("Daftar pantau"), pantau) + (r.length || pantau.length ? `<p class="start-lbl">${t("Contoh")}</p>` : "") + chipsContoh();
  }
  function showState(kind, pesan) {
    const s = $("#stateChart");
    s.hidden = false;
    $("#assetHead").hidden = true;
    if (kind === "start") {
      s.innerHTML = `<div>${icon("chart", "big-ico")}<h2>${t("Cek aset apa saja")}</h2><p>${t("Saham IDX, saham/ETF AS, kripto, indeks, atau forex. Format TradingView seperti")} <span class="mono">IDX:BBCA</span> ${t("juga bisa.")}</p>${chipsAwal()}<p class="faint" style="margin-top:16px;font-size:12px">${t("Tekan")} <kbd>/</kbd> ${t("untuk langsung mengetik ticker.")}</p></div>`;
    } else if (kind === "loading") {
      s.innerHTML = `<div class="skel-chart" role="status"><div class="batang" aria-hidden="true">${Array.from({ length: 28 }, (_, i) => `<i style="height:${30 + ((i * 37) % 55)}%"></i>`).join("")}</div><p>${esc(t("Menarik data harga {q}…", { q: state.q.toUpperCase() }))}</p></div>`;
    } else if (kind === "error") {
      const tidakAda = TIDAK_ADA.test(pesan);
      s.innerHTML = `<div>${icon(tidakAda ? "search" : "warn", "big-ico")}<h2>${t(tidakAda ? "Ticker tidak ditemukan" : "Data tidak bisa diambil")}</h2><p>${esc(pesan)}</p>
        <p class="faint" style="font-size:13px">${t("Saham IDX cukup kodenya (BBCA). Kripto: BTC atau BINANCE:BTCUSDT. Indeks: IHSG, SPX.")}</p>
        <div class="act"><button type="button" class="btn" id="btnUlang">${icon("refresh")}${t("Coba lagi")}</button></div>${chipsContoh()}</div>`;
      $("#btnUlang").addEventListener("click", () => analisa());
    }
  }

  // ---------- render ----------
  function render(d) {
    $("#stateChart").hidden = true;
    $("#assetHead").hidden = false;
    $("#secStart").hidden = true;
    const r = d.hasil, mk = d.pasar, I = r.indicators;
    $("#aSym").textContent = r.symbol;
    $("#aTag").textContent = (KELAS[mk] || t("Indeks/forex")) + " · " + labelTf(d.tf);
    $("#aLive").hidden = d.berjalan == null;
    $("#aPx").textContent = fp(r.price, mk);
    const chg = $("#aChg");
    chg.className = "chg " + (I.change_pct >= 0 ? "up" : "down");
    chg.textContent = pct(I.change_pct);
    chg.title = t("Perubahan dari bar sebelumnya");
    const nm = [...new Set([d.nama, d.kode].filter((x) => x && x !== r.symbol))].join(" · ");
    $("#aName").textContent = nm; $("#aName").hidden = !nm;
    document.title = `${r.symbol} ${skorTxt(r.score)} · Analisa Teknikal`;
    drawCharts(r, d.lapisan);
    renderSide(d);
  }

  function renderSide(d) {
    const r = d.hasil, mk = d.pasar, I = r.indicators;

    // Vonis + skor per timeframe
    $("#hasil").hidden = false; $("#skel").hidden = true;
    $("#secVerdict").hidden = false; $("#secTf").hidden = false;
    const vs = $("#vScore"); vs.textContent = skorTxt(r.score); vs.className = "score " + cls(r.score);
    $("#vLabel").textContent = r.label_id; $("#vLabel").className = "label " + cls(r.score);
    $("#vTrend").innerHTML = ist(`${r.trend.label} · ${r.trend.structure}`);  // istilah: arti awam saat disorot
    // Skor beli 0–100 (dari data harian, sama dengan kolom Beli di tab Portofolio dan kartu ekstensi)
    $("#vBeli").innerHTML = beliHtml(d.skor_beli); $("#vBeli").hidden = !d.skor_beli;
    const konf = r.mtf && r.mtf.confluence;
    $("#vKonf").hidden = !konf; $("#vKonf").innerHTML = ist(konf || "");
    const jalan = d.berjalan;
    $("#vLive").hidden = jalan == null;
    if (jalan != null) $("#vLive").innerHTML = `${icon("info", "sm")}<span>${esc(ATB.en
      ? t("Candle {mana} belum selesai (±{persen}% berjalan). Volume dihitung proyeksi, pola candle terakhir belum dihitung.", { mana: t(d.tf === "1d" ? "hari ini" : "terakhir"), persen: num(jalan * 100, 0) })
      : `Candle ${d.tf === "1d" ? "hari ini" : "terakhir"} belum selesai (±${num(jalan * 100, 0)}% berjalan). Volume dihitung proyeksi, pola candle terakhir belum dihitung.`)}</span>`;
    $("#vMtf").innerHTML = (r.mtf ? r.mtf.summary : []).map((m) => `<tr><td class="tf">${esc(labelTf(m.tf))}</td><td class="sk ${cls(m.score)}">${skorTxt(m.score)}</td><td class="${cls(m.score)}">${esc(m.label_id || "")}</td><td class="tr">${esc(m.trend)}</td></tr>`).join("");

    // Kekuatan relatif & riwayat skor (riwayat diambil terpisah supaya tampilan utama tidak menunggu)
    $("#vRs").innerHTML = rsHtml(d.rs);
    $("#vRiwayat").hidden = true;
    muatRiwayat(d);
    muatSemuaTf(d);
    // Rencana tindakan (tanpa data posisi: Cek aset terpisah dari portofolio)
    const ra = d.rencana_aksi;
    $("#secAksi").hidden = !(ra && ra.langkah);
    $("#aksiTf").textContent = "· " + labelTf(d.tf);
    if (ra && ra.langkah) { $("#aksiPill").outerHTML = sikapPill(ra).replace('class="pill', 'id="aksiPill" class="pill'); $("#aksi").innerHTML = aksiHtml(ra, { posisi: false }); }
    // Analisa tertulis
    $("#secNarasi").hidden = !d.narasi;
    $("#narasi").innerHTML = narasiHtml(d.narasi);

    // Komposisi skor: satu baris per kategori, batang dari tengah (kiri bearish, kanan bullish)
    const kat = {};
    r.signals.forEach((s) => { if (s.score) kat[s.cat] = (kat[s.cat] || 0) + s.score; });
    // Angka ditulis dalam poin skor (jumlah semua baris = skor), bukan angka mentah mesin.
    const ke = poinSkor(r.signals, r.score);
    const urut = Object.entries(kat).map(([nama, v]) => [nama, ke(v)]).filter(([, v]) => Math.abs(v) >= 0.5).sort((a, b) => Math.abs(b[1]) - Math.abs(a[1]));
    const maks = Math.max(20, ...urut.map(([, v]) => Math.abs(v)));
    $("#komposisi").hidden = !urut.length;
    $("#kList").innerHTML = urut.map(([nama, v]) => `<li><span>${esc(nama)}</span><span class="kbar" aria-hidden="true"><span class="${v > 0 ? "pos" : "neg"}" style="width:${(Math.abs(v) / maks * 50).toFixed(1)}%"></span></span><span class="v ${v > 0 ? "up" : "down"}">${num(v, 0, true)}</span></li>`).join("")
      + `<li class="jumlah"><span>${t("Skor")}</span><span></span><span class="v ${cls(r.score)}">${skorTxt(r.score)}</span></li>`;
    $("#kCatatan").hidden = !r.lawan_tren;

    // Tanda
    const fl = d.bendera || [];
    $("#secFlag").hidden = !fl.length;
    $("#flags").innerHTML = urutTanda(fl).map((f) => `<li class="${baru(f) ? "" : "lama"}">${sevIcon(f.level)}<span>${tagTanda(f)}${ist(f.teks)}${sejakTanda(f)}</span><span></span></li>`).join("");

    // Rencana
    const p = r.plan; $("#secPlan").hidden = false;
    // Label yang sama dengan Rencana tindakan di tab Ringkasan (dulu dua istilah berbeda untuk hal yang sama).
    if (ra && ra.sikap) $("#planPill").outerHTML = sikapPill(ra).replace('class="pill', 'id="planPill" class="pill');
    else { const pill = $("#planPill"); pill.className = "pill " + p.bias; pill.textContent = t({ long: "Beli saat koreksi", short: "Belum saatnya beli", wait: "Tunggu konfirmasi" }[p.bias]); }
    let h = "";
    if (p.bias === "long") {
      h = `<dt>${t("Area beli")}</dt><dd>${esc(fp(p.entry_zone[0], mk))} – ${esc(fp(p.entry_zone[1], mk))}</dd><dt title="${t("Rencana beli batal bila close di bawah level ini")}">${t("Stop (close di bawah)")}</dt><dd class="down">${esc(fp(p.stop_loss, mk))} <span class="faint">${num(-p.risk_pct, 1)}%</span></dd>`;
      p.targets.forEach((x, i) => { h += `<dt>Target ${i + 1}</dt><dd class="up">${esc(fp(x, mk))} <span class="faint">R:R ${num(p.rr[i], 1)}</span></dd>`; });
    } else if (p.bias === "short") {
      // "Target turun", bukan "Support 1/2": angkanya bisa berbeda dari S1/S2 di tabel support & resistance di bawahnya.
      p.targets.forEach((x, i) => { h += `<dt title="${t("Perkiraan tujuan harga bila tekanan turun berlanjut")}">${t("Target turun")} ${i + 1}</dt><dd>${esc(fp(x, mk))} <span class="faint">${num((x / r.price - 1) * 100, 1, true)}%</span></dd>`; });
      h += `<dt title="${t("Tren turun dianggap selesai bila close di atas level ini")}">${t("Konfirmasi naik (close di atas)")}</dt><dd>${esc(fp(p.stop_loss, mk))}</dd>`;
    } else {
      h = `<dt>Range</dt><dd>${esc(fp(p.range[0], mk))} – ${esc(fp(p.range[1], mk))}</dd><dt>${t("Menguat bila close di atas")}</dt><dd class="up">${esc(fp(p.buy_trigger, mk))}</dd><dt>${t("Melemah bila close di bawah")}</dt><dd class="down">${esc(fp(p.sell_trigger, mk))}</dd>`;
    }
    $("#plan").innerHTML = h; $("#planNote").innerHTML = ist(p.note);

    // Level
    const rows = [];
    const jarak = (x) => num((x / r.price - 1) * 100, 1, true) + "%";
    const dk = d.dekat || {};
    r.resistance.slice(0, 3).reverse().forEach((x, i, a) => rows.push(`<tr><td class="k down">R${a.length - i}</td><td class="p">${esc(fp(x.price, mk))}${a.length - i === 1 ? dekatTag(dk.r1) : ""}</td><td class="d">${jarak(x.price)}</td><td class="n" title="${t("Disentuh {n} kali — makin sering, makin kuat levelnya", { n: x.touches })}">${x.touches}×</td></tr>`));
    rows.push(`<tr class="now"><td class="k">${t("Harga")}</td><td class="p">${esc(fp(r.price, mk))}</td><td class="d"></td><td class="n"></td></tr>`);
    r.support.slice(0, 3).forEach((x, i) => rows.push(`<tr><td class="k up">S${i + 1}</td><td class="p">${esc(fp(x.price, mk))}${i === 0 ? dekatTag(dk.s1) : ""}</td><td class="d">${jarak(x.price)}</td><td class="n" title="${t("Disentuh {n} kali — makin sering, makin kuat levelnya", { n: x.touches })}">${x.touches}×</td></tr>`));
    r.trendlines.forEach((x) => rows.push(`<tr><td class="k" style="color:var(--data-biru)" title="Trendline">TL</td><td class="p">${esc(fp(x.value_now, mk))}</td><td class="d" colspan="2">${t(x.kind === "support" ? "naik" : "turun")}${x.broken ? " · " + t("ditembus") : ""}</td></tr>`));
    $("#levels").innerHTML = `<thead><tr><th></th><th>${t("Harga")}</th><th>${t("Jarak")}</th><th title="${t("Berapa kali harga berbalik di level ini")}">${t("Disentuh")}</th></tr></thead><tbody>${rows.join("")}</tbody>`; $("#secLv").hidden = false;

    // Pola
    const pats = [
      ...r.chart_patterns.map((x) => [x.bias, x.name_id, x.status + (x.target ? ` · ${t("target")} ` + fp(x.target, mk) + (x.target_hit ? " " + t("sudah tercapai") : "") : "")]),
      ...r.divergences.map((x) => [x.bias, x.name_id, "divergence"]),
      ...r.candles_recent.map((x) => [x.bias, x.name_id, ["candlestick", x.konfirmasi ? t(KONFIRMASI[x.konfirmasi] || "") : "", x.lokasi ? t("di {jenis}", { jenis: x.lokasi.jenis }) + " " + fp(x.lokasi.harga, mk) : ""].filter(Boolean).join(" · ")]),
    ];
    $("#secPat").hidden = !pats.length; $("#kosongPola").hidden = !!pats.length;
    $("#pats").innerHTML = pats.map(([b, n, s]) => `<li>${biasIcon(b)}<span>${esc(n)}<span class="sub">${ist(s)}</span></span><span></span></li>`).join("");

    // Sinyal
    $("#secSig").hidden = false;
    $("#sigs").innerHTML = sinyalHtml(r.signals, r.score);

    // Indikator
    $("#secInd").hidden = false;
    $("#inds").innerHTML = [["RSI 14", num(I.rsi14, 1)], ["ADX 14", num(I.adx14, 1)], ["Stoch K/D", `${num(I.stoch_k, 0)} / ${num(I.stoch_d, 0)}`], ["ATR", num(I.atr_pct, 1) + "%"],
      ["MA 20", fp(I.sma20, mk)], ["MA 50", fp(I.sma50, mk)], ["MA 200", fp(I.sma200, mk)], ["EMA 21", fp(I.ema21, mk)],
      [t("High 52 mg"), fp(I.high_52w, mk)], [t("Low 52 mg"), fp(I.low_52w, mk)], ["Volume", I.volume_ratio ? num(I.volume_ratio, 2) + t("× rata-rata") + (I.volume_proyeksi ? t(" (proyeksi)") : "") : "—"], ["Data", `${r.bars} ${t("bar")}`]]
      .map(([k, v]) => `<div><span>${esc(k)}</span><span>${esc(v)}</span></div>`).join("");
  }

  const KONFIRMASI = { ya: "terkonfirmasi candle berikutnya", tunggu: "menunggu konfirmasi candle berikutnya", belum: "belum terkonfirmasi", gagal: "gagal dikonfirmasi" };

  // ---------- tab hasil (Ringkasan · Level & pola · Sinyal) ----------
  const TAB = ["ringkas", "level", "sinyal"];
  function pilihTab(id, fokus) {
    if (!TAB.includes(id)) id = TAB[0];
    TAB.forEach((k) => {
      const on = k === id, b = $("#tab-" + k);
      b.setAttribute("aria-selected", String(on)); b.tabIndex = on ? 0 : -1;
      $("#tp-" + k).hidden = !on;
    });
    simpan.set("at.tab", id);
    if (fokus) $("#tab-" + id).focus();
  }
  $("#tabs").addEventListener("click", (e) => { const b = e.target.closest('[role="tab"]'); if (b) pilihTab(b.id.slice(4)); });
  $("#tabs").addEventListener("keydown", (e) => {
    const i = TAB.indexOf((document.activeElement.id || "").slice(4));
    if (i < 0) return;
    const ke = { ArrowRight: (i + 1) % TAB.length, ArrowLeft: (i + TAB.length - 1) % TAB.length, Home: 0, End: TAB.length - 1 }[e.key];
    if (ke == null) return;
    e.preventDefault(); pilihTab(TAB[ke], true);
  });
  pilihTab(simpan.get("at.tab") || "ringkas");

  // Kesimpulan semua timeframe (1H, 4H, 1D, 1W, 1M) + skor gabungan + saran. Tidak bergantung timeframe yang dibuka,
  // jadi disimpan 2 menit per aset supaya ganti timeframe tidak menarik ulang.
  let nomorSemua = 0;
  const cacheSemua = new Map();
  async function muatSemuaTf(d) {
    const nomor = ++nomorSemua, kunci = `${d.kode}|${d.pasar}|${ATB.lang}`;
    $("#vGab").hidden = true;
    let h = cacheSemua.get(kunci);
    if (!h || Date.now() - h.waktu > 120000) {
      $("#secSemua").hidden = false;
      $("#semua").innerHTML = `<p class="muted"><span class="spinner" aria-hidden="true" style="display:inline-block;width:14px;height:14px;vertical-align:-2px;margin-right:6px"></span>${t("Menghitung semua timeframe…")}</p>`;
      $("#semuaPill").className = "pill"; $("#semuaPill").textContent = "";
      try {
        const j = await (await fetch(`/api/semua_tf?q=${encodeURIComponent(d.kode)}&pasar=${encodeURIComponent(d.pasar || "")}&bahasa=${ATB.lang}`)).json();
        if (!j.ok) throw new Error(j.pesan || "");
        h = { waktu: Date.now(), j };
        cacheSemua.set(kunci, h);
      } catch {
        if (nomor === nomorSemua) { $("#secSemua").hidden = true; $("#vMtf").hidden = false; }
        return;
      }
    }
    if (nomor !== nomorSemua) return;
    tampilSemuaTf(h.j, d.tf);
  }
  function tampilSemuaTf(j, tfAktif) {
    const kelas = (s) => (s >= 20 ? "long" : s <= -20 ? "short" : "wait");
    $("#vGab").innerHTML = `<span>${t("Skor semua timeframe")}</span> <span class="num ${cls(j.skor)}">${skorTxt(j.skor)}</span> <span class="${cls(j.skor)}">${esc(j.label)}</span>`;
    $("#vGab").title = t("Rata-rata tertimbang skor 1H, 4H, 1D, 1W, dan 1M");
    $("#vGab").hidden = false;
    $("#semuaPill").className = "pill " + kelas(j.skor);
    $("#semuaPill").textContent = `${skorTxt(j.skor)} · ${j.label}`;
    const bobot = j.bobot || {};
    const baris = (j.tf || []).map((b) => `<tr class="${b.tf === tfAktif ? "aktif" : ""}"><td class="tf">${esc(b.nama)}</td><td class="sk ${cls(b.skor)}">${skorTxt(b.skor)}</td><td class="${cls(b.skor)}">${esc(b.label)}${b.berjalan ? ` <span class="faint" title="${t("Candle terakhir belum selesai")}">·</span>` : ""}</td><td class="ra">${ist(b.ringkas || "")}</td></tr>`).join("");
    const ket = Object.entries(bobot).map(([tf, w]) => `${labelTf(tf)} ${Math.round(w * 100)}%`).join(" · ");
    $("#semua").innerHTML = `<table class="mtf" aria-label="${t("Skor dan rencana per timeframe")}">${baris}</table>
      <p class="kes">${ist(j.kesimpulan)}</p>
      <h3>${t("Saran")}</h3>
      <ul class="saran">${(j.saran || []).map((x, i, a) => `<li class="${i === a.length - 1 ? "risiko" : ""}">${ist(x)}</li>`).join("")}</ul>
      <p class="note">${esc(t("Skor gabungan = rata-rata tertimbang ({ket}). Level saran dari timeframe 1D. Rencana otomatis adalah peta level, bukan sinyal pasti: di uji data lama hasil rata-ratanya belum positif.", { ket }))}</p>`;
    $("#secSemua").hidden = false;
    $("#vMtf").hidden = true;  // tabel lama (timeframe aktif + satu di atasnya) sudah tercakup di sini
  }

  let nomorRiwayat = 0;
  async function muatRiwayat(d) {
    const nomor = ++nomorRiwayat;
    try {
      const h = await (await fetch(`/api/riwayat?q=${encodeURIComponent(d.kode)}&tf=${encodeURIComponent(d.tf)}&pasar=${encodeURIComponent(d.pasar || "")}&bahasa=${ATB.lang}`)).json();
      if (nomor !== nomorRiwayat || !h.ok || !h.titik || h.titik.length < 2) return;
      const titik = h.titik[h.titik.length - 1][1] === h.skor ? h.titik : h.titik.concat([[0, h.skor]]);
      const satuan = t({ "1d": "hari", "1wk": "minggu", "1mo": "bulan" }[d.tf] || "bar");
      $("#vRiwayat").innerHTML = `<div class="riw-head"><span>${t("Skor {n} {satuan} terakhir", { n: h.titik.length, satuan })}</span><span class="num">${skorTxt(titik[0][1])} → ${skorTxt(h.skor)}</span></div>${sparkline(titik, { w: 320, h: 44 })}${h.kalimat ? `<p>${esc(h.kalimat)}</p>` : ""}`;
      $("#vRiwayat").hidden = false;
    } catch { /* riwayat hanya pelengkap */ }
  }

  // ---------- chart ----------
  // Chart dibuat sekali; saat ganti aset/timeframe hanya datanya yang diganti, jadi tidak berkedip.
  // Garis analisa (S/R, rencana, trendline, pola) digambar oleh lapisan.js — sama dengan lapisan di chart TradingView.
  let G = null, cur = null, kunciTampil = "";
  const charts = () => (G ? [G.main, G.rsiC, G.macdC].filter(Boolean) : []);
  document.querySelectorAll("#overlays .ov").forEach((b) => {
    b.setAttribute("aria-pressed", String(!!overlays[b.dataset.k]));
    b.addEventListener("click", () => {
      overlays[b.dataset.k] = !overlays[b.dataset.k];
      b.setAttribute("aria-pressed", String(overlays[b.dataset.k]));
      simpan.set("at.overlays", JSON.stringify(overlays));
      if (state.data) drawCharts(state.data.hasil, state.data.lapisan);
    });
  });
  const baseOpts = (time) => ({
    autoSize: true,
    layout: { background: { type: "solid", color: C.ground }, textColor: C.text3, fontFamily: "'Fira Code', ui-monospace, monospace", fontSize: 11, attributionLogo: false },
    grid: { vertLines: { color: C.grid }, horzLines: { color: C.grid } },
    rightPriceScale: { borderColor: C.line, minimumWidth: 64, entireTextOnly: true },
    timeScale: { borderColor: C.line, visible: time, timeVisible: false, secondsVisible: false, rightOffset: 6 },
    crosshair: { mode: 0, vertLine: { color: "#46464e", labelBackgroundColor: C.line2 }, horzLine: { color: "#46464e", labelBackgroundColor: C.line2 } },
    localization: { locale: ATB.lokalTanggal },
  });
  // Format sumbu harga: IDX 5.075 · AS $-gaya 181.60 · harga ≥ 1.000 tanpa desimal di sumbu
  function formatHarga(mk, ref) {
    if (mk === "idx") return { type: "custom", minMove: 1, formatter: (x) => Math.round(x).toLocaleString(ATB.lokal) };
    const a = Math.abs(ref) || 1;
    const d = mk === "us" ? 2 : a >= 1000 ? 0 : mk === "lain" ? (a >= 100 ? 2 : a >= 1 ? 4 : 6) : Math.min(8, Math.max(2, 4 - Math.floor(Math.log10(a))));
    return { type: "custom", minMove: Math.pow(10, -d), formatter: (x) => x.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d }) };
  }
  // Indonesia: T triliun · M miliar · jt juta · rb ribu. Inggris: T trillion · B billion · M million · K thousand.
  const SATUAN_VOL = ATB.en ? [" T", " B", " M", " K"] : [" T", " M", " jt", " rb"];
  const volTxt = (v) => (v == null ? "—" : v >= 1e12 ? num(v / 1e12, 1) + SATUAN_VOL[0] : v >= 1e9 ? num(v / 1e9, 1) + SATUAN_VOL[1] : v >= 1e6 ? num(v / 1e6, 1) + SATUAN_VOL[2] : v >= 1e3 ? num(v / 1e3, 1) + SATUAN_VOL[3] : num(v, 0));
  const penuh = (t, a) => t.map((x, i) => (a[i] == null ? { time: x } : { time: x, value: a[i] }));  // titik kosong menjaga indeks antar-panel tetap sejajar

  // Level terdekat dan garis rencana ikut masuk skala harga (selama tidak terlalu jauh), supaya selalu terlihat.
  function skalaDenganLevel(a) {
    if (!a || !a.priceRange || !cur || !cur.L) return a;
    const lo = a.priceRange.minValue, hi = a.priceRange.maxValue, tinggi = hi - lo;
    if (!(tinggi > 0)) return a;
    const k = [];
    if (overlays.sr) cur.L.level.forEach((v) => { if (v.k === "S1" || v.k === "R1") k.push(v.harga); });
    if (overlays.rencana && cur.L.rencana) {
      cur.L.rencana.garis.forEach((v) => { if (v.jenis !== "s" && !/ [23]$/.test(v.k)) k.push(v.harga); });
      if (cur.L.rencana.zona) k.push(cur.L.rencana.zona.dari, cur.L.rencana.zona.ke);
    }
    let lo2 = lo, hi2 = hi;
    k.forEach((p) => { if (p < lo && lo - p <= tinggi * 0.4) lo2 = Math.min(lo2, p); else if (p > hi && p - hi <= tinggi * 0.4) hi2 = Math.max(hi2, p); });
    return { priceRange: { minValue: lo2, maxValue: hi2 }, margins: a.margins };
  }

  class PrimitifLapisan {
    constructor() { this._view = { zOrder: () => "top", renderer: () => ({ draw: (target) => this._gambar(target) }) }; }
    attached(p) { this._chart = p.chart; this._series = p.series; this._minta = p.requestUpdate; }
    detached() { this._chart = this._series = this._minta = null; }
    updateAllViews() {}
    paneViews() { return [this._view]; }
    // Label harga garis analisa di sumbu kanan. Dulu memakai label bawaan chart, yang saling menimpa dan menutupi
    // sebagian angka sumbu ("2.4̶0̶0̶"). Sekarang digambar lapisan.js: digeser bila berdekatan, dengan latar penutup.
    priceAxisPaneViews() {
      if (!this._sumbuView) this._sumbuView = { zOrder: () => "top", renderer: () => ({ draw: (target) => this._gambarSumbu(target) }) };
      return [this._sumbuView];
    }
    _gambarSumbu(target) {
      if (!cur || !cur.L || !this._series || !window.ATLapisan) return;
      const s = this._series;
      target.useMediaCoordinateSpace(({ context, mediaSize }) => {
        const geo = { w: 4000, h: mediaSize.height, gelap: true, y: (p) => s.priceToCoordinate(p), x: () => null };
        const daftar = window.ATLapisan.gambar(null, cur.L, geo, { sr: overlays.sr, rencana: overlays.rencana, tl: false, pola: overlays.pat, nSr: 1 }).sumbu
          .filter((d) => d.pri >= 2);
        window.ATLapisan.gambarSumbu(context, daftar, { w: mediaSize.width, h: mediaSize.height, huruf: '"Fira Code", ui-monospace, monospace', latar: C.ground,
          hindariY: s.priceToCoordinate(cur.S.c[cur.n - 1]), format: cur.pf ? cur.pf.formatter : null });
      });
    }
    segarkan() { if (this._minta) this._minta(); }
    _gambar(target) {
      if (!cur || !cur.L || !this._series || !window.ATLapisan) return;
      const ts = this._chart.timeScale(), s = this._series;
      target.useMediaCoordinateSpace(({ context, mediaSize }) => {
        window.ATLapisan.gambar(context, cur.L,
          { w: mediaSize.width, h: mediaSize.height, gelap: true, y: (p) => s.priceToCoordinate(p),
            // indeks pecahan (mis. titik tengah pola) dihitung dari dua bar di sekitarnya
            x: (i) => { const f = Math.floor(i), a = ts.logicalToCoordinate(f); if (a == null || f === i) return a; const b = ts.logicalToCoordinate(f + 1); return b == null ? a : a + (b - a) * (i - f); } },
          { sr: overlays.sr, rencana: overlays.rencana, tl: overlays.tl, pola: overlays.pat, nSr: EMBED ? 2 : 3, huruf: '"Fira Sans", system-ui, sans-serif' });
      });
    }
  }

  const fmtWaktu = (x) => new Date(x * 1000).toLocaleString(ATB.lokalTanggal, cur.intraday ? { timeZone: "UTC", day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" } : { timeZone: "UTC", day: "numeric", month: "short", year: "numeric" });
  // Legenda: OHLC + MA di bar yang disorot (atau bar terakhir)
  function legend(i) {
    const { S, t, n, mk } = cur, f = (x) => esc(fp(x, mk));
    const ch = i > 0 && S.c[i - 1] ? (S.c[i] / S.c[i - 1] - 1) * 100 : null;
    const jalan = i === n - 1 && state.data && state.data.berjalan != null;
    let h = `<span class="tm">${fmtWaktu(t[i])}${cur.intraday ? " WIB" : ""}${jalan ? " · " + ATB.t("berjalan") : ""}</span><span>O <span class="v">${f(S.o[i])}</span></span><span>H <span class="v">${f(S.h[i])}</span></span><span>L <span class="v">${f(S.l[i])}</span></span><span>C <span class="v">${f(S.c[i])}</span></span>`;
    if (ch != null) h += `<span class="${ch >= 0 ? "up" : "down"}">${pct(ch)}</span>`;
    if (overlays.vol && cur.adaVol) h += `<span>Vol <span class="v">${volTxt(S.v[i])}</span></span>`;
    if (overlays.ma && !EMBED) h += `<span><b style="color:${C.ma20}">MA20</b> <span class="v">${f(S.sma20[i])}</span></span><span><b style="color:${C.ma50}">MA50</b> <span class="v">${f(S.sma50[i])}</span></span><span><b style="color:${C.ma200}">MA200</b> <span class="v">${f(S.sma200[i])}</span></span>`;
    $("#lgMain").innerHTML = h;
  }
  function subLegend(i) {
    if (!G.rsiC) return;
    const { S, md } = cur;
    $("#lgRsi").innerHTML = `<span>RSI 14 <b style="color:#b48ef0">${num(S.rsi[i], 1)}</b></span>`;
    $("#lgMacd").innerHTML = `<span>MACD <b style="color:${C.ma50}">${num(S.macd[i], md)}</b></span><span>Signal <b style="color:${C.ma20}">${num(S.macd_signal[i], md)}</b></span><span>Hist <b class="${(S.macd_hist[i] || 0) >= 0 ? "up" : "down"}">${num(S.macd_hist[i], md)}</b></span>`;
  }

  // Panel samping ikut bergulir sebagai satu halaman, jadi roda mouse di atas chart menggulir halaman (bukan zoom).
  // Zoom: cubit di trackpad / Ctrl+roda, atau tombol − + di sudut chart. Geser: seret, atau gulir mendatar.
  const opsiGerak = EMBED ? { handleScroll: { mouseWheel: false, pressedMouseMove: true, horzTouchDrag: true, vertTouchDrag: false },
    handleScale: { mouseWheel: false, pinch: true, axisPressedMouseMove: true, axisDoubleClickReset: true } } : {};
  const jepit = (x, a, b) => Math.min(b, Math.max(a, x));
  function zoom(faktor, titik = 0.85) {
    if (!G || !cur) return;
    const ts = G.main.timeScale(), r = ts.getVisibleLogicalRange();
    if (!r) return;
    const lebar = r.to - r.from, baru = jepit(lebar * faktor, 12, cur.n + 40), pusat = r.from + lebar * titik;
    ts.setVisibleLogicalRange({ from: pusat - baru * titik, to: pusat + baru * (1 - titik) });
  }
  function tampilAwal() {
    if (!G || !cur) return;
    const tampilBar = Math.min(cur.n, EMBED ? 90 : 180);
    G.main.priceScale("right").applyOptions({ autoScale: true });
    G.main.timeScale().setVisibleLogicalRange({ from: cur.n - tampilBar, to: cur.n + (EMBED ? 12 : 16) });
  }
  $("#chartCtl").addEventListener("click", (e) => {
    const b = e.target.closest("[data-aksi]");
    if (!b) return;
    const aksi = b.dataset.aksi;
    if (aksi === "perbesar") zoom(1 / 1.4);
    else if (aksi === "perkecil") zoom(1.4);
    else if (aksi === "awal") tampilAwal();
    else if (aksi === "tinggi") aturTinggi(!document.body.classList.contains("chart-tinggi"));
  });
  function aturTinggi(tinggi) {
    document.body.classList.toggle("chart-tinggi", tinggi);
    const b = $('#chartCtl [data-aksi="tinggi"]');
    b.setAttribute("aria-pressed", String(tinggi));
    b.title = t(tinggi ? "Kecilkan chart" : "Tinggikan chart");
    b.setAttribute("aria-label", b.title);
    simpan.set("at.chartTinggi", tinggi ? "1" : "0");
  }
  if (EMBED) {
    aturTinggi(simpan.get("at.chartTinggi") === "1");
    $("#cMain").addEventListener("wheel", (e) => {
      if (!G || !cur) return;
      const kotak = $("#cMain").getBoundingClientRect(), lebarPlot = Math.max(40, kotak.width - G.main.priceScale("right").width());
      if (e.ctrlKey || e.metaKey) {
        e.preventDefault();
        zoom(Math.exp(jepit(e.deltaY, -60, 60) * 0.012), jepit((e.clientX - kotak.left) / lebarPlot, 0, 1));
      } else if (Math.abs(e.deltaX) > Math.abs(e.deltaY)) {
        e.preventDefault();
        const ts = G.main.timeScale(), r = ts.getVisibleLogicalRange();
        if (!r) return;
        const geser = e.deltaX / lebarPlot * (r.to - r.from);
        ts.setVisibleLogicalRange({ from: r.from + geser, to: r.to + geser });
      }
    }, { passive: false });
  }

  function buat() {
    const main = LC.createChart($("#cMain"), { ...baseOpts(EMBED), ...opsiGerak });
    // Candle naik dan turun sama-sama terisi penuh (seperti tampilan bawaan TradingView); 17 Nov: dulu candle naik berongga
    const cs = main.addCandlestickSeries({ upColor: C.bull, downColor: C.bear, borderVisible: true, borderUpColor: C.bull, borderDownColor: C.bear, wickUpColor: C.bull, wickDownColor: C.bear,
      autoscaleInfoProvider: (asli) => skalaDenganLevel(asli()) });
    const vs = main.addHistogramSeries({ priceFormat: { type: "volume" }, priceScaleId: "vol", lastValueVisible: false, priceLineVisible: false });
    main.priceScale("vol").applyOptions({ scaleMargins: { top: 0.82, bottom: 0 } });
    const ln = (c, o) => c.addLineSeries({ lineWidth: 1, priceLineVisible: false, lastValueVisible: false, crosshairMarkerVisible: false, ...o });
    const ma = [ln(main, { color: C.ma20 }), ln(main, { color: C.ma50, lineWidth: 2 }), ln(main, { color: C.ma200, lineWidth: 2 })];
    const bb = [ln(main, { color: "rgba(178,189,204,.45)", lineStyle: 2 }), ln(main, { color: "rgba(178,189,204,.45)", lineStyle: 2 })];
    const prim = new PrimitifLapisan();
    cs.attachPrimitive(prim);
    G = { main, cs, vs, ma, bb, prim, rsiC: null, macdC: null };
    if (!EMBED) {
      G.rsiC = LC.createChart($("#cRsi"), baseOpts(false));
      G.macdC = LC.createChart($("#cMacd"), baseOpts(true));
      G.rs = G.rsiC.addLineSeries({ color: "#b48ef0", lineWidth: 1, priceLineVisible: false, crosshairMarkerVisible: false, priceFormat: { type: "custom", minMove: 1, formatter: (x) => num(x, 0) },
        autoscaleInfoProvider: () => ({ priceRange: { minValue: 0, maxValue: 100 } }) });
      [30, 70].forEach((y) => G.rs.createPriceLine({ price: y, color: C.line2, lineWidth: 1, lineStyle: 2, axisLabelVisible: false }));
      G.rsiC.priceScale("right").applyOptions({ scaleMargins: { top: 0.12, bottom: 0.08 } });
      G.hs = G.macdC.addHistogramSeries({ priceLineVisible: false, lastValueVisible: false });
      // nilai terakhir MACD/signal sudah ada di legenda; label di sumbu hanya menutupi angka sumbunya
      G.ms = ln(G.macdC, { color: C.ma50 });
      G.sg = ln(G.macdC, { color: C.ma20 });
      G.macdC.priceScale("right").applyOptions({ scaleMargins: { top: 0.18, bottom: 0.12 } });
      let sync = false;
      charts().forEach((c) => c.timeScale().subscribeVisibleLogicalRangeChange((rg) => {
        if (sync || !rg) return; sync = true;
        charts().forEach((o) => { if (o !== c) o.timeScale().setVisibleLogicalRange(rg); });
        sync = false;
      }));
    }
    // Crosshair: legenda ikut bar yang disorot; garis vertikal ikut di panel RSI & MACD
    charts().forEach((c) => c.subscribeCrosshairMove((p) => {
      if (!cur) return;
      const i = p && p.time != null ? cur.iDari.get(p.time) : undefined;
      const ii = i == null ? cur.n - 1 : i;
      legend(ii); subLegend(ii);
      [[G.main, G.cs, cur.S.c], [G.rsiC, G.rs, cur.S.rsi], [G.macdC, G.ms, cur.S.macd]].forEach(([o, s, arr]) => {
        if (!o || o === c) return;
        if (i == null || arr[i] == null) o.clearCrosshairPosition(); else o.setCrosshairPosition(arr[i], p.time, s);
      });
    }));
  }

  function drawCharts(r, L) {
    if (!G) buat();
    const S = r.series, mk = r.market, n = S.t.length;
    const t = S.t.map((x) => Math.round(x) + WIB);
    const intraday = ["5m", "15m", "30m", "1h", "4h"].includes(r.tf);
    const pf = formatHarga(mk, r.price);
    const maxAbs = Math.max(1e-9, ...S.macd.filter((v) => v != null).map(Math.abs));
    const md = maxAbs >= 100 ? 0 : maxAbs >= 1 ? 2 : maxAbs >= 0.01 ? 4 : 6;
    cur = { S, t, n, mk, intraday, md, pf, L: L || null, iDari: new Map(t.map((x, i) => [x, i])), adaVol: S.v.some((x) => x > 0) };

    charts().forEach((c) => c.applyOptions({ timeScale: { timeVisible: intraday } }));
    G.cs.applyOptions({ priceFormat: pf });
    G.cs.setData(t.map((x, i) => ({ time: x, open: S.o[i], high: S.h[i], low: S.l[i], close: S.c[i] })));
    G.vs.applyOptions({ visible: overlays.vol && cur.adaVol });
    G.vs.setData(t.map((x, i) => ({ time: x, value: S.v[i], color: S.c[i] >= S.o[i] ? "rgba(38,166,154,.32)" : "rgba(239,83,80,.32)" })));
    [S.sma20, S.sma50, S.sma200].forEach((a, i) => { G.ma[i].applyOptions({ visible: overlays.ma, priceFormat: pf }); G.ma[i].setData(penuh(t, a)); });
    [S.bb_upper, S.bb_lower].forEach((a, i) => { G.bb[i].applyOptions({ visible: overlays.bb, priceFormat: pf }); G.bb[i].setData(penuh(t, a)); });
    // Panah kecil = pola candlestick kuat di 60 bar terakhir
    const markers = overlays.pat ? (S.candles_panah || S.candles_all || []).filter((x) => x.i >= n - 60 && x.bias !== 0 && x.strength >= 2)
      .map((x) => ({ time: t[x.i], position: x.bias > 0 ? "belowBar" : "aboveBar", color: x.bias > 0 ? C.bull : C.bear, shape: x.bias > 0 ? "arrowUp" : "arrowDown" })) : [];
    markers.sort((a, b) => a.time - b.time);
    G.cs.setMarkers(markers);
    if (G.rsiC) {
      const mpf = { type: "custom", minMove: Math.pow(10, -md), formatter: (x) => num(x, md) };
      G.rs.setData(penuh(t, S.rsi));
      G.hs.applyOptions({ priceFormat: mpf });
      G.hs.setData(t.map((x, i) => (S.macd_hist[i] == null ? { time: x } : { time: x, value: S.macd_hist[i], color: S.macd_hist[i] >= 0 ? "rgba(38,166,154,.5)" : "rgba(239,83,80,.5)" })));
      G.ms.applyOptions({ priceFormat: mpf }); G.ms.setData(penuh(t, S.macd));
      G.sg.applyOptions({ priceFormat: mpf }); G.sg.setData(penuh(t, S.macd_signal));
    }
    legend(n - 1); subLegend(n - 1);
    // Harga garis kunci di sumbu kanan digambar PrimitifLapisan.priceAxisPaneViews (lihat di atas).
    G.prim.segarkan();

    // Rentang tampil hanya diatur ulang saat aset atau timeframe berganti; muat ulang aset yang sama mempertahankan zoom.
    const kunci = `${r.symbol}|${mk}|${r.tf}`;
    if (kunci !== kunciTampil) {
      kunciTampil = kunci;
      tampilAwal();
    }
    $("#chartCtl").hidden = false;
    // Samakan lebar sumbu harga supaya bar di semua panel sejajar vertikal
    const samakan = () => {
      charts().forEach((c) => c.applyOptions({ rightPriceScale: { minimumWidth: 64 } }));
      const w = Math.max(...charts().map((c) => c.priceScale("right").width()));
      if (w > 0) charts().forEach((c) => c.applyOptions({ rightPriceScale: { minimumWidth: w } }));
    };
    requestAnimationFrame(() => requestAnimationFrame(samakan));
    setTimeout(samakan, 250);
  }

  // ---------- mulai (belum ada analisa) ----------
  let portoCache = null;
  async function ambilPorto(segar = false) {
    if (MANDIRI) return null;
    if (portoCache && !segar) return portoCache;
    try { portoCache = await (await fetch("/api/portofolio?bahasa=" + ATB.lang)).json(); } catch { portoCache = null; }
    return portoCache;
  }
  async function isiStart() {
    const s = $("#secStart");
    s.hidden = false;
    // Analisa terpisah dari portofolio: halaman Cek aset tidak menampilkan daftar posisi.
    s.innerHTML = `<h2>${t("Cara membaca hasil")}</h2>
      <table class="skala"><tbody>
        <tr><td class="num up">≥ +50</td><td>${t("bullish kuat")}</td></tr><tr><td class="num up">+20…+49</td><td>bullish</td></tr>
        <tr><td class="num flat">−19…+19</td><td>${t("netral")}</td></tr><tr><td class="num down">−49…−20</td><td>bearish</td></tr><tr><td class="num down">≤ −50</td><td>${t("bearish kuat")}</td></tr>
      </tbody></table>
      <p>${t("Bagian Rencana tindakan di tab Ringkasan menulis apa yang ditunggu dan apa yang dilakukan bila harga mencapai level tertentu. Arti garis di chart: tombol ? di atas chart.")}</p>`;
  }

  // ---------- portofolio / daftar pantau ----------
  // Tanpa folder portofolio (pengaturan "folder_portfolio" kosong, mis. paket untuk orang lain) tab ini menjadi
  // Daftar pantau: ticker pilihan sendiri, disimpan di pengaturan.json → tambahan_pantau.
  let modePorto = null, daftarPantau = [];
  async function cekModePorto() {
    if (MANDIRI) return null;
    try {
      const s = await (await fetch("/api/status")).json();
      modePorto = s.portofolio || "posisi"; daftarPantau = s.pantau || [];
    } catch { modePorto = modePorto || "posisi"; }
    if (modePorto !== "posisi") $("#tabPorto").textContent = t("Daftar pantau");
    if (!state.q && !$("#stateChart").hidden && daftarPantau.length) showState("start");  // tampilkan isi daftar pantau di layar awal
    return modePorto;
  }
  function polosPantau(x) { return String(x).replace(/\.JK$/, "").replace(/-USD$/, ""); }
  function editorPantauHtml() {
    return `<div class="pantau-edit"><label for="inpPantau">${t("Ticker yang dipantau")} <span class="muted">${t("pisahkan dengan koma, mis. BBCA, TLKM, NVDA, BTC")}</span></label>
      <div class="baris"><input id="inpPantau" class="field" spellcheck="false" autocapitalize="characters" value="${esc(daftarPantau.map(polosPantau).join(", "))}">
      <button type="button" class="btn primary" id="btnSimpanPantau">${t("Simpan & pindai")}</button></div>
      <p class="muted" id="pantauInfo" role="status"></p></div>`;
  }
  async function simpanPantau() {
    const btn = $("#btnSimpanPantau"), info = $("#pantauInfo");
    const daftar = $("#inpPantau").value.split(/[,;\s]+/).map((x) => x.trim()).filter(Boolean);
    btn.disabled = true; info.textContent = t("Mengecek ticker…");
    let r;
    try { r = await (await fetch("/api/pantau", { method: "POST", headers: { "X-Panel": "1", "Content-Type": "application/json" }, body: JSON.stringify({ daftar }) })).json(); }
    catch { btn.disabled = false; info.textContent = t("panel lokal tidak merespons"); return; }
    btn.disabled = false;
    daftarPantau = r.pantau || [];
    $("#inpPantau").value = daftarPantau.map(polosPantau).join(", ");
    const gagal = (r.gagal || []).length ? " " + t("Tidak ditemukan: {daftar}", { daftar: r.gagal.join(", ") }) : "";
    if (!daftarPantau.length) { info.textContent = t("Daftar pantau kosong.") + gagal; modePorto = "kosong"; portoCache = null; return; }
    modePorto = "pantau";
    info.textContent = t("Tersimpan {n} ticker.", { n: daftarPantau.length }) + gagal;  // kemajuan pindai tampil di sebelah Pindai ulang
    await pindai();
  }
  let pollPindai = null;
  async function muatPortofolio(segar = false) {
    if (MANDIRI) return;
    const el = $("#viewPorto");
    if (!el.dataset.loaded) el.innerHTML = `<div class="state" style="position:static;min-height:300px"><div><div class="spinner" aria-hidden="true"></div><p style="margin-top:14px">${t("Memuat portofolio…")}</p></div></div>`;
    try {
      if (modePorto == null || segar) await cekModePorto();
      const pantauMode = modePorto !== "posisi";
      const d = await ambilPorto(segar || !el.dataset.loaded);
      if (!d) throw new Error(t("panel lokal tidak merespons"));
      if (pantauMode) {
        const info = $("#pantauInfo") ? $("#pantauInfo").textContent : "";
        el.innerHTML = editorPantauHtml() + `<div id="portoIsi"></div>`;
        if (info) $("#pantauInfo").textContent = info;
        const isi = $("#portoIsi");
        if (d.ada && modePorto === "pantau") window.AT.renderPortofolio(isi, d.data, { mode: "panel", onOpen: (ticker) => { setTf("1d"); cari(ticker); } });
        else isi.innerHTML = `<div class="porto-head"><div><h1>${t("Daftar pantau")}</h1><div class="meta">${t("Belum ada ticker yang dipantau.")}</div></div><div class="act"><span class="muted" id="pindaiInfo" role="status"></span></div></div>
          <p class="muted">${t("Tulis ticker di atas lalu klik Simpan & pindai. Hasilnya tampil di sini: skor, sinyal, support/resistance, dan rencana tindakan tiap ticker. Daftar ini hanya untuk analisa; tidak ada data portofolio yang dibaca.")}</p>`;
        $("#btnSimpanPantau").addEventListener("click", simpanPantau);
        $("#inpPantau").addEventListener("keydown", (e) => { if (e.key === "Enter") { e.preventDefault(); simpanPantau(); } });
      } else if (!d.ada) {
        el.innerHTML = `<div class="porto-head"><div><h1>${t("Portofolio")}</h1><div class="meta">${t("Belum pernah dipindai.")}</div></div><div class="act"><span class="muted" id="pindaiInfo" role="status"></span><button type="button" class="btn primary" id="btnPindai">${icon("refresh")}${t("Pindai portofolio")}</button></div></div>
          <p class="muted">${t("Pemindaian menarik harga live semua posisi di folder portofolio (baca-saja) lalu menganalisa satu per satu, sekitar satu menit.")}</p>`;
      } else {
        window.AT.renderPortofolio(el, d.data, { mode: "panel", onOpen: (ticker) => { setTf("1d"); cari(ticker); } });
      }
      el.dataset.loaded = "1";
      const btn = el.querySelector("#btnPindai");
      if (btn) btn.addEventListener("click", pindai);
      tampilPindai(d.pindai);
    } catch (e) {
      el.innerHTML = `<div class="state" style="position:static;min-height:300px"><div>${icon("warn", "big-ico")}<h2>${t("Portofolio tidak bisa dimuat")}</h2><p>${esc(e.message)}</p><div class="act"><button type="button" class="btn" id="btnMuatUlang">${icon("refresh")}${t("Coba lagi")}</button></div></div></div>`;
      $("#btnMuatUlang").addEventListener("click", () => muatPortofolio(true));
      cobaLagi();  // dimuat ulang otomatis begitu panel menjawab
    }
  }
  let fasePindaiDimuat = false;
  function tampilPindai(p) {
    const info = $("#pindaiInfo"), btn = $("#btnPindai");
    if (!p) return;
    if (p.berjalan) {
      if (btn) btn.disabled = true;
      const teks = p.fase === "grafik" ? t("Data sudah diperbarui · membuat {n} chart…", { n: p.grafik || "" }) : t(p.fase === "analisa" ? "Menganalisa…" : "Menarik harga…");
      if (info) info.innerHTML = `<span class="spinner" aria-hidden="true" style="display:inline-block;width:14px;height:14px;vertical-align:-2px;margin-right:6px"></span>${teks}`;
      if (!pollPindai) pollPindai = setInterval(cekPindai, 1500);
    } else if (info && p.ok === false) info.innerHTML = `<span class="down">${t("Pemindaian gagal — lihat output/log.txt")}</span>`;
  }
  async function cekPindai() {
    if (MANDIRI) return;
    let p; try { p = await (await fetch("/api/pindai")).json(); } catch { return; }
    if (p.berjalan) {
      // Data & laporan sudah ditulis sebelum chart PNG dibuat: tampilkan hasilnya sekarang.
      if (p.fase === "grafik" && !fasePindaiDimuat) { fasePindaiDimuat = true; await muatPortofolio(true); }
      else tampilPindai(p);
      return;
    }
    clearInterval(pollPindai); pollPindai = null;
    const sudahTampil = fasePindaiDimuat;
    fasePindaiDimuat = false;
    if (p.ok) { toast(t("Pemindaian selesai.")); umumkan(t("Pemindaian portofolio selesai.")); }
    // Muat ulang juga bila hasil fase 1 sudah tampil: riwayat skor 30 hari baru dihitung di fase 2.
    muatPortofolio(true);
  }
  async function pindai() {
    const r = await fetch("/api/pindai", { method: "POST", headers: { "X-Panel": "1" } });
    tampilPindai(await r.json());
  }

  // ---------- jendela sempit: skor di atas chart (tanpa perlu menggulir) ----------
  if (!EMBED && window.matchMedia) {
    const sempit = window.matchMedia("(max-width: 1080px)");
    const atur = () => {
      const v = $("#secVerdict");
      if (sempit.matches) { if (v.parentElement !== $(".chartcol")) $(".chartcol").insertBefore(v, $(".panes")); v.classList.add("di-atas"); }
      else if (v.parentElement !== $("#hasil")) { $("#hasil").prepend(v); v.classList.remove("di-atas"); }
    };
    sempit.addEventListener ? sempit.addEventListener("change", atur) : sempit.addListener(atur);
    atur();
  }

  // ---------- arti garis di chart ----------
  $("#btnArti").addEventListener("click", () => {
    const p = $("#arti"), buka = p.hidden;
    p.hidden = !buka; $("#btnArti").setAttribute("aria-expanded", String(buka));
    if (buka) p.focus({ preventScroll: true });
  });
  document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#arti").hidden) { $("#arti").hidden = true; $("#btnArti").setAttribute("aria-expanded", "false"); $("#btnArti").focus(); } });
  document.addEventListener("click", (e) => { if (!$("#arti").hidden && !e.target.closest("#arti, #btnArti")) { $("#arti").hidden = true; $("#btnArti").setAttribute("aria-expanded", "false"); } });

  // ---------- ekstensi (side panel) ----------
  if (EMBED) {
    // Susunan panel samping: pencarian + Ikuti chart + status di satu baris, vonis di atas chart, tombol lapisan di bawah chart.
    const baris = document.createElement("div");
    baris.className = "baris1";
    // Layar penuh: ekstensi membuka tab ?mandiri=1 (analisa saja, tanpa data portofolio) untuk simbol & timeframe yang sedang tampil.
    const btnPenuh = $("#btnPenuh");
    baris.append($(".search"), $("#ikutiWadah"), $("#bahasaSeg"), $("#status"), btnPenuh);
    btnPenuh.hidden = false;
    btnPenuh.addEventListener("click", () => window.parent.postMessage({ type: "layar-penuh", q: state.q || $("#q").value.trim(), tf: state.tf }, "*"));
    $("#formCari").prepend(baris);
    $("#secVerdict").hidden = true;
    $(".chartcol").insertBefore($("#secVerdict"), $(".panes"));
    $(".panes").after($("#overlays"));
    const kepala = $("#viewCek");
    const ukur = () => document.documentElement.style.setProperty("--kepala", kepala.offsetHeight + "px");
    if (window.ResizeObserver) new ResizeObserver(ukur).observe(kepala);
    ukur();

    let det = null;  // deteksi terakhir dari ekstensi: { q, tf, iv, ivLabel, situs }
    // Label interval dari ekstensi berbahasa Indonesia ("1 hari"); dalam bahasa Inggris pakai label timeframe panel (1D, 4h).
    const labelIv = (x) => (ATB.en ? labelTf(x.tf) : x.ivLabel || x.iv || "");
    const segarkanDeteksi = () => {
      const el = $("#detected"), tombol = $("#btnIkuti");
      if (!det || !det.q) {
        el.hidden = false; tombol.hidden = true;
        $("#detectedText").textContent = t("Buka chart di TradingView, Stockbit, Binance, Yahoo Finance, dll. Simbolnya terbaca otomatis.");
        return;
      }
      $("#ikutiWadah").title = t("Mengikuti chart di {situs}: {q}", { situs: det.situs, q: det.q }) + (det.tf ? " · " + labelIv(det) : "");
      if ($("#ikuti").checked) { el.hidden = true; return; }
      el.hidden = false; tombol.hidden = false;
      $("#detectedText").innerHTML = `${esc(t("Chart di {situs}:", { situs: det.situs }))} <b class="mono">${esc(det.q)}</b>${det.tf ? " · " + esc(labelIv(det)) : ""}`;
    };
    const ikutiDeteksi = () => {
      if (!det || !det.q || !$("#ikuti").checked) return;
      if (det.q === state.q && (!det.tf || det.tf === state.tf) && state.data) return;
      state.q = det.q; $("#q").value = det.q;
      if (det.tf) setTf(det.tf);
      analisa();
    };
    window.addEventListener("message", (e) => {
      if (!String(e.origin).startsWith("chrome-extension://")) return;
      const m = e.data || {};
      if (m.type !== "deteksi") return;
      det = m.q ? { q: m.q, tf: m.tf || null, iv: m.iv || "", ivLabel: m.ivLabel || "", situs: m.situs || "TradingView" } : null;
      tfDariSitus = !!(det && det.tf);
      segarkanDeteksi();
      ikutiDeteksi();
    });
    $("#ikuti").addEventListener("change", (e) => {
      segarkanDeteksi();
      if (e.target.checked) { ikutiDeteksi(); window.parent.postMessage({ type: "minta-deteksi" }, "*"); }
    });
    $("#btnIkuti").addEventListener("click", () => { $("#ikuti").checked = true; $("#ikuti").dispatchEvent(new Event("change")); });
    // Berhenti mengikuti (ketik ticker sendiri / pilih timeframe sendiri) juga memunculkan baris "Ikuti lagi".
    new MutationObserver(segarkanDeteksi).observe($("#work"), { attributes: true, attributeFilter: ["aria-busy"] });
    segarkanDeteksi();
    window.parent.postMessage({ type: "siap" }, "*");
  }

  // ---------- mulai ----------
  recent();
  // ---------- bahasa (ID / EN) ----------
  // Pilihan disimpan di server (pengaturan.json) supaya panel, panel samping, kartu, dan garis di chart selalu sama.
  // Halaman ini memakai satu bahasa sejak dimuat; ganti bahasa = simpan lalu muat ulang (alamat #q=…&tf=… dipertahankan).
  function pakaiBahasa(nilai) {
    simpan.set("at.bahasa", nilai);
    if (simpan.get("at.bahasa") === nilai) return location.reload();
    const u = new URL(location.href);  // penyimpanan browser tidak tersedia: bawa pilihan lewat alamat
    u.searchParams.set("bahasa", nilai);
    location.replace(u.toString());
  }
  document.querySelectorAll("#bahasaSeg button").forEach((b) => {
    b.setAttribute("aria-pressed", String(b.dataset.bahasa === ATB.lang));
    b.addEventListener("click", async () => {
      const nilai = b.dataset.bahasa;
      if (nilai === ATB.lang) return;
      try {
        const r = await (await fetch("/api/bahasa?nilai=" + nilai, { method: "POST", headers: { "X-Panel": "1" } })).json();
        if (!r.ok) throw new Error();
      } catch { return toast(t("Bahasa tidak bisa diganti: panel lokal tidak merespons."), 6000); }
      if (EMBED) window.parent.postMessage({ type: "bahasa", nilai }, "*");  // ekstensi menyegarkan kartu & garis di tab chart
      pakaiBahasa(nilai);
    });
  });
  let cekBahasa = 0, terhubung = false, cobaUlang = 0, tungguUlang = null, pulihTerakhir = 0;
  // Panel belum menjawab (baru menyala / sempat mati): coba lagi tiap 2 detik s.d. 2 menit, lalu muat ulang
  // tampilan yang sedang dibuka begitu tersambung, supaya tidak perlu menutup dan membuka peluncur lagi.
  function cobaLagi() {
    terhubung = false;
    if (tungguUlang || cobaUlang >= 60) return;
    cobaUlang++;
    tungguUlang = setTimeout(() => { tungguUlang = null; cekStatus(); }, 2000);
  }
  function pulihkan() {
    if (!MANDIRI) cekModePorto();  // label tab Portofolio / Daftar pantau bila /api/status pertama gagal
    if (state.view === "porto") muatPortofolio(true);
    else if (state.view === "ihsg") tampil("ihsg", { riwayat: null });
    else if (state.view === "gab") tampil("gab", { riwayat: null });
    else if (state.q && !state.data) analisa();
  }
  window.ATCobaLagi = cobaLagi;
  function cekStatus() {
    const nomor = ++cekBahasa;
    return fetch("/api/status").then((r) => r.json()).then((s) => {
      const pulih = !terhubung && cobaUlang > 0 && Date.now() - pulihTerakhir > 10000;  // tidak berputar bila tampilan tetap gagal
      terhubung = true; cobaUlang = 0;
      if (pulih) { pulihTerakhir = Date.now(); pulihkan(); }
      if (nomor !== cekBahasa) return;
      // Bahasa diganti di tempat lain (panel utama / panel samping): ikut berganti.
      if ((s.bahasa === "en" || s.bahasa === "id") && s.bahasa !== ATB.lang && !new URLSearchParams(location.search).get("bahasa")) return pakaiBahasa(s.bahasa);
      if (!state.data) setStatus(s.offline ? "warn" : "live", t(s.offline ? "Mode offline (cache)" : "Terhubung"));
      hitungIhsg(s.ihsg);
      if (!EMBED && !MANDIRI) $("#tabGab").hidden = !s.gabungan && state.view !== "gab";  // hanya bila hasil Analisa Fundamental ada
    }).catch(() => { if (!state.data) setStatus("err", t("Panel lokal mati")); cobaLagi(); });
  }
  // Jumlah tanda baru Pemindai IHSG yang belum dilihat: angka di tab (panel utama) atau baris pengingat (panel samping).
  function hitungIhsg(r) {
    const n = (r && r.baru) || 0, el = $("#ihsgHitung");
    if (el) { el.hidden = !n; el.textContent = n; el.title = t("{n} tanda baru belum dilihat", { n }); }
    if (EMBED) {
      let b = $("#ihsgBanner");
      if (!n) { if (b) b.hidden = true; return; }
      if (!b) { b = document.createElement("a"); b.id = "ihsgBanner"; b.className = "ihsg-banner"; b.target = "_blank"; b.rel = "noopener"; b.href = "/#ihsg"; document.body.prepend(b); }
      b.hidden = false; b.textContent = t("{n} tanda baru di Pemindai IHSG — buka", { n });
    }
  }
  window.ATIhsgHitung = hitungIhsg;
  setInterval(() => { if (!document.hidden) cekStatus(); }, 5 * 60 * 1000);  // angka tanda baru ikut segar setelah pindai otomatis
  cekStatus();
  if (!MANDIRI) cekModePorto();  // label tab: Portofolio atau Daftar pantau
  document.addEventListener("visibilitychange", () => { if (!document.hidden) cekStatus(); });
  const h0 = new URLSearchParams(location.hash.slice(1));
  if (location.hash === "#portofolio" || location.hash === "#ihsg" || location.hash === "#gabungan" || h0.get("q") || params.get("q")) bacaUrl();
  if (!state.q) { showState("start"); isiStart(); }
  window.ATSiap = true;  // dibaca pengaman di panel.html (muat ulang otomatis bila ada skrip yang gagal dimuat)
})();
