@echo off
powershell -NoProfile -ExecutionPolicy Bypass -File "C:\dev\kia_native_run.ps1" -Background
powershell -NoProfile -ExecutionPolicy Bypass -WindowStyle Hidden -File "C:\dev\kia_watchdog.ps1"
