"""How much should we trust the rankings?

Three checks, all written to output/robustness.json:

* Model variants. The ranking is re-run with one choice changed at a time:
  IPL balls only, equal weights, no recency weighting, pressure threshold
  0.50 and 0.60, and pressure-ball minimums loosened by 20%.
* Bootstrap. Matches are resampled with replacement 200 times (seeds 0-199)
  and the whole ranking is rebuilt each time. A player's stability is the
  share of resamples in which he finishes in the top 10.
* Split halves. Does a player's pressure value in one half of the data
  predict his value in the other half? Done for odd/even matches and for
  2022-24 against 2025-26.

The official order is the average bootstrap rank (a player outside the top
10 in a resample counts as 11th), among players who meet the sample rules
on the full data. Writes output/final_top10.json as well.

Run:  python robustness.py      (about 3-4 minutes with 4 worker processes)
"""

from __future__ import annotations

import json
from multiprocessing import Pool

import numpy as np
import pandas as pd

import config as C
import pressure_model as M

VARIANTS = ["primary", "ipl_only", "equal_weights", "recency_off",
            "pressure_t_0.5", "pressure_t_0.6", "sample_rules_0.8"]
VARIANT_LABELS = {
    "primary": "Main model", "ipl_only": "IPL balls only", "equal_weights": "Equal weights",
    "recency_off": "No recency weighting", "pressure_t_0.5": "Pressure from 0.50",
    "pressure_t_0.6": "Pressure from 0.60", "sample_rules_0.8": "Ball minimums -20%",
}


def ranked_ids(b: pd.DataFrame, **kwargs) -> dict:
    bat, bowl = M.rank_players(b, **kwargs)
    return {"bat": bat.player_id.tolist(), "bowl": bowl.player_id.tolist()}


def run_variants(base: pd.DataFrame) -> dict:
    no_recency = base.copy()
    no_recency["w"] = 1.0
    raw = M.load_balls()
    out = {
        "primary": ranked_ids(base),
        "ipl_only": ranked_ids(base.loc[base.format.eq("IPL")].copy()),
        "equal_weights": ranked_ids(base, bat_weights=(0.25,) * 4, bowl_weights=(0.25,) * 4),
        "recency_off": ranked_ids(no_recency),
        "sample_rules_0.8": ranked_ids(base, scale=0.8),
    }
    for threshold in (0.50, 0.60):
        balls = M.fit_expectations(M.add_pressure_index(raw, pressure_threshold=threshold))
        out[f"pressure_t_{threshold}"] = ranked_ids(balls)
    return out


# The bootstrap workers read these module-level globals (set before the
# pool forks) so the 200 MB ball table is not pickled for every task.
_BALLS: pd.DataFrame | None = None
_ROWS_BY_MATCH: dict | None = None


def one_bootstrap(seed: int) -> dict:
    rng = np.random.default_rng(seed)
    match_ids = _BALLS.match_id.unique()
    picked = rng.choice(match_ids, size=len(match_ids), replace=True)
    parts = [_ROWS_BY_MATCH[m] for m in picked]
    sample = _BALLS.iloc[np.concatenate(parts)].copy()
    # A match drawn twice becomes two separate matches.
    sample["match_id"] = np.repeat(np.arange(len(picked)), [len(p) for p in parts])
    ids = ranked_ids(sample)
    return {"bat": ids["bat"][:C.TOP_N], "bowl": ids["bowl"][:C.TOP_N]}


def run_bootstrap(base: pd.DataFrame) -> list:
    global _BALLS, _ROWS_BY_MATCH
    _BALLS = base.reset_index(drop=True)
    _ROWS_BY_MATCH = dict(_BALLS.groupby("match_id").indices.items())
    with Pool(C.BOOTSTRAP_WORKERS) as pool:
        return pool.map(one_bootstrap, range(C.BOOTSTRAP_SAMPLES))


