"""Plateforme de révision #AlmaUteam4ever — Flask + SQLAlchemy + coach IA (Anthropic)."""
import os
import re
import json
import glob
import time
import random
import datetime as dt
from collections import defaultdict

from flask import Flask, request, session, jsonify, render_template, Response
import drive
from werkzeug.security import generate_password_hash, check_password_hash
from sqlalchemy import (
    create_engine, MetaData, Table, Column, Integer, String, Boolean, DateTime,
    ForeignKey, select, insert, update, delete, func, Index, Text,
)

BASE = os.path.dirname(os.path.abspath(__file__))

# --------------------------------------------------------------------------- config
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///" + os.path.join(BASE, "data.db"))
if DATABASE_URL.startswith("postgres://"):
    DATABASE_URL = DATABASE_URL.replace("postgres://", "postgresql+psycopg2://", 1)
elif DATABASE_URL.startswith("postgresql://"):
    DATABASE_URL = DATABASE_URL.replace("postgresql://", "postgresql+psycopg2://", 1)

COACH_MODEL = os.environ.get("COACH_MODEL", "claude-sonnet-5-5")
COACH_DAILY_LIMIT = int(os.environ.get("COACH_DAILY_LIMIT", "40"))
ADMIN_USERS = {u.strip().lower() for u in os.environ.get("ADMIN_USERS", "sixte").split(",") if u.strip()}

app = Flask(__name__)
app.config.update(
    SECRET_KEY=os.environ.get("SECRET_KEY", "dev-only-change-me"),
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    SESSION_COOKIE_SECURE=bool(os.environ.get("RENDER") or os.environ.get("FORCE_HTTPS")),
    PERMANENT_SESSION_LIFETIME=dt.timedelta(days=30),
    JSON_AS_ASCII=False,
    MAX_CONTENT_LENGTH=drive.MAX_UPLOAD + 1024 * 1024,
)

# --------------------------------------------------------------------------- database
engine = create_engine(DATABASE_URL, pool_pre_ping=True, future=True)
meta = MetaData()
users = Table(
    "rev_users", meta,
    Column("id", Integer, primary_key=True),
    Column("username", String(60), unique=True, nullable=False),
    Column("display_name", String(80), nullable=False),
    Column("password_hash", String(255), nullable=False),
    Column("is_admin", Boolean, default=False, nullable=False),
    Column("created_at", DateTime, default=dt.datetime.utcnow),
)
attempts = Table(
    "rev_attempts", meta,
    Column("id", Integer, primary_key=True),
    Column("user_id", Integer, ForeignKey("rev_users.id"), nullable=False),
    Column("subject", String(60), nullable=False),
    Column("qid", String(40), nullable=False),
    Column("correct", Boolean, nullable=False),
    Column("ts", DateTime, default=dt.datetime.utcnow, nullable=False),
    Index("ix_rev_attempts_user", "user_id"),
)
chat_usage = Table(
    "rev_chat_usage", meta,
    Column("user_id", Integer, ForeignKey("rev_users.id"), primary_key=True),
    Column("day", String(10), primary_key=True),
    Column("n", Integer, default=0, nullable=False),
)
events = Table(
    "rev_events", meta,
    Column("id", Integer, primary_key=True),
    Column("title", String(140), nullable=False),
    Column("description", Text, default="", nullable=False),
    Column("start", DateTime, nullable=False),
    Column("end", DateTime),
    Column("all_day", Boolean, default=False, nullable=False),
    Column("subjects", String(200), default="", nullable=False),      # ids séparés par des virgules ; vide = général
    Column("everyone", Boolean, default=False, nullable=False),
    Column("created_by", Integer, ForeignKey("rev_users.id"), nullable=False),
    Column("created_at", DateTime, default=dt.datetime.utcnow),
    Index("ix_rev_events_start", "start"),
)
event_people = Table(
    "rev_event_people", meta,
    Column("event_id", Integer, ForeignKey("rev_events.id", ondelete="CASCADE"), primary_key=True),
    Column("user_id", Integer, ForeignKey("rev_users.id"), primary_key=True),
)


