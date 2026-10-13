-- 00_staging.sql
-- One clean row per MUSIC stream.
-- Source: raw_audio (whitelisted columns only, so IP data never lands in the database).
--
-- IMPORTANT: Spotify's `ts` is when the stream ENDED, not when it started.
-- Start time is derived as: start_ts = ts - ms_played.

SET TimeZone = 'UTC';

CREATE OR REPLACE TABLE stg_streams AS
WITH typed AS (
    SELECT
        CAST(ts AS TIMESTAMPTZ)                              AS end_ts,
        CAST(ms_played AS BIGINT)                            AS ms_played,
        lower(coalesce(platform, 'unknown'))                 AS platform_raw,
        master_metadata_track_name                           AS track_name,
        master_metadata_album_artist_name                    AS artist,
        master_metadata_album_album_name                     AS album,
        spotify_track_uri                                    AS track_uri,
        coalesce(reason_start, 'unknown')                    AS reason_start,
        coalesce(reason_end, 'unknown')                      AS reason_end,
        coalesce(TRY_CAST(shuffle AS BOOLEAN), false)        AS shuffle,
        TRY_CAST(skipped AS BOOLEAN)                         AS skipped_flag,
        coalesce(TRY_CAST(offline AS BOOLEAN), false)        AS offline,
        coalesce(TRY_CAST(incognito_mode AS BOOLEAN), false) AS incognito
    FROM raw_audio
    WHERE spotify_track_uri IS NOT NULL      -- drops podcasts and audiobooks
      AND master_metadata_track_name IS NOT NULL
      AND ms_played IS NOT NULL
      AND ms_played > 0                       -- zero-ms rows are logged starts with no playback
),
deduped AS (
    SELECT * FROM typed
    QUALIFY row_number() OVER (PARTITION BY end_ts, track_uri, ms_played) = 1
),
timed AS (
    SELECT *, end_ts - to_milliseconds(ms_played) AS start_ts
    FROM deduped
)
SELECT
    row_number() OVER (ORDER BY end_ts, track_uri)           AS stream_id,
    end_ts,
    start_ts,
    timezone('{{TZ}}', start_ts)                             AS start_local,
    CAST(timezone('{{TZ}}', start_ts) AS DATE)               AS local_date,
    hour(timezone('{{TZ}}', start_ts))                       AS hour_local,
    isodow(timezone('{{TZ}}', start_ts))                     AS dow,           -- 1 = Mon ... 7 = Sun
    isodow(timezone('{{TZ}}', start_ts)) >= 6                AS is_weekend,
    ms_played,
    track_uri,
    track_name,
    artist,
    album,
    reason_start,
    reason_end,
    shuffle,
    skipped_flag,
    offline,
    incognito,
    CASE
        WHEN platform_raw LIKE '%android%'                                   THEN 'android'
        WHEN platform_raw LIKE '%ios%' OR platform_raw LIKE '%iphone%'
          OR platform_raw LIKE '%ipad%'                                      THEN 'ios'
        WHEN platform_raw LIKE '%windows%' AND platform_raw LIKE '%web_player%' THEN 'web'
        WHEN platform_raw LIKE '%web_player%' OR platform_raw LIKE '%webplayer%' THEN 'web'
        WHEN platform_raw LIKE '%windows%'                                   THEN 'windows'
        WHEN platform_raw LIKE '%os x%' OR platform_raw LIKE '%macos%'
          OR platform_raw LIKE '%osx%'                                       THEN 'mac'
        WHEN platform_raw LIKE '%linux%'                                     THEN 'linux'
        ELSE 'other'
    END                                                      AS platform_family
FROM timed;
