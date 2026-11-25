#!/usr/bin/env python3
"""
Analisa Teknikal Portofolio
===========================

Program tambahan yang berdiri sendiri. Ia MEMBACA posisi dari folder
folder portofolio (transaksi.csv lewat ledger.py, plus sektor.json), menarik
harga harian live dari Yahoo Finance, lalu menjalankan mesin analisa teknikal
(ta_engine.py) untuk setiap aset yang sedang dipegang.

Tidak ada satu file pun di folder portofolio yang ditulis atau diubah:
semua hasil disimpan di folder ini (output/, cache/).

Cara pakai
----------
    python3 teknikal.py                 # tarik harga live, analisa semua posisi
    python3 teknikal.py --buka          # sama, lalu buka laporan di browser
    python3 teknikal.py --offline       # pakai harga dari cache terakhir (tanpa internet)
    python3 teknikal.py --hanya BBCA.JK NVDA
    python3 teknikal.py --tanpa-chart   # lebih cepat, tanpa gambar chart per aset

Hasil
-----
    output/teknikal.html                laporan (buka di browser)
    output/teknikal.json                data lengkap, bisa dibaca Claude
    output/chart/<ASET>.png             chart beranotasi per aset
    output/arsip/teknikal_<tanggal>.json  riwayat skor harian
    cache/ohlc/<TICKER>.csv             harga harian terakhir yang berhasil ditarik
"""
from __future__ import annotations

import argparse
import csv
import html
import importlib.util
import json
import math
import os
import re
import sys
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

sys.dont_write_bytecode = True  # jangan pernah menulis __pycache__ ke folder portofolio

import numpy as np  # noqa: E402

FOLDER = Path(__file__).resolve().parent
sys.path.insert(0, str(FOLDER))
import ta_engine as te  # noqa: E402
import wawasan as ws  # noqa: E402
import bahasa as bh  # noqa: E402

VERSI = "1.4"
CHART_VERSI = "9"  # naikkan bila gaya chart PNG berubah, supaya semua chart digambar ulang sekali
TICKER_KURS = "USDIDR=X"
WIB = timezone(timedelta(hours=7))

PENGATURAN_BAWAAN = {
    "bahasa": "id",
    "_petunjuk": "Folder portofolio hanya DIBACA. 'tambahan_pantau' = ticker Yahoo yang ingin ikut dianalisa walau belum dipegang (mis. BBRI.JK, TSLA, BTC-USD).",
    "folder_portfolio": "",
    "tambahan_pantau": [],
    "periode": "2y",
    "kurs_cadangan": 17500,
    # Pemindai IHSG (pemindai.py): pindai otomatis sekali tiap hari bursa setelah ihsg_jam WIB bila panel menyala;
    # ihsg_saringan = "longgar" / "standar" / "ketat" atau objek berisi angka (lihat pemindai.SARINGAN_BAWAAN).
    "ihsg_otomatis": True,
    "ihsg_jam": "16:30",
    "ihsg_saringan": "longgar",
}


# ==================================================================
# PENGATURAN
# ==================================================================


