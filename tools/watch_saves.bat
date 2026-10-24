@echo off
chcp 65001 >nul
title Shadow of War - слежение за сохранением
python "%~dp0watch_saves.py" %*
pause
