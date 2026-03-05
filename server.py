"""
Grand Restaurant – Server v4.1 ALL-IN-ONE
- Сам создаёт requirements.txt и Procfile при первом запуске
- Работает локально и на Railway без изменений
- Flask + SQLite + Socket.IO
"""
import sys, os, uuid, json, hashlib, sqlite3
from datetime import datetime, date
from pathlib import Path

# ─── АВТО-СОЗДАНИЕ ФАЙЛОВ ДЛЯ RAILWAY ────────────────────────────────────────
def bootstrap():
    """При первом запуске создаёт requirements.txt и Procfile если их нет"""
    here = Path(__file__).parent.resolve()

    req = here / 'requirements.txt'
    if not req.exists():
        req.write_text(
            "flask==3.0.3\n"
            "flask-socketio==5.3.6\n"
            "flask-cors==4.0.1\n"
            "eventlet==0.36.1\n"
            "gunicorn==22.0.0\n"
        )
        print("✅ Создан requirements.txt")

    pf = here / 'Procfile'
    if not pf.exists():
        pf.write_text("web: python server.py\n")
        print("✅ Создан Procfile")

    rj = here / 'railway.json'
    if not rj.exists():
        rj.write_text(json.dumps({
            "$schema": "https://railway.app/railway.schema.json",
            "build": {"builder": "NIXPACKS"},
            "deploy": {
                "startCommand": "python server.py",
                "restartPolicyType": "ON_FAILURE",
                "restartPolicyMaxRetries": 10
            }
        }, indent=2))
        print("✅ Создан railway.json")

bootstrap()

# ─── ЗАВИСИМОСТИ ─────────────────────────────────────────────────────────────
try:
    from flask import Flask, jsonify, request, render_template
    from flask_socketio import SocketIO
    from flask_cors import CORS
except ImportError:
    print("\n❌ Установите зависимости:")
    print("   pip install flask flask-socketio flask-cors eventlet\n")
    sys.exit(1)

# ─── PATH AUTO-DETECT ────────────────────────────────────────────────────────
def find_base():
    if getattr(sys, 'frozen', False):
        return Path(sys.executable).parent
    script = Path(__file__).parent.resolve()
    for p in [script, Path.cwd(), script.parent]:
        if (p / 'templates' / 'menu.html').exists():
            return p
    print("⚠️  Не найдена папка templates/")
    return script

BASE = find_base()

# Railway → /data (Volume), локально → рядом с server.py
if os.environ.get('RAILWAY_ENVIRONMENT'):
    DATA_DIR = Path('/data')
    DATA_DIR.mkdir(exist_ok=True)
    DB_PATH = str(DATA_DIR / 'restaurant.db')
else:
    DB_PATH = str(BASE / 'restaurant.db')

TMPL_DIR = str(BASE / 'templates')
STAT_DIR = str(BASE / 'static')

app = Flask(__name__, template_folder=TMPL_DIR, static_folder=STAT_DIR)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'GrandRest@2025#Key')
CORS(app)
# Eventlet нужен на Railway, локально достаточно threading
try:
    import eventlet
    eventlet.monkey_patch()
    _async_mode = 'eventlet'
except ImportError:
    _async_mode = 'threading'

socketio = SocketIO(
    app,
    cors_allowed_origins='*',
    async_mode=_async_mode,
    logger=False,
    engineio_logger=False
)

# ─── DB ──────────────────────────────────────────────────────────────────────
def db():
    c = sqlite3.connect(DB_PATH)
    c.row_factory = sqlite3.Row
    c.execute("PRAGMA journal_mode=WAL")
    return c

