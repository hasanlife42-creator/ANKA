from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
import csv
import io
from xml.sax.saxutils import escape
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, StreamingResponse, FileResponse
from starlette.middleware.sessions import SessionMiddleware

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("ANKA_DB_PATH", BASE / "data" / "anka.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
BACKUP_DIR = Path(os.getenv("ANKA_BACKUP_DIR", BASE / "backups"))
BACKUP_DIR.mkdir(parents=True, exist_ok=True)
TR = ZoneInfo("Europe/Istanbul")

app = FastAPI(title="ANKA", docs_url=None, redoc_url=None)
app.add_middleware(
    SessionMiddleware,
    secret_key=os.getenv("ANKA_SECRET_KEY", "change-this-secret"),
    same_site="lax",
    https_only=os.getenv("ANKA_HTTPS_ONLY", "0") == "1",
    max_age=60 * 60 * 12,
)

ROLE = {"admin": "Yönetici", "manager": "Müdür", "staff": "Personel"}
PAYMENT = {"cash": "Nakit", "iban": "IBAN", "easy_address": "Kolay Adres", "card": "Kolay Adres"}
STATUS = {
    "assigned": "Personele Gönderildi",
    "active": "Devam Ediyor",
    "pending": "Onay Bekliyor",
    "approved": "Onaylandı",
    "rejected": "Reddedildi",
    "cancelled": "İptal",
    "cancel_requested": "İptal Onayı Bekliyor",
}

CSS = """
:root{
  --bg:#f4f6f8;--surface:#ffffff;--surface-2:#f8fafc;--text:#0f172a;--muted:#64748b;
  --line:#e2e8f0;--nav:#0b1220;--nav-2:#111827;--brand:#f59e0b;--brand-2:#b45309;
  --green:#059669;--red:#dc2626;--orange:#d97706;--blue:#2563eb;--shadow:0 14px 40px rgba(15,23,42,.08)
}
*{box-sizing:border-box}
html{scroll-behavior:smooth}
body{margin:0;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:
linear-gradient(180deg,#f8fafc 0%,#f1f5f9 100%);color:var(--text);min-height:100vh}
a{text-decoration:none;color:inherit}
button,input,select,textarea{font:inherit}
.top{
  height:72px;background:rgba(11,18,32,.96);backdrop-filter:blur(14px);color:#fff;
  display:flex;justify-content:space-between;align-items:center;padding:0 22px;
  position:sticky;top:0;z-index:40;border-bottom:1px solid rgba(255,255,255,.08)
}
.brand{display:flex;align-items:center;gap:12px;font-weight:900;letter-spacing:.14em;font-size:22px}
.logo{
  width:40px;height:40px;border-radius:14px;background:linear-gradient(135deg,var(--brand),var(--brand-2));
  display:grid;place-items:center;color:#fff;box-shadow:0 10px 25px rgba(245,158,11,.28)
}
.user{display:flex;align-items:center;gap:12px}.user small{display:block;color:#cbd5e1}
.shell{display:grid;grid-template-columns:248px minmax(0,1fr);min-height:calc(100vh - 72px)}
nav{
  background:linear-gradient(180deg,var(--nav) 0%,var(--nav-2) 100%);
  border-right:1px solid rgba(255,255,255,.04);padding:18px 12px;position:sticky;top:72px;
  height:calc(100vh - 72px);overflow:auto
}
nav a{
  display:flex;align-items:center;gap:11px;padding:12px 14px;border-radius:13px;color:#cbd5e1;
  margin-bottom:6px;transition:.18s ease;border:1px solid transparent
}
nav a:hover{
  background:rgba(255,255,255,.07);color:#fff;border-color:rgba(255,255,255,.06);
  transform:translateX(2px)
}
nav a b{font-size:17px;width:20px;text-align:center}
nav a span{font-weight:650}
main{padding:28px;min-width:0;max-width:1600px;width:100%;margin:0 auto}
.head{display:flex;justify-content:space-between;align-items:center;gap:16px;margin-bottom:20px}
.head h1{margin:0;font-size:30px;letter-spacing:-.03em}.head p{margin:6px 0 0;color:var(--muted)}
.card{
  background:rgba(255,255,255,.96);border:1px solid rgba(226,232,240,.95);border-radius:20px;
  padding:20px;box-shadow:var(--shadow);transition:.18s ease
}
.card:hover{box-shadow:0 18px 50px rgba(15,23,42,.10)}
.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:18px}
.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-bottom:20px}
.stat{
  background:linear-gradient(180deg,#fff,#fbfdff);border:1px solid var(--line);border-radius:18px;
  padding:18px;position:relative;overflow:hidden;box-shadow:0 10px 28px rgba(15,23,42,.05)
}
.stat:before{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:linear-gradient(var(--brand),var(--brand-2))}
.stat small{display:block;color:var(--muted);margin-bottom:8px;font-weight:650}.stat strong{font-size:24px;letter-spacing:-.02em}
.warn:before{background:linear-gradient(#fb923c,#c2410c)}
.form{display:flex;flex-direction:column;gap:14px}
.form input,.form select,.form textarea,.inline input,.inline select{
  width:100%;padding:12px 13px;border:1px solid #cbd5e1;border-radius:12px;background:#fff;
  transition:.15s ease
}
.form input:focus,.form select:focus,.form textarea:focus,.inline input:focus,.inline select:focus{
  outline:none;border-color:var(--brand);box-shadow:0 0 0 4px rgba(245,158,11,.12)
}
.form label{font-weight:700;font-size:14px;color:#334155}
.btn{
  border:1px solid var(--line);background:#fff;border-radius:12px;padding:11px 15px;font-weight:800;
  cursor:pointer;transition:.16s ease;display:inline-flex;align-items:center;justify-content:center;gap:8px
}
.btn:hover{transform:translateY(-1px);box-shadow:0 8px 20px rgba(15,23,42,.08)}
.btn.primary{background:linear-gradient(135deg,#111827,#0f172a);border-color:#111827;color:#fff}
.btn.green{background:linear-gradient(135deg,#10b981,#047857);border-color:#059669;color:#fff}
.btn.red{background:linear-gradient(135deg,#ef4444,#b91c1c);border-color:#dc2626;color:#fff}
.btn.orange{background:linear-gradient(135deg,#f59e0b,#b45309);border-color:#d97706;color:#fff}
.btn.full{width:100%}.btn:disabled{opacity:.5;cursor:not-allowed;transform:none;box-shadow:none}
.table{overflow:auto;border-radius:14px;border:1px solid var(--line)}
table{width:100%;border-collapse:collapse;min-width:720px;background:#fff}
th,td{text-align:left;padding:12px 11px;border-bottom:1px solid var(--line);font-size:14px}
th{color:var(--muted);font-size:12px;text-transform:uppercase;letter-spacing:.05em;background:#f8fafc}
tr:last-child td{border-bottom:none}
.badge{display:inline-flex;padding:6px 10px;border-radius:999px;font-size:12px;font-weight:800;border:1px solid transparent}
.pending,.assigned{background:#fff7ed;color:#b45309;border-color:#fed7aa}
.approved,.active{background:#ecfdf5;color:#047857;border-color:#a7f3d0}
.rejected,.cancelled,.cancel_requested{background:#fef2f2;color:#b91c1c;border-color:#fecaca}
.help{background:#fef2f2;color:#b91c1c;animation:pulse 1.2s infinite;border-color:#fecaca}
.flash{
  padding:13px 15px;border-radius:13px;margin-bottom:16px;background:#ecfdf5;color:#047857;
  border:1px solid #a7f3d0;box-shadow:0 10px 25px rgba(5,150,105,.08)
}
.flash.error{background:#fef2f2;color:#b91c1c;border-color:#fecaca}
.login{
  min-height:100vh;display:grid;place-items:center;
  background:
  radial-gradient(circle at 15% 15%,rgba(245,158,11,.18),transparent 28%),
  radial-gradient(circle at 85% 10%,rgba(37,99,235,.12),transparent 22%),
  linear-gradient(135deg,#050816,#0f172a 58%,#111827);padding:22px
}
.loginbox{
  width:min(460px,100%);background:rgba(255,255,255,.98);border-radius:28px;padding:34px;
  box-shadow:0 35px 90px rgba(0,0,0,.38);border:1px solid rgba(255,255,255,.25)
}
.loginbrand{display:flex;align-items:center;gap:16px}.loginbrand .logo{width:64px;height:64px;font-size:28px}
.loginbrand h1{font-size:42px;letter-spacing:.17em;margin:0}.muted{color:var(--muted)}
.branch-grid,.room-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}
.room-card{position:relative;overflow:hidden}.room-card:after{
  content:"";position:absolute;right:-30px;bottom:-30px;width:90px;height:90px;border-radius:50%;
  background:rgba(245,158,11,.08)
}
.room-card h3{margin:0 0 6px;font-size:19px}.timer{font-size:38px;font-weight:950;letter-spacing:.04em;margin:15px 0}
.room-free{color:var(--muted);font-size:20px;padding:30px 0}
.inline{display:flex;gap:8px;align-items:end}
.approval{
  display:grid;grid-template-columns:1fr auto 1fr;gap:14px;align-items:center;padding:17px;
  border:1px solid var(--line);border-radius:16px;margin-bottom:11px;background:#fff;box-shadow:0 8px 24px rgba(15,23,42,.05)
}
.amount{font-size:24px;font-weight:900}
.staff-hero{max-width:720px;margin:auto}.staff-actions{display:grid;grid-template-columns:1fr 1fr;gap:12px}
.staff-actions .btn{padding:16px;font-size:17px}.active-session{text-align:center}.active-session h2{margin-bottom:4px}
.active-session .timer{font-size:58px}.settings-row{display:grid;grid-template-columns:1fr 120px auto auto;gap:8px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}
.live-pill{display:inline-flex;align-items:center;gap:7px;padding:7px 10px;border-radius:999px;background:rgba(16,185,129,.12);color:#86efac;font-size:12px;font-weight:800}
.live-dot{width:8px;height:8px;border-radius:50%;background:#22c55e;box-shadow:0 0 0 4px rgba(34,197,94,.14);animation:pulse 1.8s infinite}
@keyframes pulse{50%{opacity:.5}}
@media(max-width:1080px){.stats{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.branch-grid,.room-grid{grid-template-columns:1fr}}
@media(max-width:760px){
  .top{height:64px;padding:0 12px}.brand{font-size:18px}.logo{width:36px;height:36px}.user div{display:none}
  .shell{display:block}nav{
    position:fixed;bottom:0;left:0;right:0;top:auto;height:auto;z-index:50;display:flex;overflow-x:auto;
    padding:6px;border-top:1px solid rgba(255,255,255,.08);border-right:0
  }
  nav a{flex:0 0 auto;flex-direction:column;gap:2px;font-size:16px;padding:8px 10px;margin:0}
  nav a span{font-size:10px}main{padding:18px 12px 96px}.head{align-items:flex-start;flex-direction:column}
  .head h1{font-size:25px}.stats{grid-template-columns:1fr 1fr}.stat strong{font-size:20px}
  .inline{flex-direction:column;align-items:stretch}.active-session .timer{font-size:48px}
}
"""
def db():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA foreign_keys=ON")
    con.execute("PRAGMA journal_mode=WAL")
    return con

def utc_now() -> datetime:
    return datetime.now(timezone.utc).replace(microsecond=0)

def iso_utc(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")

def local_now_text() -> str:
    return datetime.now(TR).replace(microsecond=0).strftime("%Y-%m-%d %H:%M:%S")

def business_date() -> str:
    return datetime.now(TR).date().isoformat()

def hash_password(password, salt_hex=None):
    salt = bytes.fromhex(salt_hex) if salt_hex else os.urandom(16)
    digest = hashlib.scrypt(password.encode(), salt=salt, n=2**14, r=8, p=1, dklen=32)
    return f"{salt.hex()}${digest.hex()}"

def verify_password(password, stored):
    try:
        salt, expected = stored.split("$", 1)
        got = hash_password(password, salt).split("$", 1)[1]
        return hmac.compare_digest(got, expected)
    except Exception:
        return False

def to_kurus(value):
    try:
        d = Decimal(value.strip().replace(".", "").replace(",", "."))
    except InvalidOperation:
        raise ValueError("Geçerli tutar girin.")
    if d <= 0 or d > 1000000:
        raise ValueError("Tutar aralığı geçersiz.")
    return int((d * 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))

def money(v):
    d = Decimal(int(v or 0)) / 100
    return f"{d:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".") + " ₺"

def migrate(con):
    session_cols = {r["name"] for r in con.execute("PRAGMA table_info(sessions)").fetchall()}
    additions = {
        "help_requested": "INTEGER NOT NULL DEFAULT 0",
        "cancelled_at": "TEXT",
        "cancel_reason": "TEXT",
        "assigned_at": "TEXT",
        "accepted_at": "TEXT",
        "completed_at": "TEXT",
        "cancel_requested_at": "TEXT",
        "cancel_requested_by": "INTEGER REFERENCES users(id)",
        "cancel_decision_at": "TEXT",
        "cancel_decision_by": "INTEGER REFERENCES users(id)",
        "cancel_pay_commission": "INTEGER",
        "updated_at": "TEXT",
        "updated_by": "INTEGER REFERENCES users(id)",
    }
    for name, sql_type in additions.items():
        if name not in session_cols:
            con.execute(f"ALTER TABLE sessions ADD COLUMN {name} {sql_type}")

    user_cols = {r["name"] for r in con.execute("PRAGMA table_info(users)").fetchall()}
    for name, sql_type in {"last_login_at":"TEXT","updated_at":"TEXT","updated_by":"INTEGER REFERENCES users(id)"}.items():
        if name not in user_cols:
            con.execute(f"ALTER TABLE users ADD COLUMN {name} {sql_type}")

    con.executescript("""
    CREATE TABLE IF NOT EXISTS expenses(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      branch_id INTEGER NOT NULL REFERENCES branches(id),
      description TEXT NOT NULL,
      amount_kurus INTEGER NOT NULL,
      expense_date TEXT NOT NULL,
      created_by INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS staff_deductions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      branch_id INTEGER NOT NULL REFERENCES branches(id),
      staff_id INTEGER NOT NULL REFERENCES users(id),
      deduction_date TEXT NOT NULL,
      deduction_type TEXT NOT NULL CHECK(deduction_type IN('security','cleaning','meal')),
      description TEXT,
      amount_kurus INTEGER NOT NULL,
      created_by INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS day_closings(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      branch_id INTEGER NOT NULL REFERENCES branches(id),
      business_date TEXT NOT NULL,
      expected_cash_kurus INTEGER NOT NULL DEFAULT 0,
      expected_card_kurus INTEGER NOT NULL DEFAULT 0,
      expected_iban_kurus INTEGER NOT NULL DEFAULT 0,
      expense_kurus INTEGER NOT NULL DEFAULT 0,
      commission_kurus INTEGER NOT NULL DEFAULT 0,
      counted_cash_kurus INTEGER NOT NULL DEFAULT 0,
      counted_card_kurus INTEGER NOT NULL DEFAULT 0,
      counted_iban_kurus INTEGER NOT NULL DEFAULT 0,
      note TEXT,
      closed_by INTEGER NOT NULL REFERENCES users(id),
      closed_at TEXT NOT NULL,
      reopened_at TEXT,
      reopened_by INTEGER REFERENCES users(id),
      reopen_reason TEXT,
      UNIQUE(branch_id,business_date)
    );
    CREATE TABLE IF NOT EXISTS backups(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      filename TEXT NOT NULL,
      created_by INTEGER REFERENCES users(id),
      created_at TEXT NOT NULL,
      note TEXT
    );
    CREATE TABLE IF NOT EXISTS finance_settings(
      branch_id INTEGER PRIMARY KEY REFERENCES branches(id),
      cleaner_name TEXT NOT NULL DEFAULT 'Melis',
      cleaning_daily_wage_kurus INTEGER NOT NULL DEFAULT 175000,
      updated_at TEXT,
      updated_by INTEGER REFERENCES users(id)
    );
    CREATE TABLE IF NOT EXISTS fund_adjustments(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      branch_id INTEGER NOT NULL REFERENCES branches(id),
      fund_type TEXT NOT NULL CHECK(fund_type IN('security','cleaning')),
      adjustment_date TEXT NOT NULL,
      amount_kurus INTEGER NOT NULL,
      description TEXT NOT NULL,
      created_by INTEGER NOT NULL REFERENCES users(id),
      created_at TEXT NOT NULL
    );
    """)
    for branch in con.execute("SELECT id FROM branches").fetchall():
        con.execute("INSERT OR IGNORE INTO finance_settings(branch_id,cleaner_name,cleaning_daily_wage_kurus) VALUES(?, 'Melis', 175000)",(branch['id'],))

def init_db():
    con = db()
    con.executescript("""
    CREATE TABLE IF NOT EXISTS branches(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS users(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE COLLATE NOCASE,
      full_name TEXT NOT NULL,
      password_hash TEXT NOT NULL,
      role TEXT NOT NULL,
      branch_id INTEGER REFERENCES branches(id),
      commission_rate INTEGER NOT NULL DEFAULT 30,
      active INTEGER NOT NULL DEFAULT 1,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS rooms(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      branch_id INTEGER NOT NULL REFERENCES branches(id),
      name TEXT NOT NULL,
      active INTEGER NOT NULL DEFAULT 1,
      UNIQUE(branch_id,name)
    );
    CREATE TABLE IF NOT EXISTS services(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      duration_minutes INTEGER NOT NULL,
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS sessions(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      session_no TEXT NOT NULL UNIQUE,
      branch_id INTEGER NOT NULL REFERENCES branches(id),
      room_id INTEGER NOT NULL REFERENCES rooms(id),
      service_id INTEGER NOT NULL REFERENCES services(id),
      staff_id INTEGER NOT NULL REFERENCES users(id),
      amount_kurus INTEGER NOT NULL,
      commission_kurus INTEGER NOT NULL DEFAULT 0,
      note TEXT,
      status TEXT NOT NULL DEFAULT 'assigned',
      payment_method TEXT,
      started_at TEXT,
      ends_at TEXT,
      assigned_at TEXT,
      accepted_at TEXT,
      completed_at TEXT,
      approved_at TEXT,
      approved_by INTEGER REFERENCES users(id),
      rejection_reason TEXT,
      business_date TEXT NOT NULL,
      help_requested INTEGER NOT NULL DEFAULT 0,
      cancelled_at TEXT,
      cancel_reason TEXT
    );
    CREATE TABLE IF NOT EXISTS audit_logs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER REFERENCES users(id),
      action TEXT NOT NULL,
      entity_type TEXT NOT NULL,
      entity_id TEXT,
      details TEXT,
      ip_address TEXT,
      created_at TEXT NOT NULL
    );
    """)
    migrate(con)

    if not con.execute("SELECT 1 FROM branches").fetchone():
        con.execute("INSERT INTO branches(name) VALUES('Şube 1')")
        con.execute("INSERT INTO branches(name) VALUES('Şube 2')")
    for branch in con.execute("SELECT id FROM branches").fetchall():
        if not con.execute("SELECT 1 FROM rooms WHERE branch_id=?", (branch["id"],)).fetchone():
            for name in ("Oda 1", "Oda 2", "Oda 3"):
                con.execute("INSERT INTO rooms(branch_id,name) VALUES(?,?)", (branch["id"], name))
    if not con.execute("SELECT 1 FROM services").fetchone():
        for name, duration in (
            ("Klasik Masaj", 60),
            ("Aroma Terapi", 60),
            ("Sırt Masajı", 30),
            ("Derin Doku", 45),
        ):
            con.execute("INSERT INTO services(name,duration_minutes) VALUES(?,?)", (name, duration))
    if not con.execute("SELECT 1 FROM users").fetchone():
        con.execute(
            """INSERT INTO users(username,full_name,password_hash,role,commission_rate,active,created_at)
               VALUES('admin','ANKA Yönetici',?,'admin',30,1,?)""",
            (hash_password("Anka1234!"), local_now_text()),
        )
    con.commit()
    con.close()

init_db()

def current_user(request):
    uid = request.session.get("uid")
    if not uid:
        return None
    con = db()
    row = con.execute("SELECT * FROM users WHERE id=? AND active=1", (uid,)).fetchone()
    con.close()
    return row

def csrf(request):
    token = request.session.get("csrf")
    if not token:
        token = secrets.token_urlsafe(24)
        request.session["csrf"] = token
    return token

def csrf_ok(request, token):
    saved = request.session.get("csrf", "")
    return bool(saved and token and hmac.compare_digest(saved, token))

def flash(request, message, kind="ok"):
    request.session["flash"] = {"msg": message, "kind": kind}

def pop_flash(request):
    return request.session.pop("flash", None)

def require(request, roles=None):
    u = current_user(request)
    if not u:
        return None
    if roles and u["role"] not in roles:
        return None
    return u

def audit(request, action, entity, entity_id="", details=""):
    u = current_user(request)
    ip = request.client.host if request.client else "unknown"
    con = db()
    con.execute(
        "INSERT INTO audit_logs(user_id,action,entity_type,entity_id,details,ip_address,created_at) VALUES(?,?,?,?,?,?,?)",
        (u["id"] if u else None, action, entity, str(entity_id), details, ip, local_now_text()),
    )
    con.commit()
    con.close()

def finalize_due_sessions():
    con = db(); now_text = iso_utc(utc_now())
    due = con.execute("SELECT id FROM sessions WHERE status='active' AND ends_at IS NOT NULL AND ends_at<=?",(now_text,)).fetchall()
    for row in due:
        con.execute("UPDATE sessions SET status='pending',completed_at=COALESCE(completed_at,ends_at),help_requested=0 WHERE id=?",(row['id'],))
    con.commit(); con.close(); return [r['id'] for r in due]

def day_is_closed(branch_id:int,day:str)->bool:
    con=db(); row=con.execute("SELECT 1 FROM day_closings WHERE branch_id=? AND business_date=? AND reopened_at IS NULL",(branch_id,day)).fetchone(); con.close(); return bool(row)

def period_range(period:str,anchor:str):
    d=date.fromisoformat(anchor)
    if period=='week': start=d-timedelta(days=d.weekday()); end=start+timedelta(days=6)
    elif period=='month': start=d.replace(day=1); end=(start.replace(day=28)+timedelta(days=4)).replace(day=1)-timedelta(days=1)
    elif period=='year': start=d.replace(month=1,day=1); end=d.replace(month=12,day=31)
    else: start=end=d
    return start.isoformat(),end.isoformat()

def finance_snapshot(branch_id:int,day:str):
    con=db()
    settings=con.execute("SELECT * FROM finance_settings WHERE branch_id=?",(branch_id,)).fetchone()
    wage=int(settings['cleaning_daily_wage_kurus'] if settings else 175000)
    cleaner=settings['cleaner_name'] if settings else 'Melis'
    totals=con.execute("""SELECT COALESCE(SUM(CASE WHEN status='approved' THEN amount_kurus ELSE 0 END),0) revenue,
      COALESCE(SUM(CASE WHEN status='approved' THEN commission_kurus ELSE 0 END),0) gross_commission,
      COALESCE(SUM(CASE WHEN status='approved' AND payment_method='cash' THEN amount_kurus ELSE 0 END),0) cash,
      COALESCE(SUM(CASE WHEN status='approved' AND payment_method='iban' THEN amount_kurus ELSE 0 END),0) iban,
      COALESCE(SUM(CASE WHEN status='approved' AND payment_method='easy_address' THEN amount_kurus ELSE 0 END),0) easy_address,
      COUNT(CASE WHEN status='approved' THEN 1 END) approved_count FROM sessions WHERE branch_id=? AND business_date=?""",(branch_id,day)).fetchone()
    deds=con.execute("""SELECT deduction_type,COALESCE(SUM(amount_kurus),0) total FROM staff_deductions WHERE branch_id=? AND deduction_date=? AND active=1 GROUP BY deduction_type""",(branch_id,day)).fetchall()
    dm={r['deduction_type']:r['total'] for r in deds}; security=dm.get('security',0); cleaning=dm.get('cleaning',0); meal=dm.get('meal',0)
    expenses=con.execute("SELECT COALESCE(SUM(amount_kurus),0) total FROM expenses WHERE branch_id=? AND expense_date=? AND active=1",(branch_id,day)).fetchone()['total']
    net_staff=int(totals['gross_commission'])-security-cleaning-meal
    prior_contrib=con.execute("SELECT COALESCE(SUM(amount_kurus),0) total FROM staff_deductions WHERE branch_id=? AND deduction_type='cleaning' AND deduction_date<? AND active=1",(branch_id,day)).fetchone()['total']
    prior_days=con.execute("SELECT COUNT(DISTINCT deduction_date) c FROM staff_deductions WHERE branch_id=? AND deduction_type='cleaning' AND deduction_date<? AND active=1",(branch_id,day)).fetchone()['c']
    prior_adj=con.execute("SELECT COALESCE(SUM(amount_kurus),0) total FROM fund_adjustments WHERE branch_id=? AND fund_type='cleaning' AND adjustment_date<?",(branch_id,day)).fetchone()['total']
    opening_clean=max(0,int(prior_contrib)+int(prior_adj)-int(prior_days)*wage)
    workday=bool(int(totals['approved_count']) or cleaning)
    available=opening_clean+cleaning
    clean_subsidy=max(wage-available,0) if workday else 0
    closing_clean=max(available-wage,0) if workday else available
    prior_security=con.execute("SELECT COALESCE(SUM(amount_kurus),0) total FROM staff_deductions WHERE branch_id=? AND deduction_type='security' AND deduction_date<=? AND active=1",(branch_id,day)).fetchone()['total']
    sec_adj=con.execute("SELECT COALESCE(SUM(amount_kurus),0) total FROM fund_adjustments WHERE branch_id=? AND fund_type='security' AND adjustment_date<=?",(branch_id,day)).fetchone()['total']
    security_balance=int(prior_security)+int(sec_adj)
    business_net=int(totals['revenue'])-max(net_staff,0)-security-clean_subsidy-int(expenses)
    con.close()
    return {'cleaner':cleaner,'wage':wage,'revenue':int(totals['revenue']),'gross_commission':int(totals['gross_commission']),'net_staff':max(net_staff,0),'cash':int(totals['cash']),'iban':int(totals['iban']),'easy_address':int(totals['easy_address']),'security':security,'cleaning':cleaning,'meal':meal,'expenses':int(expenses),'opening_cleaning':opening_clean,'cleaning_subsidy':clean_subsidy,'closing_cleaning':closing_clean,'security_balance':security_balance,'business_net':business_net,'approved_count':int(totals['approved_count'])}

def maybe_backup_hourly():
    hour=datetime.now(TR).strftime('%Y%m%d_%H')
    filename=f'anka_hourly_{hour}.db'; target=BACKUP_DIR/filename
    con=db(); exists=con.execute("SELECT 1 FROM backups WHERE filename=?",(filename,)).fetchone()
    if not exists:
        dest=sqlite3.connect(target); con.backup(dest); dest.close(); con.execute("INSERT INTO backups(filename,created_at,note) VALUES(?,?,?)",(filename,local_now_text(),'Otomatik saatlik yedek')); con.commit()
    con.close()
    cutoff=datetime.now(TR)-timedelta(days=7)
    for p in BACKUP_DIR.glob('anka_hourly_*.db'):
        try:
            if datetime.fromtimestamp(p.stat().st_mtime,TR)<cutoff: p.unlink()
        except Exception: pass

def day_is_closed(branch_id: int, day: str) -> bool:
    con = db()
    row = con.execute(
        "SELECT 1 FROM day_closings WHERE branch_id=? AND business_date=? AND reopened_at IS NULL",
        (branch_id, day),
    ).fetchone()
    con.close()
    return bool(row)

def period_range(period: str, anchor: str):
    d = date.fromisoformat(anchor)
    if period == "week":
        start = d - timedelta(days=d.weekday())
        end = start + timedelta(days=6)
    elif period == "month":
        start = d.replace(day=1)
        next_month = (start.replace(day=28) + timedelta(days=4)).replace(day=1)
        end = next_month - timedelta(days=1)
    elif period == "year":
        start = d.replace(month=1, day=1)
        end = d.replace(month=12, day=31)
    else:
        start = end = d
    return start.isoformat(), end.isoformat()

def layout(request, title, body, extra_script=""):
    u = current_user(request)
    f = pop_flash(request)
    flash_html = f'<div class="flash {"error" if f and f["kind"]=="error" else ""}">{f["msg"]}</div>' if f else ""
    if not u:
        return f'<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{title}</title><style>{CSS}</style></head><body>{flash_html}{body}</body></html>'
    if u["role"] == "staff":
        nav = """<nav><a href="/"><b>⌂</b><span>Seanslarım</span></a></nav>"""
    else:
        nav = f"""<nav>
          <a href="/"><b>⌂</b><span>Panel</span></a>
          <a href="/session/new"><b>＋</b><span>Seans Gönder</span></a>
          <a href="/live"><b>◉</b><span>Seans Durumu</span></a>
          <a href="/approvals"><b>✓</b><span>Onaylar</span></a>
          <a href="/day-end"><b>▣</b><span>Gün Sonu</span></a>
          <a href="/finance"><b>₺</b><span>Finans Merkezi</span></a>
          {'<a href="/daily-summary"><b>◆</b><span>Günlük Özet</span></a><a href="/reports"><b>▥</b><span>Raporlar</span></a>' if u["role"]=="admin" else ''}
          <a href="/settings"><b>⚙</b><span>Ayarlar</span></a>
          {'<a href="/users"><b>♙</b><span>Kullanıcılar</span></a><a href="/audit"><b>◷</b><span>Geçmiş</span></a><a href="/backups"><b>⬇</b><span>Yedekler</span></a>' if u["role"]=="admin" else ''}
        </nav>"""
    common_script = """
    <script>
    function requestNoticePermission(){if("Notification" in window&&Notification.permission==="default")Notification.requestPermission();}
    function beep(){try{const C=window.AudioContext||window.webkitAudioContext,ctx=new C(),o=ctx.createOscillator(),g=ctx.createGain();o.connect(g);g.connect(ctx.destination);o.frequency.value=880;g.gain.value=.18;o.start();setTimeout(()=>{o.stop();ctx.close()},700)}catch(e){}}
    let ankaStateKey=null,ankaBusy=false,ankaReloadAt=0;
    async function pollAnkaState(){if(ankaBusy||document.hidden)return;ankaBusy=true;try{const r=await fetch('/api/state',{cache:'no-store'});if(!r.ok)return;const d=await r.json();if(ankaStateKey===null){ankaStateKey=d.key;return}if(d.key!==ankaStateKey){ankaStateKey=d.key;if(['assignment','cancel_request','approval','help'].includes(d.event)){beep();const m={assignment:'Yeni seans atandı.',cancel_request:'Yeni iptal talebi geldi.',approval:'Yeni onay bekleyen işlem var.',help:'Personel yardım istiyor.'}[d.event];if('Notification'in window&&Notification.permission==='granted')new Notification('ANKA',{body:m})}if(Date.now()-ankaReloadAt>1500){ankaReloadAt=Date.now();setTimeout(()=>location.reload(),500)}}}catch(e){}finally{ankaBusy=false}}
    document.addEventListener('click',requestNoticePermission,{once:true});document.addEventListener('visibilitychange',()=>{if(!document.hidden)pollAnkaState()});window.addEventListener('focus',pollAnkaState);pollAnkaState();setInterval(pollAnkaState,3000);if('serviceWorker'in navigator)navigator.serviceWorker.register('/service-worker.js').catch(()=>{});
    </script>"""
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0b1220"><meta name="apple-mobile-web-app-capable" content="yes"><link rel="manifest" href="/manifest.webmanifest"><link rel="icon" href="/app-icon.svg"><title>{title} • ANKA</title><style>{CSS}</style></head><body>
    <header class="top"><a class="brand" href="/"><span class="logo">A</span>ANKA</a><div class="live-pill" style="margin-left:auto;margin-right:14px"><span class="live-dot"></span>Canlı</div><div class="user"><div><strong>{u['full_name']}</strong><small>{ROLE[u['role']]}</small></div><form method="post" action="/logout"><input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn">Çıkış</button></form></div></header>
    <div class="shell">{nav}<main>{flash_html}{body}<div style="text-align:center;color:#94a3b8;font-size:12px;padding:26px 0 4px">ANKA • Professional Operations Suite</div></main></div>{common_script}{extra_script}</body></html>"""

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request):
    if current_user(request):
        return RedirectResponse("/", 303)
    body = f"""<div class="login"><section class="loginbox"><div class="loginbrand"><span class="logo">A</span><h1>ANKA</h1></div><p class="muted">Çok şubeli canlı seans yönetimi</p>
    <form method="post" class="form"><input type="hidden" name="csrf" value="{csrf(request)}"><label>Kullanıcı adı<input name="username" required autofocus></label><label>Şifre<input type="password" name="password" required></label><button class="btn primary full">Giriş Yap</button></form></section></div>"""
    return HTMLResponse(layout(request, "Giriş", body))

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...), csrf_token: str = Form(..., alias="csrf")):
    if not csrf_ok(request, csrf_token):
        flash(request, "Oturum doğrulanamadı.", "error")
        return RedirectResponse("/login", 303)
    con = db()
    u = con.execute("SELECT * FROM users WHERE username=? COLLATE NOCASE AND active=1", (username.strip(),)).fetchone()
    if not u or not verify_password(password, u["password_hash"]):
        con.close()
        flash(request, "Kullanıcı adı veya şifre hatalı.", "error")
        return RedirectResponse("/login", 303)
    con.execute("UPDATE users SET last_login_at=? WHERE id=?", (local_now_text(), u["id"]))
    con.commit()
    con.close()
    request.session.clear()
    request.session["uid"] = u["id"]
    request.session["csrf"] = secrets.token_urlsafe(24)
    audit(request, "login", "user", u["id"], "Giriş")
    return RedirectResponse("/", 303)

@app.post("/logout")
def logout(request: Request, csrf_token: str = Form(..., alias="csrf")):
    if csrf_ok(request, csrf_token):
        audit(request, "logout", "user", request.session.get("uid", ""), "Çıkış")
    request.session.clear()
    return RedirectResponse("/login", 303)

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    u = require(request)
    if not u:
        return RedirectResponse("/login", 303)
    finalize_due_sessions()
    con = db()

    if u["role"] == "staff":
        assigned = con.execute(
            """SELECT s.*,r.name room,sv.name service,sv.duration_minutes
               FROM sessions s JOIN rooms r ON r.id=s.room_id JOIN services sv ON sv.id=s.service_id
               WHERE s.staff_id=? AND s.status='assigned' ORDER BY s.id DESC LIMIT 1""",
            (u["id"],),
        ).fetchone()
        active = con.execute(
            """SELECT s.*,r.name room,sv.name service,sv.duration_minutes
               FROM sessions s JOIN rooms r ON r.id=s.room_id JOIN services sv ON sv.id=s.service_id
               WHERE s.staff_id=? AND s.status='active' ORDER BY s.id DESC LIMIT 1""",
            (u["id"],),
        ).fetchone()
        cancel_requested = con.execute(
            """SELECT s.*,r.name room,sv.name service
               FROM sessions s JOIN rooms r ON r.id=s.room_id JOIN services sv ON sv.id=s.service_id
               WHERE s.staff_id=? AND s.status='cancel_requested' ORDER BY s.id DESC LIMIT 1""",
            (u["id"],),
        ).fetchone()
        today_rows = con.execute(
            """SELECT s.*,r.name room,sv.name service
               FROM sessions s JOIN rooms r ON r.id=s.room_id JOIN services sv ON sv.id=s.service_id
               WHERE s.staff_id=? AND s.business_date=? ORDER BY s.id DESC""",
            (u["id"], business_date()),
        ).fetchall()
        totals = con.execute(
            """SELECT COUNT(*) total,
               COALESCE(SUM(CASE WHEN status='approved' THEN commission_kurus ELSE 0 END),0) commission
               FROM sessions WHERE staff_id=? AND business_date=?""",
            (u["id"], business_date()),
        ).fetchone()
        con.close()

        if active:
            body = f"""<div class="staff-hero"><section class="card active-session"><span class="badge active">Aktif Seans</span><h2>{active['service']}</h2><p>{active['room']}</p>
            <div class="timer" id="staffTimer" data-end="{active['ends_at']}">--:--</div>
            <div class="staff-actions">
              <form method="post" action="/session/{active['id']}/help"><input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn orange full">Yardım İste</button></form>
              <form method="post" action="/session/{active['id']}/cancel" class="form">
                <input type="hidden" name="csrf" value="{csrf(request)}">
                <input name="reason" placeholder="İptal sebebi" required>
                <button class="btn red full">İptal Talebi Gönder</button>
              </form>
            </div></section></div>"""
            script = """
            <script>
            let sounded=false;
            function tickStaff(){
              const el=document.getElementById("staffTimer"); if(!el)return;
              const end=new Date(el.dataset.end); let ms=end-Date.now();
              if(ms<=0){
                el.textContent="SEANS BİTTİ"; el.style.color="#dc2626";
                if(!sounded){sounded=true;beep(); if("Notification"in window&&Notification.permission==="granted")new Notification("ANKA",{body:"Seansın tamamlandı."});}
                setTimeout(()=>location.reload(),2500); return;
              }
              const m=Math.floor(ms/60000),s=Math.floor((ms%60000)/1000);
              el.textContent=String(m).padStart(2,"0")+":"+String(s).padStart(2,"0");
            }
            tickStaff();setInterval(tickStaff,1000);
            </script>
            """
            return HTMLResponse(layout(request, "Aktif Seans", body, script))

        if cancel_requested:
            body = f"""<div class="staff-hero"><section class="card active-session">
            <span class="badge pending">İptal Onayı Bekleniyor</span>
            <h2>{cancel_requested['service']}</h2><p>{cancel_requested['room']}</p>
            <p><strong>Sebep:</strong> {cancel_requested['cancel_reason'] or '—'}</p>
            <p class="muted">Müdür veya yönetici karar verecek.</p>
            </section></div>"""
            return HTMLResponse(layout(request, "İptal Onayı", body))

        if assigned:
            body = f"""<div class="staff-hero"><section class="card active-session"><span class="badge pending">Yeni Seans Atandı</span>
            <h2>{assigned['service']}</h2><p>{assigned['room']} • {assigned['duration_minutes']} dakika</p>
            <div class="amount">{money(assigned['amount_kurus'])}</div>
            <form method="post" action="/session/{assigned['id']}/accept"><input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn green full" style="padding:16px;font-size:18px">Odaya Girdim — Seansı Başlat</button></form>
            </section></div>"""
            return HTMLResponse(layout(request, "Yeni Seans", body))

        def ttime(value):
            if not value:
                return "—"
            try:
                return datetime.fromisoformat(value.replace("Z","+00:00")).astimezone(TR).strftime("%H:%M")
            except Exception:
                return value[11:16] if len(value) >= 16 else value

        rows = ""
        for r in today_rows:
            exit_time = r["cancelled_at"] or r["completed_at"] or (r["ends_at"] if r["status"] in ("pending","approved") else None)
            rows += (
                f"<tr><td>{r['service']}</td><td>{r['room']}</td>"
                f"<td>{ttime(r['started_at']) if r['status'] not in ('assigned','cancel_requested') else '—'}</td><td>{ttime(exit_time)}</td>"
                f"<td>{money(r['commission_kurus'])}</td><td><span class='badge {r['status']}'>{STATUS.get(r['status'],r['status'])}</span></td></tr>"
            )
        rows = rows or "<tr><td colspan='6'>Bugün seans yok.</td></tr>"
        body = f"""<div class="head"><div><h1>Bugünkü Seanslarım</h1><p>{business_date()}</p></div></div>
        <div class="stats"><div class="stat"><small>Bugünkü Seans</small><strong>{totals['total']}</strong></div><div class="stat"><small>Bugünkü Primim</small><strong>{money(totals['commission'])}</strong></div></div>
        <section class="card"><div class="table"><table><tr><th>Seans</th><th>Oda</th><th>Giriş</th><th>Çıkış</th><th>Prim</th><th>Durum</th></tr>{rows}</table></div></section>"""
        return HTMLResponse(layout(request, "Seanslarım", body))

    branches = con.execute("SELECT * FROM branches WHERE active=1 ORDER BY id").fetchall()
    visible = branches if u["role"] == "admin" else [b for b in branches if b["id"] == u["branch_id"]]
    cards, total_rev, total_active, total_pending, total_assigned, total_cancel = [], 0, 0, 0, 0, 0
    for branch in visible:
        x = con.execute(
            """SELECT COALESCE(SUM(CASE WHEN status='approved' THEN amount_kurus ELSE 0 END),0) rev,
               SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) active,
               SUM(CASE WHEN status='assigned' THEN 1 ELSE 0 END) assigned,
               SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) pending,
               SUM(CASE WHEN status='cancel_requested' THEN 1 ELSE 0 END) cancel_requested
               FROM sessions WHERE branch_id=? AND business_date=?""",
            (branch["id"], business_date()),
        ).fetchone()
        total_rev += x["rev"] or 0
        total_active += x["active"] or 0
        total_assigned += x["assigned"] or 0
        total_pending += x["pending"] or 0
        total_cancel += x["cancel_requested"] or 0
        cards.append(
            f"<article class='card'><h3>{branch['name']}</h3><p class='muted'>Personel bekliyor: {x['assigned'] or 0}</p><p class='muted'>Aktif: {x['active'] or 0}</p><p class='muted'>İptal talebi: {x['cancel_requested'] or 0}</p><p class='muted'>Onay bekleyen: {x['pending'] or 0}</p><div class='amount'>{money(x['rev'])}</div><a class='btn' href='/live'>Seans Durumu</a></article>"
        )
    con.close()
    body = f"""<div class="head"><div><h1>Canlı Yönetim</h1><p>{business_date()}</p></div><a class="btn primary" href="/session/new">Personele Seans Gönder</a></div>
    <div class="stats"><div class="stat"><small>Toplam Ciro</small><strong>{money(total_rev)}</strong></div><div class="stat"><small>Personel Bekliyor</small><strong>{total_assigned}</strong></div><div class="stat"><small>Aktif Seans</small><strong>{total_active}</strong></div><div class="stat warn"><small>İptal Talebi</small><strong>{total_cancel}</strong></div><div class="stat warn"><small>Onay Bekleyen</small><strong>{total_pending}</strong></div></div>
    <div class="branch-grid">{''.join(cards)}</div>"""
    return HTMLResponse(layout(request, "Panel", body))

@app.get("/session/new", response_class=HTMLResponse)
def session_new_page(request: Request):
    u = require(request, {"admin", "manager"})
    if not u:
        return RedirectResponse("/login", 303)
    con = db()
    branches = con.execute("SELECT * FROM branches WHERE active=1 ORDER BY name").fetchall()
    if u["role"] == "manager":
        branches = [b for b in branches if b["id"] == u["branch_id"]]
    branch_ids = [b["id"] for b in branches]
    placeholders = ",".join("?" * len(branch_ids))
    rooms = con.execute(
        f"SELECT r.*,b.name branch_name FROM rooms r JOIN branches b ON b.id=r.branch_id WHERE r.active=1 AND r.branch_id IN ({placeholders}) ORDER BY b.name,r.name",
        branch_ids,
    ).fetchall() if branch_ids else []
    services = con.execute("SELECT * FROM services WHERE active=1 ORDER BY name").fetchall()
    staff = con.execute(
        f"SELECT * FROM users WHERE role='staff' AND active=1 AND branch_id IN ({placeholders}) ORDER BY full_name",
        branch_ids,
    ).fetchall() if branch_ids else []
    con.close()

    branch_fields = "<label>Şube<select name='branch_id' required><option value=''>Seçin</option>" + "".join(f"<option value='{b['id']}'>{b['name']}</option>" for b in branches) + "</select></label>"
    branch_fields += "<label>Personel<select name='staff_id' required><option value=''>Seçin</option>" + "".join(f"<option value='{s['id']}'>{s['full_name']}</option>" for s in staff) + "</select></label>"
    room_options = "".join(f"<option value='{r['id']}'>{r['branch_name']} • {r['name']}</option>" for r in rooms)
    service_options = "".join(f"<option value='{s['id']}'>{s['name']} • {s['duration_minutes']} dk</option>" for s in services)
    body = f"""<div class="head"><div><h1>Personele Seans Gönder</h1><p>Sayaç personel “Odaya Girdim” dediğinde başlayacak.</p></div></div><section class="card" style="max-width:650px"><form method="post" class="form">
    <input type="hidden" name="csrf" value="{csrf(request)}">{branch_fields}
    <label>Oda<select name="room_id" required><option value="">Seçin</option>{room_options}</select></label>
    <label>Seans Türü<select name="service_id" required><option value="">Seçin</option>{service_options}</select></label>
    <label>Ödeme Yöntemi<select name="payment_method" required><option value="">Seçin</option><option value="cash">Nakit</option><option value="iban">IBAN</option><option value="easy_address">Kolay Adres</option></select></label>
    <label>Tutar<input name="amount" inputmode="decimal" placeholder="2500" required></label>
    <label>Not<textarea name="note"></textarea></label>
    <button class="btn primary full">Personele Gönder</button></form></section>"""
    return HTMLResponse(layout(request, "Seans Gönder", body))

@app.post("/session/new")
def session_new(
    request: Request,
    branch_id: int = Form(...),
    room_id: int = Form(...),
    service_id: int = Form(...),
    staff_id: int = Form(...),
    payment_method: str = Form(...),
    amount: str = Form(...),
    note: str = Form(""),
    csrf_token: str = Form(..., alias="csrf"),
):
    u = require(request, {"admin", "manager"})
    if not u:
        return RedirectResponse("/login", 303)
    if not csrf_ok(request, csrf_token):
        flash(request, "Oturum doğrulanamadı.", "error")
        return RedirectResponse("/session/new", 303)
    if payment_method not in PAYMENT:
        flash(request, "Ödeme yöntemi seçin.", "error")
        return RedirectResponse("/session/new", 303)
    if u["role"] == "manager" and branch_id != u["branch_id"]:
        flash(request, "Bu şube için yetkin yok.", "error")
        return RedirectResponse("/session/new", 303)
    if day_is_closed(branch_id, business_date()):
        flash(request, "Bu şubenin günü kapatılmış.", "error")
        return RedirectResponse("/day-end", 303)
    try:
        amount_k = to_kurus(amount)
    except ValueError as e:
        flash(request, str(e), "error")
        return RedirectResponse("/session/new", 303)

    con = db()
    service = con.execute("SELECT * FROM services WHERE id=? AND active=1", (service_id,)).fetchone()
    room = con.execute("SELECT * FROM rooms WHERE id=? AND branch_id=? AND active=1", (room_id, branch_id)).fetchone()
    staff = con.execute("SELECT * FROM users WHERE id=? AND role='staff' AND active=1 AND branch_id=?", (staff_id, branch_id)).fetchone()
    room_busy = con.execute("SELECT 1 FROM sessions WHERE room_id=? AND status IN('assigned','active','cancel_requested')", (room_id,)).fetchone()
    staff_busy = con.execute("SELECT 1 FROM sessions WHERE staff_id=? AND status IN('assigned','active','cancel_requested')", (staff_id,)).fetchone()
    if not service or not room or not staff or room_busy or staff_busy:
        con.close()
        flash(request, "Oda veya personel kullanımda; seçimleri kontrol et.", "error")
        return RedirectResponse("/session/new", 303)

    assigned = utc_now()
    no = f"{business_date().replace('-', '')}-{int(assigned.timestamp())}-{secrets.token_hex(2)}"
    cur = con.execute(
        """INSERT INTO sessions(session_no,branch_id,room_id,service_id,staff_id,amount_kurus,note,status,payment_method,started_at,ends_at,assigned_at,business_date)
           VALUES(?,?,?,?,?,?,?,'assigned',?,?,?,?,?)""",
        (no, branch_id, room_id, service_id, staff_id, amount_k, note[:500], payment_method, iso_utc(assigned), iso_utc(assigned), iso_utc(assigned), business_date()),
    )
    con.commit()
    sid = cur.lastrowid
    con.close()
    audit(request, "assign", "session", sid, f"{no}/{payment_method}")
    flash(request, "Seans personele gönderildi.")
    return RedirectResponse("/live", 303)

@app.post("/session/{sid}/help")
def request_help(request: Request, sid: int, csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"staff"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/", 303)
    con = db()
    con.execute("UPDATE sessions SET help_requested=1 WHERE id=? AND staff_id=? AND status='active'", (sid, u["id"]))
    con.commit()
    con.close()
    audit(request, "help", "session", sid, "Yardım istendi")
    flash(request, "Müdüre yardım bildirimi gönderildi.")
    return RedirectResponse("/", 303)

@app.post("/session/{sid}/cancel")
@app.post("/session/{sid}/accept")
def accept_session(request: Request, sid: int, csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"staff"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/", 303)
    con = db()
    s = con.execute(
        """SELECT s.*,sv.duration_minutes FROM sessions s JOIN services sv ON sv.id=s.service_id
           WHERE s.id=? AND s.staff_id=? AND s.status='assigned'""",
        (sid, u["id"]),
    ).fetchone()
    if not s:
        con.close()
        flash(request, "Bu seans artık başlatılamıyor.", "error")
        return RedirectResponse("/", 303)
    if day_is_closed(s["branch_id"], s["business_date"]):
        con.close()
        flash(request, "Bu gün kapatılmış.", "error")
        return RedirectResponse("/", 303)
    start = utc_now()
    end = start + timedelta(minutes=s["duration_minutes"])
    con.execute(
        "UPDATE sessions SET status='active',started_at=?,accepted_at=?,ends_at=? WHERE id=?",
        (iso_utc(start), iso_utc(start), iso_utc(end), sid),
    )
    con.commit()
    con.close()
    audit(request, "accept", "session", sid, "Personel odaya girdi")
    flash(request, "Seans başladı.")
    return RedirectResponse("/", 303)

@app.post("/session/{sid}/cancel")
def cancel_session(
    request: Request,
    sid: int,
    reason: str = Form(...),
    csrf_token: str = Form(..., alias="csrf"),
):
    u = require(request, {"staff"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/", 303)

    con = db()
    row = con.execute(
        "SELECT * FROM sessions WHERE id=? AND staff_id=? AND status IN('assigned','active','cancel_requested')",
        (sid, u["id"]),
    ).fetchone()
    if not row:
        con.close()
        flash(request, "İptal talebi oluşturulamadı.", "error")
        return RedirectResponse("/", 303)

    con.execute(
        """UPDATE sessions
           SET status='cancel_requested',
               cancel_reason=?,
               cancel_requested_at=?,
               cancel_requested_by=?
           WHERE id=?""",
        (reason.strip()[:500], iso_utc(utc_now()), u["id"], sid),
    )
    con.commit()
    con.close()
    audit(request, "cancel_request", "session", sid, reason)
    flash(request, "İptal talebi müdür/yönetici onayına gönderildi.")
    return RedirectResponse("/", 303)

@app.get("/live", response_class=HTMLResponse)
def live(request: Request):
    u = require(request, {"admin", "manager"})
    if not u:
        return RedirectResponse("/login", 303)
    finalize_due_sessions()
    con = db()

    if u["role"] == "manager":
        branches = con.execute(
            "SELECT * FROM branches WHERE id=? AND active=1",
            (u["branch_id"],),
        ).fetchall()
    else:
        branches = con.execute(
            "SELECT * FROM branches WHERE active=1 ORDER BY name"
        ).fetchall()

    branch_sections = []
    for branch in branches:
        rooms = con.execute(
            "SELECT * FROM rooms WHERE branch_id=? AND active=1 ORDER BY name",
            (branch["id"],),
        ).fetchall()
        cards = []
        for room in rooms:
            s = con.execute(
                """SELECT s.*,u.full_name staff,sv.name service,sv.duration_minutes
                   FROM sessions s
                   JOIN users u ON u.id=s.staff_id
                   JOIN services sv ON sv.id=s.service_id
                   WHERE s.room_id=? AND s.status IN('assigned','active','cancel_requested')
                   ORDER BY s.id DESC LIMIT 1""",
                (room["id"],),
            ).fetchone()

            if s and s["status"] == "assigned":
                cards.append(
                    f"""<article class="card room-card">
                    <h3>{room['name']}</h3>
                    <span class="badge pending">Personel Bekleniyor</span>
                    <p>{s['staff']} • {s['service']} • {s['duration_minutes']} dk</p>
                    <div class="room-free">Henüz başlamadı</div>
                    </article>"""
                )
            elif s and s["status"] == "cancel_requested":
                cards.append(
                    f"""<article class="card room-card">
                    <h3>{room['name']}</h3>
                    <span class="badge rejected">İptal Onayı Bekliyor</span>
                    <p>{s['staff']} • {s['service']}</p>
                    <p><strong>Sebep:</strong> {s['cancel_reason'] or '—'}</p>
                    </article>"""
                )
            elif s:
                help_badge = "<span class='badge help'>YARDIM İSTİYOR</span>" if s["help_requested"] else ""
                cards.append(
                    f"""<article class="card room-card">
                    <h3>{room['name']}</h3>{help_badge}
                    <p>{s['staff']} • {s['service']}</p>
                    <div class="timer liveTimer" data-end="{s['ends_at']}" data-id="{s['id']}">--:--</div>
                    <div class="inline">
                      <form method="post" action="/session/{s['id']}/extend">
                        <input type="hidden" name="csrf" value="{csrf(request)}">
                        <input type="hidden" name="minutes" value="15">
                        <button class="btn">+15 dk</button>
                      </form>
                      <form method="post" action="/session/{s['id']}/finish">
                        <input type="hidden" name="csrf" value="{csrf(request)}">
                        <button class="btn green">Bitir</button>
                      </form>
                    </div>
                    </article>"""
                )
            else:
                cards.append(
                    f"<article class='card room-card'><h3>{room['name']}</h3><div class='room-free'>Oda boş</div></article>"
                )

        branch_sections.append(
            f"""<section class="card" style="padding:16px">
            <div class="head" style="margin-bottom:14px">
              <div><h2 style="margin:0">{branch['name']}</h2><p>Canlı oda durumu</p></div>
            </div>
            <div class="room-grid">{''.join(cards)}</div>
            </section>"""
        )

    con.close()

    body = f"""<div class="head"><div><h1>Seans Durumu</h1><p>Tüm şubeler aynı ekranda ve otomatik güncellenir.</p></div><button class="btn" onclick="requestNoticePermission()">Bildirimleri Aç</button></div>
    <div class="grid" style="grid-template-columns:repeat({2 if len(branch_sections) > 1 else 1},minmax(0,1fr));align-items:start">
      {''.join(branch_sections)}
    </div>"""

    script = """
    <script>
    let notified={};
    function tickLive(){
      document.querySelectorAll(".liveTimer").forEach(el=>{
        const end=new Date(el.dataset.end);let ms=end-Date.now();
        if(ms<=0){
          el.textContent="BİTTİ";el.style.color="#dc2626";
          if(!notified[el.dataset.id]){
            notified[el.dataset.id]=true;beep();
            if("Notification"in window&&Notification.permission==="granted"){
              new Notification("ANKA",{body:"Bir seans tamamlandı."});
            }
            setTimeout(()=>location.reload(),2200);
          }
          return;
        }
        const m=Math.floor(ms/60000),s=Math.floor((ms%60000)/1000);
        el.textContent=String(m).padStart(2,"0")+":"+String(s).padStart(2,"0");
      });
    }
    async function pollAlerts(){
      try{
        const r=await fetch("/api/alerts");const d=await r.json();
        if(d.help_count>0 && !sessionStorage.getItem("help_"+d.help_key)){
          sessionStorage.setItem("help_"+d.help_key,"1");beep();
          if("Notification"in window&&Notification.permission==="granted"){
            new Notification("ANKA Yardım",{body:d.help_count+" seans yardım istiyor."});
          }
        }
      }catch(e){}
    }
    tickLive();
    setInterval(tickLive,1000);
    setInterval(pollAlerts,5000);
    </script>
    """
    return HTMLResponse(layout(request, "Seans Durumu", body, script))

@app.get("/api/alerts")
def alerts(request: Request):
    u = require(request, {"admin", "manager"})
    if not u:
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    finalize_due_sessions()
    con = db()
    if u["role"] == "manager":
        rows = con.execute("SELECT id FROM sessions WHERE branch_id=? AND status='active' AND help_requested=1", (u["branch_id"],)).fetchall()
    else:
        rows = con.execute("SELECT id FROM sessions WHERE status='active' AND help_requested=1").fetchall()
    con.close()
    key = "-".join(str(r["id"]) for r in rows)
    return {"help_count": len(rows), "help_key": key}

@app.post("/session/{sid}/extend")
def extend(request: Request, sid: int, minutes: int = Form(...), csrf_token: str = Form(..., alias="csrf")):
    if not require(request, {"admin", "manager"}) or not csrf_ok(request, csrf_token):
        return RedirectResponse("/live", 303)
    con = db()
    s = con.execute("SELECT * FROM sessions WHERE id=? AND status='active'", (sid,)).fetchone()
    if s:
        end = datetime.fromisoformat(s["ends_at"].replace("Z", "+00:00")) + timedelta(minutes=max(1, min(120, minutes)))
        con.execute("UPDATE sessions SET ends_at=? WHERE id=?", (iso_utc(end), sid))
        con.commit()
        audit(request, "extend", "session", sid, f"+{minutes} dk")
    con.close()
    return RedirectResponse("/live", 303)

@app.post("/session/{sid}/finish")
def finish(request: Request, sid: int, csrf_token: str = Form(..., alias="csrf")):
    if not require(request, {"admin", "manager"}) or not csrf_ok(request, csrf_token):
        return RedirectResponse("/live", 303)
    con = db()
    con.execute(
        "UPDATE sessions SET status='pending',completed_at=?,help_requested=0 WHERE id=? AND status='active'",
        (iso_utc(utc_now()), sid),
    )
    con.commit()
    con.close()
    audit(request, "finish", "session", sid, "Onaya düştü")
    flash(request, "Seans onaya düştü.")
    return RedirectResponse("/approvals", 303)

@app.post("/session/{sid}/cancel-decision")
def cancel_decision(
    request: Request,
    sid: int,
    decision: str = Form(...),
    pay_commission: int = Form(0),
    csrf_token: str = Form(..., alias="csrf"),
):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/approvals", 303)

    con = db()
    s = con.execute(
        """SELECT s.*,u.commission_rate
           FROM sessions s JOIN users u ON u.id=s.staff_id
           WHERE s.id=? AND s.status='cancel_requested'""",
        (sid,),
    ).fetchone()
    if not s:
        con.close()
        flash(request, "İptal talebi bulunamadı.", "error")
        return RedirectResponse("/approvals", 303)

    if u["role"] == "manager" and s["branch_id"] != u["branch_id"]:
        con.close()
        return RedirectResponse("/approvals", 303)

    now_text = iso_utc(utc_now())

    if decision == "approve":
        commission = 0
        if int(pay_commission) == 1:
            commission = int(
                (Decimal(s["amount_kurus"]) * Decimal(s["commission_rate"]) / 100)
                .quantize(Decimal("1"), rounding=ROUND_HALF_UP)
            )
        con.execute(
            """UPDATE sessions
               SET status='cancelled',
                   cancelled_at=?,
                   completed_at=?,
                   commission_kurus=?,
                   cancel_pay_commission=?,
                   cancel_decision_at=?,
                   cancel_decision_by=?,
                   help_requested=0
               WHERE id=?""",
            (now_text, now_text, commission, int(pay_commission), now_text, u["id"], sid),
        )
        message = "İptal onaylandı."
        audit(request, "cancel_approved", "session", sid, f"prime_yaz={int(pay_commission)}")
    else:
        # İptal reddedilirse aktif seansa geri döner; atanmış seanssa assigned'a döner.
        fallback_status = "active" if s["accepted_at"] else "assigned"
        con.execute(
            """UPDATE sessions
               SET status=?,
                   cancel_decision_at=?,
                   cancel_decision_by=?,
                   cancel_pay_commission=NULL
               WHERE id=?""",
            (fallback_status, now_text, u["id"], sid),
        )
        message = "İptal talebi reddedildi; seans devam ediyor."
        audit(request, "cancel_rejected", "session", sid, fallback_status)

    con.commit()
    con.close()
    flash(request, message)
    return RedirectResponse("/approvals", 303)

@app.post("/staff-deductions/set")
def staff_deductions_set(
    request: Request,
    branch_id: int = Form(...),
    staff_id: int = Form(...),
    day: str = Form(...),
    security: str = Form("0"),
    cleaning: str = Form("0"),
    meal: str = Form("0"),
    csrf_token: str = Form(..., alias="csrf"),
):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/day-end", 303)
    if u["role"] == "manager" and branch_id != u["branch_id"]:
        return RedirectResponse("/day-end", 303)
    if day_is_closed(branch_id, day):
        flash(request, "Kapalı güne kesinti eklenemez.", "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)

    def parse_zero(value):
        value = (value or "0").strip()
        if value in ("", "0", "0,00", "0.00"):
            return 0
        return to_kurus(value)

    try:
        values = {
            "security": parse_zero(security),
            "cleaning": parse_zero(cleaning),
            "meal": parse_zero(meal),
        }
    except ValueError as e:
        flash(request, str(e), "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)

    con = db()
    staff = con.execute(
        "SELECT 1 FROM users WHERE id=? AND role='staff' AND branch_id=?",
        (staff_id, branch_id),
    ).fetchone()
    if not staff:
        con.close()
        flash(request, "Personel bulunamadı.", "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)

    con.execute(
        "UPDATE staff_deductions SET active=0 WHERE branch_id=? AND staff_id=? AND deduction_date=?",
        (branch_id, staff_id, day),
    )
    for kind, amount_k in values.items():
        if amount_k > 0:
            con.execute(
                """INSERT INTO staff_deductions(
                   branch_id,staff_id,deduction_date,deduction_type,description,
                   amount_kurus,created_by,created_at,active
                   ) VALUES(?,?,?,?,?,?,?,?,1)""",
                (
                    branch_id,
                    staff_id,
                    day,
                    kind,
                    {"security":"Güvence","cleaning":"Temizlik","meal":"Yemek Parası"}[kind],
                    amount_k,
                    u["id"],
                    local_now_text(),
                ),
            )
    con.commit()
    con.close()
    audit(request, "set_deductions", "staff", staff_id, json.dumps(values))
    flash(request, "Personel kesintileri kaydedildi.")
    return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)





@app.get("/approvals", response_class=HTMLResponse)
def approvals(request: Request):
    u = require(request, {"admin", "manager"})
    if not u:
        return RedirectResponse("/login", 303)
    finalize_due_sessions()
    con = db()

    query = """SELECT s.*,u.full_name staff,b.name branch,sv.name service,r.name room
               FROM sessions s JOIN users u ON u.id=s.staff_id JOIN branches b ON b.id=s.branch_id
               JOIN services sv ON sv.id=s.service_id JOIN rooms r ON r.id=s.room_id
               WHERE s.status IN('pending','cancel_requested')"""
    args = []
    if u["role"] == "manager":
        query += " AND s.branch_id=?"
        args.append(u["branch_id"])
    query += " ORDER BY s.id"
    rows = con.execute(query, args).fetchall()
    con.close()

    items = ""
    for r in rows:
        if r["status"] == "cancel_requested":
            items += f"""<article class="approval"><div><span class="badge rejected">İptal Talebi</span><h3>{r['staff']}</h3>
            <p>{r['branch']} • {r['room']} • {r['service']}</p><p><strong>Sebep:</strong> {r['cancel_reason'] or '—'}</p></div>
            <div class="amount">{money(r['amount_kurus'])}</div>
            <form method="post" action="/session/{r['id']}/cancel-decision" class="form">
              <input type="hidden" name="csrf" value="{csrf(request)}">
              <label>Prime Yazılsın mı?<select name="pay_commission" required><option value="0">Hayır</option><option value="1">Evet</option></select></label>
              <button class="btn red" name="decision" value="approve">İptali Onayla</button>
              <button class="btn" name="decision" value="reject">İptali Reddet</button>
            </form></article>"""
        else:
            items += f"""<article class="approval"><div><span class="badge pending">Onay Bekliyor</span><h3>{r['staff']}</h3><p>{r['branch']} • {r['room']} • {r['service']}</p><p><strong>Ödeme:</strong> {PAYMENT.get(r['payment_method'],'—')}</p></div>
            <div class="amount">{money(r['amount_kurus'])}</div><form method="post" action="/session/{r['id']}/approve">
            <input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn green">Onayla</button></form></article>"""

    if not items:
        items = "<section class='card'><h2>Onay bekleyen işlem yok</h2></section>"
    return HTMLResponse(layout(request, "Onaylar", f"<div class='head'><div><h1>Onay Bekleyenler</h1></div></div>{items}"))

