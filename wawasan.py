"""
Wawasan tambahan di atas hasil mesin analisa (ta_engine):

- kekuatan_relatif : performa aset dibanding pasarnya (IHSG / S&P 500 / BTC)
- riwayat_skor     : skor teknikal di akhir tiap bar untuk 30 bar terakhir (disimpan di cache)
- dekat_level      : apakah harga sedang dekat support/resistance terdekat
- narasi           : penjelasan tertulis dalam bahasa sehari-hari
- fraksi_berjalan  : apakah candle terakhir belum selesai (jam bursa IDX / AS / LSE, kripto 24 jam)

Dipakai oleh teknikal.py (pindai portofolio, chart PNG, laporan), panel.py (Cek aset, ekstensi), dan CLI ta_engine.py
(skill Claude) bila file ini ada di folder yang sama. Hanya butuh ta_engine + pustaka standar.
Tidak mengubah skor: semua di sini bersifat penjelas.
"""
from __future__ import annotations

import json
import os
import re
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ta_engine as te

FOLDER = Path(__file__).resolve().parent
MINUS = "−"

# Pembanding per pasar: (kode Yahoo, nama tampil)
ACUAN = {"idx": ("^JKSE", "IHSG"), "us": ("^GSPC", "S&P 500"), "crypto": ("BTC-USD", "BTC")}
TF_HARIAN = ("1d", "1wk", "1mo")


# ------------------------------------------------------------------
# Format angka (gaya Indonesia: koma desimal, minus asli)
# ------------------------------------------------------------------

def angka(x: float, d: int = 1, tanda: bool = False) -> str:
    s = f"{abs(x):,.{d}f}".replace(",", "_").replace(".", ",").replace("_", ".")
    if round(abs(x), d) == 0:
        return s
    return (MINUS if x < 0 else "+" if tanda else "") + s


def persen(x: float, d: int = 1, tanda: bool = True) -> str:
    return angka(x, d, tanda) + "%"


def skor_teks(s: int) -> str:
    return angka(s, 0, True)


# ------------------------------------------------------------------
# Kekuatan relatif
# ------------------------------------------------------------------

def acuan_untuk(kode: str, pasar: str) -> tuple[str, str] | None:
    """Pembanding untuk sebuah aset; None bila aset itu sendiri pembandingnya atau tidak ada yang cocok."""
    if kode in ("^JKSE", "^GSPC", "BTC-USD") or kode.startswith("^"):
        return None
    if pasar == "crypto" and re.sub(r"[-_/]?(USDT|USDC|FDUSD|BUSD|USD|IDR)$", "", kode.upper()) in ("BTC", "XBT"):
        return None  # BTC dari sumber mana pun (BTCUSDT, BTC-USD) adalah pembandingnya sendiri
    if kode.endswith(".JK") or pasar == "idx":
        return ACUAN["idx"]
    if pasar == "crypto":
        return ACUAN["crypto"]
    if pasar == "us" or kode.endswith(".L"):
        return ACUAN["us"]
    return None


SATUAN_TF = {"1d": "hari", "1wk": "minggu", "1mo": "bulan"}


