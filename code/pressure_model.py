"""Pressure reliability model for the SupeRR Selector, Round 1.

The question from the brief: which players have been most reliable under
pressure, so that Rajasthan Royals can back them at the IPL 2027 auction?

How the model answers it, in four steps:

1. Pressure index. Every delivery gets a score from 0 to 1 using only what
   was known before the ball was bowled (required rate, balls left, wickets
   in hand, par score, knockout). See add_pressure_index().
2. Expected outcome. For every delivery I work out what an average player
   would have produced in the same situation (format, innings, phase,
   wickets down, required-rate band, pace or spin). See fit_expectations().
3. Player value. On pressure balls, a batter's value is runs above that
   expectation and dismissals avoided; a bowler's value is runs saved and
   extra wickets. Values are shrunk towards zero for small samples. See
   player_table().
4. Composite index. Four z-scored parts (value, second part, pressure
   versus his own ordinary balls, worst-quarter match) are combined with
   fixed weights. See rank_players().

Run:  python pressure_model.py
Writes output/model.json and caches the scored balls in output/balls.pkl.
"""

from __future__ import annotations

import json

import numpy as np
import pandas as pd

import config as C

BOWLER_WICKETS = {"Caught", "Bowled", "LBW", "Stump", "Hit Wicket"}
NOT_LEGAL = {"wide", "Overstep", "other", "Penalty"}   # do not use up a ball
NOT_FACED = {"wide", "Penalty"}                        # batter did not face it
CHARGED_TO_BOWLER = {"wide", "Overstep", "other"}      # extras the bowler owns


def clip(values, low, high):
    return np.minimum(np.maximum(values, low), high)


# ---------------------------------------------------------------------------
# 1. Load the data pack and rebuild the match state before every ball
# ---------------------------------------------------------------------------

def load_matches() -> pd.DataFrame:
    comps = pd.read_csv(C.DATA_DIR / "competitions.csv")
    matches = pd.read_csv(C.DATA_DIR / "matches.csv")
    ipl_ids = set(comps.loc[comps.comp_name.str.startswith("IPL"), "comp_id"])
    matches = matches.merge(comps[["comp_id", "comp_name", "season"]], on="comp_id", how="left")
    matches["format"] = np.where(matches.comp_id.isin(ipl_ids), "IPL", "T20I")
    matches["year"] = pd.to_datetime(matches.match_date).dt.year
    no_result = matches["result"].fillna("").str.contains("No Result|Abandon", case=False)
    matches = matches[~no_result].copy()
    matches["knockout"] = (matches.knock_out.fillna(0).astype(int) == 1).astype(int)
    return matches