def init_db():
    meta.create_all(engine)
    seed = os.environ.get("SEED_USERS", "")  # "Sixte:motdepasse,Ulysse:motdepasse,..."
    with engine.begin() as c:
        for item in [s for s in seed.split(",") if ":" in s]:
            name, pwd = item.split(":", 1)
            name, pwd = name.strip(), pwd.strip()
            if not name or not pwd:
                continue
            uname = name.lower()
            exists = c.execute(select(users.c.id).where(users.c.username == uname)).first()
            if not exists:
                c.execute(insert(users).values(
                    username=uname, display_name=name[:1].upper() + name[1:],
                    password_hash=generate_password_hash(pwd),
                    is_admin=uname in ADMIN_USERS))


# --------------------------------------------------------------------------- content
SUBJECT_ORDER = ["global-marketing", "ai-marketing", "customer-development", "lodging"]
SUBJECTS, QUESTIONS = {}, {}


def load_content():
    for f in glob.glob(os.path.join(BASE, "content", "*.json")):
        d = json.load(open(f, encoding="utf-8"))
        SUBJECTS[d["id"]] = d
        for q in d["qcm"]:
            QUESTIONS[q["id"]] = dict(q, subject=d["id"])


def ordered_subjects():
    ids = [s for s in SUBJECT_ORDER if s in SUBJECTS] + [s for s in SUBJECTS if s not in SUBJECT_ORDER]
    return [SUBJECTS[i] for i in ids]


LEVELS = [(95, "Maître", "🏆"), (80, "Expert", "🔥"), (60, "Confirmé", "⭐"), (40, "Avancé", "📈"),
          (20, "Apprenti", "🌿"), (0, "Débutant", "🌱")]


def level_for(pct):
    for th, name, icon in LEVELS:
        if pct >= th:
            return {"name": name, "icon": icon}


def user_progress(rows):
    """rows: liste de (subject, qid, correct, ts) triée par ts. -> stats par matière et par fiche."""
    last, total_correct, answered_total = {}, defaultdict(int), defaultdict(int)
    for subject, qid, correct, ts in rows:
        if qid not in QUESTIONS:
            continue
        last[qid] = correct
        answered_total[subject] += 1
        if correct:
            total_correct[subject] += 1
    out = {}
    for s in ordered_subjects():
        qs = s["qcm"]
        seen = [q for q in qs if q["id"] in last]
        mastered = [q for q in seen if last[q["id"]]]
        pct = round(100 * len(mastered) / len(qs)) if qs else 0
        fiches = {}
        for fi in s["fiches"]:
            fq = [q for q in qs if q["fiche"] == fi["id"]]
            fm = [q for q in fq if last.get(q["id"])]
            fiches[fi["id"]] = {"total": len(fq), "mastered": len(fm),
                                "seen": len([q for q in fq if q["id"] in last])}
        out[s["id"]] = {
            "total": len(qs), "seen": len(seen), "mastered": len(mastered), "pct": pct,
            "level": level_for(pct), "answers": answered_total[s["id"]],
            "correct_answers": total_correct[s["id"]],
            "score": len(mastered) * 10 + total_correct[s["id"]],
            "fiches": fiches,
        }
    return out


def attempts_of(conn, user_id):
    r = conn.execute(select(attempts.c.subject, attempts.c.qid, attempts.c.correct, attempts.c.ts)
                     .where(attempts.c.user_id == user_id).order_by(attempts.c.ts, attempts.c.id))
    return [tuple(x) for x in r]


# --------------------------------------------------------------------------- auth helpers
FAILS = defaultdict(list)


def throttled(key, limit=6, window=600):
    now = time.time()
    FAILS[key] = [t for t in FAILS[key] if now - t < window]
    return len(FAILS[key]) >= limit


def current_user():
    uid = session.get("uid")
    if not uid:
        return None
    with engine.connect() as c:
        row = c.execute(select(users).where(users.c.id == uid)).mappings().first()
    return dict(row) if row else None


def login_required(fn):
    import functools

    @functools.wraps(fn)
    def w(*a, **k):
        u = current_user()
        if not u:
            return jsonify(error="Connexion requise"), 401
        return fn(u, *a, **k)
    return w


