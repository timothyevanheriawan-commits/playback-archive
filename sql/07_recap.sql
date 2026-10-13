-- 07_recap.sql
-- "Wrapped-style" recaps. Monthly cards plus 15 insights across the whole history.
-- Everything here is an AGGREGATE. Names appear only in the small recap tables, and
-- `python -m src.export --redact-tracks` hashes them before publishing.
--
-- "Qualified" = played at least SKIP_MS. "Skip" = see 01_skips.sql.

CREATE OR REPLACE TABLE r_streams AS
SELECT
    s.stream_id,
    s.track_uri,
    s.track_name,
    s.artist,
    s.start_ts,
    s.local_date,
    CAST(date_trunc('month', s.local_date) AS DATE)  AS month,
    year(s.local_date)                               AS yr,
    s.hour_local,
    s.dow,
    s.is_weekend,
    s.platform_family,
    s.shuffle,
    s.reason_end,
    s.ms_played,
    k.is_skip,
    k.eligible,
    (s.ms_played >= {{SKIP_MS}})                     AS is_qualified,
    CASE WHEN s.hour_local <= 5  THEN 'night'
         WHEN s.hour_local <= 11 THEN 'morning'
         WHEN s.hour_local <= 17 THEN 'afternoon'
         ELSE 'evening' END                          AS daypart
FROM stg_streams s
JOIN m_skips k ON k.stream_id = s.stream_id;

-- ===================================================================== monthly cards
CREATE OR REPLACE TABLE r_month_track AS
SELECT month, track_uri, any_value(track_name) AS track_name, any_value(artist) AS artist,
       count(*) AS plays, sum(ms_played) AS ms
FROM r_streams WHERE is_qualified GROUP BY 1, 2;

CREATE OR REPLACE TABLE r_month_artist AS
SELECT month, artist, count(*) AS plays, sum(ms_played) AS ms
FROM r_streams WHERE is_qualified AND artist IS NOT NULL GROUP BY 1, 2;

