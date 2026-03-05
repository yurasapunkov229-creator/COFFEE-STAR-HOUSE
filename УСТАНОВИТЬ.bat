@echo off
title Установка зависимостей
color 0E
cd /d "%~dp0"
echo  Устанавливаю зависимости...
pip install flask flask-socketio flask-cors pywebview simple-websocket
echo.
echo  Готово! Теперь запустите ЗАПУСТИТЬ_СЕРВЕР.bat
pause
