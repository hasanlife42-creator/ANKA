from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import sqlite3
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path
from typing import Optional
from zoneinfo import ZoneInfo

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from starlette.middleware.sessions import SessionMiddleware

BASE = Path(__file__).resolve().parent
DB_PATH = Path(os.getenv("ANKA_DB_PATH", BASE / "data" / "anka.db"))
DB_PATH.parent.mkdir(parents=True, exist_ok=True)
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
:root{--bg:#f5f6f8;--card:#fff;--text:#111827;--muted:#6b7280;--line:#e5e7eb;--dark:#0f172a;--green:#059669;--red:#dc2626;--orange:#d97706;--blue:#2563eb}
*{box-sizing:border-box}body{margin:0;font-family:Inter,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif;background:var(--bg);color:var(--text)}
a{text-decoration:none;color:inherit}.top{height:68px;background:var(--dark);color:#fff;display:flex;justify-content:space-between;align-items:center;padding:0 20px;position:sticky;top:0;z-index:10}
.brand{display:flex;align-items:center;gap:10px;font-weight:900;letter-spacing:.12em;font-size:22px}.logo{width:36px;height:36px;border-radius:12px;background:linear-gradient(135deg,#f59e0b,#b45309);display:grid;place-items:center}
.user{display:flex;align-items:center;gap:12px}.user small{display:block;color:#cbd5e1}.shell{display:grid;grid-template-columns:230px 1fr;min-height:calc(100vh - 68px)}
nav{background:#fff;border-right:1px solid var(--line);padding:16px 11px}nav a{display:flex;gap:10px;padding:12px 13px;border-radius:11px;color:#475569;margin-bottom:5px}nav a:hover{background:#fff7ed;color:#9a3412;font-weight:700}
main{padding:24px;min-width:0}.head{display:flex;justify-content:space-between;align-items:center;gap:15px;margin-bottom:18px}.head h1{margin:0;font-size:28px}.head p{margin:4px 0 0;color:var(--muted)}
.card{background:#fff;border:1px solid var(--line);border-radius:18px;padding:19px;box-shadow:0 10px 28px rgba(15,23,42,.05)}.grid{display:grid;grid-template-columns:1.2fr 1fr;gap:18px}.stats{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px;margin-bottom:18px}.stat{background:#fff;border:1px solid var(--line);border-radius:15px;padding:16px}.stat small{display:block;color:var(--muted);margin-bottom:7px}.stat strong{font-size:22px}.warn{background:#fff7ed;border-color:#fed7aa}
.form{display:flex;flex-direction:column;gap:14px}.form input,.form select,.form textarea,.inline input,.inline select{width:100%;padding:11px 12px;border:1px solid #cbd5e1;border-radius:10px;font:inherit;background:#fff}.form label{font-weight:650;font-size:14px}
.btn{border:1px solid var(--line);background:#fff;border-radius:10px;padding:10px 14px;font-weight:750;cursor:pointer}.btn.primary{background:var(--dark);border-color:var(--dark);color:#fff}.btn.green{background:var(--green);border-color:var(--green);color:#fff}.btn.red{background:var(--red);border-color:var(--red);color:#fff}.btn.orange{background:var(--orange);border-color:var(--orange);color:#fff}.btn.full{width:100%}.btn:disabled{opacity:.5}
.table{overflow:auto}table{width:100%;border-collapse:collapse;min-width:680px}th,td{text-align:left;padding:11px 9px;border-bottom:1px solid var(--line);font-size:14px}th{color:var(--muted)}
.badge{display:inline-flex;padding:5px 9px;border-radius:999px;font-size:12px;font-weight:750}.pending{background:#fff7ed;color:#b45309}.approved,.active{background:#ecfdf5;color:#047857}.rejected,.cancelled,.cancel_requested{background:#fef2f2;color:#b91c1c}.assigned{background:#fff7ed;color:#b45309}.help{background:#fef2f2;color:#b91c1c;animation:pulse 1.2s infinite}
.flash{padding:12px 14px;border-radius:10px;margin-bottom:15px;background:#ecfdf5;color:#047857;border:1px solid #a7f3d0}.flash.error{background:#fef2f2;color:#b91c1c;border-color:#fecaca}
.login{min-height:100vh;display:grid;place-items:center;background:radial-gradient(circle at top,#78350f,#0f172a 70%);padding:20px}.loginbox{width:min(430px,100%);background:#fff;border-radius:24px;padding:30px;box-shadow:0 28px 70px rgba(0,0,0,.3)}.loginbrand{display:flex;align-items:center;gap:14px}.loginbrand .logo{width:58px;height:58px;font-size:26px}.loginbrand h1{font-size:40px;letter-spacing:.15em;margin:0}.muted{color:var(--muted)}
.branch-grid,.room-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:14px}.room-card{position:relative}.room-card h3{margin:0 0 5px}.timer{font-size:36px;font-weight:900;letter-spacing:.03em;margin:14px 0}.room-free{color:var(--muted);font-size:20px;padding:28px 0}.inline{display:flex;gap:8px;align-items:end}.approval{display:grid;grid-template-columns:1fr auto 1fr;gap:12px;align-items:center;padding:15px;border:1px solid var(--line);border-radius:14px;margin-bottom:10px;background:#fff}.amount{font-size:23px;font-weight:850}
.staff-hero{max-width:680px;margin:auto}.staff-actions{display:grid;grid-template-columns:1fr 1fr;gap:12px}.staff-actions .btn{padding:16px;font-size:17px}.active-session{text-align:center}.active-session h2{margin-bottom:4px}.active-session .timer{font-size:54px}.settings-row{display:grid;grid-template-columns:1fr 120px auto auto;gap:8px;align-items:center;padding:10px 0;border-bottom:1px solid var(--line)}
@keyframes pulse{50%{opacity:.55}}
@media(max-width:960px){.stats{grid-template-columns:repeat(2,1fr)}.grid{grid-template-columns:1fr}.branch-grid,.room-grid{grid-template-columns:1fr}.approval{grid-template-columns:1fr}.settings-row{grid-template-columns:1fr 90px}.settings-row form{display:contents}}
@media(max-width:700px){.top{height:62px;padding:0 12px}.user div{display:none}.shell{display:block}nav{position:fixed;bottom:0;left:0;right:0;z-index:20;display:flex;overflow-x:auto;padding:5px;border-top:1px solid var(--line);border-right:0}nav a{flex:0 0 auto;flex-direction:column;gap:0;font-size:17px;padding:7px 9px;margin:0}nav a span{font-size:10px}main{padding:16px 12px 88px}.head{align-items:flex-start}.head h1{font-size:23px}.stats{grid-template-columns:1fr 1fr}.stat strong{font-size:18px}.inline{flex-direction:column;align-items:stretch}.active-session .timer{font-size:46px}}
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
    }
    for name, sql_type in additions.items():
        if name not in session_cols:
            con.execute(f"ALTER TABLE sessions ADD COLUMN {name} {sql_type}")

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
    """)

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
    """Süresi biten aktif seansları onay bekleyen duruma geçirir."""
    con = db()
    now_text = iso_utc(utc_now())
    due = con.execute(
        "SELECT id FROM sessions WHERE status='active' AND ends_at IS NOT NULL AND ends_at<=?",
        (now_text,),
    ).fetchall()
    for row in due:
        con.execute(
            "UPDATE sessions SET status='pending',completed_at=COALESCE(completed_at,ends_at),help_requested=0 WHERE id=?",
            (row["id"],),
        )
    con.commit()
    con.close()
    return [r["id"] for r in due]

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
          {'<a href="/reports"><b>▥</b><span>Raporlar</span></a>' if u["role"]=="admin" else ''}
          <a href="/settings"><b>⚙</b><span>Ayarlar</span></a>
          {'<a href="/users"><b>♙</b><span>Kullanıcılar</span></a><a href="/audit"><b>◷</b><span>Geçmiş</span></a>' if u["role"]=="admin" else ''}
        </nav>"""

    common_script = """
    <script>
    function requestNoticePermission(){
      if("Notification" in window && Notification.permission==="default"){ Notification.requestPermission(); }
    }
    function beep(){
      try{
        const C=window.AudioContext||window.webkitAudioContext;
        const ctx=new C(),o=ctx.createOscillator(),g=ctx.createGain();
        o.connect(g);g.connect(ctx.destination);o.frequency.value=880;g.gain.value=.18;
        o.start();setTimeout(()=>{o.stop();ctx.close()},700);
      }catch(e){}
    }
    document.addEventListener("click",requestNoticePermission,{once:true});
    </script>
    """
    return f"""<!doctype html><html lang="tr"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="theme-color" content="#0f172a"><title>{title} • ANKA</title><style>{CSS}</style></head><body>
    <header class="top"><a class="brand" href="/"><span class="logo">A</span>ANKA</a><div class="user"><div><strong>{u["full_name"]}</strong><small>{ROLE[u["role"]]}</small></div><form method="post" action="/logout"><input type="hidden" name="csrf" value="{csrf(request)}"><button class="btn">Çıkış</button></form></div></header>
    <div class="shell">{nav}<main>{flash_html}{body}</main></div>{common_script}{extra_script}</body></html>"""

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
    con.close()
    if not u or not verify_password(password, u["password_hash"]):
        flash(request, "Kullanıcı adı veya şifre hatalı.", "error")
        return RedirectResponse("/login", 303)
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
@app.get("/", response_class=HTMLResponse)
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
@app.get("/session/new", response_class=HTMLResponse)
@app.get("/session/new", response_class=HTMLResponse)
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
@app.post("/session/new")
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
    room_busy = con.execute("SELECT 1 FROM sessions WHERE room_id=? AND status IN('assigned','active')", (room_id,)).fetchone()
    staff_busy = con.execute("SELECT 1 FROM sessions WHERE staff_id=? AND status IN('assigned','active')", (staff_id,)).fetchone()
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
        "SELECT * FROM sessions WHERE id=? AND staff_id=? AND status IN('assigned','active')",
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
@app.get("/live", response_class=HTMLResponse)
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
                   WHERE s.room_id=? AND s.status IN('assigned','active')
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

    body = f"""<div class="head"><div><h1>Seans Durumu</h1><p>Tüm şubeler aynı ekranda</p></div></div>
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
    users = con.execute("SELECT u.*,b.name branch FROM users u LEFT JOIN branches b ON b.id=u.branch_id ORDER BY role,full_name").fetchall()
    con.close()
    branch_options = '<option value="">Şubesiz</option>' + "".join(f"<option value='{b['id']}'>{b['name']}</option>" for b in branches)
    rows = "".join(f"<tr><td>{x['full_name']}</td><td>@{x['username']}</td><td>{ROLE[x['role']]}</td><td>{x['branch'] or 'Tüm şubeler'}</td></tr>" for x in users)
    body = f"""<div class="head"><div><h1>Kullanıcılar</h1></div></div><div class="grid"><section class="card"><form method="post" class="form">
    <input type="hidden" name="csrf" value="{csrf(request)}"><label>Ad Soyad<input name="full_name" required></label><label>Kullanıcı adı<input name="username" required></label>
    <label>Rol<select name="role"><option value="staff">Personel</option><option value="manager">Müdür</option><option value="admin">Yönetici</option></select></label>
    <label>Şube<select name="branch_id">{branch_options}</select></label><label>Prim %<input type="number" name="commission" value="30"></label>
    <label>Geçici şifre<input type="password" name="password" minlength="8" required></label><button class="btn primary">Oluştur</button></form></section>
    <section class="card"><div class="table"><table><tr><th>Ad</th><th>Kullanıcı</th><th>Rol</th><th>Şube</th></tr>{rows}</table></div></section></div>"""
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

@app.get("/day-end", response_class=HTMLResponse)
@app.get("/day-end", response_class=HTMLResponse)
@app.get("/day-end", response_class=HTMLResponse)
def day_end_page(request: Request, branch_id: Optional[int] = None, day: Optional[str] = None):
    u = require(request, {"admin", "manager"})
    if not u:
        return RedirectResponse("/login", 303)
    day = day or business_date()
    con = db()
    branches = con.execute("SELECT * FROM branches WHERE active=1 ORDER BY name").fetchall()
    if u["role"] == "manager":
        branch_id = u["branch_id"]
        branches = [b for b in branches if b["id"] == u["branch_id"]]
    if not branch_id and branches:
        branch_id = branches[0]["id"]

    staff_list = con.execute(
        "SELECT id,full_name,commission_rate FROM users WHERE role='staff' AND active=1 AND branch_id=? ORDER BY full_name",
        (branch_id,),
    ).fetchall()
    sessions = con.execute(
        """SELECT s.*,u.full_name staff,sv.name service,r.name room
           FROM sessions s JOIN users u ON u.id=s.staff_id
           JOIN services sv ON sv.id=s.service_id JOIN rooms r ON r.id=s.room_id
           WHERE s.branch_id=? AND s.business_date=? ORDER BY u.full_name,s.id""",
        (branch_id, day),
    ).fetchall()
    deductions = con.execute(
        """SELECT d.*,u.full_name staff FROM staff_deductions d JOIN users u ON u.id=d.staff_id
           WHERE d.branch_id=? AND d.deduction_date=? AND d.active=1 ORDER BY d.staff_id,d.id""",
        (branch_id, day),
    ).fetchall()
    expenses = con.execute(
        """SELECT e.*,u.full_name creator FROM expenses e JOIN users u ON u.id=e.created_by
           WHERE e.branch_id=? AND e.expense_date=? AND e.active=1 ORDER BY e.id DESC""",
        (branch_id, day),
    ).fetchall()
    totals = con.execute(
        """SELECT
           COALESCE(SUM(CASE WHEN status='approved' THEN amount_kurus ELSE 0 END),0) revenue,
           COALESCE(SUM(CASE WHEN status='approved' THEN commission_kurus ELSE 0 END),0) commission,
           COALESCE(SUM(CASE WHEN status='approved' AND payment_method='cash' THEN amount_kurus ELSE 0 END),0) cash,
           COALESCE(SUM(CASE WHEN status='approved' AND payment_method='iban' THEN amount_kurus ELSE 0 END),0) iban,
           COALESCE(SUM(CASE WHEN status='approved' AND payment_method='easy_address' THEN amount_kurus ELSE 0 END),0) easy_address,
           SUM(CASE WHEN status='active' THEN 1 ELSE 0 END) active,
           SUM(CASE WHEN status='assigned' THEN 1 ELSE 0 END) assigned,
           SUM(CASE WHEN status='pending' THEN 1 ELSE 0 END) pending,
           SUM(CASE WHEN status='cancel_requested' THEN 1 ELSE 0 END) cancel_requested
           FROM sessions WHERE branch_id=? AND business_date=?""",
        (branch_id, day),
    ).fetchone()
    expense_total = con.execute(
        "SELECT COALESCE(SUM(amount_kurus),0) total FROM expenses WHERE branch_id=? AND expense_date=? AND active=1",
        (branch_id, day),
    ).fetchone()["total"]
    closing = con.execute(
        "SELECT * FROM day_closings WHERE branch_id=? AND business_date=?",
        (branch_id, day),
    ).fetchone()
    con.close()

    by_staff_sessions = {s["id"]: [] for s in staff_list}
    for row in sessions:
        by_staff_sessions.setdefault(row["staff_id"], []).append(row)
    by_staff_deductions = {s["id"]: [] for s in staff_list}
    for row in deductions:
        by_staff_deductions.setdefault(row["staff_id"], []).append(row)

    def clock(v):
        if not v:
            return "—"
        try:
            return datetime.fromisoformat(v.replace("Z","+00:00")).astimezone(TR).strftime("%H:%M")
        except Exception:
            return "—"

    columns = ""
    total_meal_cashback = 0
    for staff in staff_list:
        items = by_staff_sessions.get(staff["id"], [])
        staff_deds = by_staff_deductions.get(staff["id"], [])
        approved = [i for i in items if i["status"] == "approved"]
        gross_commission = sum(i["commission_kurus"] for i in approved)

        security = sum(d["amount_kurus"] for d in staff_deds if d["deduction_type"] == "security")
        cleaning = sum(d["amount_kurus"] for d in staff_deds if d["deduction_type"] == "cleaning")
        meal = sum(d["amount_kurus"] for d in staff_deds if d["deduction_type"] == "meal")
        total_meal_cashback += meal

        net_commission = gross_commission - security - cleaning - meal

        session_rows = "".join(
            f"""<div style="padding:10px 0;border-bottom:1px solid var(--line)">
            <strong>{i['service']}</strong> — {money(i['amount_kurus'])}<br>
            <small>{i['room']} • {clock(i['started_at'])}-{clock(i['completed_at'] or i['cancelled_at'])} • {PAYMENT.get(i['payment_method'],'—')}</small><br>
            <span class="badge {i['status']}">{STATUS.get(i['status'],i['status'])}</span>
            {f"<div>Prim: {money(i['commission_kurus'])}</div>" if i['status']=='approved' else ""}
            </div>"""
            for i in items
        ) or "<p class='muted'>Seans yok.</p>"

        columns += f"""<section class="card" style="min-width:300px">
        <h2>{staff['full_name']}</h2>
        <div>{session_rows}</div>
        <hr>
        <p><strong>Toplam Seans:</strong> {len(items)}</p>
        <p><strong>Brüt Prim:</strong> {money(gross_commission)}</p>

        <form method="post" action="/staff-deductions/set" class="form">
          <input type="hidden" name="csrf" value="{csrf(request)}">
          <input type="hidden" name="branch_id" value="{branch_id}">
          <input type="hidden" name="staff_id" value="{staff['id']}">
          <input type="hidden" name="day" value="{day}">

          <label>Güvence<input name="security" value="{security/100:.2f}" inputmode="decimal"></label>
          <label>Temizlik<input name="cleaning" value="{cleaning/100:.2f}" inputmode="decimal"></label>
          <label>Yemek Parası<input name="meal" value="{meal/100:.2f}" inputmode="decimal"></label>

          <button class="btn">Kesintileri Kaydet</button>
        </form>

        <p style="font-size:20px"><strong>Net Prim:</strong> {money(net_commission)}</p>
        </section>"""

    expense_rows = "".join(
        f"<tr><td>{e['description']}</td><td>{money(e['amount_kurus'])}</td><td>{e['creator']}</td></tr>"
        for e in expenses
    ) or "<tr><td colspan='3'>İşletme masrafı yok.</td></tr>"

    branch_options = "".join(
        f"<option value='{b['id']}' {'selected' if b['id']==branch_id else ''}>{b['name']}</option>"
        for b in branches
    )
    blockers = int(totals["active"] or 0) + int(totals["assigned"] or 0) + int(totals["pending"] or 0) + int(totals["cancel_requested"] or 0)

    expected_cash_with_meal = int(totals["cash"] or 0) + total_meal_cashback

    if closing and not closing["reopened_at"]:
        closing_box = f"""<section class="card"><h2>Gün Kapatıldı</h2><p>{closing['closed_at']}</p>
        {'<form method="post" action="/day-end/reopen"><input type="hidden" name="csrf" value="'+csrf(request)+'"><input type="hidden" name="branch_id" value="'+str(branch_id)+'"><input type="hidden" name="day" value="'+day+'"><input name="reason" placeholder="Yeniden açma sebebi" required><button class="btn red">Günü Yeniden Aç</button></form>' if u['role']=='admin' else ''}</section>"""
    else:
        closing_box = f"""<section class="card"><h2>Fiziki Sayım ve Kapatma</h2>
        {'<div class="flash error">'+str(blockers)+' açık/bekleyen işlem var. Gün kapatılamaz.</div>' if blockers else ''}
        <p><strong>Beklenen Nakit:</strong> {money(expected_cash_with_meal)} <small>(Yemek iadeleri dahil)</small></p>
        <form method="post" action="/day-end/close" class="form"><input type="hidden" name="csrf" value="{csrf(request)}"><input type="hidden" name="branch_id" value="{branch_id}"><input type="hidden" name="day" value="{day}">
        <label>Sayılan Nakit<input name="cash" value="0" required></label><label>IBAN Toplamı<input name="iban" value="0" required></label><label>Kolay Adres Toplamı<input name="card" value="0" required></label><label>Not<textarea name="note"></textarea></label>
        <button class="btn primary" {'disabled' if blockers else ''}>Günü Kapat ve Kilitle</button></form></section>"""

    body = f"""<div class="head"><div><h1>Gün Sonu</h1><p>Personel bazlı prim ve sabit kesintiler</p></div>
    <form method="get" class="inline"><select name="branch_id">{branch_options}</select><input type="date" name="day" value="{day}"><button class="btn">Göster</button></form></div>
    <div class="stats"><div class="stat"><small>Onaylı Ciro</small><strong>{money(totals['revenue'])}</strong></div><div class="stat"><small>Nakit</small><strong>{money(totals['cash'])}</strong></div><div class="stat"><small>Yemek Geri Kasa</small><strong>{money(total_meal_cashback)}</strong></div><div class="stat"><small>IBAN</small><strong>{money(totals['iban'])}</strong></div><div class="stat"><small>Kolay Adres</small><strong>{money(totals['easy_address'])}</strong></div><div class="stat"><small>Toplam Prim</small><strong>{money(totals['commission'])}</strong></div><div class="stat warn"><small>İşletme Masrafı</small><strong>{money(expense_total)}</strong></div></div>
    <div style="display:flex;gap:14px;overflow-x:auto;padding-bottom:10px">{columns or "<section class='card'>Personel yok.</section>"}</div>
    <div class="grid" style="margin-top:18px"><section class="card"><h2>İşletme Masrafları</h2>
    <form method="post" action="/expenses/new" class="form"><input type="hidden" name="csrf" value="{csrf(request)}"><input type="hidden" name="branch_id" value="{branch_id}"><input type="hidden" name="day" value="{day}"><label>Açıklama<input name="description" required></label><label>Tutar<input name="amount" required></label><button class="btn primary">Masraf Ekle</button></form>
    <div class="table"><table><tr><th>Açıklama</th><th>Tutar</th><th>Ekleyen</th></tr>{expense_rows}</table></div></section>{closing_box}</div>"""
    return HTMLResponse(layout(request, "Gün Sonu", body))

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
@app.post("/day-end/close")
def day_end_close(request: Request, branch_id: int = Form(...), day: str = Form(...), cash: str = Form(...), card: str = Form(...), iban: str = Form(...), note: str = Form(""), csrf_token: str = Form(..., alias="csrf")):
    u = require(request, {"admin", "manager"})
    if not u or not csrf_ok(request, csrf_token):
        return RedirectResponse("/day-end", 303)
    if u["role"] == "manager" and branch_id != u["branch_id"]:
        return RedirectResponse("/day-end", 303)
    con = db()
    blockers = con.execute("SELECT COUNT(*) c FROM sessions WHERE branch_id=? AND business_date=? AND status IN('assigned','active','pending')", (branch_id, day)).fetchone()["c"]
    if blockers:
        con.close()
        flash(request, "Açık veya onay bekleyen işlemler tamamlanmadan gün kapatılamaz.", "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)
    def zero_money(v):
        return 0 if v.strip() in ("", "0", "0,00", "0.00") else to_kurus(v)
    try:
        counted_cash, counted_card, counted_iban = zero_money(cash), zero_money(card), zero_money(iban)
    except ValueError as e:
        con.close()
        flash(request, str(e), "error")
        return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)

    totals = con.execute(
        """SELECT
           COALESCE(SUM(CASE WHEN status='approved' AND payment_method='cash' THEN amount_kurus ELSE 0 END),0) cash,
           COALESCE(SUM(CASE WHEN status='approved' AND payment_method='card' THEN amount_kurus ELSE 0 END),0) card,
           COALESCE(SUM(CASE WHEN status='approved' AND payment_method='iban' THEN amount_kurus ELSE 0 END),0) iban,
           COALESCE(SUM(CASE WHEN status='approved' THEN commission_kurus ELSE 0 END),0) commission
           FROM sessions WHERE branch_id=? AND business_date=?""",
        (branch_id, day),
    ).fetchone()
    expense = con.execute("SELECT COALESCE(SUM(amount_kurus),0) total FROM expenses WHERE branch_id=? AND expense_date=? AND active=1", (branch_id, day)).fetchone()["total"]
    try:
        con.execute(
            """INSERT INTO day_closings(branch_id,business_date,expected_cash_kurus,expected_card_kurus,expected_iban_kurus,expense_kurus,commission_kurus,counted_cash_kurus,counted_card_kurus,counted_iban_kurus,note,closed_by,closed_at)
               VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (branch_id, day, totals["cash"], totals["card"], totals["iban"], expense, totals["commission"], counted_cash, counted_card, counted_iban, note[:500], u["id"], local_now_text()),
        )
        con.commit()
        flash(request, "Gün kapatıldı ve kilitlendi.")
    except sqlite3.IntegrityError:
        flash(request, "Bu gün zaten kapatılmış.", "error")
    con.close()
    audit(request, "close_day", "day", f"{branch_id}:{day}", "Gün kapatıldı")
    return RedirectResponse(f"/day-end?branch_id={branch_id}&day={day}", 303)

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

@app.get("/reports", response_class=HTMLResponse)
@app.get("/reports", response_class=HTMLResponse)
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
    <form method="get" class="inline"><select name="period"><option value="day" {'selected' if period=='day' else ''}>Günlük</option><option value="week" {'selected' if period=='week' else ''}>Haftalık</option><option value="month" {'selected' if period=='month' else ''}>Aylık</option><option value="year" {'selected' if period=='year' else ''}>Yıllık</option></select><input type="date" name="anchor" value="{anchor}"><select name="branch_id">{branch_options}</select><button class="btn">Raporla</button></form></div>
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

@app.get("/audit", response_class=HTMLResponse)
def audit_page(request: Request):
    if not require(request, {"admin"}):
        return RedirectResponse("/login", 303)
    con = db()
    rows = con.execute("SELECT a.*,u.full_name uname FROM audit_logs a LEFT JOIN users u ON u.id=a.user_id ORDER BY a.id DESC LIMIT 300").fetchall()
    con.close()
    tr = "".join(f"<tr><td>{r['created_at']}</td><td>{r['uname'] or 'Sistem'}</td><td>{r['action']}</td><td>{r['entity_type']} #{r['entity_id']}</td><td>{r['details']}</td><td>{r['ip_address']}</td></tr>" for r in rows)
    return HTMLResponse(layout(request, "Geçmiş", f"<div class='head'><div><h1>İşlem Geçmişi</h1></div></div><section class='card'><div class='table'><table><tr><th>Zaman</th><th>Kullanıcı</th><th>İşlem</th><th>Kayıt</th><th>Detay</th><th>IP</th></tr>{tr}</table></div></section>"))

@app.get("/health")
def health():
    return {"status": "ok", "app": "ANKA", "time": iso_utc(utc_now())}
