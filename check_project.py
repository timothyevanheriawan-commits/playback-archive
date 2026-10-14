"""Project health check. Run from the project root:  python check_project.py

Layers, from cheapest to most thorough:
  1. Lint        a missing comma inside a list glues two strings together (the
                 "devicesanthems" bug); invisible characters break HTML and SQL.
  2. Contract    every table the app asks for exists in data/public.
  3. Data        tables are not empty, columns are not all null, and the app's
                 headline numbers agree with the pipeline's own tables.
  4. Smoke test  actually run the Streamlit app headlessly and fail on any exception
                 or st.error, including every Explore section.

Exit code is 1 if anything FAILs. WARN means look at it, FAIL means it is broken.
"""
import io
import sys
import tokenize
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent
PUBLIC = ROOT / "data" / "public"
sys.path.insert(0, str(ROOT))

# Keep in sync with load_tables() in app.py.
REQUIRED = [f"recap_{n}" for n in (
    "monthly", "night_owl", "slow_burns", "burnout", "love_hate", "reunions",
    "records", "devices", "anthems", "daypart", "one_week_wonders", "facts",
)]

results = {"FAIL": 0, "WARN": 0, "OK": 0}


def report(level: str, msg: str) -> None:
    results[level] += 1
    print(f"  [{level}] {msg}")


# ----------------------------------------------------------------------------- 1 lint
FSTART = getattr(tokenize, "FSTRING_START", None)
FEND = getattr(tokenize, "FSTRING_END", None)
SKIP = {tokenize.NL, tokenize.COMMENT, tokenize.NEWLINE, tokenize.INDENT,
        tokenize.DEDENT, tokenize.ENCODING}
INVISIBLE = {"\u200b": "zero-width space", "\u200c": "zero-width non-joiner",
             "\u200d": "zero-width joiner", "\u2060": "word joiner", "\ufeff": "BOM"}


def python_files() -> list[Path]:
    skip = {".venv", "venv", "__pycache__", "db", ".git"}
    return [p for p in ROOT.rglob("*.py") if not skip & set(p.relative_to(ROOT).parts)]


def implicit_concat_in_lists(path: Path) -> list[int]:
    """Lines where two string literals sit next to each other inside [ ] or { }."""
    hits, stack, prev_was_string = [], [], False
    with open(path, "rb") as f:
        try:
            tokens = list(tokenize.tokenize(f.readline))
        except (tokenize.TokenError, SyntaxError):
            return hits
    for tok in tokens:
        if tok.type == tokenize.OP:
            if tok.string in ("(", "[", "{"):
                stack.append(tok.string)
            elif tok.string in (")", "]", "}") and stack:
                stack.pop()
        if tok.type in SKIP:
            continue
        starts = tok.type == tokenize.STRING or tok.type == FSTART
        if starts and prev_was_string and stack and stack[-1] in ("[", "{"):
            hits.append(tok.start[0])
        prev_was_string = tok.type == tokenize.STRING or tok.type == FEND
    return hits


def check_lint() -> None:
    print("\n1. Lint")
    bad = False
    for path in python_files():
        for line in implicit_concat_in_lists(path):
            report("FAIL", f"{path.relative_to(ROOT)}:{line} two strings with no comma inside a list")
            bad = True
    skip = {".venv", "venv", "__pycache__", "db", ".git", "raw"}
    for pattern in ("*.py", "*.sql", "*.md", "*.toml", "*.txt"):
        for path in ROOT.rglob(pattern):
            if skip & set(path.relative_to(ROOT).parts):
                continue
            text = path.read_text(encoding="utf-8", errors="ignore")
            for i, line in enumerate(text.splitlines(), 1):
                for ch, name in INVISIBLE.items():
                    if ch in line:
                        report("FAIL", f"{path.relative_to(ROOT)}:{i} contains {name}")
                        bad = True
    if not bad:
        report("OK", "no glued strings in lists, no invisible characters")


