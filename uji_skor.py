"""Uji keandalan skor (backtest sederhana).

Pertanyaannya: setelah skor harian menunjukkan angka tertentu, bagaimana harga bergerak 5 dan 20 hari bursa sesudahnya?

Cara kerja:
- Data: harga harian di cache/ohlc (hasil pindai terakhir; tidak menarik data baru, tidak membaca folder portofolio).
- Untuk setiap aset dan setiap hari (setelah 200 bar pertama), skor dihitung HANYA dari data sampai hari itu
  (fungsi yang sama dengan garis skor 30 hari, wawasan._skor_pada), lalu dibandingkan dengan return 5 dan 20 hari
  sesudahnya.
- Hasil dikelompokkan per kelompok skor dan per pasar. "Selisih vs rata-rata" = return kelompok itu dikurangi
  return rata-rata semua hari di pasar yang sama, supaya tren pasar keseluruhan (mis. kripto yang turun setahun)
  tidak dikira kehebatan skor.

Sejak mesin 1.3.0 ada dua uji tambahan dari perhitungan yang sama:
- Per kategori sinyal (tren, momentum, pola chart, …): return 20 hari saat kategori itu bullish dikurangi saat
  bearish. Positif = kategori itu searah dengan hasil; sekitar nol atau negatif = tidak membantu di pasar itu.
- Rencana: saat rencana "Area beli" aktif dan harga di dalam areanya, mana yang lebih dulu terjadi dalam 40 bar:
  target 1 tersentuh atau close di bawah Stop. Saat rencana "Belum saatnya beli": mana lebih dulu dalam 40 bar,
  harga turun ke target turun 1 atau close di atas Konfirmasi naik.

Keterbatasan (ditulis juga di hasil): sampel hanya aset yang pernah dipindai (bias pilihan), hari-hari saling
tumpang tindih (return 20 hari berurutan tidak independen), dan tanpa biaya transaksi. Anggap ini gambaran kasar,
bukan bukti statistik.

    python3 uji_skor.py            # tulis output/uji_skor.json dan cetak ringkasan
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

sys.dont_write_bytecode = True
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))

import teknikal as tk  # noqa: E402
import wawasan as ws  # noqa: E402
import ta_engine as te  # noqa: E402

KELOMPOK = [("≤ −50", -101, -50), ("−49…−20", -49, -20), ("−19…19", -19, 19), ("20…49", 20, 49), ("≥ 50", 50, 101)]
HORISON = (5, 20)
KATEGORI = ("Tren", "Momentum", "Pola chart", "Trendline", "Candlestick", "Divergence", "Volume", "Breakout", "Lokasi")
AMBANG_KAT = 0.3      # |jumlah poin mentah kategori| di atas ini = kategori itu bullish / bearish hari itu
HORISON_RENCANA = 40  # bar
LEWATI = {"_JKSE", "_GSPC", "USDIDR_X"}  # pembanding & kurs, bukan aset


def _pasar(nama_file: str) -> str:
    if nama_file.endswith(".JK"):
        return "idx"
    if nama_file.endswith("-USD"):
        return "crypto"
    return "us"


def _satu(nama_file: str):
    ticker = nama_file.replace("_", "^", 1) if nama_file.startswith("_") else nama_file
    b = tk.muat_cache(ticker)
    if b is None or len(b["c"]) < 260:
        return nama_file, []
    pasar = _pasar(nama_file)
    c, hi, lo = b["c"], b["h"], b["l"]
    baris = []
    for i in range(200, len(c) - 1):
        try:
            a = te.analyze({k: v[: i + 1] for k, v in b.items()}, market=pasar, tf="1d")
        except Exception:  # noqa: BLE001
            continue
        r = {h: (float(c[i + h]) / float(c[i]) - 1) * 100 if i + h < len(c) else None for h in HORISON}
        kat = {}
        for x in a["signals"]:
            kat[x["cat"]] = kat.get(x["cat"], 0.0) + x["score"]
        baris.append((float(b["t"][i]), int(a["score"]), r[5], r[20], kat, _hasil_rencana(a, c, hi, lo, i)))
    return nama_file, baris


def _hasil_rencana(a: dict, c, hi, lo, i: int):
    """("beli", "target"|"stop"|"belum", rr_rendah) · ("hindari", "turun"|"naik"|"belum", None) · None."""
    p, harga = a["plan"], float(c[i])
    akhir = min(len(c), i + 1 + HORISON_RENCANA)
    penuh = akhir - (i + 1) >= HORISON_RENCANA
    try:
        if p["bias"] == "long" and p["targets"]:
            z_lo, z_hi = p["entry_zone"]
            if not (z_lo <= harga <= z_hi * 1.005):
                return None  # hanya hari ketika harga memang di area beli
            stop, target = float(p["stop_loss"]), float(p["targets"][0])
            rr1 = (p.get("rr") or [None])[0]
            for j in range(i + 1, akhir):
                if c[j] < stop:
                    return ("beli", "stop", bool(rr1 is not None and rr1 < 1))
                if hi[j] >= target:
                    return ("beli", "target", bool(rr1 is not None and rr1 < 1))
            return ("beli", "belum", bool(rr1 is not None and rr1 < 1)) if penuh else None
        if p["bias"] == "short" and p["targets"]:
            naik, turun = float(p["stop_loss"]), float(p["targets"][0])
            for j in range(i + 1, akhir):
                if c[j] > naik:
                    return ("hindari", "naik", None)
                if lo[j] <= turun:
                    return ("hindari", "turun", None)
            return ("hindari", "belum", None) if penuh else None
    except (KeyError, TypeError, ValueError, IndexError):
        return None
    return None


def _uji_kategori(data: list, dasar: float) -> list[dict]:
    hasil = []
    for nama in KATEGORI:
        bull = [x[3] for x in data if x[3] is not None and x[4].get(nama, 0.0) > AMBANG_KAT]
        bear = [x[3] for x in data if x[3] is not None and x[4].get(nama, 0.0) < -AMBANG_KAT]
        baris = {"kategori": nama, "n_bull": len(bull), "n_bear": len(bear)}
        if bull:
            baris["bull"] = sum(bull) / len(bull) - dasar
        if bear:
            baris["bear"] = sum(bear) / len(bear) - dasar
        if len(bull) >= 100 and len(bear) >= 100:
            baris["beda"] = baris["bull"] - baris["bear"]
        hasil.append(baris)
    return hasil


def _uji_rencana(data: list) -> dict:
    def hitung(pilih, kunci):
        x = [r[5][1] for r in data if r[5] and pilih(r[5])]
        if not x:
            return {"n": 0}
        return {"n": len(x), **{k: 100 * x.count(k) / len(x) for k in kunci}}
    return {"beli": hitung(lambda h: h[0] == "beli", ("target", "stop", "belum")),
            "beli_rr_ok": hitung(lambda h: h[0] == "beli" and not h[2], ("target", "stop", "belum")),
            "beli_rr_rendah": hitung(lambda h: h[0] == "beli" and h[2], ("target", "stop", "belum")),
            "hindari": hitung(lambda h: h[0] == "hindari", ("turun", "naik", "belum"))}


def _ringkas(nilai: list[float]) -> dict:
    if not nilai:
        return {"n": 0}
    urut = sorted(nilai)
    return {"n": len(nilai), "rata": sum(nilai) / len(nilai), "median": urut[len(urut) // 2],
            "naik_pct": 100 * sum(1 for x in nilai if x > 0) / len(nilai)}


def main() -> None:
    nama = sorted(p.stem for p in (FOLDER / "cache" / "ohlc").glob("*.csv") if p.stem not in LEWATI)
    with ProcessPoolExecutor() as ex:
        semua = dict(ex.map(_satu, nama))
    hasil = {"dibuat": datetime.now(timezone.utc).isoformat(timespec="seconds"), "versi_mesin": te.VERSION,
             "aset": sum(1 for v in semua.values() if v), "pasar": {}}
    tgl = [t for v in semua.values() for t, *_ in v]
    if tgl:
        hasil["dari"] = datetime.fromtimestamp(min(tgl), timezone.utc).strftime("%Y-%m-%d")
        hasil["sampai"] = datetime.fromtimestamp(max(tgl), timezone.utc).strftime("%Y-%m-%d")
    for pasar in ("idx", "us", "crypto", "semua"):
        data = [x for k, v in semua.items() if pasar == "semua" or _pasar(k) == pasar for x in v]
        if not data:
            continue
        blok = {"aset": sum(1 for k, v in semua.items() if v and (pasar == "semua" or _pasar(k) == pasar)), "hari": len(data)}
        for h, idx in ((5, 2), (20, 3)):
            dasar = _ringkas([x[idx] for x in data if x[idx] is not None])
            kel = []
            for label, lo, hi in KELOMPOK:
                r = _ringkas([x[idx] for x in data if x[idx] is not None and lo <= x[1] <= hi])
                if r["n"]:
                    r["selisih"] = r["rata"] - dasar["rata"]
                kel.append({"kelompok": label, **r})
            # beda rata-rata skor tertinggi vs terendah (kelompok dengan sampel ≥ 30)
            ada = [k for k in kel if k["n"] >= 30]
            sebaran = (ada[-1]["rata"] - ada[0]["rata"]) if len(ada) >= 2 else None
            blok[f"h{h}"] = {"dasar": dasar, "kelompok": kel, "sebaran": sebaran}
        blok["kategori"] = _uji_kategori(data, blok["h20"]["dasar"].get("rata", 0.0))
        blok["rencana"] = _uji_rencana(data)
        hasil["pasar"][pasar] = blok
    hasil["horison_rencana"] = HORISON_RENCANA
    hasil["catatan"] = ("Sampel hanya aset yang pernah dipindai (bias pilihan); hari-hari tumpang tindih sehingga tidak "
                        "independen; tanpa biaya transaksi. Gambaran kasar, bukan bukti statistik.")
    (FOLDER / "output").mkdir(exist_ok=True)
    (FOLDER / "output" / "uji_skor.json").write_text(json.dumps(hasil, ensure_ascii=False, indent=1))
    for pasar, blok in hasil["pasar"].items():
        print(f"\n== {pasar}: {blok['aset']} aset, {blok['hari']} hari ==")
        for h in HORISON:
            d = blok[f"h{h}"]
            print(f" {h} hari | rata-rata semua {d['dasar']['rata']:+.2f}% (naik {d['dasar']['naik_pct']:.0f}%)")
            for k in d["kelompok"]:
                if k["n"]:
                    print(f"   {k['kelompok']:>9}  n={k['n']:5d}  rata {k['rata']:+6.2f}%  selisih {k['selisih']:+6.2f}  naik {k['naik_pct']:4.0f}%")
        print(" kategori (20 hari, bullish − bearish): " + " · ".join(f"{k['kategori']} {k['beda']:+.1f}" for k in blok["kategori"] if "beda" in k))
        rb, rh = blok["rencana"]["beli"], blok["rencana"]["hindari"]
        if rb["n"]:
            print(f" rencana beli (n={rb['n']}): target 1 dulu {rb['target']:.0f}% · stop dulu {rb['stop']:.0f}% · belum {rb['belum']:.0f}%")
        if rh["n"]:
            print(f" belum saatnya beli (n={rh['n']}): turun ke target turun 1 {rh['turun']:.0f}% · konfirmasi naik dulu {rh['naik']:.0f}% · belum {rh['belum']:.0f}%")


if __name__ == "__main__":
    main()
