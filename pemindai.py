#!/usr/bin/env python3
"""
Pemindai IHSG: semua saham Bursa Efek Indonesia yang cukup likuid, dianalisa dengan mesin yang sama, dan tanda
(flag) yang BARU muncul dibanding pindai hari bursa sebelumnya ditandai.

    python3 pemindai.py              # tarik harga (Yahoo), saring, analisa, tulis output/ihsg/ihsg.json
    python3 pemindai.py --offline    # pakai cache harga saja (cache/ihsg)
    python3 pemindai.py --maks 50    # uji cepat: hanya 50 kode pertama

Dijalankan oleh panel (tombol "Pindai IHSG" dan otomatis sekali tiap hari bursa setelah ±16:30 WIB bila panel
menyala; lihat panel.py). Tidak membaca folder portofolio sama sekali: hanya data harga + data publik IDX.

Langkah:
1. Daftar kode: daftar_ihsg.json (daftar awal), diperbarui dari IDX bila situsnya bisa diakses program
   (cache/ihsg/daftar_idx.json, sekali seminggu), ditambah pengaturan.json -> ihsg_tambahan, dikurangi ihsg_kecuali.
2. Harga harian dari Yahoo Finance (yfinance, per 80 kode). Pertama kali 2 tahun, sesudahnya hanya 1 bulan terakhir
   yang digabung ke cache/ihsg/<KODE>.JK.csv. Kode yang tidak ada datanya dilewati 7 hari (cache/ihsg/_gagal.json).
3. Ringkasan perdagangan IDX hari itu (frekuensi, bid/offer penutupan, jumlah saham) bila bisa diakses; bila tidak,
   kolom itu kosong dan saringannya dilewati.
4. Saringan likuiditas (pengaturan.json -> ihsg_saringan, bawaan "longgar"): nilai transaksi rata-rata 20 hari,
   harga minimum, hari aktif dari 20 hari terakhir, jumlah bar, dan (bila data IDX ada) frekuensi, spread
   bid/offer, papan Pemantauan Khusus.
5. Saham yang lolos dianalisa (skor 1D, skor beli, tanda) paralel; tanda dibandingkan dengan pindai hari bursa
   sebelumnya (output/ihsg/arsip/) untuk label Baru.
"""
from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
import urllib.request
from concurrent.futures import ProcessPoolExecutor, ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.dont_write_bytecode = True
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))

import numpy as np  # noqa: E402

import bahasa as bh  # noqa: E402
import ta_engine as te  # noqa: E402
import teknikal as tk  # noqa: E402
import wawasan as ws  # noqa: E402

CACHE = FOLDER / "cache" / "ihsg"
OUT = FOLDER / "output" / "ihsg"
STATUS = OUT / "status.json"
WIB = timezone(timedelta(hours=7))
VERSI = "1"

# Bawaan = "longgar" (dipilih 24 Nov 2026). 0 = saringan itu tidak dipakai.
SARINGAN_BAWAAN = {
    "nilai_rata20_min": 1e9,      # Rp, rata-rata nilai transaksi harian 20 hari terakhir
    "nilai_hari_ini_min": 0,      # Rp, nilai transaksi bar terakhir
    "harga_min": 50,              # Rp
    "hari_aktif_min": 15,         # hari dengan volume > 0 dari 20 hari terakhir
    "bar_min": 120,               # riwayat minimal (hari bursa) supaya indikator bermakna
    "frekuensi_min": 0,           # kali transaksi hari itu (hanya bila data IDX tersedia)
    "spread_maks_pct": 0,         # (offer − bid) / tengah, % (hanya bila data IDX tersedia)
    "kecuali_papan": ["Pemantauan Khusus"],
}
PRESET = {
    "longgar": dict(SARINGAN_BAWAAN),
    "standar": {**SARINGAN_BAWAAN, "nilai_rata20_min": 5e9, "nilai_hari_ini_min": 1e9, "harga_min": 100, "hari_aktif_min": 18},
    "ketat": {**SARINGAN_BAWAAN, "nilai_rata20_min": 20e9, "nilai_hari_ini_min": 5e9, "harga_min": 200, "hari_aktif_min": 20},
}
UA = ("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/131.0 Safari/537.36")


