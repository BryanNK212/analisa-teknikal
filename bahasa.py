"""
Versi bahasa Inggris untuk Analisa Teknikal.

Mesin (ta_engine.py), wawasan.py, dan teknikal.py tetap menulis dalam bahasa Indonesia (juga dipakai skill Claude).
Modul ini membuat padanan Inggrisnya:

- hasil_en(r)            : salinan hasil mesin dengan semua teks dalam bahasa Inggris
- teks(t, pasar)         : terjemahan satu teks buatan mesin/teknikal.py (sinyal, tanda, catatan rencana, ...)
- bendera_en(daftar, mk) : daftar tanda (merah/oranye/hijau/info)
- aksi_en(r)             : ringkasan aksi satu baris
- narasi_en(...)         : analisa tertulis (dibuat langsung dalam bahasa Inggris, bukan diterjemahkan kalimat per kalimat)
- dump_en(dump)          : hasil pindai portofolio (output/teknikal.json) dalam bahasa Inggris
- kalimat_riwayat_en(...), rs_en(rs), pesan_en(pesan), fp(harga, pasar)

Angka mengikuti gaya Inggris: titik desimal, koma ribuan (harga IDX 5,300 bukan 5.300).
Hanya butuh ta_engine + wawasan + pustaka standar. Tidak mengubah skor apa pun.
"""
from __future__ import annotations

import copy
import re

import ta_engine as te
import wawasan as ws

MINUS = "−"

# ------------------------------------------------------------------
# Angka & harga
# ------------------------------------------------------------------


def fp(x, mk: str) -> str:
    """Harga dalam gaya Inggris. IDX: 5,300 (mesin menulis 5.300); pasar lain sudah gaya Inggris."""
    s = te.fmt_price(x, mk)
    return s.replace(".", ",") if mk == "idx" else s


def angka(x: float, d: int = 1, tanda: bool = False) -> str:
    s = f"{abs(x):,.{d}f}"
    if round(abs(x), d) == 0:
        return s
    return (MINUS if x < 0 else "+" if tanda else "") + s


def persen(x: float, d: int = 1, tanda: bool = True) -> str:
    return angka(x, d, tanda) + "%"


def skor_teks(s: int) -> str:
    return angka(s, 0, True)


_RIBUAN_IDX = re.compile(r"(?<![\d.,$])(\d{1,3}(?:\.\d{3})+)(?![\d]|\.\d)")


def _angka_idx(t: str) -> str:
    """5.300 -> 5,300 (hanya untuk teks pasar IDX, tempat titik selalu pemisah ribuan)."""
    return _RIBUAN_IDX.sub(lambda m: m.group(1).replace(".", ","), t)


# ------------------------------------------------------------------
# Kamus
# ------------------------------------------------------------------

LABEL = {"Bullish kuat": "Strongly bullish", "Bullish": "Bullish", "Netral / tunggu konfirmasi": "Neutral / wait for confirmation",
         "Bearish": "Bearish", "Bearish kuat": "Strongly bearish",
         "Bullish awal (tren masih turun)": "Early bullish (trend still down)", "Bearish awal (tren masih naik)": "Early bearish (trend still up)"}
RS_ARAH = {
    ("kuat", "menguat"): ", and its lead is widening", ("kuat", "melemah"): ", but its lead is narrowing",
    ("lemah", "menguat"): ", but it is starting to catch up", ("lemah", "melemah"): ", and it is falling further behind",
    ("sejalan", "menguat"): ", and it is starting to outperform", ("sejalan", "melemah"): ", and it is starting to lag",
}
MACD_AWAM = {
    (True, True): "upside momentum is still strong (MACD above signal and above zero)",
    (True, False): "selling pressure is easing (MACD above signal, still below zero)",
    (False, True): "upside momentum is fading (MACD below signal, still above zero)",
    (False, False): "selling pressure is still strong (MACD below signal and below zero)",
}
SATUAN_TUNGGAL = {"hari": "day", "minggu": "week", "bulan": "month", "bar": "bar"}
TREN = {"Uptrend kuat": "Strong uptrend", "Uptrend": "Uptrend", "Downtrend kuat": "Strong downtrend", "Downtrend": "Downtrend",
        "Sideways": "Sideways"}
STRUKTUR = {"campuran": "mixed", "higher high & higher low (naik)": "higher highs & higher lows (rising)",
            "lower high & lower low (turun)": "lower highs & lower lows (falling)",
            "higher low, tapi lower high (menyempit)": "higher low but lower high (narrowing)",
            "higher high, tapi lower low (melebar/volatil)": "higher high but lower low (widening / volatile)"}
KATEGORI = {"Tren": "Trend", "Momentum": "Momentum", "Divergence": "Divergence", "Volume": "Volume", "Breakout": "Breakout",
            "Volatilitas": "Volatility", "Pola chart": "Chart pattern", "Candlestick": "Candlestick", "Trendline": "Trendline",
            "Lokasi": "Location"}
KONFLUENSI = {
    "Semua timeframe bullish — konfluensi kuat": "All timeframes bullish — strong confluence",
    "Semua timeframe bearish — konfluensi kuat": "All timeframes bearish — strong confluence",
    "Timeframe kecil berlawanan dengan timeframe besar — kemungkinan koreksi/pantulan di dalam tren besar":
        "Lower timeframe disagrees with the higher one — likely a pullback/bounce within the bigger trend",
    "Campuran — sebagian timeframe netral": "Mixed — some timeframes neutral",
}
BIAS = {"Beli saat koreksi": "Buy on weakness", "Belum saatnya beli": "Not time to buy yet", "Tunggu konfirmasi": "Wait for confirmation"}
STATUS = {
    "terkonfirmasi": "confirmed", "terbentuk, menunggu tembus neckline": "formed, waiting for a neckline break",
    "terkonfirmasi (neckline jebol)": "confirmed (neckline broken)", "terkonfirmasi (neckline tembus)": "confirmed (neckline broken)",
    "masih di dalam pola": "still inside the pattern", "breakout ke atas": "breakout to the upside",
    "tembus atas (pola wedge gagal)": "broke out upward (wedge failed)", "breakdown ke bawah": "breakdown to the downside",
    "breakout": "breakout", "konsolidasi (tunggu breakout)": "consolidating (wait for the breakout)",
}

