"""Collect everything the report and dashboard need into one JSON file.

Inputs:  output/balls.pkl, output/model.json, output/robustness.json
Outputs: output/report_data.json
         output/rankings_batters.csv, output/rankings_bowlers.csv

Run:  python build_report_data.py
"""

from __future__ import annotations

import csv
import json

import numpy as np
import pandas as pd

import auction_context as A
import config as C
import pressure_model as M
from robustness import VARIANTS, VARIANT_LABELS


def band_stats(b: pd.DataFrame) -> dict:
    """Batting and bowling averages on ordinary, middle and pressure balls."""
    faced = b[b.faced]
    out = {}
    for band in ("ordinary", "middle", "pressure"):
        bat, all_balls = faced[faced.band == band], b[b.band == band]
        out[band] = dict(
            balls=int(len(all_balls)),
            share=round(len(all_balls) / len(b), 4),
            sr=round(100 * bat.runs.mean(), 1),
            dismissal_pct=round(100 * bat.striker_out.mean(), 2),
            dot_pct=round(100 * (bat.runs == 0).mean(), 1),
            econ=round(6 * all_balls.bowler_runs.sum() / all_balls.is_legal.sum(), 2),
        )
    return out


def with_result(b: pd.DataFrame) -> pd.DataFrame:
    """Attach batting team, bowling team, winner and date to every ball."""
    extra = pd.read_csv(C.DATA_DIR / "ball_by_ball.csv",
                        usecols=["match_id", "innings", "innings_ball_num", "batting_team_id", "bowling_team_id"])
    matches = pd.read_csv(C.DATA_DIR / "matches.csv")[["match_id", "win_team_id", "match_date"]]
    return (b.merge(extra, on=["match_id", "innings", "innings_ball_num"], how="left")
             .merge(matches, on="match_id", how="left"))


def chase_profile(balls_with_result: pd.DataFrame) -> dict:
    chase = balls_with_result[(balls_with_result.band == "pressure") & (balls_with_result.innings == 2)]
    won = chase.batting_team_id == chase.win_team_id
    steep = chase.rrr >= 18
    return dict(n=int(len(chase)), median_rrr=round(float(chase.rrr.median()), 2),
                share_rrr18=round(float(steep.mean()), 3), chase_win_rate=round(float(won.mean()), 3),
                win_rate_rrr18=round(float(won[steep].mean()), 3) if steep.any() else None)


def match_series(bx: pd.DataFrame, teams: dict, pid: int, kind: str) -> list:
    """Every match where the player had pressure balls, oldest first."""
    rows = []
    if kind == "bat":
        g = bx[(bx.striker_id == pid) & bx.faced & (bx.band == "pressure")]
        for _, m in g.groupby("match_id"):
            rows.append(dict(date=str(m.match_date.iloc[0]), fmt=m.format.iloc[0],
                             opp=teams.get(m.bowling_team_id.iloc[0], ""), balls=int(len(m)),
                             runs=int(m.runs.sum()), exp=round(float(m.exp_runs.sum()), 1),
                             out=int(m.striker_out.sum()),
                             value=round(float((m.runs - m.exp_runs).sum()), 1)))
    else:
        g = bx[(bx.bowler_id == pid) & (bx.band == "pressure")]
        for _, m in g.groupby("match_id"):
            saved = (m.exp_conc - m.bowler_runs).sum() + C.RUNS_PER_WICKET * (m.bowler_wkt - m.exp_wkt).sum()
            rows.append(dict(date=str(m.match_date.iloc[0]), fmt=m.format.iloc[0],
                             opp=teams.get(m.batting_team_id.iloc[0], ""), balls=int(m.is_legal.sum()),
                             runs=int(m.bowler_runs.sum()), exp=round(float(m.exp_conc.sum()), 1),
                             wkts=int(m.bowler_wkt.sum()), value=round(float(saved), 1)))
    return sorted(rows, key=lambda r: r["date"])


def player_snapshot(table: pd.DataFrame, name: str, kind: str) -> dict:
    """Pressure numbers for any player, whether or not he meets the sample rules."""
    r = table[table.name == name].iloc[0]
    snap = dict(name=name, kind=kind, player_id=int(r.player_id), pressure_balls=int(r.balls_pressure),
                ipl_balls=int(r.ipl_balls), matches=int(r.matches_pressure),
                positive=round(100 * r.positive_share) if pd.notna(r.positive_share) else None,
                rule=M.gate_reason(r))
    if kind == "bat":
        snap.update(sr=round(float(r.sr), 1), exp_sr=round(float(r.exp_sr), 1), outs=int(r.outs))
    else:
        snap.update(econ=round(float(r.economy), 2), exp_econ=round(float(r.exp_economy), 2),
                    wickets=int(r.wickets))
    return snap


def stability_table(rob: dict, model: dict, names: dict, kind: str, n: int = 18) -> list:
    """Bootstrap view of everyone who reaches the top 10 often, eligible or not."""
    boots = rob["bootstrap"]
    key = "batters" if kind == "bat" else "bowlers"
    eligible_ids = [r["player_id"] for r in model[key]]
    candidates = set(eligible_ids) | {int(p) for p in rob[f"regulars_{kind}"]}
    rows = []
    for pid in candidates:
        pos = [b[kind].index(pid) + 1 if pid in b[kind] else C.TOP_N + 1 for b in boots]
        rows.append(dict(name=names[kind].get(pid, str(pid)), player_id=pid,
                         expected_rank=round(float(np.mean(pos)), 2),
                         boot=round(100 * sum(p <= C.TOP_N for p in pos) / len(boots)),
                         eligible=pid in eligible_ids,
                         ranks={v: (rob["variants"][v][kind].index(pid) + 1
                                    if pid in rob["variants"][v][kind] else None) for v in VARIANTS}))
    rows.sort(key=lambda r: r["expected_rank"])
    return rows[:n]


