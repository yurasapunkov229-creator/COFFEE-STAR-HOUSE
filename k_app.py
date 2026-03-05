"""k.exe — окно кухни (сервер должен быть запущен admin.exe)"""
import time, webview
import urllib.request

for _ in range(30):
    try: urllib.request.urlopen('http://localhost:5000/k', timeout=1); break
    except: time.sleep(0.5)

webview.create_window(
    '👨‍🍳 Кухня — Grand Restaurant',
    url='http://localhost:5000/k',
    width=1200, height=820, resizable=True, min_size=(800,520),
    background_color='#060908',
)
webview.start(debug=False)