# Nama pola: Indonesia (name_id) -> Inggris. Kunci = name_id persis seperti ditulis mesin.
NAMA_POLA = {
    # pola chart
    "Double Top (puncak ganda)": "Double Top", "Double Bottom (lembah ganda)": "Double Bottom",
    "Head & Shoulders (pembalikan turun)": "Head & Shoulders (bearish reversal)",
    "Inverse Head & Shoulders (pembalikan naik)": "Inverse Head & Shoulders (bullish reversal)",
    "Ascending Triangle (segitiga naik, cenderung bullish)": "Ascending Triangle (usually bullish)",
    "Descending Triangle (segitiga turun, cenderung bearish)": "Descending Triangle (usually bearish)",
    "Symmetrical Triangle (konsolidasi, tunggu arah breakout)": "Symmetrical Triangle (consolidation, wait for the breakout)",
    "Rising Wedge (wedge naik, cenderung bearish)": "Rising Wedge (usually bearish)",
    "Falling Wedge (wedge turun, cenderung bullish)": "Falling Wedge (usually bullish)",
    "Falling Wedge gagal (jebol ke bawah, bearish)": "Failed Falling Wedge (broke down, bearish)",
    "Ascending Triangle gagal (jebol ke bawah, bearish)": "Failed Ascending Triangle (broke down, bearish)",
    "Rising Wedge gagal (tembus ke atas, bullish)": "Failed Rising Wedge (broke out up, bullish)",
    "Descending Triangle gagal (tembus ke atas, bullish)": "Failed Descending Triangle (broke out up, bullish)",
    "Rectangle / Sideways range": "Rectangle / sideways range", "Channel naik": "Ascending channel", "Channel turun": "Descending channel",
    "Bull Flag (konsolidasi setelah reli, lanjutan naik)": "Bull Flag (pause after a rally, continuation up)",
    "Bear Flag (konsolidasi setelah turun, lanjutan turun)": "Bear Flag (pause after a drop, continuation down)",
    # divergence
    "Divergence bullish RSI (harga lower low, RSI higher low)": "Bullish RSI divergence (price lower low, RSI higher low)",
    "Hidden divergence bullish (tren naik berlanjut)": "Hidden bullish divergence (uptrend continuing)",
    "Divergence bearish RSI (harga higher high, RSI lower high)": "Bearish RSI divergence (price higher high, RSI lower high)",
    "Hidden divergence bearish (tren turun berlanjut)": "Hidden bearish divergence (downtrend continuing)",
    # candlestick
    "Morning Star (pembalikan naik)": "Morning Star (bullish reversal)", "Evening Star (pembalikan turun)": "Evening Star (bearish reversal)",
    "Morning Doji Star (pembalikan naik)": "Morning Doji Star (bullish reversal)", "Evening Doji Star (pembalikan turun)": "Evening Doji Star (bearish reversal)",
    "Bullish Abandoned Baby (pembalikan naik kuat)": "Bullish Abandoned Baby (strong bullish reversal)",
    "Bearish Abandoned Baby (pembalikan turun kuat)": "Bearish Abandoned Baby (strong bearish reversal)",
    "Three White Soldiers (dorongan beli kuat)": "Three White Soldiers (strong buying)",
    "Three Black Crows (tekanan jual kuat)": "Three Black Crows (strong selling)",
    "Three Inside Up (Harami naik terkonfirmasi)": "Three Inside Up (confirmed bullish Harami)",
    "Three Inside Down (Harami turun terkonfirmasi)": "Three Inside Down (confirmed bearish Harami)",
    "Three Outside Up (Engulfing naik terkonfirmasi)": "Three Outside Up (confirmed bullish Engulfing)",
    "Three Outside Down (Engulfing turun terkonfirmasi)": "Three Outside Down (confirmed bearish Engulfing)",
    "Rising Three Methods (jeda singkat, tren naik berlanjut)": "Rising Three Methods (brief pause, uptrend continues)",
    "Falling Three Methods (jeda singkat, tren turun berlanjut)": "Falling Three Methods (brief pause, downtrend continues)",
    "Bullish Three Line Strike (tiga turun dihapus satu candle naik)": "Bullish Three Line Strike (three down candles erased by one up candle)",
    "Bearish Three Line Strike (tiga naik dihapus satu candle turun)": "Bearish Three Line Strike (three up candles erased by one down candle)",
    "Bullish Kicker (berbalik naik tajam dengan gap)": "Bullish Kicker (sharp gap reversal up)",
    "Bearish Kicker (berbalik turun tajam dengan gap)": "Bearish Kicker (sharp gap reversal down)",
    "Bullish Engulfing": "Bullish Engulfing", "Bearish Engulfing": "Bearish Engulfing",
    "Piercing Line (pembalikan naik)": "Piercing Line (bullish reversal)", "Dark Cloud Cover (pembalikan turun)": "Dark Cloud Cover (bearish reversal)",
    "Bullish Harami (momentum jual melemah)": "Bullish Harami (selling momentum fading)",
    "Bearish Harami (momentum beli melemah)": "Bearish Harami (buying momentum fading)",
    "Bullish Harami Cross (jual mulai ragu)": "Bullish Harami Cross (sellers hesitating)",
    "Bearish Harami Cross (beli mulai ragu)": "Bearish Harami Cross (buyers hesitating)",
    "Tweezer Bottom (dasar ganda mini)": "Tweezer Bottom (mini double bottom)", "Tweezer Top (puncak ganda mini)": "Tweezer Top (mini double top)",
    "Dragonfly Doji (penolakan harga bawah)": "Dragonfly Doji (lower prices rejected)",
    "Gravestone Doji (penolakan harga atas)": "Gravestone Doji (higher prices rejected)",
    "Long-legged Doji (tarik-menarik kuat, ragu-ragu)": "Long-legged Doji (big tug-of-war, indecision)",
    "Doji (ragu-ragu)": "Doji (indecision)", "Spinning Top (ragu-ragu)": "Spinning Top (indecision)",
    "Hammer (pembalikan naik)": "Hammer (bullish reversal)", "Hanging Man (waspada pembalikan turun)": "Hanging Man (watch for a bearish reversal)",
    "Shooting Star (pembalikan turun)": "Shooting Star (bearish reversal)",
    "Inverted Hammer (potensi pembalikan naik)": "Inverted Hammer (possible bullish reversal)",
    "Marubozu bullish (beli dominan)": "Bullish Marubozu (buyers in full control)", "Marubozu bearish (jual dominan)": "Bearish Marubozu (sellers in full control)",
    "Bullish Belt Hold (dibuka di titik terendah lalu naik)": "Bullish Belt Hold (opened at the low, then rallied)",
    "Bearish Belt Hold (dibuka di titik tertinggi lalu turun)": "Bearish Belt Hold (opened at the high, then fell)",
}
_NAMA_URUT = sorted(NAMA_POLA, key=len, reverse=True)

BULAN = {"Jan": "Jan", "Feb": "Feb", "Mar": "Mar", "Apr": "Apr", "Mei": "May", "Jun": "Jun", "Jul": "Jul", "Agu": "Aug",
         "Sep": "Sep", "Okt": "Oct", "Nov": "Nov", "Des": "Dec"}


def nama_pola(nid: str, nama: str = "") -> str:
    """Nama pola dalam bahasa Inggris; bila tidak dikenal: nama Inggris dari mesin, atau bagian sebelum tanda kurung."""
    if nid in NAMA_POLA:
        return NAMA_POLA[nid]
    return nama or str(nid).split(" (")[0]


