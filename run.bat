@echo off
setlocal
cd /d "%~dp0"
py server.py %*
