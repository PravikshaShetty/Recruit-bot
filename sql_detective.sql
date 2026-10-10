-- SQL Detective answers. Written for SQLite, but only standard SQL is used
-- (CTEs, window functions), so it also runs on Postgres/MySQL 8+.
-- Load sql_detective_setup.sql first.


-- Q1: All currently open job postings with the recruiter who owns each one.
SELECT jp.id,
       jp.title,
       jp.department,
       r.name AS recruiter
FROM job_postings jp
JOIN recruiters r ON r.id = jp.recruiter_id
WHERE jp.status = 'open'
ORDER BY jp.id;


-- Q2: For each job posting, how many applicants reached the Final stage?
-- "Reached" = had a Final interview scheduled, whatever the outcome.
-- LEFT JOIN keeps postings with zero finalists (shown as 0), and
-- COUNT(DISTINCT ...) guards against an applicant having two Final rows.
SELECT jp.id,
       jp.title,
       COUNT(DISTINCT i.applicant_id) AS finalists
FROM job_postings jp
LEFT JOIN interviews i
       ON i.job_posting_id = jp.id
      AND i.stage = 'Final'
GROUP BY jp.id, jp.title
ORDER BY jp.id;


-- Q3: People who effectively applied to more than one job posting.
-- The trap: Ananya Rao exists as two applicant rows (ids 1 and 2) with emails
-- differing only in letter case. Grouping by applicant id would miss her, so
-- we group by the lower-cased, trimmed email to get one identity per person.
-- A posting counts as "applied to" when the person has an interview for it.
SELECT LOWER(TRIM(a.email))              AS person_email,
       MIN(a.full_name)                  AS full_name,
       COUNT(DISTINCT i.job_posting_id)  AS postings_applied_to
FROM applicants a
JOIN interviews i ON i.applicant_id = a.id
GROUP BY LOWER(TRIM(a.email))
HAVING COUNT(DISTINCT i.job_posting_id) > 1
ORDER BY full_name;


-- Q4: Final-stage conversion rate per recruiter (passed / total Final interviews),
-- only for recruiters with at least 3 Final-stage interviews.
-- Pending (NULL) outcomes still count in the denominator, as "total" was asked.
-- Multiplying by 1.0 avoids integer division.
SELECT r.name AS recruiter,
       COUNT(*)                                                   AS final_interviews,
       SUM(CASE WHEN i.outcome = 'passed' THEN 1 ELSE 0 END)      AS passed,
       ROUND(100.0 * SUM(CASE WHEN i.outcome = 'passed' THEN 1 ELSE 0 END)
             / COUNT(*), 1)                                       AS conversion_pct
FROM interviews i
JOIN job_postings jp ON jp.id = i.job_posting_id
JOIN recruiters r    ON r.id  = jp.recruiter_id
WHERE i.stage = 'Final'
GROUP BY r.id, r.name
HAVING COUNT(*) >= 3
ORDER BY conversion_pct DESC;


-- Q5 (Bonus): Recruiter with the most successful placements (passed at Final)
-- in each department. RANK() (not ROW_NUMBER) so a tie for first place shows
-- every tied recruiter. Departments with no placements do not appear.
WITH placements AS (
    SELECT jp.department,
           r.name       AS recruiter,
           COUNT(*)     AS placements
    FROM interviews i
    JOIN job_postings jp ON jp.id = i.job_posting_id
    JOIN recruiters r    ON r.id  = jp.recruiter_id
    WHERE i.stage = 'Final'
      AND i.outcome = 'passed'
    GROUP BY jp.department, r.id, r.name
),
ranked AS (
    SELECT department,
           recruiter,
           placements,
           RANK() OVER (PARTITION BY department ORDER BY placements DESC) AS rnk
    FROM placements
)
SELECT department, recruiter, placements
FROM ranked
WHERE rnk = 1
ORDER BY department;