def muat_pengaturan() -> dict:
    path = FOLDER / "pengaturan.json"
    if not path.exists():
        # Paket (buat_paket.py) membawa pengaturan_awal.json, bukan pengaturan.json, supaya memperbarui
        # dengan menimpa seluruh isi folder tidak menghapus daftar pantau dan pilihan bahasa penerima.
        awal = FOLDER / "pengaturan_awal.json"
        teks = None
        if awal.exists():
            try:
                json.loads(awal.read_text(encoding="utf-8"))
                teks = awal.read_text(encoding="utf-8")
            except (OSError, json.JSONDecodeError):
                teks = None
        path.write_text(teks or json.dumps(PENGATURAN_BAWAAN, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SystemExit(f"pengaturan.json tidak terbaca: {exc}")
    hasil = dict(PENGATURAN_BAWAAN)
    hasil.update({k: v for k, v in data.items() if not k.startswith("_")})
    return hasil


# ==================================================================
# POSISI (baca-saja dari folder portofolio)
# ==================================================================


def _muat_ledger(folder: Path):
    """Impor ledger.py milik tracker tanpa menulis apa pun ke foldernya."""
    path = folder / "ledger.py"
    if not path.exists():
        return None
    spec = importlib.util.spec_from_file_location("ledger_portofolio", path)
    modul = importlib.util.module_from_spec(spec)
    sys.modules["ledger_portofolio"] = modul
    spec.loader.exec_module(modul)
    return modul


def _replay_sederhana(path: Path) -> list[dict]:
    """Cadangan bila ledger.py tidak bisa dipakai: rata-rata tertimbang termasuk fee."""
    posisi: dict[str, dict] = {}
    baris = list(csv.DictReader(path.read_text(encoding="utf-8-sig").splitlines()))
    baris.sort(key=lambda r: (r.get("tanggal") or ""))
    for r in baris:
        tipe = (r.get("tipe") or "").strip().upper()
        tk = (r.get("ticker") or "").strip().upper()
        if tipe not in ("SALDO_AWAL", "BELI", "JUAL") or not tk:
            continue
        lembar = float(r.get("lembar") or 0)
        harga = float(r.get("harga") or 0)
        biaya = float(r.get("biaya") or 0)
        mu = (r.get("mata_uang") or "IDR").strip().upper()
        kurs = float(r.get("kurs") or 0) or (1.0 if mu == "IDR" else 0.0)
        p = posisi.setdefault(tk, {"ticker": tk, "lembar": 0.0, "modal_asli": 0.0, "modal_idr": 0.0, "mata_uang": mu})
        if tipe in ("SALDO_AWAL", "BELI"):
            modal = harga * lembar + biaya
            p["lembar"] += lembar
            p["modal_asli"] += modal
            p["modal_idr"] += modal * (kurs or 1.0)
        elif p["lembar"] > 1e-9:
            jual = min(lembar, p["lembar"])
            porsi = jual / p["lembar"]
            p["modal_asli"] -= p["modal_asli"] * porsi
            p["modal_idr"] -= p["modal_idr"] * porsi
            p["lembar"] -= jual
    hasil = []
    for p in posisi.values():
        if p["lembar"] > 1e-9:
            hasil.append({"ticker": p["ticker"], "lembar": p["lembar"], "avg": p["modal_asli"] / p["lembar"],
                          "mata_uang": p["mata_uang"], "modal_idr": p["modal_idr"]})
    return hasil


def baca_posisi(folder: Path, kurs: float) -> tuple[list[dict], str]:
    transaksi = folder / "transaksi.csv"
    if not transaksi.exists():
        return [], f"transaksi.csv tidak ditemukan di {folder}"
    try:
        ledger = _muat_ledger(folder)
        if ledger is not None:
            hasil = ledger.replay(ledger.baca_transaksi(transaksi), kurs)
            posisi = [{"ticker": p.ticker, "lembar": p.lembar, "avg": p.avg_asli, "mata_uang": p.mata_uang,
                       "modal_idr": p.biaya_idr} for p in hasil.posisi_aktif()]
            return posisi, "ledger.py (sama persis dengan tracker)"
    except Exception as exc:  # noqa: BLE001
        print(f"  ! ledger.py tidak bisa dipakai ({exc}); memakai perhitungan cadangan.", file=sys.stderr)
    return _replay_sederhana(transaksi), "perhitungan cadangan (rata-rata tertimbang)"


def folder_portofolio(cfg: dict) -> Path | None:
    """Folder portofolio dari pengaturan; None bila dikosongkan (mode analisa saja, mis. paket untuk orang lain)."""
    s = str(cfg.get("folder_portfolio") or "").strip()
    return Path(os.path.expanduser(s)) if s else None


def mode_portofolio(cfg: dict | None = None) -> str:
    """'posisi' = ada transaksi.csv; 'pantau' = hanya daftar pantau; 'kosong' = belum ada keduanya."""
    cfg = cfg or muat_pengaturan()
    f = folder_portofolio(cfg)
    if f is not None and (f / "transaksi.csv").exists():
        return "posisi"
    return "pantau" if any(str(t).strip() for t in cfg.get("tambahan_pantau") or []) else "kosong"


def baca_sektor(folder: Path) -> dict:
    try:
        return json.loads((folder / "sektor.json").read_text(encoding="utf-8")).get("sektor", {}) or {}
    except (OSError, json.JSONDecodeError):
        return {}


# ==================================================================
# PASAR & DATA HARGA
# ==================================================================


def pasar_dari_ticker(tk: str) -> str:
    if tk.endswith(".JK"):
        return "idx"
    if tk.endswith("-USD"):
        return "crypto"
    return "us"


def nama_tampil(tk: str) -> str:
    if tk.endswith(".JK"):
        return tk[:-3]
    if tk.endswith("-USD"):
        return re.sub(r"\d+$", "", tk[:-4]) or tk[:-4]
    return tk


KELAS = {"idx": "Saham IDX", "us": "Saham/ETF AS", "crypto": "Kripto"}


def _nama_file(tk: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "_", tk)


def simpan_cache(tk: str, b: dict) -> None:
    d = FOLDER / "cache" / "ohlc"
    d.mkdir(parents=True, exist_ok=True)
    tmp = d / (_nama_file(tk) + ".csv.tmp")
    with open(tmp, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(["t", "o", "h", "l", "c", "v"])
        for i in range(len(b["c"])):
            w.writerow([int(b["t"][i]), b["o"][i], b["h"][i], b["l"][i], b["c"][i], b["v"][i]])
    os.replace(tmp, d / (_nama_file(tk) + ".csv"))


def muat_cache(tk: str) -> dict | None:
    p = FOLDER / "cache" / "ohlc" / (_nama_file(tk) + ".csv")
    if not p.exists():
        return None
    rows = [[float(x) for x in r] for r in list(csv.reader(p.read_text().splitlines()))[1:] if r]
    return te.to_bars(rows) if len(rows) >= 30 else None


def _dari_dataframe(df) -> dict | None:
    if df is None or len(df) == 0:
        return None
    kol = {str(c).lower(): c for c in df.columns}
    if "close" not in kol:
        return None
    rows = []
    for idx, r in df.iterrows():
        try:
            o, h, l, c = (float(r[kol[k]]) for k in ("open", "high", "low", "close"))
        except (TypeError, ValueError, KeyError):
            continue
        if any(math.isnan(x) for x in (o, h, l, c)) or c <= 0:
            continue
        v = float(r[kol["volume"]]) if "volume" in kol and r[kol["volume"]] == r[kol["volume"]] else 0.0
        ts = idx.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rows.append([ts.timestamp(), o, h, l, c, v])
    return te.to_bars(rows) if len(rows) >= 30 else None


def tarik_harga(tickers: list[str], periode: str, offline: bool) -> tuple[dict, dict]:
    """Return (bars per ticker, keterangan sumber per ticker)."""
    data: dict[str, dict] = {}
    sumber: dict[str, str] = {}
    if not offline:
        try:
            import yfinance as yf
            print(f"  Menarik harga {len(tickers)} ticker dari Yahoo Finance (yfinance)…")
            df = yf.download(tickers, period=periode, interval="1d", group_by="ticker", auto_adjust=False,
                             progress=False, threads=True)
            for tk in tickers:
                try:
                    sub = df[tk] if len(tickers) > 1 else df
                    if hasattr(sub.columns, "levels") and getattr(sub.columns, "nlevels", 1) > 1:
                        sub = sub.droplevel(0, axis=1)
                    b = _dari_dataframe(sub)
                except Exception:  # noqa: BLE001
                    b = None
                if b is not None:
                    data[tk], sumber[tk] = b, "Yahoo (live)"
        except ImportError:
            print("  yfinance belum terpasang; memakai jalur cadangan (urllib).", file=sys.stderr)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! Unduhan massal gagal ({exc}); mencoba satu per satu.", file=sys.stderr)
        for tk in [t for t in tickers if t not in data]:
            try:
                b, _ = te.fetch_yahoo(tk, "1d")
                data[tk], sumber[tk] = b, "Yahoo (live)"
            except Exception:  # noqa: BLE001
                pass
        for tk, b in data.items():
            try:
                simpan_cache(tk, b)
            except OSError:
                pass
    for tk in [t for t in tickers if t not in data]:
        b = muat_cache(tk)
        if b is not None:
            data[tk] = b
            sumber[tk] = "cache " + datetime.fromtimestamp(b["t"][-1], WIB).strftime("%d %b %Y")
    return data, sumber


def tanggal_bar(t: float) -> str:
    return datetime.fromtimestamp(t + 7 * 3600, timezone.utc).strftime("%Y-%m-%d")


# ==================================================================
# CANDLE YANG MASIH BERJALAN
# ==================================================================
# Logikanya ada di wawasan.py (dipakai juga oleh skill Claude "analisa-teknikal"); nama lama tetap tersedia.
SESI_BURSA, TF_DETIK = ws.SESI_BURSA, ws.TF_DETIK
bursa_untuk, fraksi_berjalan = ws.bursa_untuk, ws.fraksi_berjalan


# ==================================================================
# TANDA BARU vs KONDISI LAMA
# ==================================================================


def kode_tanda(teks: str) -> str:
    """Kunci stabil sebuah tanda (tanpa angka yang berubah tiap hari), untuk membandingkan antar-pindai."""
    awalan = (("Harga tidak bergerak", "basi"), ("Trendline naik baru jebol", "tl_jebol"), ("Trendline turun baru ditembus", "tl_tembus"),
              ("Harga jebol low 20", "jebol_low20"), ("Harga menembus high 20", "tembus_high20"), ("Death cross", "death_cross"),
              ("Golden cross", "golden_cross"), ("Rugi ", "rugi_ma200"), ("Untung ", "untung_ob"), ("Oversold", "oversold"),
              ("Dekat support", "dekat_support"))
    for a, k in awalan:
        if teks.startswith(a):
            return k
    if " sedang terbentuk" in teks:
        return "terbentuk:" + teks.split(" sedang terbentuk")[0]
    if " — " in teks:
        return "pola:" + teks.split(" — ")[0]
    return "lain:" + re.sub(r"[\d.,%$()+\-−]+", "", teks).strip()[:48]


def hari_ini_wib() -> str:
    return datetime.now(WIB).strftime("%Y-%m-%d")


def muat_dasar(out_dir: Path, hari_ini: str) -> tuple[str | None, dict]:
    """Pindai terakhir dari HARI SEBELUMNYA: (tanggal, {ticker: {"skor": s, "tanda": {kode: sejak}}}).

    Dipakai untuk perubahan skor dan untuk menandai tanda yang baru muncul. Beberapa kali pindai di hari
    yang sama tetap dibandingkan dengan hari sebelumnya, jadi tanda baru hari ini tidak hilang.
    """
    for p in sorted((out_dir / "arsip").glob("teknikal_*.json"), reverse=True):
        tgl = p.stem.split("_", 1)[-1]
        if tgl >= hari_ini:
            continue
        try:
            d = json.loads(p.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        hasil = {}
        # Skor dari skala lama (mesin 1.2.x, tanpa "skala_skor") tidak dibandingkan dengan skala sekarang:
        # perubahan skornya akan terbaca besar padahal hanya skalanya yang berganti.
        skala_sama = float(d.get("skala_skor") or 6.0) == float(te.SKALA_SKOR)
        for a in (d.get("aset") or []) + (d.get("pantauan") or []):
            tanda = {}
            for f in a.get("bendera") or []:
                tanda[f.get("kode") or kode_tanda(f.get("teks", ""))] = f.get("sejak") or tgl
            hasil[a.get("ticker")] = {"skor": a.get("skor") if skala_sama else None, "tanda": tanda}
        return tgl, hasil
    return None, {}


def tandai_baru(daftar: list[dict], dasar_aset: dict | None, hari_ini: str) -> list[dict]:
    """Isi kode, baru (belum ada di pindai hari sebelumnya), dan sejak (tanggal pertama muncul)."""
    for f in daftar:
        k = kode_tanda(f["teks"])
        f["kode"] = k
        sejak = (dasar_aset or {}).get("tanda", {}).get(k)
        f["baru"] = sejak is None
        f["sejak"] = sejak or hari_ini
    return daftar


def penting_baru(a: dict) -> bool:
    return any(f.get("baru", True) and f["level"] in ("merah", "oranye") for f in a.get("bendera") or [])


# ==================================================================
# ANALISA PER ASET
# ==================================================================


def bendera(r: dict, pos: dict | None, basi: str | None, closes=None) -> list[dict]:
    """Peringatan & peluang yang relevan dengan posisi. level: merah, oranye, hijau, info."""
    out = []
    mk = r["market"]
    fp = lambda x: te.fmt_price(x, mk)  # noqa: E731
    ind = r["indicators"]
    price = r["price"]

    def add(level, teks):
        out.append({"level": level, "teks": teks})

    if basi:
        add("oranye", f"Harga tidak bergerak sejak {basi} — kemungkinan disuspensi / tidak diperdagangkan")
    for p in r["chart_patterns"]:
        lemah = p["name"] in ("Ascending Channel", "Descending Channel", "Rectangle")
        if p["confirmed"] and p.get("target_hit"):
            # gerakan terukurnya sudah selesai: bukan peringatan/peluang baru lagi, cukup keterangan
            add("info", f"{p['name_id']} — {p['status']}" + te.teks_target(p, fp))
        elif p["confirmed"] and p["bias"] < 0:
            add("oranye" if lemah else "merah", f"{p['name_id']} — {p['status']}" + te.teks_target(p, fp))
        elif p["confirmed"] and p["bias"] > 0:
            add("hijau", f"{p['name_id']} — {p['status']}" + te.teks_target(p, fp))
        elif p["bias"] < 0 and p["name"] in ("Head and Shoulders", "Double Top", "Descending Triangle", "Rising Wedge", "Bear Flag"):
            add("info", f"{p['name']} sedang terbentuk" + (f" — neckline {fp(p['neckline'])}" if p.get("neckline") else ""))
        elif p["bias"] > 0 and p["name"] in ("Inverse Head and Shoulders", "Double Bottom", "Ascending Triangle", "Falling Wedge", "Bull Flag"):
            add("info", f"{p['name']} sedang terbentuk" + (f" — neckline {fp(p['neckline'])}" if p.get("neckline") else ""))
    for tl in r["trendlines"]:
        # Hanya penembusan yang BARU (harga masih di sisi lama trendline ~5 bar lalu).
        # Trendline yang sudah lama ditembus bukan berita lagi.
        if not tl["broken"] or tl["touches"] < 3 or closes is None or len(closes) < 7:
            continue
        n = len(closes)
        garis = lambda x: tl["p1"] + (tl["p2"] - tl["p1"]) * (x - tl["i1"]) / (tl["i2"] - tl["i1"])  # noqa: E731
        lalu = n - 6
        if lalu <= tl["i2"]:
            continue
        if tl["kind"] == "support" and closes[lalu] >= garis(lalu):
            add("merah", f"Trendline naik baru jebol (sekitar {fp(tl.get('break_price', tl['value_now']))})")
        elif tl["kind"] == "resistance" and closes[lalu] <= garis(lalu):
            add("hijau", f"Trendline turun baru ditembus (sekitar {fp(tl.get('break_price', tl['value_now']))})")
    for s in r["signals"]:
        if s["cat"] == "Breakout" and s["score"] < 0:
            add("oranye", s["text"])
        elif s["cat"] == "Breakout" and s["score"] > 0:
            add("hijau", s["text"])
        elif s["text"].startswith("Death cross"):
            add("oranye", s["text"])
        elif s["text"].startswith("Golden cross"):
            add("hijau", s["text"])
    for d in r["divergences"]:
        if not d.get("weak"):
            add("oranye" if d["bias"] < 0 else "hijau", d["name_id"])
    rsi = ind.get("rsi14")
    sma200 = ind.get("sma200")
    if pos:
        pl = (price / pos["avg"] - 1) * 100 if pos["avg"] else 0
        if pl <= -20 and sma200 and price < sma200:
            add("oranye", f"Rugi {abs(pl):.0f}% dan harga masih di bawah MA200 ({fp(sma200)}) — tren belum berbalik")
        if pl >= 25 and rsi and rsi >= 70:
            add("info", f"Untung {pl:.0f}% dengan RSI {rsi:.0f} (overbought) — area wajar untuk mengamankan sebagian")
    if rsi is not None and rsi <= 30:
        add("info", f"Oversold (RSI {rsi:.0f}) — tekanan jual sudah berat, sering diikuti pantulan")
    dk = ws.dekat_level(r)
    if dk.get("s1", {}).get("dekat"):
        add("info", f"Dekat support {fp(dk['s1']['harga'])} — titik pantau, jangan sampai close di bawahnya")
    return out


def teks_aksi(r: dict) -> str:
    mk = r["market"]
    fp = lambda x: te.fmt_price(x, mk)  # noqa: E731
    p = r["plan"]
    if p["bias"] == "long":
        return f"Tren mendukung. Area beli {fp(p['entry_zone'][0])}–{fp(p['entry_zone'][1])}; stop bila close < {fp(p['stop_loss'])}."
    if p["bias"] == "short":
        tg = fp(p["targets"][0]) if p["targets"] else "-"
        return f"Lemah. Jangan tambah dulu; support berikut {tg}; konfirmasi naik bila close > {fp(p['stop_loss'])}."
    return f"Netral. Menguat bila close > {fp(p['buy_trigger'])}; melemah bila close < {fp(p['sell_trigger'])}."


def analisa_aset(tk: str, b: dict, pos: dict | None, sektor: str, kurs: float, basi: str | None, seri: bool = False,
                 acuan: tuple[dict, str] | None = None) -> dict:
    mk = pasar_dari_ticker(tk)
    sym = nama_tampil(tk)
    berjalan = fraksi_berjalan(tk, mk, b["t"][-1], "1d")
    r = te.analyze_mtf(te.auto_mtf(b, "1d", mk), symbol=sym, market=mk, primary="1d", include_series=seri, live_frac=berjalan)
    harga = r["price"]
    info = {
        "ticker": tk, "simbol": sym, "pasar": mk, "kelas": KELAS[mk], "sektor": sektor,
        "harga": harga, "tanggal_harga": tanggal_bar(b["t"][-1]),
        "skor": r["score"], "label": r["label_id"], "tren": r["trend"]["label"],
        "mtf": r.get("mtf", {}).get("summary", []), "konfluensi": r.get("mtf", {}).get("confluence", ""),
        "support": [s["price"] for s in r["support"]], "resistance": [s["price"] for s in r["resistance"]],
        "aksi": teks_aksi(r), "bendera": bendera(r, pos, basi, b["c"]), "analisa": r,
        "berjalan": round(berjalan, 3) if berjalan is not None else None,
        "dekat": ws.dekat_level(r),
        "rs": ws.kekuatan_relatif(b, acuan[0], acuan[1]) if acuan else None,
    }
    try:  # Skor beli 0–100 (1D + 1W dari data harian yang sama, lihat wawasan.skor_beli)
        bw = te.resample(b, "1wk", mk)
        r_w = te.analyze(bw, market=mk, tf="1wk") if len(bw["c"]) >= 30 else None
        info["skor_beli"] = ws.skor_beli(r, r_w, info["rs"])
    except Exception:  # noqa: BLE001
        info["skor_beli"] = None
    if pos:
        kali = kurs if pos["mata_uang"] == "USD" else 1.0
        nilai_idr = pos["lembar"] * harga * kali
        info.update({
            "lembar": pos["lembar"], "avg": pos["avg"], "mata_uang": pos["mata_uang"],
            "pl_pct": (harga / pos["avg"] - 1) * 100 if pos["avg"] else None,
            "nilai_idr": nilai_idr, "modal_idr": pos["modal_idr"],
        })
    return info


def harga_basi(data: dict) -> dict[str, str]:
    """Ticker yang bar terakhirnya tertinggal >= 3 hari dari ticker lain di pasar yang sama."""
    per_pasar: dict[str, float] = {}
    for tk, b in data.items():
        if tk == TICKER_KURS:
            continue
        mk = pasar_dari_ticker(tk)
        per_pasar[mk] = max(per_pasar.get(mk, 0), b["t"][-1])
    hasil = {}
    for tk, b in data.items():
        if tk == TICKER_KURS:
            continue
        terbaru = per_pasar[pasar_dari_ticker(tk)]
        if terbaru - b["t"][-1] >= 3 * 86400 and sum(1 for t2 in data if pasar_dari_ticker(t2) == pasar_dari_ticker(tk)) >= 3:
            hasil[tk] = datetime.fromtimestamp(b["t"][-1] + 7 * 3600, timezone.utc).strftime("%d %b %Y")
    return hasil


# ==================================================================
# LAPORAN HTML
# ==================================================================

BOBOT_LEVEL = {"merah": 3, "oranye": 2, "hijau": 0, "info": 0}

def _sprite_ikon(web: Path) -> str:
    """Ambil sprite ikon dari panel.html supaya laporan statis memakai ikon yang sama persis."""
    try:
        teks = (web / "panel.html").read_text(encoding="utf-8")
        m = re.search(r'<svg[^>]*id="ikon-sprite".*?</svg>', teks, re.S)
        if m:
            return m.group(0)
    except OSError:
        pass
    return ""


def muat_uji_skor() -> dict | None:
    """output/uji_skor.json dari `python3 uji_skor.py` (backtest skor), atau None."""
    p = FOLDER / "output" / "uji_skor.json"
    try:
        return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None
    except (OSError, ValueError):
        return None


def buat_html(dump: dict, bahasa: str = "id") -> str:
    """Laporan statis: tampilan Portofolio yang sama dengan panel, data disematkan, klik baris = chart PNG.

    bahasa="en": dump sudah diterjemahkan (bahasa.dump_en); tampilan ikut berbahasa Inggris."""
    web = FOLDER / "web"
    # Font disimpan lokal di web/; dari output/teknikal.html jalurnya ../web/
    css = (web / "panel.css").read_text(encoding="utf-8").replace('url("fira-', 'url("../web/fira-')
    js = (web / "bahasa.js").read_text(encoding="utf-8") + "\n" + (web / "portofolio.js").read_text(encoding="utf-8")
    data = json.dumps(dump, ensure_ascii=False, allow_nan=False).replace("</", "<\\/")
    judul = html.escape(f"{'Portfolio Technical Analysis' if bahasa == 'en' else 'Analisa Teknikal Portofolio'} · {dump['ringkasan']['waktu']}")
    lain = ("teknikal.html", "Bahasa Indonesia") if bahasa == "en" else ("teknikal_en.html", "English")
    return f"""<!DOCTYPE html>
<html lang="{bahasa}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{judul}</title>
<style>{css}
body {{ overflow-y: auto; }}</style></head>
<body>{_sprite_ikon(web)}<p class="lapbahasa"><a href="{lain[0]}">{lain[1]}</a></p><main class="porto" id="porto"></main>
<script>window.AT_BAHASA = "{bahasa}";</script>
<script>{js}</script>
<script>const DATA = {data};
AT.renderPortofolio(document.getElementById("porto"), DATA, {{ mode: "statis" }});</script>
</body></html>"""


# ==================================================================
# UTAMA
# ==================================================================


def _bersihkan(x):
    if isinstance(x, dict):
        return {k: _bersihkan(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_bersihkan(v) for v in x]
    if isinstance(x, float) and (math.isnan(x) or math.isinf(x)):
        return None
    if isinstance(x, (np.floating,)):
        return float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    return x


def tulis_atomik(path: Path, teks: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(teks, encoding="utf-8")
    os.replace(tmp, path)


def _tanda_chart(b: dict, skor: int, narasi: dict | None = None) -> str:
    """Sidik data yang memengaruhi gambar chart; sama = chart lama masih berlaku, tidak perlu digambar ulang."""
    import hashlib
    teks = hashlib.sha1(json.dumps(narasi or {}, sort_keys=True, ensure_ascii=False).encode("utf-8")).hexdigest()[:12]
    return f"{CHART_VERSI}|{len(b['c'])}|{b['t'][-1]:.0f}|{b['o'][-1]:.8g}|{b['h'][-1]:.8g}|{b['l'][-1]:.8g}|{b['c'][-1]:.8g}|{b['v'][-1]:.8g}|{skor}|{teks}"


def main(argv=None, kabar=None) -> int:
    """kabar(fase, **info): dipanggil panel saat fase berganti ("grafik" = data sudah ditulis, chart sedang dibuat)."""
    ap = argparse.ArgumentParser(description="Analisa teknikal untuk semua posisi di folder portofolio")
    ap.add_argument("--offline", action="store_true", help="pakai harga dari cache, tanpa internet")
    ap.add_argument("--tanpa-chart", action="store_true", help="lewati pembuatan chart PNG (lebih cepat)")
    ap.add_argument("--hanya", nargs="+", metavar="TICKER", help="analisa ticker tertentu saja (format Yahoo, mis. BBCA.JK NVDA BTC-USD)")
    ap.add_argument("--folder-portfolio", help="lokasi folder portofolio (default dari pengaturan.json)")
    ap.add_argument("--buka", action="store_true", help="buka laporan di browser setelah selesai")
    args = ap.parse_args(argv)
    kabar = kabar or (lambda fase, **info: None)

    t0 = time.time()
    cfg = muat_pengaturan()
    folder_pf = Path(os.path.expanduser(args.folder_portfolio)) if args.folder_portfolio else folder_portofolio(cfg)
    print(f"Analisa Teknikal v{VERSI}")
    if folder_pf is None:
        print("  Tanpa folder portofolio (mode analisa saja): hanya daftar pantau")
        posisi, sumber_posisi = [], "tanpa folder portofolio"
    else:
        print(f"  Membaca posisi dari {folder_pf} (baca-saja)")
        posisi, sumber_posisi = baca_posisi(folder_pf, float(cfg.get("kurs_cadangan") or 17500))
    if not posisi and not cfg.get("tambahan_pantau") and not args.hanya:
        print(f"  Tidak ada posisi dan daftar pantau kosong: {sumber_posisi}", file=sys.stderr)
        return 1
    sektor = baca_sektor(folder_pf) if folder_pf is not None else {}
    per_ticker = {p["ticker"]: p for p in posisi}
    pantau = [t.strip().upper() for t in cfg.get("tambahan_pantau") or [] if t.strip() and t.strip().upper() not in per_ticker]
    tickers = list(per_ticker) + pantau
    if args.hanya:
        diminta = {t.upper() for t in args.hanya}
        tickers = [t for t in tickers if t in diminta] + [t for t in diminta if t not in tickers]
        pantau = [t for t in tickers if t not in per_ticker]
    print(f"  {len(per_ticker)} posisi aktif ({sumber_posisi}); {len(pantau)} ticker pantauan")

    # Pembanding pasar untuk kekuatan relatif (IHSG / S&P 500 / BTC)
    acuan_kode = {t: ac for t in tickers if (ac := ws.acuan_untuk(t, pasar_dari_ticker(t)))}
    tambahan = [k for k in sorted({ac[0] for ac in acuan_kode.values()}) if k not in tickers]

    kabar("harga")
    data, sumber = tarik_harga(tickers + [TICKER_KURS] + tambahan, cfg.get("periode", "2y"), args.offline)
    kurs = float(data[TICKER_KURS]["c"][-1]) if TICKER_KURS in data else float(cfg.get("kurs_cadangan") or 17500)
    basi = harga_basi({k: v for k, v in data.items() if k in tickers})
    t_harga = time.time()

    out_dir = FOLDER / "output"
    hari_ini = hari_ini_wib()
    tgl_dasar, dasar = muat_dasar(out_dir, hari_ini)
    dir_chart = out_dir / "chart"
    file_tanda = dir_chart / "_sidik.json"
    try:
        sidik = json.loads(file_tanda.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        sidik = {}
    gambar = not args.tanpa_chart

    kabar("analisa")
    hasil, hasil_pantau, gagal, kandidat = [], [], [], []
    for tk in tickers:
        b = data.get(tk)
        if b is None or len(b["c"]) < 30:
            gagal.append(nama_tampil(tk))
            continue
        # Tanpa folder portofolio (tanpa sektor.json): tulis jenis pasarnya, bukan "Belum diisi".
        sek = sektor.get(tk) or ("Kripto" if tk.endswith("-USD") else "Belum diisi" if folder_pf is not None
                                 else "Saham IDX" if tk.endswith(".JK") else "Saham/ETF AS" if pasar_dari_ticker(tk) == "us" else "Lainnya")
        ac = acuan_kode.get(tk)
        try:
            a = analisa_aset(tk, b, per_ticker.get(tk), sek, kurs, basi.get(tk), seri=gambar,
                             acuan=(data[ac[0]], ac[1]) if ac and ac[0] in data else None)
        except Exception as exc:  # noqa: BLE001
            print(f"  ! {tk}: gagal dianalisa ({exc})", file=sys.stderr)
            gagal.append(nama_tampil(tk))
            continue
        a["sumber"] = sumber.get(tk, "")
        lama = dasar.get(tk)
        a["delta_skor"] = (a["skor"] - lama["skor"]) if lama and lama.get("skor") is not None else None
        tandai_baru(a["bendera"], lama if tgl_dasar else None, hari_ini)
        a["narasi"] = ws.narasi(a["analisa"], a["simbol"], a["bendera"], a["rs"], a["dekat"], per_ticker.get(tk), a["berjalan"])
        a["narasi_en"] = bh.narasi_en(a["analisa"], a["simbol"], a["bendera"], a["rs"], a["dekat"], per_ticker.get(tk), a["berjalan"])
        # Rencana tindakan dengan catatan posisi (hanya di tab Portofolio & laporan statis)
        a["rencana_aksi"] = ws.rencana_aksi(a["analisa"], a["dekat"], per_ticker.get(tk))
        a["rencana_aksi_en"] = bh.rencana_aksi_en(a["analisa"], a["dekat"], per_ticker.get(tk))
        a["chart"] = gambar and (dir_chart / f"{_nama_file(tk)}.png").exists()
        kandidat.append((tk, b, a))
        (hasil if tk in per_ticker else hasil_pantau).append(a)
        print(f"  {a['simbol']:<8} {a['skor']:+4d}  {a['label']:<28} {a['tren']}")

    total = sum(a.get("nilai_idr") or 0 for a in hasil)
    for a in hasil:
        a["bobot"] = (a.get("nilai_idr") or 0) / total * 100 if total else 0
    skor_tt = sum((a.get("nilai_idr") or 0) * a["skor"] for a in hasil) / total if total else 0
    sekarang = datetime.now(WIB)
    semua = hasil + hasil_pantau
    ringkas = {
        "waktu": sekarang.strftime("%d %b %Y %H:%M WIB"), "jumlah": len(hasil), "kurs": kurs,
        "sumber_posisi": sumber_posisi, "total_nilai": total, "skor_tertimbang": skor_tt, "gagal": gagal,
        "jumlah_cache": sum(1 for a in semua if not a["sumber"].startswith("Yahoo")),
        "tanggal_dasar": tgl_dasar,
        "tanda_baru": sum(1 for a in hasil if penting_baru(a)),
        "perlu_perhatian": sum(1 for a in hasil if any(f["level"] in ("merah", "oranye") for f in a["bendera"])),
        "berjalan": sorted({a["pasar"] for a in semua if a.get("berjalan") is not None}),
        "dekat_support": sum(1 for a in hasil if (a.get("dekat") or {}).get("s1", {}).get("dekat")),
        "lebih_lemah": sum(1 for a in hasil if (a.get("rs") or {}).get("rs20") is not None and a["rs"]["rs20"] <= -2),
        "ada_rs": sum(1 for a in hasil if (a.get("rs") or {}).get("rs20") is not None),
    }

    def ringkas_aset(a):
        x = {k: v for k, v in a.items() if k != "analisa"}
        r = a["analisa"]
        x["pola"] = [{"nama": p["name_id"], "status": p["status"], "bias": p["bias"], "target": p.get("target"), "target_hit": bool(p.get("target_hit"))} for p in r["chart_patterns"]]
        x["candle"] = [c["name_id"] for c in r["candles_recent"]]
        x["sinyal"] = r["signals"]
        x["rencana"] = r["plan"]
        x["indikator"] = {k: r["indicators"].get(k) for k in ("rsi14", "adx14", "sma20", "sma50", "sma200", "macd", "macd_signal", "atr_pct", "volume_ratio", "high_52w", "low_52w", "volume_proyeksi")}
        return x

    def tulis_hasil():
        dump = _bersihkan({"versi": VERSI, "mesin": te.VERSION, "skala_skor": te.SKALA_SKOR, "waktu": sekarang.isoformat(timespec="seconds"), "ringkasan": ringkas,
                           "aset": [ringkas_aset(a) for a in hasil], "pantauan": [ringkas_aset(a) for a in hasil_pantau]})
        teks = json.dumps(dump, ensure_ascii=False, indent=1)
        tulis_atomik(out_dir / "teknikal.json", teks)
        uji = muat_uji_skor()  # hasil uji_skor.py (bila ada) ikut ditampilkan di laporan statis, tidak disimpan di teknikal.json
        if uji:
            dump = {**dump, "uji_skor": uji}
        tulis_atomik(out_dir / "teknikal.html", buat_html(dump))
        tulis_atomik(out_dir / "teknikal_en.html", buat_html(bh.dump_en(dump), "en"))  # laporan yang sama dalam bahasa Inggris
        if not args.hanya:  # pindai sebagian tidak boleh menimpa riwayat harian (dipakai sebagai pembanding)
            tulis_atomik(out_dir / "arsip" / f"teknikal_{sekarang:%Y-%m-%d}.json", teks)

    # Fase 1: data & laporan ditulis dulu supaya panel bisa langsung menampilkan hasil.
    tulis_hasil()
    t_analisa = time.time()

    # Fase 2: riwayat skor 30 hari (hanya hari yang belum ada di cache), lalu chart PNG yang berubah.
    kabar("grafik", jumlah=len(kandidat))
    simpan_rw = ws._muat_riwayat()
    for tk, b, a in kandidat:
        try:
            a["riwayat"] = [[int(t), s] for t, s in ws.riwayat_skor(tk, b, a["pasar"], "1d", 30, berjalan=a["berjalan"] is not None, simpan=simpan_rw)]
        except Exception as exc:  # noqa: BLE001
            print(f"  ! riwayat {tk}: {exc}", file=sys.stderr)
            a["riwayat"] = []
        kal = ws.kalimat_riwayat(a["riwayat"], a["skor"])
        if kal:
            a["narasi"] = ws.narasi(a["analisa"], a["simbol"], a["bendera"], a["rs"], a["dekat"], per_ticker.get(tk), a["berjalan"], kal)
            a["narasi_en"] = bh.narasi_en(a["analisa"], a["simbol"], a["bendera"], a["rs"], a["dekat"], per_ticker.get(tk), a["berjalan"],
                                          bh.kalimat_riwayat_en(a["riwayat"], a["skor"]))
    ws._simpan_riwayat(simpan_rw)
    t_riwayat = time.time()
    digambar = 0
    if gambar:
        dir_chart.mkdir(parents=True, exist_ok=True)
        for tk, b, a in kandidat:
            sid = _tanda_chart(b, a["skor"], a["narasi"])
            png = dir_chart / f"{_nama_file(tk)}.png"
            if sidik.get(tk) == sid and png.exists():
                a["chart"] = True  # data & analisa tidak berubah sejak chart terakhir: pakai gambar yang ada
                continue
            try:
                te.plot_chart(b, a["analisa"], str(png), catatan={"simbol": a["simbol"], "narasi": a["narasi"], "dekat": a["dekat"],
                                                                  "rs": a["rs"], "aksi": a.get("rencana_aksi"), "waktu": sekarang.strftime("%d %b %Y %H:%M WIB")})
                a["chart"] = True
                sidik[tk] = sid
                digambar += 1
            except Exception as exc:  # noqa: BLE001
                print(f"  ! chart {tk} gagal: {exc}", file=sys.stderr)
        try:
            tulis_atomik(file_tanda, json.dumps(sidik, indent=0))
        except OSError:
            pass
    tulis_hasil()
    t_akhir = time.time()

    print(f"\nSelesai dalam {t_akhir - t0:.1f} detik (harga {t_harga - t0:.1f} · analisa {t_analisa - t_harga:.1f} · "
          f"riwayat {t_riwayat - t_analisa:.1f} · chart {t_akhir - t_riwayat:.1f}: {digambar} digambar, "
          f"{sum(1 for a in semua if a.get('chart')) - digambar} tidak berubah).")
    print(f"Skor tertimbang {skor_tt:+.0f}; {ringkas['tanda_baru']} aset dengan tanda baru"
          + (f" sejak pindai {tgl_dasar}" if tgl_dasar else "") + f" ({ringkas['perlu_perhatian']} aset punya tanda merah/oranye).")
    if ringkas["ada_rs"]:
        print(f"{ringkas['lebih_lemah']} dari {ringkas['ada_rs']} posisi lebih lemah dari pasarnya (20 hari); {ringkas['dekat_support']} posisi dekat support.")
    if ringkas["berjalan"]:
        print(f"Candle hari ini belum selesai untuk pasar: {', '.join(ringkas['berjalan'])} — volume diproyeksikan, pola candle hari ini diabaikan.")
    if gagal:
        print(f"Tanpa data: {', '.join(gagal)}")
    print(f"Laporan: {out_dir / 'teknikal.html'}")
    if args.buka:
        import webbrowser
        webbrowser.open((out_dir / "teknikal.html").as_uri())
    return 0


if __name__ == "__main__":
    sys.exit(main())
