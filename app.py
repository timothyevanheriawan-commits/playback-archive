"""10 years of listening: a personal Spotify history dashboard.



Run from the project root (next to src/ and data/):

    pip install streamlit pandas altair pyarrow

    python -m streamlit run app.py



Layout of this file: colors, styles, data loading, derived facts,

charts, page sections, main.

"""

import html

from pathlib import Path

from string import Template



import altair as alt

import pandas as pd

import streamlit as st

from archive_features import render_explore



st.set_page_config(page_title="Playback Archive · Spotify archive", page_icon="♫", layout="wide", initial_sidebar_state="expanded")

DATA = Path(__file__).parent / "data" / "public"





# ---------------------------------------------------------------- colors

class C:
    CANVAS = "#111411"
    SURFACE = "#1A1E19"
    SURFACE_ALT = "#20251F"
    RULE = "#343A32"
    TEXT = "#E4E5DC"
    MUTED = "#92998E"
    SAGE = "#A7B69A"
    SAGE_DARK = "#65725F"
    OCHRE = "#C8B989"
    CLAY = "#B99A91"
    BLUE = "#91A5B1"
    LILAC = "#A9A2B5"


PALETTE = [C.SAGE, C.OCHRE, C.BLUE, C.LILAC, C.CLAY, "#7D9383"]
FONT = "DM Sans"
MONO = "IBM Plex Mono"

