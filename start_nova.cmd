@echo off
chcp 65001 >nul
title Nova
set "PYW=C:\Users\HP\AppData\Local\Programs\Python\Python312\pythonw.exe"
set "DIR=C:\Users\HP\NovaCompanion"

rem All startup work is silent: no console, no thinking stream, no dashboard.
"%PYW%" -X utf8 "%DIR%\privacy.py"
"%PYW%" -X utf8 "%DIR%\ensure_models.py"

rem The only thing that appears is the small animated sprite on the desktop.
start "" /D "%DIR%" "%PYW%" -X utf8 "%DIR%\nova.py"

rem Click her to type. Say "stop" to halt. Everything else runs behind her.
timeout /t 2 >nul
