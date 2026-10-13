"""Generate a SYNTHETIC extended streaming history with known, planted effects.

Purpose: test the pipeline before (or without) real data, and check that the
analysis recovers what was planted. All names are obviously fake.

Planted effects (the analysis should find these):
  * skips up with shuffle on, at night, on android, for first listens
  * skips down when a track is picked by hand (clickrow) and for familiar tracks
  * skip chains: a skip makes the next skip more likely
  * NO weekend effect (a deliberate null)
  * discovery of new tracks drops during a "thesis" window
  * a 2 week listening spike (the "game release")
  * some tracks are binged and then fade at different speeds

Usage:
    python -m src.make_sample
"""
import argparse
import json
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import numpy as np

from src.config import SAMPLE_DIR

TZ_OFFSET = timedelta(hours=7)  # local time is UTC+7
START, END = date(2023, 1, 1), date(2026, 9, 30)
THESIS = (date(2026, 1, 15), date(2026, 6, 30))
SPIKE = (date(2025, 3, 10), date(2025, 3, 24))

PLATFORMS = {
    "android": "Android OS 13 API 33 (samsung, SM-A536E)",
    "windows": "Windows 10 (10.0.19045; x64)",
    "web": "web_player windows 10;chrome 120.0.0.0;desktop",
    "ios": "iOS 17.2 (iPhone14,5)",
}


def sigmoid(x: float) -> float:
    return 1.0 / (1.0 + np.exp(-x))


