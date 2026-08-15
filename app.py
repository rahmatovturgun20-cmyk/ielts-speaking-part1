# -*- coding: utf-8 -*-
"""
Multilevel Mock Test - pullik tizim + admin panel
Ishga tushirish: python start-server-https.py
"""
import atexit
import datetime
import hashlib
import hmac
import json
import logging
import os
import secrets
import sqlite3
import time
import traceback
import urllib.parse
import urllib.request
from collections import defaultdict
from logging.handlers import RotatingFileHandler

from flask import Flask, abort, jsonify, make_response, redirect, render_template_string, request, send_file, send_from_directory, session

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, "site.db")
CONFIG_FILE = os.path.join(BASE_DIR, "config.json")
CONTENT_FILE = os.path.join(BASE_DIR, "content.json")
LOG_FILE = os.path.join(BASE_DIR, "server.log")
RECEIPTS_DIR = os.path.join(BASE_DIR, "receipts")
if not os.path.isdir(RECEIPTS_DIR):
    os.makedirs(RECEIPTS_DIR)


# ---- Logging ----

def setup_logging():
    fmt = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )
    handler = RotatingFileHandler(LOG_FILE, maxBytes=5 * 1024 * 1024, backupCount=5, encoding="utf-8")
    handler.setFormatter(fmt)
    handler.setLevel(logging.INFO)
    logger = logging.getLogger("app")
    logger.setLevel(logging.INFO)
    logger.addHandler(handler)
    stream = logging.StreamHandler()
    stream.setFormatter(fmt)
    stream.setLevel(logging.WARNING)
    logger.addHandler(stream)
    return logger


log = setup_logging()
log.info("=" * 50)
log.info("Server starting...")

# ---- Xatolik handlerlari & validatorlar ----

def api_error(msg, code=400):
    """API uchun standart xatolik javobi."""
    return jsonify({"ok": False, "error": msg}), code


# ---- Xavfsizlik: rate limiting ----

_rate_attempts = defaultdict(list)  # key -> [timestamps]

def rate_limited(key, limit=10, window=600):
    """IP/action uchun urinish cheklovi. Limitdan oshsa True."""
    now = time.time()
    _rate_attempts[key] = [t for t in _rate_attempts[key] if now - t < window]
    if len(_rate_attempts[key]) >= limit:
        return True
    _rate_attempts[key].append(now)
    return False


def client_key(action):
    ip = request.remote_addr or "?"
    return "%s:%s" % (action, ip)


# ---- Xavfsizlik: fayl imzosi (magic bytes) tekshirish ----

def valid_image(data):
    """Fayl tarkibini (magic bytes) tekshiradi — faqat rasm/PDF qabul qilinadi."""
    if data[:3] == b"\xff\xd8\xff":
        return True  # JPEG
    if data[:8] == b"\x89PNG\r\n\x1a\n":
        return True  # PNG
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return True  # GIF
    if len(data) >= 12 and data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return True  # WebP
    if data[:2] == b"BM":
        return True  # BMP
    if data[:4] == b"%PDF":
        return True  # PDF
    return False


def safe_api(fn):
    """JSON endpointlarni xatoliklardan himoya qiluvchi dekorator."""
    from functools import wraps
    @wraps(fn)
    def wrapper(*a, **kw):
        try:
            return fn(*a, **kw)
        except ValueError as e:
            log.warning("Validation error in %s: %s", fn.__name__, str(e))
            return api_error(str(e))
        except sqlite3.Error as e:
            log.error("DB error in %s: %s", fn.__name__, str(e))
            return api_error("Ma'lumotlar bazasi xatosi. Iltimos qayta urinib ko'ring.", 500)
        except Exception as e:
            log.error("Unexpected error in %s: %s\n%s", fn.__name__, str(e), traceback.format_exc())
            return api_error("Serverda kutilmagan xatolik yuz berdi. Admin bilan bog'laning.", 500)
    return wrapper


def validate_phone(phone):
    """Telefon raqamni tekshirish."""
    import re
    phone = (phone or "").strip()
    cleaned = re.sub(r'[\s\-\(\)]', '', phone)
    if not cleaned.startswith('+'):
        cleaned = '+' + cleaned
    if not re.match(r'^\+?\d{7,15}$', cleaned):
        raise ValueError("Telefon raqam noto'g'ri. Masalan: +998901234567")
    return cleaned


def validate_password(pw):
    """Parolni tekshirish."""
    if not pw or len(pw.strip()) < 4:
        raise ValueError("Parol kamida 4 ta belgidan iborat bo'lishi kerak")
    return pw.strip()


def safe_db_conn():
    """Xavfsiz DB ulanish."""
    try:
        return sqlite3.connect(DB_FILE)
    except sqlite3.Error as e:
        log.error("DB connection failed: %s", str(e))
        raise sqlite3.Error("Ma'lumotlar bazasiga ulanishda xatolik")

APP_PAGES = [
    "index.html",
    "index-mobile.html",
    "CEFR-speaking-part1.html",
    "CEFR-speaking-part1-mobile.html",
    "landing.html",
]

DEFAULT_CONFIG = {
    "secret_key": "",
    "admin_phone": "+998900000000",
    "card_number": "8600 0000 0000 0000",
    "card_holder": "F.I.Sh.",
    "base_url": "https://multilevelmocktest.uz",
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "payme": {"merchant_id": "", "merchant_key": "", "enabled": False},
    "click": {"service_id": "", "merchant_id": "", "merchant_user_id": "", "secret_key": "", "enabled": False},
    "uzum": {"shop_id": "", "service_id": "", "api_key": "", "enabled": False},
}


def load_config():
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(DEFAULT_CONFIG, f, ensure_ascii=False, indent=2)
    with open(CONFIG_FILE, encoding="utf-8") as f:
        cfg = json.load(f)
    for k, v in DEFAULT_CONFIG.items():
        cfg.setdefault(k, v)
    return cfg


