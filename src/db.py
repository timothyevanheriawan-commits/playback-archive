"""Small DuckDB helpers shared by every step."""
import re

import duckdb

from src.config import DB_PATH, PARAMS


def connect(read_only: bool = False) -> duckdb.DuckDBPyConnection:
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return duckdb.connect(str(DB_PATH), read_only=read_only)


def render_sql(text: str) -> str:
    """Replace {{TOKEN}} placeholders with values from config.PARAMS."""
    for key, value in PARAMS.items():
        text = text.replace("{{" + key + "}}", str(value))
    leftover = re.findall(r"\{\{[A-Z_]+\}\}", text)
    if leftover:
        raise ValueError(f"Unreplaced SQL tokens: {sorted(set(leftover))}")
    return text


def run_sql_file(con: duckdb.DuckDBPyConnection, path) -> None:
    con.execute(render_sql(path.read_text(encoding="utf-8")))
