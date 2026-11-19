#!/usr/bin/env python3
"""
Pembaruan otomatis Analisa Teknikal dari GitHub.

Dipanggil oleh peluncur (Analisa Teknikal.app / Analisa Teknikal (Windows).bat) setiap kali dibuka,
sebelum panel dinyalakan. Tidak ada pemeriksaan terjadwal dan tidak ada notifikasi.

    python3 perbarui.py            # periksa, unduh bila ada versi baru, lalu pasang
    python3 perbarui.py --cek      # hanya periksa, tidak memasang

Cara kerja:
1. Baca rilis.json  -> {"repo": "pemilik/nama-repo", "cabang": "main", "token": ""}.
   repo kosong = pembaruan otomatis mati.
2. Bandingkan "id" di VERSI.json lokal dengan VERSI.json di GitHub (berkas kecil).
3. Bila berbeda: unduh zip cabang itu, periksa isinya, simpan berkas lama yang tertimpa ke _lama/,
   lalu tulis berkas baru satu per satu (atomik).
Tidak pernah disentuh: pengaturan.json (daftar pantau, bahasa), cache/, output/, _lama/.
Folder sumber (yang memuat buat_paket.py, yaitu komputer pemilik) tidak pernah diperbarui dari GitHub.
Gagal (tanpa internet, GitHub tidak terjangkau) = diam saja, program jalan dengan versi yang ada.
"""
from __future__ import annotations

import io
import json
import os
import shutil
import stat
import sys
import time
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath

sys.dont_write_bytecode = True
FOLDER = Path(__file__).resolve().parent
JANGAN = {"pengaturan.json", "cache", "output", "_lama", "backup", "_to_delete", "paket", ".git"}
WAJIB = ("panel.py", "ta_engine.py", "wawasan.py", "teknikal.py", "VERSI.json", "ekstensi/manifest.json")
LOG = FOLDER / "output" / "perbarui.log"


def catat(teks: str) -> None:
    baris = f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {teks}"
    print(baris)
    try:
        LOG.parent.mkdir(exist_ok=True)
        with LOG.open("a", encoding="utf-8") as f:
            f.write(baris + "\n")
    except OSError:
        pass


def baca_json(p: Path) -> dict:
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def ambil(url: str, token: str, batas: float) -> bytes:
    kepala = {"User-Agent": "AnalisaTeknikal-perbarui", "Cache-Control": "no-cache"}
    if token:
        kepala["Authorization"] = f"token {token}"
    req = urllib.request.Request(url, headers=kepala)
    try:  # Python dari python.org di Mac sering belum punya sertifikat sistem; certifi ikut terpasang bersama yfinance
        import certifi
        import ssl
        konteks = ssl.create_default_context(cafile=certifi.where())
    except Exception:  # noqa: BLE001
        konteks = None
    with urllib.request.urlopen(req, timeout=batas, context=konteks) as r:
        return r.read()


def url_versi(repo: str, cabang: str, token: str) -> str:
    if token:  # repo privat: lewat API (raw.githubusercontent butuh token juga, tapi API lebih andal)
        return f"https://api.github.com/repos/{repo}/contents/VERSI.json?ref={cabang}"
    return f"https://raw.githubusercontent.com/{repo}/{cabang}/VERSI.json?t={int(time.time())}"


def versi_jauh(repo: str, cabang: str, token: str) -> dict:
    data = ambil(url_versi(repo, cabang, token), token, 8)
    obj = json.loads(data)
    if token and "content" in obj:  # jawaban API: isi berkas dalam base64
        import base64
        obj = json.loads(base64.b64decode(obj["content"]))
    return obj


def url_zip(repo: str, cabang: str, token: str) -> str:
    if token:
        return f"https://api.github.com/repos/{repo}/zipball/{cabang}"
    return f"https://codeload.github.com/{repo}/zip/refs/heads/{cabang}"


