# Recruiter Bot

Recruiter Bot is a backend service that matches candidates with suitable jobs and jobs with suitable candidates. It ranks matches based on skills, experience, culture, and availability, providing a score and a human-readable explanation for each match.

**Tech Stack:** Python, Flask, SQLite, SQL

The project uses hand-written SQL without an ORM or query builder.

## 1. Setup and Installation

### Prerequisites

- Python 3.10 or later
- pip

### Step 1: Clone the Repository

```bash
git clone https://github.com/PravikshaShetty/Recruit-bot.git
cd Recruit-bot
```

If the project files are inside a nested `recruiter-bot` folder, navigate into that folder before continuing.

### Step 2: Create a Virtual Environment

**Windows:**

```powershell
py -m venv venv
```

### Step 3: Activate the Virtual Environment

**Windows Command Prompt:**

```cmd
venv\Scripts\activate
```

**Windows PowerShell:**

```powershell
.\venv\Scripts\Activate.ps1
```

**Linux/macOS:**

```bash
source venv/bin/activate
```

### Step 4: Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### Step 5: Run the Application

```bash
python app.py
```

The API will be available at:

`http://127.0.0.1:5000`

On first startup, the application creates and seeds the SQLite database using `schema.sql` and `seed_data.py`.

**Note:** The `/seed` endpoint resets the database and reloads the original seed data.

## 2. API Endpoints

### 2.1 List All Candidates

```bash
curl http://127.0.0.1:5000/candidates
```

Returns the available candidates and their IDs.

### 2.2 List All Jobs

```bash
curl http://127.0.0.1:5000/jobs
```

Returns the available jobs and their IDs.

### 2.3 Find Matching Candidates for a Job

```bash
curl "http://127.0.0.1:5000/jobs/1/matches"
```

Returns candidates ranked by their match scores for the specified job.

**Optional query parameters:**

Limit the number of results:

```bash
curl "http://127.0.0.1:5000/jobs/1/matches?limit=3"
```

Filter by minimum match score:

```bash
curl "http://127.0.0.1:5000/jobs/1/matches?min_score=60"
```

Combine both filters:

```bash
curl "http://127.0.0.1:5000/jobs/1/matches?limit=3&min_score=60"
```

- `limit`: Maximum number of matches to return.
- `min_score`: Minimum acceptable match score, between 0 and 100.

### 2.4 Find Matching Jobs for a Candidate

```bash
curl "http://127.0.0.1:5000/candidates/1/matches"
```

Returns jobs ranked by their match scores for the specified candidate.

**Optional query parameters:**

```bash
curl "http://127.0.0.1:5000/candidates/1/matches?limit=3"
```

```bash
curl "http://127.0.0.1:5000/candidates/1/matches?min_score=60"
```

### 2.5 Reset the Seed Data

```bash
curl -X POST http://127.0.0.1:5000/seed
```

Reloads the original candidate and job data.

### Example Match Response

Each match includes a rank, score, and explanation.

```json
{
  "candidate_id": 1,
  "name": "Sherlock H.",
  "rank": 1,
  "reason": "3/3 required skills (deduction, forensics, pattern-recognition); 8 yrs vs 3 required; culture overlap: analytical; availability: Immediate",
  "score": 92.5
}
```

The exact results depend on the matching logic and the data currently loaded.

### Error Handling

The API validates request parameters and returns appropriate HTTP error responses.

Examples:

- `404 Not Found`: Returned when the requested job or candidate does not exist.
- `400 Bad Request`: Returned when a query parameter contains an invalid value, such as a `min_score` outside the range of 0–100.

## 3. Database Design

The database uses a relational schema to store candidates, jobs, skills, and culture traits.

### Tables

| Table | Purpose |
|---|---|
| `candidates` | Stores candidate details, experience, availability, and other information. |
| `candidate_skills` | Stores skills associated with each candidate. |
| `candidate_traits` | Stores culture traits associated with each candidate. |
| `jobs` | Stores job details and minimum experience requirements. |
| `job_skills` | Stores required skills associated with each job. |
| `job_keywords` | Stores culture keywords associated with each job. |

Skills and traits are stored in separate child tables instead of comma-separated strings. This supports relational queries and allows skill and culture overlap to be calculated using SQL.

