@echo off
title Grand Restaurant — Сервер
color 0A
cd /d "%~dp0"
echo.
echo  [Запуск сервера...]
echo  Меню для клиентов: http://192.168.X.X:5000
echo  (узнайте IP через ipconfig)
echo.
python server.py
if errorlevel 1 (
    echo.
    echo  [ОШИБКА] Проверьте установку Python
    echo  pip install -r requirements.txt
    pause
)
