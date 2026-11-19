/* Analisa Teknikal — penggambar garis analisa di atas chart: support/resistance, rencana, trendline, pola.
   Berkas ini dipakai di dua tempat dan isinya HARUS sama persis:
     web/lapisan.js       chart di panel (Cek aset dan panel samping)
     ekstensi/lapisan.js  lapisan di atas chart TradingView
   Data yang digambar = kolom "lapisan" dari /api/analisa (hanya dari data harga, tanpa data portofolio).

   ATLapisan.gambar(ctx, L, geo, opsi) -> { sumbu: [{ y, harga, teks, warna, pri }] }  (harga tiap garis mendatar, untuk label di sumbu harga)
   ATLapisan.gambarSumbu(ctx, daftar, { w, h, huruf, hindariY, format, latar })       (menggambar label itu di kanvas sumbu harga;
                                                                                         format(harga) = format angka sumbu chart itu;
                                                                                         latar = warna penutup angka sumbu di balik label)
     ctx   konteks kanvas 2D, satuan piksel CSS
     L     data lapisan dari server
     geo   { w, h, y(harga) -> piksel | null, x(indeksBar) -> piksel | null, gelap: bool }
     opsi  { sr, rencana, tl, pola: bool, nSr: 1..3, keterangan: teks, huruf: keluarga huruf,
             hargaWajib: bool — label selalu memuat harga (dipakai bila harga garis tidak ditulis di sumbu harga) }

   Di chart cukup nama garisnya ("S1", "Batal"); harganya ditulis di sumbu harga lewat gambarSumbu. Bila sumbu tidak
   bisa dipakai (hargaWajib), label memuat harganya juga. Label ditaruh di ruang kosong di kanan bar terakhir; bila tidak
   muat, pindah ke tepi kiri supaya candle terbaru tidak tertutup tulisan.
   ctx boleh null: tidak ada yang digambar, hanya daftar label sumbu yang dikembalikan. */
