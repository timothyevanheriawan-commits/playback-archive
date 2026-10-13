-- 01_skips.sql
-- Question 1: what predicts a skip?
--
-- THE SKIP RULE WAS REVISED AFTER LOOKING AT REAL DATA (see METHODS.md, decision 4).
-- Spotify's `skipped` flag is not logged before 2022 and from 2023 it behaves like
-- "did not finish the track". The forward-button label (`fwdbtn`) also changes meaning
-- across years. Duration is the only signal that is comparable across the whole history, so:
--
--     is_skip   = played under SKIP_MS AND the stream was ended by the user
--                 (reason_end is fwdbtn, endplay or backbtn)
--     is_bounce = the same, but under BOUNCE_MS (sampled and dropped almost instantly)
--
-- Short plays that ended because of a logout, crash, remote device or track error are
-- not counted as skips.

CREATE OR REPLACE TABLE m_skips AS
WITH track_stats AS (
    SELECT
        track_uri,
        -- Track length is not in the export. A track is an "interlude" only if it was
        -- COMPLETED naturally in under MIN_TRACK_MS. The test must not look at skips:
        -- an earlier version used the typical play length, which wrongly dropped every
        -- track that was only ever skipped (selection bias).
        bool_or(reason_end = 'trackdone' AND ms_played < {{MIN_TRACK_MS}}) AS is_interlude,
        min(start_ts)                                                      AS first_heard_ts
    FROM stg_streams
    GROUP BY 1
)
SELECT
    s.stream_id,
    s.start_ts,
    s.end_ts,
    s.start_local,
    s.local_date,
    s.hour_local,
    s.dow,
    s.is_weekend,
    s.platform_family,
    s.shuffle,
    s.reason_start,
    s.reason_end,
    s.ms_played,
    s.track_uri,
    coalesce(s.skipped_flag, false)                             AS def_flag,
    (s.reason_end = 'fwdbtn')                                   AS def_fwd,
    (s.ms_played < {{SKIP_MS}})                                 AS def_short,
    (s.ms_played < {{SKIP_MS}} AND s.reason_end = 'fwdbtn')     AS def_old_primary,
    (s.ms_played < {{SKIP_MS}}
        AND s.reason_end IN ('fwdbtn', 'endplay', 'backbtn'))   AS is_skip,
    (s.ms_played < {{BOUNCE_MS}}
        AND s.reason_end IN ('fwdbtn', 'endplay', 'backbtn'))   AS is_bounce,
    count(*) OVER (
        PARTITION BY s.track_uri
        ORDER BY s.start_ts, s.stream_id
        ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING
    )                                                           AS prior_plays,
    date_diff('day', t.first_heard_ts, s.start_ts)              AS days_since_first,
    NOT t.is_interlude                                          AS eligible   -- drops short tracks and intros
FROM stg_streams s
JOIN track_stats t ON t.track_uri = s.track_uri;


