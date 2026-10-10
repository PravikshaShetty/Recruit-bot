# Recruiter Bot

A small backend that stores candidates and jobs and ranks the best matches in
both directions. Python + Flask, SQLite, **hand-written SQL only (no ORM)**.

## Run it locally

```bash
python -m venv venv && source venv/bin/activate   # optional
pip install -r requirements.txt
python app.py                                      # http://127.0.0.1:5000
```

On first start the database (`recruiter_bot.db`) is created and seeded from
`seed_data.py` using the DDL in `schema.sql`. `POST /seed` resets it.

## API (curl examples)

```bash
curl -X POST http://127.0.0.1:5000/seed            # (re)load seed data
curl http://127.0.0.1:5000/candidates              # list candidates + ids
curl http://127.0.0.1:5000/jobs                    # list jobs + ids

# Ranked candidates for a job (optional ?limit=N)
curl http://127.0.0.1:5000/jobs/1/matches          # Backend Detective

# Ranked jobs for a candidate (the reverse direction)
curl http://127.0.0.1:5000/candidates/6/matches    # Rick S.
```

Each match returns `rank`, `score` (0-100) and a human-readable `reason`, e.g.

```json
{"rank": 1, "name": "Sherlock H.", "score": 95.0,
 "reason": "3/3 required skills (deduction, forensics, pattern-recognition); 8 yrs vs 3 required; culture overlap: analytical; availability: Immediate"}
```

## Schema

`candidates` and `jobs` each have child tables (`candidate_skills`,
`candidate_traits`, `job_skills`, `job_keywords`) instead of comma-separated
strings, so skill overlap is a plain SQL join. There is deliberately **no
stored `matches` table**: a match is computed from current data on every
request, so scores can never go stale after an edit. The trade-off is that the
work is redone per request, which is fine at this scale; at large scale I
would cache or precompute.

## Matching algorithm

`score = 60*skills + 20*experience + 10*culture + 10*availability` (each part
is a 0-1 ratio, final score is 0-100).

- **Skills (60):** matched required skills / total required skills. Heaviest
  weight because it is the hard requirement. A candidate sharing **zero**
  required skills is not listed at all, which keeps lists meaningful.
- **Experience (20):** full marks if the candidate meets the minimum; below
  it, credit is proportional (2 yrs vs 4 required = 0.5). I do not penalise
  over-qualification, since the brief only gives a *minimum*.
- **Culture (10):** overlap between the candidate's traits and the job's
  culture keywords. Matching is exact-string, so `calm` does not match
  `calm-under-pressure`; a synonym or embedding match would be the next step.
- **Availability (10):** Immediate = full, 2 weeks = 0.6, Not looking = 0.
  "Not looking" candidates are down-ranked, not removed, because a perfect fit
  is still useful to a recruiter.
- **Tie-break:** score, then availability, then name/title alphabetically, so
  ordering is deterministic.

One SQL query (cross join + correlated subqueries) counts the overlaps for
both endpoints; Python only turns the counts into a score and reason.

## Part 2: SQL Detective

`sql_detective_setup.sql` loads the dataset as given; `sql_detective.sql`
holds the five answers. Q3 normalises emails (`LOWER(TRIM(email))`) because
Ananya Rao appears twice with different letter case.

## AI tools

I used Claude to generate a first draft of the code and SQL. I then ran the
queries and API, read through the matching logic and weights, and can explain
each decision. <!-- Edit this to describe what YOU actually did. -->
