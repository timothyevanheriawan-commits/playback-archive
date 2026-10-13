-- 06_kpis.sql
-- Headline numbers for the top of the dashboard.

CREATE OR REPLACE TABLE m_range AS
SELECT
    min(local_date) AS first_date,
    max(local_date) AS last_date,
    date_diff('day', min(local_date), max(local_date)) + 1 AS days_span
FROM stg_streams;

CREATE OR REPLACE TABLE m_kpis AS
SELECT 'streams_total' AS kpi, CAST(count(*) AS DOUBLE) AS value FROM stg_streams
UNION ALL SELECT 'hours_total', sum(ms_played) / 3600000.0 FROM stg_streams
UNION ALL SELECT 'qualified_streams', CAST(count(*) AS DOUBLE) FROM m_qualified
UNION ALL SELECT 'distinct_artists', CAST(count(DISTINCT artist) AS DOUBLE) FROM m_qualified
UNION ALL SELECT 'distinct_tracks', CAST(count(DISTINCT track_uri) AS DOUBLE) FROM m_qualified
UNION ALL SELECT 'skip_rate', avg(CAST(is_skip AS INT)) FROM m_skips WHERE eligible
UNION ALL SELECT 'sessions', CAST(count(*) AS DOUBLE) FROM m_sessions
UNION ALL SELECT 'median_session_min', median(wall_min) FROM m_sessions
UNION ALL SELECT 'binge_tracks', CAST(count(*) AS DOUBLE) FROM m_binge_tracks;