def save_config(cfg):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(cfg, f, ensure_ascii=False, indent=2)


cfg = load_config()
if not cfg["secret_key"]:
    cfg["secret_key"] = secrets.token_hex(32)
    save_config(cfg)

app = Flask(__name__)
app.secret_key = cfg["secret_key"]
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True
app.config["PERMANENT_SESSION_LIFETIME"] = datetime.timedelta(days=7)
app.config["MAX_CONTENT_LENGTH"] = 32 * 1024 * 1024


# ---- Error handlers ----

@app.errorhandler(400)
def err_400(e):
    log.warning("400 Bad Request: %s %s", request.method, request.path)
    return jsonify({"ok": False, "error": "So'rov noto'g'ri"}), 400

@app.errorhandler(404)
def err_404(e):
    return jsonify({"ok": False, "error": "Topilmadi"}), 404

@app.errorhandler(405)
def err_405(e):
    log.warning("405 Method Not Allowed: %s %s", request.method, request.path)
    return jsonify({"ok": False, "error": "Ruxsat etilmagan metod"}), 405

@app.errorhandler(500)
def err_500(e):
    log.error("500 Internal Error: %s %s | %s", request.method, request.path, traceback.format_exc())
    return jsonify({"ok": False, "error": "Server xatosi"}), 500

@app.errorhandler(Exception)
def err_unhandled(e):
    log.error("Unhandled: %s %s | %s: %s", request.method, request.path, type(e).__name__, str(e))
    log.error(traceback.format_exc())
    return jsonify({"ok": False, "error": "Kutilmagan xato"}), 500

@app.before_request
def log_request():
    if request.path.startswith("/api/") or request.path.startswith("/admin"):
        request._start_time = time.time()
        log.info("%s %s | IP: %s | UID: %s | Agent: %s",
                 request.method, request.path,
                 request.remote_addr,
                 session.get("uid"),
                 request.headers.get("User-Agent", "?")[:80])


@app.after_request
def add_security_headers(resp):
    if request.path.startswith("/api/") or request.path.startswith("/admin"):
        dur = time.time() - getattr(request, "_start_time", time.time())
        log.info("RESPONSE %s %s -> %s (%.3fs)",
                 request.method, request.path, resp.status_code, dur)
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["X-XSS-Protection"] = "1; mode=block"
    resp.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    resp.headers["Permissions-Policy"] = "microphone=(self)"
    return resp


# ---------------- DB ----------------

def db():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = db()
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      phone TEXT UNIQUE NOT NULL,
      password_hash TEXT NOT NULL,
      name TEXT DEFAULT '',
      is_admin INTEGER DEFAULT 0,
      blocked INTEGER DEFAULT 0,
      lifetime INTEGER DEFAULT 0,
      access_until TEXT,
      created_at TEXT
    );
    CREATE TABLE IF NOT EXISTS plans (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL UNIQUE,
      price INTEGER NOT NULL,
      days INTEGER,
      kind TEXT DEFAULT 'subscription',
      sort INTEGER DEFAULT 0
    );
    CREATE TABLE IF NOT EXISTS payments (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER,
      plan_id INTEGER,
      plan_name TEXT,
      provider TEXT,
      amount INTEGER,
      status TEXT DEFAULT 'pending',
      tx_id TEXT,
      receipt TEXT,
      created_at TEXT,
      paid_at TEXT
    );
    """)
    try:
        conn.execute("ALTER TABLE payments ADD COLUMN receipt TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN usage_seconds INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN last_seen TEXT")
    except sqlite3.OperationalError:
        pass
    try:
        conn.execute("ALTER TABLE users ADD COLUMN mock_used INTEGER DEFAULT 0")
    except sqlite3.OperationalError:
        pass
    # Mavjud jadval uchun unique index (race condition oldini olish)
    try:
        conn.execute("DELETE FROM plans WHERE id NOT IN (SELECT MIN(id) FROM plans GROUP BY name)")
        conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_plans_name ON plans(name)")
    except sqlite3.Error:
        pass
    n = conn.execute("SELECT COUNT(*) c FROM plans").fetchone()["c"]
    if n == 0:
        plans = [
            ("1 oylik obuna", 30000, 30, "subscription", 1),
            ("2 oylik obuna", 50000, 60, "subscription", 2),
            ("3 oylik obuna", 80000, 90, "subscription", 3),
        ]
        conn.executemany(
            "INSERT INTO plans (name, price, days, kind, sort) VALUES (?,?,?,?,?)", plans)
    # Eslatma: admin faqat CLI orqali yaratiladi (python app.py create-admin <phone> <strong_password>).
    # config.json da parol saqlanmaydi — xavfsizlik uchun.
    conn.commit()
    conn.close()
    preload_static_pages()
    log.info("DB initialized OK | pages cached: %d", len(APP_PAGES))


def preload_static_pages():
    app.config["STATIC_CACHE"] = {}
    for fn in APP_PAGES:
        p = os.path.join(BASE_DIR, fn)
        if os.path.exists(p):
            with open(p, "rb") as f:
                app.config["STATIC_CACHE"][fn] = f.read()


# ---------------- Security ----------------

def hash_password(pw, salt=None):
    if salt is None:
        salt = secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", pw.encode(), salt.encode(), 120000)
    return "pbkdf2$%s$%s" % (salt, dk.hex())


def verify_password(pw, stored):
    try:
        _, salt, hexed = stored.split("$")
        return hmac.compare_digest(hash_password(pw, salt), stored)
    except Exception:
        return False


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    conn.close()
    return u


def has_access(u):
    if u is None or u["blocked"]:
        return False
    if u["lifetime"]:
        return True
    if u["access_until"]:
        until = datetime.datetime.fromisoformat(u["access_until"])
        if until > datetime.datetime.now():
            return True
    return False


# ---- Kontent (savol-javoblar) — server tomonida himoya qilinadi ----

FREEMIUM_FREE_QUESTIONS = 6   # Part 1.1: birinchi 2 guruh (3 tadan savol) bepul
FREEMIUM_FREE_ITEMS = 2       # Part 1.2 / 2 / 3: birinchi 2 rasm/karta/topshiriq bepul

_content_cache = None


def load_content():
    """content.json faylini yuklaydi va xotirada saqlaydi."""
    global _content_cache
    if _content_cache is not None:
        return _content_cache
    with open(CONTENT_FILE, encoding="utf-8") as f:
        _content_cache = json.load(f)
    _content_cache.pop("_counts", None)
    return _content_cache


def content_totals(data):
    return {
        "part1": len(data.get("SAVOLLAR", [])),
        "part12": len(data.get("PART12_SETS", [])),
        "part2": len(data.get("PART2_CARDS", [])),
        "part3": len(data.get("PART3_SAMPLES", {})),
    }


def truncate_content(data):
    """Premium bo'lmagan foydalanuvchi uchun faqat bepul qismini qaytaradi."""
    n_q = min(FREEMIUM_FREE_QUESTIONS, len(data.get("SAVOLLAR", [])))
    savollar = data["SAVOLLAR"][:n_q]
    samples = {q: data["SAMPLES"].get(q) for q in savollar if q in data["SAMPLES"]}

    n12 = min(FREEMIUM_FREE_ITEMS, len(data.get("PART12_SETS", [])))
    sets = data["PART12_SETS"][:n12]
    free_imgs12 = {s["img"] for s in sets}
    samples12 = {img: data["PART12_SAMPLES"][img]
                 for img in free_imgs12 if img in data["PART12_SAMPLES"]}

    n2 = min(FREEMIUM_FREE_ITEMS, len(data.get("PART2_CARDS", [])))
    cards = data["PART2_CARDS"][:n2]
    card_qs = {c["q"] for c in cards}
    samples2 = {q: data["PART2_SAMPLES"][q] for q in card_qs if q in data["PART2_SAMPLES"]}

    n3 = min(FREEMIUM_FREE_ITEMS, len(data.get("PART3_SAMPLES", {})))
    imgs3 = list(data["PART3_SAMPLES"].keys())[:n3]
    samples3 = {img: data["PART3_SAMPLES"][img] for img in imgs3}

    return {
        "SAVOLLAR": savollar,
        "SAMPLES": samples,
        "PART12_TIMING": data.get("PART12_TIMING", []),
        "PART12_SETS": sets,
        "PART12_SAMPLES": samples12,
        "PART2_CARDS": cards,
        "PART2_SAMPLES": samples2,
        "PART3_SAMPLES": samples3,
    }