def build(seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)

    n_artists = 700
    track_artist, track_album = [], []
    for a in range(n_artists):
        for t in range(int(rng.integers(3, 13))):
            track_artist.append(a)
            track_album.append(f"Synthetic Album {a:03d}-{t // 4}")
    n_tracks = len(track_artist)
    track_dur = np.clip(rng.normal(215_000, 45_000, n_tracks), 95_000, 420_000).astype(int)
    decay = rng.uniform(0.86, 0.99, n_tracks)

    artist_order = rng.permutation(n_artists)
    queue = [t for a in artist_order for t in range(n_tracks) if track_artist[t] == a]

    weights = np.zeros(n_tracks)
    plays = np.zeros(n_tracks, dtype=int)
    ptr = 0

    hour_p_week = np.array([1, 1, 0.5, 0.3, 0.2, 0.3, 1, 2, 3, 3, 3, 3, 4, 4, 4, 4, 5, 6, 8, 9, 9, 8, 5, 3], float)
    hour_p_wkend = np.array([2, 1.5, 1, 0.5, 0.3, 0.3, 0.5, 1, 2, 3, 4, 5, 5, 5, 5, 5, 5, 6, 7, 8, 8, 7, 5, 3], float)
    hour_p_week /= hour_p_week.sum()
    hour_p_wkend /= hour_p_wkend.sum()

    records: list[dict] = []
    n_days = (END - START).days + 1

    for day in range(n_days):
        d = START + timedelta(days=day)
        weights *= decay
        in_thesis = THESIS[0] <= d <= THESIS[1]
        weekend = d.weekday() >= 5

        lam = 6.0 if not weekend else 5.0
        if in_thesis:
            lam *= 0.8
        if SPIKE[0] <= d <= SPIKE[1]:
            lam *= 1.9
        p_new = 0.012 if in_thesis else 0.05

        for _ in range(int(rng.poisson(lam))):
            hour = int(rng.choice(24, p=hour_p_wkend if weekend else hour_p_week))
            local_start = datetime(d.year, d.month, d.day, hour, int(rng.integers(0, 60)), int(rng.integers(0, 60)))
            plat = rng.choice(list(PLATFORMS), p=[0.55, 0.33, 0.07, 0.05])
            shuffle = bool(rng.random() < (0.6 if plat == "android" else 0.35))
            n_in_session = max(1, int(rng.lognormal(2.6, 0.7)))
            cursor = local_start
            prev_skip = False

            for k in range(n_in_session):
                is_new = False
                if (rng.random() < p_new or weights.sum() <= 0) and ptr < len(queue):
                    tid = queue[ptr]
                    ptr += 1
                    is_new = True
                else:
                    if weights.sum() <= 0:
                        break
                    tid = int(rng.choice(n_tracks, p=weights / weights.sum()))

                if k == 0:
                    reason_start = str(rng.choice(["clickrow", "appload", "playbtn"], p=[0.5, 0.3, 0.2]))
                elif prev_skip:
                    reason_start = "fwdbtn"
                elif rng.random() < 0.05:
                    reason_start = "clickrow"
                else:
                    reason_start = "trackdone"

                logit = -1.0
                logit += 0.55 * shuffle
                logit += 0.45 * (hour <= 5) - 0.10 * (6 <= hour <= 11)
                logit += {"android": 0.35, "web": 0.10, "windows": 0.0, "ios": 0.0}[plat]
                logit += 1.3 * (plays[tid] == 0) - 0.35 * np.log1p(plays[tid])
                logit += 0.8 * prev_skip
                logit -= 1.2 * (reason_start == "clickrow")
                skip = bool(rng.random() < sigmoid(logit))

                dur = int(track_dur[tid])
                stop_session = False
                if skip:
                    ms = int(rng.uniform(1_500, 25_000))
                    reason_end = "fwdbtn"
                    skipped_flag = True if rng.random() < 0.35 else None
                else:
                    if rng.random() < 0.93:
                        ms = dur - int(rng.integers(0, 1_500))
                        reason_end = "trackdone"
                    else:
                        ms = int(rng.uniform(30_000, dur * 0.95))
                        reason_end = "endplay"
                        stop_session = True
                    skipped_flag = None

                end_local = cursor + timedelta(milliseconds=ms)
                end_utc = (end_local - TZ_OFFSET).replace(tzinfo=timezone.utc)
                records.append({
                    "ts": end_utc.strftime("%Y-%m-%dT%H:%M:%SZ"),
                    "platform": PLATFORMS[plat],
                    "ms_played": ms,
                    "conn_country": "ID",
                    "ip_addr": f"10.{rng.integers(0, 255)}.{rng.integers(0, 255)}.{rng.integers(1, 255)}",
                    "master_metadata_track_name": f"Synthetic Track {tid:04d}",
                    "master_metadata_album_artist_name": f"Synthetic Artist {track_artist[tid]:03d}",
                    "master_metadata_album_album_name": track_album[tid],
                    "spotify_track_uri": f"spotify:track:synth{tid:018d}",
                    "episode_name": None,
                    "episode_show_name": None,
                    "spotify_episode_uri": None,
                    "reason_start": reason_start,
                    "reason_end": reason_end,
                    "shuffle": shuffle,
                    "skipped": skipped_flag,
                    "offline": False,
                    "offline_timestamp": None,
                    "incognito_mode": False,
                })

                weights[tid] += 0.1 if skip else 1.0
                if is_new and not skip and rng.random() < 0.2:
                    weights[tid] = rng.uniform(8, 16)   # a binge
                plays[tid] += 1
                prev_skip = skip
                cursor = end_local + timedelta(seconds=int(rng.integers(0, 3)))
                if stop_session:
                    break

        # the occasional podcast stream (must be filtered out by staging)
        if rng.random() < 0.05:
            h = int(rng.integers(7, 23))
            e = datetime(d.year, d.month, d.day, h, 15) - TZ_OFFSET
            records.append({
                "ts": e.strftime("%Y-%m-%dT%H:%M:%SZ"), "platform": PLATFORMS["android"],
                "ms_played": int(rng.integers(600_000, 2_400_000)), "conn_country": "ID",
                "ip_addr": "10.9.9.9", "master_metadata_track_name": None,
                "master_metadata_album_artist_name": None, "master_metadata_album_album_name": None,
                "spotify_track_uri": None, "episode_name": "Synthetic Episode",
                "episode_show_name": "Synthetic Show", "spotify_episode_uri": "spotify:episode:synth",
                "reason_start": "clickrow", "reason_end": "trackdone", "shuffle": False,
                "skipped": None, "offline": False, "offline_timestamp": None, "incognito_mode": False,
            })

    # a few exact duplicates (staging must remove them)
    dupes = [records[i] for i in rng.choice(len(records), size=len(records) // 1000, replace=False)]
    records.extend(dupes)
    records.sort(key=lambda r: r["ts"])
    return records


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, default=SAMPLE_DIR)
    parser.add_argument("--seed", type=int, default=7)
    args = parser.parse_args()

    records = build(args.seed)
    args.out.mkdir(parents=True, exist_ok=True)
    for old in args.out.glob("Streaming_History_Audio_*.json"):
        old.unlink()
    chunk = 40_000
    for i in range(0, len(records), chunk):
        path = args.out / f"Streaming_History_Audio_2023-2026_{i // chunk}.json"
        path.write_text(json.dumps(records[i:i + chunk]), encoding="utf-8")
    print(f"Wrote {len(records):,} synthetic records to {args.out}")


if __name__ == "__main__":
    main()