CSS = Template(
    """
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=IBM+Plex+Mono:wght@400;500&family=Newsreader:opsz,wght@6..72,400..700&display=swap');
:root {
    --canvas:$canvas; --surface:$surface; --surface-alt:$surface_alt;
    --rule:$rule; --text:$text; --muted:$muted; --sage:$sage; --ochre:$ochre;
    --head:'Newsreader',Georgia,serif; --body:'DM Sans',sans-serif; --mono:'IBM Plex Mono',monospace;
}
.stApp {background:var(--canvas);}
.stApp, .stMarkdown, .stCaption {font-family:var(--body);}
#MainMenu, footer {visibility:hidden;}
header[data-testid="stHeader"] {background:transparent;}
.hero .v, .card .v {font-variant-numeric:lining-nums tabular-nums;}
.block-container {max-width:1180px; padding-top:4.5rem; padding-bottom:3.5rem;}

/* Archive identity: understated, no gradient hero treatment. */
.kicker {font-family:var(--mono); font-size:.7rem; font-weight:500; color:var(--sage); letter-spacing:.11em; text-transform:uppercase;}
.title {font-family:var(--head); font-size:clamp(2.6rem,4.4vw,3.7rem); font-weight:600; letter-spacing:-.025em; line-height:1.05;
        margin:.65rem 0 .8rem 0; color:var(--text);}
.sub {font-size:.96rem; color:var(--muted); line-height:1.65; max-width:500px;}
.hero {background:var(--surface); border:1px solid var(--rule); border-radius:8px; padding:22px 24px; min-height:152px;}
.hero .l {font-family:var(--mono); font-size:.76rem; font-weight:500; color:var(--muted); letter-spacing:.07em; text-transform:uppercase;}
.hero .v {font-family:var(--head); font-size:clamp(2.35rem,3.5vw,3.2rem); font-weight:600; letter-spacing:-.02em; line-height:1.05;
          color:var(--text); margin:.55rem 0 .45rem;}
.hero .n {font-size:.83rem; color:var(--muted); line-height:1.5;}

.strip {display:grid; grid-template-columns:repeat(auto-fit,minmax(180px,1fr)); gap:0; margin:1.15rem 0 .6rem; border-top:1px solid var(--rule); border-bottom:1px solid var(--rule);}
.card {background:var(--surface); border:1px solid var(--rule); border-radius:8px; padding:15px 17px;}
.strip .card {background:transparent; border:0; border-radius:0; padding:16px 16px 17px 0;}
.card .k {font-family:var(--mono); font-size:.74rem; font-weight:400; color:var(--muted); letter-spacing:.045em; text-transform:uppercase;}
.card .v {font-family:var(--head); font-size:1.8rem; font-weight:600; letter-spacing:-.015em; color:var(--text); margin:.35rem 0 .25rem; line-height:1.15;}
.card .d {font-size:.82rem; color:var(--muted); line-height:1.5;}

.take {display:grid; grid-template-columns:repeat(auto-fit,minmax(260px,1fr)); gap:0 22px; margin:.8rem 0 1.2rem;}
.take .card {background:transparent; border:0; border-top:1px solid var(--rule); border-radius:0; padding:15px 0 16px;}
.take .card .v {font-size:1.8rem; color:var(--sage);}

.chapter {margin:2.2rem 0 1.15rem;}
.chapter h2 {font-family:var(--head); font-size:1.65rem; font-weight:650; letter-spacing:-.035em; line-height:1.2;
             margin:0 0 .5rem; color:var(--text);}
.chapter p {font-size:.92rem; color:var(--muted); max-width:680px; line-height:1.65; margin:0;}
.fig {margin:1.55rem 0 .35rem;}
.fig .t {font-size:.98rem; font-weight:600; color:var(--text);}
.fig .s {font-size:.82rem; color:var(--muted); margin-top:.22rem; line-height:1.5;}
.note {font-size:.85rem; color:var(--muted); margin:.3rem 0 0; max-width:720px; line-height:1.6;}
.note b {color:var(--text); font-weight:600;}

.feature {background:var(--surface); border:1px solid var(--rule); border-top:2px solid var(--sage); border-radius:8px; padding:20px 22px;}
.feature .a {font-family:var(--head); font-size:1.8rem; font-weight:650; letter-spacing:-.035em; color:var(--text); margin:.15rem 0 .55rem;}
.feature .m {font-size:.9rem; color:var(--muted); line-height:1.8;}
.feature b {color:var(--sage); font-weight:600;}

.dayrow {display:grid; grid-template-columns:repeat(auto-fit,minmax(190px,1fr)); gap:22px;}
.day .h {font-family:var(--mono); font-size:.68rem; font-weight:500; color:var(--sage); letter-spacing:.06em; text-transform:uppercase; margin-bottom:.45rem;}
.day .r {font-size:.87rem; color:var(--text); padding:.42rem 0; border-top:1px solid var(--rule);}
.day .r span {font-family:var(--mono); font-size:.75rem; color:var(--muted); margin-right:.65rem;}

.foot {margin-top:2.6rem; padding-top:.9rem; border-top:1px solid var(--rule); font-family:var(--mono); font-size:.68rem; color:var(--muted); line-height:1.7;}
button[data-baseweb="tab"] {font-family:var(--body); font-size:.86rem; font-weight:500;}
div[data-baseweb="tab-highlight"] {background-color:var(--sage) !important; height:2px !important;}
div[data-baseweb="tab-border"] {background-color:var(--rule) !important;}
[data-testid="stDataFrame"] {border:1px solid var(--rule); border-radius:8px; overflow:hidden;}
[data-testid="stAlert"] {border-radius:8px;}

@media (max-width: 760px) {
  .block-container {padding-top:4rem; padding-bottom:2.5rem;}
  .title {font-size:2.55rem;}
  .hero {margin-top:.6rem;}
  .strip {grid-template-columns:repeat(2,minmax(0,1fr));}
  .strip .card {padding:13px 10px 14px 0;}
  .card .v {font-size:1.55rem;}
}
</style>
"""
).substitute(
    canvas=C.CANVAS, surface=C.SURFACE, surface_alt=C.SURFACE_ALT,
    rule=C.RULE, text=C.TEXT, muted=C.MUTED, sage=C.SAGE, ochre=C.OCHRE,
)






# ---------------------------------------------------------------- data

@st.cache_data

def read(name: str) -> pd.DataFrame | None:

    for ext, reader in (("parquet", pd.read_parquet), ("csv", pd.read_csv)):

        path = DATA / f"{name}.{ext}"

        if path.exists():

            return reader(path)

    return None





def read_first(*names: str) -> pd.DataFrame | None:
    """Return the first optional table that exists, without making it required."""
    for name in names:
        df = read(name)
        if df is not None:
            return df
    return None



def need(name: str) -> pd.DataFrame:

    df = read(name)

    if df is None:

        st.error(f"Missing table: {name} in {DATA}")

        st.stop()

    return df





