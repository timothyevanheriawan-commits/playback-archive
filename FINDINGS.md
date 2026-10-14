# Findings

**Data:** 485,529 music streams, about 7,700 hours, 2016-03-31 to 2026-10-10 (Spotify extended streaming history, audio only). Cleaned from 506,250 raw rows by dropping 49 podcast/audiobook rows and 20,643 zero-millisecond rows. 2026 is a partial year.

## Finding 1: Spotify's skip labels cannot be compared across years

- **Question:** Has my skipping changed over ten years?
- **Metric:** skip = played under 30 s and ended by me (`fwdbtn`, `endplay` or `backbtn`). Chosen because duration is the only signal that means the same thing in every year.
- **Result:** Spotify's own `skipped` flag is 0.000 in every year from 2016 to 2021, 0.161 in 2022, then 0.64 to 0.81 from 2023. The `fwdbtn` rate moves from 0.2% (2018) to 34.7% (2022) to 19.1% (2023). Meanwhile the share of streams under 5 s stays between 46% and 59% in every year. Behavior is stable, labeling is not. On the duration rule, skip rate runs from 82.9% (2016) to 56.5% (2026) with no label discontinuity, and is 68.6% overall.
- **Does not show:** why logging changed. That the flag from 2023 onward tracks "did not finish the track" is an inference from two columns, not documented by Spotify.

## Finding 2: what predicts a skip

- **Question:** Which factor group matters most for whether a stream is skipped?
- **Metric:** out-of-time AUC. Logistic model fit on the first 80% of streams, scored on the last 20% (n = 450,266, base rate 68.6%). An ablation removes one factor group at a time and reports the AUC drop. Full model AUC is 0.857.
- **Result:**

| Factor group   | Odds ratios (95% CI)                                                                              | AUC drop when removed |
| -------------- | ------------------------------------------------------------------------------------------------- | --------------------- |
| how it started | click vs autoplay 12.8 (12.5 to 13.1); forward button 16.2 (15.8 to 16.6)                         | 0.192                 |
| familiarity    | per log of earlier plays 0.74 (0.74 to 0.75); first listen 1.08 (1.04 to 1.12)                    | 0.022                 |
| platform       | android 0.73 (0.72 to 0.74), ios 0.86 (0.84 to 0.88), vs windows                                  | 0.003                 |
| time of day    | night 1.20 (1.17 to 1.24), morning 0.80 (0.79 to 0.82), afternoon 0.92 (0.90 to 0.93), vs evening | 0.002                 |
| shuffle        | 1.24 (1.22 to 1.26)                                                                               | 0.0001                |
| weekend        | 1.10 (1.08 to 1.11)                                                                               | -0.0002               |

  How a stream started dominates everything else by roughly an order of magnitude. A track I had already played 10 times has about half the skip odds of a first listen, other things equal. With 450k streams every odds ratio is statistically distinguishable from 1, including weekend and shuffle, but removing either costs almost no out-of-time AUC. Here the ablation is a better guide to importance than the p-values.

- **Does not show:** causation. `reason_start` for a stream is set by how the previous stream ended, so "how it started" partly encodes whether I was already in a skip streak, and separates tracks I clicked on (browsing) from tracks that autoplayed (listening). It describes listening mode more than it explains a skip. The model pools all years, so the odds ratios are averages over logging eras. Platform and shuffle are confounded with activity and context.

## Finding 3: I listen deeper than I used to

- **Metric:** mean minutes played per stream, by year (hours divided by streams).
- **Result:** 0.38 min in 2016, 0.82 in 2019, 1.26 in 2021, 1.07 in 2025, 1.35 in 2026. Stream counts in 2021 (61,910) and 2026 to date (60,602) are almost the same, but hours are 1,299 and 1,365. Roughly 3.5 times the time per play compared with 2016. This agrees with the duration-based skip rate falling over the same period.
- **Caveat:** a mean over a very skewed distribution, so a few long plays move it. 2026 ends 2026-10-10 and is already the highest-hours year on record.

