-- 03_sessions.sql
-- Question 3: sessionization (window functions: LAG, running SUM).
--
-- A new session starts when the gap between the END of the previous stream and
-- the START of this one exceeds GAP_MIN minutes. The gap is swept over a grid so
-- the dashboard can show how sensitive the conclusions are to that choice.

CREATE OR REPLACE TABLE m_sessions_all AS
WITH gaps AS (
    SELECT unnest([{{GAP_GRID}}]) AS gap_min
),
base AS (
    SELECT
        g.gap_min,
        s.stream_id,
        s.start_ts,
        s.end_ts,
        s.ms_played,
        s.is_skip
    FROM m_skips s
    CROSS JOIN gaps g
),
lagged AS (
    SELECT
        *,
        LAG(end_ts) OVER (PARTITION BY gap_min ORDER BY end_ts, stream_id) AS prev_end_ts
    FROM base
),
flagged AS (
    SELECT
        *,
        CASE
            WHEN prev_end_ts IS NULL THEN 1
            WHEN date_diff('second', prev_end_ts, start_ts) > gap_min * 60 THEN 1
            ELSE 0
        END AS is_new_session
    FROM lagged
),
numbered AS (
    SELECT
        *,
        SUM(is_new_session) OVER (
            PARTITION BY gap_min
            ORDER BY end_ts, stream_id
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) AS session_id
    FROM flagged
)
SELECT
    gap_min,
    session_id,
    min(start_ts)                                            AS start_ts,
    max(end_ts)                                              AS end_ts,
    count(*)                                                 AS tracks,
    sum(ms_played) / 60000.0                                 AS listened_min,
    date_diff('second', min(start_ts), max(end_ts)) / 60.0   AS wall_min,
    sum(CAST(is_skip AS INT))                                AS skips,
    avg(CAST(is_skip AS INT))                                AS skip_rate
FROM numbered
GROUP BY gap_min, session_id;

-- Primary sessions (the gap chosen in config) with local time fields.
CREATE OR REPLACE TABLE m_sessions AS
SELECT
    session_id,
    start_ts,
    end_ts,
    timezone('{{TZ}}', start_ts)                AS start_local,
    hour(timezone('{{TZ}}', start_ts))          AS hour_local,
    isodow(timezone('{{TZ}}', start_ts))        AS dow,
    tracks,
    listened_min,
    wall_min,
    skips,
    skip_rate
FROM m_sessions_all
WHERE gap_min = {{GAP_MIN}};

CREATE OR REPLACE TABLE m_session_by_hour AS
SELECT
    hour_local,
    count(*)                    AS sessions,
    median(tracks)              AS median_tracks,
    median(wall_min)            AS median_wall_min,
    quantile_cont(wall_min, 0.9) AS p90_wall_min,
    avg(skip_rate)              AS avg_skip_rate
FROM m_sessions
GROUP BY 1
ORDER BY 1;

CREATE OR REPLACE TABLE m_session_by_dow AS
SELECT
    dow,
    (['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])[dow] AS weekday,
    count(*)                    AS sessions,
    median(tracks)              AS median_tracks,
    median(wall_min)            AS median_wall_min,
    quantile_cont(wall_min, 0.9) AS p90_wall_min,
    avg(skip_rate)              AS avg_skip_rate
FROM m_sessions
GROUP BY 1
ORDER BY 1;

CREATE OR REPLACE TABLE m_session_heat AS
SELECT
    dow,
    hour_local,
    count(*)         AS sessions,
    median(wall_min) AS median_wall_min
FROM m_sessions
GROUP BY 1, 2
ORDER BY 1, 2;

CREATE OR REPLACE TABLE m_session_gap_sensitivity AS
SELECT
    gap_min,
    count(*)                      AS sessions,
    median(tracks)                AS median_tracks,
    median(wall_min)              AS median_wall_min,
    quantile_cont(wall_min, 0.9)  AS p90_wall_min
FROM m_sessions_all
GROUP BY 1
ORDER BY 1;
