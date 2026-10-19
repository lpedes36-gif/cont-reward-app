import os, sqlite3, secrets, hmac, hashlib
from datetime import datetime, date
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash, g, abort
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get("SECRET_KEY") or "dev-only-change-this-secret-key"
DB_PATH = os.environ.get("DATABASE_PATH", os.path.join(os.path.dirname(__file__), "mr_cont.db"))
ADMIN_USERNAME = os.environ.get("ADMIN_USERNAME", "admin")
ADMIN_PASSWORD = os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")

def db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db

@app.teardown_appcontext
def close_db(_error=None):
    conn = g.pop("db", None)
    if conn is not None:
        conn.close()

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript("""
    CREATE TABLE IF NOT EXISTS users (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      username TEXT NOT NULL UNIQUE,
      password_hash TEXT NOT NULL,
      referral_code TEXT NOT NULL UNIQUE,
      referred_by INTEGER REFERENCES users(id),
      points INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS ledger (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id),
      amount INTEGER NOT NULL,
      reason TEXT NOT NULL,
      created_at TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS tasks (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      description TEXT NOT NULL,
      points INTEGER NOT NULL CHECK(points > 0),
      active INTEGER NOT NULL DEFAULT 1
    );
    CREATE TABLE IF NOT EXISTS task_claims (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      user_id INTEGER NOT NULL REFERENCES users(id),
      task_id INTEGER NOT NULL REFERENCES tasks(id),
      claim_date TEXT NOT NULL,
      UNIQUE(user_id, task_id, claim_date)
    );
    CREATE TABLE IF NOT EXISTS daily_claims (
      user_id INTEGER NOT NULL REFERENCES users(id),
      claim_date TEXT NOT NULL,
      PRIMARY KEY(user_id, claim_date)
    );
    """)
    count = conn.execute("SELECT COUNT(*) FROM tasks").fetchone()[0]
    if count == 0:
        conn.executemany(
          "INSERT INTO tasks(title, description, points) VALUES(?,?,?)",
          [
            ("Kunjungi halaman reward", "Buka halaman reward dan klaim tugas demo ini.", 15),
            ("Pelajari keamanan akun", "Gunakan kata sandi unik dan jangan bagikan kode login.", 25),
            ("Jelajahi dashboard", "Lihat saldo poin dan riwayat aktivitas akun.", 10),
          ])
    conn.commit()
    conn.close()

def now_text():
    return datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")

def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(24)
    return session["_csrf"]

app.jinja_env.globals["csrf_token"] = csrf_token

@app.before_request
def protect_post():
    if request.method == "POST":
        token = request.form.get("_csrf", "")
        expected = session.get("_csrf", "")
        if not token or not expected or not hmac.compare_digest(token, expected):
            abort(400, "Token keamanan tidak valid. Muat ulang halaman lalu coba lagi.")

def login_required(fn):
    @wraps(fn)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            flash("Silakan masuk terlebih dahulu.", "info")
            return redirect(url_for("login"))
        return fn(*args, **kwargs)
    return wrapped

def current_user():
    uid = session.get("user_id")
    if not uid:
        return None
    return db().execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()

@app.context_processor
def inject_user():
    return {"current_user": current_user()}

@app.route("/")
def index():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return render_template("index.html")

