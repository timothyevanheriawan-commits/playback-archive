# Methods

## Data

Spotify extended streaming history, audio files only. One row is one stream. Podcasts and
audiobooks (rows without a track URI) are dropped. Rows with `ms_played = 0` are dropped
(logged starts with no playback; counted in the profile as `zero_ms_removed`). Exact
duplicates on (end time, track, ms played) are dropped.

**Timestamps.** `ts` in the export is when the stream **ended**, not when it started.
Start time is `ts - ms_played`. All hour-of-day and weekday logic uses the start time in
the configured local time zone (`Asia/Jakarta`).

**Privacy.** Only whitelisted columns are loaded (see `src/config.py`). IP address, user
agent and username are never stored in the database.

## Definitions

| Term | Definition | Why |
|---|---|---|
| Qualified play | `ms_played >= 30 s` | matches Spotify's own "counts as a play" rule of thumb |
| Skip (primary) | `ms_played < 30 s` AND `reason_end` in (`fwdbtn`, `endplay`, `backbtn`) | duration is the only signal comparable across all years; see decision 4 |
| Bounce | the same, but under 5 s | sampled and dropped almost instantly |
| Skip (flag) | Spotify's `skipped = true` | comparison only; not usable before 2023 |
| Skip (old rule) | `ms_played < 30 s` AND `reason_end = 'fwdbtn'` | kept in the definitions table for comparison |
| Interlude | a track completed naturally (`trackdone`) in under 60 s | removed from skip analysis; skipped intros stay in |
| Familiarity | number of earlier streams of the same track | track age in the library is not in the export |
| Session | run of streams where each gap (previous end to next start) is at most 30 min | swept over 10, 20, 30, 45, 60 min |
| Discovery | first qualified play of an artist (or track) in the data | a 3 second play is not discovering anything |
| Binge | a track whose busiest week has at least 5 qualified plays | |
| Decay (naive) | first week after the peak at or below half the peak | shown for comparison |
| Decay (sustained) | first week after the peak from which the next 4 weeks all stay at or below half the peak | one quiet week is not decay |
| Event effect | change in a daily metric, 28 days after vs 28 days before an event | |

Recap definitions (all thresholds in `src/config.py`):

| Term | Definition |
|---|---|
| Comfort song | finished naturally 10+ times and never skipped |
| Love-hate track | 15+ qualified plays and a skip rate at or above your overall rate |
| Reunion | an artist with a gap of 365+ days between listening days, with 10+ plays before the gap and 10+ after |
| One-week wonder | 5+ qualified plays all within 14 days, then untouched for 365+ days before the data ends |
| Taste age | median days between a track's first play and each play in that month |
| Variety | top-artist share of the month, and effective artist count (exp of the entropy of artist shares) |
| Night | start hour 00:00 to 05:59 local time |

All thresholds live in `src/config.py` and are injected into the SQL as `{{TOKENS}}`.

## Models

**Q1 Skips.** Rate tables with Wilson 95% intervals (`m_skip_rates`), then a logistic
regression (`src/skip_model.py`) so overlapping factors are separated. The model is judged
out of time: fit on the first 80% of streams, scored by AUC on the last 20%. An ablation
removes one factor group at a time and reports how much the out-of-time AUC drops, which
answers "what matters most" better than coefficient size.

**Q2 Discovery.** Monthly new artists, new tracks and replay share, using qualified plays.
The first three months are flagged as ramp-up because everything looks new at the start.

**Q3 Sessions.** `LAG` finds the gap to the previous stream, a flag marks session starts,
and a running `SUM` turns flags into session ids. Done for several gap sizes at once.

**Q4 Decay.** Plays are bucketed into weeks since a track's first qualified play. Tracks
that have not decayed by the end of the data are right-censored, so the headline number is
a Kaplan-Meier curve (`m_decay_km`), not a plain median of the tracks that did decay (which
would be biased toward fast-decaying tracks).