def load_balls() -> pd.DataFrame:
    """One row per delivery with the pre-ball match state attached."""
    matches = load_matches()
    columns = [
        "match_id", "innings", "overid", "innings_ball_num",
        "striker_id", "striker_name", "bowler_id", "bowler_name",
        "runs", "is_wicket", "dismissal_type", "dismissed_player_id",
        "extras_type", "extras1_runs", "extras_2_runs", "pace_or_spin",
    ]
    b = pd.read_csv(C.DATA_DIR / "ball_by_ball.csv", usecols=columns)
    b = b[b.innings.isin([1, 2])].copy()  # super overs are dropped
    b["is_wicket"] = b["is_wicket"].astype(str).str.lower().isin(["true", "1"])
    b["extras_type"] = b["extras_type"].fillna("").replace({"None": ""})
    for col in ("runs", "extras1_runs", "extras_2_runs"):
        b[col] = pd.to_numeric(b[col], errors="coerce").fillna(0.0)
    b["dismissed_player_id"] = pd.to_numeric(b["dismissed_player_id"], errors="coerce")

    extras = b["extras1_runs"] + b["extras_2_runs"]
    b["team_runs"] = b["runs"] + extras
    b["is_legal"] = ~b["extras_type"].isin(NOT_LEGAL)
    b["faced"] = ~b["extras_type"].isin(NOT_FACED)
    b["striker_out"] = b["is_wicket"] & (b["dismissed_player_id"] == b["striker_id"])
    b["bowler_wkt"] = b["is_wicket"] & b["dismissal_type"].isin(BOWLER_WICKETS)
    # Byes, leg-byes and penalty runs stay off the bowler's figures.
    b["bowler_runs"] = b["runs"] + np.where(b["extras_type"].isin(CHARGED_TO_BOWLER), extras, 0.0)
    b["bowl_type"] = np.where(b["pace_or_spin"].eq("Spin"), "Spin", "Pace")

    b = b.sort_values(["match_id", "innings", "innings_ball_num"], kind="mergesort")
    innings = b.groupby(["match_id", "innings"], sort=False)
    b["any_wkt"] = b["is_wicket"].astype(int)  # includes non-striker run-outs
    b["score_before"] = innings["team_runs"].cumsum() - b["team_runs"]
    b["wkts_before"] = innings["any_wkt"].cumsum() - b["any_wkt"]
    b["legal_before"] = innings["is_legal"].cumsum() - b["is_legal"].astype(int)

    keep = ["match_id", "format", "year", "knockout", "season",
            "first_inn_revised_overs", "second_inn_revised_overs", "revised_target",
            "venue_country", "stage"]
    b = b.merge(matches[keep], on="match_id", how="inner")

    first_total = (b.loc[b.innings.eq(1)].groupby("match_id", sort=False)["team_runs"]
                   .sum().rename("inn1_total"))
    b = b.merge(first_total, on="match_id", how="left")

    # The revised-overs columns are stored in balls (72 means 12 overs).
    # If only the first innings was revised, the chase uses the same limit.
    limit_1 = b["first_inn_revised_overs"].fillna(120).clip(lower=6, upper=120)
    limit_2 = (b["second_inn_revised_overs"].fillna(b["first_inn_revised_overs"])
               .fillna(120).clip(lower=6, upper=120))
    b["ball_limit"] = np.where(b.innings.eq(1), limit_1, limit_2)
    b["balls_left"] = (b["ball_limit"] - b["legal_before"]).clip(lower=1)
    b["wkts_left"] = (10 - b["wkts_before"]).clip(lower=0)

    b["target"] = b["revised_target"].where(b["revised_target"].notna(), b["inn1_total"] + 1)
    b["runs_needed"] = np.where(b.innings.eq(2), b["target"] - b["score_before"], np.nan)

    # Par for the team batting first = median score at that ball count.
    first_legal = b.loc[b.innings.eq(1) & b.is_legal, ["legal_before", "score_before"]]
    par = first_legal.groupby("legal_before")["score_before"].median()
    b["par_score"] = b["legal_before"].map(par)
    gap = (b["par_score"] - b["score_before"]) / 35.0
    b["below_par"] = np.where(b.innings.eq(1) & (b.legal_before >= 24),
                              clip(gap.fillna(0).to_numpy(), 0, 1), 0.0)
    return b


# ---------------------------------------------------------------------------
# 2. Pressure index
# ---------------------------------------------------------------------------