@app.post("/session/{sid}/approve")
def approve(request: Request, sid: int, csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/approvals", 303)
    con = db()
    s = con.execute(
        """SELECT s.*,u.commission_rate FROM sessions s JOIN users u ON u.id=s.staff_id
           WHERE s.id=? AND s.status='pending'""",
        (sid,),
    ).fetchone()
    if s:
        commission = int((Decimal(s["amount_kurus"]) * Decimal(s["commission_rate"]) / 100).quantize(Decimal("1"), rounding=ROUND_HALF_UP))
        con.execute(
            "UPDATE sessions SET status='approved',commission_kurus=?,approved_at=?,approved_by=? WHERE id=?",
            (commission, iso_utc(utc_now()), u["id"], sid),
        )
        con.commit()
        audit(request, "approve", "session", sid, s["payment_method"] or "")
    con.close()
    flash(request, "İşlem onaylandı.")
    return RedirectResponse("/approvals", 303)

@app.get("/settings", response_class=HTMLResponse)
def settings(request: Request):
    u = require(request, {"admin", "manager"})
    if not u:
        return RedirectResponse("/login", 303)
    con = db()
    branches = con.execute("SELECT * FROM branches WHERE active=1 ORDER BY name").fetchall()
    if u["role"] == "manager":
        branches = [b for b in branches if b["id"] == u["branch_id"]]
    branch_ids = [b["id"] for b in branches]
    rooms = con.execute(
        """SELECT r.*,b.name branch FROM rooms r JOIN branches b ON b.id=r.branch_id
           WHERE r.branch_id IN ({}) ORDER BY b.name,r.name""".format(",".join("?" * len(branch_ids))),
        branch_ids,
    ).fetchall() if branch_ids else []
    services = con.execute("SELECT * FROM services ORDER BY name").fetchall()
    con.close()

    branch_options = "".join(f"<option value='{b['id']}'>{b['name']}</option>" for b in branches)
    room_rows = "".join(
        f"""<div class="settings-row"><form method="post" action="/settings/room/{r['id']}/edit"><input type="hidden" name="csrf" value="{csrf(request)}">
        <input name="name" value="{r['name']}" required><input value="{r['branch']}" disabled><button class="btn">Düzenle</button></form>
        <form method="post" action="/settings/room/{r['id']}/toggle"><input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn {'red' if r['active'] else 'green'}">{'Sil/Pasifleştir' if r['active'] else 'Aktifleştir'}</button></form></div>"""
        for r in rooms
    )
    service_rows = "".join(
        f"""<div class="settings-row"><form method="post" action="/settings/service/{s['id']}/edit"><input type="hidden" name="csrf" value="{csrf(request)}">
        <input name="name" value="{s['name']}" required><input type="number" name="duration" value="{s['duration_minutes']}" min="5" max="240" required><button class="btn">Düzenle</button></form>
        <form method="post" action="/settings/service/{s['id']}/toggle"><input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn {'red' if s['active'] else 'green'}">{'Sil/Pasifleştir' if s['active'] else 'Aktifleştir'}</button></form></div>"""
        for s in services
    )
    body = f"""<div class="head"><div><h1>Ayarlar</h1><p>Oda ve seans türlerini ekle, düzenle veya pasifleştir.</p></div></div><div class="grid">
    <section class="card"><h2>Odalar</h2><form method="post" action="/settings/room" class="form"><input type="hidden" name="csrf" value="{csrf(request)}"><label>Şube<select name="branch_id">{branch_options}</select></label><label>Oda adı<input name="name" required></label><button class="btn primary">Oda Ekle</button></form><hr>{room_rows}</section>
    <section class="card"><h2>Seans Türleri</h2><form method="post" action="/settings/service" class="form"><input type="hidden" name="csrf" value="{csrf(request)}"><label>Ad<input name="name" required></label><label>Süre (dk)<input type="number" name="duration" min="5" max="240" required></label><button class="btn primary">Seans Türü Ekle</button></form><hr>{service_rows}</section></div>"""
    return HTMLResponse(layout(request, "Ayarlar", body))

@app.post("/settings/room")
def add_room(request: Request, branch_id: int = Form(...), name: str = Form(...), csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/settings", 303)
    if u["role"] == "manager" and branch_id != u["branch_id"]:
        return RedirectResponse("/settings", 303)
    con = db()
    try:
        con.execute("INSERT INTO rooms(branch_id,name) VALUES(?,?)", (branch_id, name.strip()))
        con.commit()
        flash(request, "Oda eklendi.")
    except sqlite3.IntegrityError:
        flash(request, "Bu oda zaten var.", "error")
    con.close()
    return RedirectResponse("/settings", 303)

@app.post("/settings/room/{rid}/edit")
def edit_room(request: Request, rid: int, name: str = Form(...), csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/settings", 303)
    con = db()
    room = con.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
    if room and (u["role"] == "admin" or room["branch_id"] == u["branch_id"]):
        con.execute("UPDATE rooms SET name=? WHERE id=?", (name.strip(), rid))
        con.commit()
        audit(request, "edit", "room", rid, name)
    con.close()
    return RedirectResponse("/settings", 303)

@app.post("/settings/room/{rid}/toggle")
def toggle_room(request: Request, rid: int, csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/settings", 303)
    con = db()
    room = con.execute("SELECT * FROM rooms WHERE id=?", (rid,)).fetchone()
    if room and (u["role"] == "admin" or room["branch_id"] == u["branch_id"]):
        new_state = 0 if room["active"] else 1
        con.execute("UPDATE rooms SET active=? WHERE id=?", (new_state, rid))
        con.commit()
        audit(request, "toggle", "room", rid, str(new_state))
    con.close()
    return RedirectResponse("/settings", 303)

@app.post("/settings/service")
def add_service(request: Request, name: str = Form(...), duration: int = Form(...), csrf_token: str = Form(..., alias="csrf")):
    if not require(request, {"admin", "manager"}) or not csrf_ok(request, csrf_token):
        return RedirectResponse("/settings", 303)
    con = db()
    try:
        con.execute("INSERT INTO services(name,duration_minutes) VALUES(?,?)", (name.strip(), max(5, min(240, duration))))
        con.commit()
        flash(request, "Seans türü eklendi.")
    except sqlite3.IntegrityError:
        flash(request, "Bu seans türü zaten var.", "error")
    con.close()
    return RedirectResponse("/settings", 303)

@app.post("/settings/service/{sid}/edit")
def edit_service(request: Request, sid: int, name: str = Form(...), duration: int = Form(...), csrf_token: str = Form(..., alias="csrf")):
    if not require(request, {"admin", "manager"}) or not csrf_ok(request, csrf_token):
        return RedirectResponse("/settings", 303)
    con = db()
    con.execute("UPDATE services SET name=?,duration_minutes=? WHERE id=?", (name.strip(), max(5, min(240, duration)), sid))
    con.commit()
    con.close()
    audit(request, "edit", "service", sid, f"{name}/{duration}")
    return RedirectResponse("/settings", 303)

@app.post("/settings/service/{sid}/toggle")
def toggle_service(request: Request, sid: int, csrf_token: str = Form(..., alias="csrf")):
    if not require(request, {"admin", "manager"}) or not csrf_ok(request, csrf_token):
        return RedirectResponse("/settings", 303)
    con = db()
    row = con.execute("SELECT active FROM services WHERE id=?", (sid,)).fetchone()
    if row:
        state = 0 if row["active"] else 1
        con.execute("UPDATE services SET active=? WHERE id=?", (state, sid))
        con.commit()
        audit(request, "toggle", "service", sid, str(state))
    con.close()
    return RedirectResponse("/settings", 303)

@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request):
    if not require(request, {"admin"}):
        return RedirectResponse("/login", 303)
    con = db()
    branches = con.execute("SELECT * FROM branches WHERE active=1 ORDER BY name").fetchall()
    users = con.execute("SELECT u.*,b.name branch FROM users u LEFT JOIN branches b ON b.id=u.branch_id ORDER BY u.active DESC,u.role,u.full_name").fetchall()
    con.close()
    branch_options = '<option value="">Şubesiz</option>' + "".join(f"<option value='{b['id']}'>{b['name']}</option>" for b in branches)
    cards = ""
    for x in users:
        edit_branches = '<option value="">Şubesiz</option>' + "".join(
            f"<option value='{b['id']}' {'selected' if x['branch_id']==b['id'] else ''}>{b['name']}</option>" for b in branches
        )
        cards += f"""<section class="card"><h3>{x['full_name']} <span class="badge {'approved' if x['active'] else 'cancelled'}">{'Aktif' if x['active'] else 'Pasif'}</span></h3>
        <p>@{x['username']} • {ROLE[x['role']]} • {x['branch'] or 'Tüm şubeler'}</p><p class="muted">Son giriş: {x['last_login_at'] or 'Henüz giriş yapmadı'}</p>
        <form method="post" action="/users/{x['id']}/edit" class="form"><input type="hidden" name="csrf" value="{csrf(request)}">
        <label>Ad Soyad<input name="full_name" value="{x['full_name']}" required></label>
        <label>Rol<select name="role"><option value="staff" {'selected' if x['role']=='staff' else ''}>Personel</option><option value="manager" {'selected' if x['role']=='manager' else ''}>Müdür</option><option value="admin" {'selected' if x['role']=='admin' else ''}>Yönetici</option></select></label>
        <label>Şube<select name="branch_id">{edit_branches}</select></label><label>Prim %<input type="number" name="commission" value="{x['commission_rate']}" min="0" max="100"></label>
        <button class="btn">Bilgileri Güncelle</button></form>
        <div class="inline" style="margin-top:10px"><form method="post" action="/users/{x['id']}/toggle"><input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn {'red' if x['active'] else 'green'}">{'Pasifleştir' if x['active'] else 'Aktifleştir'}</button></form>
        <form method="post" action="/users/{x['id']}/password" class="inline"><input type="hidden" name="csrf" value="{csrf(request)}"><input type="password" name="password" minlength="8" placeholder="Yeni şifre" required><button class="btn">Şifreyi Sıfırla</button></form></div></section>"""
    body = f"""<div class="head"><div><h1>Kullanıcılar</h1><p>Düzenleme, pasifleştirme ve şifre sıfırlama</p></div></div>
    <div class="grid"><section class="card"><h2>Yeni Kullanıcı</h2><form method="post" class="form"><input type="hidden" name="csrf" value="{csrf(request)}">
    <label>Ad Soyad<input name="full_name" required></label><label>Kullanıcı adı<input name="username" required></label>
    <label>Rol<select name="role"><option value="staff">Personel</option><option value="manager">Müdür</option><option value="admin">Yönetici</option></select></label>
    <label>Şube<select name="branch_id">{branch_options}</select></label><label>Prim %<input type="number" name="commission" value="30"></label>
    <label>Geçici şifre<input type="password" name="password" minlength="8" required></label><button class="btn primary">Oluştur</button></form></section>
    <section style="display:grid;gap:12px">{cards}</section></div>"""
    return HTMLResponse(layout(request, "Kullanıcılar", body))

@app.post("/users")
def create_user(
    request: Request,
    full_name: str = Form(...),
    username: str = Form(...),
    role: str = Form(...),
    branch_id: Optional[int] = Form(None),
    commission: int = Form(30),
    password: str = Form(...),
    csrf_token: str = Form(..., alias="csrf"),
):
    if not require(request, {"admin"}) or not csrf_ok(request, csrf_token):
        return RedirectResponse("/users", 303)
    con = db()
    try:
        con.execute(
            """INSERT INTO users(username,full_name,password_hash,role,branch_id,commission_rate,active,created_at)
               VALUES(?,?,?,?,?,?,1,?)""",
            (username.strip(), full_name.strip(), hash_password(password), role, branch_id, max(0, min(100, commission)), local_now_text()),
        )
        con.commit()
        flash(request, "Kullanıcı oluşturuldu.")
    except sqlite3.IntegrityError:
        flash(request, "Kullanıcı adı kullanılıyor.", "error")
    con.close()
    return RedirectResponse("/users", 303)

@app.get('/day-end',response_class=HTMLResponse)
def day_end_page(request:Request,branch_id:Optional[int]=None,day:Optional[str]=None):
    u=require(request,{'admin','manager'})
    if not u:return RedirectResponse('/login',303)
    day=day or business_date(); con=db(); branches=con.execute("SELECT * FROM branches WHERE active=1 ORDER BY name").fetchall()
    if u['role']=='manager': branch_id=u['branch_id']; branches=[b for b in branches if b['id']==u['branch_id']]
    if not branch_id and branches: branch_id=branches[0]['id']
    staff=con.execute("SELECT id,full_name FROM users WHERE role='staff' AND active=1 AND branch_id=? ORDER BY full_name",(branch_id,)).fetchall()
    sessions=con.execute("""SELECT s.*,u.full_name staff,sv.name service,r.name room FROM sessions s JOIN users u ON u.id=s.staff_id JOIN services sv ON sv.id=s.service_id JOIN rooms r ON r.id=s.room_id WHERE s.branch_id=? AND s.business_date=? ORDER BY u.full_name,s.id""",(branch_id,day)).fetchall()
    deductions=con.execute("SELECT * FROM staff_deductions WHERE branch_id=? AND deduction_date=? AND active=1",(branch_id,day)).fetchall()
    expenses=con.execute("SELECT e.*,u.full_name creator FROM expenses e JOIN users u ON u.id=e.created_by WHERE e.branch_id=? AND e.expense_date=? AND e.active=1 ORDER BY e.id DESC",(branch_id,day)).fetchall(); con.close()
    snap=finance_snapshot(branch_id,day)
    bs={x['id']:[] for x in staff}; bd={x['id']:[] for x in staff}
    for x in sessions: bs.setdefault(x['staff_id'],[]).append(x)
    for x in deductions: bd.setdefault(x['staff_id'],[]).append(x)
    def clock(v):
        if not v:return '—'
        try:return datetime.fromisoformat(v.replace('Z','+00:00')).astimezone(TR).strftime('%H:%M')
        except:return '—'
    cols=''
    for person in staff:
        items=bs.get(person['id'],[]); d=bd.get(person['id'],[]); gross=sum(x['commission_kurus'] for x in items if x['status']=='approved')
        security=sum(x['amount_kurus'] for x in d if x['deduction_type']=='security'); cleaning=sum(x['amount_kurus'] for x in d if x['deduction_type']=='cleaning'); meal=sum(x['amount_kurus'] for x in d if x['deduction_type']=='meal'); net=max(gross-security-cleaning-meal,0)
        rows=''
        for x in items:
            prim_html = f"<div>Prim: {money(x['commission_kurus'])}</div>" if x['status']=='approved' else ''
            rows += f"<div style='padding:10px 0;border-bottom:1px solid var(--line)'><strong>{x['service']}</strong> - {money(x['amount_kurus'])}<br><small>{x['room']} • {clock(x['started_at'])}-{clock(x['completed_at'] or x['cancelled_at'])} • {PAYMENT.get(x['payment_method'],'—')}</small><br><span class='badge {x['status']}'>{STATUS.get(x['status'],x['status'])}</span>{prim_html}</div>"
        rows = rows or "<p class='muted'>Seans yok.</p>"
        cols+=f"""<section class='card' style='min-width:310px'><h2>{person['full_name']}</h2>{rows}<hr><p><strong>Brüt Prim:</strong> {money(gross)}</p><form method='post' action='/staff-deductions/set' class='form'><input type='hidden' name='csrf' value='{csrf(request)}'><input type='hidden' name='branch_id' value='{branch_id}'><input type='hidden' name='staff_id' value='{person['id']}'><input type='hidden' name='day' value='{day}'><label>Güvence<input name='security' value='{security/100:.2f}'></label><label>Temizlik<input name='cleaning' value='{cleaning/100:.2f}'></label><label>Yemek<input name='meal' value='{meal/100:.2f}'></label><button class='btn'>Kaydet</button></form><p style='font-size:21px'><strong>Net Ödenecek:</strong> {money(net)}</p></section>"""
    exp_rows=''.join(f"<tr><td>{e['description']}</td><td>{money(e['amount_kurus'])}</td><td>{e['creator']}</td></tr>" for e in expenses) or "<tr><td colspan='3'>Masraf yok.</td></tr>"
    opts=''.join(f"<option value='{b['id']}' {'selected' if b['id']==branch_id else ''}>{b['name']}</option>" for b in branches)
    body=f"""<div class='head'><div><h1>Gün Sonu</h1><p>Finans hesabı test modu - gün kilidi henüz kapalı</p></div><form method='get' class='inline'><select name='branch_id'>{opts}</select><input type='date' name='day' value='{day}'><button class='btn'>Göster</button><a class='btn' href='/day-end/pdf?branch_id={branch_id}&day={day}'>PDF</a><a class='btn' href='/day-end/excel?branch_id={branch_id}&day={day}'>Excel</a></form></div>
    <div class='stats'><div class='stat'><small>Ciro</small><strong>{money(snap['revenue'])}</strong></div><div class='stat'><small>Net Personel Ödemesi</small><strong>{money(snap['net_staff'])}</strong></div><div class='stat'><small>Güvenceye Ayrılan</small><strong>{money(snap['security'])}</strong></div><div class='stat'><small>Yemek Geri Kasa</small><strong>{money(snap['meal'])}</strong></div><div class='stat'><small>{snap['cleaner']} Ücreti</small><strong>{money(snap['wage'])}</strong></div><div class='stat'><small>Temizlik Kesintisi</small><strong>{money(snap['cleaning'])}</strong></div><div class='stat warn'><small>Kasadan Temizlik Desteği</small><strong>{money(snap['cleaning_subsidy'])}</strong></div><div class='stat warn'><small>İşletme Masrafı</small><strong>{money(snap['expenses'])}</strong></div><div class='stat'><small>İşletmeye Kalan</small><strong>{money(snap['business_net'])}</strong></div></div>
    <section class='card' style='margin-bottom:18px'><h2>Temizlik Fonu</h2><div class='stats'><div class='stat'><small>Devreden</small><strong>{money(snap['opening_cleaning'])}</strong></div><div class='stat'><small>Bugün Kesilen</small><strong>{money(snap['cleaning'])}</strong></div><div class='stat'><small>Kasadan Verilen</small><strong>{money(snap['cleaning_subsidy'])}</strong></div><div class='stat'><small>Devreden Bakiye</small><strong>{money(snap['closing_cleaning'])}</strong></div></div></section>
    <div style='display:flex;gap:14px;overflow-x:auto;padding-bottom:10px'>{cols or "<section class='card'>Personel yok.</section>"}</div>
    <div class='grid' style='margin-top:18px'><section class='card'><h2>İşletme Masrafları</h2><form method='post' action='/expenses/new' class='form'><input type='hidden' name='csrf' value='{csrf(request)}'><input type='hidden' name='branch_id' value='{branch_id}'><input type='hidden' name='day' value='{day}'><label>Açıklama<input name='description' required></label><label>Tutar<input name='amount' required></label><button class='btn primary'>Masraf Ekle</button></form><div class='table'><table><tr><th>Açıklama</th><th>Tutar</th><th>Ekleyen</th></tr>{exp_rows}</table></div></section><section class='card'><h2>Test Modu</h2><p>Hesaplar gerçek verilerle deneniyor. Gün kilitleme, hesap yapısı kesinleşince açılacak.</p><a class='btn primary' href='/finance?branch_id={branch_id}&day={day}'>Finans Merkezini Aç</a></section></div>"""
    return HTMLResponse(layout(request,'Gün Sonu',body))

@app.post("/expenses/new")
def expense_new(request: Request, branch_id: int = Form(...), day: str = Form(...), description: str = Form(...), amount: str = Form(...), csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/day-end", 303)
    if u["role"] == "manager" and branch_id != u["branch_id"]:
        return RedirectResponse("/day-end", 303)
    if day_is_closed(branch_id, day):
        flash(request, "Kapalı güne masraf eklenemez.", "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)
    try:
        amount_k = to_kurus(amount)
    except ValueError as e:
        flash(request, str(e), "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)
    con = db()
    cur = con.execute(
        "INSERT INTO expenses(branch_id,description,amount_kurus,expense_date,created_by,created_at) VALUES(?,?,?,?,?,?)",
        (branch_id, description.strip()[:300], amount_k, day, u["id"], local_now_text()),
    )
    con.commit()
    eid = cur.lastrowid
    con.close()
    audit(request, "create", "expense", eid, f"{description}/{amount_k}")
    flash(request, "Masraf eklendi.")
    return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)

@app.post("/staff-deductions/new")
def staff_deduction_new(
    request: Request,
    branch_id: int = Form(...),
    staff_id: int = Form(...),
    day: str = Form(...),
    deduction_type: str = Form(...),
    description: str = Form(""),
    amount: str = Form(...),
    csrf_token: str = Form(..., alias="csrf"),
):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/day-end", 303)
    if deduction_type not in {"meal", "cleaning", "custom"}:
        flash(request, "Kesinti türü geçersiz.", "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)
    if u["role"] == "manager" and branch_id != u["branch_id"]:
        return RedirectResponse("/day-end", 303)
    if day_is_closed(branch_id, day):
        flash(request, "Kapalı güne kesinti eklenemez.", "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)
    try:
        amount_k = to_kurus(amount)
    except ValueError as e:
        flash(request, str(e), "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)
    con = db()
    staff = con.execute("SELECT 1 FROM users WHERE id=? AND role='staff' AND branch_id=?", (staff_id, branch_id)).fetchone()
    if not staff:
        con.close()
        flash(request, "Personel bulunamadı.", "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)
    cur = con.execute(
        """INSERT INTO staff_deductions(branch_id,staff_id,deduction_date,deduction_type,description,amount_kurus,created_by,created_at)
           VALUES(?,?,?,?,?,?,?,?)""",
        (branch_id, staff_id, day, deduction_type, description.strip()[:300], amount_k, u["id"], local_now_text()),
    )
    con.commit()
    did = cur.lastrowid
    con.close()
    audit(request, "create", "staff_deduction", did, f"{staff_id}/{deduction_type}/{amount_k}")
    flash(request, "Personel kesintisi eklendi.")
    return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)
@app.post('/day-end/close')
def day_end_close(request:Request,branch_id:int=Form(...),day:str=Form(...),csrf_token:str=Form(...,alias='csrf'),**kwargs):
    if not require(request,{'admin','manager'}):return RedirectResponse('/login',303)
    flash(request,'Gün kilitleme test süresince kapalı. Finans hesabı kesinleşince açılacak.','error')
    return RedirectResponse(f'/day-end?branch_id={branch_id}&day={day}',303)

@app.post("/day-end/reopen")
def day_end_reopen(request: Request, branch_id: int = Form(...), day: str = Form(...), reason: str = Form(...), csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"admin"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/day-end", 303)
    con = db()
    con.execute(
        "UPDATE day_closings SET reopened_at=?,reopened_by=?,reopen_reason=? WHERE branch_id=? AND business_date=?",
        (local_now_text(), u["id"], reason[:500], branch_id, day),
    )
    con.commit()
    con.close()
    audit(request, "reopen_day", "day", f"{branch_id}:{day}", reason)
    flash(request, "Gün yeniden açıldı.")
    return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)

@app.get('/finance',response_class=HTMLResponse)
def finance_center(request:Request,branch_id:Optional[int]=None,day:Optional[str]=None):
    u=require(request,{'admin','manager'})
    if not u:return RedirectResponse('/login',303)
    day=day or business_date(); con=db(); branches=con.execute("SELECT * FROM branches WHERE active=1 ORDER BY name").fetchall()
    if u['role']=='manager': branch_id=u['branch_id']; branches=[b for b in branches if b['id']==u['branch_id']]
    if not branch_id and branches: branch_id=branches[0]['id']
    settings=con.execute("SELECT * FROM finance_settings WHERE branch_id=?",(branch_id,)).fetchone(); adjustments=con.execute("SELECT f.*,u.full_name creator FROM fund_adjustments f JOIN users u ON u.id=f.created_by WHERE f.branch_id=? ORDER BY f.id DESC LIMIT 30",(branch_id,)).fetchall(); con.close()
    snap=finance_snapshot(branch_id,day); opts=''.join(f"<option value='{b['id']}' {'selected' if b['id']==branch_id else ''}>{b['name']}</option>" for b in branches)
    adj=''.join(f"<tr><td>{x['adjustment_date']}</td><td>{'Güvence' if x['fund_type']=='security' else 'Temizlik'}</td><td>{money(x['amount_kurus'])}</td><td>{x['description']}</td><td>{x['creator']}</td></tr>" for x in adjustments) or "<tr><td colspan='5'>Hareket yok.</td></tr>"
    body=f"""<div class='head'><div><h1>ANKA Finans Merkezi</h1><p>Fonlar, temizlik ücreti ve işletme neti</p></div><form method='get' class='inline'><select name='branch_id'>{opts}</select><input type='date' name='day' value='{day}'><button class='btn'>Göster</button></form></div><div class='stats'><div class='stat'><small>Güvence Fonu</small><strong>{money(snap['security_balance'])}</strong></div><div class='stat'><small>Temizlik Devreden</small><strong>{money(snap['closing_cleaning'])}</strong></div><div class='stat'><small>Kasadan Temizlik</small><strong>{money(snap['cleaning_subsidy'])}</strong></div><div class='stat'><small>İşletmeye Kalan</small><strong>{money(snap['business_net'])}</strong></div></div><div class='grid'><section class='card'><h2>Temizlik Ayarı</h2><form method='post' action='/finance/settings' class='form'><input type='hidden' name='csrf' value='{csrf(request)}'><input type='hidden' name='branch_id' value='{branch_id}'><label>Temizlik Personeli<input name='cleaner_name' value='{settings['cleaner_name'] if settings else 'Melis'}'></label><label>Günlük Ücret<input name='wage' value='{(settings['cleaning_daily_wage_kurus'] if settings else 175000)/100:.2f}'></label><button class='btn primary'>Kaydet</button></form></section><section class='card'><h2>Fon Hareketi</h2><form method='post' action='/finance/adjustment' class='form'><input type='hidden' name='csrf' value='{csrf(request)}'><input type='hidden' name='branch_id' value='{branch_id}'><input type='hidden' name='day' value='{day}'><label>Fon<select name='fund_type'><option value='security'>Güvence</option><option value='cleaning'>Temizlik</option></select></label><label>Tutar (+ giriş / - çıkış)<input name='amount' placeholder='-7200 veya 500'></label><label>Açıklama<input name='description' required></label><button class='btn'>Hareket Ekle</button></form></section></div><section class='card' style='margin-top:18px'><h2>Son Fon Hareketleri</h2><div class='table'><table><tr><th>Tarih</th><th>Fon</th><th>Tutar</th><th>Açıklama</th><th>Ekleyen</th></tr>{adj}</table></div></section>"""
    return HTMLResponse(layout(request,'Finans Merkezi',body))

@app.post('/finance/settings')
def finance_settings_save(request:Request,branch_id:int=Form(...),cleaner_name:str=Form(...),wage:str=Form(...),csrf_token:str=Form(...,alias='csrf')):
    u=require(request,{'admin','manager'})
    if not u or not csrf_ok(request,csrf_token):return RedirectResponse('/finance',303)
    if u['role']=='manager' and branch_id!=u['branch_id']:return RedirectResponse('/finance',303)
    try:w=to_kurus(wage)
    except ValueError as e:flash(request,str(e),'error');return RedirectResponse(f'/finance?branch_id={branch_id}',303)
    con=db();con.execute("INSERT INTO finance_settings(branch_id,cleaner_name,cleaning_daily_wage_kurus,updated_at,updated_by) VALUES(?,?,?,?,?) ON CONFLICT(branch_id) DO UPDATE SET cleaner_name=excluded.cleaner_name,cleaning_daily_wage_kurus=excluded.cleaning_daily_wage_kurus,updated_at=excluded.updated_at,updated_by=excluded.updated_by",(branch_id,cleaner_name.strip(),w,local_now_text(),u['id']));con.commit();con.close();audit(request,'finance_settings','branch',branch_id,f'{cleaner_name}/{w}');flash(request,'Finans ayarı güncellendi.');return RedirectResponse(f'/finance?branch_id={branch_id}',303)

@app.post('/finance/adjustment')
def finance_adjustment(request:Request,branch_id:int=Form(...),day:str=Form(...),fund_type:str=Form(...),amount:str=Form(...),description:str=Form(...),csrf_token:str=Form(...,alias='csrf')):
    u=require(request,{'admin','manager'})
    if not u or not csrf_ok(request,csrf_token):return RedirectResponse('/finance',303)
    if fund_type not in {'security','cleaning'}:return RedirectResponse('/finance',303)
    try:
        raw=amount.strip().replace('.','').replace(',','.'); val=int((Decimal(raw)*100).quantize(Decimal('1'),rounding=ROUND_HALF_UP))
    except:flash(request,'Geçerli tutar girin.','error');return RedirectResponse(f'/finance?branch_id={branch_id}&day={day}',303)
    con=db();con.execute("INSERT INTO fund_adjustments(branch_id,fund_type,adjustment_date,amount_kurus,description,created_by,created_at) VALUES(?,?,?,?,?,?,?)",(branch_id,fund_type,day,val,description[:300],u['id'],local_now_text()));con.commit();con.close();audit(request,'fund_adjustment',fund_type,branch_id,f'{val}/{description}');flash(request,'Fon hareketi eklendi.');return RedirectResponse(f'/finance?branch_id={branch_id}&day={day}',303)

@app.get('/daily-summary',response_class=HTMLResponse)
def daily_summary(request:Request,day:Optional[str]=None):
    if not require(request,{'admin'}):return RedirectResponse('/login',303)
    day=day or business_date();con=db();branches=con.execute("SELECT * FROM branches WHERE active=1 ORDER BY name").fetchall();con.close();cards='';agg={k:0 for k in ['revenue','net_staff','security','meal','cleaning_subsidy','expenses','business_net']}
    for b in branches:
        s=finance_snapshot(b['id'],day)
        for k in agg:agg[k]+=s[k]
        cards+=f"<section class='card'><h2>{b['name']}</h2><p>Ciro: <strong>{money(s['revenue'])}</strong></p><p>Personel: {money(s['net_staff'])}</p><p>Güvence: {money(s['security'])}</p><p>{s['cleaner']}: {money(s['wage'])} (kasadan {money(s['cleaning_subsidy'])})</p><p>Masraf: {money(s['expenses'])}</p><p style='font-size:20px'><strong>Kalan: {money(s['business_net'])}</strong></p></section>"
    body=f"<div class='head'><div><h1>Yönetici Günlük Özeti</h1><p>{day}</p></div><form method='get'><input type='date' name='day' value='{day}' onchange='this.form.submit()'></form></div><div class='stats'><div class='stat'><small>Toplam Ciro</small><strong>{money(agg['revenue'])}</strong></div><div class='stat'><small>Personel Ödemesi</small><strong>{money(agg['net_staff'])}</strong></div><div class='stat'><small>Güvence</small><strong>{money(agg['security'])}</strong></div><div class='stat'><small>Temizlik Desteği</small><strong>{money(agg['cleaning_subsidy'])}</strong></div><div class='stat warn'><small>Masraflar</small><strong>{money(agg['expenses'])}</strong></div><div class='stat'><small>İşletmeye Kalan</small><strong>{money(agg['business_net'])}</strong></div></div><div class='branch-grid'>{cards}</div>"
    return HTMLResponse(layout(request,'Günlük Özet',body))

@app.get('/day-end/pdf')
def day_end_pdf(request:Request,branch_id:int,day:str):
    u=require(request,{'admin','manager'})
    if not u:return RedirectResponse('/login',303)
    from reportlab.lib.pagesizes import A4
    from reportlab.pdfgen import canvas
    from reportlab.pdfbase import pdfmetrics
    from reportlab.pdfbase.ttfonts import TTFont
    snap=finance_snapshot(branch_id,day);con=db();branch=con.execute("SELECT name FROM branches WHERE id=?",(branch_id,)).fetchone();con.close();buf=io.BytesIO();font='Helvetica'
    for fp in ['/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf','/usr/share/fonts/dejavu/DejaVuSans.ttf']:
        if Path(fp).exists():pdfmetrics.registerFont(TTFont('DejaVu',fp));font='DejaVu';break
    c=canvas.Canvas(buf,pagesize=A4);c.setFont(font,18);c.drawString(45,800,'ANKA Gün Sonu Raporu');c.setFont(font,11);y=770
    rows=[('Şube',branch['name'] if branch else ''),('Tarih',day),('Ciro',money(snap['revenue'])),('Net personel ödemesi',money(snap['net_staff'])),('Güvence',money(snap['security'])),('Yemek geri kasa',money(snap['meal'])),(f"{snap['cleaner']} ücreti",money(snap['wage'])),('Temizlik kesintisi',money(snap['cleaning'])),('Kasadan temizlik desteği',money(snap['cleaning_subsidy'])),('İşletme masrafı',money(snap['expenses'])),('İşletmeye kalan',money(snap['business_net']))]
    for a,b in rows:c.drawString(45,y,str(a));c.drawRightString(550,y,str(b));y-=27
    c.save();buf.seek(0);return StreamingResponse(buf,media_type='application/pdf',headers={'Content-Disposition':f'attachment; filename="anka_gunsonu_{day}.pdf"'})

@app.get('/day-end/excel')
def day_end_excel(request:Request,branch_id:int,day:str):
    u=require(request,{'admin','manager'})
    if not u:return RedirectResponse('/login',303)
    import xlsxwriter
    snap=finance_snapshot(branch_id,day);con=db();branch=con.execute("SELECT name FROM branches WHERE id=?",(branch_id,)).fetchone();rows=con.execute("""SELECT u.full_name,sv.name,s.amount_kurus,s.commission_kurus,s.payment_method,s.status FROM sessions s JOIN users u ON u.id=s.staff_id JOIN services sv ON sv.id=s.service_id WHERE s.branch_id=? AND s.business_date=? ORDER BY u.full_name,s.id""",(branch_id,day)).fetchall();con.close();buf=io.BytesIO();wb=xlsxwriter.Workbook(buf,{'in_memory':True});ws=wb.add_worksheet('Gün Sonu');head=wb.add_format({'bold':True,'bg_color':'#0B1220','font_color':'#FFFFFF'});moneyfmt=wb.add_format({'num_format':'#,##0.00 "₺"'});ws.write_row('A1',['ANKA Gün Sonu',branch['name'] if branch else '',day],head);summary=[('Ciro',snap['revenue']),('Net Personel',snap['net_staff']),('Güvence',snap['security']),('Yemek',snap['meal']),('Temizlik Ücreti',snap['wage']),('Temizlik Desteği',snap['cleaning_subsidy']),('Masraf',snap['expenses']),('İşletmeye Kalan',snap['business_net'])]
    for i,(a,v) in enumerate(summary,3):ws.write(i-1,0,a);ws.write_number(i-1,1,v/100,moneyfmt)
    start=13;ws.write_row(start,0,['Personel','Seans','Tutar','Prim','Ödeme','Durum'],head)
    for j,r in enumerate(rows,start+1):ws.write(j,0,r['full_name']);ws.write(j,1,r['name']);ws.write_number(j,2,r['amount_kurus']/100,moneyfmt);ws.write_number(j,3,r['commission_kurus']/100,moneyfmt);ws.write(j,4,PAYMENT.get(r['payment_method'],''));ws.write(j,5,STATUS.get(r['status'],r['status']))
    ws.set_column('A:B',24);ws.set_column('C:F',16);wb.close();buf.seek(0);return StreamingResponse(buf,media_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',headers={'Content-Disposition':f'attachment; filename="anka_gunsonu_{day}.xlsx"'})

@app.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request, period: str = "week", anchor: Optional[str] = None, branch_id: Optional[int] = None):
    u = require(request, {"admin"})
    if not u:
        return RedirectResponse("/login", 303)
    anchor = anchor or business_date()
    start, end = period_range(period, anchor)
    con = db()
    branches = con.execute("SELECT * FROM branches WHERE active=1 ORDER BY name").fetchall()

    branch_clause = ""
    args = [start, end]
    if branch_id:
        branch_clause = " AND s.branch_id=?"
        args.append(branch_id)

    totals = con.execute(
        f"""SELECT
        COALESCE(SUM(CASE WHEN s.status='approved' THEN s.amount_kurus ELSE 0 END),0) revenue,
        COALESCE(SUM(CASE WHEN s.status='approved' THEN s.commission_kurus ELSE 0 END),0) commission,
        COUNT(CASE WHEN s.status='approved' THEN 1 END) approved_count,
        COUNT(CASE WHEN s.status='cancelled' THEN 1 END) cancelled_count
        FROM sessions s WHERE s.business_date BETWEEN ? AND ? {branch_clause}""",
        args,
    ).fetchone()

    exp_args = [start, end]
    exp_clause = ""
    if branch_id:
        exp_clause = " AND branch_id=?"
        exp_args.append(branch_id)

    expense_total = con.execute(
        f"SELECT COALESCE(SUM(amount_kurus),0) total FROM expenses WHERE expense_date BETWEEN ? AND ? AND active=1 {exp_clause}",
        exp_args,
    ).fetchone()["total"]

    guarantee_total = con.execute(
        f"""SELECT COALESCE(SUM(amount_kurus),0) total FROM staff_deductions
            WHERE deduction_date BETWEEN ? AND ? AND active=1
            AND deduction_type='security' {exp_clause}""",
        exp_args,
    ).fetchone()["total"]

    cleaning_total = con.execute(
        f"""SELECT COALESCE(SUM(amount_kurus),0) total FROM staff_deductions
            WHERE deduction_date BETWEEN ? AND ? AND active=1
            AND deduction_type='cleaning' {exp_clause}""",
        exp_args,
    ).fetchone()["total"]

    meal_total = con.execute(
        f"""SELECT COALESCE(SUM(amount_kurus),0) total FROM staff_deductions
            WHERE deduction_date BETWEEN ? AND ? AND active=1
            AND deduction_type='meal' {exp_clause}""",
        exp_args,
    ).fetchone()["total"]

    staff_stats = con.execute(
        f"""SELECT u.full_name staff,COUNT(*) session_count,COALESCE(SUM(s.amount_kurus),0) revenue,COALESCE(SUM(s.commission_kurus),0) commission
        FROM sessions s JOIN users u ON u.id=s.staff_id
        WHERE s.status='approved' AND s.business_date BETWEEN ? AND ? {branch_clause}
        GROUP BY u.id ORDER BY session_count DESC,revenue DESC""",
        args,
    ).fetchall()

    service_stats = con.execute(
        f"""SELECT sv.name service,COUNT(*) session_count,COALESCE(SUM(s.amount_kurus),0) revenue
        FROM sessions s JOIN services sv ON sv.id=s.service_id
        WHERE s.status='approved' AND s.business_date BETWEEN ? AND ? {branch_clause}
        GROUP BY sv.id ORDER BY session_count DESC,revenue DESC""",
        args,
    ).fetchall()

    payment_stats = con.execute(
        f"""SELECT s.payment_method,COALESCE(SUM(s.amount_kurus),0) total
        FROM sessions s WHERE s.status='approved' AND s.business_date BETWEEN ? AND ? {branch_clause}
        GROUP BY s.payment_method""",
        args,
    ).fetchall()
    con.close()

    staff_rows = "".join(f"<tr><td>{r['staff']}</td><td>{r['session_count']}</td><td>{money(r['revenue'])}</td><td>{money(r['commission'])}</td></tr>" for r in staff_stats) or "<tr><td colspan='4'>Kayıt yok.</td></tr>"
    service_rows = "".join(f"<tr><td>{r['service']}</td><td>{r['session_count']}</td><td>{money(r['revenue'])}</td></tr>" for r in service_stats) or "<tr><td colspan='3'>Kayıt yok.</td></tr>"
    payment_rows = "".join(f"<tr><td>{PAYMENT.get(r['payment_method'],'Bilinmiyor')}</td><td>{money(r['total'])}</td></tr>" for r in payment_stats) or "<tr><td colspan='2'>Kayıt yok.</td></tr>"

    top_staff = staff_stats[0]["staff"] if staff_stats else "—"
    top_service = service_stats[0]["service"] if service_stats else "—"
    branch_options = '<option value="">Tüm Şubeler</option>' + "".join(f"<option value='{b['id']}' {'selected' if b['id']==branch_id else ''}>{b['name']}</option>" for b in branches)

    net = totals["revenue"] - expense_total - totals["commission"] + guarantee_total + cleaning_total + meal_total

    body = f"""<div class="head"><div><h1>Raporlar</h1><p>{start} — {end}</p></div>
    <form method="get" class="inline"><select name="period"><option value="day" {'selected' if period=='day' else ''}>Günlük</option><option value="week" {'selected' if period=='week' else ''}>Haftalık</option><option value="month" {'selected' if period=='month' else ''}>Aylık</option><option value="year" {'selected' if period=='year' else ''}>Yıllık</option></select><input type="date" name="anchor" value="{anchor}"><select name="branch_id">{branch_options}</select><button class="btn">Raporla</button><a class="btn" href="/reports/export.csv?period={period}&anchor={anchor}&branch_id={branch_id or ''}">CSV İndir</a></form></div>
    <div class="stats">
      <div class="stat"><small>Giren Para</small><strong>{money(totals['revenue'])}</strong></div>
      <div class="stat warn"><small>İşletme Masrafı</small><strong>{money(expense_total)}</strong></div>
      <div class="stat"><small>Personel Primi</small><strong>{money(totals['commission'])}</strong></div>
      <div class="stat"><small>Güvence Toplamı</small><strong>{money(guarantee_total)}</strong></div>
      <div class="stat"><small>Temizlik Kesintisi</small><strong>{money(cleaning_total)}</strong></div>
      <div class="stat"><small>Yemek Geri Kasa</small><strong>{money(meal_total)}</strong></div>
      <div class="stat"><small>Net</small><strong>{money(net)}</strong></div>
      <div class="stat"><small>Onaylı Seans</small><strong>{totals['approved_count']}</strong></div>
      <div class="stat"><small>En Çok Tercih Edilen Personel</small><strong>{top_staff}</strong></div>
      <div class="stat"><small>En Çok Tercih Edilen Seans</small><strong>{top_service}</strong></div>
    </div>
    <div class="grid"><section class="card"><h2>Personel Performansı</h2><div class="table"><table><tr><th>Personel</th><th>Seans</th><th>Ciro</th><th>Prim</th></tr>{staff_rows}</table></div></section>
    <section class="card"><h2>Seans Tercihleri</h2><div class="table"><table><tr><th>Seans</th><th>Adet</th><th>Ciro</th></tr>{service_rows}</table></div><h2>Ödeme Dağılımı</h2><div class="table"><table><tr><th>Yöntem</th><th>Toplam</th></tr>{payment_rows}</table></div></section></div>"""
    return HTMLResponse(layout(request, "Raporlar", body))

@app.post("/users/{uid}/edit")
def user_edit(request: Request, uid: int, full_name: str = Form(...), role: str = Form(...), branch_id: Optional[int] = Form(None), commission: int = Form(30), csrf_token: str = Form(..., alias="csrf")):
    admin = require(request, {"admin"})
    if not admin or not csrf_ok(request, csrf_token):
        return RedirectResponse("/users", 303)
    con = db()
    con.execute("UPDATE users SET full_name=?,role=?,branch_id=?,commission_rate=?,updated_at=?,updated_by=? WHERE id=?",
                (full_name.strip(), role, branch_id, max(0,min(100,commission)), local_now_text(), admin["id"], uid))
    con.commit(); con.close()
    audit(request, "edit", "user", uid, f"{full_name}/{role}/{branch_id}/{commission}")
    flash(request, "Kullanıcı güncellendi.")
    return RedirectResponse("/users", 303)

@app.post("/users/{uid}/toggle")
def user_toggle(request: Request, uid: int, csrf_token: str = Form(..., alias="csrf")):
    admin = require(request, {"admin"})
    if not admin or not csrf_ok(request, csrf_token):
        return RedirectResponse("/users", 303)
    if uid == admin["id"]:
        flash(request, "Kendi hesabınızı pasifleştiremezsiniz.", "error")
        return RedirectResponse("/users", 303)
    con = db(); row = con.execute("SELECT active FROM users WHERE id=?", (uid,)).fetchone()
    if row:
        state = 0 if row["active"] else 1
        con.execute("UPDATE users SET active=?,updated_at=?,updated_by=? WHERE id=?", (state,local_now_text(),admin["id"],uid))
        con.commit()
        audit(request, "toggle", "user", uid, str(state))
    con.close()
    return RedirectResponse("/users", 303)

@app.post("/users/{uid}/password")
def user_password(request: Request, uid: int, password: str = Form(...), csrf_token: str = Form(..., alias="csrf")):
    admin = require(request, {"admin"})
    if not admin or not csrf_ok(request, csrf_token):
        return RedirectResponse("/users", 303)
    if len(password) < 8:
        flash(request, "Şifre en az 8 karakter olmalı.", "error")
        return RedirectResponse("/users", 303)
    con = db()
    con.execute("UPDATE users SET password_hash=?,updated_at=?,updated_by=? WHERE id=?",
                (hash_password(password),local_now_text(),admin["id"],uid))
    con.commit(); con.close()
    audit(request, "password_reset", "user", uid, "Şifre sıfırlandı")
    flash(request, "Şifre sıfırlandı.")
    return RedirectResponse("/users", 303)

@app.get("/reports/export.csv")
def reports_export_csv(request: Request, period: str = "month", anchor: Optional[str] = None, branch_id: Optional[int] = None):
    if not require(request, {"admin"}):
        return RedirectResponse("/login", 303)
    anchor = anchor or business_date()
    start, end = period_range(period, anchor)
    con = db()
    q = """SELECT s.business_date,b.name branch,u.full_name staff,sv.name service,r.name room,
           s.amount_kurus,s.commission_kurus,s.payment_method,s.status,s.started_at,s.completed_at
           FROM sessions s JOIN branches b ON b.id=s.branch_id JOIN users u ON u.id=s.staff_id
           JOIN services sv ON sv.id=s.service_id JOIN rooms r ON r.id=s.room_id
           WHERE s.business_date BETWEEN ? AND ?"""
    args=[start,end]
    if branch_id:
        q += " AND s.branch_id=?"; args.append(branch_id)
    q += " ORDER BY s.business_date,s.id"
    rows = con.execute(q,args).fetchall(); con.close()
    out = io.StringIO(); w = csv.writer(out)
    w.writerow(["Tarih","Şube","Personel","Seans","Oda","Tutar","Prim","Ödeme","Durum","Giriş","Çıkış"])
    for r in rows:
        w.writerow([r["business_date"],r["branch"],r["staff"],r["service"],r["room"],r["amount_kurus"]/100,
                    r["commission_kurus"]/100,PAYMENT.get(r["payment_method"],r["payment_method"]),
                    STATUS.get(r["status"],r["status"]),r["started_at"],r["completed_at"]])
    content = "\ufeff" + out.getvalue()
    return StreamingResponse(iter([content.encode("utf-8")]), media_type="text/csv; charset=utf-8",
                             headers={"Content-Disposition":f'attachment; filename="anka_rapor_{start}_{end}.csv"'})

@app.get("/backups", response_class=HTMLResponse)
def backups_page(request: Request):
    if not require(request, {"admin"}):
        return RedirectResponse("/login", 303)
    con = db(); rows = con.execute("SELECT * FROM backups ORDER BY id DESC LIMIT 100").fetchall(); con.close()
    items = "".join(f"<tr><td>{r['created_at']}</td><td>{r['filename']}</td><td><a class='btn' href='/backups/{r['id']}/download'>İndir</a></td></tr>" for r in rows) or "<tr><td colspan='3'>Yedek yok.</td></tr>"
    body = f"""<div class="head"><div><h1>Yedekler</h1><p>Manuel veritabanı yedeği</p></div>
    <form method="post" action="/backups/create"><input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn primary">Şimdi Yedek Al</button></form></div>
    <section class="card"><div class="table"><table><tr><th>Zaman</th><th>Dosya</th><th></th></tr>{items}</table></div></section>"""
    return HTMLResponse(layout(request, "Yedekler", body))

@app.post("/backups/create")
def backup_create(request: Request, csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"admin"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/backups", 303)
    stamp = datetime.now(TR).strftime("%Y%m%d_%H%M%S")
    filename = f"anka_{stamp}.db"; target = BACKUP_DIR / filename
    source = db(); dest = sqlite3.connect(target); source.backup(dest); dest.close(); source.close()
    con = db(); cur = con.execute("INSERT INTO backups(filename,created_by,created_at,note) VALUES(?,?,?,?)",
                                  (filename,u["id"],local_now_text(),"Manuel yedek"))
    con.commit(); bid = cur.lastrowid; con.close()
    audit(request, "backup", "database", bid, filename)
    flash(request, "Yedek oluşturuldu.")
    return RedirectResponse("/backups", 303)

@app.get("/backups/{bid}/download")
def backup_download(request: Request, bid: int):
    if not require(request, {"admin"}):
        return RedirectResponse("/login", 303)
    con = db(); row = con.execute("SELECT * FROM backups WHERE id=?", (bid,)).fetchone(); con.close()
    if not row:
        return RedirectResponse("/backups", 303)
    path = BACKUP_DIR / row["filename"]
    if not path.exists():
        flash(request, "Yedek dosyası bulunamadı.", "error")
        return RedirectResponse("/backups", 303)
    return FileResponse(path, filename=row["filename"], media_type="application/octet-stream")

@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    if not require(request, {"admin"}):
        return RedirectResponse("/login", 303)
    con = db()
    rows = con.execute("SELECT a.*,u.full_name uname FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 300").fetchall()
    con.close()
    tr = "".join(f"<tr><td>{r['created_at']}</td><td>{r['uname'] or 'Sistem'}</td><td>{r['action']}</td><td>{r['entity_type']} #{r['entity_id']}</td><td>{r['details']}</td><td>{r['ip_address']}</td></tr>" for r in rows)
    return HTMLResponse(layout(request, "Geçmiş", f"<div class='head'><div><h1>İşlem Geçmişi</h1></div></div><section class='card'><div class='table'><table><tr><th>Zaman</th><th>Kullanıcı</th><th>İşlem</th><th>Kayıt</th><th>Detay</th><th>IP</th></tr>{tr}</table></div></section>"))


@app.get("/manifest.webmanifest")
def manifest():
    return JSONResponse({
        "name":"ANKA Yönetim",
        "short_name":"ANKA",
        "start_url":"/",
        "display":"standalone",
        "background_color":"#0b1220",
        "theme_color":"#0b1220",
        "description":"Çok şubeli canlı seans ve personel yönetimi",
        "icons":[
            {"src":"/app-icon.svg","sizes":"any","type":"image/svg+xml","purpose":"any maskable"}
        ]
    }, media_type="application/manifest+json")

@app.get("/app-icon.svg")
def app_icon():
    svg = """<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 512 512'>
    <defs><linearGradient id='g' x1='0' y1='0' x2='1' y2='1'><stop stop-color='#f59e0b'/><stop offset='1' stop-color='#b45309'/></linearGradient></defs>
    <rect width='512' height='512' rx='120' fill='#0b1220'/><rect x='96' y='96' width='320' height='320' rx='86' fill='url(#g)'/>
    <text x='256' y='330' text-anchor='middle' font-family='Arial' font-size='220' font-weight='900' fill='white'>A</text></svg>"""
    return HTMLResponse(svg, media_type="image/svg+xml")

@app.get("/service-worker.js")
def service_worker():
    js = """
    const CACHE='anka-v1';
    self.addEventListener('install',e=>{self.skipWaiting();});
    self.addEventListener('activate',e=>{e.waitUntil(self.clients.claim());});
    self.addEventListener('fetch',e=>{
      if(e.request.method!=='GET') return;
      e.respondWith(fetch(e.request).catch(()=>caches.match(e.request)));
    });
    """
    return HTMLResponse(js, media_type="application/javascript")

@app.get("/api/state")
def api_state(request: Request):
    maybe_backup_hourly()
    u = current_user(request)
    if not u:
        return JSONResponse({"error":"unauthorized"}, status_code=401)
    finalize_due_sessions()
    con = db()
    if u["role"] == "staff":
        rows = con.execute(
            """SELECT id,status,assigned_at,accepted_at,completed_at,cancelled_at,
                      cancel_requested_at,updated_at,help_requested
               FROM sessions WHERE staff_id=? AND business_date=?
               ORDER BY id DESC LIMIT 20""",
            (u["id"], business_date()),
        ).fetchall()
        latest = rows[0] if rows else None
        event = "assignment" if latest and latest["status"]=="assigned" else                 "cancel_request" if latest and latest["status"]=="cancel_requested" else                 "approval" if latest and latest["status"] in ("pending","approved","cancelled") else "update"
    else:
        clause,args="",[business_date()]
        if u["role"]=="manager":
            clause=" AND branch_id=?";args.append(u["branch_id"])
        rows = con.execute(
            f"""SELECT id,status,branch_id,room_id,staff_id,assigned_at,accepted_at,
                       completed_at,cancelled_at,cancel_requested_at,approved_at,
                       updated_at,help_requested
                FROM sessions WHERE business_date=? {clause}
                ORDER BY id DESC LIMIT 100""", args
        ).fetchall()
        event = "help" if any(r["help_requested"] for r in rows) else                 "cancel_request" if any(r["status"]=="cancel_requested" for r in rows) else                 "approval" if any(r["status"]=="pending" for r in rows) else "update"
    key = "|".join(":".join(str(r[k] or "") for k in r.keys()) for r in rows) or "empty"
    con.close()
    return {"key":key,"event":event,"server_time":iso_utc(utc_now())}

@app.get("/health")
def health():
    return {"status": "ok", "app": "ANKA", "time": iso_utc(utc_now())}
