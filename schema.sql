-- Hand-written DDL (no ORM). Skills/traits/keywords are normalized into
-- child tables so overlap can be computed with plain SQL joins.

DROP TABLE IF EXISTS candidate_skills;
DROP TABLE IF EXISTS candidate_traits;
DROP TABLE IF EXISTS job_skills;
DROP TABLE IF EXISTS job_keywords;
DROP TABLE IF EXISTS candidates;
DROP TABLE IF EXISTS jobs;

CREATE TABLE candidates (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    name          TEXT    NOT NULL UNIQUE,
    experience    INTEGER NOT NULL,          -- years
    availability  TEXT    NOT NULL,          -- 'Immediate' | '2 weeks' | 'Not looking'
    quirk         TEXT
);

CREATE TABLE candidate_skills (
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    skill        TEXT    NOT NULL,
    PRIMARY KEY (candidate_id, skill)
);

CREATE TABLE candidate_traits (
    candidate_id INTEGER NOT NULL REFERENCES candidates(id) ON DELETE CASCADE,
    trait        TEXT    NOT NULL,
    PRIMARY KEY (candidate_id, trait)
);

CREATE TABLE jobs (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    title          TEXT    NOT NULL UNIQUE,
    min_experience INTEGER NOT NULL,
    tagline        TEXT
);

CREATE TABLE job_skills (
    job_id INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    skill  TEXT    NOT NULL,
    PRIMARY KEY (job_id, skill)
);

CREATE TABLE job_keywords (                  -- culture keywords
    job_id  INTEGER NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    keyword TEXT    NOT NULL,
    PRIMARY KEY (job_id, keyword)
);

-- A "match" is computed on the fly from the tables above, so there is no
-- stored matches table: scores can never go stale when data changes.