def require_editor():
    u = current_user()
    if u is None or not u["is_admin"]:
        return None
    return u


def fmt_soom(n):
    try:
        return "{:,}".format(int(n)).replace(",", " ") + " so'm"
    except Exception:
        return str(n)


# ---------------- Telegram bildirishnoma ----------------

def telegram_send(text):
    """Admin Telegramiga matnli xabar yuborish."""
    token = cfg.get("telegram_bot_token", "").strip()
    chat_id = str(cfg.get("telegram_chat_id", "")).strip()
    if not token or not chat_id:
        log.info("Telegram sozlanmagan — bildirishnoma yuborilmadi")
        return
    try:
        url = "https://api.telegram.org/bot" + token + "/sendMessage"
        data = urllib.parse.urlencode({"chat_id": chat_id, "text": text}).encode()
        req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
        urllib.request.urlopen(req, timeout=10)
        log.info("Telegram bildirishnoma yuborildi")
    except Exception as e:
        log.error("Telegram sendMessage xatosi: %s", str(e))


def telegram_send_receipt(photo_path, caption):
    """Admin Telegramiga chek rasmini yuborish."""
    token = cfg.get("telegram_bot_token", "").strip()
    chat_id = str(cfg.get("telegram_chat_id", "")).strip()
    if not token or not chat_id or not os.path.isfile(photo_path):
        return
    try:
        ext = os.path.splitext(photo_path)[1].lower()
        if ext in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp"):
            url = "https://api.telegram.org/bot" + token + "/sendPhoto"
            field = "photo"
        else:
            url = "https://api.telegram.org/bot" + token + "/sendDocument"
            field = "document"
        boundary = "----Boundary" + secrets.token_hex(8)
        with open(photo_path, "rb") as f:
            img = f.read()
        body = (
            "--" + boundary + "\r\n"
            'Content-Disposition: form-data; name="chat_id"\r\n\r\n' + chat_id + "\r\n"
            "--" + boundary + "\r\n"
            'Content-Disposition: form-data; name="caption"\r\n\r\n' + caption + "\r\n"
            "--" + boundary + "\r\n"
            'Content-Disposition: form-data; name="' + field + '"; filename="receipt' + ext + '"\r\n'
            "Content-Type: application/octet-stream\r\n\r\n"
        ).encode() + img + ("\r\n--" + boundary + "--\r\n").encode()
        req = urllib.request.Request(url, data=body, headers={"Content-Type": "multipart/form-data; boundary=" + boundary})
        urllib.request.urlopen(req, timeout=20)
        log.info("Telegram chek yuborildi")
    except Exception as e:
        log.error("Telegram sendPhoto xatosi: %s", str(e))


# ---------------- Auth pages ----------------

@app.route("/paywall")
def paywall():
    body = open(os.path.join(BASE_DIR, "paywall.html"), encoding="utf-8").read()
    error = request.args.get("error", "")
    msg = request.args.get("msg", "")
    resp = make_response(render_template_string(body, error=error, msg=msg, plans=None))
    resp.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
    resp.headers["Pragma"] = "no-cache"
    return resp


@app.route("/landing")
def landing():
    return _serve_cached("landing.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/auth/login", methods=["GET", "POST"])