def add_pressure_index(b: pd.DataFrame,
                       pressure_threshold: float = C.PRESSURE_THRESHOLD,
                       ordinary_threshold: float = C.ORDINARY_THRESHOLD,
                       fade_lost_causes: bool = True) -> pd.DataFrame:
    """Score every ball from 0 (no pressure) to 1 (maximum pressure)."""
    b = b.copy()
    balls_left = b["balls_left"].to_numpy(dtype=float)
    ball_limit = b["ball_limit"].to_numpy(dtype=float)
    late = clip(1.0 - balls_left / np.maximum(ball_limit, 1.0), 0, 1)
    wkts_before = b["wkts_before"].to_numpy(dtype=float)
    wkts_left = b["wkts_left"].to_numpy(dtype=float)
    # Over number re-based so the last four overs of a shortened innings
    # still count as the death overs.
    over = b["overid"].to_numpy(dtype=float) + (20.0 - ball_limit / 6.0)
    is_chase = b["innings"].to_numpy() == 2
    runs_needed = b["runs_needed"].fillna(0).to_numpy(dtype=float)
    below_par = b["below_par"].to_numpy(dtype=float)
    knockout = b["knockout"].to_numpy(dtype=float)

    rrr = np.where(is_chase, runs_needed * 6.0 / balls_left, 0.0)
    rrr_stress = clip((rrr - 7.0) / 9.0, 0, 1)
    wkt_stress = clip((5.5 - wkts_left) / 5.5, 0, 1)
    pi = np.zeros(len(b), dtype=float)

    # Chasing side: required rate and wickets, both growing as the innings ends.
    alive = is_chase & (runs_needed > 0) & (wkts_left > 0)
    chase_score = (0.55 * rrr_stress * (0.30 + 0.70 * late)
                   + 0.25 * wkt_stress * (0.20 + 0.80 * late)
                   + 0.20 * rrr_stress * wkt_stress)
    pi = np.where(alive, chase_score, pi)

    # Situations every cricket fan would call pressure get a minimum score.
    chase_floors = [
        (alive & (balls_left <= 24) & (rrr >= 9) & (wkts_left <= 8), 0.58),           # last 4 overs, 9+ an over
        (alive & (balls_left <= 18) & (runs_needed <= 30) & (wkts_left <= 6), 0.72),  # finishing the game
        (alive & (wkts_left <= 3) & (balls_left <= 30), 0.68),                        # tail exposed
        (alive & (balls_left <= 60) & (balls_left > 24) & (rrr >= 12) & (wkts_left <= 7), 0.56),  # steep chase
        (alive & (balls_left <= 48) & (rrr >= 14) & (wkts_left >= 1), 0.60),          # very steep chase
        (alive & (over <= 6) & (wkts_left <= 5) & (rrr >= 10), 0.55),                 # powerplay collapse
    ]
    for condition, floor in chase_floors:
        pi = np.where(condition, np.maximum(pi, floor), pi)

    # Side batting first: death overs, collapses and scores below par.
    setting = ~is_chase & (wkts_left > 0)
    death = np.where(over >= 17, 1.0, np.where(over >= 15, 0.55, np.where(over >= 13, 0.15, 0.0)))
    collapse = clip((wkts_before - 2.0) / 6.0, 0, 1)
    setting_score = (0.50 * death * (0.35 + 0.65 * np.maximum(collapse, below_par))
                     + 0.30 * collapse * (0.25 + 0.75 * death)
                     + 0.20 * below_par * (0.30 + 0.70 * death))
    pi = np.where(setting, setting_score, pi)
    setting_floors = [
        (setting & (wkts_before >= 5) & (over >= 7) & (below_par >= 0.35), 0.56),  # middle-overs collapse
        (setting & (wkts_before >= 7) & (over >= 12), 0.60),                       # late collapse
    ]
    for condition, floor in setting_floors:
        pi = np.where(condition, np.maximum(pi, floor), pi)

    # A hopeless chase is slogging, not pressure: fade from RRR 15 to 0 at 21.
    if fade_lost_causes:
        fade = clip(1.0 - (rrr - 15.0) / 6.0, 0, 1)
        pi = np.where(is_chase, pi * fade, pi)
    pi = np.where(knockout == 1, np.minimum(1.0, pi * 1.12 + 0.04), pi)
    pi = np.where(is_chase & (runs_needed <= 0), 0.0, pi)  # chase already won
    pi = np.where(wkts_left <= 0, 0.0, pi)

    b["rrr"] = np.where(is_chase, rrr, np.nan)
    b["pi"] = clip(pi, 0, 1)
    b["band"] = np.where(b["pi"] >= pressure_threshold, "pressure",
                         np.where(b["pi"] <= ordinary_threshold, "ordinary", "middle"))
    return b


# ---------------------------------------------------------------------------
# 3. Expected outcome for every ball
# ---------------------------------------------------------------------------

def phase_of(over: pd.Series) -> pd.Series:
    return pd.cut(over, bins=[0, 6, 12, 16, 20], labels=["PP", "MID", "LATE", "DEATH"],
                  include_lowest=True).astype(str)


def wicket_bucket(wkts: pd.Series) -> pd.Series:
    return pd.cut(wkts, bins=[-1, 1, 3, 5, 7, 10],
                  labels=["0-1", "2-3", "4-5", "6-7", "8-10"]).astype(str)


def rrr_bucket(b: pd.DataFrame) -> pd.Series:
    r = b["rrr"]
    chase = b.innings.eq(2)
    out = pd.Series(np.where(b.innings.eq(1), "set", "na"), index=b.index)
    out.loc[chase & (r < 7)] = "<7"
    out.loc[chase & (r >= 7) & (r < 9)] = "7-9"
    out.loc[chase & (r >= 9) & (r < 11)] = "9-11"
    out.loc[chase & (r >= 11) & (r < 14)] = "11-14"
    out.loc[chase & (r >= 14)] = "14+"
    return out


# From the finest cell to the coarsest. A ball uses the first cell that has
# at least MIN_CELL_BALLS balls in it.
CELL_LADDER = [
    ["format", "innings", "phase", "wkt_bucket", "rrr_bucket", "bowl_type"],
    ["format", "innings", "phase", "wkt_bucket", "rrr_bucket"],
    ["format", "innings", "phase", "wkt_bucket"],
    ["innings", "phase", "wkt_bucket"],
]