There is no stored matches table. Matches are calculated when an endpoint is requested, ensuring that the results reflect the current database contents rather than potentially outdated scores.

The implementation uses hand-written SQL rather than an ORM or query builder.

## 4. Matching Algorithm

The matching algorithm calculates a score between 0 and 100 using four factors:

- Skills
- Experience
- Culture
- Availability

### Scoring Formula

```text
Score = (Skills * 0.55)
      + (Experience * 0.20)
      + (Culture * 0.15)
      + (Availability * 0.10)

Final Score = Score * 100
```

Each factor is represented as a value between 0 and 1.

### 4.1 Skills - 55%

Skills receive the highest weight because they are central to determining whether a candidate fits a role.

The score is calculated as:

```text
Skill Score = Matched Required Skills / Total Required Skills
```

Candidates with no overlapping required skills are excluded from the match results to keep the recommendations relevant.

### 4.2 Experience - 20%

Candidates receive full experience credit if they meet or exceed the minimum experience requirement.

Candidates below the minimum receive proportional credit.

For example, a candidate with two years of experience applying for a role requiring four years receives half the experience score.

Overqualification is not penalized because the assignment specifies minimum experience requirements.

### 4.3 Culture - 15%

Culture matching measures the overlap between a candidate's traits and a job's culture keywords.

Matching uses exact string comparisons. For example, `calm` and `calm-under-pressure` are treated as different values.

### 4.4 Availability - 10%

Availability is scored as follows:

| Availability | Score |
|---|---:|
| Immediate | 1.0 |
| 2 weeks | 0.6 |
| Not looking | 0.0 |

Candidates who are not currently looking are down-ranked rather than automatically excluded.

### 4.5 Ranking and Tie-Breaking

Matches are ranked using the following criteria:

1. Match score, highest first.
2. Availability score, highest first.
3. Candidate name or job title, alphabetically.

This ensures deterministic ordering when multiple matches have the same score.

### Implementation Approach

A hand-written SQL query calculates skill and culture overlap using the relational tables. Python then calculates the final score and generates the human-readable explanation for each match.

The same matching logic supports both endpoints:

- Finding candidates for a job.
- Finding jobs for a candidate.

## 5. SQL Detective Challenge

The SQL Detective challenge uses a separate dataset loaded through `sql_detective_setup.sql`. The solutions are provided in `sql_detective.sql`.

The file contains four required SQL queries and one bonus query.

### Query 1: Open Jobs and Recruiters

Retrieves open job postings along with the associated recruiter information.

### Query 2: Final-Stage Applicants

Counts distinct applicants who reached the Final interview stage for each job, including jobs with zero finalists.

### Query 3: Applicants Across Multiple Jobs

Identifies applicants associated with multiple job postings.

Email addresses are normalized using `LOWER(TRIM(email))` to handle differences in letter casing and surrounding whitespace.

Because the dataset does not contain a separate applications table, interview records are used to identify applicants associated with job postings.

### Query 4: Recruiter Conversion Rates

Calculates the Final-stage pass rate for recruiters with at least three Final-stage interview records.

Pending interviews with `NULL` outcomes are included in the total number of Final-stage interview records.

### Bonus Query 5: Recruiter Rankings

Ranks recruiters by placements within each department using a SQL window function.

The `RANK()` function preserves ties between recruiters with equal placement counts.

## 6. Project Structure

```text
Recruit-bot/
├── app.py
├── schema.sql
├── seed_data.py
├── requirements.txt
├── sql_detective_setup.sql
├── sql_detective.sql
├── README.md
└── .gitignore
```

| File | Description |
|---|---|
| `app.py` | Flask API, SQL queries, and matching logic. |
| `schema.sql` | Database schema and table definitions. |
| `seed_data.py` | Supplied candidate and job seed data. |
| `requirements.txt` | Python dependencies required to run the application. |
| `sql_detective_setup.sql` | SQL Detective tables and seed data. |
| `sql_detective.sql` | SQL Detective solutions. |
| `README.md` | Project setup, API documentation, and design decisions. |
| `.gitignore` | Specifies files that Git should ignore. |

## 7. AI Tool Disclosure

I used Claude and ChatGPT as AI assistance tools during development to support the initial implementation, SQL queries, and refinement of the project. I reviewed and tested the code, verified the API responses, and worked on understanding the database design, matching algorithm, and scoring decisions.