# ------------------------------------------------------------------
# Terjemahan teks buatan mesin / teknikal.py
# ------------------------------------------------------------------

def _harga(m, i=1):
    return m.group(i)


_ATURAN = [
    # tren & MA
    (r"^Harga di atas MA50 & MA200, MA50 > MA200 \(tren naik sehat\)$", "Price above MA50 & MA200, MA50 > MA200 (healthy uptrend)"),
    (r"^Harga di bawah MA50 & MA200, MA50 < MA200 \(tren turun\)$", "Price below MA50 & MA200, MA50 < MA200 (downtrend)"),
    (r"^Harga di atas MA50$", "Price above MA50"),
    (r"^Harga di bawah MA50$", "Price below MA50"),
    (r"^Posisi harga vs moving average campuran$", "Price vs moving averages is mixed"),
    (r"^Struktur swing: (.+)$", lambda m: "Swing structure: " + STRUKTUR.get(m.group(1), m.group(1))),
    (r"^(Golden cross|Death cross) MA50/MA200 (\d+) bar lalu$", lambda m: f"{m.group(1)} MA50/MA200 {m.group(2)} bar{'s' if m.group(2) != '1' else ''} ago"),
    (r"^ADX (\d+): (tren kuat|tren lemah / sideways|tren sedang), arah DI (naik|turun)$",
     lambda m: f"ADX {m.group(1)}: " + {"tren kuat": "strong trend", "tren lemah / sideways": "weak trend / sideways",
                                       "tren sedang": "moderate trend"}[m.group(2)] + f", DI pointing {'up' if m.group(3) == 'naik' else 'down'}"),
    # momentum
    (r"^RSI (\d+) overbought: momentum kuat tapi rawan koreksi$", r"RSI \1 overbought: strong momentum but prone to a pullback"),
    (r"^RSI (\d+): momentum bullish$", r"RSI \1: bullish momentum"),
    (r"^RSI (\d+): netral$", r"RSI \1: neutral"),
    (r"^RSI (\d+): momentum bearish$", r"RSI \1: bearish momentum"),
    (r"^RSI (\d+) oversold: tekanan jual berat, peluang technical rebound$", r"RSI \1 oversold: heavy selling, technical rebound possible"),
    (r"^MACD (di atas|di bawah) signal, (di atas|di bawah) nol, histogram (menguat|melemah)(?: — baru cross (ke atas|ke bawah) (\d+) bar lalu)?$",
     lambda m: f"MACD {'above' if m.group(1) == 'di atas' else 'below'} signal, {'above' if m.group(2) == 'di atas' else 'below'} zero, "
               f"histogram {'rising' if m.group(3) == 'menguat' else 'falling'}"
               + (f" — just crossed {'up' if m.group(4) == 'ke atas' else 'down'} {m.group(5)} bar{'s' if m.group(5) != '1' else ''} ago" if m.group(4) else "")),
    (r"^Stochastic cross naik di area oversold$", "Stochastic crossed up in oversold territory"),
    (r"^Stochastic cross turun di area overbought$", "Stochastic crossed down in overbought territory"),
    # volume
    (r"^Volume ([\d.]+)x rata-rata 20 hari pada candle (naik|turun)( \(proyeksi, candle belum selesai\))?$",
     lambda m: f"Volume {m.group(1)}x the 20-day average on a{'n up' if m.group(2) == 'naik' else ' down'} candle"
               + (" (projected, candle not finished)" if m.group(3) else "")),
    (r"^OBV naik saat harga turun \(akumulasi tersembunyi\)$", "OBV rising while price falls (hidden accumulation)"),
    (r"^OBV turun saat harga naik \(distribusi, kenaikan kurang didukung volume\)$",
     "OBV falling while price rises (distribution, rally not backed by volume)"),
    # breakout & volatilitas
    (r"^Harga menembus high 20 bar \((.+)\)$", r"Price broke above the 20-bar high (\1)"),
    (r"^Harga jebol low 20 bar \((.+)\)$", r"Price broke below the 20-bar low (\1)"),
    (r"^Bollinger squeeze: volatilitas sangat rendah, biasanya mendahului pergerakan besar$",
     "Bollinger squeeze: very low volatility, often precedes a big move"),
    (r"^Harga di atas Bollinger atas \(kuat, tapi sudah meregang\)$", "Price above the upper Bollinger band (strong, but stretched)"),
    (r"^Harga di bawah Bollinger bawah \(lemah, tapi sudah meregang\)$", "Price below the lower Bollinger band (weak, but stretched)"),
    # trendline & lokasi
    (r"^Trendline support jebol di sekitar (.+)$", r"Rising trendline broken near \1"),
    (r"^Trendline resistance tembus di sekitar (.+)$", r"Falling trendline broken to the upside near \1"),
    (r"^Dekat support (.+?)( — titik pantau, jangan sampai close di bawahnya)?$",
     lambda m: f"Near support {m.group(1)}" + (" — key level to watch, a close below it is a warning" if m.group(2) else "")),
    (r"^Dekat resistance (.+)$", r"Near resistance \1"),
    # tanda (teknikal.bendera)
    (r"^Harga tidak bergerak sejak (.+?) — kemungkinan disuspensi / tidak diperdagangkan$",
     r"No price change since \1 — possibly suspended / not traded"),
    (r"^Trendline naik baru jebol \(sekitar (.+)\)$", r"Rising trendline just broke (near \1)"),
    (r"^Trendline turun baru ditembus \(sekitar (.+)\)$", r"Falling trendline just broken to the upside (near \1)"),
    (r"^Rugi (\d+)% dan harga masih di bawah MA200 \((.+)\) — tren belum berbalik$",
     r"Down \1% and price still below MA200 (\2) — trend has not turned"),
    (r"^Untung (\d+)% dengan RSI (\d+) \(overbought\) — area wajar untuk mengamankan sebagian$",
     r"Up \1% with RSI \2 (overbought) — reasonable area to lock in part of the gain"),
    (r"^Oversold \(RSI (\d+)\) — tekanan jual sudah berat, sering diikuti pantulan$",
     r"Oversold (RSI \1) — heavy selling, often followed by a bounce"),
    (r"^(.+?) sedang terbentuk(?: — neckline (.+))?$", lambda m: f"{m.group(1)} forming" + (f" — neckline {m.group(2)}" if m.group(2) else "")),
]
_ATURAN = [(re.compile(a), b) for a, b in _ATURAN]

