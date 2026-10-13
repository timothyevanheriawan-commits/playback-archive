"""Step 3: the two analyses that are easier in Python than SQL.

  * Kaplan-Meier survival curve for taste decay (handles tracks still "alive" at the
    end of the data, which a plain median would silently get wrong).
  * Life-event overlay: before/after change around each event in data/events.csv,
    judged against how big that same change is on ordinary days (a placebo baseline).
"""
import numpy as np
import pandas as pd

from src.config import EVENTS_CSV, PARAMS
from src.db import connect

BURN_IN_DAYS = 90  # the first months are distorted: everything looks "new"


# ----------------------------------------------------------------------------- decay
def kaplan_meier(time: np.ndarray, event: np.ndarray) -> pd.DataFrame:
    df = pd.DataFrame({"t": time, "e": event})
    rows = [{"week": 0, "at_risk": len(df), "events": 0, "survival": 1.0}]
    survival = 1.0
    for t in sorted(df.loc[df.e == 1, "t"].unique()):
        at_risk = int((df.t >= t).sum())
        events = int(((df.t == t) & (df.e == 1)).sum())
        survival *= 1 - events / at_risk
        rows.append({"week": int(t), "at_risk": at_risk, "events": events, "survival": survival})
    return pd.DataFrame(rows)


def decay_km(con) -> None:
    tracks = con.execute(
        "SELECT sustained_halflife_wk, observed_wk_after_peak FROM m_decay_tracks"
    ).df()
    quiet_fwd = PARAMS["QUIET_FWD"]
    # A decay can only be detected if the following QUIET weeks were observed, so tracks
    # that never decayed are censored at the last testable week.
    tracks["event"] = tracks["sustained_halflife_wk"].notna().astype(int)
    tracks["time"] = np.where(
        tracks["event"] == 1,
        tracks["sustained_halflife_wk"],
        tracks["observed_wk_after_peak"] - quiet_fwd,
    )
    tracks = tracks[tracks["time"] >= 1]
    if tracks.empty:
        km = pd.DataFrame(columns=["week", "at_risk", "events", "survival"])
    else:
        km = kaplan_meier(tracks["time"].to_numpy(), tracks["event"].to_numpy())
    con.register("km_df", km)
    con.execute("CREATE OR REPLACE TABLE m_decay_km AS SELECT * FROM km_df")
    con.unregister("km_df")

    below = km[km["survival"] <= 0.5]
    median = int(below["week"].iloc[0]) if len(below) else None
    print(f"Decay KM: {len(tracks)} tracks, median time to sustained decay = "
          f"{median if median is not None else 'not reached'} weeks")


# ----------------------------------------------------------------------------- events
METRICS = {
    # name: (numerator column, denominator column or None for "per day")
    "listen_min_per_day": ("listen_min", None),
    "sessions_per_day": ("sessions", None),
    "streams_per_day": ("streams", None),
    "new_artists_per_day": ("new_artists", None),
    "skip_rate": ("skips", "eligible_streams"),
}


def window_means(num: np.ndarray, den: np.ndarray, w: int):
    """Return (before, after) arrays for every valid split index i, using window w."""
    cn = np.concatenate([[0.0], np.cumsum(num)])
    cd = np.concatenate([[0.0], np.cumsum(den)])
    idx = np.arange(w, len(num) - w + 1)
    with np.errstate(divide="ignore", invalid="ignore"):
        before = (cn[idx] - cn[idx - w]) / (cd[idx] - cd[idx - w])
        after = (cn[idx + w] - cn[idx]) / (cd[idx + w] - cd[idx])
    return idx, before, after


def event_overlay(con) -> None:
    w = PARAMS["EVENT_WINDOW_DAYS"]
    daily = con.execute("SELECT * FROM m_daily ORDER BY date").df()
    daily["date"] = pd.to_datetime(daily["date"])

    if not EVENTS_CSV.exists():
        events = pd.DataFrame(columns=["event_date", "label", "category"])
    else:
        events = pd.read_csv(EVENTS_CSV, parse_dates=["event_date"])

    rows = []
    start = daily["date"].min()
    for metric, (num_col, den_col) in METRICS.items():
        num = daily[num_col].to_numpy(dtype=float)
        den = daily[den_col].to_numpy(dtype=float) if den_col else np.ones(len(daily))
        idx, before, after = window_means(num, den, w)
        with np.errstate(divide="ignore", invalid="ignore"):
            pct = (after - before) / before
        usable = np.isfinite(pct) & (idx >= BURN_IN_DAYS)
        baseline = np.abs(pct[usable])

        for _, ev in events.iterrows():
            pos = (ev["event_date"] - start).days
            if pos < w or pos + w > len(daily) or pos < BURN_IN_DAYS:
                continue
            i = int(np.where(idx == pos)[0][0])
            if not np.isfinite(pct[i]) or len(baseline) == 0:
                continue
            extremeness = float((baseline >= abs(pct[i])).mean())
            rows.append({
                "event_date": ev["event_date"].date(),
                "label": ev["label"],
                "category": ev.get("category", ""),
                "metric": metric,
                "before": float(before[i]),
                "after": float(after[i]),
                "pct_change": float(pct[i]),
                "share_of_ordinary_days_as_extreme": extremeness,
            })

    out = pd.DataFrame(rows, columns=[
        "event_date", "label", "category", "metric", "before", "after",
        "pct_change", "share_of_ordinary_days_as_extreme",
    ])
    con.register("ev_df", out)
    con.execute("CREATE OR REPLACE TABLE m_event_effects AS SELECT * FROM ev_df")
    con.unregister("ev_df")
    print(f"Event overlay: {len(events)} event(s), {len(out)} metric comparisons "
          f"(window = {w} days, burn-in = {BURN_IN_DAYS} days)")


def run() -> None:
    con = connect()
    decay_km(con)
    event_overlay(con)
    con.close()


if __name__ == "__main__":
    run()
