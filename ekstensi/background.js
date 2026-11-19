// Analisa Teknikal — service worker: simpan deteksi per tab, beri badge skor, kirim kartu ke halaman, teruskan ke side panel.
const SERVER = "http://127.0.0.1:8768";
const status = {}; // tabId -> { q, iv, ivLabel, tf, situs, catatan, skor }

// Bahasa (id/en) ditentukan di panel dan disimpan di server; ekstensi mengetahuinya dari jawaban /api/analisa.
// Disimpan juga di chrome.storage supaya halaman "panel belum jalan" dan menu klik kanan ikut bahasanya.
let bahasa = "id";
const TEKS = {
  id: { menuKartu: "Tampilkan kartu analisa di halaman chart", menuGaris: "Tampilkan garis analisa di chart TradingView",
        off: "Analisa Teknikal — panel lokal belum jalan. Jalankan peluncur Analisa Teknikal di folder programnya.", gagal: "tidak bisa dianalisa", skor: "skor" },
  en: { menuKartu: "Show the analysis card on chart pages", menuGaris: "Show analysis lines on the TradingView chart",
        off: "Analisa Teknikal — the local panel is not running. Run the Analisa Teknikal launcher in its program folder.", gagal: "couldn't be analysed", skor: "score" },
};
const T = () => TEKS[bahasa] || TEKS.id;
const LABEL_TF = { "5m": "5m", "15m": "15m", "30m": "30m", "1h": "1H", "4h": "4H", "1d": "1D", "1wk": "1W", "1mo": "1M" };
chrome.storage.local.get({ bahasa: "id" }, (v) => { if (v.bahasa === "en" && bahasa !== "en") { bahasa = "en"; siapkanMenu(); } });
function catatBahasa(nilai) {
  if ((nilai !== "id" && nilai !== "en") || nilai === bahasa) return;
  bahasa = nilai;
  chrome.storage.local.set({ bahasa });
  siapkanMenu();
}

chrome.runtime.onInstalled.addListener(siapkan);
chrome.runtime.onStartup.addListener(siapkan);

// Pembaruan otomatis: peluncur mengambil versi terbaru dari GitHub ke folder program, termasuk folder ekstensi ini.
// Chrome tidak memuat ulang ekstensi "Load unpacked" sendiri, jadi bila versi di disk (dilaporkan panel) berbeda
// dari versi yang sedang berjalan, ekstensi memuat ulang dirinya. Paling sering sekali per 6 jam untuk versi yang
// sama, supaya tidak berulang terus bila ekstensi dimuat dari folder lain.
let cekVersiTerakhir = 0;
async function cekVersiEkstensi() {
  if (Date.now() - cekVersiTerakhir < 10 * 60 * 1000) return;
  cekVersiTerakhir = Date.now();
  try {
    const st = await (await fetch(`${SERVER}/api/status`, { cache: "no-store" })).json();
    const diDisk = st && st.ekstensi;
    const berjalan = chrome.runtime.getManifest().version;
    if (!diDisk || diDisk === berjalan) return;
    const { muatUlang = {} } = await chrome.storage.local.get("muatUlang");
    if (muatUlang.versi === diDisk && Date.now() - (muatUlang.waktu || 0) < 6 * 3600 * 1000) return;
    await chrome.storage.local.set({ muatUlang: { versi: diDisk, waktu: Date.now() } });
    chrome.runtime.reload();
  } catch { /* panel belum jalan */ }
}
cekVersiEkstensi();

function siapkan() {
  if (chrome.sidePanel && chrome.sidePanel.setPanelBehavior) {
    chrome.sidePanel.setPanelBehavior({ openPanelOnActionClick: true }).catch(() => {});
  } else {
    chrome.action.setPopup({ popup: "sidepanel.html" });
  }
  siapkanMenu();
}

