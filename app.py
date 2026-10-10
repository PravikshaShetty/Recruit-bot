import math
import sqlite3
from pathlib import Path

from flask import Flask, g, jsonify, request

from seed_data import CANDIDATES, JOBS


BASE = Path(__file__).parent
DB_PATH = BASE / "recruiter_bot.db"

app = Flask(__name__)


# Matching configuration
W_SKILLS, W_EXPERIENCE, W_TRAITS, W_AVAILABILITY = 55, 20, 15, 10

AVAILABILITY_FACTOR = {
    "Immediate": 1.0,
    "2 weeks": 0.6,
    "Not looking": 0.0,
}


def score_pair(row):
    skill_ratio = row["skill_hits"] / row["skill_total"]

    if row["experience"] >= row["min_experience"]:
        exp_ratio = 1.0
    else:
        exp_ratio = row["experience"] / row["min_experience"]

    trait_ratio = (
        row["trait_hits"] / row["kw_total"]
        if row["kw_total"]
        else 0.0
    )

    avail = AVAILABILITY_FACTOR.get(row["availability"], 0.0)

    score = (
        W_SKILLS * skill_ratio
        + W_EXPERIENCE * exp_ratio
        + W_TRAITS * trait_ratio
        + W_AVAILABILITY * avail
    )

    reason = (
        f"{row['skill_hits']}/{row['skill_total']} required skills "
        f"({row['matched_skills'] or 'none'}); "
        f"{row['experience']} yrs vs {row['min_experience']} required; "
        f"culture overlap: {row['matched_traits'] or 'none'}; "
        f"availability: {row['availability']}"
    )

    return round(score, 1), reason, avail


# Matching query
PAIR_SQL = """
SELECT
    c.id AS candidate_id,
    c.name,
    c.experience,
    c.availability,
    j.id AS job_id,
    j.title,
    j.min_experience,

    (SELECT COUNT(*)
     FROM job_skills js
     JOIN candidate_skills cs
       ON cs.skill = js.skill
      AND cs.candidate_id = c.id
     WHERE js.job_id = j.id) AS skill_hits,

    (SELECT COUNT(*)
     FROM job_skills js
     WHERE js.job_id = j.id) AS skill_total,

    (SELECT group_concat(js.skill, ', ')
     FROM job_skills js
     JOIN candidate_skills cs
       ON cs.skill = js.skill
      AND cs.candidate_id = c.id
     WHERE js.job_id = j.id) AS matched_skills,

    (SELECT COUNT(*)
     FROM job_keywords jk
     JOIN candidate_traits ct
       ON ct.trait = jk.keyword
      AND ct.candidate_id = c.id
     WHERE jk.job_id = j.id) AS trait_hits,

    (SELECT COUNT(*)
     FROM job_keywords jk
     WHERE jk.job_id = j.id) AS kw_total,

    (SELECT group_concat(jk.keyword, ', ')
     FROM job_keywords jk
     JOIN candidate_traits ct
       ON ct.trait = jk.keyword
      AND ct.candidate_id = c.id
     WHERE jk.job_id = j.id) AS matched_traits

FROM candidates c
CROSS JOIN jobs j
WHERE (:job_id IS NULL OR j.id = :job_id)
  AND (:candidate_id IS NULL OR c.id = :candidate_id)
"""


def rank(job_id=None, candidate_id=None, name_key="name", min_score=0):
    rows = get_db().execute(
        PAIR_SQL,
        {"job_id": job_id, "candidate_id": candidate_id},
    ).fetchall()

    results = []

    for row in rows:
        if row["skill_hits"] == 0:
            continue

        score, reason, avail = score_pair(row)

        if score < min_score:
            continue

        results.append({
            "row": row,
            "score": score,
            "reason": reason,
            "avail": avail,
        })

    results.sort(
        key=lambda result: (
            -result["score"],
            -result["avail"],
            result["row"][name_key],
        )
    )

    return results


def get_match_filters():
    limit_arg = request.args.get("limit")
    min_score_arg = request.args.get("min_score")

    limit = None
    min_score = 0.0

    if limit_arg is not None:
        try:
            limit = int(limit_arg)
        except ValueError:
            return None, None, (
                jsonify(error="limit must be a positive integer"),
                400,
            )

        if limit <= 0:
            return None, None, (
                jsonify(error="limit must be greater than 0"),
                400,
            )

    if min_score_arg is not None:
        try:
            min_score = float(min_score_arg)
        except ValueError:
            return None, None, (
                jsonify(error="min_score must be a number"),
                400,
            )

        if not math.isfinite(min_score) or not 0 <= min_score <= 100:
            return None, None, (
                jsonify(error="min_score must be between 0 and 100"),
                400,
            )

    return limit, min_score, None


# Database connection
def get_db():
    if "db" not in g:
        g.db = sqlite3.connect(DB_PATH, timeout=5)
        g.db.row_factory = sqlite3.Row
        g.db.execute("PRAGMA foreign_keys = ON")

    return g.db


