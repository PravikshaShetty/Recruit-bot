"""Recruiter Bot: Flask API + hand-written SQL on SQLite (no ORM).

Run:  python app.py        (auto-seeds an empty database)
"""
import sqlite3
from pathlib import Path

from flask import Flask, g, jsonify, request

from seed_data import CANDIDATES, JOBS

BASE = Path(__file__).parent
DB_PATH = BASE / "recruiter_bot.db"

app = Flask(__name__)

# ---------------------------------------------------------------- scoring
# Weights add up to 100. Skills dominate because they are the hard requirement.
W_SKILLS, W_EXPERIENCE, W_TRAITS, W_AVAILABILITY = 55, 20, 15, 10

# How soon the candidate can start. "Not looking" earns nothing but is NOT
# excluded: a great fit who is not looking is still useful to a recruiter.
AVAILABILITY_FACTOR = {"Immediate": 1.0, "2 weeks": 0.6, "Not looking": 0.0}


def score_pair(row):
    """Turn one candidate x job row (raw counts from SQL) into score + reason."""
    skill_ratio = row["skill_hits"] / row["skill_total"]

    # Meeting the minimum = full marks (no penalty for being over-qualified).
    # Below the minimum, credit is proportional: 2 yrs vs 4 required = 0.5.
    if row["experience"] >= row["min_experience"]:
        exp_ratio = 1.0
    else:
        exp_ratio = row["experience"] / row["min_experience"]

    trait_ratio = row["trait_hits"] / row["kw_total"] if row["kw_total"] else 0.0
    avail = AVAILABILITY_FACTOR.get(row["availability"], 0.0)

    score = (W_SKILLS * skill_ratio + W_EXPERIENCE * exp_ratio
             + W_TRAITS * trait_ratio + W_AVAILABILITY * avail)

    reason = (
        f"{row['skill_hits']}/{row['skill_total']} required skills"
        f" ({row['matched_skills'] or 'none'}); "
        f"{row['experience']} yrs vs {row['min_experience']} required; "
        f"culture overlap: {row['matched_traits'] or 'none'}; "
        f"availability: {row['availability']}"
    )
    return round(score, 1), reason, avail


# ------------------------------------------------------------------- SQL
# One query serves both directions: it cross-joins candidates and jobs, the
# optional filters pin one side, and correlated subqueries count the overlaps.
PAIR_SQL = """
SELECT
    c.id AS candidate_id, c.name, c.experience, c.availability,
    j.id AS job_id, j.title, j.min_experience,
    (SELECT COUNT(*) FROM job_skills js
       JOIN candidate_skills cs ON cs.skill = js.skill AND cs.candidate_id = c.id
      WHERE js.job_id = j.id)                                   AS skill_hits,
    (SELECT COUNT(*) FROM job_skills js WHERE js.job_id = j.id) AS skill_total,
    (SELECT group_concat(js.skill, ', ') FROM job_skills js
       JOIN candidate_skills cs ON cs.skill = js.skill AND cs.candidate_id = c.id
      WHERE js.job_id = j.id)                                   AS matched_skills,
    (SELECT COUNT(*) FROM job_keywords jk
       JOIN candidate_traits ct ON ct.trait = jk.keyword AND ct.candidate_id = c.id
      WHERE jk.job_id = j.id)                                   AS trait_hits,
    (SELECT COUNT(*) FROM job_keywords jk WHERE jk.job_id = j.id) AS kw_total,
    (SELECT group_concat(jk.keyword, ', ') FROM job_keywords jk
       JOIN candidate_traits ct ON ct.trait = jk.keyword AND ct.candidate_id = c.id
      WHERE jk.job_id = j.id)                                   AS matched_traits
FROM candidates c
CROSS JOIN jobs j
WHERE (:job_id IS NULL OR j.id = :job_id)
  AND (:candidate_id IS NULL OR c.id = :candidate_id)
"""