// Klik kanan ikon ekstensi: nyalakan / matikan kartu di halaman chart (berlaku untuk semua situs)
function siapkanMenu() {
  if (!chrome.contextMenus) return;
  chrome.contextMenus.removeAll(() => {
    chrome.storage.local.get({ kartuAktif: true }, ({ kartuAktif }) => {
      chrome.contextMenus.create({ id: "kartu", title: T().menuKartu, type: "checkbox", checked: kartuAktif !== false, contexts: ["action"] }, () => void chrome.runtime.lastError);
    });
    chrome.storage.local.get({ lapisanAktif: true }, ({ lapisanAktif }) => {
      chrome.contextMenus.create({ id: "lapisan", title: T().menuGaris, type: "checkbox", checked: lapisanAktif !== false, contexts: ["action"] }, () => void chrome.runtime.lastError);
    });
  });
}
if (chrome.contextMenus) {
  chrome.contextMenus.onClicked.addListener((info) => {
    if (info.menuItemId === "kartu") chrome.storage.local.set({ kartuAktif: !!info.checked });
    if (info.menuItemId === "lapisan") chrome.storage.local.set({ lapisanAktif: !!info.checked });
  });
}
chrome.storage.onChanged.addListener((ch, area) => {
  if (area !== "local" || !chrome.contextMenus) return;
  if (ch.kartuAktif) chrome.contextMenus.update("kartu", { checked: ch.kartuAktif.newValue !== false }, () => void chrome.runtime.lastError);
  if (ch.lapisanAktif) chrome.contextMenus.update("lapisan", { checked: ch.lapisanAktif.newValue !== false }, () => void chrome.runtime.lastError);
});

// Interval TradingView -> timeframe panel (sama dengan panel.py). null = situs tidak memberi timeframe.
function tfDari(iv) {
  if (!iv) return null;
  const raw = String(iv).trim(), s = raw.toUpperCase();
  if (s === "D" || s === "1D") return "1d";
  if (s === "W" || s === "1W") return "1wk";
  if (raw === "M" || raw === "1M") return "1mo";
  const m = raw.match(/^(\d+)\s*([A-Za-z]?)$/);
  if (!m) return "1d";
  const n = +m[1], u = m[2];
  if (/[sStT]/.test(u)) return "5m";
  if (u === "M") return "1mo";
  const menit = n * ({ "": 1, m: 1, h: 60, H: 60, d: 1440, D: 1440, w: 10080, W: 10080 }[u] || 1);
  if (menit >= 10080) return "1wk";
  if (menit >= 1440) return "1d";
  const pilihan = [[5, "5m"], [15, "15m"], [30, "30m"], [60, "1h"], [240, "4h"]];
  return pilihan.reduce((a, b) => (Math.abs(b[0] - menit) < Math.abs(a[0] - menit) ? b : a))[1];
}

const tandaSkor = (x) => (x > 0 ? "+" : x < 0 ? "−" : "") + Math.abs(x);
function kirimKartu(tabId, isi) {
  chrome.tabs.sendMessage(tabId, { type: "kartu", ...isi }).catch(() => {});
}

const timer = {};
async function badge(tabId) {
  const s = status[tabId];
  if (!s || !s.q) { chrome.action.setBadgeText({ tabId, text: "" }); kirimKartu(tabId, { q: "", data: null }); return; }
  const tf = s.tf || "1d", q = s.q, iv = s.iv || "";
  const basi = () => !status[tabId] || status[tabId].q !== q || (status[tabId].iv || "") !== iv;  // tab sudah pindah simbol/interval
  let d;
  try {
    const r = await fetch(`${SERVER}/api/analisa?q=${encodeURIComponent(q)}&tf=${encodeURIComponent(tf)}&ringkas=1`);
    d = await r.json();
    cekVersiEkstensi();
  } catch {
    chrome.action.setBadgeBackgroundColor({ tabId, color: "#3f3f46" });
    chrome.action.setBadgeText({ tabId, text: "off" });
    chrome.action.setTitle({ tabId, title: T().off });
    kirimKartu(tabId, { q, data: null, alasan: "off" });
    return;
  }
  if (basi()) return;
  if (!d || !d.ok) {
    chrome.action.setBadgeBackgroundColor({ tabId, color: "#3f3f46" });
    chrome.action.setBadgeText({ tabId, text: "?" });
    chrome.action.setTitle({ tabId, title: `Analisa Teknikal — ${q}: ${(d && d.pesan) || T().gagal}` });
    kirimKartu(tabId, { q, data: null, alasan: "galat" });
    return;
  }
  s.skor = d.skor;
  // Warna badge cukup gelap supaya teks putih tetap ≥ 4.5:1
  const warna = d.skor >= 20 ? "#1f7a71" : d.skor <= -20 ? "#c2403d" : "#946b1f";
  chrome.action.setBadgeBackgroundColor({ tabId, color: warna });
  chrome.action.setBadgeTextColor && chrome.action.setBadgeTextColor({ tabId, color: "#ffffff" });
  chrome.action.setBadgeText({ tabId, text: tandaSkor(d.skor) });
  catatBahasa(d.bahasa);
  chrome.action.setTitle({ tabId, title: `Analisa Teknikal — ${q} ${bahasa === "en" ? LABEL_TF[d.tf] || d.tf : s.ivLabel || (s.tf ? "" : "1D")}: ${d.label} (${T().skor} ${tandaSkor(d.skor)})` });
  // Kartu dan garis analisa (lapisan) hanya berisi hasil analisa harga; tidak ada data portofolio di sini.
  kirimKartu(tabId, { q, iv, data: d.kartu || null, lapisan: d.lapisan || null, catatan: s.catatan || "", tanpaTf: !s.tf });
}