def init_db():
    with db() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(
            id TEXT PRIMARY KEY,
            name TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'customer',
            created_at TEXT
        );
        CREATE TABLE IF NOT EXISTS orders(
            id TEXT PRIMARY KEY,
            table_number INTEGER,
            customer_name TEXT,
            kaspi_order_id TEXT,
            items TEXT,
            total REAL,
            status TEXT DEFAULT 'new',
            payment TEXT DEFAULT 'kaspi_pending',
            payment_ref TEXT,
            created_at TEXT,
            updated_at TEXT
        );
        CREATE TABLE IF NOT EXISTS settings(
            key TEXT PRIMARY KEY,
            value TEXT
        );
        CREATE TABLE IF NOT EXISTS kcheck(
            order_id TEXT,
            item_id TEXT,
            checked INTEGER DEFAULT 0,
            PRIMARY KEY(order_id, item_id)
        );
        """)
        for k, v in [
            ('kaspiPhone', '77071234567'),
            ('kaspiName',  'Grand Restaurant'),
            ('restName',   'Grand Restaurant'),
        ]:
            c.execute("INSERT OR IGNORE INTO settings VALUES(?,?)", (k, v))
    print(f"✅ База данных: {DB_PATH}")

def row2dict(row):
    d = dict(row)
    if isinstance(d.get('items'), str):
        try:    d['items'] = json.loads(d['items'])
        except: d['items'] = []
    return d

# ─── AUTH ─────────────────────────────────────────────────────────────────────
@app.route('/api/auth/register', methods=['POST'])
def register():
    d = request.get_json(silent=True) or {}
    name = str(d.get('name', '')).strip()
    pw   = str(d.get('password', ''))
    if not name or not pw: return jsonify({'error': 'Заполните все поля'}), 400
    if len(pw) < 4:        return jsonify({'error': 'Пароль минимум 4 символа'}), 400
    try:
        with db() as c:
            c.execute('INSERT INTO users VALUES(?,?,?,?,?)',
                (str(uuid.uuid4()), name,
                 hashlib.sha256(pw.encode()).hexdigest(),
                 'customer', datetime.now().isoformat()))
            row = c.execute('SELECT id,name,role FROM users WHERE name=?', (name,)).fetchone()
        return jsonify(dict(row))
    except sqlite3.IntegrityError:
        return jsonify({'error': 'Имя уже занято'}), 409

@app.route('/api/auth/login', methods=['POST'])
def login():
    d = request.get_json(silent=True) or {}
    name = str(d.get('name', '')).strip()
    pw   = str(d.get('password', ''))
    hpw  = hashlib.sha256(pw.encode()).hexdigest()
    with db() as c:
        row = c.execute(
            'SELECT id,name,role FROM users WHERE name=? AND password=?',
            (name, hpw)).fetchone()
    if not row: return jsonify({'error': 'Неверное имя или пароль'}), 401
    return jsonify(dict(row))

# ─── ORDERS ──────────────────────────────────────────────────────────────────
@app.route('/api/orders', methods=['GET'])
def get_orders():
    status = request.args.get('status')
    day    = request.args.get('date', date.today().isoformat())
    with db() as c:
        if status and status != 'all':
            rows = c.execute(
                "SELECT * FROM orders WHERE status=? AND date(created_at)=? ORDER BY created_at DESC",
                (status, day)).fetchall()
        else:
            rows = c.execute(
                "SELECT * FROM orders WHERE date(created_at)=? ORDER BY created_at DESC",
                (day,)).fetchall()
    return jsonify([row2dict(r) for r in rows])

@app.route('/api/orders', methods=['POST'])
def create_order():
    d   = request.get_json(silent=True) or {}
    now = datetime.now().isoformat()
    oid = 'ord_' + uuid.uuid4().hex[:10]
    kid = d.get('paymentRef') or ('K' + datetime.now().strftime('%H%M%S'))

    order = {
        'id':             oid,
        'table_number':   int(d.get('tableNumber', 0)),
        'customer_name':  str(d.get('customerName', 'Гость')),
        'kaspi_order_id': kid,
        'items':          json.dumps(d.get('items', []), ensure_ascii=False),
        'total':          float(d.get('total', 0)),
        'status':         'new',
        'payment':        'kaspi_pending',
        'payment_ref':    kid,
        'created_at':     now,
        'updated_at':     now,
    }
    with db() as c:
        c.execute(
            'INSERT INTO orders VALUES(:id,:table_number,:customer_name,:kaspi_order_id,'
            ':items,:total,:status,:payment,:payment_ref,:created_at,:updated_at)',
            order)
    out = {**order, 'items': d.get('items', [])}
    socketio.emit('order_placed', out)
    print(f"[+] Заказ #{kid}: стол №{order['table_number']} «{order['customer_name']}» — {order['total']:,.0f} ₸")
    return jsonify(out), 201

@app.route('/api/orders/<oid>', methods=['GET'])
def get_order(oid):
    with db() as c:
        row = c.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not row: return jsonify({'error': 'Not found'}), 404
    return jsonify(row2dict(row))

@app.route('/api/orders/<oid>/status', methods=['PUT'])
def set_status(oid):
    d      = request.get_json(silent=True) or {}
    status = str(d.get('status', ''))
    now    = datetime.now().isoformat()
    with db() as c:
        c.execute('UPDATE orders SET status=?,updated_at=? WHERE id=?', (status, now, oid))
        row = c.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not row: return jsonify({'error': 'Not found'}), 404
    order = row2dict(row)
    socketio.emit('order_status_changed', order)
    return jsonify(order)

# ── ПОДТВЕРЖДЕНИЕ ОПЛАТЫ (Admin нажимает кнопку) ─────────────────────────────
@app.route('/api/orders/<oid>/payment', methods=['PUT'])
def confirm_payment(oid):
    now = datetime.now().isoformat()
    with db() as c:
        c.execute(
            "UPDATE orders SET payment='confirmed', status='in_kitchen', updated_at=? WHERE id=?",
            (now, oid))
        row = c.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    if not row: return jsonify({'error': 'Not found'}), 404
    order = row2dict(row)
    socketio.emit('order_status_changed', order)
    socketio.emit('order_payment_confirmed', order)
    print(f"[✅] Оплата подтверждена: {oid} → кухня")
    return jsonify(order)

@app.route('/api/orders/<oid>/cancel', methods=['PUT'])
def cancel_order(oid):
    now = datetime.now().isoformat()
    with db() as c:
        c.execute("UPDATE orders SET status='cancelled',updated_at=? WHERE id=?", (now, oid))
        row = c.execute('SELECT * FROM orders WHERE id=?', (oid,)).fetchone()
    order = row2dict(row) if row else {'id': oid, 'status': 'cancelled'}
    socketio.emit('order_status_changed', order)
    return jsonify(order)

# ─── KITCHEN CHECKS ──────────────────────────────────────────────────────────
@app.route('/api/kitchen/checks/<oid>', methods=['GET'])
def get_checks(oid):
    with db() as c:
        rows = c.execute('SELECT item_id,checked FROM kcheck WHERE order_id=?', (oid,)).fetchall()
    return jsonify({r['item_id']: bool(r['checked']) for r in rows})

@app.route('/api/kitchen/checks/<oid>', methods=['PUT'])
def set_checks(oid):
    d = request.get_json(silent=True) or {}
    with db() as c:
        for item_id, checked in d.items():
            c.execute('INSERT OR REPLACE INTO kcheck VALUES(?,?,?)',
                      (oid, item_id, 1 if checked else 0))
    return jsonify({'ok': True})

@app.route('/api/kitchen/checks/<oid>', methods=['DELETE'])
def del_checks(oid):
    with db() as c:
        c.execute('DELETE FROM kcheck WHERE order_id=?', (oid,))
    return jsonify({'ok': True})

# ─── SETTINGS ────────────────────────────────────────────────────────────────
@app.route('/api/settings', methods=['GET'])
def get_settings():
    with db() as c:
        rows = c.execute('SELECT * FROM settings').fetchall()
    return jsonify({r['key']: r['value'] for r in rows})

@app.route('/api/settings', methods=['PUT'])
def save_settings():
    d = request.get_json(silent=True) or {}
    with db() as c:
        for k, v in d.items():
            c.execute('INSERT OR REPLACE INTO settings VALUES(?,?)', (str(k), str(v)))
    return jsonify({'ok': True})

@app.route('/api/stats/today')
def stats():
    day = date.today().isoformat()
    with db() as c:
        rows = c.execute(
            "SELECT status,total FROM orders WHERE date(created_at)=?", (day,)).fetchall()
    orders = [dict(r) for r in rows]
    by_s = {}
    for o in orders:
        by_s[o['status']] = by_s.get(o['status'], 0) + 1
    return jsonify({
        'total':     len(orders),
        'revenue':   sum(o['total'] for o in orders),
        'by_status': by_s
    })

# ─── PAGES ───────────────────────────────────────────────────────────────────
@app.route('/')
@app.route('/menu')
def menu_page():    return render_template('menu.html')

@app.route('/admin')
def admin_page():   return render_template('admin.html')

@app.route('/kitchen')
@app.route('/k')
def kitchen_page(): return render_template('k.html')

@app.route('/waiter')
@app.route('/o')
def waiter_page():  return render_template('o.html')

# ─── WEBSOCKET ───────────────────────────────────────────────────────────────
@socketio.on('connect')
def on_connect():    print(f'[WS] ↑ {request.sid[:8]}')

@socketio.on('disconnect')
def on_disconnect(): print(f'[WS] ↓ {request.sid[:8]}')

# ─── MAIN ────────────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()

    missing = [f for f in ['menu.html', 'admin.html', 'k.html', 'o.html']
               if not (BASE / 'templates' / f).exists()]
    if missing:
        print(f"❌ Нет файлов в templates/: {', '.join(missing)}")
        input("Нажмите Enter...")
        sys.exit(1)

    try:
        import socket as sk
        s = sk.socket(sk.AF_INET, sk.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
    except:
        ip = "192.168.X.X"

    port = int(os.environ.get('PORT', 5000))

    print()
    print("╔══════════════════════════════════════════════════════════╗")
    print("║           🍽️   Grand Restaurant  v4.1                   ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  📱 Меню (клиенты):  http://{ip}:{port}             ║")
    print(f"║  📋 Администратор:   http://localhost:{port}/admin      ║")
    print(f"║  👨‍🍳 Кухня:           http://localhost:{port}/k          ║")
    print(f"║  🚶 Официант:        http://localhost:{port}/o          ║")
    print("╠══════════════════════════════════════════════════════════╣")
    print(f"║  🗄️  БД: {str(DB_PATH)[:52]:<52} ║")
    print("╚══════════════════════════════════════════════════════════╝")
    print()

    socketio.run(
        app,
        host='0.0.0.0',
        port=port,
        debug=False,
        allow_unsafe_werkzeug=True,
        use_reloader=False
    )