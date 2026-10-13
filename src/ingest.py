"""Step 1: load the raw Spotify JSON into DuckDB (privacy by whitelist).

Usage:
    python -m src.ingest                  # reads data/raw
    python -m src.ingest --raw some/dir
"""
import argparse
import sys
from pathlib import Path

from src.config import KEEP_COLUMNS, RAW_DIR, RAW_PATTERNS
from src.db import connect


def find_files(raw_dir: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in RAW_PATTERNS:
        files.extend(raw_dir.glob(pattern))
    return sorted(set(files))


def ingest(raw_dir: Path) -> None:
    files = find_files(raw_dir)
    if not files:
        sys.exit(
            f"No audio history files found in {raw_dir}.\n"
            f"Expected names like {RAW_PATTERNS}. Put your export JSON files there."
        )

    file_list = "[" + ", ".join("'" + f.as_posix().replace("'", "''") + "'" for f in files) + "]"
    reader = f"read_json_auto({file_list}, union_by_name = true)"

    con = connect()
    con.execute("SET TimeZone = 'UTC'")

    found = {row[0] for row in con.execute(f"DESCRIBE SELECT * FROM {reader}").fetchall()}
    select = ", ".join(c if c in found else f"NULL AS {c}" for c in KEEP_COLUMNS)
    dropped = sorted(found - set(KEEP_COLUMNS))

    con.execute(f"CREATE OR REPLACE TABLE raw_audio AS SELECT {select} FROM {reader}")
    n = con.execute("SELECT count(*) FROM raw_audio").fetchone()[0]
    con.close()

    print(f"Read {len(files)} file(s), {n:,} rows into raw_audio.")
    print(f"Columns kept   : {len(KEEP_COLUMNS)}")
    print(f"Columns dropped: {', '.join(dropped) if dropped else '(none)'}")
    sensitive = [c for c in dropped if c.startswith("ip_") or "user_agent" in c or c == "username"]
    if sensitive:
        print(f"  (privacy) never stored: {', '.join(sensitive)}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw", type=Path, default=RAW_DIR, help="folder with the JSON files")
    args = parser.parse_args()
    ingest(args.raw)
