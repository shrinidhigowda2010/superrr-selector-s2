"""Charts for the PDF report (PNG files in output/figures).

Run:  python make_figures.py
"""

import json

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

import config as C  # noqa: E402

PINK, BLUE, GREY, NAVY = "#EA1A85", "#254AA5", "#9aa6c9", "#0B1A4A"
plt.rcParams.update({
    "font.size": 9, "axes.spines.top": False, "axes.spines.right": False,
    "axes.titleweight": "bold", "axes.titlesize": 10, "axes.titlecolor": NAVY,
})


def save(fig, name):
    fig.tight_layout()
    fig.savefig(C.FIGURE_DIR / f"{name}.png", dpi=180)
    plt.close(fig)


def label_bars(ax, fmt="{:.1f}"):
    for p in ax.patches:
        ax.text(p.get_x() + p.get_width() / 2, p.get_height(), fmt.format(p.get_height()),
                ha="center", va="bottom", fontsize=8)


def pressure_vs_ordinary(d):
    bs = d["band_stats"]
    fig, axes = plt.subplots(1, 4, figsize=(8, 2.3))
    for ax, (key, title) in zip(axes, [("sr", "Strike rate"), ("dismissal_pct", "Dismissals per 100 balls"),
                                       ("dot_pct", "Dot balls %"), ("econ", "Runs per over")]):
        ax.bar(["Ordinary", "Pressure"], [bs["ordinary"][key], bs["pressure"][key]], color=[BLUE, PINK])
        ax.set_title(title)
        label_bars(ax)
    save(fig, "band")


def phase_share(d):
    phases = ["PP", "MID", "LATE", "DEATH"]
    labels = ["Overs 1-6", "7-12", "13-16", "17-20"]
    fig, ax = plt.subplots(figsize=(4, 2.6))
    bottom = np.zeros(4)
    for band, colour in (("ordinary", BLUE), ("middle", GREY), ("pressure", PINK)):
        v = np.array([100 * d["phase_band"][p][band] for p in phases])
        ax.bar(labels, v, bottom=bottom, color=colour, label=band)
        bottom += v
    ax.set_ylabel("% of balls")
    ax.legend(fontsize=7, loc="upper left")
    ax.set_title("Where the pressure balls are")
    save(fig, "phase")


def fade_effect(d):
    before, after = d["chase_no_fade"], d["chase_pressure"]
    fig, axes = plt.subplots(1, 2, figsize=(4.2, 2.6))
    axes[0].bar(["Without fade", "With fade"], [before["median_rrr"], after["median_rrr"]], color=[GREY, PINK])
    axes[0].set_title("Typical required rate\non chase pressure balls")
    axes[1].bar(["Without fade", "With fade"], [100 * before["chase_win_rate"], 100 * after["chase_win_rate"]],
                color=[GREY, PINK])
    axes[1].set_title("% of those balls in\nchases that were won")
    for ax in axes:
        label_bars(ax)
    save(fig, "fade")


def top_ten(d, key, kind):
    rows = d[key]
    names = [r["name"] for r in rows][::-1]
    y = np.arange(len(rows))
    fig, axes = plt.subplots(1, 2, figsize=(8, 3.0), gridspec_kw={"width_ratios": [2, 1]})
    expected = [r["exp_sr" if kind == "bat" else "exp_economy"] for r in rows][::-1]
    actual = [r["sr" if kind == "bat" else "economy"] for r in rows][::-1]
    axes[0].hlines(y, expected, actual, color=GREY, lw=2)
    axes[0].scatter(expected, y, color=BLUE, label="expected", zorder=3)
    axes[0].scatter(actual, y, color=PINK, label="actual", zorder=3)
    axes[0].set_yticks(y)
    axes[0].set_yticklabels(names)
    axes[0].legend(fontsize=7)
    axes[0].set_title("Strike rate under pressure" if kind == "bat" else "Economy under pressure (lower is better)")
    stable = [r["boot_top10_pct"] for r in rows][::-1]
    axes[1].barh(y, stable, color=[PINK if v >= 50 else GREY for v in stable])
    axes[1].set_yticks(y)
    axes[1].set_yticklabels([])
    axes[1].set_xlim(0, 100)
    axes[1].axvline(50, color=NAVY, ls=":", lw=1)
    axes[1].set_title("Top 10 in % of resamples", fontsize=8.5)
    for i, v in enumerate(stable):
        axes[1].text(v + 1, i, f"{v}%", va="center", fontsize=7)
    save(fig, f"top_{kind}")