def auth_login():
    if request.method == "GET":
        return redirect("/paywall")
    if rate_limited(client_key("login"), limit=10, window=600):
        log.warning("LOGIN RATE LIMITED: IP=%s", request.remote_addr)
        return redirect("/paywall?error=register&msg=Juda+ko'p+urinish.+10+daqiqadan+keyin+qayta+urinib+ko'ring")
    try:
        phone = validate_phone(request.form.get("phone", ""))
        pw = request.form.get("password", "").strip()
        if not pw:
            return redirect("/paywall?error=login")
    except ValueError as e:
        return redirect("/paywall?error=register&msg=" + urllib.parse.quote(str(e)))
    try:
        conn = db()
        u = conn.execute("SELECT * FROM users WHERE phone=?", (phone,)).fetchone()
        conn.close()
    except sqlite3.Error:
        log.error("DB error in auth_login for phone=%s", phone)
        return redirect("/paywall?error=register&msg=Server+xatosi")
    if u is None:
        log.warning("LOGIN FAIL (user not found): phone=%s", phone)
        return redirect("/paywall?error=login")
    if not verify_password(pw, u["password_hash"]):
        log.warning("LOGIN FAIL (wrong password): phone=%s id=%s", phone, u["id"])
        return redirect("/paywall?error=login")
    if u["blocked"]:
        log.warning("LOGIN BLOCKED: phone=%s", phone)
        return redirect("/paywall?error=blocked")
    session.clear()
    session["uid"] = u["id"]
    log.info("LOGIN OK: uid=%s phone=%s", u["id"], phone)
    return redirect("/")


@app.route("/auth/register", methods=["POST"])
def auth_register():
    if rate_limited(client_key("register"), limit=5, window=600):
        log.warning("REGISTER RATE LIMITED: IP=%s", request.remote_addr)
        return redirect("/paywall?error=register&msg=Juda+ko'p+urinish.+10+daqiqadan+keyin+qayta+urinib+ko'ring")
    name = request.form.get("name", "").strip()
    try:
        phone = validate_phone(request.form.get("phone", ""))
        pw = validate_password(request.form.get("password", ""))
    except ValueError as e:
        return redirect("/paywall?error=register&msg=" + urllib.parse.quote(str(e)))
    now = datetime.datetime.now()
    try:
        conn = db()
        row = conn.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
        if row is not None:
            conn.close()
            return redirect("/paywall?error=exists")
        conn.execute(
            "INSERT INTO users (phone, password_hash, name, created_at) VALUES (?,?,?,?)",
            (phone, hash_password(pw), name, now.isoformat(timespec="seconds")))
        conn.commit()
        u_new = conn.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
        conn.close()
    except sqlite3.IntegrityError:
        return redirect("/paywall?error=exists")
    except sqlite3.Error as e:
        log.error("DB error in register: %s", str(e))
        return redirect("/paywall?error=register&msg=Server+xatosi")
    session.clear()
    session["uid"] = u_new["id"]
    log.info("REGISTER OK: uid=%s phone=%s name=%s", u_new["id"], phone, name)
    return redirect("/")


# ---------------- Gating ----------------

@app.route("/")
def index_page():
    u = current_user()
    if u is None:
        return _serve_cached("landing.html")
    return gate_page("index.html")


@app.route("/index.html")
def page_index():
    return gate_page("index.html")


@app.route("/index-mobile.html")
def page_index_mobile():
    return gate_page("index-mobile.html")


@app.route("/CEFR-speaking-part1.html")
def page_cefr():
    return gate_page("CEFR-speaking-part1.html")


@app.route("/CEFR-speaking-part1-mobile.html")
def page_cefr_mobile():
    return gate_page("CEFR-speaking-part1-mobile.html")


def gate_page(fn):
    u = current_user()
    if u is None or u["blocked"]:
        return redirect("/paywall")
    return _serve_cached(fn)


def _serve_cached(fn):
    data = app.config.get("STATIC_CACHE", {}).get(fn)
    if data is None:
        return abort(404)
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


REACT_INDEX = os.path.join(BASE_DIR, "react-app", "dist", "index.html")
REACT_ASSETS = os.path.join(BASE_DIR, "react-app", "dist", "assets")


def _serve_react():
    if not os.path.isfile(REACT_INDEX):
        return _serve_cached("landing.html")
    with open(REACT_INDEX, "rb") as f:
        data = f.read()
    resp = make_response(data)
    resp.headers["Content-Type"] = "text/html; charset=utf-8"
    resp.headers["Cache-Control"] = "no-store"
    return resp


@app.route("/assets/<path:name>")
def react_assets(name):
    p = os.path.join(REACT_ASSETS, name)
    if not os.path.isfile(p):
        return abort(404)
    return send_file(p)


@app.route("/cabinet")
def cabinet():
    u = current_user()
    if u is None:
        return redirect("/paywall")
    body = open(os.path.join(BASE_DIR, "paywall.html"), encoding="utf-8").read()
    return render_template_string(body, error="", plans=None)


# ---------------- APIs for app pages ----------------

@app.route("/api/me")
def api_me():
    u = current_user()
    if u is None:
        return jsonify({"ok": False})
    return jsonify({
        "ok": True,
        "id": u["id"],
        "phone": u["phone"],
        "name": u["name"],
        "is_admin": bool(u["is_admin"]),
        "access": has_access(u),
        "lifetime": bool(u["lifetime"]),
        "access_until": u["access_until"],
        "mock_used": bool(u["mock_used"]),
    })


@app.route("/api/config-public")
def api_config_public():
    return jsonify({
        "ok": True,
        "card_number": cfg["card_number"],
        "card_holder": cfg["card_holder"],
    })


@app.route("/api/plans")
def api_plans():
    conn = db()
    rows = conn.execute("SELECT * FROM plans ORDER BY sort").fetchall()
    conn.close()
    return jsonify([{
        "id": r["id"], "name": r["name"], "price": r["price"],
        "days": r["days"], "kind": r["kind"], "price_fmt": fmt_soom(r["price"]),
    } for r in rows])