def load_tables() -> dict:

    names = ["monthly", "night_owl", "slow_burns", "burnout", "love_hate", "reunions", "records", "devices",
             "anthems", "daypart", "one_week_wonders"]

    t = {n: need(f"recap_{n}") for n in names}

    t["night"] = t["night_owl"].sort_values("year")

    t["facts"] = need("recap_facts").set_index("stat")["value"]

    t["daily"] = read("daily")

    t["skip_definitions"] = read("skip_definitions")
    # Optional rollup enables a proper year-persistence index. The app still runs
    # without it and shows summary-slot evidence instead of inventing an index.
    t["artist_yearly"] = read_first(
        "recap_artist_yearly", "artist_yearly", "recap_artists_by_year", "artists_by_year"
    )

    return t





# ---------------------------------------------------------------- facts

def derive(t: dict) -> dict:

    d = {}

    dev = t["devices"].copy()

    dev["weighted_skips"] = dev["skip_rate"] * dev["streams"]

    yr = (dev.groupby("year", as_index=False)

          .agg(streams=("streams", "sum"), hours=("hours", "sum"), weighted_skips=("weighted_skips", "sum")))

    yr["skip"] = yr["weighted_skips"] / yr["streams"]

    yr["mpp"] = yr["hours"] * 60 / yr["streams"]

    d["yr"] = yr

    d["first"], d["last"] = yr.iloc[0], yr.iloc[-1]

    d["plays"], d["hours"] = yr["streams"].sum(), yr["hours"].sum()

    d["peak_plays_year"] = yr.sort_values("streams").iloc[-1]

    d["peak_hours_year"] = yr.sort_values("hours").iloc[-1]



    rec = t["records"]

    d["streak"] = rec[rec["record"].str.contains("streak")].iloc[0]



    d["n0"], d["n1"] = t["night"].iloc[0], t["night"].iloc[-1]



    r = t["reunions"].copy()

    r["ratio"] = r["plays_since_return"] / r["plays_before"]

    d["comeback"] = r.sort_values("ratio", ascending=False).iloc[0]



    d["anthem"] = t["anthems"].sort_values("year").iloc[-1]



    m = t["monthly"].copy()

    if "thin_month" in m:

        m = m[~m["thin_month"].astype(bool)]

    m["month"] = pd.to_datetime(m["month"])

    d["months"] = m

    d["peak_month"] = m.sort_values("hours").iloc[-1]

    counts = m["artist"].value_counts()

    d["month_artist"], d["month_artist_n"] = counts.index[0], int(counts.iloc[0])



    def plat(p):

        row = dev[(dev["year"] == d["last"]["year"]) & (dev["platform_family"] == p)]

        return None if row.empty else row.iloc[0]



    d["android"], d["windows"] = plat("android"), plat("windows")

    return d





# ---------------------------------------------------------------- charts

def finish(chart, height: int = 300):

    return (

        chart.properties(height=height, background="transparent")

        .configure_view(stroke=None)

        .configure_axis(grid=False, domainColor=C.RULE, tickColor=C.RULE, labelColor=C.MUTED, titleColor=C.MUTED,

                        labelFont=FONT, titleFont=FONT, labelFontSize=12, titleFontSize=12)

        .configure_axisY(grid=True, gridColor=C.RULE, gridWidth=0.6, domain=False, ticks=False)

        .configure_legend(labelFont=FONT, titleFont=FONT, labelColor=C.MUTED, titleColor=C.MUTED, orient="top")

    )





def draw(chart) -> None:

    st.altair_chart(chart, width="stretch", theme=None)





def year_bars(yr: pd.DataFrame, field: str, last_year: int, fmt: str = ","):

    return finish(

        alt.Chart(yr)

        .mark_bar(cornerRadiusTopLeft=4, cornerRadiusTopRight=4, size=24)

        .encode(x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),

                y=alt.Y(f"{field}:Q", title=None),

                color=alt.condition(alt.datum.year == last_year, alt.value(C.SAGE), alt.value(C.SAGE_DARK)),

                tooltip=["year:O", alt.Tooltip(f"{field}:Q", format=fmt)]),

        height=260,

    )





