@echo off
title Сборка .exe приложений
color 0B
cd /d "%~dp0"
echo.
echo  [1/3] admin.exe (сервер + панель администратора)...
pyinstaller --onefile --windowed --name admin ^
  --add-data "templates;templates" ^
  --add-data "static;static" ^
  --add-data "server.py;." ^
  --hidden-import flask --hidden-import flask_socketio ^
  --hidden-import flask_cors --hidden-import simple_websocket ^
  --hidden-import engineio --hidden-import socketio --hidden-import sqlite3 ^
  admin_app.py

echo  [2/3] k.exe (кухня)...
pyinstaller --onefile --windowed --name k k_app.py

echo  [3/3] o.exe (официант)...
pyinstaller --onefile --windowed --name o o_app.py

echo.
echo  ╔═══════════════════════════════╗
echo  ║  Готово! Файлы в папке dist\  ║
echo  ║  Скопируй templates\ и        ║
echo  ║  static\ рядом с admin.exe    ║
echo  ╚═══════════════════════════════╝
pause