CREATE OR REPLACE TABLE m_recap_monthly AS
WITH base AS (
    SELECT month,
           count(*)                                              AS qualified_streams,
           sum(ms_played) / 3600000.0                            AS hours,
           avg(CASE WHEN hour_local <= 5 THEN 1.0 ELSE 0.0 END)  AS night_share
    FROM r_streams WHERE is_qualified GROUP BY 1
),
song AS (
    SELECT month, track_name, artist, plays AS track_plays
    FROM r_month_track
    QUALIFY row_number() OVER (PARTITION BY month ORDER BY plays DESC, ms DESC, track_uri) = 1
),
topart AS (
    SELECT month, artist AS top_artist, plays AS top_artist_plays
    FROM r_month_artist
    QUALIFY row_number() OVER (PARTITION BY month ORDER BY plays DESC, ms DESC, artist) = 1
),
taste AS (
    -- taste age: median days between a track's first play and this month's plays of it
    SELECT q.month, median(date_diff('day', f.first_ts, q.start_ts)) AS taste_age_days
    FROM r_streams q
    JOIN m_first_track f ON f.track_uri = q.track_uri
    WHERE q.is_qualified
    GROUP BY 1
),
variety AS (
    WITH p AS (
        SELECT month, plays * 1.0 / sum(plays) OVER (PARTITION BY month) AS share
        FROM r_month_artist
    )
    SELECT month,
           max(share)                           AS top_artist_share,
           exp(-sum(share * ln(share)))         AS effective_artists
    FROM p GROUP BY 1
),
longest AS (
    SELECT month, session_date, wall_min, tracks
    FROM (
        SELECT CAST(date_trunc('month', CAST(start_local AS DATE)) AS DATE) AS month,
               CAST(start_local AS DATE) AS session_date, wall_min, tracks
        FROM m_sessions
    )
    QUALIFY row_number() OVER (PARTITION BY month ORDER BY wall_min DESC) = 1
),
joined AS (
    SELECT b.month,
           b.qualified_streams,
           round(b.hours, 2)                                  AS hours,
           b.qualified_streams < {{RECAP_MIN_STREAMS}}        AS thin_month,
           s.track_name, s.artist, s.track_plays,
           a.top_artist, a.top_artist_plays,
           b.night_share, t.taste_age_days,
           v.top_artist_share, v.effective_artists,
           l.session_date AS longest_session_date,
           l.wall_min     AS longest_session_min,
           l.tracks       AS longest_session_tracks
    FROM base b
    LEFT JOIN song    s ON s.month = b.month
    LEFT JOIN topart  a ON a.month = b.month
    LEFT JOIN taste   t ON t.month = b.month
    LEFT JOIN variety v ON v.month = b.month
    LEFT JOIN longest l ON l.month = b.month
),
mu AS (
    SELECT avg(night_share) AS mu_n, stddev_samp(night_share) AS sd_n,
           avg(taste_age_days) AS mu_t, stddev_samp(taste_age_days) AS sd_t,
           avg(top_artist_share) AS mu_s, stddev_samp(top_artist_share) AS sd_s,
           quantile_cont(top_artist_share, 0.8) AS q_top,
           quantile_cont(effective_artists, 0.8) AS q_eff
    FROM joined WHERE NOT thin_month
),
scored AS (
    SELECT j.*,
           coalesce((j.night_share - mu.mu_n) / NULLIF(mu.sd_n, 0), 0)          AS z_night,
           coalesce((j.taste_age_days - mu.mu_t) / NULLIF(mu.sd_t, 0), 0)       AS z_taste,
           coalesce((j.top_artist_share - mu.mu_s) / NULLIF(mu.sd_s, 0), 0)     AS z_share,
           mu.q_top, mu.q_eff
    FROM joined j CROSS JOIN mu
)
SELECT
    month, qualified_streams, hours, thin_month,
    track_name, artist, track_plays,
    top_artist, top_artist_plays,
    night_share, taste_age_days, top_artist_share, effective_artists,
    CASE WHEN thin_month THEN NULL
         WHEN top_artist_share >= q_top THEN 'One-artist month'
         WHEN effective_artists >= q_eff THEN 'Explorer month'
         ELSE 'Balanced month' END                                       AS variety_label,
    CASE WHEN thin_month THEN NULL
         WHEN abs(z_night) >= abs(z_taste) AND abs(z_night) >= abs(z_share)
              THEN CASE WHEN z_night >= 0 THEN 'Night-owl month' ELSE 'Daylight month' END
         WHEN abs(z_taste) >= abs(z_share)
              THEN CASE WHEN z_taste >= 0 THEN 'Rewind month' ELSE 'Fresh-ears month' END
         ELSE CASE WHEN z_share >= 0 THEN 'One-artist month' ELSE 'Spread-out month' END
    END                                                                  AS surprise_label,
    greatest(abs(z_night), abs(z_taste), abs(z_share))                   AS surprise_z,
    longest_session_date, longest_session_min, longest_session_tracks
FROM scored
ORDER BY month;

-- ===================================================================== 1 night owl
CREATE OR REPLACE TABLE m_recap_night_owl AS
WITH y AS (
    SELECT yr AS year, count(*) AS qualified_streams,
           avg(CASE WHEN hour_local <= 5 THEN 1.0 ELSE 0.0 END) AS night_share
    FROM r_streams WHERE is_qualified GROUP BY 1
),
h AS (
    SELECT yr AS year, hour_local AS peak_hour
    FROM (SELECT yr, hour_local, count(*) AS n FROM r_streams WHERE is_qualified GROUP BY 1, 2)
    QUALIFY row_number() OVER (PARTITION BY yr ORDER BY n DESC, hour_local) = 1
)
SELECT y.year, y.qualified_streams, y.night_share, h.peak_hour
FROM y JOIN h USING (year) ORDER BY y.year;

-- ===================================================================== 2 slow burns
CREATE OR REPLACE TABLE m_recap_slow_burns AS
WITH first_stream AS (
    SELECT artist, start_ts AS first_ts, is_skip AS first_was_skip
    FROM r_streams WHERE artist IS NOT NULL
    QUALIFY row_number() OVER (PARTITION BY artist ORDER BY start_ts, stream_id) = 1
),
tot AS (
    SELECT artist, count(*) AS qualified_plays, min(start_ts) AS first_q_ts
    FROM r_streams WHERE is_qualified AND artist IS NOT NULL GROUP BY 1
),
top AS (SELECT * FROM tot ORDER BY qualified_plays DESC LIMIT {{TOPN}})
SELECT t.artist,
       CAST(timezone('{{TZ}}', f.first_ts) AS DATE)        AS first_heard,
       date_diff('day', f.first_ts, t.first_q_ts)          AS days_until_first_real_listen,
       t.qualified_plays