# Kalimat di catatan rencana (bisa beberapa kalimat dalam satu catatan)
_KALIMAT = [
    (r"RSI (\d+) sudah overbought — jangan kejar harga\. Tunggu koreksi ke area beli \(sekitar EMA21\) dan pastikan harga memantul; "
     r"rencana batal jika close di bawah Stop\.",
     r"RSI \1 is already overbought — don't chase. Wait for a pullback to the buy zone (around EMA21) and make sure price bounces; "
     r"the plan is cancelled on a close below the Stop."),
    (r"Paling ideal membeli saat harga terkoreksi ke area beli; rencana batal jika close di bawah Stop\.",
     "Best to buy on a pullback into the buy zone; the plan is cancelled on a close below the Stop."),
    (r"Harga di area tertinggi: tidak ada resistance historis, target memakai kelipatan risiko \(R\)\.",
     "Price is at its highs: no historical resistance, so targets use multiples of risk (R)."),
    (r"R:R ke target pertama di bawah 1,5: lebih baik membeli lebih dekat ke support supaya risikonya kecil\.",
     "R:R to the first target is below 1.5 — better to enter closer to support to keep the risk small."),
    (r"Saham IDX umumnya tidak bisa short: anggap ini sinyal untuk menghindari beli / mengurangi posisi\.",
     "IDX stocks generally can't be shorted: treat this as a signal to avoid buying / reduce the position."),
    (r"Untuk investor, artinya hindari beli / kurangi posisi \(short hanya lewat broker yang mendukung, dengan stop di atas resistance\)\.",
     "For investors this means avoid buying / reduce the position (short only through a broker that allows it, with a stop above resistance)."),
    (r"Untuk kripto bisa short \(futures\) dengan stop di atas resistance; untuk spot artinya hindari beli / kurangi posisi\.",
     "In crypto you can short (futures) with a stop above resistance; for spot this means avoid buying / reduce the position."),
    (r"Tekanan turun dominan: hindari beli / kurangi posisi\.",
     "Selling pressure dominates: avoid buying / reduce the position."),
    (r"Pertimbangkan beli kembali hanya jika harga bertahan di support (\S+) dan muncul sinyal pembalikan\.",
     r"Consider buying back only if price holds support \1 and a reversal signal appears."),
    (r"Sinyal belum searah\. Skenario naik valid jika close di atas (\S+); skenario turun jika close di bawah (\S+)\. "
     r"Trading range: beli dekat support, jual dekat resistance\.",
     r"Signals are not aligned yet. The bullish case is valid on a close above \1; the bearish case on a close below \2. "
     r"Trading range: buy near support, sell near resistance."),
]
_KALIMAT = [(re.compile(a), b) for a, b in _KALIMAT]

# Potongan di dalam teks (setelah nama pola): umur candle, lokasi, volume, konfirmasi, status pola
_POTONGAN = [
    (r"\bcandle terakhir\b", "last candle"),
    (r"\b1 candle lalu\b", "1 candle ago"),
    (r"\b(\d+) candle lalu\b", r"\1 candles ago"),
    (r"\bdi (support|resistance|MA50|MA200) ", r"at \1 "),
    (r"\bvolume ([\d.]+)x rata-rata\b", r"volume \1x average"),
    (r"\bvolume tipis\b", "thin volume"),
    (r"\bterkonfirmasi candle berikutnya\b", "confirmed by the next candle"),
    (r"\bmenunggu konfirmasi candle berikutnya\b", "awaiting confirmation from the next candle"),
    (r"\bbelum terkonfirmasi\b", "not confirmed yet"),
    (r"\bgagal dikonfirmasi\b", "failed confirmation"),
    (r"\btarget sudah tercapai\b", "target already reached"),
    (r"\btarget (\S+) sudah tercapai\b", r"target \1 already reached"),
]
_POTONGAN = [(re.compile(a), b) for a, b in _POTONGAN]
_STATUS_URUT = sorted(STATUS, key=len, reverse=True)


def teks(t: str, mk: str = "") -> str:
    """Terjemahkan satu teks buatan mesin / teknikal.py ke bahasa Inggris. Teks yang tidak dikenal dikembalikan apa adanya."""
    if not t:
        return t
    s = str(t)
    for nid in _NAMA_URUT:  # nama pola dulu (bisa muncul di awal sinyal, tanda, atau narasi)
        if nid in s:
            s = s.replace(nid, NAMA_POLA[nid])
    for pola, ganti in _ATURAN:
        m = pola.match(s)
        if m:
            s = ganti(m) if callable(ganti) else pola.sub(ganti, s)
            break
    for pola, ganti in _KALIMAT:
        s = pola.sub(ganti, s)
    if " — " in s:  # status pola / konteks candle setelah tanda pisah
        kepala, ekor = s.split(" — ", 1)
        for st in _STATUS_URUT:
            if ekor == st or ekor.startswith(st + ","):
                ekor = STATUS[st] + ekor[len(st):]
                break
        for pola, ganti in _POTONGAN:
            ekor = pola.sub(ganti, ekor)
        s = f"{kepala} — {ekor}"
    if mk == "idx":
        s = _angka_idx(s)
    return s


def tanggal(t: str) -> str:
    """'13 Nov 2026 01:49 WIB' / 'Agu' -> nama bulan Inggris."""
    return re.sub(r"\b(" + "|".join(BULAN) + r")\b", lambda m: BULAN[m.group(1)], str(t or ""))


# ------------------------------------------------------------------
# Hasil mesin
# ------------------------------------------------------------------

def _pola_en(p: dict, mk: str) -> dict:
    p = dict(p)
    p["name_id"] = nama_pola(p.get("name_id", ""), p.get("name", ""))
    if "status" in p:
        p["status"] = STATUS.get(p["status"], p["status"])
    return p


def hasil_en(r: dict) -> dict:
    """Salinan hasil analyze()/analyze_mtf() dengan semua teks dalam bahasa Inggris (kunci tetap sama)."""
    mk = r.get("market", "")
    e = copy.deepcopy(r)
    e["label_id"] = LABEL.get(r.get("label_id"), r.get("label_id"))
    if e.get("trend"):
        e["trend"]["label"] = TREN.get(r["trend"]["label"], r["trend"]["label"])
        e["trend"]["structure"] = STRUKTUR.get(r["trend"].get("structure"), r["trend"].get("structure"))
    e["signals"] = [{**s, "cat": KATEGORI.get(s["cat"], s["cat"]), "text": teks(s["text"], mk)} for s in r.get("signals", [])]
    for k in ("chart_patterns", "divergences", "candles_recent"):
        e[k] = [_pola_en(p, mk) for p in r.get(k, [])]
    if e.get("series") and e["series"].get("candles_all"):
        e["series"]["candles_all"] = [_pola_en(p, mk) for p in r["series"]["candles_all"]]
    if e.get("plan"):
        e["plan"]["note"] = teks(r["plan"].get("note", ""), mk)
        e["plan"]["bias_id"] = BIAS.get(r["plan"].get("bias_id"), r["plan"].get("bias_id"))
    if e.get("mtf"):
        e["mtf"]["confluence"] = KONFLUENSI.get(r["mtf"].get("confluence"), r["mtf"].get("confluence"))
        e["mtf"]["summary"] = [{**x, "trend": TREN.get(x.get("trend"), x.get("trend")), "label_id": LABEL.get(x.get("label_id"), x.get("label_id"))}
                               for x in r["mtf"].get("summary", [])]
    return e