@app.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        referral = request.form.get("ref", "").strip().upper()
        if not (3 <= len(username) <= 24) or not username.replace("_", "").isalnum():
            flash("Username harus 3–24 karakter, hanya huruf, angka, dan underscore.", "error")
            return render_template("register.html")
        if len(password) < 8:
            flash("Kata sandi minimal 8 karakter.", "error")
            return render_template("register.html")
        conn = db()
        if conn.execute("SELECT 1 FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone():
            flash("Username sudah digunakan.", "error")
            return render_template("register.html")
        referred_by = None
        if referral:
            ref_user = conn.execute("SELECT id FROM users WHERE referral_code=?", (referral,)).fetchone()
            if not ref_user:
                flash("Kode referral tidak ditemukan. Kosongkan jika tidak punya.", "error")
                return render_template("register.html")
            referred_by = ref_user["id"]
        code = secrets.token_hex(4).upper()
        while conn.execute("SELECT 1 FROM users WHERE referral_code=?", (code,)).fetchone():
            code = secrets.token_hex(4).upper()
        try:
            cur = conn.execute(
              "INSERT INTO users(username,password_hash,referral_code,referred_by,created_at) VALUES(?,?,?,?,?)",
              (username, generate_password_hash(password), code, referred_by, now_text()))
            uid = cur.lastrowid
            if referred_by:
                conn.execute("UPDATE users SET points=points+50 WHERE id=?", (referred_by,))
                conn.execute("INSERT INTO ledger(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                             (referred_by, 50, "Bonus referral demo", now_text()))
                conn.execute("UPDATE users SET points=points+25 WHERE id=?", (uid,))
                conn.execute("INSERT INTO ledger(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                             (uid, 25, "Bonus pendaftaran via referral demo", now_text()))
            conn.commit()
        except sqlite3.IntegrityError:
            conn.rollback()
            flash("Username atau kode referral bermasalah.", "error")
            return render_template("register.html")
        session.clear()
        session["user_id"] = uid
        flash("Akun berhasil dibuat. Selamat datang!", "success")
        return redirect(url_for("dashboard"))
    ref = request.args.get("ref", "")
    return render_template("register.html", ref=ref)

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        user = db().execute("SELECT * FROM users WHERE username=? COLLATE NOCASE", (username,)).fetchone()
        if not user or not check_password_hash(user["password_hash"], password):
            flash("Username atau kata sandi salah.", "error")
            return render_template("login.html")
        session.clear()
        session["user_id"] = user["id"]
        flash("Berhasil masuk.", "success")
        return redirect(url_for("dashboard"))
    return render_template("login.html")

@app.route("/logout", methods=["POST"])
def logout():
    session.clear()
    flash("Anda telah keluar.", "info")
    return redirect(url_for("index"))

@app.route("/dashboard")
@login_required
def dashboard():
    user = current_user()
    today = date.today().isoformat()
    claimed = db().execute("SELECT 1 FROM daily_claims WHERE user_id=? AND claim_date=?", (user["id"], today)).fetchone()
    ledger = db().execute("SELECT * FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 8", (user["id"],)).fetchall()
    referrals = db().execute("SELECT COUNT(*) FROM users WHERE referred_by=?", (user["id"],)).fetchone()[0]
    return render_template("dashboard.html", user=user, daily_claimed=bool(claimed), ledger=ledger, referrals=referrals)

@app.route("/daily-claim", methods=["POST"])
@login_required
def daily_claim():
    user = current_user()
    today = date.today().isoformat()
    conn = db()
    try:
        conn.execute("INSERT INTO daily_claims(user_id, claim_date) VALUES(?,?)", (user["id"], today))
        conn.execute("UPDATE users SET points=points+20 WHERE id=?", (user["id"],))
        conn.execute("INSERT INTO ledger(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                     (user["id"], 20, "Bonus harian demo", now_text()))
        conn.commit()
        flash("Berhasil klaim 20 poin demo hari ini!", "success")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("Bonus harian sudah diklaim hari ini.", "info")
    return redirect(url_for("dashboard"))

@app.route("/tasks")
@login_required
def tasks():
    user = current_user()
    today = date.today().isoformat()
    rows = db().execute("""
      SELECT t.*, CASE WHEN c.id IS NULL THEN 0 ELSE 1 END AS claimed
      FROM tasks t LEFT JOIN task_claims c
      ON c.task_id=t.id AND c.user_id=? AND c.claim_date=?
      WHERE t.active=1 ORDER BY t.id
    """, (user["id"], today)).fetchall()
    return render_template("tasks.html", tasks=rows)

@app.route("/tasks/<int:task_id>/claim", methods=["POST"])
@login_required
def claim_task(task_id):
    user = current_user()
    today = date.today().isoformat()
    conn = db()
    task = conn.execute("SELECT * FROM tasks WHERE id=? AND active=1", (task_id,)).fetchone()
    if not task:
        abort(404)
    try:
        conn.execute("INSERT INTO task_claims(user_id,task_id,claim_date) VALUES(?,?,?)",
                     (user["id"], task_id, today))
        conn.execute("UPDATE users SET points=points+? WHERE id=?", (task["points"], user["id"]))
        conn.execute("INSERT INTO ledger(user_id,amount,reason,created_at) VALUES(?,?,?,?)",
                     (user["id"], task["points"], "Tugas demo: " + task["title"], now_text()))
        conn.commit()
        flash(f"Berhasil klaim {task['points']} poin demo.", "success")
    except sqlite3.IntegrityError:
        conn.rollback()
        flash("Tugas ini sudah diklaim hari ini.", "info")
    return redirect(url_for("tasks"))

@app.route("/history")
@login_required
def history():
    rows = db().execute("SELECT * FROM ledger WHERE user_id=? ORDER BY id DESC LIMIT 100",
                        (session["user_id"],)).fetchall()
    return render_template("history.html", ledger=rows)

@app.route("/admin", methods=["GET", "POST"])
def admin():
    if not session.get("is_admin"):
        if request.method == "POST":
            username = request.form.get("username", "")
            password = request.form.get("password", "")
            expected_hash = os.environ.get("ADMIN_PASSWORD_HASH")
            ok = (username == ADMIN_USERNAME and
                  ((check_password_hash(expected_hash, password) if expected_hash else
                    (not os.environ.get("ADMIN_PASSWORD") and False) or
                    (not expected_hash and hmac.compare_digest(password, ADMIN_PASSWORD)))))
            if ok:
                session["is_admin"] = True
                return redirect(url_for("admin"))
            flash("Login admin tidak valid.", "error")
        return render_template("admin_login.html")
    conn = db()
    if request.method == "POST":
        title = request.form.get("title", "").strip()
        description = request.form.get("description", "").strip()
        try:
            points = int(request.form.get("points", "0"))
        except ValueError:
            points = 0
        if not title or not description or not 1 <= points <= 10000:
            flash("Isi semua kolom. Poin harus 1–10000.", "error")
        else:
            conn.execute("INSERT INTO tasks(title,description,points) VALUES(?,?,?)",
                         (title[:100], description[:300], points))
            conn.commit()
            flash("Tugas berhasil ditambahkan.", "success")
        return redirect(url_for("admin"))
    users = conn.execute("SELECT id,username,points,referral_code,created_at FROM users ORDER BY id DESC LIMIT 100").fetchall()
    tasks = conn.execute("SELECT * FROM tasks ORDER BY id DESC").fetchall()
    return render_template("admin.html", users=users, tasks=tasks)

@app.route("/admin/logout", methods=["POST"])
def admin_logout():
    session.pop("is_admin", None)
    return redirect(url_for("index"))

@app.errorhandler(400)
def bad_request(error):
    return render_template("error.html", code=400, message=getattr(error, "description", "Permintaan tidak valid.")), 400

@app.errorhandler(404)
def not_found(error):
    return render_template("error.html", code=404, message="Halaman tidak ditemukan."), 404

with app.app_context():
    init_db()

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", "5000")), debug=False)