def rank(job_id=None, candidate_id=None, name_key="name"):
    rows = get_db().execute(
        PAIR_SQL, {"job_id": job_id, "candidate_id": candidate_id}).fetchall()
    results = []
    for row in rows:
        if row["skill_hits"] == 0:      # no shared skill = not a match at all
            continue
        score, reason, avail = score_pair(row)
        results.append({"row": row, "score": score, "reason": reason, "avail": avail})
    # Tie-break: higher score, then more available, then alphabetical (stable).
    results.sort(key=lambda r: (-r["score"], -r["avail"], r["row"][name_key]))
    return results


# --------------------------------------------------------------------- DB
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def seed(db):
    """Ingestion: (re)create the schema and load the seed data. Idempotent."""
    db.executescript((BASE / "schema.sql").read_text())
    for name, skills, exp, avail, traits, quirk in CANDIDATES:
        cur = db.execute(
            "INSERT INTO candidates (name, experience, availability, quirk) VALUES (?, ?, ?, ?)",
            (name, exp, avail, quirk))
        cid = cur.lastrowid
        db.executemany("INSERT INTO candidate_skills VALUES (?, ?)", [(cid, s) for s in skills])
        db.executemany("INSERT INTO candidate_traits VALUES (?, ?)", [(cid, t) for t in traits])
    for title, skills, min_exp, keywords, tagline in JOBS:
        cur = db.execute(
            "INSERT INTO jobs (title, min_experience, tagline) VALUES (?, ?, ?)",
            (title, min_exp, tagline))
        jid = cur.lastrowid
        db.executemany("INSERT INTO job_skills VALUES (?, ?)", [(jid, s) for s in skills])
        db.executemany("INSERT INTO job_keywords VALUES (?, ?)", [(jid, k) for k in keywords])
    db.commit()


def ensure_seeded():
    db = sqlite3.connect(DB_PATH)
    try:
        has_data = db.execute(
            "SELECT name FROM sqlite_master WHERE name = 'candidates'").fetchone()
        if not has_data or not db.execute("SELECT 1 FROM candidates LIMIT 1").fetchone():
            seed(db)
    finally:
        db.close()


# -------------------------------------------------------------- endpoints
@app.get("/")
def index():
    return jsonify(service="Recruiter Bot", endpoints=[
        "POST /seed", "GET /candidates", "GET /jobs",
        "GET /jobs/<id>/matches", "GET /candidates/<id>/matches"])


@app.post("/seed")
def seed_endpoint():
    seed(get_db())
    return jsonify(status="seeded", candidates=len(CANDIDATES), jobs=len(JOBS))


@app.get("/candidates")
def list_candidates():
    rows = get_db().execute(
        "SELECT id, name, experience, availability FROM candidates ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/jobs")
def list_jobs():
    rows = get_db().execute(
        "SELECT id, title, min_experience FROM jobs ORDER BY id").fetchall()
    return jsonify([dict(r) for r in rows])


@app.get("/jobs/<int:job_id>/matches")
def job_matches(job_id):
    job = get_db().execute("SELECT id, title FROM jobs WHERE id = ?", (job_id,)).fetchone()
    if job is None:
        return jsonify(error="job not found"), 404
    limit = request.args.get("limit", type=int)
    ranked = rank(job_id=job_id, name_key="name")[:limit]
    return jsonify(job=dict(job), matches=[
        {"rank": i, "candidate_id": r["row"]["candidate_id"], "name": r["row"]["name"],
         "score": r["score"], "reason": r["reason"]}
        for i, r in enumerate(ranked, 1)])


@app.get("/candidates/<int:candidate_id>/matches")
def candidate_matches(candidate_id):
    cand = get_db().execute(
        "SELECT id, name FROM candidates WHERE id = ?", (candidate_id,)).fetchone()
    if cand is None:
        return jsonify(error="candidate not found"), 404
    limit = request.args.get("limit", type=int)
    ranked = rank(candidate_id=candidate_id, name_key="title")[:limit]
    return jsonify(candidate=dict(cand), matches=[
        {"rank": i, "job_id": r["row"]["job_id"], "title": r["row"]["title"],
         "score": r["score"], "reason": r["reason"]}
        for i, r in enumerate(ranked, 1)])


if __name__ == "__main__":
    ensure_seeded()
    app.run(debug=True, port=5000)
