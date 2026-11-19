@echo off
rem Analisa Teknikal - peluncur Windows (klik dua kali). Isinya ada di windows\buka.ps1.
start "" powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "%~dp0windows\buka.ps1"
