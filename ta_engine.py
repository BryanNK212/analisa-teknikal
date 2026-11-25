"""
ta_engine — mesin analisa teknikal untuk saham IDX, saham US, dan kripto.

Inti analisa hanya butuh numpy. Dashboard artifact memakai port JavaScript versi 1.0 (skor sama; tambahan 1.1 —
candle berjalan, titik tembus trendline, kolom catatan di chart — hanya ada di versi Python ini).
Loader data (Yahoo Finance / Binance) memakai urllib standar; chart PNG memakai matplotlib.

Pemakaian CLI:
    python ta_engine.py BBCA                  # auto-deteksi pasar (IDX dicoba dulu untuk 4 huruf)
    python ta_engine.py US:NVDA --tf 1d
    python ta_engine.py BTC --tf 4h --out hasil/
    python ta_engine.py --csv data.csv --symbol BBCA --market idx

Pemakaian modul:
    import ta_engine as te
    bars, meta = te.load("BBCA")
    res = te.analyze(bars, symbol="BBCA", market="idx")
    print(te.to_markdown(res))
"""
from __future__ import annotations

import json
import math
import re
import sys
from datetime import datetime, timezone
from urllib.parse import quote

import numpy as np

VERSION = "1.4.1"
NAN = float("nan")

# =============================================================================
# 1. Utilitas & indikator
# =============================================================================


def _nan(n):
    return np.full(n, np.nan)


def _isnum(x):
    return x is not None and not (isinstance(x, float) and math.isnan(x))


def sma(x, n):
    x = np.asarray(x, float)
    out = _nan(len(x))
    if n <= len(x):
        w = np.lib.stride_tricks.sliding_window_view(x, n)
        out[n - 1:] = w.mean(axis=1)
    return out


def ema(x, n, wilder=False):
    """EMA (atau RMA Wilder) yang di-seed dengan SMA dari n nilai valid pertama."""
    x = np.asarray(x, float)
    out = _nan(len(x))
    valid = np.where(~np.isnan(x))[0]
    if len(valid) < n:
        return out
    s = valid[0]
    a = 1.0 / n if wilder else 2.0 / (n + 1)
    out[s + n - 1] = np.mean(x[s:s + n])
    for i in range(s + n, len(x)):
        xi = x[i] if not np.isnan(x[i]) else out[i - 1]
        out[i] = a * xi + (1 - a) * out[i - 1]
    return out


def rolling_std(x, n):
    x = np.asarray(x, float)
    out = _nan(len(x))
    if n <= len(x):
        out[n - 1:] = np.lib.stride_tricks.sliding_window_view(x, n).std(axis=1)
    return out


def rolling_max(x, n):
    x = np.asarray(x, float)
    out = _nan(len(x))
    if n <= len(x):
        out[n - 1:] = np.lib.stride_tricks.sliding_window_view(x, n).max(axis=1)
    return out


def rolling_min(x, n):
    x = np.asarray(x, float)
    out = _nan(len(x))
    if n <= len(x):
        out[n - 1:] = np.lib.stride_tricks.sliding_window_view(x, n).min(axis=1)
    return out


def rsi(c, n=14):
    c = np.asarray(c, float)
    d = np.diff(c, prepend=np.nan)
    up = np.where(d > 0, d, 0.0)
    dn = np.where(d < 0, -d, 0.0)
    up[0] = dn[0] = np.nan
    au, ad = ema(up, n, True), ema(dn, n, True)
    with np.errstate(divide="ignore", invalid="ignore"):
        r = 100 - 100 / (1 + au / ad)
    r = np.where((ad == 0) & ~np.isnan(au), 100.0, r)
    r = np.where((ad == 0) & (au == 0), 50.0, r)  # 1.4.0: harga datar (mis. saham suspensi) = netral, bukan 100
    return r


def true_range(h, l, c):
    pc = np.roll(c, 1)
    tr = np.maximum(h - l, np.maximum(np.abs(h - pc), np.abs(l - pc)))
    tr[0] = h[0] - l[0]
    return tr


def atr(h, l, c, n=14):
    return ema(true_range(h, l, c), n, True)


def macd(c, fast=12, slow=26, sig=9):
    m = ema(c, fast) - ema(c, slow)
    s = ema(m, sig)
    return m, s, m - s


def bollinger(c, n=20, k=2.0):
    mid = sma(c, n)
    sd = rolling_std(c, n)
    return mid + k * sd, mid, mid - k * sd


def stochastic(h, l, c, n=14, smooth=3, d=3):
    hh, ll = rolling_max(h, n), rolling_min(l, n)
    with np.errstate(divide="ignore", invalid="ignore"):
        raw = 100 * (c - ll) / (hh - ll)
    k = sma(np.nan_to_num(raw, nan=50.0), smooth)
    k[: n - 1 + smooth - 1] = np.nan
    dd = sma(np.nan_to_num(k, nan=50.0), d)
    dd[: n - 1 + smooth - 1 + d - 1] = np.nan
    return k, dd


def adx(h, l, c, n=14):
    up = h - np.roll(h, 1)
    dn = np.roll(l, 1) - l
    pdm = np.where((up > dn) & (up > 0), up, 0.0)
    mdm = np.where((dn > up) & (dn > 0), dn, 0.0)
    tr = true_range(h, l, c)
    pdm[0] = mdm[0] = tr[0] = np.nan
    a = ema(tr, n, True)
    with np.errstate(divide="ignore", invalid="ignore"):
        pdi = 100 * ema(pdm, n, True) / a
        mdi = 100 * ema(mdm, n, True) / a
        dx = 100 * np.abs(pdi - mdi) / (pdi + mdi)
    return ema(dx, n, True), pdi, mdi


def obv(c, v):
    s = np.sign(np.diff(c, prepend=c[0]))
    return np.cumsum(s * v)


# =============================================================================
# 2. Data: struktur bar, resample, CSV
# =============================================================================


def to_bars(rows=None, t=None, o=None, h=None, l=None, c=None, v=None):
    """Buat dict bar numpy. rows = list [t, o, h, l, c, v] (t = epoch detik)."""
    if rows is not None:
        a = np.asarray(rows, float)
        if a.ndim != 2 or a.shape[1] < 5:
            raise ValueError("rows harus berbentuk [[t,o,h,l,c,(v)], ...]")
        t, o, h, l, c = a[:, 0], a[:, 1], a[:, 2], a[:, 3], a[:, 4]
        v = a[:, 5] if a.shape[1] > 5 else np.zeros(len(a))
    b = {k: np.asarray(x, float) for k, x in zip("tohlcv", (t, o, h, l, c, v if v is not None else np.zeros(len(c))))}
    if np.nanmedian(b["t"]) > 1e11:  # milidetik -> detik
        b["t"] = b["t"] / 1000.0
    ok = ~(np.isnan(b["o"]) | np.isnan(b["h"]) | np.isnan(b["l"]) | np.isnan(b["c"]) | np.isnan(b["t"]))
    b = {k: x[ok] for k, x in b.items()}
    order = np.argsort(b["t"], kind="stable")
    b = {k: x[order] for k, x in b.items()}
    # buang timestamp duplikat (ambil yang terakhir)
    keep = np.append(np.diff(b["t"]) != 0, True)
    b = {k: x[keep] for k, x in b.items()}
    b["v"] = np.nan_to_num(b["v"], nan=0.0)
    # perbaiki high/low yang tidak konsisten
    b["h"] = np.maximum.reduce([b["h"], b["o"], b["c"]])
    b["l"] = np.minimum.reduce([b["l"], b["o"], b["c"]])
    return b


# Geser jam (detik) supaya satu sesi bursa jatuh di satu tanggal saat dibagi per hari/minggu/bulan.
# 1.4.0: dulu semua pasar memakai WIB (+7 jam), sehingga sesi saham AS (13:30–21:00 UTC) terbelah di 17:00 UTC
# dan candle harian kripto bergeser 7 jam dari candle harian Binance/TradingView (00:00 UTC).
GESER_HARI = {"idx": 7 * 3600, "us": -5 * 3600, "crypto": 0, "lain": 0}


def resample(bars, tf, market=None):
    """Resample bar ke timeframe lebih besar: '4h', '1d', '1wk', '1mo'. market menentukan batas hari (lihat GESER_HARI)."""
    t = bars["t"]
    g = GESER_HARI.get(market, 7 * 3600)
    if tf == "1wk":
        key = np.floor((t + g - 4 * 86400) / (7 * 86400))  # minggu mulai Senin
    elif tf == "1mo":
        key = np.array([(lambda d: d.year * 12 + d.month)(datetime.fromtimestamp(x + g, timezone.utc)) for x in t])
    elif tf == "1d":
        key = np.floor((t + g) / 86400)
    elif tf == "4h":
        key = np.floor(t / (4 * 3600))
    else:
        raise ValueError(tf)
    out = {k: [] for k in "tohlcv"}
    idx = np.flatnonzero(np.diff(key)) + 1
    for g in np.split(np.arange(len(t)), idx):
        if len(g) == 0:
            continue
        out["t"].append(t[g[0]])
        out["o"].append(bars["o"][g[0]])
        out["h"].append(bars["h"][g].max())
        out["l"].append(bars["l"][g].min())
        out["c"].append(bars["c"][g[-1]])
        out["v"].append(bars["v"][g].sum())
    return {k: np.asarray(x, float) for k, x in out.items()}


_COLS = {
    "t": ["date", "time", "datetime", "timestamp", "tanggal", "waktu", "open time", "opentime"],
    "o": ["open", "pembukaan", "buka", "o"],
    "h": ["high", "tertinggi", "tinggi", "h", "max"],
    "l": ["low", "terendah", "rendah", "l", "min"],
    "c": ["close", "terakhir", "penutupan", "tutup", "price", "harga", "close/last", "last", "c"],
    "v": ["volume", "vol", "vol.", "v", "volume usdt", "volume (usdt)"],
}

_MONTHS = {m: i + 1 for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"])}
_MONTHS.update({"mei": 5, "agu": 8, "agt": 8, "okt": 10, "des": 12})


def _parse_num(s, id_locale):
    s = str(s).strip().replace("$", "").replace("Rp", "").replace(" ", "").replace(" ", "")
    if s in ("", "-", "null", "None", "nan"):
        return NAN
    mult = 1.0
    m = re.match(r"^(-?[\d.,]+)\s*([KMBTkmbt]|Rb|Jt|M)?$", s)
    if not m:
        try:
            return float(s)
        except ValueError:
            return NAN
    num, suf = m.group(1), (m.group(2) or "")
    mult = {"k": 1e3, "rb": 1e3, "m": 1e6, "jt": 1e6, "b": 1e9, "t": 1e12}.get(suf.lower(), 1.0)
    if id_locale:
        num = num.replace(".", "").replace(",", ".")
    else:
        num = num.replace(",", "")
    try:
        return float(num) * mult
    except ValueError:
        return NAN


def _parse_date(s, dayfirst):
    s = str(s).strip().strip('"')
    if re.fullmatch(r"\d{9,13}(\.\d+)?", s):
        x = float(s)
        return x / 1000 if x > 1e11 else x
    m = re.match(r"(\d{4})-(\d{1,2})-(\d{1,2})(?:[ T](\d{1,2}):(\d{2})(?::(\d{2}))?)?", s)
    if m:
        y, mo, d = int(m.group(1)), int(m.group(2)), int(m.group(3))
        hh, mi, ss = int(m.group(4) or 0), int(m.group(5) or 0), int(m.group(6) or 0)
        return datetime(y, mo, d, hh, mi, ss, tzinfo=timezone.utc).timestamp()
    m = re.match(r"(\d{1,2})[/.\-](\d{1,2})[/.\-](\d{2,4})(?:\s+(\d{1,2}):(\d{2}))?", s)
    if m:
        a, b, y = int(m.group(1)), int(m.group(2)), int(m.group(3))
        y += 2000 if y < 100 else 0
        d, mo = (a, b) if dayfirst else (b, a)
        return datetime(y, mo, d, int(m.group(4) or 0), int(m.group(5) or 0), tzinfo=timezone.utc).timestamp()
    m = re.match(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2}),?\s+(\d{4})", s)  # Jan 31, 2024
    if m and m.group(1).lower() in _MONTHS:
        return datetime(int(m.group(3)), _MONTHS[m.group(1).lower()], int(m.group(2)), tzinfo=timezone.utc).timestamp()
    m = re.match(r"(\d{1,2})\s+([A-Za-z]{3})[a-z]*\.?\s+(\d{4})", s)  # 31 Jan 2024
    if m and m.group(2).lower() in _MONTHS:
        return datetime(int(m.group(3)), _MONTHS[m.group(2).lower()], int(m.group(1)), tzinfo=timezone.utc).timestamp()
    return NAN


def _split_csv_line(line, sep):
    out, cur, q = [], "", False
    for ch in line:
        if ch == '"':
            q = not q
        elif ch == sep and not q:
            out.append(cur)
            cur = ""
        else:
            cur += ch
    out.append(cur)
    return [x.strip().strip('"') for x in out]


def parse_csv(text):
    """Baca CSV OHLCV dari Yahoo, TradingView, Investing.com (EN/ID), Binance, Stockbit, dll."""
    lines = [ln for ln in text.replace("\r", "").split("\n") if ln.strip()]
    if not lines:
        raise ValueError("CSV kosong")
    head = lines[0]
    sep = max([",", ";", "\t", "|"], key=lambda s: head.count(s))
    hdr = [h.lower().strip().strip('"').strip("\ufeff") for h in _split_csv_line(head, sep)]
    known = {n for names in _COLS.values() for n in names}
    hdr = [h.rsplit(".", 1)[-1] if "." in h and h.rsplit(".", 1)[-1] in known else h for h in hdr]  # "AAPL.Open" -> "open"
    hdr = [re.sub(r"\s*\(.*?\)$", "", h) if re.sub(r"\s*\(.*?\)$", "", h) in known else h for h in hdr]
    has_header = any(any(ch.isalpha() for ch in h) for h in hdr)
    colmap = {}
    if has_header:
        for key, names in _COLS.items():
            for i, h in enumerate(hdr):
                if i in colmap.values():
                    continue
                if h in names or (key != "c" and any(h.startswith(n + " ") for n in names if len(n) > 2)):
                    colmap[key] = i
                    break
        if "c" not in colmap:
            for i, h in enumerate(hdr):
                if "close" in h and "adj" not in h and i not in colmap.values():
                    colmap["c"] = i
                    break
        body = lines[1:]
    else:  # Binance klines tanpa header: open_time, o, h, l, c, v, ...
        colmap = {"t": 0, "o": 1, "h": 2, "l": 3, "c": 4, "v": 5}
        body = lines
    missing = [k for k in "tohlc" if k not in colmap]
    if missing:
        raise ValueError(f"Kolom tidak ditemukan: {missing}. Header terbaca: {hdr}")
    rows = [_split_csv_line(ln, sep) for ln in body]
    rows = [r for r in rows if len(r) > max(colmap.values()) - (0 if "v" in colmap else 1)]
    numeric_cells = " ".join(r[colmap[k]] for r in rows[:200] for k in "ohlcv" if k in colmap and colmap[k] < len(r))
    id_header = any(hh in hdr for hh in ("tanggal", "terakhir", "pembukaan", "tertinggi", "terendah"))
    id_locale = bool(re.search(r"\d\.\d{3},\d", numeric_cells) or re.search(r"(^|\s)\d+,\d{1,2}(\s|$)", numeric_cells)) and not re.search(r"\d,\d{3}\.\d", numeric_cells)
    if id_header and not re.search(r"\d,\d{3}\.\d", numeric_cells):
        id_locale = True
    if not id_locale and sep == ";" and re.search(r"\d,\d", numeric_cells):
        id_locale = True
    firsts = [re.match(r"\s*(\d{1,2})[/.\-](\d{1,2})[/.\-]", r[colmap["t"]]) for r in rows[:300]]
    dayfirst = any(int(m.group(1)) > 12 for m in firsts if m) or (not any(int(m.group(2)) > 12 for m in firsts if m))
    out = []
    for r in rows:
        t = _parse_date(r[colmap["t"]], dayfirst)
        vals = [_parse_num(r[colmap[k]], id_locale) for k in "ohlc"]
        vol = _parse_num(r[colmap["v"]], id_locale) if "v" in colmap and colmap["v"] < len(r) else 0.0
        out.append([t] + vals + [vol])
    b = to_bars(out)
    if len(b["c"]) < 30:
        raise ValueError(f"Data terlalu sedikit ({len(b['c'])} bar). Minimal ~60 bar, ideal 200+.")
    return b