def line_by_year(df: pd.DataFrame, field: str, fmt: str, color: str, pct: bool = False):

    axis = alt.Axis(format="%") if pct else alt.Axis()

    return finish(

        alt.Chart(df)

        .mark_line(point=alt.OverlayMarkDef(filled=True, size=60, color=color), color=color, strokeWidth=2.5)

        .encode(x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),

                y=alt.Y(f"{field}:Q", title=None, axis=axis, scale=alt.Scale(zero=True)),

                tooltip=["year:O", alt.Tooltip(f"{field}:Q", format=fmt)]),

        height=240,

    )





def hours_chart(months: pd.DataFrame):

    return finish(

        alt.Chart(months)

        .mark_area(color=C.SAGE, opacity=0.2, line={"color": C.SAGE, "strokeWidth": 2}, interpolate="monotone")

        .encode(x=alt.X("month:T", title=None), y=alt.Y("hours:Q", title=None),

                tooltip=[alt.Tooltip("month:T", format="%b %Y"), alt.Tooltip("hours:Q", format=".0f"),

                         "track_name", "artist"])

    )





def calendar_chart(daily: pd.DataFrame):

    cols = {c.lower(): c for c in daily.columns}

    date_col = next((cols[k] for k in ("date", "day", "d") if k in cols), None)

    val_col = next((cols[k] for k in ("streams", "plays", "qualified_streams", "hours", "minutes") if k in cols), None)

    if not date_col or not val_col:

        st.info(f"The calendar needs a date column and a count column. Found: {', '.join(daily.columns)}")

        return None

    df = daily[[date_col, val_col]].copy()

    df["date"] = pd.to_datetime(df[date_col])

    df = df.groupby("date", as_index=False)[val_col].sum()

    df["year"] = df["date"].dt.year

    df["dow"] = df["date"].dt.dayofweek

    start = df["date"].dt.to_period("Y").dt.start_time

    df["week"] = ((df["date"] - start).dt.days + start.dt.dayofweek) // 7

    top = float(df[val_col].quantile(0.98))

    return (

        alt.Chart(df)

        .mark_rect(stroke=C.CANVAS, strokeWidth=1.5, cornerRadius=2)

        .encode(

            x=alt.X("week:O", axis=None),

            y=alt.Y("dow:O", axis=None),

            color=alt.Color(f"{val_col}:Q", title=f"{val_col} per day",

                            scale=alt.Scale(domain=[0, top / 2, top], range=["#262C25", "#84977A", C.SAGE], clamp=True)),

            tooltip=[alt.Tooltip("date:T", format="%a %d %b %Y"), alt.Tooltip(f"{val_col}:Q")],

        )

        .properties(width=900, height=62)

        .facet(row=alt.Row("year:O", title=None,

                           header=alt.Header(labelColor=C.MUTED, labelFont=FONT, labelFontSize=12,

                                             labelAngle=0, labelOrient="left", labelAlign="left")),

               spacing=6)

        .configure_view(stroke=None)

        .configure(background="transparent")

        .configure_legend(labelFont=FONT, titleFont=FONT, labelColor=C.MUTED, titleColor=C.MUTED, orient="top")

    )





def busiest_hour_chart(night: pd.DataFrame):

    return finish(

        alt.Chart(night)

        .mark_circle(size=130, color=C.OCHRE)

        .encode(x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),

                y=alt.Y("peak_hour:Q", title=None, scale=alt.Scale(domain=[0, 24]),

                        axis=alt.Axis(values=[0, 6, 12, 18, 24],

                                      labelExpr="datum.value == 0 ? 'midnight' : datum.value == 12 ? 'noon' : "

                                                "datum.value == 24 ? '' : datum.value + ':00'")),

                tooltip=["year:O", alt.Tooltip("peak_hour:Q", title="busiest hour")]),

        height=240,

    )





