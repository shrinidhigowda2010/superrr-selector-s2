#!/usr/bin/env bash
# Rebuild every output from the data pack, in order.
set -euo pipefail
PY=${PYTHON:-$(command -v python3 || command -v python)}
cd "$(dirname "$0")"
"$PY" pressure_model.py       # pressure score, expected values, rankings
"$PY" robustness.py           # 7 model versions + 200 resamples (a few minutes)
"$PY" build_report_data.py    # one JSON for the report and dashboard, plus the CSVs
"$PY" make_figures.py         # report charts
"$PY" make_report.py          # report HTML and PDF
"$PY" make_dashboard.py       # single-file dashboard (output/index.html)