@app.route("/api/content")
def api_content():
    """Kontentni kirish huquqiga qarab qaytaradi (premium = to'liq, bepul = qisqartirilgan)."""
    data = load_content()
    u = current_user()
    access = has_access(u)
    totals = content_totals(data)
    if access:
        return jsonify({"ok": True, "access": True, "totals": totals, "data": data})
    return jsonify({"ok": True, "access": False, "totals": totals, "data": truncate_content(data)})


@app.route("/api/heartbeat", methods=["POST"])
@safe_api
def api_heartbeat():
    u = current_user()
    if u is None:
        return api_error("Kirish kerak", 401)
    now = datetime.datetime.now()
    conn = db()
    row = conn.execute(
        "SELECT last_seen, usage_seconds FROM users WHERE id=?", (u["id"],)).fetchone()
    added = 0
    if row is not None and row["last_seen"]:
        try:
            last = datetime.datetime.fromisoformat(row["last_seen"])
            delta = (now - last).total_seconds()
            if 0 < delta < 120:
                added = int(delta)
        except ValueError:
            pass
    conn.execute(
        "UPDATE users SET usage_seconds = COALESCE(usage_seconds,0) + ?, last_seen=? WHERE id=?",
        (added, now.isoformat(timespec="seconds"), u["id"]))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/api/mock/start", methods=["POST"])
@safe_api
def api_mock_start():
    u = current_user()
    if u is None:
        return api_error("Avval tizimga kiring", 401)
    conn = db()
    row = conn.execute(
        "SELECT mock_used, lifetime, access_until FROM users WHERE id=?", (u["id"],)).fetchone()
    has_full = False
    if row is not None:
        if row["lifetime"]:
            has_full = True
        elif row["access_until"]:
            try:
                if datetime.datetime.fromisoformat(row["access_until"]) > datetime.datetime.now():
                    has_full = True
            except ValueError:
                pass
    if has_full:
        conn.close()
        return jsonify({"ok": True, "mock_used": True, "access": True})
    if row is None or row["mock_used"]:
        conn.close()
        return jsonify({"ok": False, "error": "Bepul mock testdan foydalanib bo'lgansiz. Davom etish uchun obuna oling.", "mock_used": True})
    conn.execute("UPDATE users SET mock_used=1 WHERE id=?", (u["id"],))
    conn.commit()
    conn.close()
    log.info("MOCK TEST FREE USE: uid=%s", u["id"])
    return jsonify({"ok": True, "mock_used": False, "access": False})


@app.route("/api/pay/checkout", methods=["POST"])
@safe_api
def api_checkout():
    u = current_user()
    if u is None:
        return api_error("Avval tizimga kiring", 401)
    plan_id = request.form.get("plan_id")
    if not plan_id:
        raise ValueError("Tarif tanlanmagan")
    try:
        conn = db()
        plan = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
        if plan is None:
            conn.close()
            raise ValueError("Tanlangan tarif topilmadi. Iltimos sahifani yangilang.")
    except sqlite3.Error:
        raise ValueError("Server xatosi. Qayta urinib ko'ring.")
    now = datetime.datetime.now().isoformat(timespec="seconds")
    tx = secrets.token_hex(8)

    receipt_name = None
    file = request.files.get("receipt")
    if file and file.filename:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp", ".pdf"):
            conn.close()
            raise ValueError("Faqat rasm (jpg, png) yoki PDF fayl yuklang")
        if file.content_length and file.content_length > 10 * 1024 * 1024:
            conn.close()
            raise ValueError("Fayl hajmi 10 MB dan katta bo'lmasligi kerak")
        data = file.read()
        if not valid_image(data):
            conn.close()
            raise ValueError("Fayl noto'g'ri — haqiqiy rasm yoki PDF yuklang")
        file.seek(0)
        receipt_name = "rct-" + tx + ext
        try:
            file.save(os.path.join(RECEIPTS_DIR, receipt_name))
        except OSError as e:
            log.error("Failed to save receipt: %s", str(e))
            conn.close()
            raise ValueError("Chek faylini saqlashda xatolik. Qayta urinib ko'ring.")

    try:
        cur = conn.execute(
            "INSERT INTO payments (user_id, plan_id, plan_name, provider, amount, status, tx_id, receipt, created_at) VALUES (?,?,?,?,?,?,?,?,?)",
            (u["id"], plan["id"], plan["name"], "card", plan["price"], "pending", tx, receipt_name, now))
        pid = cur.lastrowid
        conn.commit()
    except sqlite3.Error as e:
        log.error("Failed to create payment: %s", str(e))
        raise ValueError("To'lov yozuvi yaratishda xatolik. Qayta urinib ko'ring.")
    finally:
        conn.close()
    log.info("PAYMENT CREATED: pid=%s uid=%d plan=%s amount=%s", pid, u["id"], plan["name"], plan["price"])
    # Telegram bildirishnoma
    try:
        telegram_send(
            "💰 Yangi to'lov!\n\n"
            "ID: #%d\n"
            "Telefon: %s\n"
            "Ism: %s\n"
            "Tarif: %s\n"
            "Summa: %s\n\n"
            "Chekni tasdiqlash: %s/admin" % (pid, u["phone"], u["name"] or "-", plan["name"], fmt_soom(plan["price"]), cfg.get("base_url", "").rstrip("/"))
        )
        if receipt_name:
            telegram_send_receipt(
                os.path.join(RECEIPTS_DIR, receipt_name),
                "Chek — to'lov #%d (%s, %s)" % (pid, u["phone"], plan["name"])
            )
    except Exception as e:
        log.error("Telegram bildirishnoma xatosi: %s", str(e))
    return jsonify({"ok": True, "payment_id": pid, "manual": True})


# ---------------- Payment confirmation ----------------