def platform_chart(dev: pd.DataFrame):

    df = dev[dev["platform_family"].isin(["windows", "android", "ios"]) & (dev["streams"] >= 1000)].copy()

    df["minutes_per_play"] = df["hours"] * 60 / df["streams"]

    return finish(

        alt.Chart(df)

        .mark_line(point=alt.OverlayMarkDef(filled=True, size=50), strokeWidth=2.5)

        .encode(x=alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0)),

                y=alt.Y("minutes_per_play:Q", title=None),

                color=alt.Color("platform_family:N", title=None,

                                scale=alt.Scale(domain=["windows", "android", "ios"], range=[C.BLUE, C.SAGE, C.OCHRE])),

                tooltip=["year:O", "platform_family", alt.Tooltip("minutes_per_play:Q", format=".2f"),

                         alt.Tooltip("skip_rate:Q", format=".0%")]),

        height=240,

    )





def anthem_chart(anthems: pd.DataFrame):

    base = alt.Chart(anthems)

    x = alt.X("year:O", title=None, axis=alt.Axis(labelAngle=0))

    tip = ["year:O", "track_name", "artist", "plays"]

    stem = base.mark_rule(color=C.RULE, strokeWidth=3).encode(x=x, y=alt.Y("plays:Q", title=None), y2=alt.datum(0))

    dot = base.mark_circle(size=170, color=C.SAGE).encode(x=x, y="plays:Q", tooltip=tip)

    label = base.mark_text(dy=-16, color=C.TEXT, font=FONT, fontSize=12, fontWeight=600).encode(x=x, y="plays:Q", text="plays:Q")

    return finish(stem + dot + label, height=280)





def reunion_chart(reun: pd.DataFrame):

    df = reun.copy()

    df["left"] = pd.to_datetime(df["left_on"])

    df["back"] = pd.to_datetime(df["returned_on"])

    y = alt.Y("artist:N", sort=alt.EncodingSortField("gap_days", order="descending"), title=None)

    return finish(

        alt.Chart(df)

        .mark_bar(size=10, cornerRadius=5)

        .encode(x=alt.X("left:T", title=None), x2="back:T", y=y,

                color=alt.Color("plays_since_return:Q", title="plays since returning",

                                scale=alt.Scale(range=[C.OCHRE, C.SAGE])),

                tooltip=["artist", alt.Tooltip("left:T", title="left", format="%b %Y"),

                         alt.Tooltip("back:T", title="came back", format="%b %Y"),

                         "gap_days", "plays_before", "plays_since_return"]),

        height=480,

    )





def slow_chart(slow: pd.DataFrame):

    df = slow.copy()

    df["start"] = pd.to_datetime(df["first_heard"])

    df["end"] = df["start"] + pd.to_timedelta(df["days_until_first_real_listen"], unit="D")

    y = alt.Y("artist:N", sort=alt.EncodingSortField("days_until_first_real_listen", order="descending"), title=None)

    base = alt.Chart(df)

    tip = ["artist", alt.Tooltip("start:T", title="first heard", format="%b %Y"),

           alt.Tooltip("end:T", title="started listening", format="%b %Y"),

           "days_until_first_real_listen", "qualified_plays"]

    line = base.mark_rule(color=C.RULE, strokeWidth=4).encode(x=alt.X("start:T", title=None), x2="end:T", y=y)

    a = base.mark_circle(color=C.MUTED, size=80).encode(x="start:T", y=y, tooltip=tip)

    b = base.mark_circle(color=C.SAGE, size=100).encode(x="end:T", y=y, tooltip=tip)

    return finish(line + a + b, height=420)





# ---------------------------------------------------------------- layout helpers

def esc(x) -> str:

    return html.escape(str(x))





def chapter(headline: str, blurb: str) -> None:

    st.markdown(f'<div class="chapter"><h2>{esc(headline)}</h2><p>{esc(blurb)}</p></div>', unsafe_allow_html=True)





def figure(title: str, sub: str = "") -> None:

    s = f'<div class="s">{esc(sub)}</div>' if sub else ""

    st.markdown(f'<div class="fig"><div class="t">{esc(title)}</div>{s}</div>', unsafe_allow_html=True)





def note(text: str) -> None:

    st.markdown(f'<p class="note">{text}</p>', unsafe_allow_html=True)





def card(label: str, value: str, detail: str) -> str:

    return (f'<div class="card"><div class="k">{esc(label)}</div><div class="v">{esc(value)}</div>'

            f'<div class="d">{esc(detail)}</div></div>')





