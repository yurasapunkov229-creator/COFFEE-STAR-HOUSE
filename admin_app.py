"""admin.exe — запускает сервер + открывает окно администратора"""
import sys, os, threading, time
from pathlib import Path

if getattr(sys,'frozen',False):
    BASE = Path(sys.executable).parent
    os.chdir(BASE)
else:
    BASE = Path(__file__).parent

sys.path.insert(0, str(BASE))

import webview
_ready = threading.Event()

def run_server():
    from server import app, socketio, init_db
    init_db()
    _ready.set()
    socketio.run(app, host='0.0.0.0', port=5000, debug=False,
                 allow_unsafe_werkzeug=True, use_reloader=False)

if __name__ == '__main__':
    t = threading.Thread(target=run_server, daemon=True)
    t.start()
    _ready.wait(timeout=15)
    time.sleep(0.8)
    webview.create_window(
        '📋 Администратор — Grand Restaurant',
        url='http://localhost:5000/admin',
        width=1360, height=860, resizable=True, min_size=(960,620),
        background_color='#090c0f',
    )
    webview.start(debug=False)