**Q5 Overlay.** For each event in `data/events.csv`, compare the 28 days before and after
for five daily metrics. To judge size, the same before/after comparison is computed for
every ordinary day in the timeline. `share_of_ordinary_days_as_extreme` is the fraction of
those days whose change was at least as large. Small means the event stands out; large
means it is within normal drift. The first 90 days are excluded as burn-in.

## Design decisions that were revised

1. **Skip eligibility filter (bias found in testing).** The first version removed tracks
   whose typical play was shorter than 60 seconds, to drop interludes. That also removed
   every track that was only ever skipped, because skipped plays are short. It made first
   listens look like they were skipped 10% of the time instead of about 68% in the test
   data. The filter now looks only at naturally completed plays, never at skips.
2. **Discovery counted on raw plays.** Counting any play as discovery inflates it with
   accidental clicks. Qualified plays are the primary metric; the raw count is kept in
   `m_discovery_monthly.new_artists_raw`.
3. **Decay half-life.** The naive "first week below half" fires on a single quiet week.
   The sustained version needs 4 quiet weeks, and survival analysis handles tracks that
   never faded.

4. **The skip rule, revised on real data.** The first rule was `fwdbtn` and under 30 s,
   designed before seeing the export. On the real export (about 506k raw rows, 2016 to
   2026) the profile showed that Spotify's `skipped` flag is 0.000 for 2016 to 2021, 0.160
   in 2022, and 0.63 to 0.79 from 2023. In 2023 and 2024 it is roughly equal to the
   `fwdbtn` rate plus the `endplay` rate, so it looks like "did not finish the track"
   rather than "skipped" (an inference from two columns, not documented by Spotify).
   The `fwdbtn` rate itself moves from about 2% (2016 to 2018) to 37% (2021) to 19% (2023),
   while the share of streams under 5 s stays between 45% and 60% every year. Stable
   behaviour with unstable labels suggests the logging changed, so labels are not
   comparable across years. The primary rule now uses duration plus "ended by the user".
   The old rule is kept in `m_skip_definitions` and `m_skip_by_year` so the change is auditable.
5. **Zero-millisecond rows removed.** About 20k rows (4%) had `ms_played = 0`. They are
   logged starts, not plays, and distort discovery and session counts.

Add your own revisions here as you find them. Reviewers like seeing them.

## Known limitations

- **No track length in the export.** Interludes are inferred from completed short plays,
  so a short track you always skip is not detected as an interlude.
- **Left side of the data.** Familiarity and discovery start counting at the first stream
  in the export. If you used Spotify before the export starts, early "first listens" are
  not truly first.
- **Offline and incognito.** Offline plays are synced later and may be missing or odd.
  Incognito (private session) plays are not in the history at all.
- **Shared accounts and other people's plays** look like your behavior.
- **Fixed time zone.** Travel is not handled. `conn_country` could be used to adjust.
- **Event overlay is descriptive.** Days are autocorrelated and many metrics are compared,
  so treat small `share_of_ordinary_days_as_extreme` values as leads, not proof.
- **Logging changed over the years.** Spotify's `reason_end` and `skipped` fields do not
  mean the same thing in every year (decision 4). Only duration-based measures are compared
  across years. The skip model pools all years, in which device mix and logging also changed,
  so read its odds ratios as averages over eras, not as one stable behaviour.
- **`endplay` short plays are treated as user rejections.** Most short plays end with
  `endplay` (you picked another track), but some may be you stopping playback. This is
  not separable in the export.
- **Recap tables are descriptive.** Wrapped-style labels (night-owl month, one-artist month)
  are percentile or z-score based and exist to be fun, not to prove anything.
- **Correlation only.** The skip model describes what goes with skipping, not what causes it.
  Shuffle and platform are confounded with mood, activity and what you were doing.

## Validation

`src/make_sample.py` generates fake data with known effects (shuffle, night, platform,
familiarity, a null weekend effect, a discovery dip, a listening spike). On that data the
pipeline recovers the planted odds ratios within sampling error and reports the weekend
effect as null. If you change a model, rerun on the sample and check this still holds.