# ---------------------------------------------------------------- sections

def cover(d: dict, t: dict) -> None:

    left, right = st.columns([3, 2], gap="large")

    y0, y1 = int(d["first"]["year"]), int(d["last"]["year"])

    with left:

        st.markdown(

            '<div class="kicker">Playback Archive / personal Spotify archive</div>'

            '<div class="title">A decade in rotation.</div>'

            f'<div class="sub">A record of what stayed, what changed, and what found its way back, {y0}–{y1}. '

            '</div>',

            unsafe_allow_html=True,

        )

    with right:

        st.markdown(

            f'<div class="hero"><div class="l">Total recorded listening time</div><div class="v">{d["hours"]:,.0f} h</div>'

            f'<div class="n">Equivalent to about {d["hours"] / 24:,.0f} days of continuous playback.</div></div>',

            unsafe_allow_html=True,

        )



    s, n0, n1 = d["streak"], d["n0"], d["n1"]

    st.markdown(

        '<div class="strip">'

        + card("Total plays", f"{d['plays']:,.0f}", f"From {y0} to {y1}.")

        + card("Longest streak", f"{s['value']:,.0f} days",

               f"Listened every day, {str(s['start_date'])[:7]} to {str(s['end_date'])[:7]}.")

        + card("Skip rate", f"{d['first']['skip']:.0%} to {d['last']['skip']:.0%}", f"{y0} compared with {y1}.")

        + card("Late night", f"{n1['night_share'] / n0['night_share']:.1f}x",

               f"Share of plays at night, {int(n0['year'])} vs {int(n1['year'])}.")

        + "</div>",

        unsafe_allow_html=True,

    )





def takeaways(d: dict, t: dict) -> list[tuple[str, str]]:

    f, y0, y1 = t["facts"], int(d["first"]["year"]), int(d["last"]["year"])

    items = [

        (f"{d['first']['skip']:.0%} to {d['last']['skip']:.0%}", f"Skip rate, {y0} vs {y1}. You skip a lot less now."),

        (f"{d['first']['mpp']:.1f} to {d['last']['mpp']:.1f} min", "Average length of a play. Songs get more time before you move on."),

    ]

    best = d["peak_hours_year"]

    partial = " so far" if int(best["year"]) == y1 else ""

    items.append((f"{best['hours']:,.0f} h", f"{int(best['year'])} is your biggest year for listening time{partial}."))

    a, w = d["android"], d["windows"]

    if a is not None and w is not None:

        a_min, w_min = a["hours"] * 60 / a["streams"], w["hours"] * 60 / w["streams"]

        items.append((f"{a_min / w_min:.1f}x longer",

                      f"Plays on your phone last {a_min:.1f} min vs {w_min:.1f} min on Windows in {y1}. "

                      f"You skip {a['skip_rate']:.0%} on the phone and {w['skip_rate']:.0%} on Windows."))

    items.append((f"{int(f['one_week_wonders'])} tracks",

                  f"were played hard for one week and then dropped. That is {f['one_week_wonders_share_of_tracks']:.2%} of all tracks."))

    items.append((f"{int(f['weekend_weekday_top_artists_shared'])} artists",

                  f"are in both your weekday and weekend top lists. With shuffle on vs off, only "

                  f"{int(f['shuffle_on_off_top_artists_shared'])} overlap."))

    return items





def overview(d: dict, t: dict) -> None:

    last = int(d["last"]["year"])

    chapter("The short version", "Patterns that emerge across the full archive.")

    cards = "".join(card("", big, text).replace('<div class="k"></div>', "") for big, text in takeaways(d, t))

    st.markdown(f'<div class="take">{cards}</div>', unsafe_allow_html=True)



    left, right = st.columns(2, gap="large")

    with left:

        figure("Plays per year", f"{last} is not finished yet.")

        draw(year_bars(d["yr"], "streams", last))

    with right:

        figure("Hours per year", "More hours, with fewer plays. Each play is longer.")

        draw(year_bars(d["yr"], "hours", last, ",.0f"))



    c = d["comeback"]

    figure("Biggest comeback")

    st.markdown(

        f'<div class="feature"><div class="a">{esc(c["artist"])}</div>'

        f'<div class="m">Stopped listening in <b>{esc(str(c["left_on"])[:7])}</b> after <b>{c["plays_before"]:.0f}</b> plays.<br>'

        f'Away for <b>{c["gap_days"]:.0f} days</b>.<br>'

        f'Came back in <b>{esc(str(c["returned_on"])[:7])}</b> and played them <b>{c["plays_since_return"]:.0f}</b> times since.</div></div>',

        unsafe_allow_html=True,

    )





