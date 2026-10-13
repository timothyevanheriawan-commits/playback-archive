-- 05_daily.sql
-- Base table for Question 5 (life overlay): one row per calendar day, zero filled.
-- The event comparison itself happens in src/analysis.py.

CREATE OR REPLACE TABLE m_daily AS
WITH cal AS (
    SELECT CAST(d AS DATE) AS d
    FROM generate_series(
        (SELECT min(local_date) FROM stg_streams),
        (SELECT max(local_date) FROM stg_streams),
        INTERVAL 1 DAY
    ) AS t(d)
),
st AS (
    SELECT local_date AS d, count(*) AS streams, sum(ms_played) / 60000.0 AS listen_min
    FROM stg_streams GROUP BY 1
),
sk AS (
    SELECT local_date AS d, count(*) AS eligible_streams, sum(CAST(is_skip AS INT)) AS skips
    FROM m_skips WHERE eligible GROUP BY 1
),
na AS (
    SELECT first_date AS d, count(*) AS new_artists FROM m_first_artist GROUP BY 1
),
se AS (
    SELECT CAST(start_local AS DATE) AS d, count(*) AS sessions FROM m_sessions GROUP BY 1
)
SELECT
    cal.d                                  AS date,
    coalesce(st.streams, 0)                AS streams,
    coalesce(st.listen_min, 0)             AS listen_min,
    coalesce(sk.eligible_streams, 0)       AS eligible_streams,
    coalesce(sk.skips, 0)                  AS skips,
    coalesce(na.new_artists, 0)            AS new_artists,
    coalesce(se.sessions, 0)               AS sessions
FROM cal
LEFT JOIN st ON st.d = cal.d
LEFT JOIN sk ON sk.d = cal.d
LEFT JOIN na ON na.d = cal.d
LEFT JOIN se ON se.d = cal.d
ORDER BY cal.d;