# =============================================================================
# 3. Pasar, simbol, dan loader online
# =============================================================================

CRYPTO = {"BTC", "ETH", "SOL", "BNB", "XRP", "ADA", "DOGE", "AVAX", "DOT", "LINK", "MATIC", "POL", "TRX", "TON",
          "SUI", "APT", "ARB", "OP", "NEAR", "ATOM", "LTC", "BCH", "ETC", "UNI", "AAVE", "INJ", "SEI", "TIA", "PEPE",
          "SHIB", "WIF", "BONK", "FET", "RNDR", "RENDER", "JUP", "HBAR", "ICP", "FIL", "XLM", "XMR", "ALGO", "VET",
          "STX", "IMX", "MKR", "LDO", "RUNE", "KAS", "ENA", "ONDO", "TAO", "WLD", "PYTH", "JTO", "HYPE", "TRUMP",
          "PENGU", "VIRTUAL", "S", "FLOKI", "GALA", "SAND", "MANA", "AXS", "CRV", "DYDX", "GRT", "QNT", "EGLD", "USDT"}


def resolve(symbol, market=None):
    """Kembalikan list kandidat (market, provider, kode) sesuai urutan dicoba."""
    s = symbol.strip().upper()
    if ":" in s:
        market, s = s.split(":", 1)
    market = (market or "").lower() or None
    s = s.replace("/", "")
    if s.endswith(".JK"):
        return [("idx", "yahoo", s)]
    if market in ("idx", "id", "bei", "jk"):
        return [("idx", "yahoo", s + ".JK")]
    if market in ("us", "nasdaq", "nyse", "amex"):
        return [("us", "yahoo", s)]
    base = re.sub(r"(USDT|USDC|USD|BUSD|-USD)$", "", s) if s not in ("USDT", "USDC") else s
    if market in ("crypto", "kripto", "cc") or s.endswith(("USDT", "-USD")) or base in CRYPTO:
        return [("crypto", "binance", base + "USDT"), ("crypto", "yahoo", base + "-USD")]
    if re.fullmatch(r"[A-Z]{4}", s):
        return [("idx", "yahoo", s + ".JK"), ("us", "yahoo", s), ("crypto", "binance", s + "USDT")]
    return [("us", "yahoo", s), ("crypto", "binance", s + "USDT")]


_UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 ta-engine/1.0",
       "Accept": "application/json"}


def _get_json(url, timeout=20):
    import urllib.request
    req = urllib.request.Request(url, headers=_UA)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode("utf-8"))


_YAHOO_TF = {"1h": ("60m", "730d"), "4h": ("60m", "730d"), "1d": ("1d", "5y"), "1wk": ("1wk", "max"), "1mo": ("1mo", "max"),
             "15m": ("15m", "60d"), "30m": ("30m", "60d"), "5m": ("5m", "30d")}


def fetch_yahoo(code, tf="1d"):
    interval, rng = _YAHOO_TF.get(tf, ("1d", "5y"))
    last_err = None
    for host in ("query1", "query2"):
        try:
            j = _get_json(f"https://{host}.finance.yahoo.com/v8/finance/chart/{quote(code, safe='.-=')}?range={rng}&interval={interval}&includePrePost=false")
            res = j["chart"]["result"][0]
            q = res["indicators"]["quote"][0]
            rows = [[t, o, h, l, c, v or 0] for t, o, h, l, c, v in
                    zip(res["timestamp"], q["open"], q["high"], q["low"], q["close"], q["volume"]) if None not in (o, h, l, c)]
            if len(rows) < 30:
                raise ValueError("data terlalu sedikit")
            b = to_bars(rows)
            if tf == "4h":
                b = resample(b, "4h")
            m = res.get("meta", {})
            meta = {"provider": "Yahoo Finance", "code": code, "currency": m.get("currency"),
                    "exchange": m.get("fullExchangeName") or m.get("exchangeName"),
                    "name": m.get("longName") or m.get("shortName") or code}
            return b, meta
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"Yahoo gagal untuk {code}: {last_err}")


def fetch_binance(pair, tf="1d"):
    iv = {"1wk": "1w", "1mo": "1M"}.get(tf, tf)
    last_err = None
    for host in ("https://api.binance.com", "https://data-api.binance.vision", "https://api.binance.us"):
        try:
            j = _get_json(f"{host}/api/v3/klines?symbol={quote(pair, safe='')}&interval={iv}&limit=1000")
            if not isinstance(j, list) or len(j) < 30:
                raise ValueError(str(j)[:120])
            rows = [[k[0] / 1000, float(k[1]), float(k[2]), float(k[3]), float(k[4]), float(k[5])] for k in j]
            return to_bars(rows), {"provider": "Binance", "code": pair, "currency": "USDT", "exchange": "Binance", "name": pair}
        except Exception as e:  # noqa: BLE001
            last_err = e
    raise RuntimeError(f"Binance gagal untuk {pair}: {last_err}")


def load(symbol, market=None, tf="1d"):
    """Ambil data OHLCV online. Return (bars, meta)."""
    errors = []
    for mkt, prov, code in resolve(symbol, market):
        try:
            b, meta = (fetch_binance if prov == "binance" else fetch_yahoo)(code, tf)
            meta.update({"market": mkt, "symbol": symbol.upper().split(":")[-1].replace(".JK", ""), "tf": tf})
            return b, meta
        except Exception as e:  # noqa: BLE001
            errors.append(f"{prov}:{code} -> {e}")
    raise RuntimeError("Tidak bisa mengambil data.\n  " + "\n  ".join(errors))


# =============================================================================
# 4. Format harga
# =============================================================================


def idx_tick(p):
    return 1 if p < 200 else 2 if p < 500 else 5 if p < 2000 else 10 if p < 5000 else 25


def round_price(p, market):
    if not _isnum(p):
        return None
    if market == "lain":  # indeks, forex, komoditas: angka biasa tanpa simbol mata uang
        dec = 2 if abs(p) >= 100 else 4 if abs(p) >= 1 else 6
        return round(float(p), dec)
    if market == "idx":
        t = idx_tick(p)
        return float(round(p / t) * t)
    if market == "us":
        return round(float(p), 2)
    if p == 0:
        return 0.0
    dec = max(2, 4 - int(math.floor(math.log10(abs(p)))))
    return round(float(p), min(dec, 10))


def fmt_price(p, market):
    if not _isnum(p):
        return "-"
    p = round_price(p, market)
    if market == "lain":
        dec = 2 if abs(p) >= 100 else 4 if abs(p) >= 1 else 6
        return f"{p:,.{dec}f}"
    if market == "idx":
        return f"{p:,.0f}".replace(",", ".")
    return f"${p:,.{desimal_dolar(p)}f}"


def desimal_dolar(p):
    """Desimal harga dolar (saham AS & kripto), 1.3.0: ≥ $1.000 tanpa sen, $1–$999 dua desimal, < $1 empat angka
    penting. Dulu kripto memakai 3–5 desimal ("$69.693"), yang di samping harga rupiah "4.900" terbaca seperti ribuan."""
    a = abs(p)
    if a >= 1000:
        return 0
    if a >= 1 or a == 0:
        return 2
    return min(10, 3 - int(math.floor(math.log10(a))))


# =============================================================================
# 5. Swing, support/resistance, trendline
# =============================================================================


def pivots(h, l, k):
    n = len(h)
    ph, pl = [], []
    for i in range(k, n - k):
        if h[i] >= h[i - k:i + k + 1].max() and h[i] > h[i - k:i].max():
            ph.append(i)
        if l[i] <= l[i - k:i + k + 1].min() and l[i] < l[i - k:i].min():
            pl.append(i)
    return ph, pl


def swings(h, l, a, k=3, min_atr=1.0):
    """Swing berselang-seling H/L (zigzag) dengan filter ukuran minimal min_atr x ATR."""
    ph, pl = pivots(h, l, k)
    pts = sorted([(i, "H", h[i]) for i in ph] + [(i, "L", l[i]) for i in pl], key=lambda x: (x[0], x[1]))
    med = np.nanmedian(a)
    out = []
    for p in pts:
        if not out:
            out.append(p)
            continue
        last = out[-1]
        if p[1] == last[1]:
            if (p[1] == "H" and p[2] >= last[2]) or (p[1] == "L" and p[2] <= last[2]):
                out[-1] = p
            continue
        thr = min_atr * (a[p[0]] if not np.isnan(a[p[0]]) else med)
        if abs(p[2] - last[2]) < thr:
            continue
        out.append(p)
    return out


def support_resistance(h, l, c, a_last, ph, pl, n_bars):
    price = c[-1]
    pts = [(h[i], i) for i in ph] + [(l[i], i) for i in pl]
    if not pts:
        return [], []
    pts.sort()
    tol = max(0.6 * a_last, price * 0.005)
    clusters = []
    for p, i in pts:
        if clusters and p - clusters[-1]["mean"] <= tol:
            cl = clusters[-1]
            cl["pts"].append((p, i))
            cl["mean"] = float(np.mean([x[0] for x in cl["pts"]]))
        else:
            clusters.append({"mean": p, "pts": [(p, i)]})
    levels = []
    for cl in clusters:
        idxs = [x[1] for x in cl["pts"]]
        touches = len(idxs)
        last_i = max(idxs)
        recency = last_i / max(1, n_bars - 1)
        levels.append({"price": float(cl["mean"]), "touches": touches, "last_idx": int(last_i),
                       "strength": round(touches + 2.0 * recency, 2)})
    sup = [lv for lv in levels if lv["price"] < price - 0.15 * a_last and lv["price"] > price * 0.6]
    res = [lv for lv in levels if lv["price"] > price + 0.15 * a_last and lv["price"] < price * 1.6]
    # buang level lemah yang terlalu jauh: ambil 6 terkuat lalu urutkan dari terdekat
    sup = sorted(sorted(sup, key=lambda x: -x["strength"])[:6], key=lambda x: -x["price"])[:4]
    res = sorted(sorted(res, key=lambda x: -x["strength"])[:6], key=lambda x: x["price"])[:4]
    return sup, res


def _line_at(p1, p2, x):
    (x1, y1), (x2, y2) = p1, p2
    return y1 + (y2 - y1) * (x - x1) / (x2 - x1)


def trendlines(h, l, c, a, ph, pl):
    """Garis tren support (dari swing low naik) dan resistance (dari swing high turun)."""
    n = len(c)
    out = []
    a_last = a[-1]
    for kind, piv, arr in (("support", pl, l), ("resistance", ph, h)):
        cand = [i for i in piv if i >= n - 160][-5:]
        best = None
        for x in range(len(cand)):
            for y in range(x + 1, len(cand)):
                i, j = cand[x], cand[y]
                if j - i < 5:
                    continue
                if kind == "support" and not arr[j] > arr[i]:
                    continue
                if kind == "resistance" and not arr[j] < arr[i]:
                    continue
                line = np.array([_line_at((i, arr[i]), (j, arr[j]), z) for z in range(i, n)])
                seg = arr[i:j + 1]
                lseg = line[: j - i + 1]
                if kind == "support" and np.any(seg < lseg - 0.35 * a_last):
                    continue
                if kind == "resistance" and np.any(seg > lseg + 0.35 * a_last):
                    continue
                touches = sum(1 for z in cand if z >= i and abs(arr[z] - _line_at((i, arr[i]), (j, arr[j]), z)) <= 0.4 * a_last)
                score = touches + j / n
                if best is None or score > best[0]:
                    best = (score, i, j, touches, line)
        if best:
            _, i, j, touches, line = best
            now = float(line[-1])
            after = c[j + 1:]
            lafter = line[j + 1 - i:]
            if kind == "support":
                broken = bool(len(after) and after[-1] < lafter[-1] - 0.25 * a_last)
            else:
                broken = bool(len(after) and after[-1] > lafter[-1] + 0.25 * a_last)
            if now <= 0:
                continue
            tl = {"kind": kind, "i1": int(i), "p1": float(arr[i]), "i2": int(j), "p2": float(arr[j]),
                  "value_now": now, "touches": int(touches), "broken": broken,
                  "slope_pct_per_bar": float((arr[j] - arr[i]) / (j - i) / c[-1] * 100)}
            if broken:
                # Titik tembus = awal rangkaian close di sisi seberang garis yang berlanjut sampai sekarang.
                k = n - 1
                seberang = (lambda z: c[z] < line[z - i]) if kind == "support" else (lambda z: c[z] > line[z - i])
                while k - 1 > j and seberang(k - 1):
                    k -= 1
                tl["break_idx"] = int(k)
                tl["break_price"] = float(line[k - i])
            out.append(tl)
    return out


# =============================================================================
# 6. Pola candlestick
# =============================================================================


# Pola yang klasiknya perlu dikonfirmasi candle berikutnya (pola 1–2 candle yang menandai keraguan/penolakan).
# Pola lain (Engulfing, Star, Three ..., Kicker, dll.) sudah membawa konfirmasinya sendiri di dalam polanya.
CANDLE_PERLU_KONFIRMASI = {"Hammer", "Hanging Man", "Shooting Star", "Inverted Hammer", "Dragonfly Doji", "Gravestone Doji",
                           "Bullish Harami", "Bearish Harami", "Bullish Harami Cross", "Bearish Harami Cross",
                           "Tweezer Bottom", "Tweezer Top", "Bullish Belt Hold", "Bearish Belt Hold"}


def _konteks_tren(c, a):
    """Arah tren sebelum tiap candle: +1 naik, −1 turun, 0 tidak jelas.

    Memakai perubahan 5 dan 10 bar terakhir dibanding ATR, ditambah posisi close terhadap EMA10,
    supaya satu-dua candle besar saja tidak dianggap tren."""
    n = len(c)
    e10 = ema(c, 10)
    out = np.zeros(n, dtype=int)
    for i in range(11, n):
        aa = a[i - 1] if not np.isnan(a[i - 1]) else np.nan
        if np.isnan(aa) or aa <= 0:
            continue
        ch5, ch10 = c[i - 1] - c[i - 6], c[i - 1] - c[i - 11]
        di_atas = not np.isnan(e10[i - 1]) and c[i - 1] > e10[i - 1]
        di_bawah = not np.isnan(e10[i - 1]) and c[i - 1] < e10[i - 1]
        if ch5 > 0.8 * aa or (ch10 > 1.5 * aa and di_atas):
            out[i] = 1
        elif ch5 < -0.8 * aa or (ch10 < -1.5 * aa and di_bawah):
            out[i] = -1
    return out