def timeline(d: dict, t: dict) -> None:

    pm = d["peak_month"]

    chapter(f"{int(d['peak_plays_year']['year'])} had the most plays",

            f"{int(d['peak_plays_year']['streams']):,} plays in one year. The calendar below shows every day.")

    figure("Daily listening", "Each square represents one day. Brighter means more plays; empty means none recorded.")

    if t["daily"] is not None:

        cal = calendar_chart(t["daily"])

        if cal is not None:

            st.altair_chart(cal, width="content", theme=None)

    else:

        st.info("The daily table is missing from data/public.")



    figure("Hours per month",

           f"Busiest month: {pm['month']:%B %Y}, {pm['hours']:.0f} hours. Hover to see the top track of each month.")

    draw(hours_chart(d["months"]))



    note(f"<b>{esc(d['month_artist'])}</b> had the top track in <b>{d['month_artist_n']}</b> different months, "

         "more than any other artist.")



    figure("Top track of each month", "Months with very little listening are left out.")

    m = d["months"].assign(month=d["months"]["month"].dt.strftime("%Y-%m"))

    st.dataframe(m[["month", "track_name", "artist", "track_plays", "hours"]].sort_values("month", ascending=False),

                 hide_index=True, width="stretch")





def habits(d: dict, t: dict) -> None:

    y0, y1 = int(d["first"]["year"]), int(d["last"]["year"])

    chapter(f"Skips went from {d['first']['skip']:.0%} to {d['last']['skip']:.0%}",

            "When you listen, where you listen, and how long each song gets.")



    left, right = st.columns(2, gap="large")

    with left:

        figure("Share of plays at night", "Plays during late-night hours, by year.")

        draw(line_by_year(t["night"], "night_share", ".1%", C.SAGE, pct=True))

    with right:

        figure("Busiest hour of the day", "The hour with the most plays, by year.")

        draw(busiest_hour_chart(t["night"]))

    day = t["night"][(t["night"]["peak_hour"] >= 6) & (t["night"]["peak_hour"] <= 17)]["year"].astype(int).tolist()

    if day:

        note(f"In <b>{', '.join(map(str, day))}</b> your busiest hour was during the day, not at night.")



    left, right = st.columns(2, gap="large")

    with left:

        figure("Skip rate by year", "Share of plays that were skipped.")

        draw(line_by_year(d["yr"], "skip", ".0%", C.OCHRE, pct=True))

    with right:

        figure("Minutes per play, by device", "How long a typical play lasts on each device.")

        draw(platform_chart(t["devices"]))



    a, w = d["android"], d["windows"]

    if a is not None and w is not None:

        note(f"In <b>{y1}</b> you skip <b>{a['skip_rate']:.0%}</b> of plays on your phone and "

             f"<b>{w['skip_rate']:.0%}</b> on Windows. On the computer you browse, on the phone you let songs play.")



    figure("Most played artists by time of day")

    rows = ""

    for part in ["morning", "afternoon", "evening", "night"]:

        sub = t["daypart"][t["daypart"]["daypart"] == part].sort_values("rank")

        if sub.empty:

            continue

        lines = "".join(f'<div class="r"><span>{int(r["rank"])}</span>{esc(r["artist"])}</div>' for _, r in sub.iterrows())

        rows += f'<div class="day"><div class="h">{part}</div>{lines}</div>'

    st.markdown(f'<div class="dayrow">{rows}</div>', unsafe_allow_html=True)

    leaders = t["daypart"][t["daypart"]["rank"] == 1]["artist"].value_counts()

    if leaders.iloc[0] == t["daypart"]["daypart"].nunique():

        note(f"<b>{esc(leaders.index[0])}</b> is your most played artist at every time of day.")





