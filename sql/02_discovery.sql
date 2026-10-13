-- 02_discovery.sql
-- Question 2: discovery vs repeat listening.
--
-- A "discovery" only counts when the first listen was a QUALIFIED play
-- (ms_played >= SKIP_MS). Hitting an artist for 4 seconds and skipping is not
-- discovering them. The raw version is kept for comparison.

CREATE OR REPLACE TABLE m_qualified AS
SELECT
    stream_id,
    track_uri,
    track_name,
    artist,
    start_ts,
    local_date,
    CAST(date_trunc('month', local_date) AS DATE) AS month,
    ms_played
FROM stg_streams
WHERE ms_played >= {{SKIP_MS}};

CREATE OR REPLACE TABLE m_first_track AS
SELECT
    track_uri,
    any_value(track_name) AS track_name,
    any_value(artist)     AS artist,
    min(start_ts)         AS first_ts,
    min(local_date)       AS first_date
FROM m_qualified
GROUP BY 1;

CREATE OR REPLACE TABLE m_first_artist AS
SELECT
    artist,
    min(start_ts)                                       AS first_ts,
    min(local_date)                                     AS first_date,
    CAST(date_trunc('month', min(local_date)) AS DATE)  AS first_month
FROM m_qualified
WHERE artist IS NOT NULL
GROUP BY 1;

-- Naive version: any play, even a 2 second one, counts as discovery.
CREATE OR REPLACE TABLE m_first_artist_raw AS
SELECT
    artist,
    CAST(date_trunc('month', min(local_date)) AS DATE) AS first_month
FROM stg_streams
WHERE artist IS NOT NULL
GROUP BY 1;

CREATE OR REPLACE TABLE m_discovery_monthly AS
WITH monthly AS (
    SELECT
        month,
        count(*)                       AS streams,
        sum(ms_played) / 3600000.0     AS hours,
        count(DISTINCT artist)         AS distinct_artists,
        count(DISTINCT track_uri)      AS distinct_tracks
    FROM m_qualified
    GROUP BY 1
),
na  AS (SELECT first_month AS month, count(*) AS new_artists FROM m_first_artist GROUP BY 1),
nar AS (SELECT first_month AS month, count(*) AS new_artists_raw FROM m_first_artist_raw GROUP BY 1),
nt  AS (
    SELECT CAST(date_trunc('month', first_date) AS DATE) AS month, count(*) AS new_tracks
    FROM m_first_track GROUP BY 1
),
rp AS (
    SELECT
        q.month,
        avg(CASE WHEN q.start_ts > f.first_ts THEN 1.0 ELSE 0.0 END) AS replay_share
    FROM m_qualified q
    JOIN m_first_track f ON f.track_uri = q.track_uri
    GROUP BY 1
),
bounds AS (SELECT min(month) AS first_month, max(month) AS last_month FROM monthly)
SELECT
    m.month,
    m.streams,
    round(m.hours, 2)                                            AS hours,
    m.distinct_artists,
    m.distinct_tracks,
    coalesce(na.new_artists, 0)                                  AS new_artists,
    coalesce(nar.new_artists_raw, 0)                             AS new_artists_raw,
    coalesce(nt.new_tracks, 0)                                   AS new_tracks,
    coalesce(na.new_artists, 0) * 1.0 / m.distinct_artists       AS artist_discovery_rate,
    coalesce(nt.new_tracks, 0) * 1.0 / m.distinct_tracks         AS track_discovery_rate,
    rp.replay_share,
    date_diff('month', b.first_month, m.month)                   AS month_idx,
    date_diff('month', b.first_month, m.month) < 3               AS is_ramp_up,   -- everything is "new" at the start
    m.month = b.last_month                                       AS is_last_month -- may be a partial month
FROM monthly m
LEFT JOIN na  ON na.month  = m.month
LEFT JOIN nar ON nar.month = m.month
LEFT JOIN nt  ON nt.month  = m.month
LEFT JOIN rp  ON rp.month  = m.month
CROSS JOIN bounds b
ORDER BY m.month;
