# Listening Ledger

Ten years of my own Spotify listening (485,529 streams, about 7,700 hours, March 2016 to October 2026), cleaned and modeled in SQL and Python, and explored in a Streamlit dashboard.

**Live app:** _add your Streamlit link here after deploying_

![Dashboard screenshot](docs/screenshot.png)

## What it found

- **Spotify's own skip labels cannot be compared across years.** The `skipped` flag is never set from 2016 to 2021 and is set on about 80% of streams from 2023, while the share of streams under 5 seconds stays between 46% and 59% every year. Behavior is stable, logging is not, so skips are defined by duration instead.
- **How a stream starts predicts a skip far better than anything else.** An out-of-time logistic model reaches AUC 0.857, and removing the start reason alone costs 0.19 AUC. Familiarity costs 0.02, platform and time of day about 0.002, shuffle and weekend nothing.
- **I listen deeper than I used to.** Mean time per stream rose from 0.4 minutes in 2016 to 1.35 in 2026, with about the same number of plays per year as 2021.

Full write-up with caveats: [FINDINGS.md](FINDINGS.md). Every definition and the decisions I revised after seeing the real data: [METHODS.md](METHODS.md).

## Dashboard views

- **Listening eras** splits the timeline where skip rate, minutes per play, night share and busiest hour change most. Descriptive change points, not inferred life events.
- **Before vs. after** compares two non-overlapping year ranges.
- **Artist loyalty** measures how many years an artist stays in rotation. It measures persistence, not preference.
- **Track lifecycle** follows tracks through monthly top, yearly anthem, burnout, high-skip and one-week-wonder tables.
- **Listening fingerprint** summarizes night share, skip rate and minutes per play.

## How it works

```
data/raw/*.json  ->  DuckDB staging  ->  SQL models  ->  Python analysis  ->  data/public/*  ->  Streamlit app
 (not committed)     sql/00_staging      sql/01 to 07     src/analysis.py      33 aggregate       app.py
                                                          src/skip_model.py    tables
```

- **Ingest and cleaning:** audio streams only, zero-millisecond rows and exact duplicates removed, timestamps converted from end time to start time in `Asia/Jakarta`.
- **Models:** skip rates with Wilson intervals, a logistic model scored out of time with a factor ablation, a session model swept over five gap sizes, Kaplan-Meier survival for taste decay, and a before/after overlay for life events judged against ordinary days.
- **Validation:** `src/make_sample.py` generates fake data with known effects, and the pipeline recovers them, including a planted null.

## Run it

Dashboard only, using the committed tables in `data/public`:

```
pip install -r requirements.txt
python -m streamlit run app.py
```

Full pipeline on your own data: request your Extended Streaming History from Spotify (Account, Privacy), put the JSON files in `data/raw/`, then:

```
pip install -r requirements-pipeline.txt
python -m src.run_all
```

No Spotify data? `python -m src.make_sample` creates a fake history to run the pipeline on.

## Data and privacy

- Raw exports are never committed. The ingest keeps a whitelist of columns, so IP address, user agent and username never reach the database, and the export step scans for IP patterns before writing.
- `data/public` holds aggregates only. Track and artist names are included on purpose. To hash them, run the export with `--redact-tracks`.

## Caveats

- 2026 is a partial year (data ends 2026-10-10).
- No track length in the export, so interludes are inferred.
- Everything here is descriptive. The skip model shows what goes with skipping, not what causes it.
- More in [METHODS.md](METHODS.md#known-limitations).

## Stack

Python, DuckDB, pandas, Altair, Streamlit.