def bendera_en(daftar: list | None, mk: str = "") -> list:
    return [{**f, "teks": teks(f.get("teks", ""), mk)} for f in (daftar or [])]


def aksi_en(r: dict) -> str:
    mk = r["market"]
    p = r["plan"]
    if p["bias"] == "long":
        return f"Trend supportive. Buy zone {fp(p['entry_zone'][0], mk)}–{fp(p['entry_zone'][1], mk)}; stop on a close < {fp(p['stop_loss'], mk)}."
    if p["bias"] == "short":
        tg = fp(p["targets"][0], mk) if p.get("targets") else "-"
        return f"Weak. Don't add yet; next support {tg}; reversal up on a close > {fp(p['stop_loss'], mk)}."
    return f"Neutral. Strengthens on a close > {fp(p['buy_trigger'], mk)}; weakens on a close < {fp(p['sell_trigger'], mk)}."


SATUAN = {"hari": "days", "minggu": "weeks", "bulan": "months", "bar": "bars"}
RS_TREN = {"menguat": "strengthening", "melemah": "weakening", "datar": "flat"}


def rs_en(rs: dict | None) -> dict | None:
    if not rs:
        return rs
    return {**rs, "satuan": SATUAN.get(rs.get("satuan"), rs.get("satuan")), "tren": RS_TREN.get(rs.get("tren"), rs.get("tren"))}


def sebutan_rs(x: float) -> str:
    return "stronger than" if x >= 2 else "weaker than" if x <= -2 else "in line with"


def kalimat_riwayat_en(titik: list, skor_kini: int, satuan: str = "hari") -> str:
    """Padanan wawasan.kalimat_riwayat (fakta yang sama dari ws.fakta_riwayat)."""
    f = ws.fakta_riwayat(titik, skor_kini)
    if not f:
        return ""
    en = SATUAN.get(satuan, satuan)
    kini = skor_teks(skor_kini)
    if f[0] == "cepat":
        return f"Score {'improved' if skor_kini > f[1] else 'deteriorated'} from {skor_teks(f[1])} (5 {en} ago) to {kini}."
    if f[0] == "arah":
        _, awal, n, eks, k = f
        ekor = f", after {'dipping' if eks < min(awal, skor_kini) else 'spiking'} to {skor_teks(eks)} ({k} {en} ago)" if eks is not None else ""
        return f"Score {'improved' if skor_kini > awal else 'deteriorated'} from {skor_teks(awal)} ({n} {en} ago) to {kini}{ekor}."
    if f[0] == "sempat":
        return f"Score {'dipped' if f[1] < skor_kini else 'spiked'} to {skor_teks(f[1])} ({f[2]} {en} ago) and is now {kini}."
    return f"Score fairly stable around {kini} over the past {f[1]} {en}."


# ------------------------------------------------------------------
# Analisa tertulis (padanan wawasan.narasi)
# ------------------------------------------------------------------

def teks_target_en(p: dict, f) -> str:
    """Padanan te.teks_target: ', target 750' / ', target 750 already reached' / ''."""
    if p.get("target") is None:
        return ""
    return f", target {f(p['target'])}" + (" already reached" if p.get("target_hit") else "")


def _kecil(s: str) -> str:
    """Huruf awal kecil di tengah kalimat, kecuali singkatan (RSI, MACD) dan nama pola."""
    if not s or s[:2].isupper():
        return s
    kata = [k for k in s.split()[1:3] if k != "&"]
    if kata and kata[0][:1].isupper():
        return s
    return s[:1].lower() + s[1:]