def _cell_means(frame: pd.DataFrame, targets: dict) -> pd.DataFrame:
    """Average of each target column in the finest cell with enough balls."""
    result = pd.DataFrame(np.nan, index=frame.index, columns=list(targets))
    for keys in CELL_LADDER:
        agg = {"n": (next(iter(targets.values())), "size")}
        agg.update({name: (col, "mean") for name, col in targets.items()})
        stats = frame.groupby(keys, observed=True).agg(**agg)
        stats = stats[stats["n"] >= C.MIN_CELL_BALLS]
        filled = frame[keys].merge(stats[list(targets)], left_on=keys, right_index=True, how="left")
        for name in targets:
            result[name] = result[name].fillna(pd.Series(filled[name].to_numpy(), index=frame.index))
    for name, col in targets.items():
        result[name] = result[name].fillna(frame[col].mean())
    return result


def fit_expectations(b: pd.DataFrame) -> pd.DataFrame:
    """Attach expected runs/outs (batting) and expected runs/wickets (bowling)."""
    b = b.copy()
    b["phase"] = phase_of(b["overid"])
    b["wkt_bucket"] = wicket_bucket(b["wkts_before"])
    b["rrr_bucket"] = rrr_bucket(b)

    # Batting expectations use balls faced; bowling uses every delivery,
    # because wides are part of what a bowler gives away.
    faced = b.loc[b["faced"]]
    bat_exp = _cell_means(faced, {"exp_runs": "runs", "exp_out": "striker_out"})
    bowl_exp = _cell_means(b, {"exp_conc": "bowler_runs", "exp_wkt": "bowler_wkt"})

    b["exp_runs"] = bat_exp["exp_runs"].reindex(b.index)
    b["exp_out"] = bat_exp["exp_out"].reindex(b.index)
    b["exp_conc"] = bowl_exp["exp_conc"]
    b["exp_wkt"] = bowl_exp["exp_wkt"]
    b["rae"] = np.where(b["faced"], b["runs"] - b["exp_runs"], np.nan)                       # runs above expected
    b["wbe"] = np.where(b["faced"], b["exp_out"] - b["striker_out"].astype(float), np.nan)   # outs avoided
    b["econ_resid"] = b["exp_conc"] - b["bowler_runs"]                                       # runs saved
    b["wkt_resid"] = b["bowler_wkt"].astype(float) - b["exp_wkt"]                            # extra wickets
    b["w"] = b["year"].map(C.RECENCY_WEIGHTS).fillna(1.0)
    return b


def prepare_balls(**pressure_kwargs) -> pd.DataFrame:
    """Load, score and baseline every ball. Keyword args go to add_pressure_index."""
    return fit_expectations(add_pressure_index(load_balls(), **pressure_kwargs))


# ---------------------------------------------------------------------------
# 4. Player tables
# ---------------------------------------------------------------------------

def weighted_mean(values, weights) -> float:
    ok = np.isfinite(values) & np.isfinite(weights)
    if ok.sum() == 0 or weights[ok].sum() == 0:
        return np.nan
    return float(np.average(values[ok], weights=weights[ok]))


def shrink(value: float, n: float, prior: float) -> float:
    """Pull a value towards zero when it rests on a small sample."""
    if not np.isfinite(value) or n <= 0:
        return 0.0
    return float(n / (n + prior) * value)


def _or_zero(x: float) -> float:
    return x if np.isfinite(x) else 0.0


def _batting_row(g: pd.DataFrame, pressure: pd.DataFrame, ordinary: pd.DataFrame) -> dict:
    w_p = pressure["w"].to_numpy()
    balls = float(len(pressure))
    runs = float(pressure["runs"].sum())
    outs = float(pressure["striker_out"].sum())
    exp_runs = float(pressure["exp_runs"].sum()) if len(pressure) else 0.0
    runs_above = weighted_mean(pressure["rae"].to_numpy(), w_p)
    outs_avoided = weighted_mean(pressure["wbe"].to_numpy(), w_p)
    ordinary_value = (weighted_mean(ordinary["rae"].to_numpy(), ordinary["w"].to_numpy())
                      if len(ordinary) else np.nan)
    match_values = [weighted_mean(m["rae"].to_numpy(), m["w"].to_numpy())
                    for _, m in pressure.groupby("match_id") if len(m) >= 6]
    n_ord = float(len(ordinary))
    return dict(
        balls_pressure=balls,
        balls_ordinary=n_ord,
        weighted_balls=float(pressure["w"].sum()),
        recent_balls=float((pressure["year"] >= C.RECENT_FROM_YEAR).sum()),
        ipl_balls=float((pressure["format"] == "IPL").sum()),
        value=runs_above, second=outs_avoided, value_ordinary=ordinary_value,
        delta=runs_above - ordinary_value if np.isfinite(runs_above) and np.isfinite(ordinary_value) else np.nan,
        match_values=match_values,
        runs=runs, outs=outs,
        sr=100.0 * runs / balls if balls else np.nan,
        exp_sr=100.0 * exp_runs / balls if balls else np.nan,
        avg=runs / outs if outs else np.nan,
        sr_ordinary=100.0 * float(ordinary["runs"].sum()) / n_ord if n_ord else np.nan,
        rae_per_100=runs_above * 100 if np.isfinite(runs_above) else np.nan,
    )