def variant_grid(d, key, kind):
    rows = d[key]
    variants = d["variants"]
    short = ["Main", "IPL only", "Equal wts", "No recency", "From 0.50", "From 0.60", "Minimums -20%"]
    ranks = np.array([[r["variant_ranks"][v] or 99 for v in variants] for r in rows], float)
    shade = np.where(ranks <= 10, 1, np.where(ranks < 99, 0.45, 0))
    fig, ax = plt.subplots(figsize=(5.2, 3.2))
    cmap = matplotlib.colors.LinearSegmentedColormap.from_list("rr", ["#f1f1f6", "#ffd0e6", PINK])
    ax.imshow(shade, cmap=cmap, aspect="auto", vmin=0, vmax=1)
    for i in range(ranks.shape[0]):
        for j in range(ranks.shape[1]):
            v = ranks[i, j]
            ax.text(j, i, "-" if v == 99 else int(v), ha="center", va="center", fontsize=7,
                    color="white" if v <= 10 else NAVY)
    ax.set_xticks(range(len(short)))
    ax.set_xticklabels(short, rotation=30, fontsize=7)
    ax.set_yticks(range(len(rows)))
    ax.set_yticklabels([r["name"] for r in rows], fontsize=7)
    ax.set_title(("Batters" if kind == "bat" else "Bowlers") + ": rank when one choice changes")
    save(fig, f"heat_{kind}")


def repeatability(d):
    sh = d["split_half"]
    items = [
        ("Bat, all balls (odd/even)", sh["bat"]["all_balls_odd_even_300"][1], False),
        ("Bat, all balls (by year)", sh["bat"]["all_balls_by_time_300"][1], False),
        ("Bat, pressure (odd/even)", sh["bat"]["pressure_odd_even_30"][1], True),
        ("Bat, pressure (by year)", sh["bat"]["pressure_by_time_30"][1], True),
        ("Bowl, all balls (odd/even)", sh["bowl"]["all_balls_odd_even_300"][1], False),
        ("Bowl, all balls (by year)", sh["bowl"]["all_balls_by_time_300"][1], False),
        ("Bowl, pressure (odd/even)", sh["bowl"]["pressure_odd_even_30"][1], True),
        ("Bowl, pressure (by year, 60+)", sh["bowl"]["pressure_by_time_60"][1], True),
    ][::-1]
    fig, ax = plt.subplots(figsize=(5, 2.8))
    ax.barh([i[0] for i in items], [i[1] for i in items], color=[PINK if i[2] else BLUE for i in items])
    ax.set_xlabel("Rank correlation between the two halves")
    ax.set_title("Does it repeat?")
    for i, (_, v, _) in enumerate(items):
        ax.text(v + 0.01 if v >= 0 else v - 0.06, i, f"{v:.2f}", va="center", fontsize=7)
    save(fig, "reliab")


def match_by_match(d):
    picks = [("batters", 0), ("batters", 1), ("batters", 2), ("bowlers", 0), ("bowlers", 1), ("bowlers", 2)]
    fig, axes = plt.subplots(2, 3, figsize=(8, 4.2))
    for ax, (key, i) in zip(axes.flat, picks):
        r = d[key][i]
        values = [m["value"] for m in r["series"]]
        ax.bar(range(len(values)), values, color=[PINK if v >= 0 else GREY for v in values])
        ax.axhline(0, color=NAVY, lw=0.6)
        ax.set_title(f"{r['name']} ({'bat' if key == 'batters' else 'bowl'} #{r['final_rank']})", fontsize=8.5)
        ax.set_xticks([])
        s = r["series"]
        ax.set_xlabel(f"{len(s)} pressure matches, {s[0]['date'][:4]}-{s[-1]['date'][:4]}", fontsize=7)
    axes[0, 0].set_ylabel("runs above expected")
    axes[1, 0].set_ylabel("runs saved (+10 a wicket)")
    save(fig, "series")


def squad_exposure(d):
    squad = d["squad"]
    x = np.arange(len(squad))
    faced = [(p.get("bat") or {}).get("balls", 0) for p in squad]
    bowled = [(p.get("bowl") or {}).get("balls", 0) for p in squad]
    fig, ax = plt.subplots(figsize=(8, 2.4))
    ax.bar(x - 0.2, faced, 0.4, color=BLUE, label="pressure balls faced")
    ax.bar(x + 0.2, bowled, 0.4, color=PINK, label="pressure balls bowled")
    ax.axhline(150, color=NAVY, ls=":", lw=1)
    ax.text(len(squad) - 0.5, 155, "150-ball minimum", fontsize=7, ha="right")
    ax.set_xticks(x)
    ax.set_xticklabels([p["name"] for p in squad], rotation=60, ha="right", fontsize=7)
    ax.legend(fontsize=7)
    ax.set_title("How much pressure cricket the current RR squad has played (2022-26)")
    save(fig, "squad")


def main():
    C.FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    d = json.loads((C.OUTPUT_DIR / "report_data.json").read_text())
    pressure_vs_ordinary(d)
    phase_share(d)
    fade_effect(d)
    for key, kind in (("batters", "bat"), ("bowlers", "bowl")):
        top_ten(d, key, kind)
        variant_grid(d, key, kind)
    repeatability(d)
    match_by_match(d)
    squad_exposure(d)
    print("Figures written to", C.FIGURE_DIR)


if __name__ == "__main__":
    main()