def mark_paid(payment_id):
    now = datetime.datetime.now()
    conn = db()
    p = conn.execute("SELECT * FROM payments WHERE id=?", (payment_id,)).fetchone()
    if p is None:
        conn.close()
        return
    if p["status"] == "paid":
        conn.close()
        return
    conn.execute(
        "UPDATE payments SET status='paid', paid_at=? WHERE id=?",
        (now.isoformat(timespec="seconds"), payment_id))
    user = conn.execute("SELECT * FROM users WHERE id=?", (p["user_id"],)).fetchone()
    if user is not None:
        plan = None
        if p["plan_id"]:
            plan = conn.execute("SELECT * FROM plans WHERE id=?", (p["plan_id"],)).fetchone()
        if plan is not None and plan["kind"] == "lifetime":
            conn.execute("UPDATE users SET lifetime=1 WHERE id=?", (user["id"],))
        else:
            days = plan["days"] if (plan and plan["days"]) else 30
            finish = now + datetime.timedelta(days=days)
            old = user["access_until"]
            if user["lifetime"]:
                finish = now
            elif old:
                try:
                    old_dt = datetime.datetime.fromisoformat(old)
                    base = max(old_dt, now)
                    finish = base + datetime.timedelta(days=days)
                except ValueError:
                    finish = now + datetime.timedelta(days=days)
            conn.execute(
                "UPDATE users SET access_until=? WHERE id=?",
                (finish.isoformat(timespec="seconds"), user["id"]))
    conn.commit()
    conn.close()


# Webhook'lar olib tashlandi — to'lov faqat karta + admin tasdiqlash orqali.
# (Payme/Click/Uzum webhook'lari autentifikatsiyasiz mark_paid() chaqirardi = to'lovsiz kirish teshigi)


# ---------------- Admin ----------------

@app.route("/admin")
def admin_page():
    u = current_user()
    error = request.args.get("error", "")
    phone = request.args.get("phone", "")
    body = open(os.path.join(BASE_DIR, "admin.html"), encoding="utf-8").read()
    if u is None or not u["is_admin"]:
        return render_template_string(body, is_admin=False, error=error, phone=phone, stats={})
    now = datetime.datetime.now()
    in7 = (now + datetime.timedelta(days=7)).isoformat()
    conn = db()
    total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    active = conn.execute(
        "SELECT COUNT(*) c FROM users WHERE (lifetime=1 OR (access_until IS NOT NULL AND access_until>?)) AND blocked=0",
        (now.isoformat(),)).fetchone()["c"]
    expiring = conn.execute(
        "SELECT COUNT(*) c FROM users WHERE lifetime=0 AND access_until IS NOT NULL AND access_until>? AND access_until<=? AND blocked=0",
        (now.isoformat(), in7)).fetchone()["c"]
    revenue = conn.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='paid'").fetchone()["s"]
    conn.close()
    return render_template_string(body, is_admin=True, error="", phone="", stats={
        "total_users": total_users,
        "active": active,
        "expiring": expiring,
        "revenue": fmt_soom(revenue),
    })


@app.route("/admin/login", methods=["POST"])
def admin_login():
    if rate_limited(client_key("admin_login"), limit=5, window=600):
        log.warning("ADMIN LOGIN RATE LIMITED: IP=%s", request.remote_addr)
        return redirect("/admin?error=login&msg=too-many")
    raw_phone = request.form.get("phone", "")
    raw_pw = request.form.get("password", "")
    try:
        phone = validate_phone(raw_phone)
        pw = (raw_pw or "").strip()
    except ValueError as e:
        log.warning("ADMIN LOGIN VALIDATION FAIL: raw_phone=%r reason=%s IP=%s",
                    raw_phone, str(e), request.remote_addr)
        return redirect("/admin?error=login")
    if not phone or not pw:
        log.warning("ADMIN LOGIN EMPTY FIELD: phone=%r pw_empty=%s IP=%s",
                    phone, not pw, request.remote_addr)
        return redirect("/admin?error=login&phone=" + urllib.parse.quote(phone))
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE phone=? AND is_admin=1", (phone,)).fetchone()
    conn.close()
    if u is None:
        log.warning("ADMIN LOGIN FAIL (admin not found): phone=%s IP=%s",
                    phone, request.remote_addr)
        return redirect("/admin?error=login&phone=" + urllib.parse.quote(phone))
    if not verify_password(pw, u["password_hash"]):
        log.warning("ADMIN LOGIN FAIL (wrong password): phone=%s id=%s IP=%s",
                    phone, u["id"], request.remote_addr)
        return redirect("/admin?error=login&phone=" + urllib.parse.quote(phone))
    session.clear()
    session["uid"] = u["id"]
    session.permanent = True
    log.info("ADMIN LOGIN OK: id=%s phone=%s IP=%s", u["id"], phone, request.remote_addr)
    return redirect("/admin")


@app.route("/admin/api/stats")
@safe_api
def admin_stats():
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    now = datetime.datetime.now()
    in7 = (now + datetime.timedelta(days=7)).isoformat()
    conn = db()
    total_users = conn.execute("SELECT COUNT(*) c FROM users").fetchone()["c"]
    active = conn.execute(
        "SELECT COUNT(*) c FROM users WHERE (lifetime=1 OR (access_until IS NOT NULL AND access_until>?)) AND blocked=0",
        (now.isoformat(),)).fetchone()["c"]
    expiring = conn.execute(
        "SELECT COUNT(*) c FROM users WHERE lifetime=0 AND access_until IS NOT NULL AND access_until>? AND access_until<=? AND blocked=0",
        (now.isoformat(), in7)).fetchone()["c"]
    revenue = conn.execute(
        "SELECT COALESCE(SUM(amount),0) s FROM payments WHERE status='paid'").fetchone()["s"]
    today = now.strftime("%Y-%m-%d")
    conn.close()
    return jsonify({
        "ok": True,
        "total_users": total_users,
        "active": active,
        "expiring": expiring,
        "revenue": fmt_soom(revenue),
        "today": today,
    })