def _bowling_row(g: pd.DataFrame, pressure: pd.DataFrame, ordinary: pd.DataFrame) -> dict:
    legal = pressure["is_legal"]
    w_p = pressure["w"].to_numpy()
    balls = float(legal.sum())
    conceded = float(pressure["bowler_runs"].sum())
    wickets = float(pressure["bowler_wkt"].sum())
    exp_conc = float(pressure["exp_conc"].sum()) if len(pressure) else 0.0
    runs_saved = weighted_mean(pressure["econ_resid"].to_numpy(), w_p)
    extra_wkts = weighted_mean(pressure["wkt_resid"].to_numpy(), w_p)
    if len(ordinary):
        w_o = ordinary["w"].to_numpy()
        ord_saved = weighted_mean(ordinary["econ_resid"].to_numpy(), w_o)
        ord_wkts = weighted_mean(ordinary["wkt_resid"].to_numpy(), w_o)
    else:
        ord_saved = ord_wkts = np.nan
    # The pressure-vs-ordinary comparison uses the whole spell value
    # (runs saved plus ten runs for every extra wicket).
    spell_pressure = _or_zero(runs_saved) + C.RUNS_PER_WICKET * _or_zero(extra_wkts)
    spell_ordinary = (ord_saved + C.RUNS_PER_WICKET * ord_wkts
                      if np.isfinite(ord_saved) and np.isfinite(ord_wkts) else np.nan)
    match_values = []
    for _, m in pressure.groupby("match_id"):
        if m["is_legal"].sum() < 6:
            continue
        saved = weighted_mean(m["econ_resid"].to_numpy(), m["w"].to_numpy())
        extra = weighted_mean(m["wkt_resid"].to_numpy(), m["w"].to_numpy())
        if np.isfinite(saved) and np.isfinite(extra):
            match_values.append(saved + C.RUNS_PER_WICKET * extra)
    return dict(
        balls_pressure=balls,
        balls_ordinary=float(ordinary["is_legal"].sum()),
        weighted_balls=float(pressure.loc[legal, "w"].sum()),
        ordinary_weight=float(ordinary["w"].sum()),
        recent_balls=float(((pressure["year"] >= C.RECENT_FROM_YEAR) & legal).sum()),
        ipl_balls=float(((pressure["format"] == "IPL") & legal).sum()),
        value=runs_saved, second=extra_wkts, value_ordinary=ord_saved,
        delta=(spell_pressure - spell_ordinary
               if np.isfinite(runs_saved) and np.isfinite(spell_ordinary) else np.nan),
        match_values=match_values,
        runs_conceded=conceded, wickets=wickets,
        economy=conceded / balls * 6 if balls else np.nan,
        exp_economy=exp_conc / balls * 6 if balls else np.nan,
        spell_value_per_24=spell_pressure * 24,
    )


