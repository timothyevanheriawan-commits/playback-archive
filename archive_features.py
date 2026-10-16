"""Exploratory views for the Spotify listening archive.

All features use existing summary tables where possible. The module is intentionally
explicit about what summary-only tables can and cannot prove; it does not infer mood
or claim that monthly/yearly chart appearances represent all plays.
"""
from __future__ import annotations

import math
from typing import Any

import altair as alt
import pandas as pd
import streamlit as st

CANVAS = "#111411"
SURFACE = "#1A1E19"
RULE = "#343A32"
TEXT = "#E4E5DC"
MUTED = "#92998E"
SAGE = "#A7B69A"
OCHRE = "#C8B989"
BLUE = "#91A5B1"
CLAY = "#B99A91"
LILAC = "#A9A2B5"
FONT = "DM Sans"


def _col(df: pd.DataFrame | None, names: tuple[str, ...]) -> str | None:
    if df is None:
        return None
    lookup = {str(c).strip().lower(): c for c in df.columns}
    for name in names:
        if name.lower() in lookup:
            return lookup[name.lower()]
    return None


def _text(value: Any) -> str:
    if pd.isna(value):
        return ""
    return str(value).strip()


def _key(track: Any, artist: Any) -> tuple[str, str]:
    return (_text(track).casefold(), _text(artist).casefold())


def _fmt_num(value: Any, decimals: int = 0) -> str:
    try:
        x = float(value)
        if not math.isfinite(x):
            return "—"
        return f"{x:,.{decimals}f}"
    except (TypeError, ValueError):
        return "—"


def _pct(value: Any, decimals: int = 0) -> str:
    try:
        x = float(value)
        if not math.isfinite(x):
            return "—"
        return f"{x:.{decimals}%}"
    except (TypeError, ValueError):
        return "—"


def _chart_theme(chart: alt.Chart, height: int = 260):
    return (
        chart.properties(height=height, background="transparent")
        .configure_view(stroke=None)
        .configure_axis(
            grid=False, domainColor=RULE, tickColor=RULE,
            labelColor=MUTED, titleColor=MUTED,
            labelFont=FONT, titleFont=FONT, labelFontSize=11, titleFontSize=11,
        )
        .configure_axisY(grid=True, gridColor=RULE, gridWidth=0.6, domain=False, ticks=False)
        .configure_legend(labelFont=FONT, titleFont=FONT, labelColor=MUTED, titleColor=MUTED)
    )


def _heading(title: str, description: str) -> None:
    st.markdown(f"### {title}")
    st.caption(description)


def _annual_profile(t: dict, d: dict) -> pd.DataFrame:
    yr = d.get("yr", pd.DataFrame()).copy()
    if yr.empty or "year" not in yr:
        return pd.DataFrame()
    yr["year"] = pd.to_numeric(yr["year"], errors="coerce")
    yr = yr.dropna(subset=["year"]).copy()
    yr["year"] = yr["year"].astype(int)
    night = t.get("night")
    if isinstance(night, pd.DataFrame) and "year" in night:
        cols = [c for c in ("year", "night_share", "peak_hour") if c in night.columns]
        if len(cols) > 1:
            night_small = night[cols].copy()
            night_small["year"] = pd.to_numeric(night_small["year"], errors="coerce")
            yr = yr.merge(night_small, how="left", on="year", suffixes=("", "_night"))
    for name in ("streams", "hours", "skip", "mpp", "night_share", "peak_hour"):
        if name in yr:
            yr[name] = pd.to_numeric(yr[name], errors="coerce")
    yr = yr.sort_values("year").drop_duplicates("year", keep="last").reset_index(drop=True)
    return yr


def _daily_rollup(t: dict) -> tuple[pd.DataFrame | None, str | None]:
    daily = t.get("daily")
    if not isinstance(daily, pd.DataFrame) or daily.empty:
        return None, None
    date_col = _col(daily, ("date", "day", "d", "played_at_date"))
    value_col = _col(daily, ("streams", "plays", "qualified_streams", "hours", "minutes"))
    if not date_col or not value_col:
        return None, None
    df = daily[[date_col, value_col]].copy()
    df["date"] = pd.to_datetime(df[date_col], errors="coerce").dt.normalize()
    df["value"] = pd.to_numeric(df[value_col], errors="coerce").fillna(0)
    df = df.dropna(subset=["date"]).groupby("date", as_index=False)["value"].sum().sort_values("date")
    if df.empty:
        return None, None
    # Fill absent dates with zero; this treats missing dates within the export's coverage
    # as days with no records. The comparison UI states the daily-table basis explicitly.
    full_dates = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    df = df.set_index("date").reindex(full_dates, fill_value=0).rename_axis("date").reset_index()
    df["year"] = df["date"].dt.year
    return df, value_col


