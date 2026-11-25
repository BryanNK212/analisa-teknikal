#!/usr/bin/env python3
"""
Panel Analisa Teknikal — server lokal di http://127.0.0.1:8768

Dijalankan oleh "Analisa Teknikal.app". Panel di browser dan ekstensi Chrome
mengambil analisa dari sini. Data harga ditarik live dari Yahoo Finance / Binance
oleh komputer ini (Mac atau Windows).

Pemisahan analisa vs portofolio (sejak 10 Nov 2026):
- /api/analisa dan /api/riwayat (Cek aset, panel samping, badge & kartu ekstensi) TIDAK PERNAH membaca
  data folder portofolio maupun hasil pindai portofolio: tanpa posisi, tanpa label Baru dari arsip pindai.
- Data portofolio hanya lewat /api/portofolio, /api/pindai dan /chart/ (tab Portofolio di panel utama),
  dan ditolak bila diminta dari ekstensi atau dari halaman ?embed=1 / ?mandiri=1.

    python3 panel.py              # jalankan server lalu buka panel
    python3 panel.py --no-browser
    python3 panel.py --offline    # pakai cache harga saja (untuk uji)

Port 8765-8767 dipakai program lain dan tidak disentuh.
"""
from __future__ import annotations

import argparse
import contextlib
import os
import subprocess
import io
import json
import math
import mimetypes
import re
import sys
import threading
import time
import traceback
import urllib.parse
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.dont_write_bytecode = True
FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))

import ta_engine as te  # noqa: E402
import teknikal as tk  # noqa: E402
import wawasan as ws  # noqa: E402
import bahasa as bh  # noqa: E402

mimetypes.add_type("font/woff2", ".woff2")

PORT = 8768
HOST_SAH = {f"127.0.0.1:{PORT}", f"localhost:{PORT}"}
OFFLINE = False
MAKS_BAR = 800

# ==================================================================
# BAHASA (id / en) — satu pengaturan untuk panel, panel samping, kartu, dan garis di chart
# ==================================================================
# Disimpan di pengaturan.json ("bahasa"). Permintaan tanpa parameter bahasa memakai pengaturan ini,
# jadi ekstensi (badge, kartu, garis) otomatis ikut bahasa yang dipilih di panel.
_BAHASA = {"nilai": None}


def bahasa_aktif() -> str:
    if _BAHASA["nilai"] is None:
        try:
            _BAHASA["nilai"] = "en" if tk.muat_pengaturan().get("bahasa") == "en" else "id"
        except (SystemExit, Exception):  # noqa: BLE001
            _BAHASA["nilai"] = "id"
    return _BAHASA["nilai"]