def candle_patterns(o, h, l, c, a):
    """Pola candlestick di tiap bar: [{"i", "name", "name_id", "bias", "strength", "bars"}].

    i = indeks candle terakhir pola; bars = jumlah candle pembentuk pola. Bobot sinyal (lokasi, volume,
    konfirmasi) dihitung di analyze() karena butuh support/resistance dan volume."""
    n = len(c)
    body = np.abs(c - o)
    rng = np.maximum(h - l, 1e-12)
    upper = h - np.maximum(o, c)
    lower = np.minimum(o, c) - l
    avgb = sma(body, 14)
    bull = c > o
    bear = c < o
    trend = _konteks_tren(c, a)
    doji = body <= 0.1 * rng
    out = []

    def add(i, name, nid, bias, strength, bars):
        out.append({"i": int(i), "name": name, "name_id": nid, "bias": bias, "strength": strength, "bars": bars})

    for i in range(2, n):
        ab = avgb[i] if not np.isnan(avgb[i]) else body[: i + 1].mean()
        tr = trend[i]
        big = body[i] > 1.1 * ab
        aa = a[i] if not np.isnan(a[i]) else rng[i]
        p = i - 1
        b1, b2, b3 = i - 2, i - 1, i
        tr1 = trend[b1]

        # ---------- 5 candle: Rising / Falling Three Methods (lanjutan tren) ----------
        if i >= 4:
            k0 = i - 4
            tengah = range(k0 + 1, i)
            kecil = all(body[x] < 0.6 * body[k0] for x in tengah)
            if bull[k0] and body[k0] > 1.1 * avgb[k0] if not np.isnan(avgb[k0]) else False:
                if kecil and all(h[x] <= h[k0] + 0.1 * aa and l[x] >= l[k0] - 0.1 * aa for x in tengah) \
                        and c[i - 1] <= c[k0] and bull[i] and c[i] > c[k0] and body[i] > 0.8 * body[k0] and trend[k0] >= 0:
                    add(i, "Rising Three Methods", "Rising Three Methods (jeda singkat, tren naik berlanjut)", 1, 2, 5)
            if bear[k0] and body[k0] > 1.1 * avgb[k0] if not np.isnan(avgb[k0]) else False:
                if kecil and all(h[x] <= h[k0] + 0.1 * aa and l[x] >= l[k0] - 0.1 * aa for x in tengah) \
                        and c[i - 1] >= c[k0] and bear[i] and c[i] < c[k0] and body[i] > 0.8 * body[k0] and trend[k0] <= 0:
                    add(i, "Falling Three Methods", "Falling Three Methods (jeda singkat, tren turun berlanjut)", -1, 2, 5)

        # ---------- 4 candle: Three Line Strike ----------
        if i >= 3:
            q1, q2, q3 = i - 3, i - 2, i - 1
            if all(bear[x] for x in (q1, q2, q3)) and c[q1] > c[q2] > c[q3] and all(body[x] > 0.5 * ab for x in (q1, q2, q3)) \
                    and bull[i] and o[i] <= c[q3] + 0.1 * aa and c[i] > o[q1]:
                add(i, "Bullish Three Line Strike", "Bullish Three Line Strike (tiga turun dihapus satu candle naik)", 1, 2, 4)
            if all(bull[x] for x in (q1, q2, q3)) and c[q1] < c[q2] < c[q3] and all(body[x] > 0.5 * ab for x in (q1, q2, q3)) \
                    and bear[i] and o[i] >= c[q3] - 0.1 * aa and c[i] < o[q1]:
                add(i, "Bearish Three Line Strike", "Bearish Three Line Strike (tiga naik dihapus satu candle turun)", -1, 2, 4)

        # ---------- 3 candle ----------
        # Abandoned Baby: doji yang terpisah gap dari candle sebelum dan sesudahnya (jarang, sangat kuat)
        if bear[b1] and body[b1] > ab and doji[b2] and h[b2] < l[b1] and bull[b3] and l[b3] > h[b2] and tr1 <= 0:
            add(i, "Bullish Abandoned Baby", "Bullish Abandoned Baby (pembalikan naik kuat)", 1, 3, 3)
        elif bull[b1] and body[b1] > ab and doji[b2] and l[b2] > h[b1] and bear[b3] and h[b3] < l[b2] and tr1 >= 0:
            add(i, "Bearish Abandoned Baby", "Bearish Abandoned Baby (pembalikan turun kuat)", -1, 3, 3)
        elif bear[b1] and body[b1] > ab and body[b2] < 0.5 * ab and bull[b3] and c[b3] > (o[b1] + c[b1]) / 2 and max(o[b2], c[b2]) <= c[b1] + 0.25 * body[b1] and tr1 <= 0:
            if doji[b2]:
                add(i, "Morning Doji Star", "Morning Doji Star (pembalikan naik)", 1, 3, 3)
            else:
                add(i, "Morning Star", "Morning Star (pembalikan naik)", 1, 3, 3)
        elif bull[b1] and body[b1] > ab and body[b2] < 0.5 * ab and bear[b3] and c[b3] < (o[b1] + c[b1]) / 2 and min(o[b2], c[b2]) >= c[b1] - 0.25 * body[b1] and tr1 >= 0:
            if doji[b2]:
                add(i, "Evening Doji Star", "Evening Doji Star (pembalikan turun)", -1, 3, 3)
            else:
                add(i, "Evening Star", "Evening Star (pembalikan turun)", -1, 3, 3)
        if all(bull[x] for x in (b1, b2, b3)) and c[b1] < c[b2] < c[b3] and all(body[x] > 0.6 * ab for x in (b1, b2, b3)) \
                and o[b2] >= o[b1] and o[b3] >= o[b2] and o[b2] <= c[b1] and o[b3] <= c[b2] and all(upper[x] < 0.4 * body[x] for x in (b1, b2, b3)):
            add(i, "Three White Soldiers", "Three White Soldiers (dorongan beli kuat)", 1, 3, 3)
        if all(bear[x] for x in (b1, b2, b3)) and c[b1] > c[b2] > c[b3] and all(body[x] > 0.6 * ab for x in (b1, b2, b3)) \
                and o[b2] <= o[b1] and o[b3] <= o[b2] and o[b2] >= c[b1] and o[b3] >= c[b2] and all(lower[x] < 0.4 * body[x] for x in (b1, b2, b3)):
            add(i, "Three Black Crows", "Three Black Crows (tekanan jual kuat)", -1, 3, 3)
        # Three Inside / Outside = Harami / Engulfing yang sudah dikonfirmasi candle ketiga
        harami_naik = bear[b1] and body[b1] > ab and body[b2] < 0.5 * body[b1] and max(o[b2], c[b2]) <= o[b1] and min(o[b2], c[b2]) >= c[b1]
        harami_turun = bull[b1] and body[b1] > ab and body[b2] < 0.5 * body[b1] and max(o[b2], c[b2]) <= c[b1] and min(o[b2], c[b2]) >= o[b1]
        if harami_naik and bull[b3] and c[b3] > o[b1] and tr1 <= 0:
            add(i, "Three Inside Up", "Three Inside Up (Harami naik terkonfirmasi)", 1, 3, 3)
        elif harami_turun and bear[b3] and c[b3] < o[b1] and tr1 >= 0:
            add(i, "Three Inside Down", "Three Inside Down (Harami turun terkonfirmasi)", -1, 3, 3)
        if bear[b1] and bull[b2] and c[b2] >= o[b1] and o[b2] <= c[b1] and body[b2] > body[b1] and body[b1] > 0.3 * ab \
                and bull[b3] and c[b3] > c[b2] and tr1 <= 0:
            add(i, "Three Outside Up", "Three Outside Up (Engulfing naik terkonfirmasi)", 1, 3, 3)
        elif bull[b1] and bear[b2] and c[b2] <= o[b1] and o[b2] >= c[b1] and body[b2] > body[b1] and body[b1] > 0.3 * ab \
                and bear[b3] and c[b3] < c[b2] and tr1 >= 0:
            add(i, "Three Outside Down", "Three Outside Down (Engulfing turun terkonfirmasi)", -1, 3, 3)

        # ---------- 2 candle ----------
        if bear[p] and body[p] > 0.8 * ab and bull[i] and body[i] > ab and o[i] >= o[p] and l[i] >= o[p] - 0.1 * aa:
            add(i, "Bullish Kicker", "Bullish Kicker (berbalik naik tajam dengan gap)", 1, 3, 2)
        elif bull[p] and body[p] > 0.8 * ab and bear[i] and body[i] > ab and o[i] <= o[p] and h[i] <= o[p] + 0.1 * aa:
            add(i, "Bearish Kicker", "Bearish Kicker (berbalik turun tajam dengan gap)", -1, 3, 2)
        elif bear[p] and bull[i] and c[i] >= o[p] and o[i] <= c[p] and body[i] > body[p] and body[p] > 0.3 * ab:
            add(i, "Bullish Engulfing", "Bullish Engulfing", 1, 3 if tr < 0 else 2, 2)
        elif bull[p] and bear[i] and c[i] <= o[p] and o[i] >= c[p] and body[i] > body[p] and body[p] > 0.3 * ab:
            add(i, "Bearish Engulfing", "Bearish Engulfing", -1, 3 if tr > 0 else 2, 2)
        elif bear[p] and body[p] > ab and bull[i] and o[i] <= c[p] and c[i] > (o[p] + c[p]) / 2 and c[i] < o[p] and tr <= 0:
            add(i, "Piercing Line", "Piercing Line (pembalikan naik)", 1, 2, 2)
        elif bull[p] and body[p] > ab and bear[i] and o[i] >= c[p] and c[i] < (o[p] + c[p]) / 2 and c[i] > o[p] and tr >= 0:
            add(i, "Dark Cloud Cover", "Dark Cloud Cover (pembalikan turun)", -1, 2, 2)
        elif body[p] > ab and body[i] < 0.5 * body[p] and max(o[i], c[i]) <= max(o[p], c[p]) and min(o[i], c[i]) >= min(o[p], c[p]):
            if bear[p] and tr < 0:
                if doji[i]:
                    add(i, "Bullish Harami Cross", "Bullish Harami Cross (jual mulai ragu)", 1, 2, 2)
                else:
                    add(i, "Bullish Harami", "Bullish Harami (momentum jual melemah)", 1, 1, 2)
            elif bull[p] and tr > 0:
                if doji[i]:
                    add(i, "Bearish Harami Cross", "Bearish Harami Cross (beli mulai ragu)", -1, 2, 2)
                else:
                    add(i, "Bearish Harami", "Bearish Harami (momentum beli melemah)", -1, 1, 2)
        if tr < 0 and bear[p] and bull[i] and abs(l[i] - l[p]) <= 0.1 * aa:
            add(i, "Tweezer Bottom", "Tweezer Bottom (dasar ganda mini)", 1, 1, 2)
        if tr > 0 and bull[p] and bear[i] and abs(h[i] - h[p]) <= 0.1 * aa:
            add(i, "Tweezer Top", "Tweezer Top (puncak ganda mini)", -1, 1, 2)

        # ---------- 1 candle ----------
        if doji[i] and rng[i] > 0.3 * ab:
            if lower[i] > 0.6 * rng[i]:
                add(i, "Dragonfly Doji", "Dragonfly Doji (penolakan harga bawah)", 1 if tr < 0 else 0, 1, 1)
            elif upper[i] > 0.6 * rng[i]:
                add(i, "Gravestone Doji", "Gravestone Doji (penolakan harga atas)", -1 if tr > 0 else 0, 1, 1)
            elif upper[i] > 0.3 * rng[i] and lower[i] > 0.3 * rng[i] and rng[i] > 1.2 * ab:
                add(i, "Long-legged Doji", "Long-legged Doji (tarik-menarik kuat, ragu-ragu)", 0, 1, 1)
            else:
                add(i, "Doji", "Doji (ragu-ragu)", 0, 1, 1)
        elif lower[i] >= 2 * body[i] and upper[i] <= max(0.35 * body[i], 0.1 * rng[i]) and rng[i] > 0.8 * ab:
            if tr < 0:
                add(i, "Hammer", "Hammer (pembalikan naik)", 1, 2, 1)
            elif tr > 0:
                add(i, "Hanging Man", "Hanging Man (waspada pembalikan turun)", -1, 1, 1)
        elif upper[i] >= 2 * body[i] and lower[i] <= max(0.35 * body[i], 0.1 * rng[i]) and rng[i] > 0.8 * ab:
            if tr > 0:
                add(i, "Shooting Star", "Shooting Star (pembalikan turun)", -1, 2, 1)
            elif tr < 0:
                add(i, "Inverted Hammer", "Inverted Hammer (potensi pembalikan naik)", 1, 1, 1)
        elif body[i] >= 0.9 * rng[i] and big and body[i] > 1.4 * ab:
            add(i, "Bullish Marubozu" if bull[i] else "Bearish Marubozu",
                "Marubozu bullish (beli dominan)" if bull[i] else "Marubozu bearish (jual dominan)", 1 if bull[i] else -1, 2, 1)
        elif body[i] >= 0.7 * rng[i] and body[i] > 1.4 * ab and bull[i] and lower[i] <= 0.05 * rng[i] and tr < 0:
            add(i, "Bullish Belt Hold", "Bullish Belt Hold (dibuka di titik terendah lalu naik)", 1, 1, 1)
        elif body[i] >= 0.7 * rng[i] and body[i] > 1.4 * ab and bear[i] and upper[i] <= 0.05 * rng[i] and tr > 0:
            add(i, "Bearish Belt Hold", "Bearish Belt Hold (dibuka di titik tertinggi lalu turun)", -1, 1, 1)
        elif body[i] > 0.1 * rng[i] and body[i] <= 0.25 * rng[i] and upper[i] >= max(body[i], 0.3 * rng[i]) \
                and lower[i] >= max(body[i], 0.3 * rng[i]) and rng[i] > 1.0 * ab:
            add(i, "Spinning Top", "Spinning Top (ragu-ragu)", 0, 1, 1)
    return out


def panah_candle(cps, o, h, l, c, n):
    """Pola candle kuat untuk panah di chart (1.4.0): tanpa pola yang gagal dikonfirmasi (close sesudahnya melewati
    ujung pola ke arah berlawanan sebelum terkonfirmasi), satu panah per candle dan arah."""
    out, sudah = [], set()
    for x in sorted(cps, key=lambda z: (-z.get("bars", 1), -z["strength"])):
        i, bias = x["i"], x["bias"]
        if bias == 0 or x["strength"] < 2 or (i, bias) in sudah:
            continue
        if x["name"] in CANDLE_PERLU_KONFIRMASI:
            i0 = max(0, i - x.get("bars", 1) + 1)
            lo, hi = float(np.min(l[i0:i + 1])), float(np.max(h[i0:i + 1]))
            atas, bawah = max(o[i], c[i]), min(o[i], c[i])
            gagal = False
            for j in range(i + 1, min(n, i + 4)):
                if (bias > 0 and c[j] > atas) or (bias < 0 and c[j] < bawah):
                    break
                if (bias > 0 and c[j] < lo) or (bias < 0 and c[j] > hi):
                    gagal = True
                    break
            if gagal:
                continue
        sudah.add((i, bias))
        out.append({"i": int(i), "bias": int(bias), "name": x["name"], "strength": x["strength"]})
    return sorted(out, key=lambda z: z["i"])


