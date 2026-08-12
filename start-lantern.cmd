@echo off
rem Lantern service launcher — registered as a logon Scheduled Task (RUNBOOK.md).
set PYTHONUTF8=1
cd /d %~dp0
if not exist data mkdir data
.venv\Scripts\python.exe -m src.lantern.api >> data\service.log 2>&1