## Finding 4: binged tracks fade fast, at any size

- **Question:** How long does a binged track stay hot?
- **Metric:** weeks from a track's peak week until its plays stay at or below half the peak for 4 weeks in a row, estimated with Kaplan-Meier because some tracks never fade. A binge is a track with at least 5 plays in its busiest week (1,293 tracks; 1,280 enter the curve, and the 13 dropped had their peak in the last few weeks of data).
- **Result:** 99.6% of tracks decay, the median is 2 weeks (1 week on the naive rule), and only 0.9% are still alive at 12 weeks. A track picked for its busiest week tends to fall back by chance, most easily when the peak is small, so I split the curve by peak size:

| Peak plays | Tracks | Median weeks to decay | Alive at 12 weeks |
| ---------- | ------ | --------------------- | ----------------- |
| 5 to 6     | 586    | 1                     | 0.5%              |
| 7 to 9     | 400    | 2                     | 1.8%              |
| 10 to 19   | 280    | 1                     | 0.7%              |
| 20+        | 14     | 1                     | 0.0%              |

  There is no trend with peak size, so the short half-life is not just a small-peak artifact. The 20+ group has only 14 tracks and says little.

- **Does not show:** that I stopped playing the track, only that it fell to half its peak. Because almost every track decays within a few weeks, this metric cannot rank tracks, and a fast fade probably also reflects how discovery bursts work (not checked).

## Finding 5: life events mostly look like noise

- **Metric:** change in five daily metrics, 28 days after vs 28 days before each event, compared with the same change on every ordinary day. `share_of_ordinary_days_as_extreme` is the fraction of ordinary days that changed at least as much, so small means the event stands out.
- **Result:** 11 events, 50 comparisons. Two fall below 0.05: starting university (2022-07-19), new artists per day up 260% (0.023), and COVID (2020-03-20), new artists per day up 184% (0.045). With 50 comparisons, about 2.5 below 0.05 are expected by chance alone, so two is what noise looks like. One lead worth following: three of the seven most unusual comparisons are new artists per day (university, COVID, and the first internship at +114%, 0.11), which would fit discovery jumping at life transitions. The first internship (2025-02-01) also shows listening minutes up 78% (0.06). The other 38 comparisons all sit within normal drift (at least 19% of ordinary days changed as much).
- **Does not show:** that any event caused anything. Days are autocorrelated and many metrics were tested. Starting middle school (2016-07-13) shows listening minutes down 72% (0.072), but it sits 104 days into the data, just past the 90-day burn-in, so I treat it as unreliable.

## The one that surprised me

The median stream lasts 4.5 seconds. 51.7% of streams end before 5 s and 68.4% end before 30 s; only 31.6% count as a qualified play. I expected it to last 10 seconds.

It is not a logging artifact: zero-millisecond rows were already removed, and the under-5-second share sits between 46% and 59% in every year, including the years where the labels broke. It also shows up in sessions: with a 30 minute gap rule, a typical session is 17 tracks in 29 minutes, under two minutes a track. Session length itself does not survive the gap choice (median 12 minutes at a 10 minute gap, 55 at a 60 minute gap, with sessions falling from 24,895 to 10,732), so I only report it as a range, and wall-clock time includes pauses.

## Where my first metric was wrong

My first skip rule was "played under 30 s and ended with the forward button", chosen before I looked at the data. On the 450,266 eligible streams it flags 16.5%, Spotify's own flag flags 31.8%, and plain "under 30 s" flags 69.7%. These cannot all be right. The flag is not set on 60% of the streams my final rule counts as skips (184,719 of 309,091), mostly because it is never set before 2022. I switched to a duration rule that is comparable across all years (68.6%) and kept the old rule in `m_skip_definitions` and `m_skip_by_year` so the change is auditable. See METHODS.md decisions 4 and 5.

## What I would do next

Separate listening from browsing: analyze skip rate only within streams that started by autoplay, where a skip is a cleaner signal than for streams I clicked on. Then test the new-artist spikes at life events against a permutation baseline built for that one metric.