def narasi_en(r: dict, simbol: str, bendera: list | None = None, rs: dict | None = None, dekat: dict | None = None,
              pos: dict | None = None, berjalan: float | None = None, riwayat: str = "") -> dict:
    """Analisa tertulis dalam bahasa Inggris: {"inti", "singkat", "paragraf": [kondisi, skenario]}.

    r = hasil mesin ASLI (bahasa Indonesia); bendera = daftar tanda asli. Semua teks dibuat di sini."""
    mk = r["market"]
    f = lambda x: fp(x, mk)  # noqa: E731
    ind = r["indicators"]
    harga = r["price"]
    skor = int(r["score"])
    tren_id = r["trend"]["label"]
    tren = TREN.get(tren_id, tren_id)
    harian = r.get("tf") in ws.TF_HARIAN
    dekat = dekat or ws.dekat_level(r)
    label = LABEL.get(r["label_id"], r["label_id"])

    # --- kondisi
    ma = []
    if ind.get("sma50"):
        ma.append(("above" if harga > ind["sma50"] else "below", "MA50"))
    if ind.get("sma200"):
        ma.append(("above" if harga > ind["sma200"] else "below", "MA200"))
    if len(ma) == 2 and ma[0][0] == ma[1][0]:
        posisi_ma = f"price {ma[0][0]} MA50 and MA200"
    else:
        posisi_ma = ("price " + " but ".join(f"{a} {b}" for a, b in ma)) if ma else ""
    arah = tren.lower().split()[-1] if tren else ""
    ra = rencana_aksi_en(r, dekat) or {}
    sikap = ra.get("sikap")
    lawan = bool(r.get("lawan_tren"))
    sb = SATUAN_TUNGGAL.get(ws.SATUAN_TF.get(r.get("tf"), "bar"), "bar")
    if sikap == "hindari":
        k0 = (f"{simbol} is starting to weaken even though the 50-{sb} trend is still up: hold off on new buying." if lawan
              else f"{simbol} is still under selling pressure: there is no technical reason to buy yet." if arah == "downtrend"
              else f"{simbol} is leaning weak: there is no technical reason to buy yet.")
    elif sikap == "beli":
        k0 = (f"{simbol} " + ("is showing early signs of a bullish reversal and is in the buy zone" if lawan else "is in the buy zone")
              + (", but the setup is less attractive because the target is close" if ra.get("rr_rendah") else "") + ".")
    elif sikap == "tunggu_koreksi":
        k0 = (f"{simbol} " + ("is showing early signs of a bullish reversal" if lawan else "is bullish")
              + ", but price is already above the buy zone: better to wait for a pullback.")
    elif sikap == "tunggu":
        k0 = f"{simbol} has no clear direction yet: wait for confirmation."
    else:
        k0 = ""
    label_pendek = (label.split(" (")[0].lower() if not label.startswith("Neutral") else "neutral")
    alasan = []
    if lawan:
        searah = sorted((x for x in r.get("signals", []) if x["score"] * skor > 0), key=lambda x: -abs(x["score"]))[:2]
        alasan = [teks(x["text"], mk).split(" — ")[0] for x in searah]
        k1 = (f"The 50-{sb} trend is still {'down' if skor > 0 else 'up'}" + (f" ({posisi_ma})" if posisi_ma else "")
              + f", but the technical score is {skor_teks(skor)} ({label_pendek})"
              + (" because of " + " and ".join(_kecil(x) for x in alasan) if alasan else "") + ".")
    else:
        if ma and ((arah == "uptrend" and all(a == "below" for a, _ in ma)) or (arah == "downtrend" and all(a == "above" for a, _ in ma))):
            k1 = f"{simbol} is still in {'an' if tren.lower().startswith('up') else 'a'} {tren.lower()}, but {posisi_ma.replace('price ', 'price is already ', 1)}."
        elif tren_id == "Sideways":
            k1 = f"{simbol} is moving sideways" + (f": {posisi_ma}" if posisi_ma else "") + "."
        else:
            k1 = f"{simbol} is in {'an' if tren.lower().startswith('up') else 'a'} {tren.lower()}" + (f": {posisi_ma}" if posisi_ma else "") + "."
        k1 += f" Technical score {skor_teks(skor)} ({label_pendek})."

    rsi = ind.get("rsi14")
    if rsi is None:
        mom = ""
    elif rsi >= 70:
        mom = f"RSI {angka(rsi, 0)} is overbought, momentum strong but prone to a pullback"
    elif rsi >= 55:
        mom = f"momentum still positive (RSI {angka(rsi, 0)})"
    elif rsi > 45:
        mom = f"momentum neutral (RSI {angka(rsi, 0)})"
    elif rsi > 30:
        mom = f"momentum weak (RSI {angka(rsi, 0)})"
    else:
        mom = f"RSI {angka(rsi, 0)} is oversold — heavy selling, a technical bounce can happen"
    if ind.get("macd") is not None and ind.get("macd_signal") is not None:
        macd = MACD_AWAM[(ind["macd"] > ind["macd_signal"], ind["macd"] > 0)]
        mom = f"{mom}; {macd}" if mom else macd
    k2 = (mom[:1].upper() + mom[1:] + ".") if mom else ""

    peristiwa = []
    for b in (bendera or []):
        if b.get("baru", True) and b["level"] in ("merah", "oranye", "hijau"):
            peristiwa.append(teks(b["teks"], mk).split(" — ")[0])
    for p in r.get("chart_patterns", []):
        nama = nama_pola(p["name_id"], p.get("name", ""))
        if p.get("confirmed") and not any(nama in x for x in peristiwa):
            peristiwa.append(f"{nama} {STATUS.get(p['status'], p['status'])}" + teks_target_en(p, f))
    for d in r.get("divergences", []):
        nama = nama_pola(d["name_id"], d.get("name", "")).split(" (")[0]
        if not d.get("weak") and not any(nama in x for x in peristiwa):
            peristiwa.append(nama)
    peristiwa = [x for x in peristiwa if not any(ws.dua_kata(a_) in x.lower() for a_ in alasan)]
    k3 = ("Worth noting: " + "; ".join(_kecil(x) for x in peristiwa[:2]) + ".") if peristiwa else ""

    k4 = ""
    if rs and rs.get("rs20") is not None:
        hari = SATUAN.get(rs.get("satuan") or "hari", rs.get("satuan") or "days")
        gerak = lambda x: ("rose " if x >= 0 else "fell ") + persen(abs(x), tanda=False)  # noqa: E731
        k4 = (f"Over the past 20 {hari} {simbol} {gerak(rs['aset20'])} while {rs['acuan']} {gerak(rs['acuan20'])} — "
              f"{sebutan_rs(rs['rs20'])} the market")
        k4 += RS_ARAH.get((ws.kelas_rs(rs["rs20"]), rs.get("tren")), "") + "."

    # --- skenario
    p = r["plan"]
    s_txt = []
    if dekat.get("s1"):
        s1 = dekat["s1"]
        s_txt.append(f"nearest support {f(s1['harga'])} ({persen(s1['jarak_pct'])}{', very close' if s1['dekat'] else ''})")
    if dekat.get("r1"):
        r1 = dekat["r1"]
        s_txt.append(f"resistance {f(r1['harga'])} ({persen(r1['jarak_pct'])}{', very close' if r1['dekat'] else ''})")
    j1 = ("Key levels: " + ", ".join(s_txt) + ".") if s_txt else ""
    if p["bias"] == "long":
        j2 = (f"As long as price holds above {f(p['stop_loss'])}, {f(p['entry_zone'][0])}–{f(p['entry_zone'][1])} "
              f"is the buy-on-pullback zone" + (f" with a first target at {f(p['targets'][0])}" if p.get("targets") else "") + ".")
    elif p["bias"] == "short":
        tg = p.get("targets") or []
        j2 = (f"While price stays below {f(p['stop_loss'])}, selling pressure dominates"
              + (f"; next support {f(tg[0])}" + (f" then {f(tg[1])}" if len(tg) > 1 else "") if tg else "")
              + f". A reversal is only confirmed on a close above {f(p['stop_loss'])}.")
    else:
        j2 = (f"Direction unclear: strengthens on a close above {f(p['buy_trigger'])}, "
              f"weakens on a close below {f(p['sell_trigger'])}.")
    j3 = ""
    if pos and pos.get("avg") and harga < pos["avg"]:
        j3 = f"Getting back to the position's average price ({f(pos['avg'])}) needs a {persen((pos['avg'] / harga - 1) * 100, tanda=False)} rise."
    mtf = (r.get("mtf") or {}).get("summary") or []
    j4 = ""
    if len(mtf) > 1:
        besar = mtf[-1]
        sama = (besar["score"] >= 20 and skor >= 20) or (besar["score"] <= -20 and skor <= -20)
        lawan = (besar["score"] >= 20 and skor <= -20) or (besar["score"] <= -20 and skor >= 20)
        nama_tf = {"1wk": "weekly", "1d": "daily", "4h": "4-hour", "1mo": "monthly"}.get(besar["tf"], besar["tf"])
        if sama:
            j4 = f"The {nama_tf} timeframe agrees (score {skor_teks(besar['score'])}), so the signal is more reliable."
        elif lawan:
            j4 = f"The {nama_tf} timeframe disagrees (score {skor_teks(besar['score'])}) — this may only be a pullback/bounce within the bigger trend."
    j5 = ""
    if berjalan is not None:
        j5 = f"Note: {'today’s' if harian else 'the latest'} candle is not finished, so the numbers can still change until the close."

    kondisi = " ".join(x for x in (k0, k1, k2, riwayat, k3, k4) if x)
    skenario = " ".join(x for x in (j1, j2, j4, j3, j5) if x)

    bagian = [tren]
    if rsi is not None:
        bagian.append("oversold" if rsi <= 30 else "overbought" if rsi >= 70 else "momentum " + ("positive" if rsi >= 55 else "weak" if rsi <= 45 else "neutral"))
    singkat = " · ".join(bagian)
    if dekat.get("s1"):
        bagian.append(f"S1 {f(dekat['s1']['harga'])} ({persen(dekat['s1']['jarak_pct'])})")
    return {"inti": " · ".join(bagian), "singkat": singkat, "paragraf": [kondisi, skenario]}