-- Tidy long table of skip rates with Wilson 95% intervals (dashboard friendly).
CREATE OR REPLACE TABLE m_skip_rates AS
WITH e AS (
    SELECT
        *,
        CASE
            WHEN prior_plays = 0 THEN '1 first listen'
            WHEN prior_plays <= 2 THEN '2 2nd-3rd listen'
            WHEN prior_plays <= 9 THEN '3 4th-10th listen'
            ELSE '4 11th+ listen'
        END AS familiarity,
        CASE
            WHEN reason_start IN ('trackdone', 'fwdbtn', 'clickrow') THEN reason_start
            ELSE 'other'
        END AS reason_start_grp
    FROM m_skips
    WHERE eligible
),
agg AS (
    SELECT 'hour' AS dimension, lpad(CAST(hour_local AS VARCHAR), 2, '0') AS level,
           hour_local AS sort_key, count(*) AS streams, sum(CAST(is_skip AS INT)) AS skips
    FROM e GROUP BY ALL
    UNION ALL
    SELECT 'weekday', (['Mon','Tue','Wed','Thu','Fri','Sat','Sun'])[dow], dow,
           count(*), sum(CAST(is_skip AS INT))
    FROM e GROUP BY ALL
    UNION ALL
    SELECT 'platform', platform_family, 0, count(*), sum(CAST(is_skip AS INT))
    FROM e GROUP BY ALL
    UNION ALL
    SELECT 'shuffle', CASE WHEN shuffle THEN 'on' ELSE 'off' END, 0,
           count(*), sum(CAST(is_skip AS INT))
    FROM e GROUP BY ALL
    UNION ALL
    SELECT 'how it started', reason_start_grp, 0, count(*), sum(CAST(is_skip AS INT))
    FROM e GROUP BY ALL
    UNION ALL
    SELECT 'familiarity', substr(familiarity, 3), CAST(substr(familiarity, 1, 1) AS INT),
           count(*), sum(CAST(is_skip AS INT))
    FROM e GROUP BY ALL
    UNION ALL
    SELECT 'year', CAST(year(local_date) AS VARCHAR), year(local_date),
           count(*), sum(CAST(is_skip AS INT))
    FROM e GROUP BY ALL
),
rates AS (
    SELECT *, skips * 1.0 / streams AS skip_rate FROM agg
)
SELECT
    dimension,
    level,
    sort_key,
    streams,
    skips,
    skip_rate,
    ((skip_rate + 1.96*1.96/(2*streams))
        - 1.96 * sqrt(skip_rate*(1-skip_rate)/streams + 1.96*1.96/(4*streams*streams)))
        / (1 + 1.96*1.96/streams)                                 AS ci_low,
    ((skip_rate + 1.96*1.96/(2*streams))
        + 1.96 * sqrt(skip_rate*(1-skip_rate)/streams + 1.96*1.96/(4*streams*streams)))
        / (1 + 1.96*1.96/streams)                                 AS ci_high
FROM rates
ORDER BY dimension, sort_key, level;


-- How much do the competing skip definitions disagree?
CREATE OR REPLACE TABLE m_skip_definitions AS
WITH e AS (SELECT * FROM m_skips WHERE eligible),
n AS (SELECT count(*) AS total FROM e),
d AS (
    SELECT 'Spotify skipped flag (all years)' AS definition, sum(CAST(def_flag AS INT)) AS flagged FROM e
    UNION ALL SELECT 'reason_end = fwdbtn', sum(CAST(def_fwd AS INT)) FROM e
    UNION ALL SELECT 'played under threshold', sum(CAST(def_short AS INT)) FROM e
    UNION ALL SELECT 'OLD primary: fwdbtn and under threshold', sum(CAST(def_old_primary AS INT)) FROM e
    UNION ALL SELECT 'PRIMARY: under threshold, ended by user', sum(CAST(is_skip AS INT)) FROM e
    UNION ALL SELECT 'bounce: under 5 s, ended by user', sum(CAST(is_bounce AS INT)) FROM e
    UNION ALL SELECT 'flag set, not primary', sum(CAST(def_flag AND NOT is_skip AS INT)) FROM e
    UNION ALL SELECT 'primary, flag not set', sum(CAST(is_skip AND NOT def_flag AS INT)) FROM e
)
SELECT d.definition, n.total AS streams, d.flagged, d.flagged * 1.0 / n.total AS share
FROM d CROSS JOIN n;


-- Per-year view of every signal. This is the evidence that logging changed over time.
CREATE OR REPLACE TABLE m_skip_by_year AS
SELECT
    year(local_date)                                              AS year,
    count(*)                                                      AS streams,
    avg(CAST(def_flag AS INT))                                    AS flag_rate,
    avg(CAST(def_fwd AS INT))                                     AS fwd_rate,
    avg(CASE WHEN reason_end = 'endplay' THEN 1.0 ELSE 0.0 END)   AS endplay_rate,
    avg(CAST(is_skip AS INT))                                     AS primary_skip_rate,
    avg(CAST(is_bounce AS INT))                                   AS bounce_rate
FROM m_skips
WHERE eligible
GROUP BY 1
ORDER BY 1;