def player_table(b: pd.DataFrame, kind: str) -> pd.DataFrame:
    """One row per batter (kind='bat') or bowler (kind='bowl') with shrunk values."""
    if kind == "bat":
        d = b.loc[b["faced"]]
        id_col, name_col, prior, build = "striker_id", "striker_name", C.BAT_PRIOR_BALLS, _batting_row
    else:
        d = b
        id_col, name_col, prior, build = "bowler_id", "bowler_name", C.BOWL_PRIOR_BALLS, _bowling_row

    names = d.groupby(id_col)[name_col].agg(lambda s: s.mode().iloc[0] if len(s.mode()) else s.iloc[0])

    rows = []
    for pid, g in d.groupby(id_col, sort=False):
        pressure = g[g.band.eq("pressure")]
        ordinary = g[g.band.eq("ordinary")]
        r = build(g, pressure, ordinary)
        n = r["weighted_balls"]
        ordinary_n = r.pop("ordinary_weight", None)
        if ordinary_n is None:
            ordinary_n = float(ordinary["w"].sum())

        ms = np.array([v for v in r.pop("match_values") if np.isfinite(v)], dtype=float)
        p25 = float(np.percentile(ms, 25)) if len(ms) else np.nan
        positive = float(np.mean(ms > 0)) if len(ms) else np.nan

        r.update(
            player_id=int(pid),
            name=names.loc[pid],
            matches_pressure=int(pressure["match_id"].nunique()),
            matches_for_floor=int(len(ms)),
            t20i_balls=r["balls_pressure"] - r["ipl_balls"],
            shrunk_value=shrink(_or_zero(r["value"]), n, prior),
            shrunk_second=shrink(_or_zero(r["second"]), n, prior),
            # A player with few ordinary balls (a pure finisher) is not
            # punished for having no quiet-phase baseline.
            shrunk_delta=shrink(_or_zero(r["delta"]), min(n, ordinary_n), prior),
            floor=shrink(_or_zero(p25), len(ms), C.FLOOR_PRIOR_MATCHES),
            positive_share=positive if np.isfinite(positive) else None,
            last_year=int(g["year"].max()),
            first_year=int(g["year"].min()),
        )
        rows.append(r)
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# 5. Sample rules and composite index
# ---------------------------------------------------------------------------

def zscore(s: pd.Series) -> pd.Series:
    x = s.astype(float)
    mu, sd = x.mean(), x.std(ddof=0)
    if not np.isfinite(sd) or sd < 1e-9:
        return pd.Series(np.zeros(len(s)), index=s.index)
    return ((x - mu) / sd).clip(-3, 3)


def min_pressure_balls(ipl_balls, t20i_balls, scale: float = 1.0):
    """Players with evidence from only one competition need a longer record."""
    few_ipl = np.asarray(ipl_balls) < C.FORMAT_EVIDENCE_BALLS
    few_t20i = np.asarray(t20i_balls) < C.FORMAT_EVIDENCE_BALLS
    base = np.where(few_ipl, C.MIN_BALLS_T20I_ONLY,
                    np.where(few_t20i, C.MIN_BALLS_IPL_ONLY, C.MIN_BALLS_BOTH_FORMATS))
    return base * scale


def eligible(df: pd.DataFrame, scale: float = 1.0) -> pd.Series:
    """Sample rules only. Nothing here looks at how well the player did.

    `scale` loosens or tightens the pressure-ball minimums (used in the
    robustness check); the match and recent-ball rules stay fixed.
    """
    return ((df.balls_pressure >= min_pressure_balls(df.ipl_balls, df.t20i_balls, scale))
            & (df.matches_for_floor >= C.MIN_FLOOR_MATCHES)
            & (df.recent_balls >= C.MIN_RECENT_BALLS)
            & (df.last_year >= C.MIN_LAST_YEAR))


def rank_table(df: pd.DataFrame, weights, scale: float = 1.0) -> pd.DataFrame:
    elig = df[eligible(df, scale)].copy()
    parts = ["shrunk_value", "shrunk_second", "shrunk_delta", "floor"]
    zcols = ["z_value", "z_second", "z_delta", "z_floor"]
    for part, z in zip(parts, zcols):
        elig[z] = zscore(elig[part])
    elig["index_z"] = sum(w * elig[z] for w, z in zip(weights, zcols))
    elig["index"] = (50 + 12 * elig["index_z"]).clip(0, 100)
    elig = elig.sort_values(["index_z", "shrunk_value"], ascending=False)
    elig["rank"] = np.arange(1, len(elig) + 1)
    return elig


def rank_players(b: pd.DataFrame, bat_weights=C.BAT_WEIGHTS, bowl_weights=C.BOWL_WEIGHTS,
                 scale: float = 1.0):
    """Return (batters, bowlers) ranked tables for a set of scored balls."""
    return (rank_table(player_table(b, "bat"), bat_weights, scale),
            rank_table(player_table(b, "bowl"), bowl_weights, scale))