# ------------------------------------------------------------------
# Pesan server
# ------------------------------------------------------------------

_PESAN = [
    (r"^Isi ticker dulu, mis\. BBCA, NVDA, BTC, atau IDX:TLKM\.$", "Enter a ticker first, e.g. BBCA, NVDA, BTC, or IDX:TLKM."),
    (r"^Ticker tidak valid\. Contoh: BBCA, NVDA, BTC, atau IDX:TLKM\.$", "Invalid ticker. Examples: BBCA, NVDA, BTC, or IDX:TLKM."),
    (r"^Mode offline: (.+) tidak ada di cache harga\.$", r"Offline mode: \1 is not in the price cache."),
    (r"^Ticker tidak ditemukan atau data tidak tersedia \((.+?)\)\. Rincian: (.*)$", r"Ticker not found or no data available (\1). Details: \2"),
    (r"^Data (.+) terlalu sedikit \((\d+) bar\) untuk timeframe (.+)\.$", r"Not enough data for \1 (\2 bars) on the \3 timeframe."),
    (r"^Terjadi kesalahan: (.*)$", r"Something went wrong: \1"),
    (r"^timeframe (.+) tidak dikenal, memakai 1D$", r"timeframe \1 not recognised, using 1D"),
    (r"^(.+) terlalu kecil, memakai 5m$", r"\1 is too small, using 5m"),
    (r"^(.+) dibulatkan ke (.+)$", r"\1 rounded to \2"),
]
_PESAN = [(re.compile(a), b) for a, b in _PESAN]


def pesan_en(t: str | None) -> str | None:
    if not t:
        return t
    for pola, ganti in _PESAN:
        if pola.match(t):
            return pola.sub(ganti, t)
    return t


# ------------------------------------------------------------------
# Hasil pindai portofolio (output/teknikal.json)
# ------------------------------------------------------------------

SUMBER_POSISI = {"ledger.py (sama persis dengan tracker)": "ledger.py (identical to the tracker)",
                 "perhitungan cadangan (rata-rata tertimbang)": "fallback calculation (weighted average)"}


SEKTOR_BAWAAN = {"Kripto": "Crypto", "Belum diisi": "Not set", "Saham IDX": "IDX stock", "Saham/ETF AS": "US stock/ETF", "Lainnya": "Other"}


def aset_en(a: dict) -> dict:
    """Satu aset dari teknikal.json dalam bahasa Inggris. Analisa tertulis memakai 'narasi_en' yang dibuat saat pindai."""
    mk = a.get("pasar", "")
    e = dict(a)
    e["label"] = LABEL.get(a.get("label"), a.get("label"))
    e["tren"] = TREN.get(a.get("tren"), a.get("tren"))
    e["sektor"] = SEKTOR_BAWAAN.get(a.get("sektor"), a.get("sektor"))  # hanya label bawaan; nama sektor dari sektor.json dibiarkan
    e["konfluensi"] = KONFLUENSI.get(a.get("konfluensi"), a.get("konfluensi"))
    e["mtf"] = [{**x, "trend": TREN.get(x.get("trend"), x.get("trend")), "label_id": LABEL.get(x.get("label_id"), x.get("label_id"))}
                for x in a.get("mtf") or []]
    e["bendera"] = bendera_en(a.get("bendera"), mk)
    e["pola"] = [{**p, "nama": nama_pola(p.get("nama", "")), "status": STATUS.get(p.get("status"), p.get("status"))} for p in a.get("pola") or []]
    e["candle"] = [nama_pola(c) for c in a.get("candle") or []]
    e["sinyal"] = [{**s, "cat": KATEGORI.get(s.get("cat"), s.get("cat")), "text": teks(s.get("text", ""), mk)} for s in a.get("sinyal") or []]
    if a.get("rencana"):
        p = a["rencana"]
        e["rencana"] = {**p, "note": teks(p.get("note", ""), mk), "bias_id": BIAS.get(p.get("bias_id"), p.get("bias_id"))}
        try:
            e["aksi"] = aksi_en({"market": mk, "plan": p})
        except (KeyError, TypeError, IndexError):
            pass
    e["rs"] = rs_en(a.get("rs"))
    if a.get("narasi_en"):
        e["narasi"] = a["narasi_en"]
    e.pop("narasi_en", None)
    if a.get("rencana_aksi_en") is not None:
        e["rencana_aksi"] = a["rencana_aksi_en"]
    e.pop("rencana_aksi_en", None)
    return e


def dump_en(dump: dict) -> dict:
    e = dict(dump)
    r = dict(dump.get("ringkasan") or {})
    r["waktu"] = tanggal(r.get("waktu", ""))
    r["sumber_posisi"] = SUMBER_POSISI.get(r.get("sumber_posisi"), r.get("sumber_posisi"))
    e["ringkasan"] = r
    e["aset"] = [aset_en(a) for a in dump.get("aset") or []]
    e["pantauan"] = [aset_en(a) for a in dump.get("pantauan") or []]
    e["bahasa"] = "en"
    return e


# ------------------------------------------------------------------
# Rencana tindakan (padanan wawasan.rencana_aksi; logikanya sama, hanya templatnya Inggris)
# ------------------------------------------------------------------

