# Who holds their nerve? Pressure picks for Rajasthan Royals

SupeRR Selector Season 2, Round 1, by SHRINIDHI GOWDA HG.

The brief asks which players RR should back at the IPL 2027 auction because
they are reliable under pressure. This code answers that from the
ball-by-ball data pack (IPL and T20I, 2022 to 2026) and builds the PDF report
and the dashboard.

## How to run

```bash
pip install -r requirements.txt
# copy the data pack CSVs into data/  (see data/README.md)
./run_all.sh
```

The full run takes five to ten minutes on a laptop, most of it the 200
bootstrap resamples. Everything is deterministic (the resamples use seeds
0 to 199), so you get the same lists every time. The PDF step needs Google
Chrome or Chromium; without it you can open `output/report.html` and print
it to PDF yourself.

## What each file does

| File | What it does |
|---|---|
| `config.py` | Every setting in one place: thresholds, weights, sample rules, the RR squad. |
| `pressure_model.py` | Rebuilds the match state before each ball, scores pressure from 0 to 1, works out an expected outcome for every ball, and ranks batters and bowlers. Writes `output/model.json`. |
| `robustness.py` | Re-runs the ranking seven ways and on 200 resampled datasets, checks whether pressure form repeats across halves of the data, and sets the final order. Writes `output/robustness.json` and `output/final_top10.json`. |
| `auction_context.py` | Squad status, fitness notes and the auction shortlist, taken from public reporting. Never used inside the model. |
| `build_report_data.py` | Pulls everything together for the report and dashboard, and writes the two rankings CSVs. |
| `make_figures.py` | Charts for the report. |
| `make_report.py` | The methodology report (HTML, then PDF). |
| `make_dashboard.py` | The dashboard: one HTML file with the data and chart library inside, so it works offline. |
| `templates/dashboard.html` | Layout and scripts for the dashboard. |
| `assets/chart.umd.min.js` | Chart.js 4.4.1 (MIT licence), inlined into the dashboard. |

## The method in brief

1. **Pressure score.** Each ball gets a score from 0 to 1 from the situation
   before it was bowled: required rate, balls and wickets left, score against
   par, knockout games. Hopeless chases (required rate above 15) fade out.
   Pressure balls are those at 0.55 or above; ordinary balls are 0.28 or below.
2. **Expected outcome.** For every ball, the average result of all balls in the
   same format, innings, phase, wickets-down band, required-rate band and pace
   or spin.
3. **Player value.** Batters: runs above expected and dismissals avoided.
   Bowlers: runs saved and extra wickets (one wicket = ten runs). Also how a
   player's pressure value compares with his own ordinary balls, and his worst
   quarter of pressure matches. Small samples are shrunk towards zero.
4. **Order.** A weighted index ranks the players. The final order is the
   average position across 200 resamples of the matches.

Sample rules (150 / 200 / 280 pressure balls depending on format evidence,
8 qualifying matches, 40 recent balls) are set without looking at results.

## Outputs

- `output/index.html`: the dashboard
- `output/SupeRR_Methodology_Report.pdf`: the report
- `output/rankings_batters.csv`, `output/rankings_bowlers.csv`
