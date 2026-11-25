/* Analisa Teknikal — tab Pemindai IHSG: semua saham IHSG yang lolos saringan likuiditas, dengan tanda baru.
   Data dari /api/ihsg (hasil pemindai.py). Tidak memuat data portofolio. */
(function (root) {
  "use strict";
  const B = root.ATB, t = B.t;
  const { esc, fp, num, pct, skorTxt, cls, icon, sevIcon, beliBadge, tglPendek } = root.AT;
  const P = { data: null, fund: null, saring: { baru: null, arah: "semua", beli: 0, cari: "", fund: "semua" }, urut: ["baru", -1], semua: false, poll: null, onOpen: null, el: null };

  function rupiah(x) {
    if (x == null || !isFinite(x)) return "—";
    const a = Math.abs(x);
    if (B.en) return a >= 1e12 ? `IDR ${num(x / 1e12, 1)}T` : a >= 1e9 ? `IDR ${num(x / 1e9, 1)}B` : `IDR ${num(x / 1e6, 0)}M`;
    return a >= 1e12 ? `Rp${num(x / 1e12, 1)} T` : a >= 1e9 ? `Rp${num(x / 1e9, 1)} M` : `Rp${num(x / 1e6, 0)} jt`;
  }
  const waktu = (iso) => { try { const d = new Date(iso); return Number.isNaN(d.getTime()) ? iso : d.toLocaleString(B.lokalTanggal, { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" }); } catch { return iso; } };
  const ARAH = (f) => (f.level === "hijau" ? 1 : f.level === "merah" || f.level === "oranye" ? -1 : 0);
  const TAG = { volatil: ["Volatil", "ATR ≥ 8% harga: gerakan harian besar, risiko tinggi"], baru_lolos: ["Baru lolos", "Baru masuk saringan likuiditas dibanding pindai sebelumnya"] };

  // ---------- Analisa Fundamental (program terpisah, hanya dibaca bila ada; bukan data portofolio) ----------
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
        ${t("Kelompok: fundamental ≥ {f} dan skor beli ≥ {b}. Fundamental = apa yang layak dibeli, skor beli = kapan; keduanya tidak dirata-rata.", { f: num(f.fund_min, 0), b: num(f.beli_min, 0) })}</p>
      <div class="fund-aksi">${buka}</div></div>`;
  }
  root.ATFund = { kotak: fundKotak };

  function nilaiUrut(a, k) {
    if (k === "baru") return a.baru_n * 1000 + (a.skor_beli ? a.skor_beli.skor : 0);
    if (k === "beli") return a.skor_beli ? a.skor_beli.skor : -1;
    if (k === "kode") return a.kode;
    if (k === "fund") return a.fund ? a.fund.skor : -1;
    return a[k] == null ? -1e18 : a[k];
  }

  function baris(a) {
    const fl = a.bendera || [];
    const baru = fl.filter((f) => f.baru && f.level !== "info");
    let tampil = (baru.length ? baru : fl.filter((f) => f.level !== "info")).slice(0, 2);
    if (!tampil.length) tampil = fl.slice(0, 1);  // hanya tanda info (mis. dekat support): tampilkan satu, redup
    const sisa = fl.length - tampil.length;
    const tag = (a.tag || []).filter((x) => TAG[x]).map((x) => `<span class="tag-ihsg ${x}" title="${esc(t(TAG[x][1]))}">${esc(t(TAG[x][0]))}</span>`).join("");
    return `<tr class="row" data-k="${esc(a.kode)}" tabindex="0">
      <td><span class="sym">${esc(a.kode)}</span>${tag}</td>
      <td class="r num">${esc(fp(a.harga, "idx"))}<span class="delta ${a.chg >= 0 ? "up" : "down"}">${pct(a.chg)}</span></td>
      <td class="r num">${rupiah(a.nilai)}<span class="delta faint" title="${t("Rata-rata nilai transaksi 20 hari")}">${t("rata²")} ${rupiah(a.nilai20)}</span></td>
      ${P.data.sumber_idx && P.data.sumber_idx.ringkasan ? `<td class="r num">${a.frek != null ? num(a.frek, 0) + "×" : "—"}${a.spread != null ? `<span class="delta faint" title="${t("Selisih bid–offer penutupan")}">spread ${num(a.spread, 1)}%</span>` : ""}</td>` : ""}
      <td class="r"><span class="badge ${cls(a.skor)}">${skorTxt(a.skor)}</span></td>
      <td class="r">${beliBadge(a.skor_beli)}</td>
      ${P.fund ? `<td class="r">${fundSel(a.fund)}</td>` : ""}
      <td>${tampil.length ? tampil.map((f) => `<div class="sig${f.baru ? "" : " lama"}">${sevIcon(f.level)}<span class="t" title="${esc(f.teks)}">${f.baru ? `<span class="tbaru">${t("Baru")}</span>` : ""}${esc(f.teks)}</span></div>`).join("") : `<div class="sig lama"><span class="t faint">${t("Tidak ada tanda")}</span></div>`}${sisa > 0 ? `<span class="lagi" title="${esc(fl.filter((f) => !tampil.includes(f)).map((f) => f.teks).join("\n"))}">+${sisa}</span>` : ""}</td>
      <td><span class="langkah1">${a.langkah ? "→ " + esc(a.langkah) : ""}</span></td>
    </tr>`;
  }

  function saring(aset) {
    const S = P.saring, q = S.cari.trim().toUpperCase();
    return aset.filter((a) => {
      if (q && !a.kode.includes(q)) return false;
      if (S.baru && !a.baru_n) return false;
      if (S.beli && !(a.skor_beli && a.skor_beli.skor >= S.beli)) return false;
      if (P.fund && S.fund !== "semua" && (a.fund ? a.fund.grup : "tanpa_fund") !== S.fund) return false;
      if (S.arah !== "semua") {
        const f = (a.bendera || []).filter((x) => (S.baru ? x.baru : true));
        if (!f.some((x) => ARAH(x) === (S.arah === "naik" ? 1 : -1))) return false;
      }
      return true;
    });
  }

  function gambarTabel() {
    const el = P.el, d = P.data;
    const [k, dir] = P.urut;
    const rows = saring(d.aset || []).sort((a, b) => { const x = nilaiUrut(a, k), y = nilaiUrut(b, k); return (x > y ? 1 : x < y ? -1 : 0) * dir; });
    const batas = P.semua ? rows.length : 150;
    el.querySelectorAll("#tblIhsg th").forEach((th) => {
      const b = th.querySelector(".sort");
      if (b && b.dataset.k === k) th.setAttribute("aria-sort", dir > 0 ? "ascending" : "descending"); else th.removeAttribute("aria-sort");
    });
    const tb = el.querySelector("#tblIhsg tbody");
    tb.innerHTML = rows.length ? rows.slice(0, batas).map(baris).join("") : `<tr class="empty-row"><td colspan="${el.querySelectorAll("#tblIhsg thead th").length}">${t("Tidak ada saham untuk saringan ini.")}</td></tr>`;
    const lagi = el.querySelector("#ihsgLagi");
    lagi.hidden = rows.length <= batas;
    lagi.textContent = t("Tampilkan semua ({n})", { n: rows.length });
    el.querySelector("#ihsgJumlah").textContent = t("{n} saham", { n: rows.length });
  }

  function infoHtml(st) {
    const jalan = st && st.berjalan;
    const fase = jalan ? ({ daftar: "menyiapkan daftar", harga: "menarik harga", saring: "menyaring", analisa: "menganalisa", mulai: "memulai" }[st.fase] || "berjalan") : "";
    const prog = jalan && st.jumlah ? ` ${num(st.selesai_n || 0, 0)}/${num(st.jumlah, 0)}` : "";
    return jalan ? `<span class="spinner" aria-hidden="true" style="display:inline-block;width:14px;height:14px;vertical-align:-2px;margin-right:6px"></span>${esc(t("Memindai: {fase}", { fase: t(fase) }))}${prog}`
      : st && st.ok === false && st.pesan ? `<span class="down">${esc(t("Pindai gagal"))}: ${esc(st.pesan)}</span>` : "";
  }
  function kepala(d, st) {
    const jalan = st && st.berjalan;
    const meta = d ? t("Data {tgl} · dipindai {w} · {lolos} dari {total} saham lolos saringan", { tgl: esc(tglPendek(d.tanggal_bursa)), w: esc(waktu(d.waktu)), lolos: d.lolos, total: d.daftar_total })
      + (d.tanggal_dasar ? " · " + t("{n} tanda baru dibanding {tgl}", { n: d.baru_total, tgl: esc(tglPendek(d.tanggal_dasar)) }) : " · " + t("tanda baru mulai dihitung pada pindai hari bursa berikutnya"))
      : t("Belum pernah dipindai.");
    return `<div class="porto-head"><div><h1>${t("Pemindai IHSG")}</h1><div class="meta">${meta}</div></div>
      <div class="act"><span class="muted" id="ihsgInfo" role="status">${infoHtml(st)}</span>
      <button type="button" class="btn primary" id="btnIhsg" ${jalan ? "disabled" : ""}>${icon("refresh")}${t("Pindai IHSG")}</button></div></div>`;
  }

  function render() {
    const el = P.el, j = P.cache || {}, d = j.data, st = j.status;
    P.data = d;
    P.fund = j.fund || null;
    if (!d) {
      el.innerHTML = kepala(null, st) + `<div class="state" style="position:static;min-height:240px"><div><p>${t("Klik Pindai IHSG untuk memindai semua saham IHSG. Pindai pertama menarik riwayat harga ±900 saham (beberapa menit); sesudahnya jauh lebih cepat.")}</p></div></div>`;
      pasangTombol();
      return;
    }
    if (P.saring.baru == null) P.saring.baru = d.baru_total > 0;
    const S = d.saringan || {};
    const ket = [S.nilai_rata20_min ? t("nilai transaksi rata-rata 20 hari ≥ {x}", { x: rupiah(S.nilai_rata20_min) }) : "", S.nilai_hari_ini_min ? t("hari ini ≥ {x}", { x: rupiah(S.nilai_hari_ini_min) }) : "",
      S.harga_min ? t("harga ≥ Rp{x}", { x: num(S.harga_min, 0) }) : "", S.hari_aktif_min ? t("aktif ≥ {x} dari 20 hari", { x: S.hari_aktif_min }) : "",
      S.frekuensi_min ? t("frekuensi ≥ {x}×", { x: S.frekuensi_min }) : "", S.spread_maks_pct ? t("spread ≤ {x}%", { x: S.spread_maks_pct }) : ""].filter(Boolean).join(" · ");
    const tolak = Object.entries(d.ditolak_alasan || {}).map(([a, n]) => `${esc(t(a))} ${n}`).join(" · ");
    const idx = d.sumber_idx || {};
    const kolomFrek = idx.ringkasan ? `<th class="r"><button type="button" class="sort" data-k="frek">${t("Frek")}${icon("sort", "ar")}</button></th>` : "";
    el.innerHTML = kepala(d, st) + (d.peringatan ? `<p class="down ihsg-peringatan">${icon("alert")} ${esc(t(d.peringatan))}</p>` : "") + `
      <div class="filters ihsg-saring">
        <div class="chips" role="group" aria-label="${t("Saringan")}">
          <button type="button" class="chip sans" data-s="baru" aria-pressed="${!!P.saring.baru}">${t("Hanya tanda baru")}${d.baru_total ? ` (${d.baru_total})` : ""}</button>
          <button type="button" class="chip sans" data-arah="semua" aria-pressed="${P.saring.arah === "semua"}">${t("Semua arah")}</button>
          <button type="button" class="chip sans" data-arah="naik" aria-pressed="${P.saring.arah === "naik"}">${t("Bullish")}</button>
          <button type="button" class="chip sans" data-arah="turun" aria-pressed="${P.saring.arah === "turun"}">${t("Bearish")}</button>
          ${[0, 40, 70, 80].map((x) => `<button type="button" class="chip sans" data-beli="${x}" aria-pressed="${P.saring.beli === x}">${x ? t("Skor beli ≥ {x}", { x }) : t("Semua skor beli")}</button>`).join("")}
        </div>
        ${P.fund ? (() => {
          const n = { semua: 0, kandidat: 0, pantau: 0, trading: 0, lewati: 0, tanpa_tek: 0, tanpa_fund: 0 };
          (d.aset || []).forEach((a) => { n.semua++; n[a.fund ? a.fund.grup : "tanpa_fund"]++; });
          return `<div class="chips fund-chips" role="group" aria-label="${t("Kelompok fundamental + teknikal")}">${["semua", "kandidat", "pantau", "trading", "lewati", "tanpa_tek", "tanpa_fund"].filter((g) => g === "semua" || n[g])
            .map((g) => `<button type="button" class="chip sans g-${g}" data-fund="${g}" aria-pressed="${P.saring.fund === g}" ${g !== "semua" ? `title="${esc(t(F_GRUP_KET[g]))}"` : ""}>${g === "semua" ? t("Semua kelompok") : esc(t(F_GRUP[g]))} (${n[g]})</button>`).join("")}</div>`;
        })() : ""}
        <input type="search" id="ihsgCari" placeholder="${t("Cari kode, mis. BBRI")}" value="${esc(P.saring.cari)}" aria-label="${t("Cari kode saham")}">
        <span class="muted" id="ihsgJumlah"></span>
      </div>
      <div class="tblwrap"><table class="tbl" id="tblIhsg"><thead><tr>
        <th><button type="button" class="sort" data-k="kode">${t("Saham")}${icon("sort", "ar")}</button></th>
        <th class="r"><button type="button" class="sort" data-k="chg">${t("Harga")}${icon("sort", "ar")}</button></th>
        <th class="r"><button type="button" class="sort" data-k="nilai">${t("Nilai transaksi")}${icon("sort", "ar")}</button></th>
        ${kolomFrek}
        <th class="r"><button type="button" class="sort" data-k="skor">${t("Skor")}${icon("sort", "ar")}</button></th>
        <th class="r"><button type="button" class="sort" data-k="beli">${t("Beli")}${icon("sort", "ar")}</button></th>
        ${P.fund ? `<th class="r"><button type="button" class="sort" data-k="fund" title="${esc(t("Skor fundamental 0–100 dari Analisa Fundamental (sorot angka untuk rinciannya)"))}">${t("Fund")}${icon("sort", "ar")}</button></th>` : ""}
        <th><button type="button" class="sort" data-k="baru">${t("Tanda")}${icon("sort", "ar")}</button></th>
        <th>${t("Langkah (1D)")}</th></tr></thead><tbody></tbody></table></div>
      <button type="button" class="btn small" id="ihsgLagi" hidden></button>
      <p class="hsisa">${t("Saringan")}: ${ket}${S.kecuali_papan && S.kecuali_papan.length && idx.daftar ? " · " + t("tanpa papan {p}", { p: esc(S.kecuali_papan.join(", ")) }) : ""}. ${tolak ? t("Tidak lolos") + ": " + tolak + "." : ""}
        ${idx.ringkasan ? "" : t("Frekuensi dan bid/offer dari IDX tidak bisa diambil saat ini, jadi saringan itu dilewati.")}
        ${j.otomatis ? t("Pindai otomatis sekali tiap hari bursa setelah {jam} WIB selama panel menyala.", { jam: esc(j.jam) }) : t("Pindai otomatis mati (pengaturan.json → ihsg_otomatis).")}
        ${P.fund ? t("Fundamental dari Analisa Fundamental, dinilai {w}. Kelompok: fundamental ≥ {f} dan skor beli ≥ {b} (ambang dari pengaturan Analisa Fundamental).", { w: esc(waktu(P.fund.waktu)), f: num(P.fund.fund_min, 0), b: num(P.fund.beli_min, 0) }) : ""}
        ${t("Analisa teknikal otomatis, bukan rekomendasi; saham likuiditas rendah tetap berisiko (spread lebar, mudah digerakkan).")}</p>`;
    el.querySelectorAll("#tblIhsg .sort").forEach((b) => b.addEventListener("click", () => {
      const k = b.dataset.k; P.urut = [k, P.urut[0] === k ? -P.urut[1] : k === "kode" ? 1 : -1]; gambarTabel();
    }));
    el.querySelectorAll(".ihsg-saring .chip").forEach((b) => b.addEventListener("click", () => {
      if (b.dataset.s) P.saring.baru = !P.saring.baru;
      if (b.dataset.arah) P.saring.arah = b.dataset.arah;
      if (b.dataset.beli != null) P.saring.beli = +b.dataset.beli;
      if (b.dataset.fund) { P.saring.fund = b.dataset.fund; if (b.dataset.fund !== "semua") P.saring.baru = false; }  // kelompok: tampilkan semua anggotanya
      render();
    }));
    el.querySelector("#ihsgCari").addEventListener("input", (e) => { P.saring.cari = e.target.value; gambarTabel(); });
    el.querySelector("#ihsgLagi").addEventListener("click", () => { P.semua = true; gambarTabel(); });
    const tb = el.querySelector("#tblIhsg tbody");
    const buka = (tr) => { if (tr && P.onOpen) P.onOpen(tr.dataset.k + ".JK"); };
    tb.addEventListener("click", (e) => buka(e.target.closest("tr.row")));
    tb.addEventListener("keydown", (e) => { if ((e.key === "Enter" || e.key === " ") && e.target.matches("tr.row")) { e.preventDefault(); buka(e.target); } });
    pasangTombol();
    gambarTabel();
  }

  function pasangTombol() {
    const b = P.el.querySelector("#btnIhsg");
    if (b) b.addEventListener("click", async () => {
      b.disabled = true;
      try { await fetch("/api/ihsg/pindai", { method: "POST", headers: { "X-Panel": "1" } }); } catch { /* panel mati */ }
      mulaiPoll(true);
    });
  }

  function mulaiPoll(segera) {
    if (P.poll) return;
    const cek = async () => {
      let j; try { j = await (await fetch("/api/ihsg?status=1")).json(); } catch { return; }
      if (j.status && j.status.berjalan) {
        P.cache = { ...(P.cache || {}), status: j.status };
        const info = P.el.querySelector("#ihsgInfo"), b = P.el.querySelector("#btnIhsg");
        if (info) info.innerHTML = infoHtml(j.status);
        if (b) b.disabled = true;
        return;
      }
      clearInterval(P.poll); P.poll = null;
      await muat(true);
    };
    P.poll = setInterval(cek, 2000);
    if (segera) cek();
  }

  async function muat(paksa) {
    try { P.cache = await (await fetch("/api/ihsg?bahasa=" + B.lang)).json(); } catch { P.el.innerHTML = `<p class="down">${t("Panel lokal tidak merespons.")}</p>`; if (root.ATCobaLagi) root.ATCobaLagi(); return; }
    render();
    if (P.cache.status && P.cache.status.berjalan) mulaiPoll(false);
    // tanda baru sudah dilihat: badge ekstensi dan angka di tab kembali kosong
    if (P.cache.data) fetch("/api/ihsg/dilihat", { method: "POST", headers: { "X-Panel": "1" } }).then((r) => r.json()).then((r) => { if (root.ATIhsgHitung) root.ATIhsgHitung(r.ringkas); }).catch(() => {});
    return paksa;
  }

  root.ATIhsg = { tampil(el, onOpen) { P.el = el; P.onOpen = onOpen; if (!P.cache) el.innerHTML = `<div class="state" style="position:static;min-height:300px"><div><div class="spinner" aria-hidden="true"></div></div></div>`; muat(); } };
})(window);
