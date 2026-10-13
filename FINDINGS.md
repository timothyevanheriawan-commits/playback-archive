# Findings

> Template. Run the pipeline on your real data, then replace every TODO. Keep it to 3 to 5
> findings. A reviewer reads this page, not your charts. Each finding states the metric,
> why that metric, the result with its uncertainty, and what it does not show.

**Data:** TODO streams, TODO hours, TODO first date to TODO last date.

## Finding 1: what predicts a skip

- **Question:** TODO
- **Metric:** skip = played under 30 s and ended by the user (forward, backward or
  `endplay`). Chosen because Spotify's own flag and the forward-button label are not
  comparable across years (see below and `skip_by_year`).
- **Result:** TODO. Use the ablation table: which factor group costs the most out-of-time
  AUC when removed? Quote odds ratios with their intervals.
- **Does not show:** causation. TODO example of a confounder.

## Finding 2: discovery and busy periods

- **Metric:** share of a month's distinct artists that were heard for the first time (qualified plays).
- **Result:** TODO. Compare thesis or exam months with the rest. State the sample size per month.
- **Caveat:** TODO (ramp-up months excluded; last month may be partial).

## Finding 3: how I listen in sessions

- **Metric:** median session length (wall clock minutes) with a 30 minute gap rule.
- **Result:** TODO by hour and weekday. Include the gap sensitivity: does the conclusion
  survive 10 and 60 minute gaps?
- **Caveat:** TODO

## Finding 4: how fast taste decays

- **Metric:** weeks from a track's peak week until its plays stay at or below half the peak
  for 4 weeks in a row, estimated with Kaplan-Meier because some tracks never fade.
- **Result:** TODO median, plus the share still alive at 12 weeks.
- **Caveat:** TODO

## Finding 5: what life events show up

- **Metric:** change in daily listening minutes, sessions, discovery and skip rate, 28 days
  after vs before each event, compared with ordinary days.
- **Result:** TODO which events stand out and which do not. Say plainly what showed nothing.

## The one that surprised me

TODO. What did you expect, what did the data say, and what did you check to make sure it
was real and not an artifact?

## Where my first metric was wrong

My first skip rule was "played under 30 s and ended with the forward button", chosen
before I had looked at the data. The real export showed it was wrong in two ways:

- Spotify's `skipped` flag is never set from 2016 to 2021 (0.000), is set on 16% of
  streams in 2022, and on 63% to 79% from 2023. From 2023 it tracks "ended before the
  end of the track", not "skipped".
- The `fwdbtn` label itself drifts: about 2% of streams in 2016 to 2018, 37% in 2021,
  19% in 2023. The share of streams under 5 s barely moves (45% to 60%), so the behaviour
  is stable and the labelling is what changed.
- On the full history the old rule found 18.5% skips, the flag 30.9%, and plain
  "under 30 s" 71.0%. These cannot all be right.

I switched to a duration rule (under 30 s and ended by me), which is comparable across
all years. TODO: new skip rate overall and by year, after rerunning `src.run_all`.
Also removed about 20k zero-millisecond rows. See METHODS.md decisions 4 and 5.

## Recap highlights (optional)

TODO. Pick 3 of the 15 recap insights that are genuinely interesting (for example comfort
songs, reunions, one-week wonders) and state each in one line with the number.

## What I would do next

TODO, one or two lines.