def bobot_candle(x, n, o, h, l, c, v, vs, a, levels, sma50, sma200, berjalan=False, has_vol=True):
    """Lengkapi satu pola candle dengan konteks: konfirmasi, lokasi, volume. Mengembalikan bobot sinyal (sudah dibatasi).

    - konfirmasi (hanya pola di CANDLE_PERLU_KONFIRMASI): "ya" bila candle sesudahnya close searah melewati badan pola,
      "gagal" bila close berlawanan melewati ujung pola, "tunggu" bila belum ada candle berikutnya yang selesai,
      "belum" bila candle sesudahnya ada tapi belum memutuskan.
    - lokasi: pola bullish yang low-nya menyentuh support (atau MA50/MA200) dan close di atasnya, pola bearish
      yang high-nya menyentuh resistance dan close di bawahnya.
    - volume: candle terakhir pola dibanding rata-rata 20 bar."""
    i, bias = x["i"], x["bias"]
    akhir = n - 2 if berjalan else n - 1  # candle terakhir yang sudah selesai
    i0 = max(0, i - x.get("bars", 1) + 1)
    lo, hi = float(np.min(l[i0:i + 1])), float(np.max(h[i0:i + 1]))
    aa = float(a[i]) if not np.isnan(a[i]) else float(hi - lo)
    kali = 1.0

    if x["name"] in CANDLE_PERLU_KONFIRMASI and bias != 0:
        # "tunggu" = belum ada candle berikutnya; "belum" = sudah ada, tapi belum memutuskan arah.
        x["konfirmasi"] = "tunggu" if i + 1 > akhir else "belum"
        atas_badan, bawah_badan = max(o[i], c[i]), min(o[i], c[i])
        for j in range(i + 1, akhir + 1):
            if (bias > 0 and c[j] > atas_badan) or (bias < 0 and c[j] < bawah_badan):
                x["konfirmasi"] = "ya"
                break
            if (bias > 0 and c[j] < lo) or (bias < 0 and c[j] > hi):
                x["konfirmasi"] = "gagal"
                break
        kali *= {"ya": 1.3, "gagal": 0.0}.get(x["konfirmasi"], 0.6)

    if bias != 0 and kali > 0:
        # 1.4.0: candle bullish hanya dicek ke support, bearish ke resistance (dulu semua level diberi label yang sama)
        jenis = "support" if bias > 0 else "resistance"
        daftar = levels.get(jenis, []) if isinstance(levels, dict) else levels
        calon = [(float(p), jenis) for p in daftar]
        for nama, ser in (("MA50", sma50), ("MA200", sma200)):
            if ser is not None and not np.isnan(ser[i]):
                calon.append((float(ser[i]), nama))
        kena = None
        for harga, nama in calon:
            if bias > 0 and abs(lo - harga) <= 0.6 * aa and c[i] > harga:
                kena = (harga, nama) if kena is None or abs(lo - harga) < abs(lo - kena[0]) else kena
            elif bias < 0 and abs(hi - harga) <= 0.6 * aa and c[i] < harga:
                kena = (harga, nama) if kena is None or abs(hi - harga) < abs(hi - kena[0]) else kena
        if kena:
            x["lokasi"] = {"jenis": kena[1], "harga": kena[0]}
            kali *= 1.4
        else:
            kali *= 0.8

    if has_vol and vs is not None and not np.isnan(vs[i]) and vs[i] > 0 and v[i] > 0:
        vr = float(v[i] / vs[i])
        x["volume_ratio"] = round(vr, 2)
        if bias != 0 and kali > 0:
            if vr >= 1.5:
                kali *= 1.3
            elif vr <= 0.7:
                kali *= 0.8

    umur = akhir - i
    w = bias * x["strength"] * 0.35 * (1.0 if umur <= 0 else 0.7) * kali
    w = max(-1.5, min(1.5, w))
    x["bobot"] = round(float(w), 2)
    return w


def teks_candle(x, n, market, berjalan=False):
    """Teks sinyal candle: nama, umur, lokasi, volume, status konfirmasi."""
    akhir = n - 2 if berjalan else n - 1
    umur = akhir - x["i"]
    bagian = ["candle terakhir" if umur <= 0 else f"{umur} candle lalu"]
    lok = x.get("lokasi")
    if lok:
        bagian.append(f"di {lok['jenis']} {fmt_price(lok['harga'], market)}")
    vr = x.get("volume_ratio")
    if vr is not None and x["bias"] != 0 and (vr >= 1.5 or vr <= 0.7):
        bagian.append(f"volume {vr:.1f}x rata-rata" if vr >= 1.5 else "volume tipis")
    k = x.get("konfirmasi")
    if k == "ya":
        bagian.append("terkonfirmasi candle berikutnya")
    elif k == "tunggu":
        bagian.append("menunggu konfirmasi candle berikutnya")
    elif k == "belum":
        bagian.append("belum terkonfirmasi")
    elif k == "gagal":
        bagian.append("gagal dikonfirmasi")
    return f"{x['name_id']} — " + ", ".join(bagian)


# =============================================================================
# 7. Pola chart
# =============================================================================


FLAG_ATR, FLAG_PCT, FLAG_TIANG, FLAG_LEBAR, FLAG_PANTUL = 4.5, 0.07, 12, 0.45, 0.45
TARGET_JAUH_TURUN, TARGET_JAUH_NAIK = 0.5, 1.0   # target pola > 50% di bawah / > 100% di atas harga: tidak dipakai
SKALA_SKOR = 10.0   # skor = 100·tanh(mentah / SKALA_SKOR); 1.2.x memakai 6 (63% hari berlabel "kuat")


def chart_patterns(o, h, l, c, a, sw):
    n = len(c)
    price = c[-1]
    a_last = a[-1]
    pats = []
    recent = n - 60

    def after_close(i):
        return c[i + 1:] if i + 1 < n else np.array([])

    S = [s for s in sw if s[0] >= n - 220]

    # --- Double / triple top & bottom
    for end in (len(S) - 1, len(S) - 2):
        if end < 2:
            continue
        x1, x2, x3 = S[end - 2], S[end - 1], S[end]
        if x3[0] < recent or x3[0] - x1[0] < 6:
            continue
        tol = max(0.8 * a[x3[0]], 0.02 * x3[2])
        if x1[1] == "H" and x2[1] == "L" and x3[1] == "H" and abs(x1[2] - x3[2]) <= tol and (min(x1[2], x3[2]) - x2[2]) >= max(2.5 * a[x3[0]], 0.03 * x3[2]):
            top = max(x1[2], x3[2])
            neck = x2[2]
            ac = after_close(x3[0])
            if len(ac) and ac.max() > top + 0.3 * a_last:
                continue
            conf = bool(len(ac) and (ac < neck - 0.1 * a_last).any())
            if conf and price > neck + 0.25 * a_last:
                continue  # 1.4.0: neckline sudah jebol lalu direbut kembali (bear trap): pola gagal, bukan sinyal turun
            target = neck - (top - neck)
            pats.append({"name": "Double Top", "name_id": "Double Top (puncak ganda)", "bias": -1,
                         "status": "terkonfirmasi" if conf else "terbentuk, menunggu tembus neckline",
                         "confirmed": conf, "points": [list(map(float, (x[0], x[2]))) for x in (x1, x2, x3)],
                         "neckline": float(neck), "invalidation": float(top), "target": float(target),
                         "start_idx": int(x1[0]), "end_idx": int(x3[0])})
            break
        if x1[1] == "L" and x2[1] == "H" and x3[1] == "L" and abs(x1[2] - x3[2]) <= tol and (x2[2] - max(x1[2], x3[2])) >= max(2.5 * a[x3[0]], 0.03 * x3[2]):
            bot = min(x1[2], x3[2])
            neck = x2[2]
            ac = after_close(x3[0])
            if len(ac) and ac.min() < bot - 0.3 * a_last:
                continue
            conf = bool(len(ac) and (ac > neck + 0.1 * a_last).any())
            if conf and price < neck - 0.25 * a_last:
                continue  # 1.4.0: neckline sudah tembus lalu ditinggalkan lagi (bull trap): pola gagal
            target = neck + (neck - bot)
            pats.append({"name": "Double Bottom", "name_id": "Double Bottom (lembah ganda)", "bias": 1,
                         "status": "terkonfirmasi" if conf else "terbentuk, menunggu tembus neckline",
                         "confirmed": conf, "points": [list(map(float, (x[0], x[2]))) for x in (x1, x2, x3)],
                         "neckline": float(neck), "invalidation": float(bot), "target": float(target),
                         "start_idx": int(x1[0]), "end_idx": int(x3[0])})
            break

    # --- Head & Shoulders / Inverse
    for end in (len(S) - 1, len(S) - 2):
        if end < 4:
            continue
        p = S[end - 4:end + 1]
        if p[-1][0] < recent:
            continue
        types = "".join(x[1] for x in p)
        ls, n1, hd, n2, rs = p
        if types == "HLHLH":
            sh_tol = max(1.2 * a[rs[0]], 0.035 * rs[2])
            if hd[2] > ls[2] + 0.5 * a[hd[0]] and hd[2] > rs[2] + 0.5 * a[hd[0]] and abs(ls[2] - rs[2]) <= sh_tol:
                neck_now = _line_at((n1[0], n1[2]), (n2[0], n2[2]), n - 1)
                neck_head = _line_at((n1[0], n1[2]), (n2[0], n2[2]), hd[0])
                ac = after_close(rs[0])
                if len(ac) and ac.max() > hd[2]:
                    continue
                conf = bool(len(ac) and ac[-1] < neck_now - 0.1 * a_last) or bool(len(ac) and (ac < np.array([_line_at((n1[0], n1[2]), (n2[0], n2[2]), z) for z in range(rs[0] + 1, n)]) - 0.1 * a_last).any())
                # 1.4.0: batal bila harga sekarang di atas bahu kanan (= level batal yang ditampilkan), atau neckline
                # sudah jebol lalu direbut kembali.
                if price > rs[2] or (conf and price > neck_now + 0.25 * a_last):
                    continue
                pats.append({"name": "Head and Shoulders", "name_id": "Head & Shoulders (pembalikan turun)", "bias": -1,
                             "status": "terkonfirmasi (neckline jebol)" if conf else "terbentuk, menunggu tembus neckline",
                             "confirmed": conf, "points": [list(map(float, (x[0], x[2]))) for x in p],
                             "neckline": float(neck_now), "neckline_pts": [[float(n1[0]), float(n1[2])], [float(n2[0]), float(n2[2])]],
                             "invalidation": float(rs[2]), "target": float(neck_now - (hd[2] - neck_head)),
                             "start_idx": int(ls[0]), "end_idx": int(rs[0])})
                break
        if types == "LHLHL":
            sh_tol = max(1.2 * a[rs[0]], 0.035 * rs[2])
            if hd[2] < ls[2] - 0.5 * a[hd[0]] and hd[2] < rs[2] - 0.5 * a[hd[0]] and abs(ls[2] - rs[2]) <= sh_tol:
                neck_now = _line_at((n1[0], n1[2]), (n2[0], n2[2]), n - 1)
                neck_head = _line_at((n1[0], n1[2]), (n2[0], n2[2]), hd[0])
                ac = after_close(rs[0])
                if len(ac) and ac.min() < hd[2]:
                    continue
                conf = bool(len(ac) and (ac > np.array([_line_at((n1[0], n1[2]), (n2[0], n2[2]), z) for z in range(rs[0] + 1, n)]) + 0.1 * a_last).any())
                if price < rs[2] or (conf and price < neck_now - 0.25 * a_last):
                    continue
                pats.append({"name": "Inverse Head and Shoulders", "name_id": "Inverse Head & Shoulders (pembalikan naik)", "bias": 1,
                             "status": "terkonfirmasi (neckline tembus)" if conf else "terbentuk, menunggu tembus neckline",
                             "confirmed": conf, "points": [list(map(float, (x[0], x[2]))) for x in p],
                             "neckline": float(neck_now), "neckline_pts": [[float(n1[0]), float(n1[2])], [float(n2[0]), float(n2[2])]],
                             "invalidation": float(rs[2]), "target": float(neck_now + (neck_head - hd[2])),
                             "start_idx": int(ls[0]), "end_idx": int(rs[0])})
                break

    # --- Segitiga, wedge, channel (garis regresi swing high & low)
    win = min(90, n - 5)
    W = [s for s in S if s[0] >= n - win]
    Hs = [s for s in W if s[1] == "H"][-4:]
    Ls = [s for s in W if s[1] == "L"][-4:]
    if len(Hs) >= 2 and len(Ls) >= 2 and len(Hs) + len(Ls) >= 5:
        start = min(Hs[0][0], Ls[0][0])
        hx, hy = np.array([s[0] for s in Hs], float), np.array([s[2] for s in Hs])
        lx, ly = np.array([s[0] for s in Ls], float), np.array([s[2] for s in Ls])
        sh, ih = np.polyfit(hx, hy, 1)
        sl, il = np.polyfit(lx, ly, 1)
        fit_ok = (np.abs(hy - (sh * hx + ih)).max() <= 0.9 * a_last) and (np.abs(ly - (sl * lx + il)).max() <= 0.9 * a_last)
        w0 = (sh * start + ih) - (sl * start + il)
        w1 = (sh * (n - 1) + ih) - (sl * (n - 1) + il)
        if fit_ok and w0 > 1.5 * a_last:
            L = (n - 1 - start)
            dh, dl = sh * L, sl * L
            flat = 0.3 * w0
            fh, fl = abs(dh) < flat, abs(dl) < flat
            converging = 0 < w1 < 0.75 * w0
            parallel = abs(w1 - w0) < 0.25 * w0
            name = None
            if converging:
                if fh and dl > flat:
                    name, nid, bias = "Ascending Triangle", "Ascending Triangle (segitiga naik, cenderung bullish)", 1
                elif fl and dh < -flat:
                    name, nid, bias = "Descending Triangle", "Descending Triangle (segitiga turun, cenderung bearish)", -1
                elif dh < -flat and dl > flat:
                    name, nid, bias = "Symmetrical Triangle", "Symmetrical Triangle (konsolidasi, tunggu arah breakout)", 0
                elif dh > flat and dl > flat:
                    name, nid, bias = "Rising Wedge", "Rising Wedge (wedge naik, cenderung bearish)", -1
                elif dh < -flat and dl < -flat:
                    name, nid, bias = "Falling Wedge", "Falling Wedge (wedge turun, cenderung bullish)", 1
            elif parallel:
                if fh and fl:
                    name, nid, bias = "Rectangle", "Rectangle / Sideways range", 0
                elif dh > flat and dl > flat:
                    name, nid, bias = "Ascending Channel", "Channel naik", 1
                elif dh < -flat and dl < -flat:
                    name, nid, bias = "Descending Channel", "Channel turun", -1
            if name:
                up_now, lo_now = sh * (n - 1) + ih, sl * (n - 1) + il
                status, conf, target, arah = "masih di dalam pola", False, None, 0
                if price > up_now + 0.2 * a_last:
                    status, conf, target, arah = "breakout ke atas", True, up_now + w0, 1
                    bias = 1 if bias >= 0 or name in ("Descending Triangle", "Descending Channel") else bias
                    if name == "Rising Wedge":
                        status = "tembus atas (pola wedge gagal)"
                        bias = 1
                    if name in ("Rising Wedge", "Descending Triangle"):
                        # pola yang biasanya bearish malah tembus ke atas: nama "cenderung bearish" menyesatkan
                        nid, status = f"{name} gagal (tembus ke atas, bullish)", "terkonfirmasi"
                elif price < lo_now - 0.2 * a_last:
                    status, conf, target, arah = "breakdown ke bawah", True, lo_now - w0, -1
                    bias = -1
                    if name in ("Falling Wedge", "Ascending Triangle"):
                        # pola yang biasanya bullish malah jebol ke bawah (mis. dulu tertulis
                        # "Falling Wedge (wedge turun, cenderung bullish) — breakdown ke bawah" dengan tanda merah)
                        nid, status = f"{name} gagal (jebol ke bawah, bearish)", "terkonfirmasi"
                pats.append({"name": name, "name_id": nid, "bias": int(bias), "status": status, "confirmed": conf,
                             "upper": [[float(start), float(sh * start + ih)], [float(n - 1), float(up_now)]],
                             "lower": [[float(start), float(sl * start + il)], [float(n - 1), float(lo_now)]],
                             "upper_now": float(up_now), "lower_now": float(lo_now), "target": None if target is None else float(target),
                             "start_idx": int(start), "end_idx": int(n - 1)})
                if arah:
                    # bar pertama rangkaian close terakhir di luar garis = awal breakout (dipakai cek "target tercapai")
                    j = n - 1
                    while j - 1 > start and ((arah > 0 and c[j - 1] > sh * (j - 1) + ih) or (arah < 0 and c[j - 1] < sl * (j - 1) + il)):
                        j -= 1
                    pats[-1]["break_idx"] = int(j)

    # --- Bull / bear flag
    # 1.3.0: syarat diperketat (dulu muncul di ~30% aset sekaligus saat pasar turun). Tiang harus tajam
    # (≥ FLAG_ATR ATR dan ≥ FLAG_PCT dalam ≤ FLAG_TIANG bar), bendera sempit (≤ FLAG_LEBAR × tiang) dan
    # hanya memantul ≤ FLAG_PANTUL × tiang.
    best = None
    for cl in range(4, 16):
        pe = n - 1 - cl
        if pe < 5:
            break
        # 1.4.0: kotak bendera tanpa candle terakhir, supaya candle terakhir bisa menjadi breakout
        # (dulu ikut dihitung, sehingga close > batas atas kotak mustahil terjadi).
        cons_h, cons_l = h[pe + 1:n - 1].max(), l[pe + 1:n - 1].min()
        for pl_ in range(3, FLAG_TIANG + 1):
            ps = pe - pl_
            if ps < 0:
                break
            move = c[pe] - c[ps]
            aa = a[pe] if not np.isnan(a[pe]) else a_last
            if abs(move) < FLAG_ATR * aa or abs(move) / c[ps] < FLAG_PCT:
                continue
            if (cons_h - cons_l) > FLAG_LEBAR * abs(move):
                continue
            if move > 0 and cons_l > c[pe] - FLAG_PANTUL * move and cons_h <= h[ps:pe + 1].max() + 0.3 * aa:
                cand = ("Bull Flag", "Bull Flag (konsolidasi setelah reli, lanjutan naik)", 1, ps, pe, move, cons_h, cons_l)
            elif move < 0 and cons_h < c[pe] - FLAG_PANTUL * move and cons_l >= l[ps:pe + 1].min() - 0.3 * aa:
                cand = ("Bear Flag", "Bear Flag (konsolidasi setelah turun, lanjutan turun)", -1, ps, pe, move, cons_h, cons_l)
            else:
                continue
            if best is None or abs(move) > abs(best[5]):
                best = cand
    if best:
        name, nid, bias, ps, pe, move, ch_, cl_ = best
        brk = ch_ if bias > 0 else cl_
        conf = (price > ch_) if bias > 0 else (price < cl_)
        pats.append({"name": name, "name_id": nid, "bias": bias,
                     "status": "breakout" if conf else "konsolidasi (tunggu breakout)", "confirmed": bool(conf),
                     "pole": [[float(ps), float(c[ps])], [float(pe), float(c[pe])]],
                     "box": [float(pe + 1), float(cl_), float(n - 1), float(ch_)],
                     "trigger": float(brk), "target": float(brk + move), "invalidation": float(cl_ if bias > 0 else ch_),
                     "start_idx": int(ps), "end_idx": int(n - 1)})
        if conf:
            j = n - 1
            while j - 1 > pe and ((bias > 0 and c[j - 1] > ch_) or (bias < 0 and c[j - 1] < cl_)):
                j -= 1
            pats[-1]["break_idx"] = int(j)
    # Double top/bottom yang belum terkonfirmasi dan menempel di batas segitiga/flag = bagian dari pola itu
    geo = [p for p in pats if p["name"] in ("Ascending Triangle", "Descending Triangle", "Rectangle", "Bull Flag", "Bear Flag", "Symmetrical Triangle")]
    keep = []
    for p in pats:
        if p["name"] in ("Double Top", "Double Bottom") and any(g["start_idx"] <= p["end_idx"] and (not p["confirmed"] or g["name"] in ("Bull Flag", "Bear Flag")) for g in geo):
            continue
        keep.append(p)
    # 1.3.0: target yang sudah tercapai ditandai (dulu tetap ditulis "target X" walau harga sudah melewatinya),
    # dan target yang tidak wajar (≤ 0, atau lebih dari 50% di bawah / 100% di atas harga) tidak dipakai.
    for p in keep:
        tg = p.get("target")
        if tg is None or not p.get("bias"):
            continue
        if tg <= 0 or (p["bias"] < 0 and tg < price * (1 - TARGET_JAUH_TURUN)) or (p["bias"] > 0 and tg > price * (1 + TARGET_JAUH_NAIK)):
            p["target_teoretis"], p["target"] = float(tg), None
            continue
        if not p.get("confirmed"):
            continue
        # pola swing: sejak swing terakhir; pola garis/flag: sejak awal breakout (break_idx). Bukan sejak awal pola:
        # harga di awal wedge/channel sering sudah melewati targetnya, sehingga breakout baru langsung dicap "tercapai".
        k = min(int(p["end_idx"]), n - 1) if "points" in p else int(p.get("break_idx", n - 3))
        k = max(0, min(k, n - 1))
        p["target_hit"] = bool(l[k:].min() <= tg) if p["bias"] < 0 else bool(h[k:].max() >= tg)
    return keep