def gate_reason(row) -> str:
    """Plain-English list of the sample rules a player does not meet."""
    need = int(min_pressure_balls([row.ipl_balls], [row.t20i_balls])[0])
    reasons = []
    if row.balls_pressure < need:
        reasons.append(f"{int(row.balls_pressure)} pressure balls, needs {need}")
    if row.matches_for_floor < C.MIN_FLOOR_MATCHES:
        reasons.append(f"{int(row.matches_for_floor)} matches with 6+ pressure balls, needs {C.MIN_FLOOR_MATCHES}")
    if row.recent_balls < C.MIN_RECENT_BALLS:
        reasons.append(f"{int(row.recent_balls)} pressure balls in 2025-26, needs {C.MIN_RECENT_BALLS}")
    if row.last_year < C.MIN_LAST_YEAR:
        reasons.append("no matches in 2025-26")
    return "Meets every sample rule" if not reasons else "; ".join(reasons)


# ---------------------------------------------------------------------------
# 6. Nationality (from the T20I sides a player appears for)
# ---------------------------------------------------------------------------

def nationalities() -> dict:
    comps = pd.read_csv(C.DATA_DIR / "competitions.csv")
    mapping = pd.read_csv(C.DATA_DIR / "competition_team_player_mapping.csv")
    ipl_ids = set(comps.loc[comps.comp_name.str.startswith("IPL"), "comp_id"])
    intl = mapping.loc[~mapping.comp_id.isin(ipl_ids), ["player_id", "team_name"]].drop_duplicates()
    return {int(pid): sorted(set(g.team_name)) for pid, g in intl.groupby("player_id")}


def primary_nation(teams: list) -> str:
    if not teams:
        return "IPL only"
    if any(t == "India" or t.startswith("India ") for t in teams):
        return "India"
    senior = [t for t in teams if not t.endswith(" A")] or teams
    return senior[0] if len(senior) == 1 else ", ".join(senior[:3])


# ---------------------------------------------------------------------------
# Main: write the full model output
# ---------------------------------------------------------------------------

def _clean(value, digits=None):
    """Make numpy/pandas values JSON friendly."""
    if value is None or (isinstance(value, float) and not np.isfinite(value)):
        return None
    if isinstance(value, (np.integer,)):
        return int(value)
    if isinstance(value, (float, np.floating)):
        return round(float(value), digits) if digits is not None else float(value)
    return value


def player_record(row, nations: dict, kind: str) -> dict:
    rec = {
        "rank": int(row["rank"]) if "rank" in row and pd.notna(row["rank"]) else None,
        "player_id": int(row.player_id),
        "name": row["name"],
        "nation": primary_nation(nations.get(int(row.player_id), [])),
        "balls_pressure": int(row.balls_pressure),
        "balls_ordinary": int(row.balls_ordinary),
        "ipl_balls": int(row.ipl_balls),
        "t20i_balls": int(max(row.t20i_balls, 0)),
        "matches_pressure": int(row.matches_pressure),
        "matches_for_floor": int(row.matches_for_floor),
        "recent_balls": int(row.recent_balls),
        "positive_share": _clean(row.positive_share, 3),
        "delta": _clean(row.delta, 4),
        "shrunk_value": _clean(row.shrunk_value, 6),
        "last_year": int(row.last_year),
    }
    for z in ("index", "index_z", "z_value", "z_second", "z_delta", "z_floor"):
        if z in row:
            rec[z] = _clean(row[z], 3 if z == "index_z" else (1 if z == "index" else 2))
    if kind == "bat":
        rec.update(runs=int(row.runs), outs=int(row.outs), sr=_clean(row.sr, 1),
                   exp_sr=_clean(row.exp_sr, 1), avg=_clean(row.avg, 1),
                   sr_ordinary=_clean(row.sr_ordinary, 1), rae_per_100=_clean(row.rae_per_100, 1))
    else:
        rec.update(runs_conceded=int(row.runs_conceded), wickets=int(row.wickets),
                   economy=_clean(row.economy, 2), exp_economy=_clean(row.exp_economy, 2),
                   spell_value_per_24=_clean(row.spell_value_per_24, 2))
    return rec