def final_order(eligible_ids: list, boots: list, variants: dict, kind: str) -> list:
    """Average bootstrap rank (11 when outside the top 10) for every eligible player."""
    n = len(boots)
    rows = []
    for pid in eligible_ids:
        positions = [b[kind].index(pid) + 1 if pid in b[kind] else C.TOP_N + 1 for b in boots]
        in_top = sum(p <= C.TOP_N for p in positions)
        rows.append({
            "player_id": pid,
            "expected_rank": round(float(np.mean(positions)), 2),
            "boot_top10_pct": round(100 * in_top / n),
            "primary_rank": eligible_ids.index(pid) + 1,
            "variant_ranks": {v: (variants[v][kind].index(pid) + 1 if pid in variants[v][kind] else None)
                              for v in VARIANTS},
        })
    rows.sort(key=lambda r: (r["expected_rank"], r["primary_rank"]))
    for i, r in enumerate(rows, 1):
        r["final_rank"] = i
        r["variants_in_top10"] = sum(1 for v in VARIANTS
                                     if r["variant_ranks"][v] and r["variant_ranks"][v] <= C.TOP_N)
    return rows


def bootstrap_regulars(boots: list, eligible_ids: list, kind: str, min_share: float = 0.2) -> dict:
    """Players outside the eligible list who still show up often in resamples."""
    counts = {}
    for b in boots:
        for pid in b[kind]:
            counts[pid] = counts.get(pid, 0) + 1
    return {pid: round(100 * c / len(boots)) for pid, c in counts.items()
            if pid not in eligible_ids and c / len(boots) >= min_share}


def split_half(b: pd.DataFrame) -> dict:
    """Spearman correlation of a player's per-ball value between two halves."""

    def spearman(frame, id_col, value_col, mask, min_balls, first_half):
        def per_player(x):
            g = x.groupby(id_col)
            return pd.DataFrame({"n": g.size(), "v": g[value_col].mean()})
        a, c = per_player(frame[mask & first_half]), per_player(frame[mask & ~first_half])
        j = a.join(c, lsuffix="_a", rsuffix="_b", how="inner")
        j = j[(j.n_a >= min_balls) & (j.n_b >= min_balls)]
        return [int(len(j)), round(float(j.v_a.rank().corr(j.v_b.rank())), 3)]

    out = {}
    for kind, frame, id_col, value in (("bat", b[b.faced], "striker_id", "rae"),
                                       ("bowl", b, "bowler_id", "econ_resid")):
        pressure = frame.band.eq("pressure")
        everything = pd.Series(True, index=frame.index)
        res = {}
        for split, first in (("odd_even", frame.match_id % 2 == 0), ("by_time", frame.year <= 2024)):
            for min_balls in (30, 60):
                res[f"pressure_{split}_{min_balls}"] = spearman(frame, id_col, value, pressure, min_balls, first)
            res[f"all_balls_{split}_300"] = spearman(frame, id_col, value, everything, 300, first)
        out[kind] = res
    return out


def main():
    print("Preparing balls ...")
    base = pd.read_pickle(C.OUTPUT_DIR / "balls.pkl")
    model = json.loads((C.OUTPUT_DIR / "model.json").read_text())

    print("Running model variants ...")
    variants = run_variants(base)
    print(f"Running {C.BOOTSTRAP_SAMPLES} bootstrap resamples ...")
    boots = run_bootstrap(base)

    result = {"variants": variants, "bootstrap": boots, "split_half": split_half(base)}
    final = {}
    for kind, key in (("bat", "batters"), ("bowl", "bowlers")):
        eligible_ids = [r["player_id"] for r in model[key]]
        order = final_order(eligible_ids, boots, variants, kind)
        result[f"order_{kind}"] = order
        result[f"regulars_{kind}"] = bootstrap_regulars(boots, eligible_ids, kind)
        by_id = {r["player_id"]: r for r in model[key]}
        final[key] = [{**by_id[r["player_id"]], **r} for r in order[:C.TOP_N]]

    (C.OUTPUT_DIR / "robustness.json").write_text(json.dumps(result))
    (C.OUTPUT_DIR / "final_top10.json").write_text(json.dumps(final, indent=1))
    for key in ("batters", "bowlers"):
        print(f"\nFinal {key}:")
        for r in final[key]:
            print(f"  {r['final_rank']:>2}  {r['name']:<26} stable {r['boot_top10_pct']:>3}%  "
                  f"variants {r['variants_in_top10']}/7")


if __name__ == "__main__":
    main()