FROM top t JOIN first_stream f USING (artist)
WHERE f.first_was_skip
ORDER BY days_until_first_real_listen DESC;

-- ===================================================================== 3 burnout record
CREATE OR REPLACE TABLE m_recap_burnout AS
SELECT track_name, artist, peak_plays,
       first_date + CAST(peak_wk * 7 AS INTEGER) AS peak_week_start,
       sustained_halflife_wk, is_censored, observed_wk_after_peak
FROM m_decay_tracks
ORDER BY peak_plays DESC
LIMIT 10;

-- ===================================================================== 4 comfort songs
CREATE OR REPLACE TABLE m_recap_comfort AS
SELECT any_value(track_name) AS track_name, any_value(artist) AS artist,
       count(*) FILTER (WHERE reason_end = 'trackdone') AS completions,
       min(local_date) AS first_date, max(local_date) AS last_date
FROM r_streams
GROUP BY track_uri
HAVING count(*) FILTER (WHERE is_skip) = 0
   AND count(*) FILTER (WHERE reason_end = 'trackdone') >= {{COMFORT_MIN_PLAYS}}
ORDER BY completions DESC
LIMIT 15;

-- ===================================================================== 5 love-hate list
CREATE OR REPLACE TABLE m_recap_love_hate AS
WITH t AS (
    SELECT track_uri, any_value(track_name) AS track_name, any_value(artist) AS artist,
           count(*) FILTER (WHERE is_qualified) AS qualified_plays,
           count(*) FILTER (WHERE is_skip)      AS skips,
           count(*)                             AS streams
    FROM r_streams WHERE eligible GROUP BY 1
),
ov AS (SELECT avg(CAST(is_skip AS INT)) AS overall FROM r_streams WHERE eligible)
SELECT track_name, artist, qualified_plays, skips, streams, skips * 1.0 / streams AS skip_rate
FROM t CROSS JOIN ov
WHERE qualified_plays >= {{LOVEHATE_MIN_PLAYS}} AND skips * 1.0 / streams >= ov.overall
ORDER BY qualified_plays DESC
LIMIT 15;

-- ===================================================================== 6 reunions
CREATE OR REPLACE TABLE m_recap_reunions AS
WITH d AS (
    SELECT artist, local_date AS d, count(*) AS plays
    FROM r_streams WHERE is_qualified AND artist IS NOT NULL GROUP BY 1, 2
),
g AS (
    SELECT artist, d,
           LAG(d) OVER (PARTITION BY artist ORDER BY d) AS prev_d,
           sum(plays) OVER (PARTITION BY artist ORDER BY d
                            ROWS BETWEEN UNBOUNDED PRECEDING AND 1 PRECEDING) AS plays_before,
           sum(plays) OVER (PARTITION BY artist) AS plays_total
    FROM d
)
SELECT artist,
       date_diff('day', prev_d, d)  AS gap_days,
       prev_d                       AS left_on,
       d                            AS returned_on,
       plays_before,
       plays_total - plays_before   AS plays_since_return
FROM g
WHERE prev_d IS NOT NULL
  AND date_diff('day', prev_d, d) >= {{REUNION_GAP_DAYS}}
  AND plays_before >= {{REUNION_MIN_PLAYS}}
  AND plays_total - plays_before >= {{REUNION_MIN_PLAYS}}
QUALIFY row_number() OVER (PARTITION BY artist ORDER BY date_diff('day', prev_d, d) DESC) = 1
ORDER BY plays_since_return DESC
LIMIT 15;

-- ===================================================================== 9 records
CREATE OR REPLACE TABLE m_recap_records AS
WITH loop AS (
    SELECT track_name, artist, local_date,
           count(*) OVER (PARTITION BY track_uri ORDER BY start_ts
                          RANGE BETWEEN INTERVAL 24 HOURS PRECEDING AND CURRENT ROW) AS plays_24h
    FROM r_streams WHERE is_qualified
),
loop_best AS (SELECT * FROM loop ORDER BY plays_24h DESC, local_date LIMIT 1),
days AS (SELECT DISTINCT local_date AS d FROM stg_streams),
isl AS (SELECT d, d - CAST(row_number() OVER (ORDER BY d) AS INTEGER) AS grp FROM days),
streak AS (
    SELECT min(d) AS start_date, max(d) AS end_date, count(*) AS n
    FROM isl GROUP BY grp ORDER BY n DESC, start_date LIMIT 1
),
gaps AS (
    SELECT d AS end_d, LAG(d) OVER (ORDER BY d) AS start_d FROM days
),
drought AS (
    SELECT start_d + 1 AS start_date, end_d - 1 AS end_date,
           date_diff('day', start_d, end_d) - 1 AS n
    FROM gaps WHERE start_d IS NOT NULL ORDER BY n DESC, start_d LIMIT 1
)
SELECT 'most plays of one track in 24 hours' AS record, CAST(plays_24h AS DOUBLE) AS value,
       track_name, artist, local_date - 1 AS start_date, local_date AS end_date