(function (root) {
  "use strict";

  // Garis memakai warna yang sama di chart gelap dan terang; teks label disesuaikan supaya tetap terbaca (≥ 4.5:1).
  const TEMA = {
    gelap: { naik: "#26a69a", turun: "#ef5350", batal: "#e0a64b", aksen: "#6ea8fe", netral: "#bcbcc2",
             tNaik: "#2db8aa", tTurun: "#f26a67", tBatal: "#e0a64b", tAksen: "#8ab9ff", tNetral: "#e4e4e7", tRedup: "#bcbcc2",
             halo: "rgba(11,11,12,.88)", zona: "rgba(110,168,254,.10)" },
    terang: { naik: "#26a69a", turun: "#ef5350", batal: "#b7791f", aksen: "#2962ff", netral: "#64748b",
              tNaik: "#0f766e", tTurun: "#c62828", tBatal: "#8a5a00", tAksen: "#1d4ed8", tNetral: "#334155", tRedup: "#475569",
              halo: "rgba(255,255,255,.9)", zona: "rgba(41,98,255,.08)" },
  };
  const GAYA = { tegas: [], putus: [5, 4], titik: [2, 3], pemicu: [7, 3] };
  // Latar label di sumbu harga: cukup gelap supaya teks putih ≥ 4.5:1.
  const SUMBU = { naik: "#1f7a71", turun: "#c2403d", batal: "#946b1f", aksen: "#2f62c9", netral: "#475569" };

  // Konteks "bisu" untuk menghitung tanpa menggambar.
  const BISU = new Proxy({}, { get: (_t, k) => (k === "measureText" ? () => ({ width: 0 }) : () => {}), set: () => true });

  function gambar(ctx, L, geo, opsi) {
    const sumbu = [];
    if (!L || !geo || !(geo.w > 0) || !(geo.h > 0)) return { sumbu };
    if (!ctx) ctx = BISU;
    const o = Object.assign({ sr: true, rencana: true, tl: true, pola: true, nSr: 3, keterangan: "", hargaWajib: false,
      huruf: 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif' }, opsi || {});
    const T = geo.gelap ? TEMA.gelap : TEMA.terang;
    const w = geo.w, h = geo.h;
    const angka = (v) => (v == null || !isFinite(v) ? null : v);
    const Y = (p) => (p == null ? null : angka(geo.y(p)));
    const X = (i) => (i == null ? null : angka(geo.x(i)));
    const hurufLabel = `600 11px ${o.huruf}`;

    ctx.save();
    ctx.lineJoin = "round";
    ctx.lineCap = "butt";
    ctx.textBaseline = "middle";

    const garis = (titik, warna, gaya, tebal, alfa) => {
      const p = titik.filter((q) => q[0] != null && q[1] != null);
      if (p.length < 2) return;
      ctx.save();
      ctx.globalAlpha = alfa == null ? 1 : alfa;
      ctx.strokeStyle = warna;
      ctx.lineWidth = tebal || 1;
      ctx.setLineDash(GAYA[gaya] || []);
      ctx.beginPath();
      p.forEach((q, i) => (i ? ctx.lineTo(q[0], q[1]) : ctx.moveTo(q[0], q[1])));
      ctx.stroke();
      ctx.restore();
    };
    const tulis = (s, x, y, warna, rata, huruf) => {
      ctx.font = huruf || hurufLabel;
      ctx.textAlign = rata || "right";
      ctx.lineWidth = 3.5;
      ctx.strokeStyle = T.halo;
      ctx.setLineDash([]);
      ctx.strokeText(s, x, y);
      ctx.fillStyle = warna;
      ctx.fillText(s, x, y);
    };

    // ---------- 1. area masuk (rencana beli) ----------
    const label = [];  // { y, nama, teks, warna } — ditulis tepat di atas garisnya
    const zona = o.rencana && L.rencana && L.rencana.zona;
    if (zona) {
      const a = Y(zona.ke), b = Y(zona.dari);
      if (a != null && b != null && Math.max(a, b) > 0 && Math.min(a, b) < h) {
        const atas = Math.min(a, b), tinggi = Math.max(2, Math.abs(b - a));
        ctx.fillStyle = T.zona;
        ctx.fillRect(0, atas, w, tinggi);
        garis([[0, atas], [w, atas]], T.aksen, "tegas", 1, 0.55);
        garis([[0, atas + tinggi], [w, atas + tinggi]], T.aksen, "tegas", 1, 0.55);
        label.push({ y: atas, nama: zona.k, teks: zona.teks, warna: T.tAksen });
        sumbu.push({ y: Y(zona.ke), harga: zona.ke, teks: zona.teks_ke || "", warna: SUMBU.aksen, pri: 3 },
          { y: Y(zona.dari), harga: zona.dari, teks: zona.teks_dari || "", warna: SUMBU.aksen, pri: 3 });
      }
    }

    // ---------- 2. pola chart ----------
    if (o.pola) (L.pola || []).forEach((p) => {
      const warna = p.bias > 0 ? T.naik : p.bias < 0 ? T.turun : T.netral;
      (p.segmen || []).forEach((s) => garis(s.titik.map(([i, v]) => [X(i), Y(v)]), warna, s.gaya, s.tebal, 0.95));
    });

    // ---------- 3. trendline ----------
    if (o.tl) (L.tl || []).forEach((t) => {
      garis([[X(t.i1), Y(t.p1)], [X(t.i2), Y(t.p2)]], T.aksen, t.putus ? "putus" : "tegas", 1.5, t.putus ? 0.7 : 1);
    });

    // ---------- 4. garis mendatar: level, rencana, target pola ----------
    const datar = [];  // { y, warna, tWarna, gaya, tebal, nama, teks, pri }
    const tambah = (harga, d) => { const y = Y(harga); if (y != null && y >= -1 && y <= h + 1) datar.push(Object.assign({ y, harga }, d)); };
    if (o.sr) (L.level || []).forEach((v) => {
      if (+String(v.k).slice(1) > o.nSr) return;
      const s = v.jenis === "s";
      tambah(v.harga, { warna: s ? T.naik : T.turun, tWarna: s ? T.tNaik : T.tTurun, sWarna: s ? SUMBU.naik : SUMBU.turun, gaya: "putus", tebal: 1, nama: v.k, teks: v.teks,
        pri: v.k === "S1" || v.k === "R1" ? 2 : 1 });
    });
    if (o.rencana && L.rencana) (L.rencana.garis || []).forEach((v) => {
      const d = { batal: { warna: T.batal, tWarna: T.tBatal, sWarna: SUMBU.batal, gaya: "tegas", tebal: 1.5, pri: 5 },
                  target: { warna: T.naik, tWarna: T.tNaik, sWarna: SUMBU.naik, gaya: "titik", tebal: 1.5, pri: 4 },
                  naik: { warna: T.naik, tWarna: T.tNaik, sWarna: SUMBU.naik, gaya: "pemicu", tebal: 1.5, pri: 4 },
                  turun: { warna: T.turun, tWarna: T.tTurun, sWarna: SUMBU.turun, gaya: "pemicu", tebal: 1.5, pri: 4 },
                  s: { warna: T.naik, tWarna: T.tNaik, sWarna: SUMBU.naik, gaya: "putus", tebal: 1, pri: 1 } }[v.jenis];
      if (d) tambah(v.harga, Object.assign({ nama: v.k, teks: v.teks }, d));
    });
    if (o.pola) (L.pola || []).forEach((p) => {
      if (p.target == null) return;
      const naik = p.bias > 0, turun = p.bias < 0;
      tambah(p.target, { warna: naik ? T.naik : turun ? T.turun : T.netral, tWarna: naik ? T.tNaik : turun ? T.tTurun : T.tNetral,
        sWarna: naik ? SUMBU.naik : turun ? SUMBU.turun : SUMBU.netral, gaya: "titik", tebal: 1, nama: (L.teks && L.teks.target_pola) || "Target pola", teks: p.target_teks, pri: 3 });
    });
    // Garis yang berimpit digabung jadi satu garis dengan nama gabungan (mis. "R1 · Target 1").
    datar.sort((a, b) => a.y - b.y || a.pri - b.pri);
    const gabung = [];
    datar.forEach((d) => {
      const g = gabung[gabung.length - 1];
      if (g && Math.abs(d.y - g.y) < 2.5) {
        if (!g.nama.includes(d.nama)) g.nama.push(d.nama);
        if (d.pri > g.pri) Object.assign(g, { y: d.y, harga: d.harga, warna: d.warna, tWarna: d.tWarna, sWarna: d.sWarna, gaya: d.gaya, tebal: d.tebal, teks: d.teks, pri: d.pri });
      } else gabung.push(Object.assign({}, d, { nama: [d.nama] }));
    });
    gabung.forEach((g) => {
      garis([[0, g.y], [w, g.y]], g.warna, g.gaya, g.tebal, 0.9);
      label.push({ y: g.y, nama: g.nama.join(" · "), teks: g.teks, warna: g.tWarna });
      sumbu.push({ y: g.y, harga: g.harga, teks: g.teks, warna: g.sWarna, pri: g.pri });
    });

    // ---------- 5. label garis ----------
    const TINGGI = 13;
    const kotak = [];  // tempat yang sudah terisi tulisan: { x0, x1, y0, y1 }
    const tabrak = (k) => kotak.some((u) => k.x0 < u.x1 + 4 && k.x1 > u.x0 - 4 && k.y0 < u.y1 && k.y1 > u.y0);
    const lebarTeks = (s, huruf) => { ctx.font = huruf || hurufLabel; return ctx.measureText(s).width; };
    if (o.keterangan) {
      const hk = `500 10.5px ${o.huruf}`, lk = lebarTeks(o.keterangan, hk);
      tulis(o.keterangan, w - 6, 10, T.tRedup, "right", hk);
      kotak.push({ x0: w - 6 - lk, x1: w - 6, y0: 3, y1: 17 });
    }
    const penuh = (l) => `${l.nama}  ${l.teks}`;
    const xAkhir = X(L.n - 1);
    const ruang = xAkhir == null ? -1 : w - xAkhir - 12;  // ruang kosong di kanan bar terakhir
    label.sort((a, b) => a.y - b.y).forEach((l) => {
      const s = o.hargaWajib ? penuh(l) : l.nama, lw = lebarTeks(s);
      // Urutan tempat: kanan (ruang kosong setelah bar terakhir) di atas/bawah garis, lalu tepi kiri di atas/bawah garis.
      const muat = (x0, yy) => yy > TINGGI / 2 + 1 && yy < h - TINGGI / 2 - 1 && !tabrak({ x0, x1: x0 + lw, y0: yy - TINGGI / 2, y1: yy + TINGGI / 2 });
      const sisi = lw > ruang ? [true] : [false, true];
      let kiri = null, y = null;
      for (const k of sisi) {
        const x0 = k ? 6 : w - 6 - lw;
        y = [l.y - 8, l.y + 9].find((yy) => muat(x0, yy));
        if (y != null) { kiri = k; break; }
      }
      if (y == null) return;  // tidak ada tempat: garisnya tetap tampil, labelnya dilewati
      const x0 = kiri ? 6 : w - 6 - lw;
      kotak.push({ x0, x1: x0 + lw, y0: y - TINGGI / 2, y1: y + TINGGI / 2 });
      tulis(s, kiri ? 6 : w - 6, y, l.warna, kiri ? "left" : "right");
    });

    // ---------- 6. nama pola ----------
    if (o.pola) (L.pola || []).forEach((p) => {
      const x = X(p.i_label), y = Y(p.p_label);
      if (x == null || y == null || !p.nama) return;
      const lw = lebarTeks(p.nama);
      if (x < -lw || x > w + lw) return;
      const xx = Math.max(6 + lw / 2, Math.min(w - 6 - lw / 2, x));
      const atas = p.bias < 0;
      const yy = [14, 28, 42].map((d) => Math.max(10, Math.min(h - 10, y + (atas ? -d : d + 1))))
        .find((v) => !tabrak({ x0: xx - lw / 2, x1: xx + lw / 2, y0: v - TINGGI / 2, y1: v + TINGGI / 2 }));
      if (yy == null) return;
      kotak.push({ x0: xx - lw / 2, x1: xx + lw / 2, y0: yy - TINGGI / 2, y1: yy + TINGGI / 2 });
      tulis(p.nama, xx, yy, p.bias > 0 ? T.tNaik : p.bias < 0 ? T.tTurun : T.tNetral, "center");
    });

    ctx.restore();
    return { sumbu };
  }

  // Label harga di sumbu harga (kotak berwarna, teks putih), seperti label garis bawaan chart.
  // Yang berprioritas tinggi digambar dulu. Label yang akan menimpa label lain atau harga terakhir digeser paling
  // jauh satu tinggi label; bila tetap tidak ada tempat, dilewati (garis dan namanya tetap ada di chart).
  function gambarSumbu(ctx, daftar, geo) {
    if (!ctx || !daftar || !geo || !(geo.w > 0) || !(geo.h > 0)) return;
    const T = 17, terpakai = geo.hindariY == null || !isFinite(geo.hindariY) ? [] : [geo.hindariY];
    const bebas = (y) => y > T / 2 && y < geo.h - T / 2 && !terpakai.some((u) => Math.abs(u - y) < T);
    ctx.save();
    ctx.font = `500 11.5px ${geo.huruf || 'system-ui, -apple-system, "Segoe UI", Roboto, sans-serif'}`;
    ctx.textBaseline = "middle";
    ctx.textAlign = "left";
    const jadi = [];
    daftar.filter((d) => d && d.teks && d.y != null && isFinite(d.y) && d.y > T / 2 && d.y < geo.h - T / 2)
      .sort((a, b) => b.pri - a.pri)
      .forEach((d) => {
        if (geo.hindariY != null && Math.abs(d.y - geo.hindariY) < 1.5) return;  // sama dengan harga terakhir: labelnya sudah ada
        let y = bebas(d.y) ? d.y : null;
        for (let g = 1; g <= T && y == null; g++) { const c = [d.y - g, d.y + g].find(bebas); if (c != null) y = c; }
        if (y == null) return;
        terpakai.push(y);
        jadi.push({ d, y });
      });
    if (geo.latar) {
      // Tutup angka sumbu di balik label. Tepinya memudar supaya angka yang terpotong tidak terlihat tercoret, dan
      // tidak melebar sampai menutupi label harga terakhir milik chart. Semua penutup digambar sebelum labelnya.
      jadi.forEach(({ y }) => {
        const y0 = Math.round(y - T / 2), sisi = (arah) => {
          if (geo.hindariY == null || !isFinite(geo.hindariY)) return 9;
          const jarak = arah < 0 ? y - geo.hindariY : geo.hindariY - y;  // > 0 bila harga terakhir ada di sisi itu
          return jarak > 0 ? Math.max(0, Math.min(9, jarak - T)) : 9;
        };
        const pa = sisi(-1), pb = sisi(1), tinggi = T + pa + pb, g = ctx.createLinearGradient(0, y0 - pa, 0, y0 + T + pb), tembus = "rgba(0,0,0,0)";
        g.addColorStop(0, pa ? tembus : geo.latar); g.addColorStop(pa / tinggi, geo.latar); g.addColorStop((pa + T) / tinggi, geo.latar); g.addColorStop(1, pb ? tembus : geo.latar);
        ctx.fillStyle = g; ctx.fillRect(0, y0 - pa, geo.w, tinggi);
      });
    }
    jadi.forEach(({ d, y }) => {
      ctx.fillStyle = d.warna || SUMBU.netral;
      ctx.fillRect(0, Math.round(y - T / 2), geo.w, T);
      ctx.fillStyle = "#ffffff";
      let teks = d.teks;
      if (geo.format && d.harga != null) { try { teks = String(geo.format(d.harga)); } catch { teks = d.teks; } }
      ctx.fillText(teks, 5, y + 0.5, geo.w - 7);
    });
    ctx.restore();
  }

  root.ATLapisan = { gambar, gambarSumbu, TEMA };
})(typeof window !== "undefined" ? window : globalThis);