function teruskan(tabId) {
  const s = status[tabId] || { q: "" };
  chrome.runtime.sendMessage({ type: "deteksi", tabId, ...s }).catch(() => {});
}

function bukaPanel(tab, q, tf) {
  // Harus dipanggil langsung (tanpa await sebelumnya) supaya masih dihitung sebagai klik pengguna.
  const cadangan = () => chrome.tabs.create({ url: `${SERVER}/?mandiri=1#q=${encodeURIComponent(q || "")}&tf=${encodeURIComponent(tf || "1d")}`, index: tab.index + 1 });
  if (!chrome.sidePanel || !chrome.sidePanel.open) return cadangan();
  try {
    chrome.sidePanel.open({ windowId: tab.windowId }).catch(cadangan);
  } catch { cadangan(); }
}

chrome.runtime.onMessage.addListener((m, sender, balas) => {
  if (!m) return;
  if (m.type === "tv" && sender.tab) {
    const tabId = sender.tab.id;
    status[tabId] = { q: m.q, iv: m.iv, ivLabel: m.ivLabel, tf: tfDari(m.iv), situs: m.situs || "TradingView", catatan: m.catatan || "" };
    teruskan(tabId);
    clearTimeout(timer[tabId]);
    timer[tabId] = setTimeout(() => badge(tabId), 120);  // jeda singkat: cukup untuk menyatukan perubahan simbol + interval yang datang beruntun
  } else if (m.type === "segarkan" && sender.tab) {
    clearTimeout(timer[sender.tab.id]);
    badge(sender.tab.id);
  } else if (m.type === "bahasa") {
    // Bahasa diganti di panel samping: segarkan badge, kartu, dan garis di semua tab chart yang sedang dipantau.
    catatBahasa(m.nilai);
    Object.keys(status).forEach((id) => { if (status[id] && status[id].q) badge(+id); });
  } else if (m.type === "buka-panel" && sender.tab) {
    bukaPanel(sender.tab, m.q, m.tf);
  } else if (m.type === "state") {
    chrome.tabs.query({ active: true, windowId: m.windowId }).then(([tab]) => {
      if (!tab) return balas({ q: "" });
      const s = status[tab.id];
      if (s) return balas({ tabId: tab.id, ...s });
      chrome.tabs.sendMessage(tab.id, { type: "minta" }).then((d) => {
        if (d && d.q) { status[tab.id] = { ...d, tf: tfDari(d.iv) }; balas({ tabId: tab.id, ...status[tab.id] }); }
        else balas({ q: "" });
      }).catch(() => balas({ q: "" }));
    });
    return true;
  }
});

chrome.tabs.onActivated.addListener(({ tabId }) => teruskan(tabId));
chrome.tabs.onRemoved.addListener((tabId) => { delete status[tabId]; clearTimeout(timer[tabId]); delete timer[tabId]; });