FROM loop_best
UNION ALL
SELECT 'longest streak of days with any listening', CAST(n AS DOUBLE), NULL, NULL, start_date, end_date FROM streak
UNION ALL
SELECT 'longest drought (days with no listening)', CAST(n AS DOUBLE), NULL, NULL, start_date, end_date FROM drought;

-- ===================================================================== 10 device migration
CREATE OR REPLACE TABLE m_recap_devices AS
WITH y AS (
    SELECT yr AS year, platform_family, count(*) AS streams,
           sum(ms_played) / 3600000.0 AS hours,
           avg(CASE WHEN eligible THEN CAST(is_skip AS INT) END) AS skip_rate
    FROM r_streams GROUP BY 1, 2
)
SELECT year, platform_family, streams,
       streams * 1.0 / sum(streams) OVER (PARTITION BY year) AS share_of_year,
       hours, skip_rate
FROM y ORDER BY year, streams DESC;

-- ===================================================================== 11 weekend vs weekday
CREATE OR REPLACE TABLE r_artist_mode AS
SELECT artist,
       count(*) FILTER (WHERE is_weekend)     AS we,
       count(*) FILTER (WHERE NOT is_weekend) AS wd
FROM r_streams WHERE is_qualified AND artist IS NOT NULL GROUP BY 1;

CREATE OR REPLACE TABLE m_recap_weekend AS
WITH tot AS (SELECT sum(we) AS we_t, sum(wd) AS wd_t FROM r_artist_mode),
s AS (
    SELECT a.artist, a.we AS plays_weekend, a.wd AS plays_weekday,
           a.we * 1.0 / tot.we_t AS weekend_share,
           a.wd * 1.0 / tot.wd_t AS weekday_share,
           ((a.we + 0.5) / tot.we_t) / ((a.wd + 0.5) / tot.wd_t) AS lift   -- >1 weekend, <1 weekday
    FROM r_artist_mode a CROSS JOIN tot
    WHERE a.we + a.wd >= {{RECAP_MIN_ARTIST_PLAYS}}
)
SELECT * FROM (SELECT 'weekend' AS side, * FROM s ORDER BY lift DESC LIMIT 10)
UNION ALL
SELECT * FROM (SELECT 'weekday' AS side, * FROM s ORDER BY lift ASC LIMIT 10);

-- ===================================================================== 12 anthem of each year
CREATE OR REPLACE TABLE m_recap_anthems AS
WITH t AS (
    SELECT year(f.first_date) AS year, q.track_uri,
           any_value(q.track_name) AS track_name, any_value(q.artist) AS artist,
           count(*) AS plays, sum(q.ms_played) AS ms, min(f.first_date) AS first_date
    FROM r_streams q JOIN m_first_track f ON f.track_uri = q.track_uri
    WHERE q.is_qualified AND year(q.local_date) = year(f.first_date)
    GROUP BY 1, 2
)
SELECT year, track_name, artist, plays, first_date
FROM t
QUALIFY row_number() OVER (PARTITION BY year ORDER BY plays DESC, ms DESC, track_uri) = 1
ORDER BY year;

-- ===================================================================== 13 shuffle vs shuffle off
CREATE OR REPLACE TABLE m_recap_shuffle AS
WITH a AS (
    SELECT CASE WHEN shuffle THEN 'shuffle on' ELSE 'shuffle off' END AS mode, artist, count(*) AS plays
    FROM r_streams WHERE is_qualified AND artist IS NOT NULL GROUP BY 1, 2
),
r AS (
    SELECT mode, artist, plays,
           plays * 1.0 / sum(plays) OVER (PARTITION BY mode) AS share_of_mode,
           row_number() OVER (PARTITION BY mode ORDER BY plays DESC, artist) AS rank
    FROM a
)
SELECT * FROM r WHERE rank <= {{TOPN}} ORDER BY mode, rank;