@app.teardown_appcontext
def close_db(_exc):
    db = g.pop("db", None)

    if db is not None:
        db.close()


def seed(db):
    db.executescript(
        (BASE / "schema.sql").read_text(encoding="utf-8")
    )

    for name, skills, exp, avail, traits, quirk in CANDIDATES:
        cursor = db.execute(
            """
            INSERT INTO candidates
                (name, experience, availability, quirk)
            VALUES (?, ?, ?, ?)
            """,
            (name, exp, avail, quirk),
        )

        candidate_id = cursor.lastrowid

        db.executemany(
            "INSERT INTO candidate_skills VALUES (?, ?)",
            [(candidate_id, skill) for skill in skills],
        )

        db.executemany(
            "INSERT INTO candidate_traits VALUES (?, ?)",
            [(candidate_id, trait) for trait in traits],
        )

    for title, skills, min_exp, keywords, tagline in JOBS:
        cursor = db.execute(
            """
            INSERT INTO jobs
                (title, min_experience, tagline)
            VALUES (?, ?, ?)
            """,
            (title, min_exp, tagline),
        )

        job_id = cursor.lastrowid

        db.executemany(
            "INSERT INTO job_skills VALUES (?, ?)",
            [(job_id, skill) for skill in skills],
        )

        db.executemany(
            "INSERT INTO job_keywords VALUES (?, ?)",
            [(job_id, keyword) for keyword in keywords],
        )

    db.commit()


def ensure_seeded():
    db = sqlite3.connect(DB_PATH, timeout=5)

    try:
        candidates_table = db.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'candidates'
            """
        ).fetchone()

        jobs_table = db.execute(
            """
            SELECT name
            FROM sqlite_master
            WHERE type = 'table' AND name = 'jobs'
            """
        ).fetchone()

        if not candidates_table or not jobs_table:
            seed(db)
            return

        candidate_count = db.execute(
            "SELECT COUNT(*) FROM candidates"
        ).fetchone()[0]

        job_count = db.execute(
            "SELECT COUNT(*) FROM jobs"
        ).fetchone()[0]

        if candidate_count == 0 or job_count == 0:
            seed(db)

    finally:
        db.close()


# API endpoints
@app.get("/")
def index():
    return jsonify(
        service="Recruiter Bot",
        endpoints=[
            "POST /seed",
            "GET /candidates",
            "GET /jobs",
            "GET /jobs/<id>/matches",
            "GET /candidates/<id>/matches",
        ],
    )


@app.post("/seed")
def seed_endpoint():
    seed(get_db())

    return jsonify(
        status="seeded",
        candidates=len(CANDIDATES),
        jobs=len(JOBS),
    )


@app.get("/candidates")
def list_candidates():
    rows = get_db().execute(
        """
        SELECT id, name, experience, availability
        FROM candidates
        ORDER BY id
        """
    ).fetchall()

    return jsonify([dict(row) for row in rows])


@app.get("/jobs")
def list_jobs():
    rows = get_db().execute(
        """
        SELECT id, title, min_experience
        FROM jobs
        ORDER BY id
        """
    ).fetchall()

    return jsonify([dict(row) for row in rows])


@app.get("/jobs/<int:job_id>/matches")
def job_matches(job_id):
    job = get_db().execute(
        "SELECT id, title FROM jobs WHERE id = ?",
        (job_id,),
    ).fetchone()

    if job is None:
        return jsonify(error="job not found"), 404

    limit, min_score, error = get_match_filters()

    if error is not None:
        return error

    ranked = rank(
        job_id=job_id,
        name_key="name",
        min_score=min_score,
    )

    if limit is not None:
        ranked = ranked[:limit]

    matches = [
        {
            "rank": position,
            "candidate_id": result["row"]["candidate_id"],
            "name": result["row"]["name"],
            "score": result["score"],
            "reason": result["reason"],
        }
        for position, result in enumerate(ranked, start=1)
    ]

    return jsonify(job=dict(job), matches=matches)


@app.get("/candidates/<int:candidate_id>/matches")
def candidate_matches(candidate_id):
    candidate = get_db().execute(
        "SELECT id, name FROM candidates WHERE id = ?",
        (candidate_id,),
    ).fetchone()

    if candidate is None:
        return jsonify(error="candidate not found"), 404

    limit, min_score, error = get_match_filters()

    if error is not None:
        return error

    ranked = rank(
        candidate_id=candidate_id,
        name_key="title",
        min_score=min_score,
    )

    if limit is not None:
        ranked = ranked[:limit]

    matches = [
        {
            "rank": position,
            "job_id": result["row"]["job_id"],
            "title": result["row"]["title"],
            "score": result["score"],
            "reason": result["reason"],
        }
        for position, result in enumerate(ranked, start=1)
    ]

    return jsonify(candidate=dict(candidate), matches=matches)


if __name__ == "__main__":
    ensure_seeded()
    app.run(debug=True, port=5000)