def atur_bahasa(nilai: str) -> str:
    nilai = "en" if nilai == "en" else "id"
    path = FOLDER / "pengaturan.json"
    tk.muat_pengaturan()  # memastikan berkasnya ada
    data = json.loads(path.read_text(encoding="utf-8"))
    data["bahasa"] = nilai
    tk.tulis_atomik(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    _BAHASA["nilai"] = nilai
    return nilai


def atur_pantau(daftar: list) -> dict:
    """Simpan daftar pantau (tambahan_pantau) dari tab Daftar pantau. Tiap ticker dicek dulu ke sumber harga
    dan disimpan dalam format Yahoo (BBCA.JK, NVDA, BTC-USD), sama dengan yang dibaca pemindai."""
    tk.muat_pengaturan()
    path = FOLDER / "pengaturan.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    hasil, gagal = [], []
    for q in [str(x).strip().upper() for x in daftar if str(x).strip()][:60]:
        if not re.fullmatch(r"[A-Z0-9.^=:_/-]{1,24}", q):
            gagal.append(q)
            continue
        try:
            mkt, code, _b, _m = tarik(urai_simbol(q, None)[0], "1d")
        except (ValueError, LookupError):
            gagal.append(q)
            continue
        if mkt == "crypto":
            code = re.sub(r"(USDT|-USD)$", "", code) + "-USD"
        if code not in hasil:
            hasil.append(code)
    data["tambahan_pantau"] = hasil
    tk.tulis_atomik(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")
    return {"ok": True, "pantau": hasil, "gagal": gagal}


def pilih_bahasa(diminta: str | None) -> str:
    return diminta if diminta in ("id", "en") else bahasa_aktif()


# ==================================================================
# SIMBOL: format TradingView, Yahoo, atau polos
# ==================================================================

BURSA_AS = {"NASDAQ", "NYSE", "AMEX", "NYSEARCA", "NYSEAMERICAN", "BATS", "CBOE", "ARCA", "OTC", "CBOEBZX", "NYSEMKT",
            "US"}  # "US:" dipakai ekstensi untuk ticker Yahoo tanpa akhiran (pasti bursa AS)
BURSA_KRIPTO = {"BINANCE", "BINANCEUS", "BYBIT", "OKX", "BITGET", "KUCOIN", "MEXC", "GATEIO", "COINBASE", "BITSTAMP",
                "KRAKEN", "CRYPTO", "CRYPTOCAP", "BITFINEX", "GEMINI", "HTX", "UPBIT", "PHEMEX", "POLONIEX", "INDODAX", "TOKOCRYPTO"}
BURSA_FX = {"FX", "FX_IDC", "OANDA", "FOREXCOM", "SAXO", "FXCM", "PEPPERSTONE", "ICMARKETS", "CAPITALCOM", "EIGHTCAP"}
AKHIRAN = {"LSE": ".L", "LSIN": ".L", "HKEX": ".HK", "TSE": ".T", "XETR": ".DE", "FWB": ".F", "ASX": ".AX", "SGX": ".SI",
           "TSX": ".TO", "EURONEXT": ".PA", "SIX": ".SW", "KRX": ".KS", "NSE": ".NS", "BSE": ".BO", "MYX": ".KL", "SET": ".BK"}
INDEKS = {"IDX:COMPOSITE": "^JKSE", "IDX:LQ45": "^JKLQ45", "IDX:IDX30": "^JKIDX30", "SP:SPX": "^GSPC", "TVC:SPX": "^GSPC",
          "NASDAQ:NDX": "^NDX", "TVC:NDQ": "^NDX", "NASDAQ:IXIC": "^IXIC", "DJ:DJI": "^DJI", "TVC:DJI": "^DJI",
          "TVC:NI225": "^N225", "XETR:DAX": "^GDAXI", "TVC:DEU40": "^GDAXI", "TVC:UKX": "^FTSE", "FTSE:UKX": "^FTSE",
          "TVC:DXY": "DX-Y.NYB", "TVC:VIX": "^VIX", "CBOE:VIX": "^VIX", "TVC:GOLD": "GC=F", "OANDA:XAUUSD": "GC=F",
          "TVC:SILVER": "SI=F", "TVC:USOIL": "CL=F", "TVC:UKOIL": "BZ=F", "TVC:HSI": "^HSI", "TVC:SX5E": "^STOXX50E"}


NAMA_INDEKS = {"^JKSE": "IHSG", "^JKLQ45": "LQ45", "^JKIDX30": "IDX30", "^GSPC": "S&P 500", "^NDX": "Nasdaq 100", "^IXIC": "Nasdaq",
               "^DJI": "Dow Jones", "^N225": "Nikkei 225", "^GDAXI": "DAX", "^FTSE": "FTSE 100", "DX-Y.NYB": "DXY", "^VIX": "VIX",
               "GC=F": "Emas", "SI=F": "Perak", "CL=F": "Minyak WTI", "BZ=F": "Minyak Brent", "^HSI": "Hang Seng", "^STOXX50E": "Euro Stoxx 50"}


def pasar_yahoo(code: str) -> str:
    if code.endswith(".JK"):
        return "idx"
    if code.endswith("-USD"):
        return "crypto"
    if code.startswith("^") or code.endswith("=X") or code.endswith("=F") or code.startswith("DX-Y"):
        return "lain"
    if re.search(r"\.[A-Z]{1,2}$", code) and not re.search(r"\.[AB]$", code):
        return "lain"  # saham bursa luar (7203.T, 0700.HK, SAP.DE, ...); BRK.A/BRK.B tetap saham AS
    return "us"

# Nama pendek yang biasa diketik tanpa awalan bursa.
INDEKS_PENDEK = {"IHSG": "^JKSE", "JKSE": "^JKSE", "COMPOSITE": "^JKSE", "LQ45": "^JKLQ45", "IDX30": "^JKIDX30",
                 "SPX": "^GSPC", "SP500": "^GSPC", "NDX": "^NDX", "NASDAQ": "^IXIC", "DJI": "^DJI",
                 "VIX": "^VIX", "DXY": "DX-Y.NYB", "NIKKEI": "^N225", "NI225": "^N225", "HSI": "^HSI", "DAX": "^GDAXI",
                 "GOLD": "GC=F", "XAUUSD": "GC=F", "EMAS": "GC=F", "SILVER": "SI=F", "XAGUSD": "SI=F",
                 "USOIL": "CL=F", "WTI": "CL=F", "UKOIL": "BZ=F", "BRENT": "BZ=F"}
MATA_UANG = {"USD", "IDR", "EUR", "JPY", "GBP", "AUD", "NZD", "CAD", "CHF", "SGD", "HKD", "CNY", "CNH", "MYR", "KRW", "THB", "INR"}


def urai_simbol(q: str, pasar: str | None) -> tuple[list[tuple[str, str, str]], str]:
    """Return (kandidat [(market, provider, kode)], nama tampil)."""
    q = (q or "").strip().upper().replace(" ", "")
    if not q:
        raise ValueError("Isi ticker dulu, mis. BBCA, NVDA, BTC, atau IDX:TLKM.")
    if not re.fullmatch(r"[A-Z0-9.^=:_/!&-]{1,40}", q):
        raise ValueError("Ticker tidak valid. Contoh: BBCA, NVDA, BTC, atau IDX:TLKM.")
    pasar = None if pasar in (None, "", "auto") else pasar
    if ":" in q and pasar is None:
        bursa, sym = q.split(":", 1)
        bursa = re.sub(r"_(DLY|MINI|DL)$", "", bursa).replace(" ", "")
        kunci = f"{bursa}:{sym}"
        if kunci in INDEKS:
            return [("lain", "yahoo", INDEKS[kunci])], NAMA_INDEKS.get(INDEKS[kunci], sym)
        if bursa == "IDX":
            return [("idx", "yahoo", sym + ".JK")], sym
        if bursa in BURSA_AS:
            return [("us", "yahoo", sym.replace(".", "-"))], sym
        if bursa in BURSA_KRIPTO:
            base = re.sub(r"(\.P|PERP)$", "", sym)
            base = re.sub(r"(USDT|USDC|BUSD|FDUSD|USD|IDR|BIDR)$", "", base) or base
            return te.resolve(base, "crypto"), base
        if bursa in BURSA_FX and re.fullmatch(r"[A-Z]{6}", sym):
            return [("lain", "yahoo", f"{sym}=X")], sym
        if bursa in AKHIRAN:
            # Bursa di luar IDX/AS (Tokyo, Hong Kong, London, ...): harga tanpa simbol dolar, tanpa jam/acuan New York.
            return [("lain", "yahoo", sym + AKHIRAN[bursa])], sym
        q = sym
    if pasar is None and q in INDEKS_PENDEK:
        kode = INDEKS_PENDEK[q]
        return [("lain", "yahoo", kode)], NAMA_INDEKS.get(kode, q)
    if pasar is None and re.fullmatch(r"[A-Z]{6}", q) and q[:3] in MATA_UANG and q[3:] in MATA_UANG:
        return [("lain", "yahoo", f"{q}=X")], q
    if q.startswith("^") or q.endswith(("=X", "=F", ".JK", "-USD")) or re.search(r"\.[A-Z]{1,3}$", q):
        return [(pasar_yahoo(q), "yahoo", q)], NAMA_INDEKS.get(q) or tk.nama_tampil(q)
    return te.resolve(q, pasar), q


def tf_dari_tradingview(iv: str | None) -> tuple[str, str | None]:
    """Interval TradingView ('15', '240', 'D', '1W', tombol '15m'/'4h') -> timeframe panel + catatan bila dibulatkan.

    Huruf kecil 'm' = menit (tombol TradingView), huruf besar 'M' = bulan.
    """
    if not iv:
        return "1d", None
    raw = str(iv).strip()
    s = raw.upper()
    if s in ("D", "1D"):
        return "1d", None
    if s in ("W", "1W"):
        return "1wk", None
    if raw in ("M", "1M"):
        return "1mo", None
    m = re.fullmatch(r"(\d+)\s*([A-Za-z]?)", raw)
    if not m:
        return "1d", f"timeframe {iv} tidak dikenal, memakai 1D"
    n, u = int(m.group(1)), m.group(2)
    if u in ("S", "s", "T", "t"):
        return "5m", f"{iv} terlalu kecil, memakai 5m"
    if u == "M":
        return "1mo", None if n == 1 else f"{iv} dibulatkan ke 1M"
    menit = n * {"": 1, "m": 1, "h": 60, "H": 60, "d": 1440, "D": 1440, "w": 10080, "W": 10080}.get(u, 1)
    if menit >= 10080:
        return "1wk", None if menit == 10080 else f"{iv} dibulatkan ke 1W"
    if menit >= 1440:
        return "1d", None if menit == 1440 else f"{iv} dibulatkan ke 1D"
    pilihan = [(5, "5m"), (15, "15m"), (30, "30m"), (60, "1h"), (240, "4h")]
    best = min(pilihan, key=lambda x: abs(x[0] - menit))
    return best[1], None if best[0] == menit else f"{iv} dibulatkan ke {best[1]}"


# ==================================================================
# DATA HARGA (cache di memori)
# ==================================================================

_CACHE: dict[tuple[str, str], tuple[float, dict, dict]] = {}
_KUNCI = threading.Lock()
_SEDANG: dict[tuple[str, str], threading.Lock] = {}  # satu pengambilan per (kode, timeframe) pada satu waktu
_GAGAL: dict[tuple[str, str], float] = {}  # kandidat yang baru gagal (mis. NVDA.JK): dilewati 10 menit bila masih ada kandidat lain
GAGAL_TTL = 600
CACHE_MAKS = 200


def _kunci_ambil(kunci: tuple[str, str]) -> threading.Lock:
    with _KUNCI:
        return _SEDANG.setdefault(kunci, threading.Lock())


def _ttl(tf: str) -> int:
    return 60 if tf in ("5m", "15m", "30m", "1h", "4h") else 300


def tarik(kandidat: list[tuple[str, str, str]], tf: str) -> tuple[str, str, dict, dict]:
    errors = []
    for nomor, (mkt, prov, code) in enumerate(kandidat):
        kunci = (code, tf)
        with _KUNCI:
            ada = _CACHE.get(kunci)
            gagal = _GAGAL.get(kunci)
        if gagal and time.time() - gagal < GAGAL_TTL and nomor < len(kandidat) - 1 and not ada:
            errors.append(f"{code}: baru saja tidak ditemukan")
            continue
        if ada and time.time() - ada[0] < _ttl(tf):
            return mkt, code, ada[1], ada[2]
        if OFFLINE:
            b = tk.muat_cache(code)
            if b is not None and tf in ("1wk", "1mo"):
                b = te.resample(b, tf, mkt)
            elif tf != "1d":
                b = None
            if b is not None:
                return mkt, code, b, {"provider": "cache", "name": code}
            errors.append(f"{code}: tidak ada di cache")
            continue
        # Panel samping, kartu, dan badge sering meminta aset yang sama hampir bersamaan: yang kedua menunggu
        # hasil yang pertama, tidak menarik ulang dari Yahoo/Binance.
        with _kunci_ambil(kunci):
            with _KUNCI:
                ada = _CACHE.get(kunci)
            if ada and time.time() - ada[0] < _ttl(tf):
                return mkt, code, ada[1], ada[2]
            try:
                b, meta = (te.fetch_binance if prov == "binance" else te.fetch_yahoo)(code, tf)
            except Exception as exc:  # noqa: BLE001
                b, meta = _yfinance(code, tf, exc)
                if b is None:
                    errors.append(f"{code}: {exc}")
                    with _KUNCI:
                        _GAGAL[kunci] = time.time()
                    continue
            with _KUNCI:
                _CACHE[kunci] = (time.time(), b, meta)
                _GAGAL.pop(kunci, None)
                if len(_CACHE) > CACHE_MAKS:  # buang yang paling lama supaya memori tidak tumbuh terus
                    for k in sorted(_CACHE, key=lambda x: _CACHE[x][0])[:len(_CACHE) - CACHE_MAKS]:
                        _CACHE.pop(k, None)
        return mkt, code, b, meta
    kode = ", ".join(k[2] for k in kandidat)
    if OFFLINE:
        raise LookupError(f"Mode offline: {kode} tidak ada di cache harga.")
    raise LookupError(f"Ticker tidak ditemukan atau data tidak tersedia ({kode}). Rincian: " + "; ".join(errors[:2]))


def _yfinance(code: str, tf: str, err) -> tuple[dict | None, dict]:
    if not code or "USDT" in code:
        return None, {}
    try:
        import yfinance as yf
        iv, rng = te._YAHOO_TF.get(tf, ("1d", "5y"))
        df = yf.download(code, period=rng, interval=iv, auto_adjust=False, progress=False)
        if hasattr(df.columns, "nlevels") and df.columns.nlevels > 1:
            df = df.droplevel(1, axis=1)
        b = tk._dari_dataframe(df)
        if b is not None and tf == "4h":
            b = te.resample(b, "4h")
        return b, {"provider": "Yahoo (yfinance)", "name": code}
    except Exception:  # noqa: BLE001
        return None, {}


def kurs_usd() -> float:
    try:
        _, _, b, _ = tarik([("lain", "yahoo", tk.TICKER_KURS)], "1d")
        return float(b["c"][-1])
    except Exception:  # noqa: BLE001
        return float(tk.muat_pengaturan().get("kurs_cadangan") or 17500)


def _potong(b: dict, n: int) -> dict:
    return {k: v[-n:] for k, v in b.items()} if len(b["c"]) > n else b


def kandidat_acuan(code: str, mkt: str) -> tuple[list, str] | None:
    ac = ws.acuan_untuk(code, mkt)
    if not ac:
        return None
    # Kripto dibandingkan dengan BTC dari sumber yang sama dengan asetnya (cap waktu intraday sejajar).
    kand = te.resolve("BTC", "crypto") if mkt == "crypto" else [("lain", "yahoo", ac[0])]
    return kand, ac[1]


def kekuatan_relatif(code: str, mkt: str, b: dict, tf: str) -> dict | None:
    ka = kandidat_acuan(code, mkt)
    if not ka:
        return None
    try:
        _, _, ba, _ = tarik(ka[0], tf)
    except Exception:  # noqa: BLE001
        return None
    return ws.kekuatan_relatif(b, ba, ka[1], harian=tf in ws.TF_HARIAN, tf=tf)


def _siapkan_acuan(kandidat: list, tf: str) -> None:
    """Tarik data pembanding (IHSG / S&P 500 / BTC) di latar selagi data asetnya ditarik, supaya tidak antre."""
    if OFFLINE or not kandidat:
        return
    mkt, _, code = kandidat[0]
    ka = kandidat_acuan(code, mkt)
    if not ka:
        return

    def kerja():
        try:
            tarik(ka[0], tf)
        except Exception:  # noqa: BLE001
            pass

    threading.Thread(target=kerja, daemon=True).start()


# Simbol yang dianalisa lewat pengganti dengan harga berbeda dari chart asalnya (garis tidak boleh digambar di chart itu).
_PENGGANTI_FUTURES = {"GC=F", "SI=F", "CL=F", "BZ=F"}


def kuotasi_lain(q: str, code: str) -> bool:
    q = (q or "").strip().upper().replace(" ", "")
    if ":" in q:
        bursa, sym = q.split(":", 1)
        if bursa in BURSA_KRIPTO and re.search(r"(IDR|BIDR)$", sym):
            return True  # pasangan rupiah dianalisa lewat USDT
        if code in _PENGGANTI_FUTURES:
            return True  # emas/perak/minyak spot atau CFD dianalisa lewat kontrak futures
    return False


LABEL_GARIS = {
    # Stop = rencana beli batal bila close di bawahnya. Konfirmasi naik = pandangan bearish selesai bila close di atasnya
    # (dulu keduanya bernama "Batal", yang membingungkan karena artinya berlawanan).
    # Label dibuat pendek supaya muat di ruang kosong sebelah kanan candle terakhir.
    "id": {"area": "Area beli", "stop": "Stop", "batal": "Konfirmasi naik", "target": "Target", "target_turun": "Target turun", "naik": "Menguat", "turun": "Melemah",
           "target_pola": "Target pola"},
    "en": {"area": "Buy zone", "stop": "Stop", "batal": "Reversal up", "target": "Target", "target_turun": "Target down", "naik": "Breakout",
           "turun": "Breakdown", "target_pola": "Pattern target"},
}


def lapisan(r: dict, b: dict, mkt: str, tf: str, lain: bool = False, bahasa: str = "id") -> dict:
    """Garis analisa untuk digambar di atas chart (chart panel dan chart TradingView lewat ekstensi).

    Hanya dari data harga: support/resistance, rencana, trendline, pola. Indeks bar mengacu ke `b`;
    `waktu` = waktu buka bar-bar terakhir (detik UTC) supaya chart lain bisa mencocokkan posisi mendatarnya.
    """
    n = len(b["c"])
    en = bahasa == "en"
    N = LABEL_GARIS["en" if en else "id"]
    fp = (lambda x: bh.fp(x, mkt)) if en else (lambda x: te.fmt_price(x, mkt))  # noqa: E731
    bulat = lambda x: float(te.round_price(x, mkt))  # noqa: E731
    harga = float(r["price"])
    sama = lambda x, y: abs(x - y) <= max(abs(y), 1e-12) * 0.003  # noqa: E731

    level = []
    for i, v in enumerate(r["support"][:3]):
        level.append({"k": f"S{i + 1}", "jenis": "s", "harga": bulat(v["price"]), "teks": fp(v["price"]), "sentuh": v.get("touches")})
    for i, v in enumerate(r["resistance"][:3]):
        level.append({"k": f"R{i + 1}", "jenis": "r", "harga": bulat(v["price"]), "teks": fp(v["price"]), "sentuh": v.get("touches")})
    ada = lambda x: any(sama(x, v["harga"]) for v in level)  # noqa: E731

    p = r["plan"]
    zona, garis = None, []
    tambah = lambda k, jenis, x: garis.append({"k": k, "jenis": jenis, "harga": bulat(x), "teks": fp(x)})  # noqa: E731
    try:
        if p["bias"] == "long":
            lo, hi = sorted(p["entry_zone"][:2])
            zona = {"k": N["area"], "dari": bulat(lo), "ke": bulat(hi), "teks": f"{fp(lo)} – {fp(hi)}", "teks_dari": fp(lo), "teks_ke": fp(hi)}
            tambah(N["stop"], "batal", p["stop_loss"])
            for i, x in enumerate(p["targets"][:3]):
                tambah(f"{N['target']} {i + 1}", "target", x)
        elif p["bias"] == "short":
            tambah(N["batal"], "batal", p["stop_loss"])  # bearish batal bila close di atas level ini
            # Target turun yang berimpit dengan garis support atau target pola tidak digambar dua kali.
            target_pola = [c["target"] for c in r["chart_patterns"] if c.get("target") is not None]
            sisa = [x for x in p["targets"][:3] if not ada(x) and not any(sama(x, y) for y in target_pola)]
            for i, x in enumerate(sisa):
                tambah(N["target_turun"] if len(sisa) == 1 else f"{N['target_turun']} {i + 1}", "s", x)
        else:
            if p.get("buy_trigger") is not None:
                tambah(N["naik"], "naik", p["buy_trigger"])
            if p.get("sell_trigger") is not None:
                tambah(N["turun"], "turun", p["sell_trigger"])
    except (KeyError, TypeError, ValueError):
        zona, garis = None, []

    tl = []
    for t in r["trendlines"]:
        try:
            i1, p1 = float(t["i1"]), float(t["p1"])
            if t.get("i2") is not None and t["i2"] != t["i1"]:
                kemiringan = (t["p2"] - p1) / (t["i2"] - i1)
            else:
                kemiringan = (t["value_now"] - p1) / ((n - 1) - i1 or 1)
            akhir = n - 1 + 4  # diproyeksikan beberapa bar ke depan
            if t.get("broken"):
                # Trendline yang sudah ditembus berhenti beberapa bar setelah titik tembus.
                akhir = n - 1
                if t.get("break_idx") is not None:
                    akhir = min(n - 1, int(t["break_idx"]) + 3)
                else:
                    for i in range(int(math.ceil(t.get("i2") or i1)) + 1, n):
                        v = p1 + kemiringan * (i - i1)
                        if (b["c"][i] < v) if t["kind"] == "support" else (b["c"][i] > v):
                            akhir = min(n - 1, i + 3)
                            break
            tl.append({"i1": i1, "p1": p1, "i2": float(akhir), "p2": p1 + kemiringan * (akhir - i1),
                       "jenis": "s" if t["kind"] == "support" else "r", "putus": bool(t.get("broken"))})
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue

    pola = []
    for c in r["chart_patterns"]:
        try:
            segmen = []
            seg = lambda titik, gaya, tebal: segmen.append({"titik": [[float(i), float(v)] for i, v in titik], "gaya": gaya, "tebal": tebal})  # noqa: E731
            if c.get("points"):
                seg(c["points"], "tegas", 2)
            for sisi in ("upper", "lower"):
                if c.get(sisi):
                    seg(c[sisi], "putus", 1)
            if c.get("neckline_pts"):
                (a0, v0), (a1, v1) = c["neckline_pts"][:2]
                seg([[a0, v0], [n - 1, v0 + (v1 - v0) * ((n - 1) - a0) / ((a1 - a0) or 1)]], "pemicu", 1)
            elif c.get("neckline") is not None and c.get("points"):
                seg([[c["start_idx"], c["neckline"]], [n - 1, c["neckline"]]], "pemicu", 1)
            if c.get("pole"):
                seg(c["pole"], "tegas", 2)
            if c.get("box"):
                x0, bawah, x1, atas = c["box"][:4]
                seg([[x0, atas], [x1, atas]], "tegas", 1)
                seg([[x0, bawah], [x1, bawah]], "tegas", 1)
            i0 = max(0, min(n - 1, int(c.get("start_idx", n - 1))))
            i9 = max(i0, min(n - 1, int(c.get("end_idx", n - 1))))
            bias = int(c.get("bias") or 0)
            # Nama pola ditulis di atas harga tertinggi pola (bearish) atau di bawah harga terendahnya (lainnya).
            p_label = float(max(b["h"][i0:i9 + 1])) if bias < 0 else float(min(b["l"][i0:i9 + 1]))
            target = None if c.get("target_hit") else c.get("target")  # target yang sudah tercapai tidak digambar lagi
            nama_pola = bh.nama_pola(c.get("name_id") or "", c.get("name") or "") if en else str(c.get("name_id") or c.get("name") or "")
            pola.append({"nama": nama_pola.split(" (")[0], "bias": bias, "status": (bh.STATUS.get(c.get("status"), c.get("status")) if en else c.get("status")) or "",
                         "segmen": segmen, "i_label": (i0 + i9) / 2, "p_label": p_label,
                         "target": bulat(target) if target is not None else None, "target_teks": fp(target) if target is not None else ""})
        except (KeyError, TypeError, ValueError, ZeroDivisionError):
            continue

    waktu = [int(x) for x in b["t"][-500:]]
    label = bh.LABEL.get(r["label_id"], r["label_id"]) if en else r["label_id"]
    return {"tf": tf, "n": n, "awal": n - len(waktu), "waktu": waktu, "harga": harga, "harga_teks": fp(harga), "skor": int(r["score"]), "label": label,
            "bahasa": "en" if en else "id", "teks": {"target_pola": N["target_pola"]},
            "level": level, "rencana": {"bias": p.get("bias"), "zona": zona, "garis": garis}, "tl": tl, "pola": pola, "kuotasi_lain": bool(lain)}


def riwayat(q: str, tf: str, pasar: str | None, bahasa: str = "id") -> dict:
    """Skor 30 bar terakhir untuk sparkline di panel (diminta terpisah supaya analisa utama tetap cepat)."""
    tf = tf if re.fullmatch(r"(5m|15m|30m|1h|4h|1d|1wk|1mo)", tf or "") else tf_dari_tradingview(tf)[0]
    kandidat, _ = urai_simbol(q, pasar)
    mkt, code, bars, _ = tarik(kandidat, tf)
    b = _potong(bars, MAKS_BAR)
    berjalan = tk.fraksi_berjalan(code, mkt, b["t"][-1], tf)
    titik = ws.riwayat_skor(code, b, mkt, tf, 30, berjalan=berjalan is not None, persisten=False)
    skor = int(te.analyze(b, market=mkt, tf=tf, live_frac=berjalan)["score"])
    satuan = ws.SATUAN_TF.get(tf, "bar")
    kalimat = bh.kalimat_riwayat_en(titik, skor, satuan) if bahasa == "en" else ws.kalimat_riwayat(titik, skor, satuan)
    return {"ok": True, "kode": code, "tf": tf, "titik": [[int(t), s] for t, s in titik], "skor": skor, "kalimat": kalimat, "bahasa": bahasa}


def skor_beli_aset(kandidat, mkt, code, tf, r, b, rs, berjalan, nama) -> dict | None:
    """Skor beli 0–100 (wawasan.skor_beli) dari data HARIAN, apa pun timeframe yang sedang dibuka, supaya angkanya
    sama di Cek aset, panel samping, kartu, dan tab Portofolio. Gagal = None (skor beli tidak ditampilkan)."""
    try:
        if tf == "1d":
            bd, rd, jalan = b, r, berjalan
        else:
            prov = next((pv for m_, pv, c_ in kandidat if c_ == code), "yahoo")
            _, _, bd, _ = tarik([(mkt, prov, code)], "1d")
            bd = _potong(bd, MAKS_BAR)
            jalan = tk.fraksi_berjalan(code, mkt, bd["t"][-1], "1d")
            rd = te.analyze(bd, symbol=nama, market=mkt, tf="1d", live_frac=jalan)
        bw = te.resample(bd, "1wk", mkt)
        rw = te.analyze(bw, market=mkt, tf="1wk") if len(bw["c"]) >= 30 else None
        rs_d = rs if (tf == "1d" and rs is not None) else kekuatan_relatif(code, mkt, bd, "1d")
        return ws.skor_beli(rd, rw, rs_d)
    except Exception:  # noqa: BLE001
        return None


def semua_tf(q: str, pasar: str | None, bahasa: str = "id") -> dict:
    """Kesimpulan semua timeframe (1H, 4H, 1D, 1W, 1M) + skor gabungan + saran. Hanya dari data harga.
    Tiap timeframe ditarik sama persis seperti saat timeframe itu dibuka di panel (skornya sama), paralel dan lewat
    cache panel, jadi berpindah timeframe sesudahnya langsung tampil."""
    kandidat, _ = urai_simbol(q, pasar)
    mkt, code, _, _ = tarik(kandidat, "1d")
    prov = next((pv for m_, pv, c_ in kandidat if c_ == code), "yahoo")
    satu_kandidat = [(mkt, prov, code)]

    def hitung(tf):
        try:
            _, _, b, _ = tarik(satu_kandidat, tf)
        except Exception:  # noqa: BLE001 - mis. tanpa data per jam / mode offline: timeframe itu dilewati
            return tf, None
        b = _potong(b, MAKS_BAR)
        if len(b["c"]) < 30:
            return tf, None
        jalan = tk.fraksi_berjalan(code, mkt, b["t"][-1], tf)
        return tf, te.analyze(b, symbol=code, market=mkt, tf=tf, live_frac=jalan)

    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=5) as ex:
        hasil = {tf: r for tf, r in ex.map(hitung, ws.URUT_TF) if r is not None}
    if "1d" not in hasil:
        raise LookupError(f"Data {code} terlalu sedikit untuk kesimpulan semua timeframe.")
    k = bh.kesimpulan_semua_tf_en(hasil) if bahasa == "en" else ws.kesimpulan_semua_tf(hasil)
    return tk._bersihkan({"ok": True, "kode": code, "pasar": mkt, "bahasa": bahasa, **k})


def analisa(q: str, tf: str, pasar: str | None, ringkas: bool = False, bahasa: str = "id") -> dict:
    """bahasa="en": semua teks (label, tanda, analisa tertulis, sinyal, rencana, garis) dalam bahasa Inggris; angkanya sama."""
    en = bahasa == "en"
    tf_catatan = None
    if tf and not re.fullmatch(r"(5m|15m|30m|1h|4h|1d|1wk|1mo)", tf):
        tf, tf_catatan = tf_dari_tradingview(tf)
    tf = tf or "1d"
    kandidat, tampil = urai_simbol(q, pasar)
    if not ringkas:
        _siapkan_acuan(kandidat, tf)
    mkt, code, bars, meta = tarik(kandidat, tf)
    b = _potong(bars, MAKS_BAR)
    if len(b["c"]) < 30:
        raise LookupError(f"Data {code} terlalu sedikit ({len(b['c'])} bar) untuk timeframe {tf}.")
    nama = tampil if mkt != "crypto" else re.sub(r"(USDT|-USD)$", "", code)
    berjalan = tk.fraksi_berjalan(code, mkt, b["t"][-1], tf)
    r = te.analyze_mtf(te.auto_mtf(b, tf, mkt), symbol=tk.nama_tampil(code) if code.endswith((".JK", "-USD")) else nama,
                       market=mkt, primary=tf, include_series=not ringkas, meta=meta, live_frac=berjalan)
    # Analisa murni dari data harga. Sengaja tidak membaca folder portofolio atau arsip pindai portofolio
    # (posisi, avg, P/L, label Baru) supaya Cek aset, panel samping, dan kartu ekstensi terpisah dari portofolio.
    fl = tk.bendera(r, None, None, b["c"])
    rs = kekuatan_relatif(code, mkt, b, tf) if not ringkas else None
    dekat = ws.dekat_level(r)
    simbol = r["symbol"] or nama
    lap = lapisan(r, b, mkt, tf, kuotasi_lain(q, code), bahasa)  # garis analisa untuk chart; hanya dari data harga
    beli = skor_beli_aset(kandidat, mkt, code, tf, r, b, rs, berjalan, nama)
    if beli and en:
        beli["label"] = bh.LABEL_BELI.get(beli["label"], beli["label"])
    if en:
        narasi = bh.narasi_en(r, simbol, fl, rs, dekat, None, berjalan)
        rencana = bh.rencana_aksi_en(r, dekat)  # tanpa posisi: analisa terpisah dari portofolio
        fl_t, label, tren, aksi = bh.bendera_en(fl, mkt), bh.LABEL.get(r["label_id"], r["label_id"]), bh.TREN.get(r["trend"]["label"], r["trend"]["label"]), bh.aksi_en(r)
        fp, persen = (lambda x: bh.fp(x, mkt)), bh.persen
    else:
        narasi = ws.narasi(r, simbol, fl, rs, dekat, None, berjalan)
        rencana = ws.rencana_aksi(r, dekat)
        fl_t, label, tren, aksi = fl, r["label_id"], r["trend"]["label"], tk.teks_aksi(r)
        fp, persen = (lambda x: te.fmt_price(x, mkt)), ws.persen
    hasil = {"ok": True, "bahasa": bahasa, "q": q, "kode": code, "pasar": mkt, "tf": tf, "tf_catatan": bh.pesan_en(tf_catatan) if en else tf_catatan,
             "nama": meta.get("name") or nama, "bursa": meta.get("exchange") or meta.get("provider"),
             "sumber": meta.get("provider", ""), "waktu_tarik": datetime.now().strftime("%H:%M"),
             "skor": r["score"], "label": label, "tren": tren,
             "aksi": aksi, "bendera": fl_t, "berjalan": berjalan,
             "rs": bh.rs_en(rs) if en else rs, "dekat": dekat, "narasi": narasi, "rencana_aksi": rencana,
             "lapisan": lap, "skor_beli": beli}
    if ringkas:
        # Kartu kecil di halaman chart (ekstensi).
        level = [{"k": k.upper(), "harga": fp(dekat[k]["harga"]), "jarak": persen(dekat[k]["jarak_pct"]),
                  "dekat": bool(dekat[k].get("dekat"))} for k in ("s1", "r1") if dekat.get(k)]
        tanda = [{"teks": f["teks"], "level": f["level"]} for f in fl_t
                 if f["level"] in ("merah", "oranye")][:2]
        hasil["kartu"] = {"simbol": simbol, "kode": code, "pasar": mkt, "skor": r["score"], "label": label,
                          "singkat": narasi.get("singkat") or narasi["inti"], "tf": tf, "level": level,
                          "berjalan": berjalan is not None, "tanda": tanda, "bahasa": bahasa,
                          "langkah": (rencana or {}).get("ringkas") or (rencana or {}).get("judul", ""),
                          "beli": {"skor": beli["skor"], "label": beli["label"]} if beli else None}
    if not ringkas:
        hasil["hasil"] = bh.hasil_en(r) if en else r
    return tk._bersihkan(hasil)


# ==================================================================
# PEMINDAI IHSG (pemindai.py sebagai proses terpisah)
# ==================================================================
# Semua saham IHSG yang lolos saringan likuiditas. Hanya data harga & data publik IDX; tidak membaca portofolio.
# Jalan saat tombol "Pindai IHSG" diklik, dan otomatis sekali tiap hari bursa setelah jam pengaturan
# (ihsg_jam, bawaan 16:30 WIB) selama panel menyala (ihsg_otomatis, bawaan true).

IHSG_DIR = FOLDER / "output" / "ihsg"
_KUNCI_IHSG = threading.Lock()
IHSG = {"proses": None, "coba": None}


def _baca(p: Path, bawaan=None):
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return bawaan


def ihsg_status() -> dict:
    st = _baca(IHSG_DIR / "status.json", {}) or {}
    pr = IHSG["proses"]
    if st.get("berjalan") and pr is not None and pr.poll() is not None:
        # proses anak sudah keluar tapi status masih "berjalan" (mis. galat sebelum sempat menulis status)
        st.update(berjalan=False, ok=False, pesan=st.get("pesan") or "Pindai terhenti sebelum selesai (lihat output/ihsg/log.txt).")
    elif st.get("berjalan") and pr is None:
        # panel dimulai ulang di tengah pindai: proses lama mungkin masih jalan; anggap terhenti setelah 30 menit
        try:
            mulai = datetime.fromisoformat(st.get("mulai") or "")
            basi = (datetime.now(mulai.tzinfo) - mulai).total_seconds() > 1800
        except ValueError:
            basi = True
        if basi:
            st.update(berjalan=False, ok=False, pesan=st.get("pesan") or "Pindai terhenti sebelum selesai.")
    return st


def mulai_ihsg() -> bool:
    with _KUNCI_IHSG:
        if ihsg_status().get("berjalan"):
            return False
        IHSG_DIR.mkdir(parents=True, exist_ok=True)
        # status ditulis (atomik) SEBELUM proses anak mulai, supaya tidak menimpa fase yang sudah ditulis anak
        tmp = IHSG_DIR / "status.json.tmp"
        tmp.write_text(json.dumps({"berjalan": True, "fase": "mulai", "mulai": datetime.now().astimezone().isoformat(timespec="seconds"),
                                   "selesai": None, "ok": None, "pesan": ""}), encoding="utf-8")
        os.replace(tmp, IHSG_DIR / "status.json")
        env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONUTF8": "1"}
        with open(IHSG_DIR / "log.txt", "w", encoding="utf-8") as log:  # anak memegang salinannya sendiri
            IHSG["proses"] = subprocess.Popen([sys.executable, str(FOLDER / "pemindai.py")] + (["--offline"] if OFFLINE else []),
                                              cwd=str(FOLDER), stdout=log, stderr=subprocess.STDOUT, env=env)
        return True


def ihsg_ringkas() -> dict:
    """Untuk /api/status dan badge ekstensi: jumlah tanda baru yang belum dilihat."""
    d = _baca(IHSG_DIR / "ihsg.json") or {}
    dilihat = (_baca(IHSG_DIR / "dilihat.json", {}) or {}).get("id")
    st = ihsg_status()
    return {"ada": bool(d), "id": d.get("id"), "waktu": d.get("waktu"), "baru": int(d.get("baru_total") or 0) if d.get("id") != dilihat else 0,
            "baru_total": int(d.get("baru_total") or 0), "berjalan": bool(st.get("berjalan"))}


TAG_EN = {"volatil": "volatile", "berjalan": "live", "baru_lolos": "newly passes"}


def ihsg_data(bahasa: str) -> dict:
    d = _baca(IHSG_DIR / "ihsg.json")
    out = {"ok": True, "ada": bool(d), "status": ihsg_status(), "ringkas": ihsg_ringkas(),
           "otomatis": bool(tk.muat_pengaturan().get("ihsg_otomatis", True)), "jam": str(tk.muat_pengaturan().get("ihsg_jam") or "16:30")}
    if not d:
        return out
    if bahasa == "en" and d.get("peringatan"):
        m = re.match(r"(\d+) dari (\d+) unduhan harga gagal", d["peringatan"])
        if m:
            d["peringatan"] = f"{m.group(1)} of {m.group(2)} price downloads failed (probably a network or Yahoo problem); try scanning again later."
    if bahasa == "en":
        for a in d.get("aset") or []:
            a["bendera"] = bh.bendera_en(a.get("bendera"), "idx")
            a["label"] = bh.LABEL.get(a.get("label"), a.get("label"))
            a["tren"] = bh.TREN.get(a.get("tren"), a.get("tren"))
            if a.get("skor_beli"):
                a["skor_beli"]["label"] = bh.LABEL_BELI.get(a["skor_beli"].get("label"), a["skor_beli"].get("label"))
            a["langkah"] = a.get("langkah_en") or a.get("langkah")
    for a in d.get("aset") or []:
        a.pop("langkah_en", None)
    out["data"] = d
    return out


def _jadwal_ihsg() -> None:
    """Pindai otomatis sekali tiap hari bursa (Senin–Jumat) setelah jam ihsg_jam WIB, selama panel menyala."""
    from datetime import timedelta, timezone as tz
    wib = tz(timedelta(hours=7))
    while True:
        time.sleep(60)
        try:
            cfg = tk.muat_pengaturan()
            if not cfg.get("ihsg_otomatis", True) or OFFLINE:
                continue
            now = datetime.now(wib)
            jj, mm = (int(x) for x in str(cfg.get("ihsg_jam") or "16:30").split(":")[:2])
            if now.weekday() > 4 or (now.hour, now.minute) < (jj, mm):
                continue
            hari = now.strftime("%Y-%m-%d")
            st = ihsg_status()
            if st.get("berjalan") or (st.get("ok") and (st.get("tanggal_pindai") or st.get("tanggal")) == hari):
                continue
            coba = IHSG["coba"]
            if coba and coba[0] == hari and (coba[1] >= 2 or time.time() - coba[2] < 1800):
                continue  # gagal: dicoba lagi paling banyak sekali, 30 menit kemudian
            IHSG["coba"] = (hari, (coba[1] + 1) if coba and coba[0] == hari else 1, time.time())
            mulai_ihsg()
        except Exception:  # noqa: BLE001
            traceback.print_exc()


# ==================================================================
# PINDAI PORTOFOLIO (latar belakang)
# ==================================================================

_KUNCI_PINDAI = threading.Lock()
PINDAI = {"berjalan": False, "mulai": None, "selesai": None, "ok": None, "pesan": "", "fase": None, "grafik": 0}


def _kabar(fase, **info):
    PINDAI.update(fase=fase, grafik=info.get("jumlah", PINDAI.get("grafik", 0)))


def _pindai():
    PINDAI.update(berjalan=True, mulai=datetime.now().isoformat(timespec="seconds"), selesai=None, ok=None, pesan="", fase="harga", grafik=0)
    buf = io.StringIO()
    try:
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            kode = tk.main(["--offline"] if OFFLINE else [], kabar=_kabar)
        PINDAI.update(ok=(kode == 0), pesan=buf.getvalue()[-600:])
    except BaseException as exc:  # noqa: BLE001
        PINDAI.update(ok=False, pesan=f"{exc}\n{buf.getvalue()[-400:]}")
    finally:
        (FOLDER / "output").mkdir(exist_ok=True)
        (FOLDER / "output" / "log.txt").write_text(buf.getvalue(), encoding="utf-8")
        PINDAI.update(berjalan=False, fase=None, selesai=datetime.now().isoformat(timespec="seconds"))


# ==================================================================
# HTTP
# ==================================================================


class Penangan(BaseHTTPRequestHandler):
    server_version = "AnalisaTeknikal/1.0"

    def log_message(self, fmt, *args):  # tenang
        pass

    def _host_sah(self) -> bool:
        # Tolak DNS rebinding: hanya alamat lokal ini yang dilayani.
        return (self.headers.get("Host") or "") in HOST_SAH

    def _kirim(self, kode: int, isi: bytes, jenis: str, cache: bool = False):
        self.send_response(kode)
        self.send_header("Content-Type", jenis)
        self.send_header("Content-Length", str(len(isi)))
        self.send_header("Cache-Control", "max-age=300" if cache else "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        # Hanya panel ini sendiri dan panel samping ekstensi yang boleh memuatnya dalam iframe.
        self.send_header("Content-Security-Policy", "frame-ancestors 'self' chrome-extension:")
        self.end_headers()
        self.wfile.write(isi)

    def _json(self, data, kode=200):
        self._kirim(kode, json.dumps(data, ensure_ascii=False, allow_nan=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self):
        if not self._host_sah():
            return self._kirim(403, b"forbidden", "text/plain")
        u = urllib.parse.urlparse(self.path)
        qs = {k: v[0] for k, v in urllib.parse.parse_qs(u.query).items()}
        bahasa = pilih_bahasa(qs.get("bahasa"))
        try:
            if u.path in ("/", "/index.html"):
                # Nomor versi aset (dari waktu ubah file web/) supaya browser tidak memakai CSS/JS lama sesudah pembaruan.
                web = FOLDER / "web"
                versi = str(int(max((f.stat().st_mtime for f in web.iterdir() if f.is_file()), default=0)))
                isi = (web / "panel.html").read_text(encoding="utf-8").replace("__V__", versi)
                return self._kirim(200, isi.encode("utf-8"), "text/html; charset=utf-8")
            if u.path.startswith("/web/"):
                return self._file(FOLDER / "web" / Path(u.path[5:]).name, cache=True)
            if u.path.startswith("/chart/"):
                if self._dari_analisa():
                    return self._kirim(403, b"data portofolio tidak tersedia di mode analisa", "text/plain")
                return self._file(FOLDER / "output" / "chart" / Path(u.path[7:]).name)
            if u.path == "/api/status":
                st = {"ok": True, "versi": tk.VERSI, "offline": OFFLINE, "bahasa": bahasa_aktif(), "ihsg": ihsg_ringkas()}
                try:  # versi ekstensi di disk: ekstensi memuat ulang dirinya bila versinya tertinggal (pembaruan otomatis)
                    st["ekstensi"] = json.loads((FOLDER / "ekstensi" / "manifest.json").read_text(encoding="utf-8")).get("version")
                except (OSError, ValueError):
                    pass
                if not self._dari_analisa():  # ekstensi & mode analisa tidak perlu tahu apa pun soal portofolio
                    try:
                        cfg = tk.muat_pengaturan()
                        st["portofolio"] = tk.mode_portofolio(cfg)
                        if st["portofolio"] != "posisi":
                            st["pantau"] = [str(t) for t in cfg.get("tambahan_pantau") or []]
                    except (SystemExit, Exception):  # noqa: BLE001
                        st["portofolio"] = "kosong"
                return self._json(st)
            if u.path == "/api/analisa":
                return self._json(analisa(qs.get("q", ""), qs.get("tf", "1d"), qs.get("pasar"), qs.get("ringkas") == "1", bahasa))
            if u.path == "/api/riwayat":
                return self._json(riwayat(qs.get("q", ""), qs.get("tf", "1d"), qs.get("pasar"), bahasa))
            if u.path == "/api/ihsg":
                return self._json(ihsg_data(bahasa) if qs.get("status") != "1" else {"ok": True, "status": ihsg_status(), "ringkas": ihsg_ringkas()})
            if u.path == "/api/semua_tf":
                return self._json(semua_tf(qs.get("q", ""), qs.get("pasar"), bahasa))
            if u.path in ("/api/portofolio", "/api/pindai") or u.path.startswith("/chart/"):
                if self._dari_analisa():
                    return self._kirim(403, b"data portofolio tidak tersedia di mode analisa", "text/plain")
            if u.path == "/api/portofolio":
                p = FOLDER / "output" / "teknikal.json"
                if not p.exists():
                    return self._json({"ok": True, "ada": False, "pindai": PINDAI})
                data = json.loads(p.read_text(encoding="utf-8"))
                uji = tk.muat_uji_skor()  # hasil uji_skor.py (statistik gabungan, tanpa data posisi)
                if uji:
                    data["uji_skor"] = uji
                if bahasa == "en":
                    data = bh.dump_en(data)
                return self._json({"ok": True, "ada": True, "data": data, "pindai": PINDAI})
            if u.path == "/api/pindai":
                return self._json({"ok": True, **PINDAI})
            return self._kirim(404, b"not found", "text/plain")
        except (ValueError, LookupError) as exc:
            return self._json({"ok": False, "pesan": bh.pesan_en(str(exc)) if bahasa == "en" else str(exc)}, 200)
        except Exception as exc:  # noqa: BLE001
            traceback.print_exc()
            return self._json({"ok": False, "pesan": f"Something went wrong: {exc}" if bahasa == "en" else f"Terjadi kesalahan: {exc}"}, 500)

    def _dari_analisa(self) -> bool:
        """Permintaan dari ekstensi (panel samping, kartu, badge) atau halaman ?embed=1 / ?mandiri=1."""
        asal = (self.headers.get("Origin") or "") + " " + (self.headers.get("Referer") or "")
        if "chrome-extension://" in asal:
            return True
        q = urllib.parse.parse_qs(urllib.parse.urlparse(self.headers.get("Referer") or "").query)
        return q.get("embed") == ["1"] or q.get("mandiri") == ["1"]

    def do_POST(self):
        if not self._host_sah() or self.headers.get("X-Panel") != "1":
            return self._kirim(403, b"forbidden", "text/plain")
        u = urllib.parse.urlparse(self.path)
        if u.path == "/api/bahasa":
            # Ganti bahasa (id/en). Boleh dari panel samping: ini bukan data portofolio.
            nilai = urllib.parse.parse_qs(u.query).get("nilai", [""])[0]
            if nilai not in ("id", "en"):
                return self._json({"ok": False, "pesan": "nilai harus id atau en"}, 400)
            return self._json({"ok": True, "bahasa": atur_bahasa(nilai)})
        if self._dari_analisa():
            return self._kirim(403, b"forbidden", "text/plain")
        if u.path == "/api/pantau":
            try:
                n = min(int(self.headers.get("Content-Length") or 0), 20000)
                daftar = json.loads(self.rfile.read(n).decode("utf-8") or "{}").get("daftar") or []
                if not isinstance(daftar, list):
                    raise ValueError
            except (ValueError, json.JSONDecodeError):
                return self._json({"ok": False, "pesan": "daftar tidak valid"}, 400)
            return self._json(atur_pantau(daftar))
        if u.path == "/api/ihsg/pindai":
            mulai = mulai_ihsg()
            time.sleep(0.05)
            return self._json({"ok": True, "dimulai": mulai, "status": ihsg_status()})
        if u.path == "/api/ihsg/dilihat":
            d = _baca(IHSG_DIR / "ihsg.json") or {}
            if d.get("id"):
                (IHSG_DIR / "dilihat.json").write_text(json.dumps({"id": d["id"]}), encoding="utf-8")
            return self._json({"ok": True, "ringkas": ihsg_ringkas()})
        if u.path == "/api/pindai":
            with _KUNCI_PINDAI:  # dua klik beruntun tidak boleh memicu dua pemindaian sekaligus
                if not PINDAI["berjalan"]:
                    PINDAI.update(berjalan=True, fase="harga")
                    threading.Thread(target=_pindai, daemon=True).start()
            time.sleep(0.05)
            return self._json({"ok": True, **PINDAI})
        return self._kirim(404, b"not found", "text/plain")

    def _file(self, path: Path, cache: bool = False):
        if not path.exists() or not path.is_file():
            return self._kirim(404, b"not found", "text/plain")
        jenis = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
        if jenis.startswith("text/") or jenis in ("application/javascript",):
            jenis += "; charset=utf-8"
        return self._kirim(200, path.read_bytes(), jenis, cache=cache)


def main(argv=None) -> int:
    global OFFLINE
    ap = argparse.ArgumentParser(description="Panel Analisa Teknikal (server lokal)")
    ap.add_argument("--port", type=int, default=PORT)
    ap.add_argument("--no-browser", action="store_true")
    ap.add_argument("--offline", action="store_true", help="pakai cache harga saja")
    args = ap.parse_args(argv)
    OFFLINE = args.offline
    HOST_SAH.update({f"127.0.0.1:{args.port}", f"localhost:{args.port}"})
    srv = ThreadingHTTPServer(("127.0.0.1", args.port), Penangan)
    threading.Thread(target=_jadwal_ihsg, daemon=True).start()
    url = f"http://127.0.0.1:{args.port}/"
    print(f"Panel Analisa Teknikal berjalan di {url}  (Ctrl+C untuk berhenti)")
    if not args.no_browser:
        import webbrowser
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