# ----------------------------------------------------------------------------- 2 and 3 data
def load(name: str) -> pd.DataFrame | None:
    for ext, reader in (("parquet", pd.read_parquet), ("csv", pd.read_csv)):
        path = PUBLIC / f"{name}.{ext}"
        if path.exists():
            return reader(path)
    return None


def pick(df: pd.DataFrame, names: tuple[str, ...]) -> str | None:
    lookup = {c.lower(): c for c in df.columns}
    return next((lookup[n] for n in names if n in lookup), None)


def check_contract() -> None:
    print("\n2. Contract: tables the app requires")
    missing = [n for n in REQUIRED if load(n) is None]
    for n in missing:
        report("FAIL", f"missing table {n} in data/public")
    if not missing:
        report("OK", f"all {len(REQUIRED)} required tables present")


def check_data() -> None:
    print("\n3. Data sanity")
    for path in sorted(PUBLIC.glob("*")):
        if path.suffix not in (".parquet", ".csv"):
            continue
        df = load(path.stem)
        if df is None:
            continue
        if df.empty:
            report("WARN", f"{path.stem} has 0 rows")
            continue
        empty_cols = [c for c in df.columns if df[c].isna().all()]
        if empty_cols:
            report("WARN", f"{path.stem} has all-null columns: {empty_cols}")

    # Cross-check: the app's yearly skip rate (weighted from recap_devices) should
    # match the pipeline's own skip_by_year within a small tolerance.
    dev, sby = load("recap_devices"), load("skip_by_year")
    if dev is None or sby is None:
        report("WARN", "cannot cross-check skip rate: recap_devices or skip_by_year missing")
        return
    ycol, rcol = pick(sby, ("year",)), pick(sby, ("primary_skip_rate", "skip_rate", "skip"))
    if not ycol or not rcol:
        report("WARN", f"cannot cross-check skip rate: skip_by_year columns are {list(sby.columns)}")
        return
    d = dev.copy()
    d["w"] = d["skip_rate"] * d["streams"]
    app = d.groupby("year").apply(lambda g: g["w"].sum() / g["streams"].sum(), include_groups=False)
    ref = sby.set_index(ycol)[rcol]
    diff = (app - ref).dropna().abs()
    worst = diff.max() if len(diff) else float("nan")
    if len(diff) and worst > 0.01:
        report("WARN", f"app skip rate differs from skip_by_year by up to {worst:.3f}; "
                       f"worst years: {diff.sort_values(ascending=False).head(3).round(3).to_dict()}")
    else:
        report("OK", f"app skip rate matches skip_by_year (max diff {worst:.4f})")


# ----------------------------------------------------------------------------- 4 smoke test
def smoke_test() -> None:
    print("\n4. Smoke test: run the app headlessly")
    try:
        from streamlit.testing.v1 import AppTest
    except Exception as exc:
        report("WARN", f"streamlit AppTest unavailable ({exc}); upgrade streamlit")
        return

    def problems(at) -> list[str]:
        out = [f"exception: {getattr(e, 'value', e)}" for e in at.exception]
        out += [f"st.error: {e.value}" for e in at.error]
        return out

    at = AppTest.from_file(str(ROOT / "app.py"), default_timeout=180).run()
    found = problems(at)
    for p in found:
        report("FAIL", f"main page: {p[:300]}")
    if not found:
        report("OK", "main page renders without errors")

    try:
        radio = at.radio(key="archive_explore_section")
        options = list(radio.options)
    except Exception:
        report("WARN", "Explore section not found in the app (is the Explore tab wired in?)")
        return
    for option in options:
        at.radio(key="archive_explore_section").set_value(option).run()
        found = problems(at)
        for p in found:
            report("FAIL", f"Explore / {option}: {p[:300]}")
        if not found:
            report("OK", f"Explore / {option} renders")


def main() -> None:
    check_lint()
    check_contract()
    check_data()
    smoke_test()
    print(f"\nSummary: {results['OK']} ok, {results['WARN']} warn, {results['FAIL']} fail")
    sys.exit(1 if results["FAIL"] else 0)


if __name__ == "__main__":
    main()
