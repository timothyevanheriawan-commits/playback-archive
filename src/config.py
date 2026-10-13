"""Central config. Change the numbers here; SQL files read them as {{NAME}} tokens."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
SAMPLE_DIR = ROOT / "data" / "raw_sample"
PUBLIC_DIR = ROOT / "data" / "public"
EVENTS_CSV = ROOT / "data" / "events.csv"
SQL_DIR = ROOT / "sql"
DB_PATH = ROOT / "db" / "spotify.duckdb"
REPORT_DIR = ROOT / "reports"

PARAMS = {
    "TZ": "Asia/Jakarta",        # local time zone for hour-of-day and weekday logic
    "SKIP_MS": 30_000,           # a play under this many ms can count as a skip
    "BOUNCE_MS": 5_000,          # under this many ms = a bounce (sampled and dropped)
    "MIN_TRACK_MS": 60_000,      # ignore tracks completed naturally in under this (interludes)
    "GAP_MIN": 30,               # primary session gap, in minutes
    "GAP_GRID": "10,20,30,45,60",  # sensitivity sweep for the session gap
    "BINGE_MIN_PLAYS": 5,        # plays in the busiest week for a track to count as a binge
    "DECAY_QUIET_WEEKS": 4,      # weeks that must stay under half the peak to call it decayed
    "MIN_OBS_WEEKS": 8,          # weeks of follow-up needed after the peak to trust a track
    "EVENT_WINDOW_DAYS": 28,     # before/after window for life events
    # --- recap (Wrapped-style) settings ---
    "RECAP_MIN_STREAMS": 100,    # months with fewer qualified plays are flagged thin
    "TOPN": 20,                  # size of "top artists" lists used for overlaps
    "COMFORT_MIN_PLAYS": 10,     # finished this many times and never skipped
    "LOVEHATE_MIN_PLAYS": 15,    # qualified plays needed for the love-hate list
    "REUNION_GAP_DAYS": 365,     # silence that counts as "dropped" an artist
    "REUNION_MIN_PLAYS": 10,     # plays needed both before the gap and after the return
    "RECAP_MIN_ARTIST_PLAYS": 100,  # artists below this are ignored in weekend/weekday lift
    "WONDER_MIN_PLAYS": 5,       # one-week wonder: at least this many plays
    "WONDER_SPAN_DAYS": 14,      # ...all within this many days
    "WONDER_QUIET_DAYS": 365,    # ...and not touched for this long before the data ends
}
PARAMS["QUIET_FWD"] = PARAMS["DECAY_QUIET_WEEKS"] - 1

# Spotify has used both names over the years.
RAW_PATTERNS = ["Streaming_History_Audio_*.json", "endsong_*.json"]

# Only these columns are ever read into the database. IP address, user agent and
# username are deliberately NOT on the list, so they never leave the raw files.
KEEP_COLUMNS = [
    "ts",
    "platform",
    "ms_played",
    "conn_country",
    "master_metadata_track_name",
    "master_metadata_album_artist_name",
    "master_metadata_album_album_name",
    "spotify_track_uri",
    "episode_name",
    "episode_show_name",
    "spotify_episode_uri",
    "reason_start",
    "reason_end",
    "shuffle",
    "skipped",
    "offline",
    "offline_timestamp",
    "incognito_mode",
]
