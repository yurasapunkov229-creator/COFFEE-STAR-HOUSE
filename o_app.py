"""o.exe — окно официанта"""
import time, webview
import urllib.request

for _ in range(30):
    try: urllib.request.urlopen('http://localhost:5000/o', timeout=1); break
    except: time.sleep(0.5)

webview.create_window(
    '🚶 Официант — Grand Restaurant',
    url='http://localhost:5000/o',
    width=960, height=720, resizable=True, min_size=(600,500),
    background_color='#080a0f',
)
webview.start(debug=False)
