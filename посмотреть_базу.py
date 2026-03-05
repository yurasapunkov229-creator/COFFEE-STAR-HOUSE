"""
Просмотр базы данных restaurant.db
Запустить: python посмотреть_базу.py
"""
import sqlite3, json, os
from pathlib import Path

# Ищем базу рядом со скриптом
DB = Path(__file__).parent / 'restaurant.db'
if not DB.exists():
    print(f"❌ База не найдена: {DB}")
    input("Enter...")
    exit()

conn = sqlite3.connect(str(DB))
conn.row_factory = sqlite3.Row
c = conn.cursor()

print("=" * 60)
print(f"  База данных: {DB}")
print("=" * 60)

# ─── ТАБЛИЦЫ ───────────────────────────────────────────────
tables = c.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
print(f"\n📋 Таблицы в базе: {[t[0] for t in tables]}\n")

# ─── НАСТРОЙКИ ─────────────────────────────────────────────
print("  НАСТРОЙКИ:")
print("-" * 40)
rows = c.execute("SELECT * FROM settings").fetchall()
for r in rows:
    print(f"  {r['key']:<20} = {r['value']}")

# ─── ПОЛЬЗОВАТЕЛИ ──────────────────────────────────────────
print("\n ПОЛЬЗОВАТЕЛИ:")
print("-" * 40)
users = c.execute("SELECT id, name, role, created_at FROM users").fetchall()
if not users:
    print("  (нет пользователей)")
for u in users:
    print(f"  [{u['role']}] {u['name']:<20} — {u['created_at'][:16]}")

# ─── ЗАКАЗЫ ────────────────────────────────────────────────
print("\n ЗАКАЗЫ (все):")
print("-" * 60)
orders = c.execute("SELECT * FROM orders ORDER BY created_at DESC").fetchall()
if not orders:
    print("  (нет заказов)")
for o in orders:
    items = json.loads(o['items']) if o['items'] else []
    items_str = ", ".join(f"{i['emoji']}{i['name']}×{i['qty']}" for i in items)
    pay_icon = "✅" if o['payment'] == 'confirmed' else "⏳"
    print(f"\n  🪑 Стол №{o['table_number']}  |  👤 {o['customer_name']}")
    print(f"  ID: {o['id']}")
    print(f"  Статус: {o['status']:<15} Оплата: {pay_icon} {o['payment']}")
    print(f"  Сумма:  {o['total']:,.0f} ₸")
    print(f"  Блюда:  {items_str}")
    print(f"  Время:  {o['created_at'][:16]}")

# ─── СТАТИСТИКА ────────────────────────────────────────────
print("\n" + "=" * 60)
print("📊 СТАТИСТИКА:")
print("-" * 40)

total = c.execute("SELECT COUNT(*) FROM orders").fetchone()[0]
revenue = c.execute("SELECT SUM(total) FROM orders WHERE status != 'cancelled'").fetchone()[0] or 0
by_status = c.execute("SELECT status, COUNT(*) as cnt FROM orders GROUP BY status").fetchall()
today = c.execute("SELECT COUNT(*) FROM orders WHERE date(created_at) = date('now')").fetchone()[0]

print(f"  Всего заказов:     {total}")
print(f"  Заказов сегодня:   {today}")
print(f"  Общая выручка:     {revenue:,.0f} ₸")
print(f"\n  По статусам:")
for s in by_status:
    print(f"    {s['status']:<20} — {s[1]} шт.")

print("\n" + "=" * 60)
conn.close()
input("\nНажмите Enter для выхода...")