"""Step 5: export PUBLIC aggregates only, with privacy guards.

Writes CSV and Parquet files to data/public. These are the only data files the
dashboard (and a public repo) should ever see. Stream-level tables are never exported.

Usage:
    python -m src.export
    python -m src.export --redact-tracks     # hash track and artist names in every table
"""
import argparse
import json
import re

from src.config import PUBLIC_DIR
from src.db import connect

EXPORTS = {
    "kpis": "m_kpis",
    "range": "m_range",
    "skip_rates": "m_skip_rates",
    "skip_definitions": "m_skip_definitions",
    "skip_by_year": "m_skip_by_year",
    "skip_model": "m_skip_model",
    "skip_ablation": "m_skip_ablation",
    "skip_model_meta": "m_skip_model_meta",
    "discovery_monthly": "m_discovery_monthly",
    "session_by_hour": "m_session_by_hour",
    "session_by_dow": "m_session_by_dow",
    "session_heat": "m_session_heat",
    "session_gap_sensitivity": "m_session_gap_sensitivity",
    "decay_summary": "m_decay_summary",
    "decay_km": "m_decay_km",
    "decay_tracks": "m_decay_tracks",
    "event_effects": "m_event_effects",
    "daily": "m_daily",
    # recap (Wrapped-style). These contain track and artist names.
    "recap_monthly": "m_recap_monthly",
    "recap_night_owl": "m_recap_night_owl",
    "recap_slow_burns": "m_recap_slow_burns",
    "recap_burnout": "m_recap_burnout",
    "recap_comfort": "m_recap_comfort",
    "recap_love_hate": "m_recap_love_hate",
    "recap_reunions": "m_recap_reunions",
    "recap_records": "m_recap_records",
    "recap_devices": "m_recap_devices",
    "recap_weekend": "m_recap_weekend",
    "recap_shuffle": "m_recap_shuffle",
    "recap_daypart": "m_recap_daypart",
    "recap_anthems": "m_recap_anthems",
    "recap_one_week_wonders": "m_recap_one_week_wonders",
    "recap_facts": "m_recap_facts",
}

# Columns that hold names, and the prefix used when --redact-tracks hashes them.
# The same artist always gets the same hash, across every table.
NAME_COLUMNS = {"track_name": "track_", "artist": "artist_", "top_artist": "artist_"}

BANNED_COLUMNS = {
    "ip_addr", "ip_addr_decrypted", "user_agent_decrypted", "username",
    "stream_id", "conn_country", "spotify_track_uri", "track_uri",
}
MAX_ROWS = 5000
IPV4 = re.compile(r"(?<![\d.])(?:\d{1,3}\.){3}\d{1,3}(?![\d.])")


def export(redact_tracks: bool) -> None:
    PUBLIC_DIR.mkdir(parents=True, exist_ok=True)
    for old in PUBLIC_DIR.glob("*"):
        if old.suffix in {".csv", ".parquet", ".json"}:
            old.unlink()

    con = connect(read_only=True)
    existing = {r[0] for r in con.execute("SHOW TABLES").fetchall()}
    manifest = {}

    for name, table in EXPORTS.items():
        if table not in existing:
            print(f"  skip {name:<26} (table {table} not built)")
            continue

        raw_cols = [r[0] for r in con.execute(f"DESCRIBE {table}").fetchall()]
        rows = con.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
        if rows > MAX_ROWS:
            raise SystemExit(f"Refusing to export {table}: {rows:,} rows looks like stream-level data")

        select = "*"
        if redact_tracks:
            reps = [
                f"'{prefix}' || substr(md5({col}), 1, 6) AS {col}"
                for col, prefix in NAME_COLUMNS.items() if col in raw_cols
            ]
            if reps:
                select = f"* REPLACE ({', '.join(reps)})"
        query = f"SELECT {select} FROM {table}"
        if "track_uri" in raw_cols:
            query = f"SELECT * EXCLUDE (track_uri) FROM ({query})"

        # banned-column check runs on what is actually written, not on the source table
        out_cols = [r[0] for r in con.execute(f"DESCRIBE {query}").fetchall()]
        bad = BANNED_COLUMNS.intersection(out_cols)
        if bad:
            raise SystemExit(f"Refusing to export {table}: banned columns {sorted(bad)}")

        csv_path = (PUBLIC_DIR / f"{name}.csv").as_posix()
        pq_path = (PUBLIC_DIR / f"{name}.parquet").as_posix()
        con.execute(f"COPY ({query}) TO '{csv_path}' (HEADER, DELIMITER ',')")
        con.execute(f"COPY ({query}) TO '{pq_path}' (FORMAT PARQUET)")
        manifest[name] = {"rows": rows, "columns": out_cols}
        print(f"  wrote {name:<26} {rows:>6,} rows")
    con.close()

    # Last line of defence: scan every exported CSV for anything that looks like an IP.
    for path in PUBLIC_DIR.glob("*.csv"):
        text = path.read_text(encoding="utf-8")
        hit = IPV4.search(text)
        if hit:
            raise SystemExit(f"Possible IP address in {path.name}: {hit.group(0)}")

    (PUBLIC_DIR / "_manifest.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    note = "names hashed" if redact_tracks else "names NOT hashed (use --redact-tracks before publishing)"
    print(f"Exported {len(manifest)} tables to {PUBLIC_DIR}. IP scan passed. {note}.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--redact-tracks", action="store_true")
    args = parser.parse_args()
    export(args.redact_tracks)
