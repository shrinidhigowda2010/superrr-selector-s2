"""Settings shared by every step of the pipeline.

All paths are relative to this folder, so the project runs from wherever it
is unzipped. Put the six CSV files from the data pack in ./data.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "output"
FIGURE_DIR = OUTPUT_DIR / "figures"
TEMPLATE_DIR = ROOT / "templates"
ASSET_DIR = ROOT / "assets"

AUTHOR = "SHRINIDHI GOWDA HG"

# --- Pressure bands -------------------------------------------------------
# Every ball gets a pressure index between 0 and 1 from the match state
# before it is bowled. Balls at or above PRESSURE_THRESHOLD are "pressure"
# balls; balls at or below ORDINARY_THRESHOLD are "ordinary". The band in
# between is left out of both comparisons.
PRESSURE_THRESHOLD = 0.55
ORDINARY_THRESHOLD = 0.28

# --- Weights in the composite index ---------------------------------------
# Batting:  scoring vs expected, survival vs expected, pressure minus own
#           ordinary level, match floor (25th percentile match).
# Bowling:  runs saved vs expected, wickets vs expected, pressure minus own
#           ordinary level, match floor.
BAT_WEIGHTS = (0.36, 0.16, 0.18, 0.30)
BOWL_WEIGHTS = (0.40, 0.26, 0.14, 0.20)
RUNS_PER_WICKET = 10.0  # one wicket is worth ten runs in a bowling spell

# Recent seasons count for more because the auction is about 2027.
RECENCY_WEIGHTS = {2022: 0.70, 2023: 0.85, 2024: 1.00, 2025: 1.20, 2026: 1.35}

# Shrinkage: a value measured over n balls is multiplied by n / (n + k).
# A batter with 180 weighted pressure balls keeps half of his raw edge.
BAT_PRIOR_BALLS = 180.0
BOWL_PRIOR_BALLS = 200.0
FLOOR_PRIOR_MATCHES = 8.0

# --- Sample rules (never performance rules) -------------------------------
MIN_BALLS_BOTH_FORMATS = 150  # some IPL and some T20I pressure evidence
MIN_BALLS_IPL_ONLY = 200      # fewer than 40 T20I pressure balls
MIN_BALLS_T20I_ONLY = 280     # fewer than 40 IPL pressure balls
FORMAT_EVIDENCE_BALLS = 40
MIN_FLOOR_MATCHES = 8         # matches with 6+ pressure balls
MIN_RECENT_BALLS = 40         # pressure balls in 2025-26
MIN_LAST_YEAR = 2025
RECENT_FROM_YEAR = 2025

# Expected-value cells with fewer balls than this fall back to a coarser cell.
MIN_CELL_BALLS = 200

# --- Robustness -----------------------------------------------------------
BOOTSTRAP_SAMPLES = 200
BOOTSTRAP_WORKERS = 4
TOP_N = 10

# --- Rajasthan Royals squad after the IPL 2027 retentions -----------------
# (name in the data pack, player_id, role, country, note)
RR_SQUAD = [
    ("Riyan Parag", 6423, "Batter", "India", "Captain, middle order"),
    ("Yashasvi Jaiswal", 6819, "Batter", "India", "Opener"),
    ("Vaibhav Sooryavanshi", 50284, "Batter", "India", "Opener"),
    ("Ravindra Jadeja", 152, "All-rounder", "India", "Spin all-rounder, middle order"),
    ("Dhruv Jurel", 7260, "Keeper", "India", "Wicketkeeper, middle order"),
    ("Jofra Archer", 3298, "Bowler", "England", "Overseas pace"),
    ("Aman Rao Perala", 47523, "Bowler", "India", "Pace"),
    ("Brijesh Sharma", 67036, "Bowler", "India", "Pace"),
    ("Nandre Burger", 7312, "Bowler", "South Africa", "Overseas pace"),
    ("Dasun Shanaka", 2436, "All-rounder", "Sri Lanka", "Overseas finisher"),
    ("Donovan Ferreira", 8182, "All-rounder", "South Africa", "Overseas keeper and finisher"),
    ("Lhuan Pretorius", 43798, "Batter", "South Africa", "Overseas top order"),
    ("Ravi Bishnoi", 7503, "Bowler", "India", "Wrist spin"),
    ("Sandeep Sharma", 2411, "Bowler", "India", "Death and new-ball pace"),
    ("Shubham Dubey", 25139, "Batter", "India", "Middle order"),
    ("Sushant Mishra", 7269, "Bowler", "India", "Left-arm pace"),
    ("Yash Punja", 41503, "Batter", "India", "Batter"),
    ("Mohammed Shami", 1566, "Bowler", "India", "Traded in, pace"),
    ("Manimaran Siddharth", 6237, "Bowler", "India", "Traded in, spin"),
]