def admin_required(fn):
    import functools

    @functools.wraps(fn)
    def w(u, *a, **k):
        if not u["is_admin"]:
            return jsonify(error="Réservé à l'admin"), 403
        return fn(u, *a, **k)
    return login_required(w)


@app.before_request
def csrf_guard():
    if request.method in ("POST", "PUT", "DELETE") and request.path.startswith("/api/"):
        if request.headers.get("X-Requested-With") != "fetch":
            return jsonify(error="Requête refusée"), 403


@app.after_request
def headers(resp):
    resp.headers["X-Content-Type-Options"] = "nosniff"
    resp.headers["X-Frame-Options"] = "DENY"
    resp.headers["Referrer-Policy"] = "same-origin"
    if request.path.startswith("/api/"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


# --------------------------------------------------------------------------- pages & auth API
@app.get("/")
def index():
    return render_template("index.html")


@app.get("/healthz")
def healthz():
    return "ok"


@app.post("/api/login")
def api_login():
    data = request.get_json(silent=True) or {}
    uname = str(data.get("username", "")).strip().lower()
    pwd = str(data.get("password", ""))
    key = (request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip(), uname)
    if throttled(key):
        return jsonify(error="Trop d'essais. Réessaie dans 10 minutes."), 429
    with engine.connect() as c:
        row = c.execute(select(users).where(users.c.username == uname)).mappings().first()
    if not row or not check_password_hash(row["password_hash"], pwd):
        FAILS[key].append(time.time())
        return jsonify(error="Nom ou mot de passe incorrect."), 401
    session.clear()
    session["uid"] = row["id"]
    session.permanent = True
    return jsonify(ok=True)


@app.post("/api/logout")
def api_logout():
    session.clear()
    return jsonify(ok=True)


@app.get("/api/me")
def api_me():
    u = current_user()
    if not u:
        return jsonify(user=None)
    return jsonify(user={"name": u["display_name"], "username": u["username"], "is_admin": u["is_admin"]},
                   coach_enabled=bool(os.environ.get("ANTHROPIC_API_KEY")), coach_limit=COACH_DAILY_LIMIT)


@app.post("/api/password")
@login_required
def api_password(u):
    data = request.get_json(silent=True) or {}
    old, new = str(data.get("old", "")), str(data.get("new", ""))
    if not check_password_hash(u["password_hash"], old):
        return jsonify(error="Ancien mot de passe incorrect."), 400
    if len(new) < 6:
        return jsonify(error="Le nouveau mot de passe doit faire au moins 6 caractères."), 400
    with engine.begin() as c:
        c.execute(update(users).where(users.c.id == u["id"]).values(password_hash=generate_password_hash(new)))
    return jsonify(ok=True)


# --------------------------------------------------------------------------- subjects API
@app.get("/api/subjects")
@login_required
def api_subjects(u):
    with engine.connect() as c:
        prog = user_progress(attempts_of(c, u["id"]))
    out = []
    for s in ordered_subjects():
        out.append({"id": s["id"], "emoji": s["emoji"], "name": s["name"], "teacher": s["teacher"],
                    "n_fiches": len(s["fiches"]), "n_qcm": len(s["qcm"]), "progress": prog[s["id"]]})
    overall = round(sum(p["pct"] for p in prog.values()) / len(prog)) if prog else 0
    return jsonify(subjects=out, overall=overall, level=level_for(overall),
                   score=sum(p["score"] for p in prog.values()))


@app.get("/api/subjects/<sid>")
@login_required
def api_subject(u, sid):
    s = SUBJECTS.get(sid)
    if not s:
        return jsonify(error="Matière inconnue"), 404
    with engine.connect() as c:
        prog = user_progress(attempts_of(c, u["id"]))[sid]
    fiches = [{"id": f["id"], "title": f["title"], "body": f["body"], "n_qcm": prog["fiches"][f["id"]]["total"],
               "mastered": prog["fiches"][f["id"]]["mastered"]} for f in s["fiches"]]
    return jsonify(id=s["id"], emoji=s["emoji"], name=s["name"], teacher=s["teacher"],
                   coverage=s["coverage"], fiches=fiches, progress=prog)


# --------------------------------------------------------------------------- quiz API
def pick_questions(subject, user_rows, n, mode, fiche):
    pool = [q for q in SUBJECTS[subject]["qcm"] if not fiche or q["fiche"] == fiche]
    history = defaultdict(list)
    for s_, qid, correct, ts in user_rows:
        history[qid].append(correct)
    weights = []
    for q in pool:
        h = history.get(q["id"], [])
        if not h:
            w = 3.0                      # jamais vue
        elif not h[-1]:
            w = 5.0                      # ratée à la dernière tentative
        else:
            w = 1.0 / (1 + sum(h))       # réussie : de moins en moins souvent
        if mode == "weak":                # ne cibler que les questions ratées (puis, à défaut, les jamais vues)
            w = 6.0 if (h and not h[-1]) else (0.05 if not h else 0.02)
        weights.append(w)
    n = max(1, min(n, len(pool)))
    chosen, idx = [], list(range(len(pool)))
    for _ in range(n):
        tot = sum(weights[i] for i in idx)
        r, acc = random.random() * tot, 0
        for i in idx:
            acc += weights[i]
            if acc >= r:
                chosen.append(pool[i])
                idx.remove(i)
                break
    random.shuffle(chosen)
    return chosen


@app.post("/api/quiz/start")
@login_required
def api_quiz_start(u):
    data = request.get_json(silent=True) or {}
    sid = data.get("subject")
    if sid not in SUBJECTS:
        return jsonify(error="Matière inconnue"), 404
    try:
        n = int(data.get("n", 10))
    except (TypeError, ValueError):
        n = 10
    with engine.connect() as c:
        rows = attempts_of(c, u["id"])
    qs = pick_questions(sid, rows, n, data.get("mode", "mixed"), data.get("fiche") or None)
    fiche_title = {f["id"]: f["title"] for f in SUBJECTS[sid]["fiches"]}
    payload = []
    for q in qs:
        opts = [q["correct"]] + list(q["wrong"])
        random.shuffle(opts)
        payload.append({"id": q["id"], "q": q["q"], "options": opts, "fiche": q["fiche"],
                        "fiche_title": fiche_title[q["fiche"]]})
    return jsonify(questions=payload)


@app.post("/api/quiz/answer")
@login_required
def api_quiz_answer(u):
    data = request.get_json(silent=True) or {}
    q = QUESTIONS.get(data.get("qid"))
    if not q:
        return jsonify(error="Question inconnue"), 404
    chosen = str(data.get("choice", ""))
    ok = chosen == q["correct"]
    with engine.begin() as c:
        c.execute(insert(attempts).values(user_id=u["id"], subject=q["subject"], qid=q["id"],
                                          correct=ok, ts=dt.datetime.utcnow()))
    return jsonify(correct=ok, right=q["correct"], why=q["why"], fiche=q["fiche"])


# --------------------------------------------------------------------------- leaderboard
@app.get("/api/leaderboard")
@login_required
def api_leaderboard(u):
    with engine.connect() as c:
        urows = c.execute(select(users.c.id, users.c.display_name)).all()
        allrows = defaultdict(list)
        for uid, subject, qid, correct, ts in c.execute(
                select(attempts.c.user_id, attempts.c.subject, attempts.c.qid, attempts.c.correct, attempts.c.ts)
                .order_by(attempts.c.ts, attempts.c.id)):
            allrows[uid].append((subject, qid, correct, ts))
    board = []
    for uid, name in urows:
        prog = user_progress(allrows.get(uid, []))
        overall = round(sum(p["pct"] for p in prog.values()) / len(prog))
        board.append({"name": name, "me": uid == u["id"], "overall": overall, "level": level_for(overall),
                      "score": sum(p["score"] for p in prog.values()),
                      "subjects": {sid: p["pct"] for sid, p in prog.items()}})
    board.sort(key=lambda b: (-b["score"], b["name"]))
    return jsonify(board=board, subjects=[{"id": s["id"], "emoji": s["emoji"], "name": s["name"]}
                                          for s in ordered_subjects()])


# --------------------------------------------------------------------------- coach
def strip_md(t):
    return re.sub(r"\*+", "", t)


def course_notes(sid):
    s = SUBJECTS[sid]
    parts = []
    for f in s["fiches"]:
        parts.append(f"## {f['title']['en']}  ({f['title']['fr']})")
        parts.extend("- " + strip_md(b) for b in f["body"]["en"])
    return "\n".join(parts)


def weak_points(rows, sid):
    last = {}
    for subject, qid, correct, ts in rows:
        if subject == sid:
            last[qid] = correct
    bad = defaultdict(int)
    for qid, ok in last.items():
        if not ok and qid in QUESTIONS:
            bad[QUESTIONS[qid]["fiche"]] += 1
    titles = {f["id"]: f["title"]["fr"] for f in SUBJECTS[sid]["fiches"]}
    return [titles[k] for k, _ in sorted(bad.items(), key=lambda kv: -kv[1])][:4]


def coach_system(sid, weak):
    s = SUBJECTS[sid]
    weak_txt = ("\nPoints faibles actuels de l'étudiant (QCM ratés) : " + "; ".join(weak) + ".") if weak else ""
    return (
        f"Tu es le coach de révision d'un étudiant d'AlmaU (équipe #AlmaUteam4ever) pour le cours « {s['name']['en']} » "
        f"({s['teacher']}). Il prépare le midterm de la semaine prochaine ; l'examen est en anglais.\n\n"
        "RÈGLES\n"
        "- Réponds dans la langue de l'étudiant (français par défaut) et garde les termes techniques en anglais entre parenthèses.\n"
        "- Appuie-toi d'abord sur les NOTES DE COURS ci-dessous. Si tu ajoutes un exemple ou une explication qui n'y est pas, "
        "dis-le clairement (« exemple pour illustrer, pas dans le cours »). Si le sujet n'est pas couvert par les notes, dis-le honnêtement "
        "et suggère de vérifier avec le support de cours ; n'invente ni chiffre ni source.\n"
        "- Pédagogie : explique simplement, donne un exemple concret (« à quoi ça ressemble »), puis un mini-check de compréhension.\n"
        "- Si l'étudiant veut s'entraîner, pose UNE question à la fois, attends sa réponse, corrige avec bienveillance et précision.\n"
        "- Sois concis (moins de 180 mots sauf demande explicite). Utilise des listes courtes et du **gras** pour les mots-clés.\n"
        "- Reste dans le cadre de la révision de ce cours ; pour autre chose, ramène poliment au sujet.\n"
        f"- Limites du matériel fourni : {s['coverage']}{weak_txt}\n\n"
        f"NOTES DE COURS\n{course_notes(sid)}"
    )


@app.post("/api/coach")
@login_required
def api_coach(u):
    key = os.environ.get("ANTHROPIC_API_KEY")
    if not key:
        return jsonify(error="Le coach IA n'est pas encore activé (clé API manquante côté serveur)."), 503
    data = request.get_json(silent=True) or {}
    sid = data.get("subject")
    if sid not in SUBJECTS:
        return jsonify(error="Matière inconnue"), 404
    msg = str(data.get("message", "")).strip()[:2000]
    if not msg:
        return jsonify(error="Message vide"), 400
    hist = []
    for m in (data.get("history") or [])[-12:]:
        if m.get("role") in ("user", "assistant") and str(m.get("content", "")).strip():
            hist.append({"role": m["role"], "content": str(m["content"])[:3000]})
    while hist and hist[0]["role"] != "user":
        hist.pop(0)
    # alternance stricte user/assistant
    cleaned = []
    for m in hist:
        if cleaned and cleaned[-1]["role"] == m["role"]:
            cleaned[-1]["content"] += "\n" + m["content"]
        else:
            cleaned.append(m)
    if cleaned and cleaned[-1]["role"] == "user":
        cleaned.pop()
    cleaned.append({"role": "user", "content": msg})

    today = dt.date.today().isoformat()
    with engine.begin() as c:
        row = c.execute(select(chat_usage.c.n).where((chat_usage.c.user_id == u["id"]) & (chat_usage.c.day == today))).first()
        used = row[0] if row else 0
        if used >= COACH_DAILY_LIMIT:
            return jsonify(error=f"Limite quotidienne atteinte ({COACH_DAILY_LIMIT} messages). Reviens demain !"), 429
        if row:
            c.execute(update(chat_usage).where((chat_usage.c.user_id == u["id"]) & (chat_usage.c.day == today)).values(n=used + 1))
        else:
            c.execute(insert(chat_usage).values(user_id=u["id"], day=today, n=1))
        rows = attempts_of(c, u["id"])
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=key, timeout=60)
        resp = client.messages.create(
            model=COACH_MODEL, max_tokens=900,
            system=[{"type": "text", "text": coach_system(sid, weak_points(rows, sid)),
                     "cache_control": {"type": "ephemeral"}}],
            messages=cleaned,
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
    except Exception as e:  # noqa: BLE001
        app.logger.exception("coach error")
        return jsonify(error="Le coach n'a pas pu répondre pour le moment. Réessaie dans un instant."), 502
    return jsonify(reply=text, left=COACH_DAILY_LIMIT - used - 1)


# --------------------------------------------------------------------------- Google Drive (cours)
def drive_guard(fn):
    import functools

    @functools.wraps(fn)
    def w(*a, **k):
        if not drive.mode():
            return jsonify(error="Google Drive n'est pas encore connecté côté serveur (voir README)."), 503
        try:
            return fn(*a, **k)
        except Exception as e:  # noqa: BLE001
            app.logger.exception("drive error")
            msg = str(e)
            if "storageQuota" in msg or "quota" in msg.lower():
                return jsonify(error="Google refuse l'ajout (quota du compte de service). Utilise le mode OAuth du propriétaire (README)."), 502
            return jsonify(error="Erreur Google Drive : impossible de joindre le dossier pour le moment."), 502
    return w


@app.get("/api/drive/status")
@login_required
def drive_status(u):
    return jsonify(enabled=bool(drive.mode()), mode=drive.mode(), max_mb=drive.MAX_UPLOAD // 1048576,
                   can_upload=drive.mode() == "oauth" or bool(drive.mode()),
                   root=f"https://drive.google.com/drive/folders/{drive.ROOT_ID}")


@app.get("/api/drive/<sid>/files")
@login_required
@drive_guard
def drive_files(u, sid):
    if sid not in SUBJECTS or sid not in drive.FOLDER_MAP:
        return jsonify(error="Matière inconnue"), 404
    folder = request.args.get("folder") or drive.FOLDER_MAP[sid]
    if folder != drive.FOLDER_MAP[sid] and drive.owning_subject(folder) != sid:
        return jsonify(error="Dossier hors de cette matière"), 404
    crumbs = []
    files = drive.list_folder(folder, sid)
    return jsonify(folder=folder, root=drive.FOLDER_MAP[sid], files=files, crumbs=crumbs)


@app.get("/api/drive/file/<fid>")
@login_required
@drive_guard
def drive_file(u, fid):
    if not re.fullmatch(r"[\w-]{10,80}", fid):
        return jsonify(error="Identifiant invalide"), 400
    if drive.owning_subject(fid) is None:
        return jsonify(error="Fichier hors des dossiers de cours"), 404
    meta = drive.file_meta(fid)
    if meta["mimeType"] == drive.FOLDER_MIME:
        return jsonify(error="C'est un dossier"), 400
    if meta.get("size") and int(meta["size"]) > 60 * 1024 * 1024:
        return jsonify(error="Fichier trop lourd pour être ouvert ici : ouvre-le directement dans Drive.", link=meta.get("webViewLink")), 413
    data, mime, name = drive.download(fid, meta)
    inline = mime == "application/pdf" or mime.startswith("image/")
    from urllib.parse import quote
    disp = ("inline" if inline and request.args.get("dl") != "1" else "attachment") + f"; filename*=UTF-8''{quote(name)}"
    return Response(data, mimetype=mime, headers={"Content-Disposition": disp, "Cache-Control": "private, max-age=300"})


@app.post("/api/drive/<sid>/upload")
@login_required
@drive_guard
def drive_upload(u, sid):
    if sid not in SUBJECTS or sid not in drive.FOLDER_MAP:
        return jsonify(error="Matière inconnue"), 404
    f = request.files.get("file")
    if not f or not f.filename:
        return jsonify(error="Aucun fichier reçu."), 400
    name = os.path.basename(f.filename).strip()[:180]
    ext = os.path.splitext(name)[1].lower()
    if ext not in drive.ALLOWED_EXT:
        return jsonify(error=f"Type de fichier non accepté ({ext or 'sans extension'}). Formats : PDF, PPTX, DOCX, images, etc."), 400
    data = f.read()
    if len(data) > drive.MAX_UPLOAD:
        return jsonify(error=f"Fichier trop lourd (max {drive.MAX_UPLOAD // 1048576} Mo)."), 413
    if not data:
        return jsonify(error="Fichier vide."), 400
    folder = request.form.get("folder") or drive.FOLDER_MAP[sid]
    if folder != drive.FOLDER_MAP[sid] and drive.owning_subject(folder) != sid:
        return jsonify(error="Dossier hors de cette matière"), 404
    note = f"Ajouté par {u['display_name']} via la plateforme le {dt.date.today().isoformat()}"
    res = drive.upload(folder, name, data, f.mimetype, note)
    return jsonify(ok=True, id=res["id"], name=res["name"])


# --------------------------------------------------------------------------- agenda partagé
def parse_dt(v):
    try:
        return dt.datetime.fromisoformat(str(v))
    except (TypeError, ValueError):
        return None


def event_dict(row, people, me):
    ids = [p[0] for p in people]
    return {"id": row["id"], "title": row["title"], "description": row["description"],
            "start": row["start"].isoformat(timespec="minutes"),
            "end": row["end"].isoformat(timespec="minutes") if row["end"] else None,
            "all_day": row["all_day"], "subjects": [x for x in row["subjects"].split(",") if x],
            "everyone": row["everyone"], "people": [{"id": p[0], "name": p[1]} for p in people],
            "created_by": row["created_by"], "author": row["author"],
            "mine": row["everyone"] or me in ids, "editable": None}


def load_events(c, where=None):
    q = (select(events, users.c.display_name.label("author")).join(users, users.c.id == events.c.created_by)
         .order_by(events.c.start, events.c.id))
    if where is not None:
        q = q.where(where)
    rows = c.execute(q).mappings().all()
    ppl = defaultdict(list)
    ids = [r["id"] for r in rows]
    if ids:
        for eid, uid, name in c.execute(select(event_people.c.event_id, users.c.id, users.c.display_name)
                                        .join(users, users.c.id == event_people.c.user_id)
                                        .where(event_people.c.event_id.in_(ids)).order_by(users.c.display_name)):
            ppl[eid].append((uid, name))
    return rows, ppl


def clean_event(data, u):
    title = str(data.get("title", "")).strip()[:140]
    if not title:
        return None, "Il faut un titre."
    start = parse_dt(data.get("start"))
    if not start:
        return None, "Date de début invalide."
    end = parse_dt(data.get("end")) if data.get("end") else None
    if end and end < start:
        return None, "La fin doit être après le début."
    all_day = bool(data.get("all_day"))
    subs = [s for s in (data.get("subjects") or []) if s in SUBJECTS]
    everyone = bool(data.get("everyone"))
    with engine.connect() as c:
        valid = {r[0] for r in c.execute(select(users.c.id))}
    people = sorted({int(x) for x in (data.get("people") or []) if str(x).isdigit() and int(x) in valid})
    if not everyone and not people:
        people = [u["id"]]
    return dict(title=title, description=str(data.get("description", "")).strip()[:1500], start=start, end=end,
                all_day=all_day, subjects=",".join(dict.fromkeys(subs)), everyone=everyone), people


@app.get("/api/people")
@login_required
def api_people(u):
    with engine.connect() as c:
        rows = c.execute(select(users.c.id, users.c.display_name).order_by(users.c.display_name)).all()
    return jsonify(people=[{"id": r[0], "name": r[1], "me": r[0] == u["id"]} for r in rows],
                   subjects=[{"id": s["id"], "emoji": s["emoji"], "name": s["name"]} for s in ordered_subjects()])


@app.get("/api/events")
@login_required
def api_events(u):
    since = parse_dt(request.args.get("from")) or (dt.datetime.now() - dt.timedelta(days=45))
    with engine.connect() as c:
        rows, ppl = load_events(c, events.c.start >= since)
    out = []
    for r in rows:
        e = event_dict(r, ppl[r["id"]], u["id"])
        e["editable"] = u["is_admin"] or r["created_by"] == u["id"]
        out.append(e)
    return jsonify(events=out)


@app.post("/api/events")
@login_required
def api_event_create(u):
    vals, people = clean_event(request.get_json(silent=True) or {}, u)
    if vals is None:
        return jsonify(error=people), 400
    with engine.begin() as c:
        eid = c.execute(insert(events).values(created_by=u["id"], created_at=dt.datetime.utcnow(), **vals)).inserted_primary_key[0]
        if not vals["everyone"]:
            c.execute(insert(event_people), [{"event_id": eid, "user_id": p} for p in people])
    return jsonify(ok=True, id=eid)


@app.post("/api/events/<int:eid>")
@login_required
def api_event_update(u, eid):
    with engine.begin() as c:
        row = c.execute(select(events).where(events.c.id == eid)).mappings().first()
        if not row:
            return jsonify(error="Événement introuvable"), 404
        if not (u["is_admin"] or row["created_by"] == u["id"]):
            return jsonify(error="Seul l'auteur (ou l'admin) peut modifier cet événement."), 403
        vals, people = clean_event(request.get_json(silent=True) or {}, u)
        if vals is None:
            return jsonify(error=people), 400
        c.execute(update(events).where(events.c.id == eid).values(**vals))
        c.execute(delete(event_people).where(event_people.c.event_id == eid))
        if not vals["everyone"]:
            c.execute(insert(event_people), [{"event_id": eid, "user_id": p} for p in people])
    return jsonify(ok=True)


@app.delete("/api/events/<int:eid>")
@login_required
def api_event_delete(u, eid):
    with engine.begin() as c:
        row = c.execute(select(events.c.created_by).where(events.c.id == eid)).first()
        if not row:
            return jsonify(error="Événement introuvable"), 404
        if not (u["is_admin"] or row[0] == u["id"]):
            return jsonify(error="Seul l'auteur (ou l'admin) peut supprimer cet événement."), 403
        c.execute(delete(event_people).where(event_people.c.event_id == eid))
        c.execute(delete(events).where(events.c.id == eid))
    return jsonify(ok=True)


# --------------------------------------------------------------------------- admin
@app.get("/api/admin/users")
@admin_required
def admin_users(u):
    with engine.connect() as c:
        rows = c.execute(select(users.c.id, users.c.username, users.c.display_name, users.c.is_admin)).all()
        counts = dict(c.execute(select(attempts.c.user_id, func.count()).group_by(attempts.c.user_id)).all())
    return jsonify(users=[{"id": r[0], "username": r[1], "name": r[2], "is_admin": r[3],
                           "answers": counts.get(r[0], 0)} for r in rows])


@app.post("/api/admin/users")
@admin_required
def admin_create(u):
    data = request.get_json(silent=True) or {}
    name, pwd = str(data.get("name", "")).strip(), str(data.get("password", ""))
    if not name or len(pwd) < 6:
        return jsonify(error="Nom requis et mot de passe d'au moins 6 caractères."), 400
    uname = name.lower()
    with engine.begin() as c:
        if c.execute(select(users.c.id).where(users.c.username == uname)).first():
            return jsonify(error="Ce nom existe déjà."), 400
        c.execute(insert(users).values(username=uname, display_name=name[:1].upper() + name[1:],
                                       password_hash=generate_password_hash(pwd), is_admin=False))
    return jsonify(ok=True)


@app.post("/api/admin/reset")
@admin_required
def admin_reset(u):
    data = request.get_json(silent=True) or {}
    uname, pwd = str(data.get("username", "")).strip().lower(), str(data.get("password", ""))
    if len(pwd) < 6:
        return jsonify(error="Mot de passe trop court (6 caractères min)."), 400
    with engine.begin() as c:
        r = c.execute(update(users).where(users.c.username == uname).values(password_hash=generate_password_hash(pwd)))
        if not r.rowcount:
            return jsonify(error="Utilisateur introuvable."), 404
    return jsonify(ok=True)


load_content()
init_db()

if __name__ == "__main__":
    app.run(debug=True, port=int(os.environ.get("PORT", 5000)))
