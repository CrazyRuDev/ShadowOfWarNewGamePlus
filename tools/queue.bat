@echo off
chcp 65001 >nul
title Shadow of War - очередь Немезиды
python "%~dp0..\research\queue.py" %*
pause
