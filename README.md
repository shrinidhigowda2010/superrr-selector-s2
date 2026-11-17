# Who holds their nerve?

Pressure picks for Rajasthan Royals at the IPL 2027 auction.
SupeRR Selector Season 2, Round 1, by SHRINIDHI GOWDA HG.

**Dashboard:** open `index.html`, or the GitHub Pages link for this repo once
Pages is switched on (Settings > Pages > Deploy from branch > main, root).

**Report:** [SupeRR_Methodology_Report.pdf](SupeRR_Methodology_Report.pdf)

## The answer

| # | Batters | Bowlers |
|---|---|---|
| 1 | David Miller | Varun Chakravarthy |
| 2 | Namboori Tilak Varma | Kuldeep Yadav |
| 3 | Tim David | Mustafizur Rahman |
| 4 | Tristan Stubbs | Rashid Khan |
| 5 | Romario Shepherd | Matheesha Pathirana |
| 6 | Shivam Dube | Jason Holder |
| 7 | Rovman Powell | Jasprit Bumrah |
| 8 | Rinku Singh | Mitchell Santner |
| 9 | Rashid Khan | Bhuvneshwar Kumar |
| 10 | Suryakumar Yadav | Avesh Khan |

Full numbers are in `results/`. Every ball in the IPL and T20I data
(2022 to 2026) gets a pressure score from the situation before it was bowled,
and each player is compared with what an average player would have done on
the same balls. The order is the average position across 200 resamples of
the matches.

## Layout

```
index.html                      the dashboard (one file, works offline)
SupeRR_Methodology_Report.pdf   the report
results/                        rankings CSVs for both lists
screenshots/                    dashboard screenshots
code/                           the pipeline that builds all of the above
```

## Rebuilding everything

The ball-by-ball data pack belongs to the organisers and is not in this repo.
Put its CSV files in `code/data/` (the list is in `code/data/README.md`), then:

```bash
cd code
pip install -r requirements.txt
./run_all.sh
```

See `code/README.md` for what each script does.
