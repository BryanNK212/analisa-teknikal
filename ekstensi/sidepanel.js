// Side panel: memuat panel lokal dalam iframe dan meneruskan deteksi chart (TradingView, Stockbit, Binance, dll.) ke dalamnya.
const SERVER = "http://127.0.0.1:8768";
const frame = document.getElementById("panel");
const off = document.getElementById("off");
let windowId = null, siap = false, terakhir = null;
if (!(chrome.sidePanel && chrome.sidePanel.setPanelBehavior)) document.body.classList.add("popup");

// Halaman "panel belum jalan" ikut bahasa terakhir yang dipilih di panel (disimpan oleh background.js).
let en = false;
const TEKS_OFF = {
  id: ["Panel lokal belum jalan", "Ekstensi ini mengambil analisa dari program Analisa Teknikal yang berjalan di komputer ini.",
       "Buka folder <code>Analisa Teknikal</code> (Finder di Mac, File Explorer di Windows).", "Klik dua kali <code>Analisa Teknikal.app</code> (Mac) atau <code>Analisa Teknikal (Windows).bat</code>.", "Kembali ke sini dan klik Coba lagi.", "Coba lagi"],
  en: ["The local panel is not running", "This extension gets its analysis from the Analisa Teknikal program running on this computer.",
       "Open the <code>Analisa Teknikal</code> folder (Finder on Mac, File Explorer on Windows).", "Double-click <code>Analisa Teknikal.app</code> (Mac) or <code>Analisa Teknikal (Windows).bat</code>.", "Come back here and click Try again.", "Try again"],
};
function terapkanBahasa(nilai) {
  en = nilai === "en";
  const x = TEKS_OFF[en ? "en" : "id"];
  off.querySelector("h1").textContent = x[0];
  off.querySelector("p").textContent = x[1];
  off.querySelectorAll("li").forEach((li, i) => { li.innerHTML = x[2 + i]; });
  document.getElementById("coba").textContent = x[5];
  document.documentElement.lang = en ? "en" : "id";
}
chrome.storage.local.get({ bahasa: "id" }, (v) => terapkanBahasa(v.bahasa));
chrome.storage.onChanged.addListener((ch, area) => { if (area === "local" && ch.bahasa) terapkanBahasa(ch.bahasa.newValue); });

async function cekServer() {
  try {
    const r = await fetch(`${SERVER}/api/status`, { cache: "no-store" });
    if (!r.ok) throw new Error();
    off.hidden = true;
    if (!frame.src) frame.src = `${SERVER}/?embed=1`;
    frame.hidden = false;
  } catch {
    off.hidden = false; frame.hidden = true; frame.removeAttribute("src"); siap = false;
    const info = document.getElementById("cekInfo");
    if (info) info.textContent = en
      ? "Checked " + new Date().toLocaleTimeString("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) + " — not connected yet. Rechecked automatically every 5 seconds."
      : "Dicek " + new Date().toLocaleTimeString("id-ID", { hour: "2-digit", minute: "2-digit", second: "2-digit" }) + " — belum terhubung. Dicek ulang otomatis tiap 5 detik.";
  }
}

function kirim(d) {
  terakhir = d;
  if (!siap || !frame.contentWindow) return;
  // tf null = situs tidak memberi timeframe (Stockbit, Binance, dll.): panel memakai timeframe yang sedang dipilih
  frame.contentWindow.postMessage({ type: "deteksi", q: d.q || "", tf: d.tf || null, iv: d.iv || "", ivLabel: d.ivLabel || "", situs: d.situs || "" }, SERVER);
}

async function mintaState() {
  if (windowId == null) windowId = (await chrome.windows.getCurrent()).id;
  const d = await chrome.runtime.sendMessage({ type: "state", windowId }).catch(() => null);
  if (d) kirim(d);
}

chrome.runtime.onMessage.addListener(async (m) => {
  if (!m || m.type !== "deteksi") return;
  const [tab] = await chrome.tabs.query({ active: true, windowId: windowId ?? undefined, lastFocusedWindow: windowId == null });
  if (tab && tab.id === m.tabId) kirim(m);
});

window.addEventListener("message", (e) => {
  if (e.origin !== SERVER) return;
  if (e.data && e.data.type === "siap") { siap = true; terakhir ? kirim(terakhir) : mintaState(); }
  if (e.data && e.data.type === "minta-deteksi") mintaState();
  if (e.data && e.data.type === "layar-penuh") {
    // Tab baru di sebelah tab chart: tampilan analisa lengkap (?mandiri=1), tanpa tab Portofolio.
    const d = e.data, q = String(d.q || ""), tf = String(d.tf || "1d");
    const url = `${SERVER}/?mandiri=1` + (q ? `#q=${encodeURIComponent(q)}&tf=${encodeURIComponent(tf)}` : "");
    chrome.tabs.query({ active: true, windowId: windowId ?? undefined, lastFocusedWindow: windowId == null })
      .then(([tab]) => chrome.tabs.create(tab ? { url, index: tab.index + 1, windowId: tab.windowId } : { url }))
      .catch(() => chrome.tabs.create({ url }));
  }
  if (e.data && e.data.type === "bahasa" && (e.data.nilai === "id" || e.data.nilai === "en")) {
    chrome.runtime.sendMessage({ type: "bahasa", nilai: e.data.nilai }).catch(() => {});
    siap = false;  // panel memuat ulang dirinya; deteksi terakhir dikirim lagi begitu panel melapor "siap"
    terapkanBahasa(e.data.nilai);
  }
});

document.getElementById("coba").addEventListener("click", cekServer);
chrome.windows.getCurrent().then((w) => { windowId = w.id; });
cekServer().then(mintaState);
setInterval(() => { if (!off.hidden) cekServer(); }, 5000);
