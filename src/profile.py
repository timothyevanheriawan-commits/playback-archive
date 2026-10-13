"""Phase 1: profile the raw data BEFORE trusting any metric.

Usage:
    python -m src.profile

Prints a report and saves it to reports/data_profile.txt (gitignored).
"""
import pandas as pd

from src.config import REPORT_DIR
from src.db import connect


def section(title: str) -> str:
    return f"\n=== {title} ===\n"


def run() -> None:
    con = connect(read_only=True)
    q = lambda sql: con.execute(sql).df()  # noqa: E731
    out = []

    out.append(section("Volume and range"))
    out.append(q("""
        SELECT count(*) AS raw_rows,
               count(*) FILTER (WHERE spotify_track_uri IS NULL) AS non_music_rows,
               min(CAST(ts AS TIMESTAMPTZ)) AS first_ts,
               max(CAST(ts AS TIMESTAMPTZ)) AS last_ts
        FROM raw_audio""").to_string(index=False))

    out.append(section("Cleaning: what staging removed"))
    out.append(q("""
        SELECT (SELECT count(*) FROM raw_audio) AS raw_rows,
               (SELECT count(*) FROM raw_audio WHERE spotify_track_uri IS NULL) AS podcasts_or_audiobooks,
               (SELECT count(*) FROM raw_audio WHERE spotify_track_uri IS NOT NULL AND ms_played = 0) AS zero_ms_removed,
               (SELECT count(*) FROM stg_streams) AS clean_music_streams""").to_string(index=False))

    out.append(section("Null rates in key columns (music rows)"))
    out.append(q("""
        SELECT round(100.0 * avg(CAST(reason_start IS NULL AS INT)), 2) AS pct_null_reason_start,
               round(100.0 * avg(CAST(reason_end IS NULL AS INT)), 2)   AS pct_null_reason_end,
               round(100.0 * avg(CAST(shuffle IS NULL AS INT)), 2)      AS pct_null_shuffle,
               round(100.0 * avg(CAST(skipped IS NULL AS INT)), 2)      AS pct_null_skipped_flag,
               round(100.0 * avg(CASE WHEN skipped THEN 1 ELSE 0 END), 2) AS pct_skipped_true
        FROM raw_audio WHERE spotify_track_uri IS NOT NULL""").to_string(index=False))

    out.append(section("ms_played distribution (clean streams)"))
    out.append(q("""
        SELECT round(100.0 * avg(CAST(ms_played < 5000 AS INT)), 1)                       AS pct_under_5s,
               round(100.0 * avg(CAST(ms_played < {s} AS INT)), 1)                        AS pct_under_threshold,
               round(100.0 * avg(CAST(ms_played >= {s} AS INT)), 1)                       AS pct_qualified,
               round(median(ms_played) / 1000.0, 1)                                       AS median_sec
        FROM stg_streams""".format(s=30000)).to_string(index=False))

    out.append(section("reason_end"))
    out.append(q("""SELECT reason_end, count(*) AS streams,
                           round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
                    FROM stg_streams GROUP BY 1 ORDER BY 2 DESC""").to_string(index=False))

    out.append(section("reason_start"))
    out.append(q("""SELECT reason_start, count(*) AS streams,
                           round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
                    FROM stg_streams GROUP BY 1 ORDER BY 2 DESC""").to_string(index=False))

    out.append(section("Skip signals by year (did logging change over time?)"))
    out.append(q("""SELECT year, streams,
                           round(flag_rate, 3) AS flag_rate, round(fwd_rate, 3) AS fwd_rate,
                           round(endplay_rate, 3) AS endplay_rate,
                           round(primary_skip_rate, 3) AS skip_rate, round(bounce_rate, 3) AS bounce_rate
                    FROM m_skip_by_year ORDER BY year""").to_string(index=False))

    out.append(section("Platform families"))
    out.append(q("""SELECT platform_family, count(*) AS streams,
                           round(100.0 * count(*) / sum(count(*)) OVER (), 1) AS pct
                    FROM stg_streams GROUP BY 1 ORDER BY 2 DESC""").to_string(index=False))

    out.append(section("Streams per year"))
    out.append(q("""SELECT year(local_date) AS year, count(*) AS streams,
                           round(sum(ms_played) / 3600000.0, 1) AS hours
                    FROM stg_streams GROUP BY 1 ORDER BY 1""").to_string(index=False))

    out.append(section("Longest silent gaps between streams (days)"))
    out.append(q("""
        WITH d AS (SELECT DISTINCT local_date AS d FROM stg_streams),
        g AS (SELECT d, LAG(d) OVER (ORDER BY d) AS prev FROM d)
        SELECT prev AS last_day_before_gap, d AS first_day_after_gap,
               date_diff('day', prev, d) - 1 AS silent_days
        FROM g WHERE prev IS NOT NULL ORDER BY silent_days DESC LIMIT 8""").to_string(index=False))

    out.append(section("Flags worth knowing about"))
    out.append(q("""SELECT count(*) FILTER (WHERE offline) AS offline_streams,
                           count(*) FILTER (WHERE incognito) AS incognito_streams,
                           (SELECT count(*) FROM raw_audio WHERE spotify_track_uri IS NOT NULL AND ms_played = 0) AS zero_ms_removed
                    FROM stg_streams""").to_string(index=False))
    con.close()

    report = "\n".join(out)
    REPORT_DIR.mkdir(exist_ok=True)
    (REPORT_DIR / "data_profile.txt").write_text(report, encoding="utf-8")
    print(report)


if __name__ == "__main__":
    pd.set_option("display.width", 140)
    run()
