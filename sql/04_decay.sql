-- 04_decay.sql
-- Question 4: taste decay. How long does a binged track stay hot?
--
-- Plays are bucketed into weeks since each track's first qualified play.
-- A track is a "binge" if its busiest week has at least BINGE_MIN_PLAYS plays.
--
-- Two half-life definitions are computed side by side:
--   naive     : first week after the peak with plays <= half the peak.
--               Noisy: one quiet week "decays" a track that comes right back.
--   sustained : first week after the peak from which the next DECAY_QUIET_WEEKS
--               weeks ALL stay at or below half the peak.
-- Tracks that never decay by the end of the data are right-censored, which the
-- Python step (analysis.py) handles with a Kaplan-Meier curve.

CREATE OR REPLACE TABLE m_data_end AS
SELECT max(local_date) AS data_end FROM stg_streams;

CREATE OR REPLACE TABLE m_track_weekly AS
SELECT
    q.track_uri,
    date_diff('day', f.first_date, q.local_date) // 7 AS wk,
    count(*)                                          AS plays
FROM m_qualified q
JOIN m_first_track f ON f.track_uri = q.track_uri
GROUP BY 1, 2;

CREATE OR REPLACE TABLE m_binge_tracks AS
WITH ranked AS (
    SELECT
        track_uri,
        wk    AS peak_wk,
        plays AS peak_plays,
        row_number() OVER (PARTITION BY track_uri ORDER BY plays DESC, wk) AS rn
    FROM m_track_weekly
)
SELECT
    r.track_uri,
    f.track_name,
    f.artist,
    f.first_date,
    r.peak_wk,
    r.peak_plays,
    date_diff('day', f.first_date, d.data_end) // 7 AS data_end_wk
FROM ranked r
JOIN m_first_track f ON f.track_uri = r.track_uri
CROSS JOIN m_data_end d
WHERE r.rn = 1
  AND r.peak_plays >= {{BINGE_MIN_PLAYS}};

CREATE OR REPLACE TABLE m_decay_series AS
WITH grid AS (
    SELECT
        b.track_uri,
        b.peak_wk,
        b.peak_plays,
        b.data_end_wk,
        g.wk
    FROM m_binge_tracks b,
         LATERAL (SELECT unnest(generate_series(b.peak_wk, b.data_end_wk)) AS wk) g
),
filled AS (
    SELECT
        g.*,
        coalesce(w.plays, 0) AS plays
    FROM grid g
    LEFT JOIN m_track_weekly w
           ON w.track_uri = g.track_uri AND w.wk = g.wk
)
SELECT
    *,
    plays <= peak_plays / 2.0 AS is_below_half,
    max(plays) OVER (
        PARTITION BY track_uri ORDER BY wk
        ROWS BETWEEN CURRENT ROW AND {{QUIET_FWD}} FOLLOWING
    ) AS fwd_max,
    count(*) OVER (
        PARTITION BY track_uri ORDER BY wk
        ROWS BETWEEN CURRENT ROW AND {{QUIET_FWD}} FOLLOWING
    ) AS fwd_n
FROM filled;

CREATE OR REPLACE TABLE m_decay_tracks AS
WITH h AS (
    SELECT
        track_uri,
        min(wk - peak_wk) FILTER (WHERE wk > peak_wk AND is_below_half)  AS naive_halflife_wk,
        min(wk - peak_wk) FILTER (
            WHERE wk > peak_wk
              AND fwd_n = {{DECAY_QUIET_WEEKS}}
              AND fwd_max <= peak_plays / 2.0
        )                                                                AS sustained_halflife_wk
    FROM m_decay_series
    GROUP BY 1
)
SELECT
    b.track_uri,
    b.track_name,
    b.artist,
    b.first_date,
    b.peak_wk,
    b.peak_plays,
    h.naive_halflife_wk,
    h.sustained_halflife_wk,
    b.data_end_wk - b.peak_wk                         AS observed_wk_after_peak,
    h.sustained_halflife_wk IS NULL                   AS is_censored,
    (b.data_end_wk - b.peak_wk) >= {{MIN_OBS_WEEKS}}  AS is_usable
FROM m_binge_tracks b
JOIN h ON h.track_uri = b.track_uri;

CREATE OR REPLACE TABLE m_decay_summary AS
SELECT
    count(*)                                                       AS binge_tracks,
    count(*) FILTER (WHERE is_usable)                              AS usable_tracks,
    median(naive_halflife_wk) FILTER (WHERE is_usable)             AS median_naive_wk,
    median(sustained_halflife_wk) FILTER (WHERE is_usable)         AS median_sustained_wk_decayed_only,
    avg(CAST(is_censored AS INT)) FILTER (WHERE is_usable)         AS share_still_alive
FROM m_decay_tracks;