def write_csv(rows: list, kind: str, path) -> None:
    common = ["final_rank", "name", "player_id", "nation", "index", "boot_top10_pct", "expected_rank",
              "variants_in_top10", "balls_pressure", "ipl_balls", "t20i_balls", "matches_pressure",
              "positive_matches_pct"]
    stats = ["sr", "exp_sr", "runs", "outs"] if kind == "bat" else ["economy", "exp_economy", "wickets"]
    columns = common + stats + ["status", "flag", "rr_fit"]
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(columns)
        for r in rows:
            values = {**r, "rr_fit": r["fit"], "positive_matches_pct": r["positive_pct"],
                      "variants_in_top10": f"{r['variants_in_top10']}/7"}
            writer.writerow(["" if values.get(c) is None else values.get(c) for c in columns])


def main():
    b = pd.read_pickle(C.OUTPUT_DIR / "balls.pkl")
    model = json.loads((C.OUTPUT_DIR / "model.json").read_text())
    rob = json.loads((C.OUTPUT_DIR / "robustness.json").read_text())
    final = json.loads((C.OUTPUT_DIR / "final_top10.json").read_text())
    bat_all = pd.read_pickle(C.OUTPUT_DIR / "batters_all.pkl")
    bowl_all = pd.read_pickle(C.OUTPUT_DIR / "bowlers_all.pkl")
    tables = {"bat": bat_all, "bowl": bowl_all}
    names = {k: dict(zip(t.player_id, t.name)) for k, t in tables.items()}
    teams = (pd.read_csv(C.DATA_DIR / "teams.csv").drop_duplicates("team_id")
             .set_index("team_id").team_name.to_dict())

    bx = with_result(b)
    no_fade = with_result(M.add_pressure_index(M.load_balls(), fade_lost_causes=False))
    ordinary_chase = bx[(bx.band == "ordinary") & (bx.innings == 2)]

    phase = pd.crosstab(b.phase, b.band, normalize="index").round(3)
    out = {
        "author": C.AUTHOR,
        "as_of": A.AS_OF,
        "situation": model["situation"],
        "settings": model["settings"],
        "band_stats": band_stats(b),
        "phase_band": {p: {k: float(phase.loc[p, k]) for k in phase.columns} for p in ["PP", "MID", "LATE", "DEATH"]},
        "pi_hist": np.histogram(b.pi, bins=20, range=(0, 1))[0].tolist(),
        "chase_pressure": chase_profile(bx),
        "chase_no_fade": chase_profile(no_fade),
        "chase_ordinary_win_rate": round(float((ordinary_chase.batting_team_id == ordinary_chase.win_team_id).mean()), 3),
        "split_half": rob["split_half"],
        "variant_labels": VARIANT_LABELS,
        "variants": VARIANTS,
        "variant_pool_sizes": {v: {k: len(rob["variants"][v][k]) for k in ("bat", "bowl")} for v in VARIANTS},
    }

    for key, kind in (("batters", "bat"), ("bowlers", "bowl")):
        rows = []
        for r in final[key]:
            pick = A.PICKS[r["name"]]
            rows.append({**r, **pick,
                         "positive_pct": round(100 * r["positive_share"]) if r["positive_share"] is not None else None,
                         "series": match_series(bx, teams, r["player_id"], kind)})
        out[key] = rows
        write_csv(rows, kind, C.OUTPUT_DIR / f"rankings_{key}.csv")
        out[f"stability_{kind}"] = stability_table(rob, model, names, kind)

    out["squad"] = model["squad"]
    out["choke_bat"] = [x["name"] for x in model["choke_bat"]]
    out["choke_bowl"] = [x["name"] for x in model["choke_bowl"]]

    lookups = {t["key"] for t in A.TARGETS} | {x["key"] for x in A.WATCH + A.AVOID + A.UNAVAILABLE}
    out["snapshots"] = {k: player_snapshot(tables[k.split("|")[1]], k.split("|")[0], k.split("|")[1])
                        for k in sorted(lookups)}

    order_rank = {k: {r["player_id"]: r["final_rank"] for r in rob[f"order_{k}"]} for k in ("bat", "bowl")}
    model_index = {k: {r["player_id"]: r["index"] for r in model["batters" if k == "bat" else "bowlers"]}
                   for k in ("bat", "bowl")}
    checked = []
    for item in A.CHECKED_NOT_PICKED:
        snap = player_snapshot(tables[item["kind"]], item["name"], item["kind"])
        pid = snap["player_id"]
        snap.update(reason=item["reason"], final_rank=order_rank[item["kind"]].get(pid),
                    index=model_index[item["kind"]].get(pid),
                    pool_size=len(order_rank[item["kind"]]))
        checked.append(snap)
    out["checked_not_picked"] = checked

    out["board"] = dict(targets=A.TARGETS, watch=A.WATCH, avoid=A.AVOID, unavailable=A.UNAVAILABLE,
                        purse_note=A.PURSE_NOTE, public_information=A.PUBLIC_INFORMATION)

    (C.OUTPUT_DIR / "report_data.json").write_text(json.dumps(out, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    print("Wrote report_data.json and the two rankings CSVs.")
    print("Chase pressure with fade:", out["chase_pressure"])
    print("Chase pressure without fade:", out["chase_no_fade"])


if __name__ == "__main__":
    main()