-- ===================================================================== 14 daypart identity
CREATE OR REPLACE TABLE m_recap_daypart AS
WITH a AS (
    SELECT daypart, artist, count(*) AS plays
    FROM r_streams WHERE is_qualified AND artist IS NOT NULL GROUP BY 1, 2
),
r AS (
    SELECT daypart, artist, plays,
           plays * 1.0 / sum(plays) OVER (PARTITION BY daypart) AS share_of_daypart,
           row_number() OVER (PARTITION BY daypart ORDER BY plays DESC, artist) AS rank
    FROM a
)
SELECT daypart, rank, artist, plays, share_of_daypart
FROM r WHERE rank <= 3
ORDER BY CASE daypart WHEN 'morning' THEN 1 WHEN 'afternoon' THEN 2 WHEN 'evening' THEN 3 ELSE 4 END, rank;

-- ===================================================================== 15 one-week wonders
CREATE OR REPLACE TABLE r_wonders AS
WITH t AS (
    SELECT track_uri, any_value(track_name) AS track_name, any_value(artist) AS artist,
           count(*) AS plays, min(local_date) AS first_date, max(local_date) AS last_date
    FROM r_streams WHERE is_qualified GROUP BY 1
)
SELECT t.track_name, t.artist, t.plays, t.first_date, t.last_date
FROM t CROSS JOIN m_data_end d
WHERE t.plays >= {{WONDER_MIN_PLAYS}}
  AND date_diff('day', t.first_date, t.last_date) <= {{WONDER_SPAN_DAYS}}
  AND date_diff('day', t.last_date, d.data_end) >= {{WONDER_QUIET_DAYS}};

CREATE OR REPLACE TABLE m_recap_one_week_wonders AS
SELECT * FROM r_wonders ORDER BY plays DESC LIMIT 15;

-- ===================================================================== scalar facts
CREATE OR REPLACE TABLE m_recap_facts AS
SELECT 'weekend_weekday_top_artists_shared' AS stat,
       CAST((SELECT count(*) FROM
              (SELECT artist FROM r_artist_mode ORDER BY we DESC LIMIT {{TOPN}})
              JOIN (SELECT artist FROM r_artist_mode ORDER BY wd DESC LIMIT {{TOPN}}) USING (artist)) AS DOUBLE) AS value,
       'how many of the top {{TOPN}} weekend artists are also in the top {{TOPN}} weekday artists' AS detail
UNION ALL
SELECT 'shuffle_on_off_top_artists_shared',
       CAST((SELECT count(*) FROM (
              SELECT artist FROM m_recap_shuffle WHERE mode = 'shuffle on'
              INTERSECT
              SELECT artist FROM m_recap_shuffle WHERE mode = 'shuffle off')) AS DOUBLE),
       'how many of the top {{TOPN}} artists with shuffle on are also in the top {{TOPN}} with shuffle off'
UNION ALL
SELECT 'skip_rate_shuffle_on',
       (SELECT avg(CAST(is_skip AS INT)) FROM r_streams WHERE eligible AND shuffle),
       'share of eligible streams skipped with shuffle on'
UNION ALL
SELECT 'skip_rate_shuffle_off',
       (SELECT avg(CAST(is_skip AS INT)) FROM r_streams WHERE eligible AND NOT shuffle),
       'share of eligible streams skipped with shuffle off'
UNION ALL
SELECT 'one_week_wonders',
       CAST((SELECT count(*) FROM r_wonders) AS DOUBLE),
       'tracks played at least {{WONDER_MIN_PLAYS}} times within {{WONDER_SPAN_DAYS}} days and untouched for {{WONDER_QUIET_DAYS}}+ days'
UNION ALL
SELECT 'one_week_wonders_share_of_tracks',
       (SELECT count(*) FROM r_wonders) * 1.0 / (SELECT count(DISTINCT track_uri) FROM r_streams WHERE is_qualified),
       'share of all distinct qualified tracks'
UNION ALL
SELECT 'bounce_share_of_all_streams',
       (SELECT avg(CAST(is_bounce AS INT)) FROM m_skips),
       'streams under 5 s that you ended yourself';