# ------------------------------------------------------------------
# utilitas
# ------------------------------------------------------------------

def _baca_json(p: Path, bawaan=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return bawaan


def _tulis_json(p: Path, data) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    os.replace(tmp, p)


def kabar(**isi) -> None:
    st = _baca_json(STATUS, {}) or {}
    st.update(isi)
    try:
        _tulis_json(STATUS, st)
    except OSError:
        pass


def saringan(cfg: dict) -> dict:
    s = cfg.get("ihsg_saringan")
    if isinstance(s, str):
        return dict(PRESET.get(s, SARINGAN_BAWAAN))
    return {**SARINGAN_BAWAAN, **(s if isinstance(s, dict) else {})}


# ------------------------------------------------------------------
# 1. daftar kode & data publik IDX (best effort)
# ------------------------------------------------------------------

def _idx_json(jalur: str, batas: float = 20):
    """GET JSON dari situs IDX. Situs ini sering menolak program (Cloudflare); gagal = None, tidak apa-apa."""
    for host in ("https://www.idx.co.id", "https://idx.co.id"):
        try:
            req = urllib.request.Request(host + jalur, headers={
                "User-Agent": UA, "Accept": "application/json, text/plain, */*", "Accept-Language": "id-ID,id;q=0.9,en;q=0.8",
                "Referer": host + "/id/data-pasar/ringkasan-perdagangan/ringkasan-saham/"})
            with urllib.request.urlopen(req, timeout=batas) as r:
                teks = r.read().decode("utf-8", "replace")
            if teks.lstrip().startswith(("{", "[")):
                return json.loads(teks)
        except Exception:  # noqa: BLE001
            continue
    return None


def daftar_idx(offline: bool) -> dict:
    """{kode: {"nama", "papan", "saham"}} dari IDX, disimpan seminggu. {} bila tidak bisa diakses."""
    p = CACHE / "daftar_idx.json"
    lama = _baca_json(p, {}) or {}
    if offline or (lama.get("waktu", 0) > time.time() - 7 * 86400 and lama.get("data")):
        return lama.get("data") or {}
    j = _idx_json("/primary/StockData/GetSecuritiesStock?start=0&length=9999&code=&sector=&board=&language=id-id")
    data = {}
    for x in (j or {}).get("data") or []:
        kode = str(x.get("Code") or "").strip().upper()
        if len(kode) == 4 and kode.isalpha():
            data[kode] = {"nama": x.get("Name"), "papan": x.get("ListingBoard"), "saham": x.get("Shares")}
    if data:
        _tulis_json(p, {"waktu": time.time(), "data": data})
        return data
    return lama.get("data") or {}


def ringkasan_idx(tanggal: str, offline: bool) -> dict:
    """{kode: {"frek", "nilai", "bid", "offer", "saham"}} untuk satu tanggal bursa (YYYY-MM-DD). {} bila gagal."""
    p = CACHE / f"ringkasan_{tanggal}.json"
    ada = _baca_json(p)
    if ada is not None:
        return ada
    if offline:
        return {}
    j = _idx_json(f"/primary/TradingSummary/GetStockSummary?length=9999&start=0&date={tanggal.replace('-', '')}")
    data = {}
    for x in (j or {}).get("data") or []:
        kode = str(x.get("StockCode") or "").strip().upper()
        if not kode:
            continue
        data[kode] = {"frek": x.get("Frequency"), "nilai": x.get("Value"), "bid": x.get("Bid"), "offer": x.get("Offer"),
                      "saham": x.get("ListedShares")}
    if data:
        _tulis_json(p, data)
    return data


def daftar_kode(cfg: dict, idx: dict) -> list[str]:
    awal = _baca_json(FOLDER / "daftar_ihsg.json", {}) or {}
    kode = set(awal.get("kode") or []) | set(idx)
    kode |= {str(x).upper().replace(".JK", "") for x in cfg.get("ihsg_tambahan") or []}
    kode -= {str(x).upper().replace(".JK", "") for x in cfg.get("ihsg_kecuali") or []}
    return sorted(k for k in kode if len(k) == 4 and k.isalpha())


# ------------------------------------------------------------------
# 2. harga harian (Yahoo) + cache
# ------------------------------------------------------------------

def _file(kode: str) -> Path:
    return CACHE / f"{kode}.JK.csv"


def muat(kode: str) -> dict | None:
    p = _file(kode)
    if not p.exists():
        return None
    try:
        rows = [[float(x) for x in baris.split(",")] for baris in p.read_text().splitlines()[1:] if baris]
    except ValueError:
        return None
    return te.to_bars(rows) if len(rows) >= 2 else None


def simpan(kode: str, b: dict) -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    baris = ["t,o,h,l,c,v"] + [f"{int(b['t'][i])},{b['o'][i]},{b['h'][i]},{b['l'][i]},{b['c'][i]},{b['v'][i]}" for i in range(len(b["c"]))]
    tmp = _file(kode).with_suffix(".csv.tmp")
    tmp.write_text("\n".join(baris) + "\n")
    os.replace(tmp, _file(kode))


def _beda_tumpang(lama: dict | None, baru: dict | None) -> bool:
    """True bila close di tanggal yang sama berbeda > 2% antara cache dan unduhan baru (mis. stock split / reverse
    split / harga yang disesuaikan ulang): sambungan 1 bulan ke cache lama akan membuat gap palsu, jadi unduh ulang penuh."""
    if not lama or not baru:
        return False
    kl = {int((t + 7 * 3600) // 86400): c for t, c in zip(lama["t"], lama["c"])}
    for t, c in zip(baru["t"][:-1], baru["c"][:-1]):  # bar terakhir bisa masih berjalan
        k = int((t + 7 * 3600) // 86400)
        if k in kl and kl[k] > 0 and abs(c / kl[k] - 1) > 0.02:
            return True
    return False


def _gabung(lama: dict | None, baru: dict | None, maks: int = 600) -> dict | None:
    if baru is None:
        return lama
    if lama is None:
        rows = {}
    else:
        rows = {int((t + 7 * 3600) // 86400): [t, o, h, l, c, v] for t, o, h, l, c, v in zip(*(lama[k] for k in "tohlcv"))}
    for t, o, h, l, c, v in zip(*(baru[k] for k in "tohlcv")):
        rows[int((t + 7 * 3600) // 86400)] = [t, o, h, l, c, v]
    urut = [rows[k] for k in sorted(rows)][-maks:]
    return te.to_bars(urut) if len(urut) >= 2 else None


def _unduh(tickers: list[str], periode: str, threads: int = 4) -> dict:
    """{ticker: bars} lewat yfinance; tanpa yfinance: satu per satu lewat Yahoo v8 (lebih lambat).
    threads dibatasi (bukan True = satu thread per kode): pindai 24 Nov dengan 80 kode sekaligus menghabiskan
    batas berkas terbuka macOS (256 untuk aplikasi Finder) sehingga ratusan unduhan gagal dengan EMFILE."""
    hasil = {}
    try:
        import yfinance as yf
        df = yf.download(tickers, period=periode, interval="1d", group_by="ticker", auto_adjust=False,
                         progress=False, threads=threads)
        for t in tickers:
            try:
                sub = df[t] if len(tickers) > 1 else df
                if hasattr(sub.columns, "nlevels") and sub.columns.nlevels > 1:
                    sub = sub.droplevel(0, axis=1)
                sub = sub.dropna(how="all")
                b = _bars_df(sub)
            except Exception:  # noqa: BLE001
                b = None
            if b is not None:
                hasil[t] = b
        return hasil
    except ImportError:
        pass
    except Exception:  # noqa: BLE001 - mis. dibatasi Yahoo: coba satu per satu
        pass

    def satu(t):
        try:
            b, _ = te.fetch_yahoo(t, "1d")
            return t, b
        except Exception:  # noqa: BLE001
            return t, None
    with ThreadPoolExecutor(max_workers=6) as ex:
        for t, b in ex.map(satu, tickers):
            if b is not None:
                hasil[t] = b
    return hasil


def _bars_df(df) -> dict | None:
    """Seperti teknikal._dari_dataframe, tapi menerima riwayat pendek (pembaruan 1 bulan)."""
    if df is None or len(df) == 0:
        return None
    kol = {str(c).lower(): c for c in df.columns}
    if "close" not in kol:
        return None
    rows = []
    for i, r in df.iterrows():
        try:
            o, h, l, c = (float(r[kol[k]]) for k in ("open", "high", "low", "close"))
        except (TypeError, ValueError, KeyError):
            continue
        if any(math.isnan(x) for x in (o, h, l, c)) or c <= 0:
            continue
        v = float(r[kol["volume"]]) if "volume" in kol and r[kol["volume"]] == r[kol["volume"]] else 0.0
        ts = i.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rows.append([ts.timestamp(), o, h, l, c, v])
    return te.to_bars(rows) if rows else None


def tarik_semua(kode: list[str], offline: bool) -> tuple[dict, list[str], str | None]:
    """({kode: bars}, [kode tanpa data], peringatan atau None)."""
    data = {}
    gagal = _baca_json(CACHE / "_gagal.json", {}) or {}
    sekarang = time.time()
    for k in kode:
        b = muat(k)
        if b is not None:
            data[k] = b
    if offline:
        return data, [k for k in kode if k not in data], None
    penuh = [k for k in kode if (k not in data or data[k]["t"][-1] < sekarang - 10 * 86400)
             and gagal.get(k, 0) < sekarang - 7 * 86400]
    inkremental = [k for k in kode if k in data and k not in penuh]
    total = len(penuh) + len(inkremental)
    berhasil, gagal_kali_ini, unduh_ulang = set(), [], []
    selesai = 0

    def proses(kelompok, periode, threads):
        nonlocal selesai
        hasil = _unduh([k + ".JK" for k in kelompok], periode, threads)
        for k in kelompok:
            b = hasil.get(k + ".JK")
            if b is None:
                gagal_kali_ini.append((k, periode))
                continue
            if periode == "1mo" and _beda_tumpang(data.get(k), b):
                unduh_ulang.append(k)  # split dsb.: ambil ulang 2 tahun
                continue
            g = _gabung(data.get(k) if periode == "1mo" else None, b)
            if g is not None:
                data[k] = g
                berhasil.add(k)
                try:
                    simpan(k, g)
                except OSError:
                    pass
                gagal.pop(k, None)

    UKURAN = 40
    for daftar, periode in ((penuh, "2y"), (inkremental, "1mo")):
        for i in range(0, len(daftar), UKURAN):
            proses(daftar[i:i + UKURAN], periode, 4)
            selesai += len(daftar[i:i + UKURAN])
            kabar(fase="harga", selesai_n=selesai, jumlah=total)
            time.sleep(0.5)  # jangan membanjiri Yahoo
    # Sekali lagi untuk yang gagal (kelompok kecil, 2 thread) dan yang perlu unduh ulang penuh.
    ulang = [(k, "2y" if k in unduh_ulang else p) for k, p in gagal_kali_ini] + [(k, "2y") for k in unduh_ulang]
    gagal_kali_ini.clear()
    for periode in ("2y", "1mo"):
        ks = sorted({k for k, p in ulang if p == periode})
        for i in range(0, len(ks), 15):
            proses(ks[i:i + 15], periode, 2)
            time.sleep(1.0)
    gagal_akhir = sorted({k for k, _ in gagal_kali_ini} - berhasil)
    # Kode baru dilewati 7 hari hanya bila unduhan lain umumnya berhasil (kode itu memang tidak ada di Yahoo).
    # Bila banyak yang gagal sekaligus, itu gangguan (jaringan, batas Yahoo, batas berkas terbuka): jangan dicatat.
    dicoba = len(berhasil) + len(gagal_akhir)
    peringatan = None
    if dicoba and len(gagal_akhir) / dicoba > 0.3:
        peringatan = f"{len(gagal_akhir)} dari {dicoba} unduhan harga gagal (kemungkinan gangguan jaringan atau Yahoo); coba pindai lagi nanti."
    else:
        for k in gagal_akhir:
            if k not in data:  # hanya kode yang memang belum pernah punya data
                gagal[k] = sekarang
    try:
        _tulis_json(CACHE / "_gagal.json", gagal)
    except OSError:
        pass
    return data, [k for k in kode if k not in data], peringatan


# ------------------------------------------------------------------
# 3–4. ukuran likuiditas & saringan
# ------------------------------------------------------------------

def ukur(b: dict, ring: dict | None, info: dict | None) -> dict:
    c, v = np.asarray(b["c"], float), np.asarray(b["v"], float)
    nilai = c * v
    m = {"harga": float(c[-1]), "chg": float((c[-1] / c[-2] - 1) * 100) if len(c) > 1 and c[-2] > 0 else 0.0,
         "nilai": float(nilai[-1]), "nilai20": float(nilai[-20:].mean()), "aktif20": int((v[-20:] > 0).sum()),
         "bar": int(len(c)), "tick_pct": te.idx_tick(float(c[-1])) / float(c[-1]) * 100}
    if ring:
        m["frek"] = ring.get("frek")
        bid, off = ring.get("bid") or 0, ring.get("offer") or 0
        if bid and off and off >= bid:
            m["spread"] = (off - bid) / ((off + bid) / 2) * 100
        if ring.get("saham"):
            m["kap"] = float(ring["saham"]) * float(c[-1])
    if info:
        m["papan"] = info.get("papan")
        if "kap" not in m and info.get("saham"):
            try:
                m["kap"] = float(info["saham"]) * float(c[-1])
            except (TypeError, ValueError):
                pass
    return m


def lolos(m: dict, S: dict) -> str | None:
    """None bila lolos; selain itu alasan singkat tidak lolos."""
    if m["bar"] < S["bar_min"]:
        return "riwayat pendek"
    if m["harga"] < S["harga_min"]:
        return "harga rendah"
    if m["aktif20"] < S["hari_aktif_min"]:
        return "jarang diperdagangkan"
    if m["nilai20"] < S["nilai_rata20_min"]:
        return "nilai transaksi kecil"
    if S["nilai_hari_ini_min"] and m["nilai"] < S["nilai_hari_ini_min"]:
        return "nilai hari ini kecil"
    if S["frekuensi_min"] and m.get("frek") is not None and m["frek"] < S["frekuensi_min"]:
        return "frekuensi rendah"
    if S["spread_maks_pct"] and m.get("spread") is not None and m["spread"] > S["spread_maks_pct"]:
        return "spread lebar"
    if m.get("papan") and m["papan"] in (S.get("kecuali_papan") or []):
        return "papan " + str(m["papan"])
    return None


# ------------------------------------------------------------------
# 5. analisa (paralel) & tanda baru
# ------------------------------------------------------------------

def _analisa_satu(arg):
    kode, b, bj = arg
    T = kode + ".JK"
    try:
        jalan = ws.fraksi_berjalan(T, "idx", b["t"][-1], "1d")
        r = te.analyze_mtf(te.auto_mtf(b, "1d", "idx"), symbol=kode, market="idx", primary="1d", live_frac=jalan)
        bw = te.resample(b, "1wk", "idx")
        rw = te.analyze(bw, market="idx", tf="1wk") if len(bw["c"]) >= 30 else None
        rs = ws.kekuatan_relatif(b, bj, "IHSG") if bj is not None else None
        sb = ws.skor_beli(r, rw, rs)
        fl = tk.bendera(r, None, None, b["c"])
        ind = r["indicators"]
        vr, chg = ind.get("volume_ratio"), ind.get("change_pct") or 0.0
        if vr and vr >= 2 and not (jalan is not None and jalan < 0.25):
            if chg >= 3:
                fl.append({"level": "hijau", "teks": f"Lonjakan volume {vr:.1f}x rata-rata dengan harga naik {chg:.1f}%"})
            elif chg <= -3:
                fl.append({"level": "oranye", "teks": f"Lonjakan volume {vr:.1f}x rata-rata dengan harga turun {abs(chg):.1f}%"})
        if sb["skor"] >= 60:
            fl.append({"level": "hijau", "teks": f"Skor beli {sb['skor']} ({sb['label'].lower()})"})
        ra = ws.rencana_aksi(r)
        ra_en = bh.rencana_aksi_en(r)
        tag = []
        if (ind.get("atr_pct") or 0) >= 8:
            tag.append("volatil")
        if jalan is not None:
            tag.append("berjalan")
        return {"kode": kode, "skor": int(r["score"]), "label": r["label_id"], "tren": r["trend"]["label"],
                "skor_beli": sb, "bendera": fl, "langkah": ra.get("ringkas") or ra.get("judul", ""),
                "langkah_en": ra_en.get("ringkas") or ra_en.get("judul", ""), "sikap": ra.get("sikap"),
                "rr_rendah": bool(ra.get("rr_rendah")), "atr_pct": ind.get("atr_pct"), "rsi": ind.get("rsi14"),
                "tag": tag, "s1": (r["support"] or [{}])[0].get("price"), "r1": (r["resistance"] or [{}])[0].get("price")}
    except Exception as exc:  # noqa: BLE001
        return {"kode": kode, "galat": str(exc)[:120]}


def muat_dasar(hari_ini: str) -> tuple[str | None, dict]:
    for p in sorted((OUT / "arsip").glob("ihsg_*.json"), reverse=True):
        tgl = p.stem.split("_", 1)[-1]
        if tgl >= hari_ini:
            continue
        d = _baca_json(p)
        if d:
            return tgl, d.get("aset") or {}
    return None, {}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Pemindai IHSG")
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--maks", type=int, default=0)
    args = ap.parse_args(argv)
    mulai = time.time()
    try:  # macOS memberi aplikasi Finder batas 256 berkas terbuka; unduhan paralel butuh lebih
        import resource
        lunak, keras = resource.getrlimit(resource.RLIMIT_NOFILE)
        target = 4096 if keras == resource.RLIM_INFINITY else min(4096, keras)
        if lunak < target:
            resource.setrlimit(resource.RLIMIT_NOFILE, (target, keras))
    except (ImportError, ValueError, OSError):  # Windows tidak punya modul resource
        pass
    OUT.mkdir(parents=True, exist_ok=True)
    _tulis_json(STATUS, {"berjalan": True, "fase": "daftar", "mulai": datetime.now(WIB).isoformat(timespec="seconds"),
                         "pid": os.getpid(), "selesai": None, "ok": None, "pesan": ""})
    try:
        cfg = tk.muat_pengaturan()
        S = saringan(cfg)
        idx = daftar_idx(args.offline)
        kode = daftar_kode(cfg, idx)
        if args.maks:
            kode = kode[:args.maks]
        kabar(fase="harga", jumlah=len(kode), selesai_n=0)
        data, tanpa, peringatan = tarik_semua(kode, args.offline)
        bj = None
        try:
            bj = muat("_JKSE")
            if not args.offline:
                hasil = _unduh(["^JKSE"], "2y")
                if hasil.get("^JKSE") is not None:
                    bj = hasil["^JKSE"]
                    simpan("_JKSE", bj)
        except Exception:  # noqa: BLE001
            pass
        # tanggal bursa terakhir = bar terbaru di antara semua saham
        t_akhir = max((b["t"][-1] for b in data.values()), default=time.time())
        tgl_bursa = datetime.fromtimestamp(t_akhir, WIB).strftime("%Y-%m-%d")
        ring = ringkasan_idx(tgl_bursa, args.offline)
        kabar(fase="saring")
        ukuran, ditolak = {}, {}
        for k, b in data.items():
            if b["t"][-1] < t_akhir - 5 * 86400:
                ditolak[k] = "tidak diperdagangkan / suspensi"
                continue
            m = ukur(b, ring.get(k), idx.get(k))
            alasan = lolos(m, S)
            if alasan:
                ditolak[k] = alasan
            else:
                ukuran[k] = m
        kabar(fase="analisa", jumlah=len(ukuran), selesai_n=0)
        hasil = []
        tugas = [(k, data[k], bj) for k in sorted(ukuran)]
        pekerja = max(1, min(8, (os.cpu_count() or 2) - 1))
        try:
            with ProcessPoolExecutor(max_workers=pekerja) as ex:
                for i, x in enumerate(ex.map(_analisa_satu, tugas, chunksize=8)):
                    hasil.append(x)
                    if i % 25 == 0:
                        kabar(selesai_n=i)
        except Exception:  # noqa: BLE001 - mis. lingkungan tanpa multiprocessing: satu per satu
            hasil = [_analisa_satu(t) for t in tugas]
        # Arsip & "Baru" per tanggal BURSA (bukan tanggal hari ini): pindai di akhir pekan / libur / pagi sebelum
        # bursa buka memakai data hari bursa terakhir, jadi tetap dibandingkan dengan hari bursa sebelumnya.
        hari_ini = tgl_bursa
        tgl_dasar, dasar = muat_dasar(hari_ini)
        aset, baru_total, galat = [], 0, []
        for x in hasil:
            if x.get("galat"):
                galat.append(x["kode"])
                continue
            k = x["kode"]
            fl = tk.tandai_baru(x["bendera"], dasar.get(k), hari_ini)
            if not tgl_dasar:  # belum ada pembanding: tidak ada yang disebut baru
                for f in fl:
                    f["baru"] = False
            x["bendera"] = fl
            x["baru_n"] = sum(1 for f in fl if f["baru"] and f["level"] in ("merah", "oranye", "hijau"))
            if tgl_dasar and k not in dasar:
                x["tag"].append("baru_lolos")
            baru_total += x["baru_n"]
            x.update(ukuran[k])
            aset.append(x)
        aset.sort(key=lambda a: (-a["baru_n"], -a["skor_beli"]["skor"]))
        waktu = datetime.now(WIB)
        dump = tk._bersihkan({
            "versi": VERSI, "mesin": te.VERSION, "id": waktu.strftime("%Y%m%d%H%M%S"), "waktu": waktu.isoformat(timespec="seconds"),
            "tanggal_bursa": tgl_bursa, "tanggal_dasar": tgl_dasar, "saringan": S,
            "daftar_total": len(kode), "data_ok": len(data), "tanpa_data": tanpa[:200], "ditolak_n": len(ditolak),
            "ditolak_alasan": {a: sum(1 for v in ditolak.values() if v == a) for a in sorted(set(ditolak.values()))},
            "lolos": len(aset), "galat": galat, "sumber_idx": {"daftar": bool(idx), "ringkasan": bool(ring)},
            "baru_total": baru_total, "aset": aset, "durasi": round(time.time() - mulai, 1), "peringatan": peringatan})
        _tulis_json(OUT / "ihsg.json", dump)
        # arsip ringkas untuk pembanding besok: kode tanda + sejak
        arsip = {"tanggal": hari_ini, "aset": {a["kode"]: {"skor": a["skor"], "tanda": {f["kode"]: f["sejak"] for f in a["bendera"]}}
                                               for a in aset}}
        _tulis_json(OUT / "arsip" / f"ihsg_{hari_ini}.json", arsip)
        pesan = f"{len(aset)} dari {len(kode)} saham lolos saringan; {baru_total} tanda baru." + (f" Peringatan: {peringatan}" if peringatan else "")
        kabar(berjalan=False, ok=True, fase=None, selesai=waktu.isoformat(timespec="seconds"), pesan=pesan, tanggal=hari_ini,
              tanggal_pindai=waktu.strftime("%Y-%m-%d"), peringatan=peringatan)
        print(pesan, f"({dump['durasi']} detik)")
        return 0
    except Exception as exc:  # noqa: BLE001
        kabar(berjalan=False, ok=False, fase=None, selesai=datetime.now(WIB).isoformat(timespec="seconds"), pesan=str(exc)[:300])
        print(f"Pemindai IHSG gagal: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
