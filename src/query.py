"""Run any SQL against the project database. Handy for learning DuckDB.

Examples:
    python -m src.query "SHOW TABLES"
    python -m src.query "SELECT artist, count(*) AS plays FROM stg_streams GROUP BY 1 ORDER BY 2 DESC LIMIT 10"
"""
import sys

import pandas as pd

from src.db import connect

if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pd.set_option("display.width", 160)
    pd.set_option("display.max_columns", 30)
    con = connect(read_only=True)
    print(con.execute(sys.argv[1]).df().to_string(index=False))
    con.close()