def teks_target(p, fp):
    """', target 750' / ', target 750 sudah tercapai' / '' — dipakai tanda, markdown, dan narasi."""
    if p.get("target") is None:
        return ""
    return f", target {fp(p['target'])}" + (" sudah tercapai" if p.get("target_hit") else "")


def divergences(h, l, c, r, ph, pl):
    n = len(c)
    out = []
    lows = [i for i in pl if not np.isnan(r[i])][-2:]
    highs = [i for i in ph if not np.isnan(r[i])][-2:]
    # 1.4.0: batal bila harga sudah menembus ujung pivot kedua (bullish: close di bawah low pivot; bearish: di atas high)
    if len(lows) == 2 and lows[1] >= n - 25 and lows[1] - lows[0] >= 4 and c[-1] >= l[lows[1]]:
        i, j = lows
        if l[j] < l[i] and r[j] > r[i] + 2:
            out.append({"name": "Bullish RSI Divergence", "name_id": "Divergence bullish RSI (harga lower low, RSI higher low)", "bias": 1, "i1": int(i), "i2": int(j)})
        elif l[j] > l[i] and r[j] < r[i] - 2:
            out.append({"name": "Hidden Bullish Divergence", "name_id": "Hidden divergence bullish (tren naik berlanjut)", "bias": 1, "i1": int(i), "i2": int(j), "weak": True})
    if len(highs) == 2 and highs[1] >= n - 25 and highs[1] - highs[0] >= 4 and c[-1] <= h[highs[1]]:
        i, j = highs
        if h[j] > h[i] and r[j] < r[i] - 2:
            out.append({"name": "Bearish RSI Divergence", "name_id": "Divergence bearish RSI (harga higher high, RSI lower high)", "bias": -1, "i1": int(i), "i2": int(j)})
        elif h[j] < h[i] and r[j] > r[i] + 2:
            out.append({"name": "Hidden Bearish Divergence", "name_id": "Hidden divergence bearish (tren turun berlanjut)", "bias": -1, "i1": int(i), "i2": int(j), "weak": True})
    return out


# =============================================================================
# 8. Analisa utama
# =============================================================================


def _arah(a, b):
    """1 bila a > b, −1 bila a < b, 0 bila sama (1.4.0: harga datar tidak lagi dihitung bearish)."""
    return 1 if a > b else -1 if a < b else 0


def _last(x):
    x = np.asarray(x, float)
    return float(x[-1]) if len(x) and not np.isnan(x[-1]) else None


def _crossed(a1, b1, lookback):
    """+1 jika a memotong ke atas b dalam lookback bar terakhir, -1 jika ke bawah, 0 jika tidak."""
    d = a1 - b1
    for k in range(1, min(lookback, len(d) - 1) + 1):
        i = len(d) - k
        if np.isnan(d[i]) or np.isnan(d[i - 1]):
            break
        if d[i - 1] <= 0 < d[i]:
            return 1, k - 1
        if d[i - 1] >= 0 > d[i]:
            return -1, k - 1
    return 0, None