def aman(rel: str) -> bool:
    p = PurePosixPath(rel)
    return bool(rel) and not p.is_absolute() and ".." not in p.parts and p.parts[0] not in JANGAN


def pasang(data: bytes, id_baru: str) -> int:
    z = zipfile.ZipFile(io.BytesIO(data))
    isi: dict[str, zipfile.ZipInfo] = {}
    for info in z.infolist():
        if info.is_dir():
            continue
        bagian = info.filename.split("/", 1)  # zip GitHub: semua berkas di bawah satu folder akar
        if len(bagian) == 2 and aman(bagian[1]):
            isi[bagian[1]] = info
    kurang = [w for w in WAJIB if w not in isi]
    if kurang:
        raise RuntimeError(f"isi unduhan tidak lengkap: {kurang}")
    if json.loads(z.read(isi["VERSI.json"])).get("id") != id_baru:
        raise RuntimeError("VERSI.json di zip tidak sama dengan yang diumumkan (coba lagi nanti)")

    lama = FOLDER / "_lama"
    if lama.exists():
        shutil.rmtree(lama, ignore_errors=True)
    lama.mkdir(exist_ok=True)

    berubah = 0
    for rel, info in sorted(isi.items()):
        baru = z.read(info)
        tujuan = FOLDER / rel
        if tujuan.exists():
            if tujuan.read_bytes() == baru:
                continue
            cadang = lama / rel
            cadang.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(tujuan, cadang)
        tujuan.parent.mkdir(parents=True, exist_ok=True)
        sementara = tujuan.with_name(tujuan.name + ".baru")
        sementara.write_bytes(baru)
        mode = (info.external_attr >> 16) & 0o777
        if mode & 0o111 or rel.endswith("Contents/MacOS/buka"):
            sementara.chmod(sementara.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
        os.replace(sementara, tujuan)  # atomik: peluncur yang sedang berjalan tetap memegang berkas lama
        berubah += 1

    # Berkas program yang sudah tidak ada di versi baru dipindah ke _lama/ (bukan dihapus).
    sebelumnya = baca_json(lama / "VERSI.json").get("berkas") or []
    for rel in sebelumnya:
        if rel not in isi and aman(rel) and (FOLDER / rel).is_file():
            cadang = lama / rel
            cadang.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(FOLDER / rel), str(cadang))
            berubah += 1
    return berubah


def main() -> int:
    hanya_cek = "--cek" in sys.argv
    if (FOLDER / "buat_paket.py").exists() or (FOLDER / ".git").exists():
        print("Folder sumber: tidak diperbarui dari GitHub.")
        return 0
    cfg = baca_json(FOLDER / "rilis.json")
    repo = str(cfg.get("repo") or "").strip().strip("/")
    if not repo:
        print("Pembaruan otomatis mati (rilis.json -> repo kosong).")
        return 0
    cabang = str(cfg.get("cabang") or "main").strip()
    token = str(cfg.get("token") or "").strip()
    lokal = baca_json(FOLDER / "VERSI.json")
    try:
        jauh = versi_jauh(repo, cabang, token)
    except Exception as exc:  # noqa: BLE001 - tanpa internet dsb.: diam saja
        print(f"Tidak bisa memeriksa pembaruan ({exc}).")
        return 0
    id_baru = str(jauh.get("id") or "")
    if not id_baru or id_baru == lokal.get("id"):
        print(f"Sudah versi terbaru ({lokal.get('tanggal', '?')}).")
        return 0
    if hanya_cek:
        print(f"Ada versi baru: {jauh.get('tanggal', '?')} (terpasang: {lokal.get('tanggal', '?')}).")
        return 0
    try:
        data = ambil(url_zip(repo, cabang, token), token, 90)
        n = pasang(data, id_baru)
    except Exception as exc:  # noqa: BLE001
        catat(f"Pembaruan gagal, tetap memakai versi lama: {exc}")
        return 0
    catat(f"Diperbarui ke versi {jauh.get('tanggal', '?')} ({id_baru}), {n} berkas berubah.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