@app.route("/admin/api/users")
@safe_api
def admin_users():
    if require_editor() is None:
        return api_error("Ruxsat yo'q", 401)
    q = request.args.get("q", "").strip()
    conn = db()
    if q:
        rows = conn.execute(
            "SELECT id, phone, name, is_admin, blocked, lifetime, access_until, usage_seconds, last_seen, created_at FROM users WHERE phone LIKE ? OR name LIKE ? ORDER BY id DESC LIMIT 500",
            ("%" + q + "%", "%" + q + "%")).fetchall()
    else:
        rows = conn.execute(
            "SELECT id, phone, name, is_admin, blocked, lifetime, access_until, usage_seconds, last_seen, created_at FROM users ORDER BY id DESC LIMIT 500").fetchall()
    conn.close()
    return jsonify({"ok": True, "users": [dict(r) for r in rows]})


@app.route("/admin/api/users/add", methods=["POST"])
@safe_api
def admin_add_user():
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    phone = request.form.get("phone", "").strip()
    pw = request.form.get("password", "")
    name = request.form.get("name", "").strip()
    if not phone or not pw:
        return jsonify({"ok": False, "error": "Telefon va parol kiritilishi shart"})
    conn = db()
    if conn.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone():
        conn.close()
        return jsonify({"ok": False, "error": "Bunday telefon allaqachon bor"})
    conn.execute(
        "INSERT INTO users (phone, password_hash, name, created_at) VALUES (?,?,?,?)",
        (phone, hash_password(pw), name, datetime.datetime.now().isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/admin/api/users/<int:uid>/extend", methods=["POST"])
@safe_api
def admin_extend(uid):
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    days = request.form.get("days", type=int, default=30)
    if not days or days <= 0:
        return jsonify({"ok": False, "error": "Noto'g'ri kun"})
    now = datetime.datetime.now()
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if u is None:
        conn.close()
        return jsonify({"ok": False, "error": "Foydalanuvchi topilmadi"})
    old = u["access_until"]
    base = datetime.datetime.fromisoformat(old) if old else now
    start = max(base, now)
    finish = (start + datetime.timedelta(days=days)).isoformat(timespec="seconds")
    log.info("ADMIN EXTEND: uid=%s +%ddays by admin=%s", uid, days, session.get("uid")); conn.execute("UPDATE users SET access_until=? WHERE id=?", (finish, uid))
    conn.execute("UPDATE users SET lifetime=0 WHERE id=? AND lifetime=0", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True, "until": finish})


@app.route("/admin/api/users/<int:uid>/grant", methods=["POST"])
@safe_api
def admin_grant(uid):
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    plan_id = request.form.get("plan_id", type=int)
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if u is None:
        conn.close()
        return jsonify({"ok": False, "error": "Foydalanuvchi topilmadi"})
    plan = None
    if plan_id:
        plan = conn.execute("SELECT * FROM plans WHERE id=?", (plan_id,)).fetchone()
    days = (plan["days"] if plan and plan["days"] else 30)
    now = datetime.datetime.now()
    old = u["access_until"]
    try:
        base = datetime.datetime.fromisoformat(old) if old else now
        start = max(base, now)
    except ValueError:
        start = now
    finish = (start + datetime.timedelta(days=days)).isoformat(timespec="seconds")
    conn.execute("UPDATE users SET access_until=? WHERE id=?", (finish, uid))
    conn.execute(
        "INSERT INTO payments (user_id, plan_id, plan_name, provider, amount, status, created_at, paid_at) VALUES (?,?,?,?,?,?,?,?)",
        (uid, plan["id"] if plan else None, plan["name"] if plan else "Qo'lda ruxsat",
         "telegram", plan["price"] if plan else 0, "paid",
         now.isoformat(timespec="seconds"), now.isoformat(timespec="seconds")))
    conn.commit()
    conn.close()
    log.info("ADMIN GRANT: uid=%s plan=%s by admin=%s",
             uid, (plan["name"] if plan else "Qo'lda"), session.get("uid"))
    return jsonify({"ok": True, "until": finish, "days": days})


@app.route("/admin/api/users/<int:uid>/lifetime", methods=["POST"])
@safe_api
def admin_lifetime(uid):
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    conn = db()
    conn.execute("UPDATE users SET lifetime=1 WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/admin/api/users/<int:uid>/block", methods=["POST"])
@safe_api
def admin_block(uid):
    u = require_editor()
    if u is None:
        return jsonify({"ok": False}), 401
    conn = db()
    target = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if target is not None and target["id"] == u["id"]:
        conn.close()
        return jsonify({"ok": False, "error": "O'zingizni bloklay olmaysiz"})
    log.warning("ADMIN TOGGLE BLOCK: uid=%s by admin=%s", uid, session.get("uid")); conn.execute("UPDATE users SET blocked = 1 - blocked WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/admin/api/users/<int:uid>/delete", methods=["POST"])
@safe_api
def admin_delete(uid):
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    conn = db()
    u = conn.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    if u is None:
        conn.close()
        return jsonify({"ok": False, "error": "Topilmadi"})
    if u["is_admin"]:
        n_admin = conn.execute("SELECT COUNT(*) c FROM users WHERE is_admin=1").fetchone()["c"]
        if n_admin <= 1:
            conn.close()
            return jsonify({"ok": False, "error": "So'nggi adminni o'chirib bo'lmaydi"})
    log.warning("ADMIN DELETE USER: uid=%s by admin=%s", uid, session.get("uid")); conn.execute("DELETE FROM users WHERE id=?", (uid,))
    conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/admin/api/payments")
@safe_api
def admin_payments():
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    st = request.args.get("status", "")
    conn = db()
    if st:
        rows = conn.execute(
            "SELECT p.*, u.phone FROM payments p LEFT JOIN users u ON u.id=p.user_id WHERE p.status=? ORDER BY p.id DESC LIMIT 500",
            (st,)).fetchall()
    else:
        rows = conn.execute(
            "SELECT p.*, u.phone FROM payments p LEFT JOIN users u ON u.id=p.user_id ORDER BY p.id DESC LIMIT 500").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["phone"] = d.get("phone") or "—"
        d["amount_fmt"] = fmt_soom(d["amount"])
        d["receipt_url"] = ("/admin/api/receipts/" + d["receipt"]) if d.get("receipt") else None
        out.append(d)
    return jsonify({"ok": True, "payments": out})


@app.route("/admin/api/payments/<int:pid>/confirm", methods=["POST"])
@safe_api
def admin_confirm_payment(pid):
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    log.info("ADMIN CONFIRM PAYMENT: pid=%s by uid=%s", pid, session.get("uid")); mark_paid(pid); return jsonify({"ok": True})


@app.route("/admin/api/receipts/<path:name>")
def admin_receipt(name):
    if require_editor() is None:
        return redirect("/admin")
    safe = os.path.basename(name)
    if safe != name or ".." in name:
        return abort(404)
    p = os.path.join(RECEIPTS_DIR, safe)
    if not os.path.isfile(p):
        return abort(404)
    return send_file(p)


@app.route("/admin/api/plans")
@safe_api
def admin_plans():
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    conn = db()
    rows = conn.execute("SELECT * FROM plans ORDER BY sort").fetchall()
    conn.close()
    out = []
    for r in rows:
        d = dict(r)
        d["price_fmt"] = fmt_soom(d["price"])
        out.append(d)
    return jsonify({"ok": True, "plans": out})


@app.route("/admin/api/plans/<int:pid>", methods=["POST"])
@safe_api
def admin_update_plan(pid):
    if require_editor() is None:
        return jsonify({"ok": False}), 401
    name = request.form.get("name", "").strip()
    price = request.form.get("price", type=int, default=0)
    days = request.form.get("days", type=int)
    conn = db()
    if name and price > 0:
        conn.execute("UPDATE plans SET name=?, price=?, days=? WHERE id=?", (name, price, days, pid))
        conn.commit()
    conn.close()
    return jsonify({"ok": True})


@app.route("/admin/api/config", methods=["GET", "POST"])
@safe_api
def admin_config():
    u = require_editor()
    if u is None:
        return jsonify({"ok": False}), 401
    if request.method == "POST":
        card = request.form.get("card_number", "").strip()
        holder = request.form.get("card_holder", "").strip()
        base_url = request.form.get("base_url", "").strip()
        tg_token = request.form.get("telegram_bot_token", "").strip()
        tg_chat = request.form.get("telegram_chat_id", "").strip()
        cfg["card_number"] = card or cfg["card_number"]
        cfg["card_holder"] = holder or cfg["card_holder"]
        if base_url:
            cfg["base_url"] = base_url
        if tg_token:
            cfg["telegram_bot_token"] = tg_token
        if tg_chat:
            cfg["telegram_chat_id"] = tg_chat
        save_config(cfg)
        return jsonify({"ok": True})
    return jsonify({
        "ok": True,
        "card_number": cfg["card_number"],
        "card_holder": cfg["card_holder"],
        "base_url": cfg["base_url"],
        "telegram_bot_token": cfg.get("telegram_bot_token", ""),
        "telegram_chat_id": cfg.get("telegram_chat_id", ""),
    })


@app.route("/admin/api/backup")
def admin_backup():
    u = require_editor()
    if u is None:
        return redirect("/admin")
    if not os.path.exists(DB_FILE):
        return abort(404)
    ts = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
    return send_file(DB_FILE, as_attachment=True,
                     download_name="site-backup-%s.db" % ts)


# ---------------- Static assets ----------------

# XAVFSIZLIK: whitelist yondashuv — faqat ruxsat berilgan fayllar/xususiyatlar xizmat qilinadi.
# Blacklist (qora ro'yxat) xavfli edi: yangi fayl qo'shilsa (.bat/.vbs/.exe/.pdf va h.k.) oshkor bo'lardi.
ALLOWED_PAGES = {
    "index.html", "index-mobile.html", "landing.html", "paywall.html", "admin.html",
    "cefr-speaking-part1.html", "cefr-speaking-part1-mobile.html", "signal-preview.html",
}
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp", ".gif")


def _allowed_static(low):
    if low in ALLOWED_PAGES:
        return True
    if (low.startswith("part12/") or low.startswith("part3/")) and low.endswith(IMG_EXT):
        return True
    if (low.startswith("signal") or low == "beep.wav") and low.endswith(".wav"):
        return True
    return False


@app.route("/<path:filename>")
def static_assets(filename):
    if "../" in filename or filename.startswith("/"):
        return abort(404)
    low = filename.lower()
    if not _allowed_static(low):
        return abort(404)
    return send_from_directory(BASE_DIR, filename)


def create_admin_cli():
    import sys
    args = [a for a in sys.argv[1:]]
    if len(args) >= 2 and args[0] == "create-admin":
        if len(args) < 3 or len(args[2].strip()) < 6:
            print("Xato: kuchli parol kerak (kamida 6 belgi).")
            print("Ishlatish: python app.py create-admin <telefon> <parol>")
            return True
        init_db()
        phone = args[1]
        pw = args[2]
        conn = db()
        row = conn.execute("SELECT id FROM users WHERE phone=?", (phone,)).fetchone()
        if row is None:
            conn.execute(
                "INSERT INTO users (phone, password_hash, name, is_admin, created_at) VALUES (?,?,?,1,?)",
                (phone, hash_password(pw), "Admin",
                 datetime.datetime.now().isoformat(timespec="seconds")))
            print("Admin yaratildi:", phone)
        else:
            conn.execute("UPDATE users SET is_admin=1, password_hash=? WHERE id=?",
                         (hash_password(pw), row["id"]))
            print("Admin yangilandi:", phone)
        conn.commit()
        conn.close()
        return True
    return False


def main():
    if create_admin_cli():
        return
    init_db()
    atexit.register(lambda: log.info("Server shutting down"))
    log.info("Server running on https://0.0.0.0:8443")
    app.run(host="0.0.0.0", port=8443)


if __name__ == "__main__":
    main()