def analyze(bars, symbol="", market=None, tf="1d", include_series=False, meta=None, live_frac=None):
    """live_frac: bagian sesi yang sudah berjalan (0–1) bila bar terakhir belum selesai, None bila sudah selesai.
    Bila diisi: volume bar terakhir diproyeksikan ke satu bar penuh, sinyal volume diabaikan di awal sesi,
    dan pola candlestick pada bar yang belum selesai tidak dihitung."""
    b = bars if isinstance(bars, dict) else to_bars(bars)
    t, o, h, l, c, v = (np.asarray(b[k], float) for k in "tohlcv")
    n = len(c)
    v_asli = v
    berjalan = live_frac is not None and n > 1
    if berjalan:
        live_frac = float(min(1.0, max(0.0, live_frac)))
        v = v.copy()
        v[-1] = v[-1] / max(live_frac, 0.05)
    if n < 30:
        raise ValueError(f"Butuh minimal 30 bar, hanya ada {n}.")
    if market is None:
        market = resolve(symbol)[0][0] if symbol else "us"
    price = float(c[-1])

    # --- indikator
    s20, s50, s200 = sma(c, 20), sma(c, 50), sma(c, 200)
    e9, e21 = ema(c, 9), ema(c, 21)
    r = rsi(c)
    m, ms, mh = macd(c)
    bu, bm, bl = bollinger(c)
    a = atr(h, l, c)
    a = np.where(np.isnan(a), np.nanmean(true_range(h, l, c)[:14]), a)
    a = np.maximum(np.nan_to_num(a, nan=0.0), max(abs(price) * 1e-4, 1e-9))  # 1.4.0: harga datar total -> ATR 0 -> bagi nol
    k_, d_ = stochastic(h, l, c)
    ax, pdi, mdi = adx(h, l, c)
    vs = sma(v, 20)
    ob = obv(c, v_asli if berjalan and live_frac < 0.25 else v)  # 1.4.0: proyeksi volume awal sesi (s.d. 20×) tidak masuk OBV
    a_last = float(a[-1])
    has_vol = bool(np.nansum(v[-20:]) > 0)

    ind = {
        "price": price, "change_pct": float((c[-1] / c[-2] - 1) * 100) if n > 1 else 0.0,
        "sma20": _last(s20), "sma50": _last(s50), "sma200": _last(s200), "ema9": _last(e9), "ema21": _last(e21),
        "rsi14": _last(r), "macd": _last(m), "macd_signal": _last(ms), "macd_hist": _last(mh),
        "bb_upper": _last(bu), "bb_mid": _last(bm), "bb_lower": _last(bl),
        "atr14": a_last, "atr_pct": a_last / price * 100,
        "stoch_k": _last(k_), "stoch_d": _last(d_), "adx14": _last(ax), "plus_di": _last(pdi), "minus_di": _last(mdi),
        "volume": float(v_asli[-1]), "volume_avg20": _last(vs), "volume_ratio": (float(v[-1] / vs[-1]) if has_vol and _isnum(_last(vs)) and vs[-1] > 0 else None),
        "high_52w": float(h[-252:].max()), "low_52w": float(l[-252:].min()),
    }
    bw = (bu - bl) / bm
    if n >= 140 and not np.isnan(bw[-1]):
        ind["bb_width_pct"] = float(bw[-1] * 100)
        ind["bb_squeeze"] = bool(bw[-1] <= np.nanpercentile(bw[-126:], 10))
    else:
        ind["bb_squeeze"] = False

    # --- struktur
    kmaj = 5 if n >= 150 else 3
    ph5, pl5 = pivots(h, l, kmaj)
    ph3, pl3 = pivots(h, l, 3)
    sw = swings(h, l, a, k=3, min_atr=1.0)
    # 1.4.0: indeks digabung tanpa dobel (pivot k=5 hampir selalu juga pivot k=3; dulu terhitung dua sentuhan)
    sup, res = support_resistance(h, l, c, a_last, sorted(set(ph5) | set(ph3[-6:])), sorted(set(pl5) | set(pl3[-6:])), n)
    tls = trendlines(h, l, c, a, ph3, pl3)
    cps = candle_patterns(o, h, l, c, a)
    if berjalan:
        cps = [x for x in cps if x["i"] < n - 1]  # candle yang belum selesai belum membentuk pola
    chp = chart_patterns(o, h, l, c, a, sw)
    dv = divergences(h, l, c, r, ph3, pl3)

    # --- tren
    sH = [s for s in sw if s[1] == "H"][-2:]
    sL = [s for s in sw if s[1] == "L"][-2:]
    structure = "campuran"
    st_score = 0
    if len(sH) == 2 and len(sL) == 2:
        hh, hl = sH[1][2] > sH[0][2], sL[1][2] > sL[0][2]
        if hh and hl:
            structure, st_score = "higher high & higher low (naik)", 2
        elif not hh and not hl:
            structure, st_score = "lower high & lower low (turun)", -2
        elif hl:
            structure, st_score = "higher low, tapi lower high (menyempit)", 0.5
        else:
            structure, st_score = "higher high, tapi lower low (melebar/volatil)", -0.5
    lb = min(50, n)
    xs = np.arange(lb)
    slope = np.polyfit(xs, c[-lb:], 1)[0]
    slope_atr = float(slope * lb / a_last)

    signals = []

    def sig(cat, score, text):
        signals.append({"cat": cat, "score": round(float(score), 2), "text": text})

    # MA
    ma_pts = 0.0
    if ind["sma50"]:
        ma_pts += _arah(price, ind["sma50"])
    if ind["sma200"]:
        ma_pts += _arah(price, ind["sma200"])
        if ind["sma50"]:
            ma_pts += _arah(ind["sma50"], ind["sma200"])
    elif ind["sma20"] and ind["sma50"]:
        ma_pts += _arah(ind["sma20"], ind["sma50"])
    adx_v = ind["adx14"] or 0
    trend_mult = 1.25 if adx_v >= 25 else 0.7 if adx_v < 18 else 1.0
    if ma_pts >= 2:
        txt = "Harga di atas MA50" + (" & MA200, MA50 > MA200 (tren naik sehat)" if ind["sma200"] else "")
    elif ma_pts <= -2:
        txt = "Harga di bawah MA50" + (" & MA200, MA50 < MA200 (tren turun)" if ind["sma200"] else "")
    else:
        txt = "Posisi harga vs moving average campuran"
    sig("Tren", ma_pts * trend_mult, txt)
    sig("Tren", st_score * trend_mult, f"Struktur swing: {structure}")
    gc, gk = _crossed(s50, s200, 15)
    if gc:
        sig("Tren", 1.0 * gc, ("Golden cross" if gc > 0 else "Death cross") + f" MA50/MA200 {gk} bar lalu")
    if adx_v:
        dirn = "naik" if (ind["plus_di"] or 0) > (ind["minus_di"] or 0) else "turun"
        sig("Tren", 0, f"ADX {adx_v:.0f}: " + ("tren kuat" if adx_v >= 25 else "tren lemah / sideways" if adx_v < 18 else "tren sedang") + f", arah DI {dirn}")

    if slope_atr > 3:
        trend_label = "Uptrend kuat" if st_score > 0 and adx_v >= 25 else "Uptrend"
    elif slope_atr > 1:
        trend_label = "Uptrend"
    elif slope_atr < -3:
        trend_label = "Downtrend kuat" if st_score < 0 and adx_v >= 25 else "Downtrend"
    elif slope_atr < -1:
        trend_label = "Downtrend"
    else:
        trend_label = "Sideways"

    # Momentum
    rv = ind["rsi14"]
    if rv is not None:
        if rv >= 70:
            sig("Momentum", 0, f"RSI {rv:.0f} overbought: momentum kuat tapi rawan koreksi")
        elif rv >= 55:
            sig("Momentum", 1, f"RSI {rv:.0f}: momentum bullish")
        elif rv > 45:
            sig("Momentum", 0, f"RSI {rv:.0f}: netral")
        elif rv > 30:
            sig("Momentum", -1, f"RSI {rv:.0f}: momentum bearish")
        else:
            sig("Momentum", 0, f"RSI {rv:.0f} oversold: tekanan jual berat, peluang technical rebound")
    if ind["macd"] is not None and ind["macd_signal"] is not None:
        mc, mk = _crossed(m, ms, 5)
        pts = 0.75 * _arah(m[-1], ms[-1]) + 0.5 * _arah(m[-1], 0)
        rising = mh[-1] > mh[-2] if not np.isnan(mh[-2]) else False
        txt = f"MACD {'di atas' if m[-1] > ms[-1] else 'di bawah'} signal, {'di atas' if m[-1] > 0 else 'di bawah'} nol, histogram {'menguat' if rising else 'melemah'}"
        if mc:
            txt += f" — baru cross {'ke atas' if mc > 0 else 'ke bawah'} {mk} bar lalu"
            pts += 0.5 * mc
        sig("Momentum", pts, txt)
    if ind["stoch_k"] is not None and ind["stoch_d"] is not None:
        sc, _ = _crossed(k_, d_, 3)
        if sc > 0 and ind["stoch_k"] < 30:
            sig("Momentum", 0.5, "Stochastic cross naik di area oversold")
        elif sc < 0 and ind["stoch_k"] > 70:
            sig("Momentum", -0.5, "Stochastic cross turun di area overbought")
    # 1.4.0: bobot diturunkan (1,5 -> 0,75; hidden 0,75 -> 0,4). Di uji_skor 1.3.0 kategori ini justru berlawanan arah
    # dengan hasil 20 hari di ketiga pasar.
    for d in dv:
        sig("Divergence", (0.4 if d.get("weak") else 0.75) * d["bias"], d["name_id"])

    # Volume
    if has_vol and ind["volume_ratio"]:
        vr = ind["volume_ratio"]
        up_bar = c[-1] >= o[-1]
        if vr >= 1.5 and not (berjalan and live_frac < 0.25):
            sig("Volume", 0.5 if up_bar else -0.5, f"Volume {vr:.1f}x rata-rata 20 hari pada candle {'naik' if up_bar else 'turun'}" + (" (proyeksi, candle belum selesai)" if berjalan else ""))
        obv_s = np.polyfit(np.arange(20), ob[-20:], 1)[0] if n >= 20 else 0
        pr_s = np.polyfit(np.arange(20), c[-20:], 1)[0] if n >= 20 else 0
        if obv_s > 0 and pr_s < 0:
            sig("Volume", 0.5, "OBV naik saat harga turun (akumulasi tersembunyi)")
        elif obv_s < 0 and pr_s > 0:
            sig("Volume", -0.5, "OBV turun saat harga naik (distribusi, kenaikan kurang didukung volume)")

    # Breakout & Bollinger
    if n >= 21:
        hi20, lo20 = h[-21:-1].max(), l[-21:-1].min()
        if price > hi20:
            sig("Breakout", 1, f"Harga menembus high 20 bar ({fmt_price(hi20, market)})")
        elif price < lo20:
            sig("Breakout", -1, f"Harga jebol low 20 bar ({fmt_price(lo20, market)})")
    if ind.get("bb_squeeze"):
        sig("Volatilitas", 0, "Bollinger squeeze: volatilitas sangat rendah, biasanya mendahului pergerakan besar")
    if ind["bb_upper"] and price > ind["bb_upper"]:
        sig("Volatilitas", 0, "Harga di atas Bollinger atas (kuat, tapi sudah meregang)")
    elif ind["bb_lower"] and price < ind["bb_lower"]:
        sig("Volatilitas", 0, "Harga di bawah Bollinger bawah (lemah, tapi sudah meregang)")

    # Pola
    for p in chp:
        w = 2.0 if p["confirmed"] else 1.0
        if p["name"] in ("Ascending Channel", "Descending Channel", "Rectangle"):
            w *= 0.5
        if p.get("target_hit"):
            w = min(w, 0.5)  # gerakan terukurnya sudah selesai: pola ini bukan lagi alasan utama
        sig("Pola chart", w * p["bias"], f"{p['name_id']} — {p['status']}" + (", target sudah tercapai" if p.get("target_hit") else ""))
    # Candle 3 bar terakhir (yang sudah selesai). Bobot memperhitungkan konfirmasi, lokasi (S/R, MA50/MA200), dan volume.
    akhir_c = n - 2 if berjalan else n - 1
    calon_c = [x for x in cps if x["i"] >= akhir_c - 2]
    # Pola yang seluruh candlenya sudah tercakup pola lain yang lebih panjang ke arah yang sama tidak dihitung lagi
    # (mis. Engulfing di dalam Three Outside Up, Harami di dalam Three Inside Up). Pola netral hanya untuk candle terakhir.
    calon_c.sort(key=lambda x: (-x.get("bars", 1), -x["strength"], -x["i"]))
    recent_c, rentang_c = [], []
    for x in calon_c:
        x0 = x["i"] - x.get("bars", 1) + 1
        if x["bias"] == 0 and x["i"] < akhir_c:
            continue
        if any(b_ == x["bias"] and a0 <= x0 and x["i"] <= a1 for a0, a1, b_ in rentang_c):
            continue
        rentang_c.append((x0, x["i"], x["bias"]))
        recent_c.append(x)
    recent_c.sort(key=lambda x: x["i"])
    level_c = {"support": [s_["price"] for s_ in sup[:3]], "resistance": [s_["price"] for s_ in res[:3]]}
    bobot_c = [bobot_candle(x, n, o, h, l, c, v, vs, a, level_c, s50, s200, berjalan, has_vol) for x in recent_c]
    # Candlestick hanya pemicu jangka pendek: total sumbangannya dibatasi ±2 poin.
    total_c = sum(bobot_c)
    skala_c = 2.0 / abs(total_c) if abs(total_c) > 2.0 else 1.0
    for x, w in zip(recent_c, bobot_c):
        if skala_c != 1.0:
            x["bobot"] = round(w * skala_c, 2)
        sig("Candlestick", w * skala_c, teks_candle(x, n, market, berjalan))
    for tl in tls:
        if tl["broken"]:
            sig("Trendline", -1 if tl["kind"] == "support" else 1, f"Trendline {tl['kind']} {'jebol' if tl['kind'] == 'support' else 'tembus'} di sekitar {fmt_price(tl.get('break_price', tl['value_now']), market)}")

    # Lokasi vs S/R
    if sup and (price - sup[0]["price"]) <= 0.6 * a_last:
        sig("Lokasi", 0.5, f"Dekat support {fmt_price(sup[0]['price'], market)}")
    if res and (res[0]["price"] - price) <= 0.6 * a_last:
        sig("Lokasi", -0.5, f"Dekat resistance {fmt_price(res[0]['price'], market)}")

    raw = sum(s["score"] for s in signals)
    score = int(round(100 * math.tanh(raw / SKALA_SKOR)))
    # 1.3.0: skor bullish saat tren 50 bar masih turun (atau sebaliknya) = pembalikan awal, belum "kuat":
    # skor dibatasi ±49 dan labelnya menyebut trennya, supaya tidak tampil "+72 Bullish kuat · Downtrend".
    lawan_tren = (score >= 20 and trend_label.startswith("Downtrend")) or (score <= -20 and trend_label.startswith("Uptrend"))
    if lawan_tren:
        score = max(-49, min(49, score))
    if lawan_tren and score > 0:
        label, label_id = "Buy", "Bullish awal (tren masih turun)"
    elif lawan_tren:
        label, label_id = "Sell", "Bearish awal (tren masih naik)"
    elif score >= 50:
        label, label_id = "Strong Buy", "Bullish kuat"
    elif score >= 20:
        label, label_id = "Buy", "Bullish"
    elif score > -20:
        label, label_id = "Neutral", "Netral / tunggu konfirmasi"
    elif score > -50:
        label, label_id = "Sell", "Bearish"
    else:
        label, label_id = "Strong Sell", "Bearish kuat"

    plan = trade_plan(price, a_last, score, sup, res, chp, market, rv, ind["ema21"], ind["high_52w"])

    result = {
        "version": VERSION, "symbol": symbol, "market": market, "tf": tf, "bars": n,
        "last_time": datetime.fromtimestamp(float(t[-1]), timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
        "meta": meta or {},
        "price": price, "indicators": ind,
        "trend": {"label": trend_label, "structure": structure, "slope_atr_50": round(slope_atr, 2), "adx": adx_v},
        "support": sup, "resistance": res, "trendlines": tls,
        "chart_patterns": chp, "candles_recent": recent_c, "divergences": dv,
        "signals": signals, "score": score, "raw_score": round(raw, 2), "lawan_tren": bool(lawan_tren), "label": label, "label_id": label_id,
        "plan": plan,
    }
    if berjalan:
        ind["volume_proyeksi"] = True
        result["bar_berjalan"] = {"fraksi": round(live_frac, 3)}
    if include_series:
        result["series"] = {
            "t": t.tolist(), "o": o.tolist(), "h": h.tolist(), "l": l.tolist(), "c": c.tolist(), "v": v_asli.tolist(),
            "sma20": s20.tolist(), "sma50": s50.tolist(), "sma200": s200.tolist(), "ema9": e9.tolist(), "ema21": e21.tolist(),
            "bb_upper": bu.tolist(), "bb_lower": bl.tolist(), "rsi": r.tolist(), "macd": m.tolist(), "macd_signal": ms.tolist(),
            "macd_hist": mh.tolist(), "stoch_k": k_.tolist(), "stoch_d": d_.tolist(), "atr": a.tolist(),
            "candles_all": cps, "candles_panah": panah_candle(cps, o, h, l, c, n), "swings": [[int(s[0]), s[1], float(s[2])] for s in sw],
        }
    return _clean(result)


def trade_plan(price, a, score, sup, res, pats, market, rsi_v=None, ema21_v=None, high52=None):
    rp = lambda x: round_price(x, market)  # noqa: E731
    sup_p = [s["price"] for s in sup]
    res_p = [s["price"] for s in res]
    if not res_p and high52 and high52 > price + 0.5 * a:
        res_p = [high52]
    # 1.4.0: target pola yang sudah tercapai atau terlalu dekat (< 0,7 ATR) tidak dipakai sebagai target rencana
    pat_targets_up = [p["target"] for p in pats if p.get("target") and p["bias"] > 0 and p["target"] - price >= 0.7 * a and not p.get("target_hit")]
    pat_targets_dn = [p["target"] for p in pats if p.get("target") and p["bias"] < 0 and price - p["target"] >= 0.7 * a and not p.get("target_hit")]
    if score >= 20:
        near_sup = next((s for s in sup_p if price - s <= 3 * a), None)
        overbought = bool(rsi_v and rsi_v >= 70)
        if overbought:
            entry_hi = price - 0.5 * a
            entry_lo = min(max(ema21_v or price - 2 * a, price - 2.5 * a), entry_hi - 0.5 * a)
        else:
            entry_hi = price
            entry_lo = max(near_sup or price - a, price - a)
        ref = (entry_lo + entry_hi) / 2 if overbought else price
        stop = (near_sup - 0.5 * a) if (near_sup and near_sup < entry_lo) else entry_lo - 1.0 * a
        stop = min(stop, entry_lo - 0.5 * a, ref - 1.0 * a)
        risk = ref - stop
        tg = [x for x in res_p if x - ref >= 0.7 * a][:2] + sorted(pat_targets_up)[:1]
        tg = sorted(set(rp(x) for x in tg))
        for mult in (2, 3, 4, 6):
            if len(tg) >= 2:
                break
            x = rp(ref + risk * mult)
            if x not in tg and x > ref:
                tg = sorted(tg + [x])
        if overbought:
            note = (f"RSI {rsi_v:.0f} sudah overbought — jangan kejar harga. Tunggu koreksi ke area beli (sekitar EMA21) "
                    "dan pastikan harga memantul; rencana batal jika close di bawah Stop.")
        else:
            note = "Paling ideal membeli saat harga terkoreksi ke area beli; rencana batal jika close di bawah Stop."
        if not res and not (high52 and high52 > price + 0.5 * a):
            note += " Harga di area tertinggi: tidak ada resistance historis, target memakai kelipatan risiko (R)."
        if tg and (tg[0] - ref) / risk < 1.5:
            note += " R:R ke target pertama di bawah 1,5: lebih baik membeli lebih dekat ke support supaya risikonya kecil."
        return {"bias": "long", "bias_id": "Beli saat koreksi",
                "entry_zone": [rp(entry_lo), rp(entry_hi)], "entry_ref": rp(ref), "stop_loss": rp(stop), "targets": tg[:3],
                "risk_pct": round(risk / ref * 100, 2),
                "rr": [round((x - ref) / risk, 2) for x in tg[:3]],
                "invalidation": rp(stop), "note": note}
    if score <= -20:
        near_res = next((r_ for r_ in res_p if r_ - price <= 3 * a), None)
        stop = (near_res + 0.5 * a) if near_res else price + 2 * a
        stop = max(stop, price + 1.0 * a)
        risk = stop - price
        tg = [x for x in sup_p if price - x >= 0.7 * a][:2] + sorted(pat_targets_dn, reverse=True)[:1]
        tg = sorted(set(rp(x) for x in tg), reverse=True)
        for mult in (2, 3, 4, 6):
            if len(tg) >= 2:
                break
            x = rp(price - risk * mult)
            if x not in tg and x is not None and 0 < x < price:
                tg = sorted(tg + [x], reverse=True)
        tg = [x for x in tg if x > 0]
        back = f"Pertimbangkan beli kembali hanya jika harga bertahan di support {fmt_price(tg[0], market) if tg else '-'} dan muncul sinyal pembalikan."
        if market == "idx":
            note = "Saham IDX umumnya tidak bisa short: anggap ini sinyal untuk menghindari beli / mengurangi posisi. " + back
        elif market == "us":
            note = "Untuk investor, artinya hindari beli / kurangi posisi (short hanya lewat broker yang mendukung, dengan stop di atas resistance). " + back
        elif market == "crypto":
            note = "Untuk kripto bisa short (futures) dengan stop di atas resistance; untuk spot artinya hindari beli / kurangi posisi."
        else:
            note = "Tekanan turun dominan: hindari beli / kurangi posisi. " + back
        return {"bias": "short", "bias_id": "Belum saatnya beli",
                "entry_zone": [rp(price), rp(min(near_res or price + a, price + a))], "stop_loss": rp(stop), "targets": tg[:3],
                "risk_pct": round(risk / price * 100, 2), "rr": [round((price - x) / risk, 2) for x in tg[:3]],
                "invalidation": rp(stop), "note": note}
    s1 = sup_p[0] if sup_p else price - 2 * a
    r1 = res_p[0] if res_p else price + 2 * a
    return {"bias": "wait", "bias_id": "Tunggu konfirmasi",
            "buy_trigger": rp(r1 + 0.2 * a), "sell_trigger": rp(s1 - 0.2 * a),
            "range": [rp(s1), rp(r1)], "stop_loss": None, "targets": [],
            "note": f"Sinyal belum searah. Skenario naik valid jika close di atas {fmt_price(rp(r1 + 0.2 * a), market)}; "
                    f"skenario turun jika close di bawah {fmt_price(rp(s1 - 0.2 * a), market)}. Trading range: beli dekat support, jual dekat resistance."}


def detect_tf(bars):
    """Tebak timeframe dari jarak antar bar."""
    d = float(np.median(np.diff(bars["t"]))) if len(bars["t"]) > 2 else 86400
    for tf, sec in (("15m", 900), ("30m", 1800), ("1h", 3600), ("4h", 14400)):
        if d <= sec * 1.5:
            return tf
    if d <= 4 * 86400:
        return "1d"
    if d <= 10 * 86400:
        return "1wk"
    return "1mo"


def analyze_mtf(bars_by_tf, symbol="", market=None, primary=None, include_series=False, meta=None, live_frac=None):
    """Analisa multi-timeframe. bars_by_tf = {'1d': bars, '1wk': bars, ...}."""
    order = ["15m", "30m", "1h", "4h", "1d", "1wk", "1mo"]
    tfs = sorted(bars_by_tf, key=lambda x: order.index(x) if x in order else 99)
    primary = primary or tfs[0]
    results = {}
    for tf in tfs:
        bb = bars_by_tf[tf]
        if len(bb["c"]) < 30:
            continue
        results[tf] = analyze(bb, symbol=symbol, market=market, tf=tf, include_series=include_series and tf == primary, meta=meta,
                              live_frac=live_frac if tf == primary else None)
    main = results[primary]
    summary = [{"tf": tf, "trend": r_["trend"]["label"], "score": r_["score"], "label_id": r_["label_id"]} for tf, r_ in results.items()]
    signs = [np.sign(x["score"]) if abs(x["score"]) >= 20 else 0 for x in summary]
    if all(s > 0 for s in signs):
        conf = "Semua timeframe bullish — konfluensi kuat"
    elif all(s < 0 for s in signs):
        conf = "Semua timeframe bearish — konfluensi kuat"
    elif signs and signs[-1] != 0 and signs[0] != 0 and signs[0] != signs[-1]:
        conf = "Timeframe kecil berlawanan dengan timeframe besar — kemungkinan koreksi/pantulan di dalam tren besar"
    else:
        conf = "Campuran — sebagian timeframe netral"
    main["mtf"] = {"summary": summary, "confluence": conf}
    return main


def run_json(csv_text=None, rows=None, symbol="", market=None, tf=None, meta=None):
    """Kembalikan JSON string hasil analisa + series (format yang sama dengan dashboard)."""
    b = parse_csv(csv_text) if csv_text else to_bars(rows)
    tf = tf or detect_tf(b)
    if not market or market == "auto":
        market = resolve(symbol)[0][0] if symbol else "us"
    res = analyze_mtf(auto_mtf(b, tf, market), symbol=symbol, market=market, primary=tf, include_series=True, meta=meta)
    return json.dumps(res, ensure_ascii=False, allow_nan=False)


def auto_mtf(bars, tf="1d", market=None):
    """Buat timeframe lebih besar dari data yang ada."""
    out = {tf: bars}
    if tf in ("1h", "30m", "15m"):
        out["4h"] = resample(bars, "4h", market)
        out["1d"] = resample(bars, "1d", market)
    elif tf == "4h":
        out["1d"] = resample(bars, "1d", market)
    elif tf == "1d":
        out["1wk"] = resample(bars, "1wk", market)
    elif tf == "1wk":
        out["1mo"] = resample(bars, "1mo", market)
    return {k: v for k, v in out.items() if len(v["c"]) >= 30}


def _clean(x):
    if isinstance(x, dict):
        return {k: _clean(v) for k, v in x.items()}
    if isinstance(x, (list, tuple)):
        return [_clean(v) for v in x]
    if isinstance(x, (np.floating, float)):
        return None if math.isnan(x) or math.isinf(x) else float(x)
    if isinstance(x, (np.integer,)):
        return int(x)
    if isinstance(x, np.bool_):
        return bool(x)
    return x


# =============================================================================
# 9. Laporan
# =============================================================================


def to_markdown(r):
    mk = r["market"]
    fp = lambda x: fmt_price(x, mk)  # noqa: E731
    ind = r["indicators"]
    mname = {"idx": "Saham IDX", "us": "Saham US", "crypto": "Kripto"}.get(mk, mk)
    name = (r.get("meta") or {}).get("name")
    L = []
    title = f"## {r['symbol']}" + (f" — {name}" if name and name != r["symbol"] and not str(name).endswith((".JK", "USDT")) else "")
    L.append(title)
    L.append(f"{mname} · timeframe {r['tf']} · data terakhir {r['last_time']} · {r['bars']} bar")
    L.append("")
    L.append(f"**Harga:** {fp(r['price'])} ({ind['change_pct']:+.2f}%)  ")
    L.append(f"**Skor teknikal:** {r['score']:+d}/100 → **{r['label_id']}**  ")
    L.append(f"**Tren:** {r['trend']['label']} · struktur {r['trend']['structure']}")
    if r.get("mtf"):
        L.append("")
        L.append("**Multi-timeframe:** " + " · ".join(f"{s['tf']}: {s['trend']} ({s['score']:+d})" for s in r["mtf"]["summary"]))
        L.append(f"_{r['mtf']['confluence']}_")
    L.append("")
    L.append("### Level penting")
    L.append("| Resistance | Support |")
    L.append("|---|---|")
    for i in range(max(len(r["resistance"]), len(r["support"]), 1)):
        rr = r["resistance"][i] if i < len(r["resistance"]) else None
        ss = r["support"][i] if i < len(r["support"]) else None
        rtxt = "{} ({}x)".format(fp(rr["price"]), rr["touches"]) if rr else "-"
        stxt = "{} ({}x)".format(fp(ss["price"]), ss["touches"]) if ss else "-"
        L.append(f"| {rtxt} | {stxt} |")
    for tl in r["trendlines"]:
        L.append(f"- Trendline {tl['kind']}: sekarang di {fp(tl['value_now'])}" + (" — **sudah ditembus**" if tl["broken"] else f" ({tl['touches']} sentuhan)"))
    L.append("")
    L.append("### Indikator")
    def f1(x, d=1):
        return "-" if x is None else f"{x:.{d}f}"
    L.append(f"- MA20 {fp(ind['sma20'])} · MA50 {fp(ind['sma50'])} · MA200 {fp(ind['sma200'])}")
    L.append(f"- RSI14 {f1(ind['rsi14'])} · Stoch {f1(ind['stoch_k'])}/{f1(ind['stoch_d'])} · ADX {f1(ind['adx14'])}")
    L.append(f"- MACD {f1(ind['macd'], 3 if mk != 'idx' else 1)} / signal {f1(ind['macd_signal'], 3 if mk != 'idx' else 1)}")
    L.append(f"- Bollinger {fp(ind['bb_lower'])} – {fp(ind['bb_upper'])} · ATR {fp(ind['atr14'])} ({ind['atr_pct']:.1f}%)")
    if ind.get("volume_ratio"):
        L.append(f"- Volume {ind['volume_ratio']:.2f}x rata-rata 20 bar")
    L.append(f"- Range 52 minggu: {fp(ind['low_52w'])} – {fp(ind['high_52w'])}")
    if r["chart_patterns"] or r["candles_recent"] or r["divergences"]:
        L.append("")
        L.append("### Pola terdeteksi")
        for p in r["chart_patterns"]:
            extra = teks_target(p, fp).replace(", ", " · ", 1)
            if p.get("neckline"):
                extra = f" · neckline {fp(p['neckline'])}" + extra
            L.append(f"- **{p['name_id']}** — {p['status']}{extra}")
        for d in r["divergences"]:
            L.append(f"- **{d['name_id']}**")
        for x in r["candles_recent"]:
            L.append(f"- Candle: {x['name_id']}")
    L.append("")
    L.append("### Sinyal (kontribusi dalam poin skor)")
    total = sum(s["score"] for s in r["signals"])
    ke = (r["score"] / total) if abs(total) >= 0.05 else 0.0  # poin mentah -> poin skor (jumlahnya = skor)
    for s in sorted(r["signals"], key=lambda s: -abs(s["score"])):
        mark = "🟢" if s["score"] > 0 else "🔴" if s["score"] < 0 else "⚪"
        L.append(f"- {mark} {s['cat']}: {s['text']}" + (f" ({s['score'] * ke:+.0f})" if s["score"] else ""))
    p = r["plan"]
    L.append("")
    L.append(f"### Rencana: {p['bias_id']}")
    if p["bias"] == "long":
        L.append(f"- Area beli: {fp(p['entry_zone'][0])} – {fp(p['entry_zone'][1])}")
        L.append(f"- Stop (close di bawah): {fp(p['stop_loss'])} (risiko {p['risk_pct']}%)")
        L.append("- Target: " + ", ".join(f"{fp(x)} (R:R {rr})" for x, rr in zip(p["targets"], p["rr"])))
    elif p["bias"] == "short":
        if p.get("targets"):
            L.append("- Target turun: " + ", ".join(fp(x) for x in p["targets"]))
        L.append(f"- Konfirmasi naik (close di atas): {fp(p['stop_loss'])}")
    else:
        L.append(f"- Range: {fp(p['range'][0])} – {fp(p['range'][1])}")
        L.append(f"- Pemicu naik: close > {fp(p['buy_trigger'])} · pemicu turun: close < {fp(p['sell_trigger'])}")
    L.append(f"- {p['note']}")
    L.append("")
    L.append("_Analisa teknikal otomatis, bukan rekomendasi investasi. Selalu cek berita, fundamental, dan manajemen risiko sendiri._")
    return "\n".join(L)


# =============================================================================
# 10. Chart PNG (matplotlib)
# =============================================================================


def plot_chart(bars, r, path, last_n=160, catatan=None):
    """Chart PNG beranotasi. catatan (opsional) = {"simbol", "narasi": {"inti", "paragraf"}, "dekat", "rs", "aksi", "waktu"}:
    bila diisi, kolom kanan berisi skor, level, rencana, dan analisa tertulis sehingga gambar lengkap saat dibagikan."""
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    from matplotlib.patches import Rectangle

    full = analyze(bars, symbol=r["symbol"], market=r["market"], tf=r["tf"], include_series=True) if "series" not in r else r
    S = full["series"]
    n = len(S["c"])
    s0 = max(0, n - last_n)
    X = np.arange(s0, n)
    sl = slice(s0, n)
    arr = lambda k: np.array([np.nan if v is None else v for v in S[k]], float)  # noqa: E731
    o, h, l, c, v = (arr(k) for k in "ohlcv")
    mk = r["market"]

    # Palet sama dengan panel (web/panel.css): latar slate gelap, warna arah standar TradingView
    bg, fg, grid = "#0b0b0c", "#bcbcc2", "#1b1b1e"
    up, dn = "#26a69a", "#ef5350"
    lebar = catatan is not None
    fig = plt.figure(figsize=(19, 9.6) if lebar else (14, 9), facecolor=bg)
    if lebar:
        luar = fig.add_gridspec(1, 2, width_ratios=[3.3, 1.3], wspace=0.09, left=0.015, right=0.985, top=0.95, bottom=0.05)
        gs = luar[0].subgridspec(4, 1, height_ratios=[5, 1.1, 1.3, 1.3], hspace=0.05)
        axt = fig.add_subplot(luar[1])
        axt.axis("off")
    else:
        gs = fig.add_gridspec(4, 1, height_ratios=[5, 1.1, 1.3, 1.3], hspace=0.05)
    ax = fig.add_subplot(gs[0])
    axv = fig.add_subplot(gs[1], sharex=ax)
    axr = fig.add_subplot(gs[2], sharex=ax)
    axm = fig.add_subplot(gs[3], sharex=ax)
    for a_ in (ax, axv, axr, axm):
        a_.set_facecolor(bg)
        a_.tick_params(colors=fg, labelsize=9)
        a_.grid(color=grid, linewidth=0.6)
        for sp in a_.spines.values():
            sp.set_color(grid)
        a_.yaxis.tick_right()

    w = 0.6
    from matplotlib.collections import PolyCollection

    def kotak(sumbu, y0, y1, muka, tepi, lw=0.0, z=3, alpha=None):
        # Semua kotak dalam satu koleksi: jauh lebih cepat daripada satu patch per candle.
        verts = [((x - w / 2, a), (x - w / 2, b), (x + w / 2, b), (x + w / 2, a)) for x, a, b in zip(X, y0, y1)]
        sumbu.add_collection(PolyCollection(verts, facecolors=muka, edgecolors=tepi, linewidths=lw, zorder=z, alpha=alpha), autolim=False)

    naik = c[sl] >= o[sl]  # candle naik dan turun terisi penuh (sama dengan panel)
    warna = np.where(naik, up, dn)
    ax.vlines(X, l[sl], h[sl], colors=warna, linewidth=0.8, zorder=2)
    badan_lo = np.minimum(o[sl], c[sl])
    badan_hi = np.maximum(np.maximum(o[sl], c[sl]), badan_lo + 1e-9)
    kotak(ax, badan_lo, badan_hi, warna, warna, lw=0.8)  # badan menutupi sumbu di dalamnya
    vv = np.nan_to_num(v[sl])
    kotak(axv, np.zeros_like(vv), vv, warna, "none", alpha=0.45)
    axv.set_ylim(0, (vv.max() or 1) * 1.08)
    for k, col, lw in (("sma20", "#e0a64b", 1.0), ("sma50", "#6ea8fe", 1.3), ("sma200", "#b48ef0", 1.4)):
        ax.plot(X, arr(k)[sl], color=col, linewidth=lw, label=k.upper().replace("SMA", "MA"))
    ax.fill_between(X, arr("bb_upper")[sl], arr("bb_lower")[sl], color="#8e8e96", alpha=0.08, label="Bollinger")

    for s in r["support"][:3]:
        ax.axhline(s["price"], color=up, linestyle="--", linewidth=0.9, alpha=0.8)
        ax.text(s0 + 1, s["price"], f" S {fmt_price(s['price'], mk)}", color=up, fontsize=8, va="bottom", bbox=dict(boxstyle="square,pad=0.15", facecolor=bg, edgecolor="none", alpha=0.85), zorder=6)
    for s in r["resistance"][:3]:
        ax.axhline(s["price"], color=dn, linestyle="--", linewidth=0.9, alpha=0.8)
        ax.text(s0 + 1, s["price"], f" R {fmt_price(s['price'], mk)}", color=dn, fontsize=8, va="bottom", bbox=dict(boxstyle="square,pad=0.15", facecolor=bg, edgecolor="none", alpha=0.85), zorder=6)
    for tl in r["trendlines"]:
        x1 = max(tl["i1"], s0)
        y1 = _line_at((tl["i1"], tl["p1"]), (tl["i2"], tl["p2"]), x1)
        x2 = min(n - 1, tl["break_idx"] + 3) if tl.get("break_idx") is not None else n - 1
        y2 = _line_at((tl["i1"], tl["p1"]), (tl["i2"], tl["p2"]), x2)
        ax.plot([x1, x2], [y1, y2], color="#6ea8fe", linewidth=1.1, alpha=0.9, linestyle=":" if tl["broken"] else "-")
    for p in r["chart_patterns"]:
        col = up if p["bias"] > 0 else dn if p["bias"] < 0 else "#f2f2f3"
        if p.get("points"):
            pts = [q for q in p["points"] if q[0] >= s0]
            if pts:
                ax.plot([q[0] for q in pts], [q[1] for q in pts], color=col, linewidth=1.6, marker="o", markersize=4)
        for key in ("upper", "lower"):
            if p.get(key):
                (xa, ya), (xb, yb) = p[key]
                ax.plot([max(xa, s0), xb], [_line_at((xa, ya), (xb, yb), max(xa, s0)), yb], color=col, linewidth=1.4, linestyle="-.")
        if p.get("neckline_pts"):
            (xa, ya), (xb, yb) = p["neckline_pts"]
            ax.plot([max(xa, s0), n - 1], [_line_at((xa, ya), (xb, yb), max(xa, s0)), _line_at((xa, ya), (xb, yb), n - 1)], color=col, linestyle=":", linewidth=1.3)
        elif p.get("neckline") and p.get("points"):
            ax.hlines(p["neckline"], max(p["start_idx"], s0), n - 1, color=col, linestyle=":", linewidth=1.3)
        if p.get("box"):
            x0, y0, x1b, y1b = p["box"]
            ax.add_patch(Rectangle((x0, y0), x1b - x0, y1b - y0, fill=False, edgecolor=col, linewidth=1.2))
        if p.get("pole"):
            (xa, ya), (xb, yb) = p["pole"]
            ax.plot([xa, xb], [ya, yb], color=col, linewidth=2)
        if p.get("target") and not p.get("target_hit"):
            ax.axhline(p["target"], color=col, linewidth=0.7, alpha=0.5)
        lx = max(p["start_idx"], s0)
        ax.annotate(p["name"], (lx, h[lx:n].max() if p["bias"] < 0 else l[lx:n].min()), color=col, fontsize=9, fontweight="bold",
                    xytext=(0, 6 if p["bias"] < 0 else -14), textcoords="offset points")
    for x in S.get("candles_panah", S["candles_all"]):
        if x["i"] >= n - 20 and x["bias"] != 0 and x["strength"] >= 2:
            i = x["i"]
            y = l[i] - 0.4 * (h[i] - l[i]) if x["bias"] > 0 else h[i] + 0.4 * (h[i] - l[i])
            ax.annotate("▲" if x["bias"] > 0 else "▼", (i, y), color=up if x["bias"] > 0 else dn, ha="center", fontsize=9)
    # Legenda di atas bidang chart (dulu di pojok kiri atas, menimpa label "R …" dan namanya sendiri).
    ax.legend(loc="lower left" if lebar else "lower right", bbox_to_anchor=(0.0 if lebar else 1.0, 1.0), ncol=4, fontsize=8, frameon=False,
              labelcolor=fg, borderaxespad=0.2, handlelength=1.6, columnspacing=1.4)
    if not lebar:  # versi lebar menampilkan judul & skor di kolom kanan
        ax.set_title(f"{r['symbol']} · {r['tf']} · {fmt_price(r['price'], mk)} · skor {r['score']:+d} ({r['label_id']}) · {r['trend']['label']}",
                     color=fg, fontsize=11, loc="left")
    lo_, hi_ = np.nanmin(l[sl]), np.nanmax(h[sl])
    ax.set_ylim(lo_ - (hi_ - lo_) * 0.06, hi_ + (hi_ - lo_) * 0.06)

    rr_ = arr("rsi")
    axr.plot(X, rr_[sl], color="#b48ef0", linewidth=1)
    for y in (30, 70):
        axr.axhline(y, color="#55555e", linestyle="--", linewidth=0.7)
    axr.set_ylim(0, 100)
    axr.set_ylabel("RSI", color=fg, fontsize=8)
    mh = np.nan_to_num(arr("macd_hist")[sl])
    kotak(axm, np.minimum(mh, 0), np.maximum(mh, 0), np.where(mh >= 0, up, dn), "none", alpha=0.6)
    axm.plot(X, arr("macd")[sl], color="#6ea8fe", linewidth=1)
    axm.plot(X, arr("macd_signal")[sl], color="#e0a64b", linewidth=1)
    axm.set_ylabel("MACD", color=fg, fontsize=8)
    axv.set_ylabel("Vol", color=fg, fontsize=8)
    from matplotlib.ticker import FuncFormatter
    axv.yaxis.set_major_formatter(FuncFormatter(lambda x, _: f"{x/1e9:.1f}B" if x >= 1e9 else f"{x/1e6:.0f}M" if x >= 1e6 else f"{x/1e3:.0f}K" if x >= 1e3 else f"{x:.0f}"))
    axv.yaxis.get_offset_text().set_visible(False)
    t = np.array(S["t"])
    ticks = np.linspace(s0, n - 1, 8).astype(int)
    fmt = "%d %b %y" if r["tf"] in ("1d", "1wk", "1mo") else "%d %b %H:%M"
    axm.set_xticks(ticks)
    axm.set_xticklabels([datetime.fromtimestamp(t[i] + (7 * 3600 if mk == "idx" else 0), timezone.utc).strftime(fmt) for i in ticks])
    for a_ in (ax, axv, axr):
        plt.setp(a_.get_xticklabels(), visible=False)
    ax.set_xlim(s0 - 1, n + 2)
    if lebar:
        _panel_catatan(fig, axt, r, catatan, {"bg": bg, "fg": fg, "up": up, "dn": dn})
    else:
        fig.subplots_adjust(left=0.02, right=0.94, top=0.95, bottom=0.05)
    fig.savefig(path, dpi=110, facecolor=bg)
    plt.close(fig)
    return path


def _panel_catatan(fig, ax, r, cat, w):
    """Kolom teks di kanan chart PNG: skor, level, rencana, kekuatan relatif, dan analisa tertulis."""
    import textwrap
    mk = r["market"]
    fp = lambda x: fmt_price(x, mk)  # noqa: E731
    minus = "\u2212"

    def pct(x):
        s = f"{abs(x):.1f}".replace(".", ",")
        return (minus if x < 0 else "+") + s + "%"

    fg, up, dn = w["fg"], w["up"], w["dn"]
    teks2, teks3, netral = "#f2f2f3", "#8e8e96", "#e0a64b"
    # "$" berpasangan dibaca matplotlib sebagai rumus; teks dibungkus dulu, lalu "$" di-escape saat digambar
    t_asli = ax.text

    def _text(x, y, teks, **kw):
        return t_asli(x, y, str(teks).replace("$", r"\$"), **kw)

    ax.text = _text
    kotak = ax.get_window_extent().transformed(fig.dpi_scale_trans.inverted())
    tinggi, lebar_pt = kotak.height * 72, kotak.width * 72
    pos = [0.0]

    def tulis(teks, ukuran=9.5, warna=fg, tebal=False, spasi=1.45, x=0.0, bungkus=True, sesudah=0.0):
        maks = max(10, int((lebar_pt * (1 - x)) / (0.53 * ukuran)))
        for baris in (textwrap.wrap(teks, maks) if bungkus else [teks]):
            if pos[0] + ukuran * spasi > tinggi - 22:
                return False
            ax.text(x, 1 - pos[0] / tinggi, baris, transform=ax.transAxes, va="top", ha="left", fontsize=ukuran,
                    color=warna, fontweight="bold" if tebal else "normal")
            pos[0] += ukuran * spasi
        pos[0] += sesudah
        return True

    skor = int(r["score"])
    warna_skor = up if skor >= 20 else dn if skor <= -20 else netral
    tf = {"1d": "harian", "1wk": "mingguan", "1mo": "bulanan"}.get(r.get("tf"), r.get("tf"))
    tulis(f"{cat.get('simbol') or r['symbol']} · {tf} · {fp(r['price'])}", 13, teks2, True, sesudah=4)
    awal = pos[0]
    tulis((minus if skor < 0 else "+" if skor > 0 else "") + str(abs(skor)), 26, warna_skor, True, spasi=1.1)
    ax.text(0.30, 1 - (awal + 4) / tinggi, r["label_id"], transform=ax.transAxes, va="top", fontsize=12.5, color=warna_skor, fontweight="bold")
    ax.text(0.30, 1 - (awal + 21) / tinggi, r["trend"]["label"], transform=ax.transAxes, va="top", fontsize=10, color=fg)
    pos[0] += 6
    nar = cat.get("narasi") or {}
    if nar.get("inti"):
        tulis(nar["inti"], 10, fg, sesudah=6)

    tulis("Level", 10.5, teks2, True, sesudah=1)
    baris = [(f"R{i + 1}", x["price"], dn) for i, x in enumerate(r["resistance"][:2])][::-1]
    baris += [("Harga", r["price"], teks2)] + [(f"S{i + 1}", x["price"], up) for i, x in enumerate(r["support"][:2])]
    for k, harga, warna in baris:
        y = 1 - pos[0] / tinggi
        ax.text(0.0, y, k, transform=ax.transAxes, va="top", fontsize=9.5, color=warna, fontweight="bold")
        ax.text(0.16, y, fp(harga), transform=ax.transAxes, va="top", fontsize=9.5, color=teks2)
        if k != "Harga":
            ax.text(0.62, y, pct((harga / r["price"] - 1) * 100), transform=ax.transAxes, va="top", fontsize=9.5, color=teks3)
        pos[0] += 9.5 * 1.45
    pos[0] += 6

    p = r["plan"]
    judul = {"long": "Beli saat koreksi", "short": "Belum saatnya beli", "wait": "Tunggu konfirmasi"}[p["bias"]]
    aksi = cat.get("aksi") or {}
    if aksi.get("langkah"):
        # Rencana tindakan "jika … maka …" (sama dengan tab Ringkasan), supaya gambar tetap lengkap bila dibagikan.
        tulis("Rencana tindakan", 10.5, teks2, True, sesudah=1)
        tulis(aksi.get("judul", ""), 9.5, fg, sesudah=2)
        for x in aksi["langkah"][:3]:
            kond = x["kondisi"][:1].lower() + x["kondisi"][1:]
            tulis(f"• Jika {kond}: " + x["tindakan"].split(". ")[0].rstrip(".") + ".", 9.0, fg, spasi=1.4)
    elif p["bias"] == "long":
        tulis(f"Rencana · {judul}", 10.5, teks2, True, sesudah=1)
        tulis(f"Area beli {fp(p['entry_zone'][0])}–{fp(p['entry_zone'][1])}; stop bila close < {fp(p['stop_loss'])}", 9.5)
        if p.get("targets"):
            tulis("Target " + ", ".join(fp(x) for x in p["targets"][:2]), 9.5)
    elif p["bias"] == "short":
        tulis(f"Rencana · {judul}", 10.5, teks2, True, sesudah=1)
        if p.get("targets"):
            tulis("Target turun " + ", ".join(fp(x) for x in p["targets"][:2]), 9.5)
        tulis(f"Konfirmasi naik bila close > {fp(p['stop_loss'])}", 9.5)
    else:
        tulis(f"Rencana · {judul}", 10.5, teks2, True, sesudah=1)
        tulis(f"Menguat bila close > {fp(p['buy_trigger'])}; melemah bila close < {fp(p['sell_trigger'])}", 9.5)
    pos[0] += 6

    rs = cat.get("rs")
    if rs and rs.get("rs20") is not None:
        sebut = "lebih kuat" if rs["rs20"] >= 2 else "lebih lemah" if rs["rs20"] <= -2 else "sejalan"
        tulis(f"vs {rs['acuan']} 20 {rs.get('satuan') or 'hari'}: {pct(rs['rs20'])} ({sebut})", 9.5, fg, sesudah=6)

    if nar.get("paragraf"):
        tulis("Analisa", 10.5, teks2, True, sesudah=1)
        for par in nar["paragraf"]:
            if not tulis(par, 9.2, fg, spasi=1.42, sesudah=5):
                ax.text(0.0, 1 - (tinggi - 30) / tinggi, "…", transform=ax.transAxes, va="top", fontsize=9.5, color=teks3)
                break
    ax.text(0.0, 0.0, f"Analisa Teknikal · {cat.get('waktu', '')} · bukan rekomendasi investasi", transform=ax.transAxes,
            va="bottom", fontsize=7.5, color=teks3)


# =============================================================================
# 11. CLI
# =============================================================================


def _wawasan():
    """Modul wawasan.py (narasi, kekuatan relatif, candle berjalan) bila ada di folder yang sama. Opsional."""
    sys.modules.setdefault("ta_engine", sys.modules[__name__])  # supaya wawasan memakai modul ini, bukan salinan kedua
    try:
        import wawasan
    except ImportError:
        return None
    return wawasan


def _tulisan(ws, res, bars, kode, market, args, berjalan):
    """Analisa tertulis + data kolom catatan chart. Kekuatan relatif butuh data pembanding online (dilewati untuk CSV)."""
    dekat = ws.dekat_level(res)
    rs = None
    ac = None if (args.csv or args.no_rs) else ws.acuan_untuk(kode, market)
    if ac:
        try:
            ba, _ = load(ac[0], None, args.tf)
            rs = ws.kekuatan_relatif(bars, ba, ac[1], harian=args.tf in ws.TF_HARIAN, tf=args.tf)
        except Exception:  # noqa: BLE001  (pembanding hanya pelengkap)
            rs = None
    try:
        titik = ws.riwayat_skor(kode, bars, market, args.tf, 30, berjalan=berjalan is not None, persisten=False)
        kalimat = ws.kalimat_riwayat(titik, int(res["score"]), ws.SATUAN_TF.get(args.tf, "bar"))
    except Exception:  # noqa: BLE001
        titik, kalimat = [], ""
    simbol = res.get("symbol") or kode
    narasi = ws.narasi(res, simbol, None, rs, dekat, None, berjalan, kalimat)
    aksi = ws.rencana_aksi(res, dekat) if hasattr(ws, "rencana_aksi") else {}
    res.update({"narasi": narasi, "rs": rs, "dekat": dekat, "riwayat_skor": [[int(t), int(x)] for t, x in titik], "rencana_aksi": aksi})
    return {"simbol": simbol, "narasi": narasi, "dekat": dekat, "rs": rs, "aksi": aksi,
            "waktu": datetime.now().astimezone().strftime("%d %b %Y %H:%M %Z").strip()}


def main(argv=None):
    import argparse
    import os
    ap = argparse.ArgumentParser(description="Analisa teknikal saham IDX / US / kripto")
    ap.add_argument("symbol", nargs="?", help="mis. BBCA, IDX:TLKM, US:NVDA, BTC, SOLUSDT")
    ap.add_argument("--symbol", dest="symbol_opt", help="nama simbol (untuk mode --csv)")
    ap.add_argument("--market", choices=["idx", "us", "crypto"], help="paksa pasar")
    ap.add_argument("--tf", default="1d", help="15m,30m,1h,4h,1d,1wk,1mo (default 1d)")
    ap.add_argument("--csv", help="pakai file CSV OHLCV, bukan data online")
    ap.add_argument("--out", default=".", help="folder output (json, md, png)")
    ap.add_argument("--no-mtf", action="store_true", help="matikan multi-timeframe")
    ap.add_argument("--no-chart", action="store_true")
    ap.add_argument("--json", action="store_true", help="cetak JSON, bukan markdown")
    ap.add_argument("--export-rows", type=int, default=300, help="jumlah bar terakhir untuk file *_dashboard.json (0 = tidak)")
    ap.add_argument("--polos", action="store_true", help="chart tanpa kolom catatan analisa di kanan")
    ap.add_argument("--no-rs", action="store_true", help="lewati perbandingan dengan IHSG / S&P 500 / BTC")
    args = ap.parse_args(argv)
    args.symbol = args.symbol or args.symbol_opt
    if not args.symbol and not args.csv:
        ap.error("isi symbol atau --csv")
    meta = {}
    if args.csv:
        with open(args.csv, encoding="utf-8-sig", errors="replace") as f:
            bars = parse_csv(f.read())
        sym = (args.symbol or os.path.splitext(os.path.basename(args.csv))[0]).upper()
        market = args.market or resolve(sym)[0][0]
        meta = {"provider": "CSV", "code": os.path.basename(args.csv)}
    else:
        bars, meta = load(args.symbol, args.market, args.tf)
        sym, market = meta["symbol"], meta["market"]
    ws = _wawasan()
    kode = meta.get("code") or sym
    berjalan = ws.fraksi_berjalan(kode, market, float(bars["t"][-1]), args.tf) if ws else None
    if args.no_mtf:
        res = analyze(bars, symbol=sym, market=market, tf=args.tf, meta=meta, live_frac=berjalan)
    else:
        res = analyze_mtf(auto_mtf(bars, args.tf, market), symbol=sym, market=market, primary=args.tf, live_frac=berjalan)
        res["meta"] = meta
    catatan = _tulisan(ws, res, bars, kode, market, args, berjalan) if ws else None
    os.makedirs(args.out, exist_ok=True)
    base = os.path.join(args.out, f"{sym}_{args.tf}")
    with open(base + ".json", "w") as f:
        json.dump(res, f, indent=1, ensure_ascii=False)
    md = to_markdown(res)
    if catatan:
        aksi = res.get("rencana_aksi") or {}
        if aksi.get("langkah"):
            md += "\n## Rencana tindakan\n\n**" + aksi["judul"] + "**\n\n" + "\n".join(
                f"- Jika {x['kondisi'][0].lower() + x['kondisi'][1:]}: {x['tindakan']}" for x in aksi["langkah"]) + "\n"
        md += "\n## Analisa\n\n" + "\n\n".join(catatan["narasi"]["paragraf"]) + "\n"
    with open(base + ".md", "w") as f:
        f.write(md)
    if args.export_rows:
        k = min(args.export_rows, len(bars["c"]))
        dec = 0 if market == "idx" else 2 if market == "us" else 8
        rows = [[int(bars["t"][i]), round(float(bars["o"][i]), dec), round(float(bars["h"][i]), dec), round(float(bars["l"][i]), dec),
                 round(float(bars["c"][i]), dec), int(bars["v"][i])] for i in range(len(bars["c"]) - k, len(bars["c"]))]
        doc = {"symbol": sym, "market": market, "tf": args.tf, "name": meta.get("name") or sym, "source": meta.get("provider", ""),
               "updatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "rows": rows}
        with open(base + "_dashboard.json", "w") as f:
            json.dump({"path": f"assets/{re.sub(r'[^A-Za-z0-9_.-]', '', sym)}_{args.tf}", "data": doc}, f, separators=(",", ":"))
    if not args.no_chart:
        try:
            plot_chart(bars, res, base + ".png", catatan=None if args.polos else catatan)
            res["chart_path"] = base + ".png"
        except ImportError:
            pass
    print(json.dumps(res, ensure_ascii=False) if args.json else md)
    if not args.json:
        print(f"\n[file] {base}.json  {base}.md" + (f"  {base}.png" if res.get("chart_path") else ""), file=sys.stderr)
    return res


if __name__ == "__main__":
    main()
