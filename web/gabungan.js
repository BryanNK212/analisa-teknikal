/* Analisa Teknikal — tab Gabungan: teknikal (Pemindai IHSG) + fundamental (program Analisa Fundamental), per saham.
   Cek aset dan Pemindai IHSG tetap murni teknikal; Analisa Fundamental tetap murni fundamental. Data dari /api/gabungan,
   yang hanya membaca hasil pindai kedua program. Tidak memuat data portofolio. Tab ini hanya muncul bila hasil
   Analisa Fundamental ada (pengaturan.json → folder_fundamental, bawaan ~/Analisa Fundamental). */
(function (root) {
  "use strict";
  const B = root.ATB, t = B.t;
  const { esc, fp, num, pct, skorTxt, cls, icon, sevIcon, beliBadge, beliHtml, tglPendek } = root.AT;
  const G = { cache: null, el: null, onOpen: null, saring: { grup: "semua", cari: "", sektor: "" }, urut: ["grup", 1], buka: null, semua: false };
  const waktu = (iso) => { try { const d = new Date(iso); return Number.isNaN(d.getTime()) ? iso || "—" : d.toLocaleString(B.lokalTanggal, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); } catch { return iso; } };

  // ---------- teks & potongan tampilan fundamental ----------
  // Fundamental = apa yang layak dibeli, skor beli = kapan. Keduanya tidak dirata-rata; 4 kelompok seperti di Analisa Fundamental.
  const F_LABEL = { sangat_kuat: "Sangat kuat", kuat: "Kuat", cukup: "Cukup", lemah: "Lemah", buruk: "Buruk" };
  const F_KELAS = { baik_murah: "Berkualitas & murah", baik_wajar: "Berkualitas, harga wajar", baik_mahal: "Berkualitas tapi mahal", lemah_murah: "Murah tapi lemah", lemah: "Fundamental lemah", baik_tanpa_harga: "Berkualitas", lemah_tanpa_harga: "Fundamental lemah" };
  const F_VONIS = { murah: "Murah", agak_murah: "Agak murah", wajar: "Sekitar wajar", agak_mahal: "Agak mahal", mahal: "Mahal" };
  const F_GRUP = { kandidat: "Kandidat beli", pantau: "Pantau", trading: "Trading saja", lewati: "Lewati dulu", tanpa_tek: "Tanpa skor beli", tanpa_fund: "Belum dinilai fundamental" };
  const F_GRUP_KET = { kandidat: "fundamental kuat dan teknikal siap", pantau: "fundamental kuat, tunggu momen teknikal", trading: "teknikal bagus tetapi fundamental lemah: hanya untuk jangka pendek", lewati: "fundamental dan teknikal sama-sama belum mendukung", tanpa_tek: "belum ada skor beli teknikal", tanpa_fund: "tidak ada di hasil Analisa Fundamental (tidak lolos saringannya atau belum dipindai)" };
  const kelasFund = (x) => (x >= 65 ? "up" : x >= 50 ? "flat" : "down");
  const fTeks = (peta, k) => (k && peta[k] ? t(peta[k]) : "");
  const mosTxt = (m) => (m == null || !isFinite(m) ? "—" : m < -1 ? "< −100%" : pct(m * 100));
  const kelasMos = (m) => (m == null ? "faint" : m >= 0.1 ? "up" : m <= -0.1 ? "down" : "flat");
  const tglIso = (iso) => (iso ? tglPendek(String(iso).slice(0, 10)) : "—");
  function fundSel(f) {
    if (!f) return `<span class="faint" title="${esc(t(F_GRUP_KET.tanpa_fund))}">—</span>`;
    const judul = [t("Fundamental {x}/100 · {label}", { x: f.skor, label: fTeks(F_LABEL, f.label) }), fTeks(F_KELAS, f.kelas),
      f.mos != null ? t("MoS {x} ({v})", { x: mosTxt(f.mos), v: fTeks(F_VONIS, f.vonis) }) : "", ...(f.merah || [])].filter(Boolean).join(" · ");
    return `<span class="beli-b ${kelasFund(f.skor)}" title="${esc(judul)}">${f.skor}</span>${f.merah && f.merah.length ? " " + sevIcon("merah") : ""}`
      + (f.mos != null ? `<span class="delta faint" title="${esc(t("Margin of safety terhadap harga wajar (Analisa Fundamental)"))}">MoS ${mosTxt(f.mos)}</span>` : "");
  }
  function fundGrup(g) {
    return g && F_GRUP[g] ? `<span class="pill g-${g}" title="${esc(t(F_GRUP_KET[g] || ""))}">${esc(t(F_GRUP[g]))}</span>` : "";
  }
  // Kotak di Cek aset (saham IDX). f dari /api/analisa → fundamental.
  function fundKotak(f) {
    const buka = `<a class="btn small" href="${esc(f.url)}#${encodeURIComponent(f.kode)}" target="_blank" rel="noopener">${t("Buka Analisa Fundamental")} ↗</a>`;
    if (!f.ada) return `<div class="fund"><div class="beli-kepala"><span>${t("Fundamental")}</span></div><p class="note">${t("Belum dinilai di Analisa Fundamental (tidak lolos saringannya atau belum dipindai).")}</p><div class="fund-aksi">${buka}</div></div>`;
    const P4 = f.pilar || {};
    const pilar = [["valuasi", "Valuasi"], ["kualitas", "Kualitas"], ["kesehatan", "Kesehatan"], ["dividen", "Dividen"]]
      .map(([k, n]) => `<span>${t(n)} <b class="${P4[k] == null ? "faint" : kelasFund(P4[k])}">${P4[k] == null ? "—" : P4[k]}</b></span>`).join("");
    const tanda = (f.tanda || []).map((x) => `<div class="sig">${sevIcon(x.level)}<span class="t">${esc(x.teks)}</span></div>`).join("");
    const harga = f.wajar != null ? ` · ${t("harga wajar")} <b>${esc(fp(f.wajar, "idx"))}</b> · MoS <b class="${kelasMos(f.mos)}">${mosTxt(f.mos)}</b> (${esc(fTeks(F_VONIS, f.vonis))})` : "";
    const lalu = f.skor_lalu != null && f.skor_lalu !== f.skor ? ` <span class="faint" title="${esc(t("Skor di pindai fundamental hari sebelumnya"))}">(${f.skor > f.skor_lalu ? "▲" : "▼"} ${t("dari")} ${f.skor_lalu})</span>` : "";
    return `<div class="fund">
      <div class="beli-kepala"><span>${t("Fundamental")}</span><span class="beli-angka ${kelasFund(f.skor)}">${f.skor}<span class="faint">/100</span></span><span class="${kelasFund(f.skor)}">${esc(fTeks(F_LABEL, f.label))}</span>${lalu}${fundGrup(f.grup)}</div>
      <div class="beli-meter" aria-hidden="true"><span class="${kelasFund(f.skor)}" style="width:${Math.max(2, Math.min(100, f.skor))}%"></span></div>
      <div class="fund-baris">${esc(fTeks(F_KELAS, f.kelas))}${harga}</div>
      <div class="fund-pilar">${pilar}</div>
      ${tanda ? `<div class="fund-tanda">${tanda}</div>` : ""}
      <p class="note">${t("Laporan s.d. {lap} · harga {h} per {tgl} · dinilai {w}.", { lap: tglIso(f.tanggal_laporan), h: f.harga != null ? fp(f.harga, "idx") : "—", tgl: tglIso(f.harga_tanggal || f.waktu), w: esc(waktu(f.waktu)) })}
        ${t("Kelompok: fundamental ≥ {f} dan skor beli ≥ {b}.", { f: num(f.fund_min, 0), b: num(f.beli_min, 0) })}</p>
      <div class="fund-aksi">${buka}</div></div>`;
  }

  // Nama sektor dari Yahoo (lewat Analisa Fundamental) berbahasa Inggris; di mode Indonesia diterjemahkan
  // dengan kamus yang sama seperti panel Analisa Fundamental. Nilai saringan tetap nama aslinya.
  const SEKTOR_ID = { "Financial Services": "Keuangan", "Energy": "Energi", "Basic Materials": "Bahan baku", "Consumer Defensive": "Konsumer primer", "Consumer Cyclical": "Konsumer non-primer", "Industrials": "Perindustrian", "Real Estate": "Properti", "Communication Services": "Telekomunikasi & media", "Technology": "Teknologi", "Healthcare": "Kesehatan", "Utilities": "Utilitas" };
  const sektorNm = (s) => (B.en ? s : SEKTOR_ID[s] || s);
  const GRUP_URUT = { kandidat: 0, pantau: 1, trading: 2, lewati: 3, tanpa_tek: 4, tanpa_fund: 5 };
  const sbeli = (r) => (r.tek && r.tek.skor_beli ? r.tek.skor_beli.skor : null);
  function nilaiUrut(r, k) {
    if (k === "grup") return GRUP_URUT[r.grup] * 1000 - ((r.fund ? r.fund.skor : 0) + (sbeli(r) || 0)) / 2;
    if (k === "kode") return r.kode;
    if (k === "fund") return r.fund ? r.fund.skor : -1;
    if (k === "beli") return sbeli(r) ?? -1;
    if (k === "tek") return r.tek ? r.tek.skor : -1e9;
    if (k === "mos") return r.fund && r.fund.mos != null ? r.fund.mos : -1e9;
    if (k === "chg") return r.tek && r.tek.chg != null ? r.tek.chg : -1e9;
    return 0;
  }
  function saring(rows) {
    const S = G.saring, q = S.cari.trim().toUpperCase();
    return rows.filter((r) => (S.grup === "semua" || r.grup === S.grup) && (!S.sektor || (r.sektor || "") === S.sektor)
      && (!q || r.kode.includes(q) || (r.nama || "").toUpperCase().includes(q)));
  }
  function tandaSel(r) {
    const fm = r.fund ? (r.fund.tanda || []).filter((x) => x.level === "merah") : [];
    const tm = r.tek ? (r.tek.bendera || []).filter((x) => x.level === "merah" || x.level === "oranye") : [];
    const th = r.tek ? (r.tek.bendera || []).filter((x) => x.level === "hijau") : [];
    const bag = [];
    if (fm.length) bag.push(`<span title="${esc(t("Fundamental") + ": " + fm.map((x) => x.teks).join(" · "))}">${sevIcon("merah")}<span class="faint">F${fm.length}</span></span>`);
    if (tm.length) bag.push(`<span title="${esc(t("Teknikal") + ": " + tm.map((x) => x.teks).join(" · "))}">${sevIcon(tm.some((x) => x.level === "merah") ? "merah" : "oranye")}<span class="faint">T${tm.length}</span></span>`);
    if (th.length) bag.push(`<span title="${esc(t("Teknikal") + ": " + th.map((x) => x.teks).join(" · "))}">${sevIcon("hijau")}<span class="faint">T${th.length}</span></span>`);
    return bag.length ? `<span class="gab-tanda">${bag.join("")}</span>` : `<span class="faint">—</span>`;
  }
  function baris(r) {
    const tk = r.tek, f = r.fund;
    return `<tr class="row${G.buka === r.kode ? " terbuka" : ""}" data-k="${esc(r.kode)}" tabindex="0" aria-expanded="${G.buka === r.kode}">
      <td><span class="sym">${esc(r.kode)}</span>${r.nama ? `<span class="gab-nama" title="${esc(r.nama)}">${esc(r.nama.replace(/^PT\.? /i, "").replace(/ Tbk\.?$/i, ""))}</span>` : ""}</td>
      <td class="r num">${r.harga != null ? esc(fp(r.harga, "idx")) : "—"}${tk && tk.chg != null ? `<span class="delta ${tk.chg >= 0 ? "up" : "down"}">${pct(tk.chg)}</span>` : ""}</td>
      <td>${fundGrup(r.grup)}</td>
      <td class="r">${fundSel(f && { ...f, merah: (f.tanda || []).filter((x) => x.level === "merah").map((x) => x.teks) })}</td>
      <td class="gab-kelas">${f ? esc(fTeks(F_KELAS, f.kelas)) : `<span class="faint">—</span>`}</td>
      <td class="r">${tk ? beliBadge(tk.skor_beli) : `<span class="faint">—</span>`}</td>
      <td class="r">${tk ? `<span class="badge ${cls(tk.skor)}" title="${esc(tk.label || "")}">${skorTxt(tk.skor)}</span>` : `<span class="faint">—</span>`}</td>
      <td><span class="langkah1">${tk && tk.langkah ? "→ " + esc(tk.langkah) : ""}</span></td>
      <td>${tandaSel(r)}</td>
    </tr>${G.buka === r.kode ? `<tr class="gab-detail"><td colspan="9">${detail(r)}</td></tr>` : ""}`;
  }
  function detail(r) {
    const tk = r.tek;
    const kiri = tk ? `<div class="gab-kol"><h3>${t("Teknikal")} <span class="muted">· 1D</span></h3>
        <div class="beli-kepala"><span>${t("Skor teknikal")}</span><span class="badge ${cls(tk.skor)}">${skorTxt(tk.skor)}</span><span class="${cls(tk.skor)}">${esc(tk.label || "")}</span><span class="muted">${esc(tk.tren || "")}</span></div>
        ${tk.skor_beli ? `<div style="margin-top:8px">${beliHtml(tk.skor_beli)}</div>` : ""}
        ${tk.langkah ? `<p class="langkah1" style="margin-top:8px">→ ${esc(tk.langkah)}</p>` : ""}
        ${(tk.bendera || []).length ? `<div class="fund-tanda">${tk.bendera.map((x) => `<div class="sig">${sevIcon(x.level)}<span class="t">${x.baru ? `<span class="tbaru">${t("Baru")}</span>` : ""}${esc(x.teks)}</span></div>`).join("")}</div>` : ""}
        <p class="note">${[tk.s1 != null ? "S1 " + esc(fp(tk.s1, "idx")) : "", tk.r1 != null ? "R1 " + esc(fp(tk.r1, "idx")) : "", tk.rsi != null ? "RSI " + num(tk.rsi, 0) : ""].filter(Boolean).join(" · ")}</p>
        <div class="fund-aksi"><button type="button" class="btn small" data-chart="${esc(r.kode)}">${icon("chart")}${t("Buka chart di Cek aset")}</button></div></div>`
      : `<div class="gab-kol"><h3>${t("Teknikal")}</h3><p class="note">${t("Tidak ada di hasil Pemindai IHSG (tidak lolos saringan likuiditasnya). Chart-nya tetap bisa dibuka di Cek aset.")}</p>
        <div class="fund-aksi"><button type="button" class="btn small" data-chart="${esc(r.kode)}">${icon("chart")}${t("Buka chart di Cek aset")}</button></div></div>`;
    const kanan = r.fund ? `<div class="gab-kol">${fundKotak({ ...r.fund, grup: r.grup })}</div>`
      : `<div class="gab-kol"><h3>${t("Fundamental")}</h3><p class="note">${t(F_GRUP_KET.tanpa_fund)}.</p>
        <div class="fund-aksi"><a class="btn small" href="${esc(G.cache.url_fund)}#${encodeURIComponent(r.kode)}" target="_blank" rel="noopener">${t("Buka Analisa Fundamental")} ↗</a></div></div>`;
    return `<div class="gab-dua">${kiri}${kanan}</div><p class="note gab-ket">${esc(t(F_GRUP_KET[r.grup] || ""))}</p>`;
  }
  function gambarTabel() {
    const el = G.el, d = G.cache;
    const [k, dir] = G.urut;
    const rows = saring(d.baris).sort((a, b) => { const x = nilaiUrut(a, k), y = nilaiUrut(b, k); return (x > y ? 1 : x < y ? -1 : 0) * dir; });
    const batas = G.semua ? rows.length : 200;
    el.querySelectorAll("#tblGab th").forEach((th) => {
      const b = th.querySelector(".sort");
      if (b && b.dataset.k === k) th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending"); else th.removeAttribute("aria-sort");
    });
    el.querySelector("#tblGab tbody").innerHTML = rows.length ? rows.slice(0, batas).map(baris).join("") : `<tr class="empty-row"><td colspan="9">${t("Tidak ada saham untuk saringan ini.")}</td></tr>`;
    const lagi = el.querySelector("#gabLagi");
    lagi.hidden = rows.length <= batas;
    lagi.textContent = t("Tampilkan semua ({n})", { n: rows.length });
    el.querySelector("#gabJumlah").textContent = t("{n} saham", { n: rows.length });
  }
  function render() {
    const el = G.el, d = G.cache;
    if (!d || !d.ada) {
      el.innerHTML = `<div class="porto-head"><div><h1>${t("Gabungan")}</h1></div></div><p class="muted">${t("Hasil Analisa Fundamental tidak ditemukan. Tab ini menggabungkan Pemindai IHSG dengan hasil pindai program Analisa Fundamental (folder ~/Analisa Fundamental).")}</p>`;
      return;
    }
    const A = d.ambang, n = { semua: d.baris.length, kandidat: 0, pantau: 0, trading: 0, lewati: 0, tanpa_tek: 0, tanpa_fund: 0 };
    d.baris.forEach((r) => n[r.grup]++);
    const sektor = [...new Set(d.baris.map((r) => r.sektor).filter(Boolean))].sort((a, b) => sektorNm(a).localeCompare(sektorNm(b)));
    const tk = d.tek || {}, fu = d.fund || {};
    const meta = [tk.ada ? t("Teknikal: Pemindai IHSG {w} · {n} saham", { w: esc(waktu(tk.waktu)), n: tk.lolos }) : t("Pemindai IHSG belum pernah dijalankan."),
      t("Fundamental: dinilai {w}, harga per {tgl} · {n} emiten", { w: esc(waktu(fu.waktu)), tgl: esc(tglIso(fu.harga_tanggal || fu.waktu)), n: fu.n })].join(" · ");
    el.innerHTML = `<div class="porto-head"><div><h1>${t("Gabungan")}</h1><div class="meta">${meta}</div></div>
        <div class="act"><a class="btn" href="${esc(d.url_fund)}" target="_blank" rel="noopener">${t("Buka Analisa Fundamental")} ↗</a></div></div>
      ${tk.basi ? `<p class="flat ihsg-peringatan">${icon("warn")} ${t("Hasil Pemindai IHSG belum diperbarui sejak hari bursa terakhir; skor beli bisa sudah berubah. Jalankan Pindai IHSG.")}</p>` : ""}
      ${fu.harga_tanggal && tk.tanggal_bursa && fu.harga_tanggal < tk.tanggal_bursa ? `<p class="flat ihsg-peringatan">${icon("warn")} ${t("Harga fundamental masih per {f}, sedangkan Pemindai IHSG per {t}: MoS dan kelompok memakai harga lama. Buka Analisa Fundamental sekali; ia menilai ulang otomatis dengan harga terbaru tanpa internet (±3 detik).", { f: esc(tglIso(fu.harga_tanggal)), t: esc(tglIso(tk.tanggal_bursa)) })}</p>` : ""}
      <div class="filters gab-ambang">
        <span class="muted">${t("Kelompok")}:</span>
        <label>${t("Fundamental ≥")} <input type="number" id="gabFund" min="0" max="100" step="5" value="${num(A.fund_min, 0)}"></label>
        <label>${t("Skor beli ≥")} <input type="number" id="gabBeli" min="0" max="100" step="5" value="${num(A.beli_min, 0)}"></label>
        <span class="muted">${t("Fundamental = apa yang layak dibeli, skor beli = kapan; keduanya tidak dirata-rata.")}</span>
      </div>
      <div class="filters ihsg-saring gab-saring">
        <div class="chips" role="group" aria-label="${t("Kelompok fundamental + teknikal")}">${["semua", "kandidat", "pantau", "trading", "lewati", "tanpa_tek", "tanpa_fund"].filter((g) => g === "semua" || n[g])
          .map((g) => `<button type="button" class="chip sans g-${g}" data-grup="${g}" aria-pressed="${G.saring.grup === g}" ${g !== "semua" ? `title="${esc(t(F_GRUP_KET[g]))}"` : ""}>${g === "semua" ? t("Semua kelompok") : esc(t(F_GRUP[g]))} (${n[g]})</button>`).join("")}</div>
        <select id="gabSektor" class="field" aria-label="${t("Sektor")}"><option value="">${t("Semua sektor")}</option>${sektor.map((s) => `<option value="${esc(s)}"${s === G.saring.sektor ? " selected" : ""}>${esc(sektorNm(s))}</option>`).join("")}</select>
        <input type="search" id="gabCari" placeholder="${t("Cari kode atau nama")}" value="${esc(G.saring.cari)}" aria-label="${t("Cari kode atau nama")}">
        <span class="muted" id="gabJumlah"></span>
      </div>
      <div class="tblwrap"><table class="tbl" id="tblGab"><thead><tr>
        <th><button type="button" class="sort" data-k="kode">${t("Saham")}${icon("sort", "ar")}</button></th>
        <th class="r"><button type="button" class="sort" data-k="chg">${t("Harga")}${icon("sort", "ar")}</button></th>
        <th><button type="button" class="sort" data-k="grup">${t("Kelompok")}${icon("sort", "ar")}</button></th>
        <th class="r"><button type="button" class="sort" data-k="fund" title="${esc(t("Skor fundamental 0–100 dari Analisa Fundamental (sorot angka untuk rinciannya)"))}">${t("Fund")}${icon("sort", "ar")}</button></th>
        <th><button type="button" class="sort" data-k="mos">${t("Kualitas × harga")}${icon("sort", "ar")}</button></th>
        <th class="r"><button type="button" class="sort" data-k="beli">${t("Beli")}${icon("sort", "ar")}</button></th>
        <th class="r"><button type="button" class="sort" data-k="tek">${t("Teknikal")}${icon("sort", "ar")}</button></th>
        <th>${t("Langkah (1D)")}</th><th>${t("Tanda")}</th></tr></thead><tbody></tbody></table></div>
      <button type="button" class="btn small" id="gabLagi" hidden></button>
      <p class="hsisa">${t("Klik satu baris untuk melihat teknikal dan fundamental saham itu berdampingan. Teknikal dari hasil Pemindai IHSG (1D), fundamental dari hasil pindai Analisa Fundamental; tab ini tidak menarik data baru. Kandidat beli = fundamental ≥ {f} dan skor beli ≥ {b}; Pantau = fundamental kuat, teknikal belum; Trading saja = teknikal bagus, fundamental lemah; Lewati dulu = keduanya belum.", { f: num(A.fund_min, 0), b: num(A.beli_min, 0) })}
        ${t("Analisa otomatis, bukan rekomendasi investasi.")}</p>`;
    el.querySelectorAll("#tblGab .sort").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.k; G.urut = [k, G.urut[0] === k ? -G.urut[1] : k === "kode" || k === "grup" ? 1 : -1]; gambarTabel();
    }));
    // Chip kelompok: cukup tandai pilihan dan gambar ulang tabel (render penuh menghapus posisi gulir).
    el.querySelectorAll(".gab-saring .chip").forEach((b) => b.addEventListener("click", () => {
      G.saring.grup = b.dataset.grup;
      el.querySelectorAll(".gab-saring .chip").forEach((x) => x.setAttribute("aria-pressed", String(x === b)));
      gambarTabel();
    }));
    el.querySelector("#gabSektor").addEventListener("change", (e) => { G.saring.sektor = e.target.value; gambarTabel(); });
    el.querySelector("#gabCari").addEventListener("input", (e) => { G.saring.cari = e.target.value; gambarTabel(); });
    el.querySelector("#gabLagi").addEventListener("click", () => { G.semua = true; gambarTabel(); });
    ["#gabFund", "#gabBeli"].forEach((s) => el.querySelector(s).addEventListener("change", simpanAmbang));
    const tb = el.querySelector("#tblGab tbody");
    const buka = (tr) => { G.buka = G.buka === tr.dataset.k ? null : tr.dataset.k; gambarTabel(); };
    tb.addEventListener("click", (e) => {
      const c = e.target.closest("[data-chart]");
      if (c) { e.preventDefault(); if (G.onOpen) G.onOpen(c.dataset.chart + ".JK"); return; }  // .JK: tetap saham IDX walau pilihan pasar di Cek aset sedang AS (FAST = KFC Indonesia, bukan Fastenal)
      if (e.target.closest("a, button, details, summary")) return;
      const tr = e.target.closest("tr.row"); if (tr) buka(tr);
    });
    tb.addEventListener("keydown", (e) => { const tr = e.target.closest("tr.row"); if (tr && (e.key === "Enter" || e.key === " ")) { e.preventDefault(); buka(tr); } });
    gambarTabel();
  }
  async function simpanAmbang() {
    const isi = { fund_min: +G.el.querySelector("#gabFund").value, beli_min: +G.el.querySelector("#gabBeli").value };
    try {
      const r = await (await fetch("/api/gabungan/ambang", { method: "POST", headers: { "X-Panel": "1", "Content-Type": "application/json" }, body: JSON.stringify(isi) })).json();
      if (r.ok) await muat();
    } catch { /* panel tidak menjawab: biarkan angka di layar */ }
  }
  async function muat() {
    try { G.cache = await (await fetch("/api/gabungan?bahasa=" + B.lang)).json(); }
    catch { G.el.innerHTML = `<p class="down">${t("Panel lokal tidak merespons.")}</p>`; if (root.ATCobaLagi) root.ATCobaLagi(); return; }
    render();
  }
  root.ATGabungan = { tampil(el, onOpen) { G.el = el; G.onOpen = onOpen; if (!G.cache) el.innerHTML = `<div class="state" style="position:static;min-height:300px"><div><div class="spinner" aria-hidden="true"></div></div></div>`; muat(); } };
})(window);
