"""Kaplan-Meier taste decay split by how big the track's peak week was.

Put this file in src/ and run from the project root:  python -m src.decay_by_peak

Why: a track is picked because of its busiest week, then asked when it falls to half of
that week. Picking on the maximum makes a drop afterwards likely by chance alone,
especially when the peak is small (5 plays down to 2 is easy). If the median decay time
differs a lot by peak size, the single headline median mostly measures that effect, not taste.
"""
import numpy as np
import pandas as pd

from src.analysis import kaplan_meier
from src.config import PARAMS
from src.db import connect

BINS = [4, 6, 9, 19, np.inf]
LABELS = ["5-6", "7-9", "10-19", "20+"]


def summarize(name: str, g: pd.DataFrame) -> dict:
    km = kaplan_meier(g["time"].to_numpy(), g["event"].to_numpy())
    below = km[km["survival"] <= 0.5]
    return {
        "peak_plays": name,
        "tracks": len(g),
        "decayed": int(g["event"].sum()),
        "still_alive_pct": round(100 * (1 - g["event"].mean()), 1),
        "median_wk": int(below["week"].iloc[0]) if len(below) else "not reached",
        "alive_at_12wk_pct": round(100 * km.loc[km["week"] <= 12, "survival"].iloc[-1], 1),
    }


def main() -> None:
    con = connect()
    t = con.execute(
        "SELECT track_uri, peak_plays, sustained_halflife_wk, observed_wk_after_peak "
        "FROM m_decay_tracks"
    ).df()
    con.close()

    quiet_fwd = PARAMS["QUIET_FWD"]
    t["event"] = t["sustained_halflife_wk"].notna().astype(int)
    t["time"] = np.where(
        t["event"] == 1, t["sustained_halflife_wk"], t["observed_wk_after_peak"] - quiet_fwd
    )

    dropped = t[t["time"] < 1]
    print(f"binge tracks: {len(t)}")
    print(f"dropped from KM (time < 1, peak in the last few weeks of data, all censored): "
          f"{len(dropped)}")

    t = t[t["time"] >= 1].copy()
    t["bucket"] = pd.cut(t["peak_plays"], bins=BINS, labels=LABELS)

    rows = [summarize("all", t)]
    for label in LABELS:
        g = t[t["bucket"] == label]
        if len(g):
            rows.append(summarize(label, g))
    print()
    print(pd.DataFrame(rows).to_string(index=False))


if __name__ == "__main__":
    main()
