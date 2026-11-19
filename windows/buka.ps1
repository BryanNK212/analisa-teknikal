# Analisa Teknikal - peluncur Windows: nyalakan panel lokal (port 8768), pindai portofolio/daftar pantau,
# lalu buka panel di browser. Dijalankan oleh "Analisa Teknikal (Windows).bat" di folder program.
# Port 8765-8767 dipakai program lain dan tidak disentuh. Berkas ini sengaja hanya berisi huruf ASCII.
$Folder = Split-Path -Parent $PSScriptRoot
$Port = 8768
$Dasar = "http://127.0.0.1:$Port"

function Pesan([string]$Teks) {
  try { Add-Type -AssemblyName PresentationFramework; [System.Windows.MessageBox]::Show($Teks, "Analisa Teknikal") | Out-Null }
  catch { Write-Host $Teks; Read-Host "Tekan Enter untuk menutup" | Out-Null }
}

if (-not (Test-Path (Join-Path $Folder "panel.py"))) { Pesan "panel.py tidak ditemukan di $Folder."; exit 1 }

# Python yang punya numpy (utamakan yang juga punya yfinance). "py" = Python Launcher dari python.org.
$PyExe = $null
foreach ($butuh in @("numpy, yfinance", "numpy")) {
  foreach ($k in @("py -3", "python", "python3")) {
    $p = $k -split " "
    $exe = $p[0]
    $pre = @($p | Select-Object -Skip 1)
    if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
    $hasil = & $exe @pre -c "import $butuh, sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $hasil) { $PyExe = ($hasil | Select-Object -Last 1).Trim(); break }
  }
  if ($PyExe) { break }
}
if (-not $PyExe) {
  Pesan "Belum ada Python dengan numpy.`n`n1. Pasang Python dari python.org (centang 'Add python.exe to PATH').`n2. Buka Command Prompt, jalankan:`n   py -m pip install numpy yfinance matplotlib tzdata`n3. Klik dua kali peluncur ini lagi."
  exit 1
}

# Pembaruan otomatis dari GitHub (perbarui.py; rilis.json -> repo). Tanpa internet: dilewati.
if (Test-Path (Join-Path $Folder "perbarui.py")) {
  $env:PYTHONDONTWRITEBYTECODE = "1"
  $env:PYTHONUTF8 = "1"
  New-Item -ItemType Directory -Force -Path (Join-Path $Folder "output") | Out-Null
  try {
    Start-Process -FilePath $PyExe -ArgumentList @("perbarui.py") -WorkingDirectory $Folder -WindowStyle Hidden -Wait `
      -RedirectStandardOutput (Join-Path $Folder "output\perbarui_terakhir.log") -RedirectStandardError (Join-Path $Folder "output\perbarui_galat.log")
  } catch { }
}

# Panel lama di port ini dimatikan dulu supaya yang jalan selalu versi terbaru (hanya proses panel.py ini).
Get-CimInstance Win32_Process -Filter "Name like 'python%'" -ErrorAction SilentlyContinue |
  Where-Object { $_.CommandLine -like "*panel.py*--port $Port*" } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force -ErrorAction SilentlyContinue }
Start-Sleep -Milliseconds 400

$Out = Join-Path $Folder "output"
New-Item -ItemType Directory -Force -Path $Out | Out-Null
$env:PYTHONDONTWRITEBYTECODE = "1"
$env:PYTHONUTF8 = "1"
$env:PYTHONIOENCODING = "utf-8"
Start-Process -FilePath $PyExe -ArgumentList @("panel.py", "--port", "$Port", "--no-browser") -WorkingDirectory $Folder `
  -WindowStyle Hidden -RedirectStandardOutput (Join-Path $Out "panel.log") -RedirectStandardError (Join-Path $Out "panel_galat.log")

for ($i = 0; $i -lt 120; $i++) {
  $st = $null
  try { $st = Invoke-RestMethod -Uri "$Dasar/api/status" -TimeoutSec 2 -UseBasicParsing } catch { $st = $null }
  if ($st) {
    # Belum ada portofolio maupun daftar pantau (mis. baru dipasang): langsung ke Cek aset, tanpa pindai.
    if ($st.portofolio -eq "kosong") {
      Start-Process "$Dasar/"
    } else {
      try { Invoke-RestMethod -Method Post -Uri "$Dasar/api/pindai" -Headers @{ "X-Panel" = "1" } -TimeoutSec 5 -UseBasicParsing | Out-Null } catch { }
      Start-Process "$Dasar/#portofolio"
    }
    exit 0
  }
  Start-Sleep -Milliseconds 250
}
Pesan "Panel tidak mau menyala. Keterangannya ada di output\panel_galat.log di folder Analisa Teknikal."
Start-Process notepad.exe (Join-Path $Out "panel_galat.log")
exit 1
