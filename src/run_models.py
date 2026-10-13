"""Step 2: run the SQL models in order (sql/00_*.sql ... sql/06_*.sql)."""
import re
import time

from src.config import SQL_DIR
from src.db import connect, render_sql


def run_models() -> None:
    con = connect()
    for path in sorted(SQL_DIR.glob("*.sql")):
        text = render_sql(path.read_text(encoding="utf-8"))
        started = time.time()
        con.execute(text)
        tables = re.findall(r"CREATE OR REPLACE TABLE (\w+)", text)
        sizes = ", ".join(
            f"{t}={con.execute(f'SELECT count(*) FROM {t}').fetchone()[0]:,}" for t in tables
        )
        print(f"{path.name:<22} {time.time() - started:5.1f}s  {sizes}")
    con.close()


if __name__ == "__main__":
    run_models()