T_AKSI_EN = {
    "judul_short": "Not time to buy yet · downtrend over on a close above {stop}",
    "judul_short_pos": "Don't add yet · downtrend over on a close above {stop}",
    "judul_long_zona": "Buy zone {lo}–{hi} · stop on a close below {stop}",
    "judul_long_zona_rr": "Buy zone {lo}–{hi}, but the target is close (R:R {rr}) · stop on a close below {stop}",
    "r_short": "Wait for a close > {stop}",
    "r_long_zona": "Buy zone {lo}–{hi} · stop < {stop}",
    "r_long_zona_rr": "Buy zone {lo}–{hi} (low R:R) · stop < {stop}",
    "r_long_atas": "Wait for a pullback to {lo}–{hi}",
    "r_wait": "Up on a close > {naik} · down < {turun}",
    "judul_long_atas": "Uptrend · wait for a pullback to {lo}–{hi}",
    "judul_wait": "Wait for direction · up on a close above {naik}, down below {turun}",
    "s_naik_k": "Close above {stop}",
    "s_naik_t": "The downtrend is considered over (Reversal up line). Only then build a buy plan; the buy zone is recalculated by the next analysis.",
    "s_naik_s": "downtrend over", "s_naik_n": "reversal up",
    "s_tahan_k": "Holds support {s1} and a bullish reversal candle appears",
    "s_tahan_t": "Early sign of a bounce, but still speculative while price is below {stop}.",
    "s_jebol_k": "Close below support {s1}",
    "s_jebol_t": "Support broken: selling pressure continues{ke}.",
    "s_jebol_ke": " toward {x}",
    "s_jebol_s": "selling pressure continues", "s_jebol_n": "support",
    "l_zona_k": "Price is in the buy zone {lo}–{hi}",
    "l_zona_t": "Buying/adding is fine in stages (split into 2–3 buys), not all at once.",
    "l_turun_k": "Price pulls back to the buy zone {lo}–{hi}",
    "l_turun_t": "Buy/add zone. Don't chase at the current price.",
    "l_zona_s": "buy zone", "l_zona_n": "buy zone", "l_masuk_s": "enters the buy zone",
    "l_stop_k": "Close below {stop}",
    "l_stop_t": "Buy plan cancelled (Stop line): exit per the stop or don't add. Distance from the buy zone to the stop ±{risk}.",
    "l_stop_s": "buy plan cancelled", "l_stop_n": "stop",
    "l_t1_k": "Reaches target 1 at {t1}",
    "l_t1_t": "A reasonable area to lock in part of the profit (R:R {rr}).",
    "l_t1_s": "area to take partial profit", "l_t1_n": "target 1",
    "l_rr_lemah": " Note: target 1 is closer than the stop (R:R {rr}), so this setup is less attractive.",
    "w_naik_k": "Close above {naik}",
    "w_naik_t": "Upward direction confirmed; only then build a buy plan.",
    "w_naik_s": "upward direction confirmed", "w_naik_n": "upside trigger",
    "w_turun_k": "Close below {turun}",
    "w_turun_t": "Downward direction: avoid buying.",
    "w_turun_s": "downward direction", "w_turun_n": "downside trigger",
    "w_antara_k": "Price stays between the two",
    "w_antara_t": "No action needed yet; just monitor.",
    "pos_tinjau": " If you hold it: this is the point to review the position and reduce risk.",
    "pos_rugi": "Position down {pl} and price below the MA200 ({ma200}): adding now means adding into a downtrend. Getting back to the average price ({avg}) needs a {perlu} rise.",
    "pos_untung_ob": "Position up {pl} with RSI {rsi} (overbought): locking in part of the profit is reasonable.",
    "pos_untung_lemah": "Position still up {pl}; if support {s1} breaks, part of the profit can be locked in.",
    "pos_rugi_ringan": "Position down {pl}; average price {avg} (needs a {perlu} rise).",
    "pos_untung": "Position up {pl}; average price {avg}.",
    "pantau": "{jarak} {letak} {nama} {harga} · a close {sisi} it: {akibat}",
    "di_atas": "above", "di_bawah": "below",
    "pantau_zona": "In the buy zone {lo}–{hi}",
}


def rencana_aksi_en(r: dict, dekat: dict | None = None, pos: dict | None = None) -> dict:
    mk = r["market"]
    return ws.rencana_aksi(r, dekat, pos, T=T_AKSI_EN, fp=lambda x: fp(x, mk),
                           pct=lambda x, tanda=True: persen(x, tanda=tanda), num=lambda x, d=1: angka(x, d))


# ------------------------------------------------------------------
# Kesimpulan semua timeframe (padanan wawasan.kesimpulan_semua_tf)
# ------------------------------------------------------------------

T_SEMUA_EN = {
    "semua_naik": "Every timeframe points up: a strong, healthy trend from short to long term.",
    "naik_rehat": "The big trend is up; the daily/short term is resting (consolidating) with no sign of a reversal yet.",
    "koreksi_dalam_naik": "The big trend (weekly/monthly) is up, but the daily/short term is pulling back.",
    "naik_awal": "Starting to strengthen from below: daily and short term are up, the big trend hasn't followed yet.",
    "semua_turun": "Every timeframe points down: selling pressure dominates across all horizons.",
    "turun_rehat": "The big trend is down; the daily/short term is holding for now, with no sign of a reversal yet.",
    "pantul_dalam_turun": "The big trend (weekly/monthly) is down, but the daily/short term is bouncing.",
    "turun_awal": "Starting to weaken: daily and short term are down, the big trend hasn't turned down yet.",
    "campur": "Timeframes disagree or are neutral: no clear direction yet.",
    "s_semua_naik": ["Existing positions can be held while the daily close stays above {batal}.",
                     "Don't chase new buys; wait for a pullback to {zona}."],
    "s_naik_rehat": ["Hold positions; adding is safest near support {s1} ({s1_jarak}).",
                     "The uptrend resumes on a daily close above {r1}."],
    "s_koreksi_dalam_naik": ["A pullback inside an uptrend can be a chance to buy gradually near {s1} ({s1_jarak}).",
                             "Wait for a turn on the small timeframes (4H/1H score back to ≥ +20) before entering; cancel on a daily close below {batal}."],
    "s_naik_awal": ["The reversal up is still early: if you enter, start small and add once the 1W score is above +20 too.",
                    "Cancel if the daily close falls back below {s1}."],
    "s_semua_turun": ["Avoid new buys; consider reducing existing positions.",
                      "The trend is considered to have turned on a daily close above {konfirmasi} with an improving 1W score."],
    "s_turun_rehat": ["No reversal yet: avoid buying while price is below {r1}.",
                      "If support {s1} breaks, the decline is likely to continue."],
    "s_pantul_dalam_turun": ["A bounce inside a downtrend: don't chase it; a rise towards {r1} can be used to reduce positions.",
                             "For new buys, wait for the 1W score to rise above +20 too."],
    "s_turun_awal": ["Protect positions: the weakness continues on a daily close below {s1}.",
                     "Don't add until the daily close is back above {r1}."],
    "s_campur": ["Wait for direction: a daily close above {naik} = bullish case, below {turun} = bearish case.",
                 "If you still enter, keep the size small with a clear stop."],
    "s_risiko": "Size positions from the distance to the stop (e.g. a maximum loss of 1–2% of capital per position).",
    "tanpa_level": "-",
}


def kesimpulan_semua_tf_en(hasil: dict) -> dict:
    mk = next(iter(hasil.values()))["market"]
    k = ws.kesimpulan_semua_tf(hasil, T=T_SEMUA_EN, fp=lambda x: fp(x, mk), pct=lambda x: persen(x),
                               rencana=lambda r: rencana_aksi_en(r))
    k["label"] = LABEL.get(k["label"], k["label"])
    for b in k["tf"]:
        b["label"] = LABEL.get(b["label"], b["label"])
        b["tren"] = TREN.get(b["tren"], b["tren"])
    return k