def _describe_metric_delta(before: float, after: float, fmt: str = "number") -> str:
    if not math.isfinite(before) or not math.isfinite(after):
        return "Not comparable"
    if fmt == "pct":
        return f"{(after - before) * 100:+.1f} pp"
    if abs(before) < 1e-10:
        return "—" if abs(after) < 1e-10 else "from zero"
    return f"{(after / before - 1) * 100:+.1f}%"


def render_listening_eras(t: dict, d: dict) -> None:
    _heading(
        "Listening eras",
        "Periods are segmented at the largest year-to-year shifts in listening behavior, not guessed life events. "
        "The available signals are skip rate, minutes per play, night-listening share, and busiest hour.",
    )
    profile = _annual_profile(t, d)
    metrics = [m for m in ("skip", "mpp", "night_share", "peak_hour") if m in profile and profile[m].notna().sum() >= 2]
    if len(profile) < 4 or not metrics:
        st.info("At least four annual records and two years of comparable behavior metrics are needed to segment listening eras.")
        return

    diff_rows = []
    for i in range(1, len(profile)):
        parts = {}
        for metric in metrics:
            vals = profile[metric].astype(float)
            diffs = vals.diff().dropna().abs()
            scale = float(diffs.median()) if not diffs.empty else 0.0
            if not math.isfinite(scale) or scale <= 1e-9:
                scale = float(diffs.std(ddof=0)) if not diffs.empty else 0.0
            if not math.isfinite(scale) or scale <= 1e-9:
                scale = max(float(vals.max() - vals.min()), 1.0)
            change = abs(float(profile.iloc[i][metric]) - float(profile.iloc[i - 1][metric])) / scale
            parts[metric] = change
        ranked = sorted(parts.items(), key=lambda item: item[1], reverse=True)
        diff_rows.append({
            "boundary": f"{int(profile.iloc[i - 1]['year'])} → {int(profile.iloc[i]['year'])}",
            "new_year": int(profile.iloc[i]["year"]),
            "position": i,
            "shift_score": sum(parts.values()) / len(parts),
            "main_shift": ranked[0][0].replace("mpp", "minutes per play").replace("skip", "skip rate").replace("night_share", "night share").replace("peak_hour", "busiest hour"),
        })
    changes = pd.DataFrame(diff_rows).sort_values("shift_score", ascending=False)
    max_breaks = min(3, max(1, len(profile) // 4))
    break_count = st.slider("Number of era boundaries", min_value=1, max_value=max_breaks, value=min(2, max_breaks), key="era_break_count")

    # A boundary cannot create a one-year era, and selected boundaries cannot be adjacent.
    candidates = changes[changes["position"].between(2, len(profile) - 2)].sort_values("shift_score", ascending=False)
    selected_positions: list[int] = []
    for _, row in candidates.iterrows():
        pos = int(row["position"])
        if all(abs(pos - chosen) >= 2 for chosen in selected_positions):
            selected_positions.append(pos)
        if len(selected_positions) >= break_count:
            break
    if not selected_positions:
        st.info("There are not enough distinct year boundaries to split these records into multiple eras.")
        return

    selected_positions.sort()
    boundary_years = {int(profile.iloc[pos]["year"]) for pos in selected_positions}
    eras = []
    start_pos = 0
    for end_pos in selected_positions + [len(profile)]:
        part = profile.iloc[start_pos:end_pos].copy()
        if part.empty:
            continue
        eras.append({
            "Era": f"{int(part['year'].min())}–{int(part['year'].max())}",
            "Years": f"{int(part['year'].min())}–{int(part['year'].max())}",
            "Annual plays (mean)": part["streams"].mean() if "streams" in part else float("nan"),
            "Minutes / play": (part["hours"].sum() * 60 / part["streams"].sum()) if {"hours", "streams"}.issubset(part.columns) and part["streams"].sum() else float("nan"),
            "Skip rate (mean)": part["skip"].mean() if "skip" in part else float("nan"),
            "Night share (mean)": part["night_share"].mean() if "night_share" in part else float("nan"),
            "Busiest hour (median)": part["peak_hour"].median() if "peak_hour" in part else float("nan"),
        })
        start_pos = end_pos
    eras_df = pd.DataFrame(eras)
    if not eras_df.empty:
        display = eras_df.copy()
        if "Annual plays (mean)" in display:
            display["Annual plays (mean)"] = display["Annual plays (mean)"].map(lambda x: _fmt_num(x))
        for col in ("Minutes / play", "Busiest hour (median)"):
            if col in display:
                display[col] = display[col].map(lambda x: _fmt_num(x, 1))
        for col in ("Skip rate (mean)", "Night share (mean)"):
            if col in display:
                display[col] = display[col].map(lambda x: _pct(x, 1))
        st.dataframe(display, hide_index=True, width="stretch")

    selected_changes = changes[changes["position"].isin(selected_positions)].sort_values("position")
    if not selected_changes.empty:
        chart = alt.Chart(selected_changes).mark_bar(color=SAGE, size=26, cornerRadiusEnd=2).encode(
            x=alt.X("boundary:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("shift_score:Q", title="Relative shift", axis=alt.Axis(labels=False, ticks=False)),
            tooltip=["boundary", alt.Tooltip("shift_score:Q", format=".2f"), "main_shift"],
        )
        st.altair_chart(_chart_theme(chart, 170), width="stretch")
        st.caption("Boundary scores average normalized changes across the available behavior metrics. They rank shifts within this archive; they are not statistical proof of a life event.")
    last_year = int(profile["year"].max())
    st.caption(f"The last available year is {last_year}. If it is incomplete, yearly volume and era averages involving it should not be compared as full-year totals.")


def _period_summary(profile: pd.DataFrame, t: dict, start_year: int, end_year: int) -> dict:
    subset = profile[profile["year"].between(start_year, end_year)].copy()
    result: dict[str, Any] = {"start": start_year, "end": end_year, "n_years": len(subset)}
    if subset.empty:
        return result
    result["plays"] = float(subset["streams"].sum()) if "streams" in subset else float("nan")
    result["hours"] = float(subset["hours"].sum()) if "hours" in subset else float("nan")
    if "weighted_skips" in subset and result.get("plays", 0) > 0:
        result["skip"] = float(subset["weighted_skips"].sum() / result["plays"])
    elif "skip" in subset and "streams" in subset and subset["streams"].sum() > 0:
        result["skip"] = float((subset["skip"] * subset["streams"]).sum() / subset["streams"].sum())
    else:
        result["skip"] = float(subset["skip"].mean()) if "skip" in subset else float("nan")
    result["mpp"] = result["hours"] * 60 / result["plays"] if result.get("plays", 0) > 0 else float("nan")
    if "night_share" in subset:
        if "streams" in subset and subset["streams"].sum() > 0:
            result["night"] = float((subset["night_share"] * subset["streams"]).sum() / subset["streams"].sum())
        else:
            result["night"] = float(subset["night_share"].mean())
    else:
        result["night"] = float("nan")

    daily, daily_value_label = _daily_rollup(t)
    if daily is not None:
        start = max(pd.Timestamp(start_year, 1, 1), daily["date"].min())
        end = min(pd.Timestamp(end_year, 12, 31), daily["date"].max())
        if start <= end:
            daily_slice = daily[daily["date"].between(start, end)]
            n_days = (end - start).days + 1
            result["daily_rate"] = float(daily_slice["value"].sum() / n_days) if n_days else float("nan")
            result["daily_value_label"] = daily_value_label or "daily table"
            result["calendar_days"] = n_days

    monthly = t.get("monthly")
    if isinstance(monthly, pd.DataFrame) and "artist" in monthly and "month" in monthly:
        mm = monthly.copy()
        mm["month"] = pd.to_datetime(mm["month"], errors="coerce")
        mm = mm[mm["month"].dt.year.between(start_year, end_year)]
        if not mm.empty:
            result["top_month_artists"] = mm["artist"].dropna().astype(str).value_counts().head(5).rename_axis("Artist").reset_index(name="Monthly top-track appearances")
    return result


def render_period_compare(t: dict, d: dict) -> None:
    _heading(
        "Before vs. after",
        "Choose two non-overlapping periods and compare the recorded behavior. The daily rate uses the daily summary table when available; artist appearances are monthly top-track slots, not total artist plays.",
    )
    profile = _annual_profile(t, d)
    years = [int(y) for y in profile["year"].tolist()] if not profile.empty else []
    if len(years) < 2:
        st.info("At least two years of annual summaries are needed for a period comparison.")
        return
    n = len(years)
    early_end_idx = min(n - 2, max(0, n // 3))
    late_start_idx = max(early_end_idx + 1, min(n - 1, (2 * n) // 3))
    early_default = (years[0], years[early_end_idx])
    late_default = (years[late_start_idx], years[-1])
    left, right = st.columns(2)
    with left:
        early = st.select_slider("Earlier period", options=years, value=early_default, key="compare_early")
    with right:
        late = st.select_slider("Later period", options=years, value=late_default, key="compare_late")
    overlap = not (early[1] < late[0] or late[1] < early[0])
    if overlap:
        st.warning("Choose non-overlapping year ranges to make the comparison interpretable.")
        return

    a = _period_summary(profile, t, int(early[0]), int(early[1]))
    b = _period_summary(profile, t, int(late[0]), int(late[1]))
    col_a, col_b = st.columns(2, gap="large")
    for container, summary, label in ((col_a, a, f"{early[0]}–{early[1]}"), (col_b, b, f"{late[0]}–{late[1]}")):
        with container:
            st.markdown(f"#### {label}")
            st.metric("Recorded plays", _fmt_num(summary.get("plays")))
            st.metric("Listening hours", _fmt_num(summary.get("hours")))
            st.metric("Weighted skip rate", _pct(summary.get("skip"), 1))
            st.metric("Minutes per play", _fmt_num(summary.get("mpp"), 2))
            st.metric("Night-listening share", _pct(summary.get("night"), 1))
            if "daily_rate" in summary:
                st.metric(f"{summary.get('daily_value_label', 'Daily value')} per calendar day", _fmt_num(summary["daily_rate"], 1))
            else:
                st.caption("Daily rate unavailable: the daily table is missing or lacks a recognizable date/count column.")
    st.divider()
    st.markdown("#### What changed")
    comparisons = [
        ("Weighted skip rate", a.get("skip", float("nan")), b.get("skip", float("nan")), "pct"),
        ("Minutes per play", a.get("mpp", float("nan")), b.get("mpp", float("nan")), "number"),
        ("Night-listening share", a.get("night", float("nan")), b.get("night", float("nan")), "pct"),
    ]
    rows = []
    for label, av, bv, fmt in comparisons:
        rows.append({"Metric": label, "Earlier": _pct(av, 1) if fmt == "pct" else _fmt_num(av, 2), "Later": _pct(bv, 1) if fmt == "pct" else _fmt_num(bv, 2), "Change": _describe_metric_delta(float(av), float(bv), fmt) if pd.notna(av) and pd.notna(bv) else "—"})
    st.dataframe(pd.DataFrame(rows), hide_index=True, width="stretch")
    artist_left, artist_right = st.columns(2)
    with artist_left:
        st.markdown("**Artists featuring in earlier monthly top tracks**")
        if "top_month_artists" in a:
            st.dataframe(a["top_month_artists"], hide_index=True, width="stretch")
        else:
            st.caption("No monthly top-track artist table is available for this period.")
    with artist_right:
        st.markdown("**Artists featuring in later monthly top tracks**")
        if "top_month_artists" in b:
            st.dataframe(b["top_month_artists"], hide_index=True, width="stretch")
        else:
            st.caption("No monthly top-track artist table is available for this period.")
    st.caption("Total plays and listening hours depend on period length. Use the daily rate, weighted ratios, and minutes-per-play figure for more useful behavioral comparisons. The last year may be incomplete.")


def _artist_year_rollup(t: dict, years: list[int]) -> pd.DataFrame | None:
    df = t.get("artist_yearly")
    if not isinstance(df, pd.DataFrame) or df.empty:
        return None
    artist_col = _col(df, ("artist", "artist_name", "name"))
    year_col = _col(df, ("year", "year_num", "listening_year"))
    plays_col = _col(df, ("streams", "plays", "qualified_plays", "play_count", "total_plays", "stream_count"))
    if not artist_col or not year_col:
        return None
    if not plays_col:
        # Without an explicit count field, a row may represent a ranked artist rather than
        # true listening presence, so do not silently call it a loyalty index.
        return None
    slim = df[[artist_col, year_col, plays_col]].copy()
    slim.columns = ["artist", "year", "plays"]
    slim["artist"] = slim["artist"].astype(str).str.strip()
    slim["year"] = pd.to_numeric(slim["year"], errors="coerce")
    slim["plays"] = pd.to_numeric(slim["plays"], errors="coerce").fillna(0)
    slim = slim.dropna(subset=["year"])
    slim["year"] = slim["year"].astype(int)
    slim = slim[slim["year"].isin(years) & (slim["artist"] != "") & (slim["plays"] > 0)]
    if slim.empty:
        return None
    total_years = max(1, len(years))
    out = slim.groupby("artist", as_index=False).agg(
        total_plays=("plays", "sum"), active_years=("year", "nunique"),
    )
    out["Loyalty index"] = out["active_years"] / total_years * 100
    out["Years active"] = out["active_years"].map(lambda x: f"{int(x)} / {total_years}")
    out = out.sort_values(["Loyalty index", "total_plays"], ascending=False)
    return out


def render_artist_loyalty(t: dict, d: dict) -> None:
    _heading(
        "Artist loyalty",
        "Consistency over raw popularity. The index is the share of covered years with at least one recorded play—but only when an artist-by-year play-count table exists.",
    )
    profile = _annual_profile(t, d)
    years = [int(y) for y in profile["year"].tolist()] if not profile.empty else []
    indexed = _artist_year_rollup(t, years)
    if indexed is not None:
        show = indexed.head(25).copy()
        show["Loyalty index"] = show["Loyalty index"].map(lambda x: f"{x:.0f}/100")
        show["total_plays"] = show["total_plays"].map(_fmt_num)
        show = show.rename(columns={"artist": "Artist", "total_plays": "Recorded plays", "Years active": "Years active"})
        st.dataframe(show[["Artist", "Loyalty index", "Years active", "Recorded plays"]], hide_index=True, width="stretch")
        chart_data = indexed.head(15).sort_values("Loyalty index", ascending=True)
        chart = alt.Chart(chart_data).mark_bar(color=SAGE, size=13, cornerRadiusEnd=2).encode(
            x=alt.X("Loyalty index:Q", title="Share of covered years active", scale=alt.Scale(domain=[0, 100])),
            y=alt.Y("artist:N", title=None, sort="-x"),
            tooltip=["artist", alt.Tooltip("Loyalty index:Q", format=".1f"), "active_years", alt.Tooltip("total_plays:Q", format=",")],
        )
        st.altair_chart(_chart_theme(chart, max(220, len(chart_data) * 23)), width="stretch")
        st.caption("Definition: active years ÷ years covered in the annual archive × 100. This measures persistence, not affection, and ignores play counts when deciding the index score.")
        return

    st.info("A true artist loyalty index needs an artist-by-year table with play counts. No compatible table was found, so the fallback below shows archive evidence only; it does not pretend monthly leaders are all artist plays.")
    monthly = t.get("monthly")
    records: dict[str, dict[str, Any]] = {}

    def entry(artist: Any) -> dict[str, Any] | None:
        name = _text(artist)
        if not name:
            return None
        if name not in records:
            records[name] = {"Artist": name, "Monthly top-track months": 0, "Year anthem appearances": 0, "Daypart #1 appearances": 0, "Largest recorded comeback gap (days)": None}
        return records[name]

    if isinstance(monthly, pd.DataFrame) and "artist" in monthly:
        month_col = _col(monthly, ("month", "date"))
        for artist, group in monthly.groupby("artist", dropna=True):
            row = entry(artist)
            if row is not None:
                row["Monthly top-track months"] = group[month_col].nunique() if month_col else len(group)
    anthems = t.get("anthems")
    if isinstance(anthems, pd.DataFrame) and "artist" in anthems:
        for artist, group in anthems.groupby("artist", dropna=True):
            row = entry(artist)
            if row is not None:
                row["Year anthem appearances"] = int(group["year"].nunique()) if "year" in group else len(group)
    daypart = t.get("daypart")
    if isinstance(daypart, pd.DataFrame) and {"artist", "rank"}.issubset(daypart.columns):
        leaders = daypart[pd.to_numeric(daypart["rank"], errors="coerce") == 1]
        for artist, group in leaders.groupby("artist", dropna=True):
            row = entry(artist)
            if row is not None:
                row["Daypart #1 appearances"] = len(group)
    reunions = t.get("reunions")
    if isinstance(reunions, pd.DataFrame) and {"artist", "gap_days"}.issubset(reunions.columns):
        for _, reunion in reunions.iterrows():
            row = entry(reunion.get("artist"))
            if row is not None:
                gap = pd.to_numeric(pd.Series([reunion.get("gap_days")]), errors="coerce").iloc[0]
                if pd.notna(gap):
                    old = row["Largest recorded comeback gap (days)"]
                    row["Largest recorded comeback gap (days)"] = int(max(gap, old or 0))
    if not records:
        st.info("No usable artist names were found in the monthly, yearly anthem, daypart, or comeback summaries.")
        return
    fallback = pd.DataFrame(records.values()).sort_values(
        ["Monthly top-track months", "Year anthem appearances", "Daypart #1 appearances"], ascending=False
    )
    st.dataframe(fallback.head(30), hide_index=True, width="stretch")
    st.caption("To enable the numeric index, add `data/public/recap_artist_yearly.parquet` (or CSV) with columns `artist`, `year`, and `streams` or `plays`. Rows should represent an artist's recorded plays in each active year.")


def _track_tables(t: dict) -> dict[str, pd.DataFrame]:
    names = ("monthly", "anthems", "burnout", "love_hate", "one_week_wonders")
    return {name: t.get(name) for name in names if isinstance(t.get(name), pd.DataFrame) and not t[name].empty}


def _track_catalog(t: dict) -> list[tuple[tuple[str, str], str]]:
    seen: dict[tuple[str, str], str] = {}
    for df in _track_tables(t).values():
        track_col = _col(df, ("track_name", "track", "title", "name"))
        artist_col = _col(df, ("artist", "artist_name"))
        if not track_col:
            continue
        for _, row in df.iterrows():
            track = _text(row.get(track_col))
            artist = _text(row.get(artist_col)) if artist_col else ""
            if not track:
                continue
            key = _key(track, artist)
            seen[key] = f"{track} — {artist}" if artist else track
    return sorted(seen.items(), key=lambda item: item[1].casefold())


def _matching_rows(df: pd.DataFrame | None, key: tuple[str, str]) -> pd.DataFrame:
    if not isinstance(df, pd.DataFrame) or df.empty:
        return pd.DataFrame()
    track_col = _col(df, ("track_name", "track", "title", "name"))
    artist_col = _col(df, ("artist", "artist_name"))
    if not track_col:
        return pd.DataFrame()
    mask = df[track_col].map(lambda x: _text(x).casefold()) == key[0]
    if artist_col:
        mask &= df[artist_col].map(lambda x: _text(x).casefold()) == key[1]
    return df[mask].copy()


def render_track_lifecycle(t: dict, d: dict) -> None:
    _heading(
        "Track lifecycle explorer",
        "Choose a song to inspect its appearances in the existing monthly/yearly summaries, plus burnout and skip-related records. These are summary-table appearances—not a complete play-by-play timeline.",
    )
    catalog = _track_catalog(t)
    if not catalog:
        st.info("No track names were found in the available monthly, anthem, burnout, skip, or one-week summary tables.")
        return
    labels = [label for _, label in catalog]
    chosen_label = st.selectbox("Track", labels, index=0, key="lifecycle_track")
    key = next(k for k, label in catalog if label == chosen_label)
    matches = {name: _matching_rows(df, key) for name, df in _track_tables(t).items()}
    monthly_hits = matches.get("monthly", pd.DataFrame())
    anthem_hits = matches.get("anthems", pd.DataFrame())
    burnout_hits = matches.get("burnout", pd.DataFrame())
    skip_hits = matches.get("love_hate", pd.DataFrame())
    wonder_hits = matches.get("one_week_wonders", pd.DataFrame())

    c1, c2, c3, c4 = st.columns(4)
    with c1:
        st.metric("Monthly top-track appearances", len(monthly_hits))
    with c2:
        st.metric("Year anthem appearances", len(anthem_hits))
    with c3:
        if not skip_hits.empty and "skip_rate" in skip_hits:
            st.metric("Recorded skip rate", _pct(pd.to_numeric(skip_hits.iloc[0]["skip_rate"], errors="coerce"), 1))
        else:
            st.metric("Recorded skip rate", "—")
    with c4:
        if not burnout_hits.empty and "sustained_halflife_wk" in burnout_hits:
            st.metric("Sustained half-life", f"{_fmt_num(burnout_hits.iloc[0]['sustained_halflife_wk'], 1)} weeks")
        else:
            st.metric("Sustained half-life", "—")

    events = []
    month_col = _col(monthly_hits, ("month", "date"))
    monthly_plays_col = _col(monthly_hits, ("track_plays", "plays", "qualified_plays"))
    for _, row in monthly_hits.iterrows():
        if not month_col:
            continue
        date = pd.to_datetime(row.get(month_col), errors="coerce")
        if pd.isna(date):
            continue
        events.append({"date": date, "appearance": "Monthly top track", "plays_in_summary": pd.to_numeric(row.get(monthly_plays_col), errors="coerce") if monthly_plays_col else None})
    anthem_year_col = _col(anthem_hits, ("year", "year_num"))
    anthem_plays_col = _col(anthem_hits, ("plays", "qualified_plays", "streams"))
    anthem_date_col = _col(anthem_hits, ("first_date", "date"))
    for _, row in anthem_hits.iterrows():
        date = pd.to_datetime(row.get(anthem_date_col), errors="coerce") if anthem_date_col else pd.NaT
        year = pd.to_numeric(pd.Series([row.get(anthem_year_col)]), errors="coerce").iloc[0] if anthem_year_col else pd.NA
        if pd.isna(date) and pd.notna(year):
            date = pd.Timestamp(int(year), 7, 1)
        if pd.isna(date):
            continue
        events.append({"date": date, "appearance": "Yearly anthem", "plays_in_summary": pd.to_numeric(row.get(anthem_plays_col), errors="coerce") if anthem_plays_col else None})

    if events:
        event_df = pd.DataFrame(events).sort_values("date")
        chart = alt.Chart(event_df).mark_point(filled=True, size=115, stroke=CANVAS, strokeWidth=1).encode(
            x=alt.X("date:T", title=None, axis=alt.Axis(format="%Y", labelAngle=0)),
            y=alt.Y("appearance:N", title=None, sort=["Monthly top track", "Yearly anthem"]),
            color=alt.Color("appearance:N", title=None, scale=alt.Scale(domain=["Monthly top track", "Yearly anthem"], range=[SAGE, OCHRE]), legend=None),
            tooltip=[alt.Tooltip("date:T", title="Date", format="%b %Y"), "appearance", alt.Tooltip("plays_in_summary:Q", title="Plays in summary", format=",")],
        )
        st.altair_chart(_chart_theme(chart, 180), width="stretch")
    else:
        st.caption("This track has no dated appearances in the monthly or annual anthem summaries.")

    if not monthly_hits.empty:
        _heading("Months it led", "The recorded count is the track's play count in months where it was the top track; it is not its lifetime total.")
        show_cols = [c for c in ("month", "track_name", "artist", "track_plays", "hours") if c in monthly_hits.columns]
        show = monthly_hits[show_cols].copy()
        if "month" in show:
            show["month"] = pd.to_datetime(show["month"], errors="coerce").dt.strftime("%Y-%m")
            show = show.sort_values("month", ascending=False)
        st.dataframe(show, hide_index=True, width="stretch")
    if not anthem_hits.empty:
        _heading("Yearly anthem records", "Years in which this track was the most-played track, according to the yearly summary table.")
        st.dataframe(anthem_hits, hide_index=True, width="stretch")
    if not skip_hits.empty:
        _heading("Play and skip evidence", "These figures come from the project's existing qualified-play definition.")
        st.dataframe(skip_hits, hide_index=True, width="stretch")
    if not burnout_hits.empty:
        _heading("Burnout summary", "Half-life and censoring are shown as produced by the existing analysis; the method notes warn that this measure may be coarse.")
        st.dataframe(burnout_hits, hide_index=True, width="stretch")
    if not wonder_hits.empty:
        _heading("One-week wonder record", "This track appears in the existing short-lived listening summary.")
        st.dataframe(wonder_hits, hide_index=True, width="stretch")


def render_fingerprint(t: dict, d: dict) -> None:
    _heading(
        "Listening fingerprint",
        "A compact description of your recorded habits—not a personality diagnosis. Every dimension below maps to an observable metric from the existing summaries.",
    )
    profile = _annual_profile(t, d)
    if profile.empty:
        st.info("Annual behavior summaries are required to build a listening fingerprint.")
        return
    total_streams = float(profile["streams"].sum()) if "streams" in profile else 0.0
    total_hours = float(profile["hours"].sum()) if "hours" in profile else 0.0
    weighted_skip = float(profile["weighted_skips"].sum() / total_streams) if "weighted_skips" in profile and total_streams else (
        float((profile["skip"] * profile["streams"]).sum() / total_streams) if {"skip", "streams"}.issubset(profile.columns) and total_streams else float("nan")
    )
    minutes_per_play = total_hours * 60 / total_streams if total_streams else float("nan")
    if "night_share" in profile and profile["night_share"].notna().any():
        if "streams" in profile and profile["streams"].sum() > 0:
            night_share = float((profile["night_share"] * profile["streams"]).sum() / profile["streams"].sum())
        else:
            night_share = float(profile["night_share"].mean())
        night_peak = profile.loc[profile["night_share"].idxmax()]
    else:
        night_share, night_peak = float("nan"), None
    skip_best = profile.loc[profile["skip"].idxmin()] if "skip" in profile and profile["skip"].notna().any() else None
    duration_peak = profile.loc[profile["mpp"].idxmax()] if "mpp" in profile and profile["mpp"].notna().any() else None
    hour_mode = profile["peak_hour"].mode().iloc[0] if "peak_hour" in profile and profile["peak_hour"].notna().any() else None

    m1, m2, m3 = st.columns(3)
    m1.metric("Night-listening share", _pct(night_share, 1), help="Weighted annual share of plays classified as late night, based on the current analysis definition.")
    m2.metric("Skip rate", _pct(weighted_skip, 1), help="A short play may count as a skip; this is not a direct measure of dislike.")
    m3.metric("Average minutes per play", _fmt_num(minutes_per_play, 2))

    details = []
    if night_peak is not None:
        details.append({"Dimension": "Night listening", "Finding": f"Highest in {int(night_peak['year'])} ({_pct(night_peak['night_share'], 1)} of plays).", "How to read it": "Describes timing, not mood or sleep behavior."})
    if skip_best is not None:
        details.append({"Dimension": "Lowest annual skip rate", "Finding": f"{int(skip_best['year'])} ({_pct(skip_best['skip'], 1)}).", "How to read it": "Depends on the project's short-play/skip definition."})
    if duration_peak is not None:
        details.append({"Dimension": "Longest average play", "Finding": f"{int(duration_peak['year'])} ({_fmt_num(duration_peak['mpp'], 2)} minutes per play).", "How to read it": "Long sessions may include idle or paused playback."})
    if hour_mode is not None:
        details.append({"Dimension": "Most common busiest hour", "Finding": f"{int(hour_mode):02d}:00 across annual records.", "How to read it": "This is the mode of each year's busiest hour, not the most common listening hour across all plays."})
    if details:
        st.dataframe(pd.DataFrame(details), hide_index=True, width="stretch")

    left, right = st.columns(2, gap="large")
    with left:
        if "night_share" in profile:
            _heading("Night share by year", "The proportion of annual plays classified as late-night listening.")
            ch = alt.Chart(profile.dropna(subset=["night_share"])).mark_line(color=SAGE, strokeWidth=2, point=alt.OverlayMarkDef(color=SAGE, filled=True, size=55)).encode(
                x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("night_share:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(zero=True)),
                tooltip=["year:O", alt.Tooltip("night_share:Q", title="Night share", format=".1%")],
            )
            st.altair_chart(_chart_theme(ch, 230), width="stretch")
    with right:
        if "skip" in profile:
            _heading("Skip rate by year", "Track the direction over time; do not interpret short plays as dislike automatically.")
            ch = alt.Chart(profile.dropna(subset=["skip"])).mark_line(color=OCHRE, strokeWidth=2, point=alt.OverlayMarkDef(color=OCHRE, filled=True, size=55)).encode(
                x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),
                y=alt.Y("skip:Q", title=None, axis=alt.Axis(format="%"), scale=alt.Scale(zero=True)),
                tooltip=["year:O", alt.Tooltip("skip:Q", title="Skip rate", format=".1%")],
            )
            st.altair_chart(_chart_theme(ch, 230), width="stretch")
    cols = [c for c in ("year", "streams", "hours", "mpp", "skip", "night_share", "peak_hour") if c in profile.columns]
    annual = profile[cols].copy()
    annual = annual.rename(columns={"year": "Year", "streams": "Plays", "hours": "Hours", "mpp": "Minutes / play", "skip": "Skip rate", "night_share": "Night share", "peak_hour": "Busiest hour"})
    st.dataframe(annual, hide_index=True, width="stretch")
    st.caption("If the last year is partial, its volume and patterns may reflect only the months currently present in the export.")


def render_explore(t: dict, d: dict) -> None:
    st.markdown("## Explore the archive")
    st.caption("Five views for comparing periods, spotting behavioral shifts, and inspecting the songs behind your summary statistics.")
    selector = st.radio(
        "Explore section",
        ["Listening eras", "Before vs. after", "Artist loyalty", "Track lifecycle", "Listening fingerprint"],
        horizontal=True, label_visibility="collapsed", key="archive_explore_section",
    )
    st.divider()
    if selector == "Listening eras":
        render_listening_eras(t, d)
    elif selector == "Before vs. after":
        render_period_compare(t, d)
    elif selector == "Artist loyalty":
        render_artist_loyalty(t, d)
    elif selector == "Track lifecycle":
        render_track_lifecycle(t, d)
    else:
        render_fingerprint(t, d)
