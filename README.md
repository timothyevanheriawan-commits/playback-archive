# Playback Archive — Spotify archive

A Streamlit dashboard for exploring a personal Spotify extended streaming history.

## Run

From the project root (the directory containing `app.py`, `src/`, and `data/`):

```bash
pip install streamlit pandas altair pyarrow
python -m streamlit run app.py
```

Keep the existing `src/` and `data/public/` directories in place. The redesign expects the same summary tables as the original app; it does not replace the analysis pipeline.

## New Explore views

- **Listening eras** segments adjacent years at the strongest relative changes across skip rate, minutes per play, night-listening share, and busiest hour. These are descriptive change points, not inferred life events.
- **Before vs. after** compares two user-selected, non-overlapping year ranges. Daily rates use the daily summary table where its date/count fields can be identified.
- **Artist loyalty** computes year coverage (`active years / covered years × 100`) when a compatible artist-by-year play-count table exists. Otherwise it shows a clearly labeled fallback based on artists appearing in monthly top-track, yearly anthem, daypart-leading, and comeback summaries. The fallback is not a true artist play-count index.
- **Track lifecycle** combines the current monthly top-track, yearly anthem, burnout, high-skip, and one-week-wonder summary records. It does not imply that these summary appearances form a complete play-by-play history.
- **Listening fingerprint** summarizes measurable patterns including night-listening share, skip rate, and average minutes per play. It does not assign a personality type.

## Enabling the numeric artist loyalty index

Add `data/public/recap_artist_yearly.parquet` (CSV also accepted) with at least these columns:

| Column               | Meaning                                          |
| -------------------- | ------------------------------------------------ |
| `artist`             | Artist name                                      |
| `year`               | Calendar year                                    |
| `streams` or `plays` | Recorded play count for that artist in that year |

Rows should represent recorded artist-year listening counts, not only the artist that led a month or year. The index is the number of covered years in which the artist has a positive play count divided by the number of years in the annual archive. It measures persistence, not preference.

## Caveats

- The latest year may be incomplete; annual totals and period comparisons must be read with that in mind.
- Existing definitions of qualified plays and skips remain unchanged.
- Long listening sessions may include idle or paused playback. The current analytical method notes remain relevant.