def kekuatan_relatif(b: dict, ba: dict, nama: str, harian: bool = True, periode=(20, 60), tf: str = "1d") -> dict | None:
    """Perubahan harga aset vs pembanding pada N bar terakhir yang tanggalnya sama-sama ada.

    harian: bar disejajarkan per tanggal (1d/1wk/1mo); intraday disejajarkan per cap waktu persis.
    tf menentukan satuan teks ("20 hari", "20 minggu", "20 bulan", "20 bar")."""
    kunci = (lambda t: int(t // 86400)) if harian else (lambda t: int(t))
    acuan = {kunci(t): c for t, c in zip(ba["t"], ba["c"])}
    pas = [(float(c), float(acuan[kunci(t)])) for t, c in zip(b["t"], b["c"]) if kunci(t) in acuan]
    if len(pas) < 25:
        return None
    hasil = {"acuan": nama, "satuan": SATUAN_TF.get(tf, "bar") if harian else "bar"}
    for n in periode:
        if len(pas) > n:
            (a0, b0), (a1, b1) = pas[-1 - n], pas[-1]
            if a0 > 0 and b0 > 0 and b1 > 0:
                hasil[f"aset{n}"] = (a1 / a0 - 1) * 100
                hasil[f"acuan{n}"] = (b1 / b0 - 1) * 100
                hasil[f"rs{n}"] = ((a1 / a0) / (b1 / b0) - 1) * 100
    rasio = [x / y for x, y in pas if y > 0]
    if len(rasio) >= 25:
        rata = sum(rasio[-20:]) / 20
        hasil["tren"] = "menguat" if rasio[-1] > rata * 1.005 else "melemah" if rasio[-1] < rata * 0.995 else "datar"
    return hasil if "rs20" in hasil else None


def sebutan_rs(rs: float) -> str:
    return "lebih kuat dari" if rs >= 2 else "lebih lemah dari" if rs <= -2 else "sejalan dengan"


def dua_kata(x: str) -> str:
    """Kunci untuk mengenali peristiwa yang sama dalam dua kalimat berbeda: dua kata pertama (huruf kecil);
    untuk trendline cukup katanya ("Trendline resistance tembus …" = "Trendline turun baru ditembus …")."""
    k = x.lower().split()
    return "trendline" if "trendline" in k[:2] else " ".join(k[:2])


def kelas_rs(rs: float) -> str:
    return "kuat" if rs >= 2 else "lemah" if rs <= -2 else "sejalan"


# Arah kekuatan relatif, ditulis supaya tidak terbaca bertentangan (dulu: "lebih kuat dari pasar, dan kekuatan
# relatifnya sedang melemah").
RS_ARAH = {
    ("kuat", "menguat"): ", dan keunggulannya makin lebar", ("kuat", "melemah"): ", tetapi keunggulannya mulai menyusut",
    ("lemah", "menguat"): ", tetapi mulai mengejar", ("lemah", "melemah"): ", dan makin tertinggal",
    ("sejalan", "menguat"): ", dan mulai mengungguli", ("sejalan", "melemah"): ", dan mulai tertinggal",
}
# MACD dalam bahasa awam: (di atas signal?, di atas nol?) -> kalimat
MACD_AWAM = {
    (True, True): "dorongan naik masih kuat (MACD di atas signal dan di atas nol)",
    (True, False): "tekanan turun mulai berkurang (MACD di atas signal, masih di bawah nol)",
    (False, True): "dorongan naik mulai melemah (MACD di bawah signal, masih di atas nol)",
    (False, False): "tekanan turun masih kuat (MACD di bawah signal dan di bawah nol)",
}


# ------------------------------------------------------------------
# Candle yang masih berjalan
# ------------------------------------------------------------------

# Jam perdagangan reguler per bursa (jam lokal). Senin=0 … Jumat=4.
_IDX_SJ = [(9, 0, 12, 0), (13, 30, 16, 0)]
_IDX_JUMAT = [(9, 0, 11, 30), (14, 0, 16, 0)]
SESI_BURSA = {
    "idx": ("Asia/Jakarta", 7, {0: _IDX_SJ, 1: _IDX_SJ, 2: _IDX_SJ, 3: _IDX_SJ, 4: _IDX_JUMAT}),
    "us": ("America/New_York", -5, {d: [(9, 30, 16, 0)] for d in range(5)}),
    "lse": ("Europe/London", 0, {d: [(8, 0, 16, 30)] for d in range(5)}),
}
INDEKS_AS = {"^GSPC", "^NDX", "^IXIC", "^DJI", "^VIX"}
TF_DETIK = {"5m": 300, "15m": 900, "30m": 1800, "1h": 3600, "4h": 14400}


def _zona(nama: str, cadangan_jam: int):
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(nama)
    except Exception:  # noqa: BLE001  (tanpa database zona waktu: pakai selisih tetap)
        return timezone(timedelta(hours=cadangan_jam))


def bursa_untuk(kode: str, pasar: str) -> str | None:
    if kode.endswith(".JK") or kode.startswith("^JK") or pasar == "idx":
        return "idx"
    if kode.endswith(".L"):
        return "lse"
    if pasar == "crypto":
        return "kripto"
    if pasar == "us" or kode in INDEKS_AS:
        return "us"
    return None


def fraksi_berjalan(kode: str, pasar: str, t_akhir: float, tf: str = "1d", sekarang: datetime | None = None) -> float | None:
    """Bagian sesi yang sudah lewat (0–1) bila bar terakhir belum selesai; None bila sudah selesai atau tidak diketahui.

    Bar harian dari Yahoo/Binance memakai tanggal perdagangan (UTC) sebagai cap waktunya.
    Data dianggap final 15 menit setelah bursa tutup.
    """
    now = sekarang or datetime.now(timezone.utc)
    ts = now.timestamp()
    bursa = bursa_untuk(kode, pasar)
    if tf in TF_DETIK:
        lewat = ts - t_akhir
        if not (0 <= lewat < TF_DETIK[tf]):
            return None
        if bursa in SESI_BURSA:  # 1.4.0: bursa sudah tutup = bar intraday terakhir sudah selesai
            nama_z, jam_z, jadwal_z = SESI_BURSA[bursa]
            lk = now.astimezone(_zona(nama_z, jam_z))
            sesi_z = jadwal_z.get(lk.weekday())
            m = lk.hour * 60 + lk.minute
            if not sesi_z or m >= sesi_z[-1][2] * 60 + sesi_z[-1][3] + 15 or m < sesi_z[0][0] * 60 + sesi_z[0][1]:
                return None
        return max(0.0, lewat / TF_DETIK[tf])
    tgl_bar = datetime.fromtimestamp(t_akhir, timezone.utc).date()
    if bursa == "kripto":
        mulai = datetime(tgl_bar.year, tgl_bar.month, tgl_bar.day, tzinfo=timezone.utc).timestamp()
        if tf == "1d":
            panjang = 86400
        elif tf == "1wk":
            panjang = 7 * 86400
        elif tf == "1mo":
            bulan_dpn = datetime(tgl_bar.year + tgl_bar.month // 12, tgl_bar.month % 12 + 1, 1, tzinfo=timezone.utc)
            panjang = bulan_dpn.timestamp() - mulai
        else:
            return None
        lewat = ts - mulai
        return lewat / panjang if 0 <= lewat < panjang else None
    if bursa not in SESI_BURSA:
        return None
    nama, jam, jadwal = SESI_BURSA[bursa]
    lokal = now.astimezone(_zona(nama, jam))
    sesi = jadwal.get(lokal.weekday())
    mnt = lokal.hour * 60 + lokal.minute

    def fraksi_hari_ini() -> float | None:
        if not sesi:
            return None
        total = sum((h2 * 60 + m2) - (h1 * 60 + m1) for h1, m1, h2, m2 in sesi)
        if mnt >= sesi[-1][2] * 60 + sesi[-1][3] + 15:
            return None
        lewat = sum(max(0, min(mnt, h2 * 60 + m2) - (h1 * 60 + m1)) for h1, m1, h2, m2 in sesi)
        return min(1.0, lewat / total)

    if tf == "1d":
        return fraksi_hari_ini() if tgl_bar == lokal.date() else None
    if tf == "1wk":
        # bar mingguan berjalan sampai sesi Jumat selesai. 1.4.0: dibandingkan per minggu (Senin), karena bar minggu
        # yang dimulai Selasa (Senin libur) dulu masih dianggap berjalan pada Senin pagi minggu berikutnya.
        senin_bar = tgl_bar - timedelta(days=tgl_bar.weekday())
        senin_ini = lokal.date() - timedelta(days=lokal.weekday())
        if senin_bar != senin_ini or lokal.weekday() > 4:
            return None
        hari = fraksi_hari_ini()
        if hari is None and lokal.weekday() == 4:
            return None
        return min(1.0, (lokal.weekday() + (hari if hari is not None else 1.0)) / 5)
    if tf == "1mo":
        if (tgl_bar.year, tgl_bar.month) != (lokal.year, lokal.month):
            return None
        # 1.4.0: dihitung per hari bursa (Senin–Jumat); hari bursa terakhir bulan ini setelah tutup = sudah selesai
        import calendar
        jml = calendar.monthrange(lokal.year, lokal.month)[1]
        hari_bursa = [d for d in range(1, jml + 1) if datetime(lokal.year, lokal.month, d).weekday() < 5]
        if not hari_bursa:
            return None
        hari = fraksi_hari_ini()
        lewat_hari = sum(1 for d in hari_bursa if d < lokal.day) + (hari if (lokal.day in hari_bursa and hari is not None) else (1.0 if lokal.day in hari_bursa else 0.0))
        if lokal.day >= hari_bursa[-1] and (lokal.day > hari_bursa[-1] or hari is None):
            return None
        return min(1.0, lewat_hari / len(hari_bursa))
    return None


# ------------------------------------------------------------------
# Dekat support / resistance
# ------------------------------------------------------------------

def dekat_level(r: dict) -> dict:
    """Jarak harga ke S1/R1. 'dekat' = dalam 0,6 ATR, paling jauh 3% (aset yang sangat bergejolak tidak dianggap
    'dekat' hanya karena ATR-nya lebar)."""
    harga, atr = r["price"], r["indicators"].get("atr14") or 0
    batas = min(0.6 * atr, 0.03 * harga) if atr else 0.015 * harga
    out = {}
    if r.get("support"):
        s1 = r["support"][0]["price"]
        out["s1"] = {"harga": s1, "jarak_pct": (s1 / harga - 1) * 100, "dekat": bool(harga - s1 <= batas)}
    if r.get("resistance"):
        r1 = r["resistance"][0]["price"]
        out["r1"] = {"harga": r1, "jarak_pct": (r1 / harga - 1) * 100, "dekat": bool(r1 - harga <= batas)}
    return out


# ------------------------------------------------------------------
# Riwayat skor
# ------------------------------------------------------------------

_KUNCI = threading.Lock()
_MEMORI: dict[tuple, list] = {}
FILE_RIWAYAT = FOLDER / "cache" / "skor_harian.json"
VERSI_RIWAYAT = "1.4.1|1"  # naikkan hanya bila skor mesin berubah (1.3.0: skala skor baru), supaya cache tidak dihitung ulang


def _muat_riwayat() -> dict:
    try:
        d = json.loads(FILE_RIWAYAT.read_text(encoding="utf-8"))
        return d.get("data", {}) if d.get("versi") == VERSI_RIWAYAT else {}
    except (OSError, ValueError):
        return {}


def _simpan_riwayat(data: dict) -> None:
    try:
        FILE_RIWAYAT.parent.mkdir(parents=True, exist_ok=True)
        tmp = FILE_RIWAYAT.with_suffix(".json.tmp")
        tmp.write_text(json.dumps({"versi": VERSI_RIWAYAT, "data": data}, separators=(",", ":")), encoding="utf-8")
        os.replace(tmp, FILE_RIWAYAT)
    except OSError:
        pass


def _skor_pada(b: dict, i: int, market: str, tf: str) -> int | None:
    potong = {k: v[: i + 1] for k, v in b.items()}
    if len(potong["c"]) < 60:
        return None
    try:
        return int(te.analyze(potong, market=market, tf=tf)["score"])
    except Exception:  # noqa: BLE001
        return None


def riwayat_skor(kode: str, b: dict, market: str, tf: str = "1d", n: int = 30, berjalan: bool = False,
                 simpan: dict | None = None, persisten: bool = True) -> list[list]:
    """Skor di akhir tiap bar untuk n bar terakhir: [[waktu_unix, skor], ...].

    Bar yang belum selesai tidak dihitung (skornya bisa berubah sampai close).
    Untuk timeframe harian, hasil per tanggal disimpan di cache/skor_harian.json sehingga pindai berikutnya
    hanya menghitung hari yang baru. `simpan` = isi cache yang sudah dimuat (dipakai pindai massal).
    persisten=False: hanya cache di memori (dipakai panel; panjang datanya berbeda dari pindai portofolio).
    """
    akhir = len(b["c"]) - (2 if berjalan else 1)
    awal = max(60, akhir - n + 1)
    if akhir < awal:
        return []
    if tf != "1d" or not persisten:
        kunci = (kode, tf, float(b["t"][akhir]), len(b["c"]))
        with _KUNCI:
            if kunci in _MEMORI:
                return _MEMORI[kunci]
        hasil = [[float(b["t"][i]), s] for i in range(awal, akhir + 1) if (s := _skor_pada(b, i, market, tf)) is not None]
        with _KUNCI:
            if len(_MEMORI) > 200:
                _MEMORI.clear()
            _MEMORI[kunci] = hasil
        return hasil
    sendiri = simpan is None
    data = _muat_riwayat() if sendiri else simpan
    per_tanggal = data.setdefault(kode, {})
    hasil, berubah = [], False
    for i in range(awal, akhir + 1):
        tgl = datetime.fromtimestamp(b["t"][i], timezone.utc).strftime("%Y-%m-%d")
        s = per_tanggal.get(tgl)
        if s is None:
            s = _skor_pada(b, i, market, tf)
            if s is None:
                continue
            per_tanggal[tgl] = s
            berubah = True
        hasil.append([float(b["t"][i]), s])
    if len(per_tanggal) > 90:  # simpan secukupnya
        for k in sorted(per_tanggal)[:-90]:
            del per_tanggal[k]
    if sendiri and berubah:
        _simpan_riwayat(data)
    return hasil


def fakta_riwayat(titik: list, skor_kini: int):
    """Fakta arah skor untuk kalimat riwayat (dipakai versi Indonesia dan Inggris), atau None bila tidak berarti.

    titik[-k] = skor k bar lalu; titik[0] = awal jendela (sama dengan garis skor di sebelahnya).
    ("cepat", s5) · ("arah", awal, n, ekstrem|None, k) · ("sempat", ekstrem, k) · ("stabil", n)
    Dulu kalimatnya membandingkan dengan 20 bar lalu sementara judul garis skor memakai awal jendela (30 bar),
    jadi terbaca dua titik awal yang berbeda ("−62 → −43" vs "membaik dari −95")."""
    if len(titik) < 6:
        return None
    nilai = [float(x[1]) for x in titik]
    n = len(nilai)
    if abs(skor_kini - nilai[-5]) >= 15:
        return ("cepat", int(nilai[-5]))
    if n < 15:
        return None
    awal = nilai[0]
    eks, k_eks, jauh = None, None, 0.0
    for idx in (min(range(n), key=nilai.__getitem__), max(range(n), key=nilai.__getitem__)):
        d = min(abs(nilai[idx] - awal), abs(nilai[idx] - skor_kini))
        if d > jauh:
            eks, k_eks, jauh = nilai[idx], n - idx, d
    if jauh < 25:
        eks = k_eks = None
    if abs(skor_kini - awal) >= 25:
        return ("arah", int(awal), n, None if eks is None else int(eks), k_eks)
    if eks is not None:
        return ("sempat", int(eks), k_eks)
    if max(nilai + [skor_kini]) - min(nilai + [skor_kini]) <= 20:
        return ("stabil", n)
    return None


def kalimat_riwayat(titik: list, skor_kini: int, satuan: str = "hari") -> str:
    """'Skor membaik dari −80 (5 hari lalu) menjadi −40.' — hanya bila perubahannya berarti.

    Jaraknya ditulis dalam bar ("5 hari lalu", "30 hari lalu") dan titik awalnya sama dengan garis skor di sebelahnya."""
    f = fakta_riwayat(titik, skor_kini)
    if not f:
        return ""
    kini = skor_teks(skor_kini)
    if f[0] == "cepat":
        return f"Skor {'membaik' if skor_kini > f[1] else 'memburuk'} dari {skor_teks(f[1])} (5 {satuan} lalu) menjadi {kini}."
    if f[0] == "arah":
        _, awal, n, eks, k = f
        ekor = f", setelah sempat {'turun' if eks < min(awal, skor_kini) else 'naik'} ke {skor_teks(eks)} ({k} {satuan} lalu)" if eks is not None else ""
        return f"Skor {'membaik' if skor_kini > awal else 'memburuk'} dari {skor_teks(awal)} ({n} {satuan} lalu) menjadi {kini}{ekor}."
    if f[0] == "sempat":
        return f"Skor sempat {'turun' if f[1] < skor_kini else 'naik'} ke {skor_teks(f[1])} ({f[2]} {satuan} lalu), sekarang {kini}."
    return f"Skor relatif stabil di sekitar {kini} dalam {f[1]} {satuan} terakhir."


# ------------------------------------------------------------------
# Rencana tindakan (action plan)
# ------------------------------------------------------------------
# Disusun dari rencana mesin (r["plan"]) dan level support/resistance: daftar "jika … maka …" dengan harga yang
# jelas, supaya pengguna tahu apa yang ditunggu dan apa yang dilakukan bila level itu tercapai.
# Tanpa `pos` (Cek aset, panel samping, kartu ekstensi) isinya murni dari data harga. Dengan `pos` (hanya tab
# Portofolio dan laporan statis) ditambah satu catatan tentang posisi.
# Bahasa: templat T (Indonesia di sini; Inggris di bahasa.py) + fungsi format harga/persen.

T_AKSI_ID = {
    # Tanpa data posisi (Cek aset, panel samping, kartu, daftar pantau) kalimatnya tidak mengandaikan sudah punya.
    "judul_short": "Belum saatnya beli · tren turun selesai bila close di atas {stop}",
    "judul_short_pos": "Jangan tambah dulu · tren turun selesai bila close di atas {stop}",
    "judul_long_zona": "Area beli {lo}–{hi} · stop bila close di bawah {stop}",
    "judul_long_zona_rr": "Area beli {lo}–{hi}, tapi target dekat (R:R {rr}) · stop bila close di bawah {stop}",
    # Versi ringkas (kolom tabel, kartu ekstensi, blok Hari ini): angka pentingnya di depan supaya tidak terpotong.
    "r_short": "Tunggu close > {stop}",
    "r_long_zona": "Area beli {lo}–{hi} · stop < {stop}",
    "r_long_zona_rr": "Area beli {lo}–{hi} (R:R rendah) · stop < {stop}",
    "r_long_atas": "Tunggu koreksi ke {lo}–{hi}",
    "r_wait": "Naik bila close > {naik} · turun bila < {turun}",
    "judul_long_atas": "Tren naik · tunggu koreksi ke {lo}–{hi}",
    "judul_wait": "Tunggu arah · naik bila close di atas {naik}, turun bila di bawah {turun}",
    "s_naik_k": "Close di atas {stop}",
    "s_naik_t": "Tren turun dianggap selesai (garis Konfirmasi naik). Baru setelah itu menyusun rencana beli; area belinya dihitung ulang dari analisa berikutnya.",
    "s_naik_s": "tren turun selesai", "s_naik_n": "konfirmasi naik",
    "s_tahan_k": "Bertahan di support {s1} dan muncul candle pembalikan naik",
    "s_tahan_t": "Tanda awal pantulan, tapi masih spekulatif selama harga di bawah {stop}.",
    "s_jebol_k": "Close di bawah support {s1}",
    "s_jebol_t": "Support jebol: tekanan turun berlanjut{ke}.",
    "s_jebol_ke": " ke sekitar {x}",
    "s_jebol_s": "tekanan turun berlanjut", "s_jebol_n": "support",
    "l_zona_k": "Harga di area beli {lo}–{hi}",
    "l_zona_t": "Boleh beli/tambah bertahap (dibagi 2–3 kali), jangan sekaligus.",
    "l_turun_k": "Harga turun ke area beli {lo}–{hi}",
    "l_turun_t": "Area beli/tambah. Jangan mengejar di harga sekarang.",
    "l_zona_s": "area beli", "l_zona_n": "area beli", "l_masuk_s": "masuk area beli",
    "l_stop_k": "Close di bawah {stop}",
    "l_stop_t": "Rencana beli batal (garis Stop): keluar sesuai stop atau jangan tambah. Jarak area beli ke stop ±{risk}.",
    "l_stop_s": "rencana beli batal", "l_stop_n": "stop",
    "l_t1_k": "Mencapai target 1 di {t1}",
    "l_t1_t": "Area wajar mengamankan sebagian keuntungan (R:R {rr}).",
    "l_t1_s": "area ambil untung sebagian", "l_t1_n": "target 1",
    "l_rr_lemah": " Catatan: target 1 lebih dekat daripada stop (R:R {rr}), jadi peluang ini kurang menarik.",
    "w_naik_k": "Close di atas {naik}",
    "w_naik_t": "Arah naik terkonfirmasi; baru menyusun rencana beli.",
    "w_naik_s": "arah naik terkonfirmasi", "w_naik_n": "pemicu naik",
    "w_turun_k": "Close di bawah {turun}",
    "w_turun_t": "Arah turun: hindari beli.",
    "w_turun_s": "arah turun", "w_turun_n": "pemicu turun",
    "w_antara_k": "Harga di antara keduanya",
    "w_antara_t": "Belum perlu aksi; cukup pantau.",
    "pos_tinjau": " Kalau memegang: ini titik untuk meninjau ulang posisi dan mengurangi risiko.",
    "pos_rugi": "Posisi rugi {pl} dan harga di bawah MA200 ({ma200}): menambah sekarang berarti menambah di tren turun. Untuk kembali ke harga rata-rata ({avg}) perlu naik {perlu}.",
    "pos_untung_ob": "Posisi untung {pl} dengan RSI {rsi} (overbought): wajar mengamankan sebagian.",
    "pos_untung_lemah": "Posisi masih untung {pl}; bila support {s1} jebol, sebagian keuntungan bisa diamankan.",
    "pos_rugi_ringan": "Posisi rugi {pl}; harga rata-rata {avg} (perlu naik {perlu}).",
    "pos_untung": "Posisi untung {pl}; harga rata-rata {avg}.",
    "pantau": "{jarak} {letak} {nama} {harga} · close {sisi}nya: {akibat}",
    "di_atas": "di atas", "di_bawah": "di bawah",
    "pantau_zona": "Di area beli {lo}–{hi}",
}


def rencana_aksi(r: dict, dekat: dict | None = None, pos: dict | None = None, T: dict | None = None,
                 fp=None, pct=None, num=None) -> dict:
    """Rencana tindakan: {"sikap", "judul", "ringkas", "rr_rendah", "punya", "langkah": [{arah, kondisi, tindakan,
    harga, jarak_pct}], "posisi", "pantau": {nama, harga, jarak_pct, jarak_atr, teks}, "dekat"}.

    "ringkas" = judul pendek dengan angka di depan (tabel, kartu, Hari ini). "rr_rendah" = di area beli tapi target 1
    lebih dekat daripada stop (label tidak lagi hijau). "punya" = dihitung dengan data posisi.

    sikap: "hindari" (bearish), "beli" (bullish & harga di area masuk), "tunggu_koreksi" (bullish, di atas area),
    "tunggu" (netral). "dekat" = harga ≤ 0,6 ATR (dan ≤ 3%) dari level keputusan terdekat (atau di area beli): dipakai blok
    "Hari ini" di tab Portofolio. Tidak mengubah skor."""
    T = T or T_AKSI_ID
    mk = r["market"]
    fp = fp or (lambda x: te.fmt_price(x, mk))
    pct = pct or (lambda x, tanda=True: persen(x, tanda=tanda))
    num = num or angka
    p = r["plan"]
    harga = float(r["price"])
    ind = r["indicators"]
    atr = float(ind.get("atr14") or 0) or harga * 0.02
    dekat = dekat or dekat_level(r)
    jarak = lambda x: (x / harga - 1) * 100  # noqa: E731
    sup = [float(s["price"]) for s in r.get("support") or []]
    langkah = []

    def tambah(arah, kode, harga_level=None, isi=None, ekor=""):
        isi = isi or {}
        langkah.append({"arah": arah, "kode": kode, "kondisi": T[kode + "_k"].format(**isi),
                        "tindakan": T[kode + "_t"].format(**isi) + ekor,
                        "harga": harga_level, "jarak_pct": None if harga_level is None else jarak(harga_level),
                        "singkat": T.get(kode + "_s", ""), "nama": T.get(kode + "_n", "")})

    ada_pos = bool(pos and pos.get("avg"))
    rr_rendah = False
    try:
        if p["bias"] == "short":
            stop = float(p["stop_loss"])
            sikap = "hindari"
            judul = T["judul_short_pos" if ada_pos else "judul_short"].format(stop=fp(stop))
            ringkas = T["r_short"].format(stop=fp(stop))
            tambah("naik", "s_naik", stop, {"stop": fp(stop)})
            s1 = dekat.get("s1", {}).get("harga") if dekat.get("s1") else None
            if s1 is not None and s1 < harga:
                lanjut = next((x for x in sup if x < s1 * 0.995), None)
                if lanjut is None:
                    lanjut = next((float(x) for x in p.get("targets") or [] if float(x) < s1 * 0.995), None)
                tambah("tahan", "s_tahan", None, {"s1": fp(s1), "stop": fp(stop)})
                tambah("turun", "s_jebol", s1, {"s1": fp(s1), "ke": T["s_jebol_ke"].format(x=fp(lanjut)) if lanjut else ""},
                       T["pos_tinjau"] if ada_pos else "")
        elif p["bias"] == "long":
            lo, hi = sorted(float(x) for x in p["entry_zone"][:2])
            stop = float(p["stop_loss"])
            di_zona = harga <= hi * 1.002
            sikap = "beli" if di_zona else "tunggu_koreksi"
            isi = {"lo": fp(lo), "hi": fp(hi)}
            rr1 = (p.get("rr") or [None])[0]
            rr_rendah = bool(di_zona and rr1 is not None and rr1 < 1)
            kunci = ("long_zona_rr" if rr_rendah else "long_zona") if di_zona else "long_atas"
            judul = T["judul_" + kunci].format(lo=fp(lo), hi=fp(hi), stop=fp(stop), rr=num(rr1, 1) if rr1 is not None else "—")
            ringkas = T["r_" + kunci].format(lo=fp(lo), hi=fp(hi), stop=fp(stop))
            rr_lemah = T["l_rr_lemah"].format(rr=num(rr1, 1)) if rr1 is not None and rr1 < 1 else ""
            if di_zona:
                tambah("naik", "l_zona", None, isi, rr_lemah)
            else:
                tambah("tahan", "l_turun", hi, isi, rr_lemah)
                langkah[-1]["singkat"], langkah[-1]["nama"] = T["l_masuk_s"], T["l_zona_n"]
            tambah("turun", "l_stop", stop, {"stop": fp(stop), "risk": pct(float(p.get("risk_pct") or 0), tanda=False)},
                   T["pos_tinjau"] if ada_pos else "")
            tg = p.get("targets") or []
            if tg:
                rr = (p.get("rr") or [None])[0]
                tambah("naik", "l_t1", float(tg[0]), {"t1": fp(float(tg[0])), "rr": num(rr, 1) if rr is not None else "—"})
        else:
            naik, turun = float(p["buy_trigger"]), float(p["sell_trigger"])
            sikap = "tunggu"
            judul = T["judul_wait"].format(naik=fp(naik), turun=fp(turun))
            ringkas = T["r_wait"].format(naik=fp(naik), turun=fp(turun))
            tambah("naik", "w_naik", naik, {"naik": fp(naik)})
            tambah("turun", "w_turun", turun, {"turun": fp(turun)}, T["pos_tinjau"] if ada_pos else "")
            tambah("tahan", "w_antara")
    except (KeyError, TypeError, ValueError, IndexError):
        return {}

    # level keputusan terdekat (untuk blok "Hari ini" dan kalimat pantau)
    calon = [x for x in langkah if x["harga"] is not None]
    pantau = None
    if calon:
        x = min(calon, key=lambda x: abs(x["harga"] - harga))
        j_atr = abs(x["harga"] - harga) / atr if atr else None
        pantau = {"nama": x["nama"], "harga": x["harga"], "jarak_pct": x["jarak_pct"], "jarak_atr": j_atr, "arah": x["arah"],
                  "teks": T["pantau"].format(jarak=pct(abs(x["jarak_pct"]), tanda=False), nama=x["nama"], harga=fp(x["harga"]), akibat=x["singkat"],
                                             letak=T["di_atas"] if x["harga"] < harga else T["di_bawah"],
                                             sisi=T["di_bawah"] if x["harga"] < harga else T["di_atas"])}
    if sikap == "beli":
        lo, hi = sorted(float(v) for v in p["entry_zone"][:2])
        pantau = {"nama": T["l_zona_n"], "harga": hi, "jarak_pct": 0.0, "jarak_atr": 0.0, "arah": "naik",
                  "teks": T["pantau_zona"].format(lo=fp(lo), hi=fp(hi))}
    # sama ketatnya dengan label "dekat" S1/R1 (≤ 0,6 ATR, ≤ 3%), supaya blok "Hari ini" tidak berisi separuh portofolio
    dekat_keputusan = bool(pantau and pantau["jarak_atr"] is not None and pantau["jarak_atr"] <= 0.6 and abs(pantau["jarak_pct"]) <= 3)

    catatan = ""
    if ada_pos:
        avg = float(pos["avg"])
        pl = (harga / avg - 1) * 100
        ma200, rsi = ind.get("sma200"), ind.get("rsi14")
        perlu = pct((avg / harga - 1) * 100, tanda=False) if harga < avg else ""
        if pl <= -20 and ma200 and harga < ma200:
            catatan = T["pos_rugi"].format(pl=pct(abs(pl), tanda=False), ma200=fp(ma200), avg=fp(avg), perlu=perlu)
        elif pl >= 25 and rsi and rsi >= 70:
            catatan = T["pos_untung_ob"].format(pl=pct(pl, tanda=False), rsi=num(rsi, 0))
        elif pl > 0 and sikap == "hindari" and dekat.get("s1"):
            catatan = T["pos_untung_lemah"].format(pl=pct(pl, tanda=False), s1=fp(dekat["s1"]["harga"]))
        elif pl < 0:
            catatan = T["pos_rugi_ringan"].format(pl=pct(abs(pl), tanda=False), avg=fp(avg), perlu=perlu)
        else:
            catatan = T["pos_untung"].format(pl=pct(pl, tanda=False), avg=fp(avg))
    for x in langkah:
        x.pop("singkat", None)
        x.pop("nama", None)
    return {"sikap": sikap, "judul": judul, "ringkas": ringkas, "rr_rendah": rr_rendah, "punya": ada_pos, "langkah": langkah,
            "posisi": catatan, "pantau": pantau, "dekat": dekat_keputusan}


# ------------------------------------------------------------------
# Narasi
# ------------------------------------------------------------------

def _huruf_kecil_awal(s: str) -> str:
    """Huruf awal kecil untuk teks di tengah kalimat, kecuali singkatan (RSI, MACD) dan nama pola (Double Top, Bear Flag)."""
    if not s or s[:2].isupper():
        return s
    kata = [k for k in s.split()[1:3] if k != "&"]
    if kata and kata[0][:1].isupper():
        return s
    return s[:1].lower() + s[1:]


def narasi(r: dict, simbol: str, bendera: list | None = None, rs: dict | None = None, dekat: dict | None = None,
           pos: dict | None = None, berjalan: float | None = None, riwayat: str = "") -> dict:
    """Penjelasan tertulis: {"inti": satu baris, "paragraf": [kondisi, skenario]}."""
    mk = r["market"]
    fp = lambda x: te.fmt_price(x, mk)  # noqa: E731
    ind = r["indicators"]
    harga = r["price"]
    skor = int(r["score"])
    tren = r["trend"]["label"]
    harian = r.get("tf") in TF_HARIAN
    dekat = dekat or dekat_level(r)

    # --- kondisi
    ma = []
    if ind.get("sma50"):
        ma.append(("di atas" if harga > ind["sma50"] else "di bawah") + " MA50")
    if ind.get("sma200"):
        ma.append(("di atas" if harga > ind["sma200"] else "di bawah") + " MA200")
    if len(ma) == 2 and ma[0].split()[1] == ma[1].split()[1]:
        posisi_ma = f"harga {ma[0].rsplit(' ', 1)[0]} MA50 dan MA200"
    else:
        posisi_ma = "harga " + " tapi ".join(ma) if ma else ""
    frasa = f"{simbol} bergerak sideways" if tren == "Sideways" else f"{simbol} dalam {_huruf_kecil_awal(tren)}"
    arah = tren.lower().split()[0] if tren else ""
    # Kalimat pertama = kesimpulan (apa artinya bagi pembaca), baru sesudahnya alasannya.
    ra = rencana_aksi(r, dekat) or {}
    sikap = ra.get("sikap")
    lawan = bool(r.get("lawan_tren"))  # skor berlawanan dengan tren 50 bar (label "… awal")
    sb = SATUAN_TF.get(r.get("tf"), "bar")
    if sikap == "hindari":
        k0 = (f"{simbol} mulai melemah walau tren 50 {sb} masih naik: tahan dulu pembelian baru." if lawan
              else f"{simbol} masih dalam tekanan turun: belum ada alasan teknikal untuk membeli." if arah == "downtrend"
              else f"{simbol} cenderung melemah: belum ada alasan teknikal untuk membeli.")
    elif sikap == "beli":
        k0 = (f"{simbol} " + ("mulai menunjukkan pembalikan naik dan berada di area beli" if lawan else "berada di area beli")
              + (", tapi peluangnya kurang menarik karena target dekat" if ra.get("rr_rendah") else "") + ".")
    elif sikap == "tunggu_koreksi":
        k0 = (f"{simbol} " + ("mulai menunjukkan pembalikan naik" if lawan else "dalam kondisi bullish")
              + ", tapi harga sudah di atas area beli: lebih baik menunggu koreksi.")
    elif sikap == "tunggu":
        k0 = f"{simbol} belum punya arah yang jelas: tunggu konfirmasi."
    else:
        k0 = ""
    label_pendek = _huruf_kecil_awal(r["label_id"].split(" (")[0])
    alasan = []
    if lawan:
        # Skor dan tren berlawanan: sebut keduanya dan jelaskan dari mana skornya, supaya tidak terbaca bertentangan.
        searah = sorted((x for x in r.get("signals", []) if x["score"] * skor > 0), key=lambda x: -abs(x["score"]))[:2]
        alasan = [x["text"].split(" — ")[0] for x in searah]
        k1 = (f"Tren 50 {sb} masih {'turun' if skor > 0 else 'naik'}" + (f" ({posisi_ma})" if posisi_ma else "")
              + f", tetapi skor teknikal {skor_teks(skor)} ({label_pendek})"
              + (" karena " + " dan ".join(_huruf_kecil_awal(x) for x in alasan) if alasan else "") + ".")
    else:
        if ma and ((arah == "uptrend" and all(x.startswith("di bawah") for x in ma))
                   or (arah == "downtrend" and all(x.startswith("di atas") for x in ma))):
            # tren (struktur swing) dan posisi harga terhadap MA berlawanan: sebut keduanya dengan jelas
            k1 = f"{simbol} masih dalam {_huruf_kecil_awal(tren)}, tapi {posisi_ma.replace('harga ', 'harga sudah ', 1)}."
        else:
            k1 = frasa + (f": {posisi_ma}" if posisi_ma else "") + "."
        k1 += f" Skor teknikal {skor_teks(skor)} ({label_pendek})."

    rsi = ind.get("rsi14")
    if rsi is None:
        mom = ""
    elif rsi >= 70:
        mom = f"RSI {angka(rsi, 0)} sudah overbought, momentum kuat tapi rawan koreksi"
    elif rsi >= 55:
        mom = f"momentum masih positif (RSI {angka(rsi, 0)})"
    elif rsi > 45:
        mom = f"momentum netral (RSI {angka(rsi, 0)})"
    elif rsi > 30:
        mom = f"momentum lemah (RSI {angka(rsi, 0)})"
    else:
        mom = f"RSI {angka(rsi, 0)} sudah oversold — tekanan jual berat, pantulan teknikal bisa terjadi"
    if ind.get("macd") is not None and ind.get("macd_signal") is not None:
        # arti awamnya dulu, istilahnya di dalam kurung
        macd = MACD_AWAM[(ind["macd"] > ind["macd_signal"], ind["macd"] > 0)]
        mom = f"{mom}; {macd}" if mom else macd
    k2 = (mom[:1].upper() + mom[1:] + ".") if mom else ""

    # peristiwa penting: tanda baru dulu, lalu pola terkonfirmasi / divergence
    peristiwa = []
    for f in (bendera or []):
        if f.get("baru", True) and f["level"] in ("merah", "oranye", "hijau"):
            peristiwa.append(f["teks"].split(" — ")[0])
    for p in r.get("chart_patterns", []):
        if p.get("confirmed") and not any(p["name_id"] in x for x in peristiwa):
            peristiwa.append(f"{p['name_id']} {p['status']}" + te.teks_target(p, fp))
    for d in r.get("divergences", []):
        if not d.get("weak") and not any(d["name_id"][:20] in x for x in peristiwa):
            peristiwa.append(d["name_id"].split(" (")[0])
    peristiwa = [x for x in peristiwa if not any(dua_kata(a_) in x.lower() for a_ in alasan)]  # sudah disebut sebagai alasan skor
    k3 = ("Yang perlu dicatat: " + "; ".join(_huruf_kecil_awal(x) for x in peristiwa[:2]) + ".") if peristiwa else ""

    k4 = ""
    if rs and rs.get("rs20") is not None:
        hari = rs.get("satuan") or "hari"
        gerak = lambda x: ("naik " if x >= 0 else "turun ") + persen(abs(x), tanda=False)  # noqa: E731
        k4 = (f"Dalam 20 {hari} terakhir {simbol} {gerak(rs['aset20'])} sementara {rs['acuan']} {gerak(rs['acuan20'])} — "
              f"{sebutan_rs(rs['rs20'])} pasar")
        k4 += RS_ARAH.get((kelas_rs(rs["rs20"]), rs.get("tren")), "") + "."

    # --- skenario
    p = r["plan"]
    s_txt = []
    if dekat.get("s1"):
        s1 = dekat["s1"]
        s_txt.append(f"support terdekat {fp(s1['harga'])} ({persen(s1['jarak_pct'])}{', sangat dekat' if s1['dekat'] else ''})")
    if dekat.get("r1"):
        r1 = dekat["r1"]
        s_txt.append(f"resistance {fp(r1['harga'])} ({persen(r1['jarak_pct'])}{', sangat dekat' if r1['dekat'] else ''})")
    j1 = ("Level penting: " + ", ".join(s_txt) + ".") if s_txt else ""
    if p["bias"] == "long":
        j2 = (f"Selama bertahan di atas {fp(p['stop_loss'])}, area {fp(p['entry_zone'][0])}–{fp(p['entry_zone'][1])} "
              f"adalah area beli saat koreksi" + (f" dengan target terdekat {fp(p['targets'][0])}" if p.get("targets") else "") + ".")
    elif p["bias"] == "short":
        tg = p.get("targets") or []
        j2 = (f"Selama harga di bawah {fp(p['stop_loss'])}, tekanan turun masih dominan"
              + (f"; support berikutnya {fp(tg[0])}" + (f" lalu {fp(tg[1])}" if len(tg) > 1 else "") if tg else "")
              + f". Pembalikan baru terkonfirmasi bila close di atas {fp(p['stop_loss'])}.")
    else:
        j2 = (f"Arah belum jelas: menguat bila close di atas {fp(p['buy_trigger'])}, "
              f"melemah bila close di bawah {fp(p['sell_trigger'])}.")
    j3 = ""
    if pos and pos.get("avg") and harga < pos["avg"]:
        j3 = f"Untuk kembali ke harga rata-rata posisi ({fp(pos['avg'])}) dibutuhkan kenaikan {persen((pos['avg'] / harga - 1) * 100, tanda=False)}."
    mtf = (r.get("mtf") or {}).get("summary") or []
    j4 = ""
    if len(mtf) > 1:
        besar = mtf[-1]
        sama = (besar["score"] >= 20 and skor >= 20) or (besar["score"] <= -20 and skor <= -20)
        lawan = (besar["score"] >= 20 and skor <= -20) or (besar["score"] <= -20 and skor >= 20)
        nama_tf = {"1wk": "mingguan", "1d": "harian", "4h": "4 jam", "1mo": "bulanan"}.get(besar["tf"], besar["tf"])
        if sama:
            j4 = f"Timeframe {nama_tf} searah (skor {skor_teks(besar['score'])}), jadi sinyalnya lebih bisa dipercaya."
        elif lawan:
            j4 = f"Timeframe {nama_tf} berlawanan (skor {skor_teks(besar['score'])}) — bisa jadi hanya koreksi/pantulan di dalam tren yang lebih besar."
    j5 = ""
    if berjalan is not None:
        j5 = f"Catatan: candle {'hari ini' if harian else 'terakhir'} belum selesai, jadi angka masih bisa berubah sampai close."

    kondisi = " ".join(x for x in (k0, k1, k2, riwayat, k3, k4) if x)
    skenario = " ".join(x for x in (j1, j2, j4, j3, j5) if x)

    # inti satu baris (kartu ekstensi & judul chart)
    bagian = [tren]
    if rsi is not None:
        bagian.append("oversold" if rsi <= 30 else "overbought" if rsi >= 70 else "momentum " + ("positif" if rsi >= 55 else "lemah" if rsi <= 45 else "netral"))
    singkat = " · ".join(bagian)  # tanpa level: kartu ekstensi menampilkan S1/R1 sendiri
    if dekat.get("s1"):
        bagian.append(f"S1 {fp(dekat['s1']['harga'])} ({persen(dekat['s1']['jarak_pct'])})")
    return {"inti": " · ".join(bagian), "singkat": singkat, "paragraf": [kondisi, skenario]}


# ------------------------------------------------------------------
# Kesimpulan semua timeframe + skor gabungan (1.4.0)
# ------------------------------------------------------------------
# Bobot skor gabungan. Di uji data lama (Jun 2025 – Nov 2026), gabungan 1D + 1W memisahkan hasil 20 hari lebih baik
# daripada 1D saja (beda kelompok skor tertinggi vs terendah 4,1 vs 2,9 poin), jadi harian dan mingguan diberi bobot
# terbesar; 1H/4H (belum bisa diuji karena tidak ada riwayat intraday panjang) hanya pelengkap waktu masuk.
BOBOT_TF = {"1h": 0.10, "4h": 0.15, "1d": 0.35, "1wk": 0.30, "1mo": 0.10}
URUT_TF = ["1h", "4h", "1d", "1wk", "1mo"]
NAMA_TF = {"1h": "1H", "4h": "4H", "1d": "1D", "1wk": "1W", "1mo": "1M"}

T_SEMUA_ID = {
    "semua_naik": "Semua timeframe searah naik: tren kuat dan sehat dari jangka pendek sampai panjang.",
    "naik_rehat": "Tren besar naik; harian/jangka pendek sedang istirahat (konsolidasi), belum ada tanda berbalik.",
    "koreksi_dalam_naik": "Tren besar (mingguan/bulanan) naik, tetapi harian/jangka pendek sedang koreksi.",
    "naik_awal": "Mulai menguat dari bawah: harian dan jangka pendek naik, tren besar belum ikut.",
    "semua_turun": "Semua timeframe searah turun: tekanan jual dominan di semua jangka waktu.",
    "turun_rehat": "Tren besar turun; harian/jangka pendek sedang tertahan, belum ada tanda pembalikan.",
    "pantul_dalam_turun": "Tren besar (mingguan/bulanan) turun, tetapi harian/jangka pendek sedang memantul.",
    "turun_awal": "Mulai melemah: harian dan jangka pendek turun, tren besar belum ikut turun.",
    "campur": "Timeframe saling berlawanan atau netral: belum ada arah yang jelas.",
    "s_semua_naik": ["Posisi yang ada bisa ditahan selama close 1D bertahan di atas {batal}.",
                     "Beli baru jangan dikejar; tunggu koreksi ke {zona}."],
    "s_naik_rehat": ["Tahan posisi; beli tambahan paling aman dekat support {s1} ({s1_jarak}).",
                     "Lanjutan naik terkonfirmasi bila close 1D di atas {r1}."],
    "s_koreksi_dalam_naik": ["Koreksi di dalam tren naik bisa jadi kesempatan mencicil beli dekat {s1} ({s1_jarak}).",
                             "Tunggu tanda berbalik di timeframe kecil (skor 4H/1H kembali ≥ +20) sebelum masuk; batal bila close 1D di bawah {batal}."],
    "s_naik_awal": ["Pembalikan naik masih awal: kalau masuk, mulai kecil dan tambah bila skor 1W ikut di atas +20.",
                    "Batal bila close 1D kembali di bawah {s1}."],
    "s_semua_turun": ["Hindari beli baru; posisi yang ada pertimbangkan dikurangi.",
                      "Tren baru dianggap berbalik bila close 1D di atas {konfirmasi} dan skor 1W membaik."],
    "s_turun_rehat": ["Belum ada pembalikan: hindari beli selama harga di bawah {r1}.",
                      "Bila support {s1} jebol, tekanan turun kemungkinan berlanjut."],
    "s_pantul_dalam_turun": ["Pantulan di dalam tren turun: jangan dikejar; kenaikan ke {r1} bisa dipakai untuk mengurangi posisi.",
                             "Beli baru tunggu skor 1W ikut di atas +20."],
    "s_turun_awal": ["Lindungi posisi: pelemahan berlanjut bila close 1D di bawah {s1}.",
                     "Jangan menambah sampai close 1D kembali di atas {r1}."],
    "s_campur": ["Tunggu arah: close 1D di atas {naik} = skenario naik, di bawah {turun} = skenario turun.",
                 "Kalau tetap masuk, pakai ukuran kecil dan stop yang jelas."],
    "s_risiko": "Atur ukuran posisi dari jarak ke stop (mis. rugi maksimal 1–2% modal per posisi).",
    "tanpa_level": "-",
}


def label_skor(skor: float) -> str:
    """Label untuk skor gabungan (ambang sama dengan skor per timeframe)."""
    return ("Bullish kuat" if skor >= 50 else "Bullish" if skor >= 20 else "Netral / tunggu konfirmasi" if skor > -20
            else "Bearish" if skor > -50 else "Bearish kuat")


def kesimpulan_semua_tf(hasil: dict, T: dict | None = None, fp=None, pct=None, rencana=None) -> dict:
    """hasil = {tf: hasil analyze()} untuk 1H, 4H, 1D, 1W, 1M (yang tersedia saja).

    Mengembalikan {"skor", "label", "kasus", "kesimpulan", "saran": [...], "tf": [{tf, nama, skor, label, tren,
    sikap, ringkas, rr_rendah, berjalan}], "horizon": {pendek, menengah, panjang}, "bobot"}."""
    T = T or T_SEMUA_ID
    tfs = [tf for tf in URUT_TF if tf in hasil]
    if not tfs:
        raise ValueError("tidak ada timeframe")
    mk = hasil[tfs[0]]["market"]
    fp = fp or (lambda x: te.fmt_price(x, mk))
    pct = pct or (lambda x: persen(x))
    rencana = rencana or (lambda r: rencana_aksi(r))
    baris = []
    for tf in tfs:
        r = hasil[tf]
        try:
            ra = rencana(r) or {}
        except Exception:  # noqa: BLE001
            ra = {}
        baris.append({"tf": tf, "nama": NAMA_TF[tf], "skor": int(r["score"]), "label": r["label_id"],
                      "tren": r["trend"]["label"], "sikap": ra.get("sikap"), "ringkas": ra.get("ringkas") or ra.get("judul", ""),
                      "rr_rendah": bool(ra.get("rr_rendah")), "berjalan": "bar_berjalan" in r})
    w = sum(BOBOT_TF[tf] for tf in tfs)
    skor = int(round(sum(BOBOT_TF[tf] * float(hasil[tf]["score"]) for tf in tfs) / w))

    def rata(xs):
        v = [float(hasil[t]["score"]) for t in xs if t in hasil]
        return sum(v) / len(v) if v else None

    hz = {"pendek": rata(["1h", "4h"]), "menengah": rata(["1d"]), "panjang": rata(["1wk", "1mo"])}
    arah = {k: (0 if v is None else 1 if v >= 20 else -1 if v <= -20 else 0) for k, v in hz.items()}
    ap, am, ak = arah["panjang"], arah["menengah"], arah["pendek"]
    ada_pendek = hz["pendek"] is not None
    if ap > 0 and am > 0 and (ak > 0 or not ada_pendek):
        kasus = "semua_naik"
    elif ap < 0 and am < 0 and (ak < 0 or not ada_pendek):
        kasus = "semua_turun"
    elif ap > 0 and (am < 0 or ak < 0):
        kasus = "koreksi_dalam_naik"
    elif ap < 0 and (am > 0 or ak > 0):
        kasus = "pantul_dalam_turun"
    elif ap > 0:
        kasus = "naik_rehat"
    elif ap < 0:
        kasus = "turun_rehat"
    elif am > 0 and ak >= 0:
        kasus = "naik_awal"
    elif am < 0 and ak <= 0:
        kasus = "turun_awal"
    else:
        kasus = "campur"

    # Level dari timeframe harian (timeframe keputusan); bila tidak ada, dari timeframe terbesar yang tersedia.
    rd = hasil.get("1d") or hasil[tfs[-1]]
    p, harga = rd["plan"], float(rd["price"])
    sup = [float(s["price"]) for s in rd.get("support") or []]
    res = [float(s["price"]) for s in rd.get("resistance") or []]
    a = float(rd["indicators"].get("atr14") or harga * 0.02)
    s1 = sup[0] if sup else harga - 2 * a
    r1 = res[0] if res else harga + 2 * a
    # Batas batal bawaan di bawah S1 (S2 bila cukup dekat, atau S1 − 0,5 ATR), supaya "cicil dekat S1" dan "batal
    # di bawah ..." tidak menyebut harga yang sama (25 Nov: dulu keduanya S1 bila rencana 1D bukan beli).
    s2 = sup[1] if len(sup) > 1 and s1 - sup[1] <= 2 * a else None
    batal = s2 if s2 is not None else te.round_price(s1 - 0.5 * a, mk)
    lv = {"s1": fp(s1), "s1_jarak": pct((s1 / harga - 1) * 100), "r1": fp(r1), "naik": fp(r1), "turun": fp(s1),
          "zona": fp(s1), "batal": fp(batal), "konfirmasi": fp(r1)}
    try:
        if p["bias"] == "long":
            lo, hi = sorted(float(x) for x in p["entry_zone"][:2])
            lv.update(zona=f"{fp(lo)}–{fp(hi)}", batal=fp(float(p["stop_loss"])))
        elif p["bias"] == "short":
            lv.update(konfirmasi=fp(float(p["stop_loss"])))
        else:
            lv.update(naik=fp(float(p["buy_trigger"])), turun=fp(float(p["sell_trigger"])))
    except (KeyError, TypeError, ValueError):
        pass
    saran = [x.format(**lv) for x in T["s_" + kasus]] + [T["s_risiko"]]
    return {"skor": skor, "label": label_skor(skor), "kasus": kasus, "kesimpulan": T[kasus], "saran": saran,
            "tf": baris, "horizon": {k: (None if v is None else int(round(v))) for k, v in hz.items()},
            "bobot": {tf: BOBOT_TF[tf] for tf in tfs}}


# ------------------------------------------------------------------
# Skor beli 0–100 (1.4.0)
# ------------------------------------------------------------------
# Satu angka "seberapa layak dibeli sekarang" dari sisi teknikal saja (tanpa valuasi/fundamental/berita).
# Sengaja hanya dari data harian (1D + 1W hasil resample harian) supaya angkanya sama di Cek aset, panel samping,
# kartu ekstensi, tab Portofolio, dan bisa diuji ke data lama (uji_skor.py).
BOBOT_BELI = {"tren": 40, "lokasi": 20, "rr": 15, "rs": 15, "konfirmasi": 10}
LABEL_BELI = [(80, "Menarik"), (70, "Layak dicicil"), (40, "Pantau"), (0, "Belum layak")]
# Syarat label (25 Nov 2026). Di uji data lama, menaikkan angka batas saja tidak memperbaiki hasil; yang membantu adalah
# syarat tambahan. "Menarik" (≥ 80): tren 1D+1W rata-rata ≥ +40, R:R target 1 ≥ 1,5, dan untuk saham IDX nilai
# transaksi rata-rata 20 hari ≥ Rp5 M (saham tipis mudah digerakkan; syarat ini tidak bisa diuji karena cache uji hanya
# berisi saham likuid). IDX: +5,0 poin vs pasar dalam 20 hari dan rencana beli +0,22R (sebelumnya +2,5 / −0,02R).
# "Layak dicicil" (70–79): tren rata-rata ≥ +20. Yang tidak memenuhi syarat dibatasi di 79 / 69.
SYARAT_MENARIK = {"tren": 40, "rr": 1.5, "nilai_idr": 5e9}
SYARAT_DICICIL = {"tren": 20}


def label_beli(skor: int) -> str:
    return next(nama for batas, nama in LABEL_BELI if skor >= batas)


def _jepit(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


def skor_beli(r_d: dict, r_w: dict | None = None, rs: dict | None = None) -> dict:
    """r_d = analyze() harian, r_w = analyze() mingguan (resample harian), rs = kekuatan_relatif harian (rs20).

    Komponen (poin maksimal): tren 1D+1W (40), lokasi harga terhadap area beli/support dan RSI (20),
    imbal hasil vs risiko rencana 1D (15), kekuatan relatif 20 hari vs pasar (15), konfirmasi momentum & volume (10).
    Bila rata-rata skor 1D dan 1W masih negatif, skor dibatasi 59; "Menarik" dan "Layak dicicil" punya syarat tambahan
    (SYARAT_MENARIK, SYARAT_DICICIL). "batas": {"ke": 59|69|79, "alasan": [{"k": "tren"|"rr"|"nilai", "nilai", "min"}]}.
    Mengembalikan {"skor", "label", "komponen": {nama: poin}, "maks": BOBOT_BELI}."""
    B = BOBOT_BELI
    harga = float(r_d["price"])
    ind = r_d["indicators"]
    atr = float(ind.get("atr14") or 0) or harga * 0.02
    rsi = ind.get("rsi14")
    p = r_d["plan"]
    s_d = float(r_d["score"])
    s_w = float(r_w["score"]) if r_w else s_d
    k = {}
    # 1. Tren: rata-rata skor 1D dan 1W (−100..100) -> 0..1
    k["tren"] = B["tren"] * _jepit((0.5 * s_d + 0.5 * s_w + 100) / 200)
    # 2. Lokasi: di area beli / dekat support = baik; jauh di atas area beli atau RSI jenuh beli = mengejar harga.
    #    Catatan 25 Nov: karena batas atas area beli rencana 1D hampir selalu = harga, komponen ini dalam praktik
    #    berarti "rencana beli aktif dan RSI < 70" (20/20) vs RSI ≥ 70 (6/20). Dua rumus kontinu (jarak ke S1/EMA21,
    #    potongan bila menempel di bawah R1) sudah diuji pada data yang sama dan memisahkan hasil 20 hari lebih buruk
    #    (beda kelompok 80–100 vs 0–39: +2,3 rumus ini, +0,3 kontinu, +1,0 dengan potongan R1), jadi rumus ini dipertahankan.
    sup = [float(s["price"]) for s in r_d.get("support") or []]
    res = [float(s["price"]) for s in r_d.get("resistance") or []]
    if p["bias"] == "long":
        lo, hi = sorted(float(x) for x in p["entry_zone"][:2])
        jauh = (harga - hi) / atr
        lok = 1.0 if jauh <= 0.002 * harga / atr else 0.6 if jauh <= 1 else 0.3 if jauh <= 2 else 0.1
    elif p["bias"] == "short":
        lok = 0.2
    else:
        dekat_s = bool(sup) and (harga - sup[0]) <= atr
        dekat_r = bool(res) and (res[0] - harga) <= atr
        lok = 0.7 if dekat_s and not dekat_r else 0.3 if dekat_r and not dekat_s else 0.5
    if rsi is not None and rsi >= 70:
        lok = min(lok, 0.3)
    k["lokasi"] = B["lokasi"] * lok
    # 3. Imbal hasil vs risiko (R:R target 1 rencana 1D)
    rr1 = (p.get("rr") or [None])[0] if p["bias"] == "long" else None
    if rr1 is not None:
        k["rr"] = B["rr"] * _jepit(rr1 / 2.0)
    else:
        k["rr"] = B["rr"] * (0.4 if p["bias"] == "wait" else 0.1)
    # 4. Kekuatan relatif 20 hari: −10% .. +10% -> 0..1 (tanpa pembanding = tengah)
    rs20 = (rs or {}).get("rs20")
    k["rs"] = B["rs"] * (_jepit((rs20 + 10) / 20) if rs20 is not None else 0.5)
    # 5. Konfirmasi: jumlah poin mentah Momentum + Volume harian, −3 .. +3 -> 0..1
    mv = sum(float(x["score"]) for x in r_d.get("signals") or [] if x.get("cat") in ("Momentum", "Volume"))
    k["konfirmasi"] = B["konfirmasi"] * _jepit((mv + 3) / 6)
    skor = int(round(sum(k.values())))
    tren = 0.5 * s_d + 0.5 * s_w
    batas = None
    # Selama rata-rata tren 1D+1W masih negatif, paling tinggi "Pantau" (59): selaras dengan saran semua timeframe
    # ("beli baru tunggu tren besar membaik"). Di uji data lama batas ini tidak mengubah hasil per kelompok.
    if tren < 0 and skor > 59:
        skor, batas = 59, {"ke": 59, "alasan": [{"k": "tren", "nilai": round(tren), "min": 0}]}
    if skor >= 80:
        alasan = []
        if tren < SYARAT_MENARIK["tren"]:
            alasan.append({"k": "tren", "nilai": round(tren), "min": SYARAT_MENARIK["tren"]})
        if rr1 is None or rr1 < SYARAT_MENARIK["rr"]:
            alasan.append({"k": "rr", "nilai": None if rr1 is None else round(rr1, 1), "min": SYARAT_MENARIK["rr"]})
        nilai = float(ind.get("volume_avg20") or 0) * harga
        if r_d.get("market") == "idx" and nilai < SYARAT_MENARIK["nilai_idr"]:
            alasan.append({"k": "nilai", "nilai": round(nilai), "min": SYARAT_MENARIK["nilai_idr"]})
        if alasan:
            skor, batas = 79, {"ke": 79, "alasan": alasan}
    if 70 <= skor and tren < SYARAT_DICICIL["tren"]:
        skor, batas = 69, {"ke": 69, "alasan": [{"k": "tren", "nilai": round(tren), "min": SYARAT_DICICIL["tren"]}]}
    return {"skor": skor, "label": label_beli(skor), "komponen": {n: round(v, 1) for n, v in k.items()}, "maks": dict(B),
            "dibatasi": batas is not None, "batas": batas}