def favorites(d: dict, t: dict) -> None:

    a = d["anthem"]

    chapter(f"{a['track_name']} is the song of {int(a['year'])}",

            "Each year's most played track, plus the songs that burned out or flashed by.")

    figure("The song of each year", "Number of plays of the most played track. Hover for the name.")

    draw(anthem_chart(t["anthems"]))

    st.dataframe(t["anthems"].rename(columns={"first_date": "first played"}), hide_index=True, width="stretch")



    left, right = st.columns(2, gap="large")

    with left:

        figure("Frequently played, frequently skipped", "Tracks that accumulated plays despite a high skip rate.")

        love = t["love_hate"].assign(skip_rate=(t["love_hate"]["skip_rate"] * 100).round(1))

        st.dataframe(love[["track_name", "artist", "qualified_plays", "skips", "skip_rate"]],

                     hide_index=True, width="stretch")

    with right:

        figure("Brief, intense listening")

        st.dataframe(t["one_week_wonders"], hide_index=True, width="stretch")



    figure("Songs that burned out", "Peak week and how long the interest lasted.")

    st.dataframe(t["burnout"][["track_name", "artist", "peak_plays", "peak_week_start",

                               "sustained_halflife_wk", "is_censored"]],

                 hide_index=True, width="stretch")





def comebacks(d: dict, t: dict) -> None:

    c = d["comeback"]

    chapter(f"{c['artist']} came back after {c['gap_days']:.0f} days",

            "Artists you left for over a year and then returned to, and artists that took years to click.")

    figure("Artists you left and came back to", "Each bar is the time away. Color shows plays since returning.")

    draw(reunion_chart(t["reunions"]))

    figure("Artists that took years to click",

           "Grey dot is the first time you played them. Coral dot is when you started really listening.")

    draw(slow_chart(t["slow_burns"]))

    note("The first play of a slow burn may have been an accidental autoplay, so treat these gaps as an upper limit.")





def notes(d: dict, t: dict) -> None:

    chapter("How this was made", "Where the numbers come from and what to be careful about.")

    n_tables = len(list(DATA.glob("*.parquet")))

    st.markdown(

        f"""

- **Source:** my Spotify extended streaming history export, {int(d['first']['year'])} to {int(d['last']['year'])}.

- **Tables:** {n_tables} tables produced by the analysis code in `src/`.

- **Qualified plays:** some tables only count plays that pass a minimum rule. The exact rule is in `src/`.

- **Names:** track and artist names are shown as recorded.

- **Partial year:** {int(d['last']['year'])} is not finished.

        """

    )

    if t["skip_definitions"] is not None:

        figure("How a skip is defined", "Different definitions give different skip rates.")

        st.dataframe(t["skip_definitions"], hide_index=True, width="stretch")

    st.markdown(

        """

**Things to be careful about**



- The skip rate is around 70% in most years. A skip here probably means a short play, not dislike. Use it to compare, not as an absolute number.

- Listening sessions of 6 to 8 hours probably include paused or idle playback.

- Burnout half-life is one week for almost every track, so it is too coarse to rank tracks.

- Phone skip rates fell as phone use grew. The device and the behavior change together, so one does not prove the other.

        """

    )

    bounce = t["facts"].get("bounce_share_of_all_streams")

    if bounce is not None:

        st.caption(f"Bounce share of all plays: {bounce:.0%}. The bounce rule is defined in src/.")





# ---------------------------------------------------------------- main

def main() -> None:


    st.markdown(CSS, unsafe_allow_html=True)

    t = load_tables()

    d = derive(t)



    cover(d, t)

    names = ["Overview", "Timeline", "Habits", "Track archive", "Comebacks", "Explore", "Method notes"]

    for tab, render in zip(st.tabs(names), (overview, timeline, habits, favorites, comebacks, lambda d, t: render_explore(t, d), notes)):

        with tab:

            render(d, t)



    st.markdown('<div class="foot">Built from my Spotify extended streaming history. '

                '</div>', unsafe_allow_html=True)





main()