def squad_summary(bat_all, bowl_all, bat, bowl, nations) -> list:
    """How the current RR squad looks through the pressure lens."""
    out = []
    for name, pid, role, country, note in C.RR_SQUAD:
        entry = {"name": name, "player_id": pid, "role": role, "country": country, "note": note}
        for kind, all_rows, ranked in (("bat", bat_all, bat), ("bowl", bowl_all, bowl)):
            hit = all_rows[all_rows.player_id == pid]
            rank_hit = ranked[ranked.player_id == pid]
            entry[f"{kind}_rank"] = int(rank_hit["rank"].iloc[0]) if len(rank_hit) else None
            if len(hit) and hit.balls_pressure.iloc[0] > 0:
                row = hit.iloc[0]
                block = {"balls": int(row.balls_pressure), "reason": gate_reason(row),
                         "positive_share": _clean(row.positive_share, 3)}
                if kind == "bat" and pd.notna(row.sr):
                    block.update(sr=_clean(row.sr, 1), exp_sr=_clean(row.exp_sr, 1))
                if kind == "bowl" and row.balls_pressure >= 12 and pd.notna(row.economy):
                    block.update(econ=_clean(row.economy, 2), exp_econ=_clean(row.exp_economy, 2),
                                 wickets=int(row.wickets))
                entry[kind] = block
        out.append(entry)
    return out


def choke_list(ranked: pd.DataFrame, nations: dict, kind: str, n: int = 8) -> list:
    """Eligible players outside the top 10 who drop furthest below their ordinary level."""
    x = ranked.dropna(subset=["delta"])
    x = x[(x["rank"] > C.TOP_N) & (x["balls_ordinary"] >= 80) & (x["delta"] < 0)]
    return [player_record(r, nations, kind) for _, r in x.sort_values("delta").head(n).iterrows()]


def situation_summary(b: pd.DataFrame, bat: pd.DataFrame, bowl: pd.DataFrame) -> dict:
    band = b["band"]
    return {
        "balls": int(len(b)),
        "pressure_balls": int((band == "pressure").sum()),
        "ordinary_balls": int((band == "ordinary").sum()),
        "middle_balls": int((band == "middle").sum()),
        "pressure_share": round(float((band == "pressure").mean()), 4),
        "matches": int(b.match_id.nunique()),
        "ipl_matches": int(b.loc[b.format.eq("IPL"), "match_id"].nunique()),
        "t20i_matches": int(b.loc[b.format.eq("T20I"), "match_id"].nunique()),
        "eligible_batters": int(len(bat)),
        "eligible_bowlers": int(len(bowl)),
    }


def main():
    C.OUTPUT_DIR.mkdir(exist_ok=True)
    print("Loading and scoring every ball ...")
    b = prepare_balls()
    b.to_pickle(C.OUTPUT_DIR / "balls.pkl")

    bat_all, bowl_all = player_table(b, "bat"), player_table(b, "bowl")
    bat = rank_table(bat_all, C.BAT_WEIGHTS)
    bowl = rank_table(bowl_all, C.BOWL_WEIGHTS)
    bat_all.to_pickle(C.OUTPUT_DIR / "batters_all.pkl")
    bowl_all.to_pickle(C.OUTPUT_DIR / "bowlers_all.pkl")
    nations = nationalities()

    payload = {
        "situation": situation_summary(b, bat, bowl),
        "batters": [player_record(r, nations, "bat") for _, r in bat.iterrows()],
        "bowlers": [player_record(r, nations, "bowl") for _, r in bowl.iterrows()],
        "squad": squad_summary(bat_all, bowl_all, bat, bowl, nations),
        "choke_bat": choke_list(bat, nations, "bat"),
        "choke_bowl": choke_list(bowl, nations, "bowl"),
        "settings": {
            "bat_weights": C.BAT_WEIGHTS, "bowl_weights": C.BOWL_WEIGHTS,
            "runs_per_wicket": C.RUNS_PER_WICKET, "recency": C.RECENCY_WEIGHTS,
            "bat_prior_balls": C.BAT_PRIOR_BALLS, "bowl_prior_balls": C.BOWL_PRIOR_BALLS,
            "pressure_threshold": C.PRESSURE_THRESHOLD, "ordinary_threshold": C.ORDINARY_THRESHOLD,
        },
    }
    (C.OUTPUT_DIR / "model.json").write_text(json.dumps(payload, indent=1))

    print(f"{payload['situation']['pressure_balls']:,} pressure balls in "
          f"{payload['situation']['matches']} matches; "
          f"{len(bat)} batters and {len(bowl)} bowlers meet the sample rules.")
    for label, table in (("Batters", bat), ("Bowlers", bowl)):
        print(f"\n{label} (single-run order, before the bootstrap):")
        for _, r in table.head(12).iterrows():
            print(f"  {int(r['rank']):>2}  {r['name']:<26} index {r['index']:.1f}")


if __name__ == "__main__":
    main()
