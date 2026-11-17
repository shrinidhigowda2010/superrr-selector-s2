"""Build the methodology report: output/report.html, then a PDF.

The PDF is printed with headless Chrome or Chromium (whichever is
installed). Author and title are written into the PDF metadata.

Run:  python make_report.py
"""

from __future__ import annotations

import html
import json
import shutil
import subprocess

import config as C

E = html.escape
PDF_NAME = "SupeRR_Methodology_Report.pdf"

CSS = """
@page{size:A4;margin:15mm 14mm}
body{font-family:Georgia,'Times New Roman',serif;color:#1b2440;font-size:9.8pt;line-height:1.45}
h1{font-family:Arial,sans-serif;color:#0B1A4A;font-size:21pt;margin:0 0 4px}
h2{font-family:Arial,sans-serif;color:#0B1A4A;font-size:13.5pt;margin:16px 0 6px;padding-bottom:3px;border-bottom:2px solid #EA1A85}
h3{font-family:Arial,sans-serif;color:#254AA5;font-size:10.5pt;margin:10px 0 4px}
p{margin:5px 0 7px}
.title{border-left:6px solid #EA1A85;padding:4px 0 4px 14px;margin-bottom:10px}
.title .sub{font-family:Arial,sans-serif;color:#555d7a;font-size:10pt}
table{border-collapse:collapse;width:100%;font-family:Arial,sans-serif;font-size:7.8pt;margin:6px 0}
th{background:#eef1fa;color:#0B1A4A;text-align:left;padding:4px;font-weight:600}
td{padding:4px;border-bottom:1px solid #e3e6f0;vertical-align:top}
td small,th small{color:#6b7392;font-size:7pt}
.rank td{border-bottom:none;padding:3px 4px}.rank tr.top td{border-top:1px solid #e3e6f0;padding-top:5px}.fit{color:#3a4262;font-size:7.6pt;padding-bottom:5px!important}.pool{color:#b0105f;font-weight:600}.note{color:#7a5300}
.pb{page-break-before:always}.two{display:flex;gap:14px}.two>div{flex:1}
.aside{background:#f6f7fb;border-left:3px solid #254AA5;padding:6px 12px;margin:8px 0}
.lists ol{margin:2px 0 2px 18px;padding:0;font-family:Arial,sans-serif;font-size:9.4pt}
.small{font-size:8.3pt;color:#555d7a}
ul{margin:4px 0 6px 18px;padding:0}li{margin:2px 0}
img{display:block;margin:4px auto}
"""


def img(name, width="100%"):
    return f'<img src="figures/{name}.png" style="width:{width}">'


def plain_status(r):
    return "In the auction pool" if r["pool"] else r["status"].replace("Retained by ", "Retained, ")


def top_table(rows, kind):
    head = ("<tr><th>#</th><th>Player</th><th>Pressure balls<br><small>IPL / T20I</small></th>"
            + ("<th>SR</th><th>Expected</th>" if kind == "bat" else "<th>Econ</th><th>Expected</th><th>Wkts</th>")
            + "<th>Index</th><th>Good matches</th><th>Top 10 in resamples</th><th>Versions</th><th>Status</th></tr>")
    span = 10 if kind == "bat" else 11
    body = ""
    for r in rows:
        stats = (f"<td>{r['sr']:.1f}</td><td>{r['exp_sr']:.1f}</td>" if kind == "bat"
                 else f"<td>{r['economy']:.2f}</td><td>{r['exp_economy']:.2f}</td><td>{r['wickets']}</td>")
        note = f" <span class='note'>{E(r['flag'])}</span>" if r.get("flag") else ""
        body += (f"<tr class='top'><td>{r['final_rank']}</td><td><b>{E(r['name'])}</b> <small>{E(r['nation'])}</small></td>"
                 f"<td>{r['balls_pressure']} <small>({r['ipl_balls']} / {r['t20i_balls']})</small></td>{stats}"
                 f"<td>{r['index']:.1f}</td><td>{r['positive_pct']}%</td><td>{r['boot_top10_pct']}%</td>"
                 f"<td>{r['variants_in_top10']}/7</td>"
                 f"<td class='{'pool' if r['pool'] else ''}'>{E(plain_status(r))}</td></tr>"
                 f"<tr><td></td><td colspan='{span - 1}' class='fit'>For RR: {E(r['fit'])}{note}</td></tr>")
    return f"<table class='rank'>{head}{body}</table>"


def evidence(s):
    if s["kind"] == "bat":
        return f"{s['pressure_balls']} balls, SR {s['sr']} vs {s['exp_sr']}, good in {s['positive']}% of matches"
    return (f"{s['pressure_balls']} balls, {s['econ']} an over vs {s['exp_econ']}, "
            f"{s['wickets']} wkts, good in {s['positive']}% of matches")


def checked_table(rows):
    body = ""
    for c in rows:
        if c["kind"] == "bat":
            line = f"{c['pressure_balls']} balls, SR {c['sr']} vs {c['exp_sr']}"
        else:
            line = f"{c['pressure_balls']} balls, econ {c['econ']} vs {c['exp_econ']}"
        where = (f"No. {c['final_rank']} of {c['pool_size']} {'batters' if c['kind'] == 'bat' else 'bowlers'}"
                 f" (index {c['index']:.1f})" if c["final_rank"] else "Below the sample rules")
        body += (f"<tr><td><b>{E(c['name'])}</b></td><td>{'Batting' if c['kind'] == 'bat' else 'Bowling'}</td>"
                 f"<td>{line}</td><td>{E(where)}</td><td>{E(c['reason'])}</td></tr>")
    return ("<table><tr><th>Player</th><th>Looked at</th><th>Under pressure</th><th>Where he lands</th>"
            f"<th>Why he is not in my ten</th></tr>{body}</table>")


def names(rows):
    return ", ".join(rows[:-1]) + " and " + rows[-1] if len(rows) > 1 else "".join(rows)


def build_html(d):
    s, bs, st = d["situation"], d["band_stats"], d["settings"]
    cp, nf = d["chase_pressure"], d["chase_no_fade"]
    sh = d["split_half"]
    bat, bowl = d["batters"], d["bowlers"]
    board, snaps = d["board"], d["snapshots"]
    everyone = bat + bowl
    steady = [r["name"] for r in everyone if r["boot_top10_pct"] >= 70]
    shaky = [f"{r['name']} ({r['boot_top10_pct']}%)" for r in everyone if r["boot_top10_pct"] < 50]
    pool = [r["name"] for r in everyone if r["pool"]]
    lift_risk = round(bs["pressure"]["dismissal_pct"] / bs["ordinary"]["dismissal_pct"] * 100 - 100)

    def near_misses(kind):
        out = []
        for r in d[f"stability_{kind}"]:
            if not r["eligible"]:
                out.append(f"{r['name']} ({r['boot']}%)")
        return out

    def next_in_line(kind, top_ids):
        return [f"{r['name']} ({r['boot']}%)" for r in d[f"stability_{kind}"]
                if r["eligible"] and r["player_id"] not in top_ids][:2]

    bat_ids = {r["player_id"] for r in bat}
    bowl_ids = {r["player_id"] for r in bowl}
    rel = lambda k, key: sh[k][key][1]  # noqa: E731

    targets = "".join(
        f"<tr><td><b>{E(t['priority'])}</b></td><td><b>{E(t['name'])}</b><br><small>{t['slot']}, {E(t['role'])}</small></td>"
        f"<td>{E(evidence(snaps[t['key']]))}</td><td>{E(t['why'])}</td><td><small>{E(t['risk'])}</small></td></tr>"
        for t in board["targets"])
    avoid = "".join(f"<li><b>{E(a['name'])}.</b> {E(a['note'])}</li>" for a in board["avoid"])
    elsewhere = "".join(f"<li><b>{E(a['name'])}.</b> {E(a['note'])}</li>" for a in board["unavailable"] + board["watch"])
    public = "".join(f"<li>{E(x)}</li>" for x in board["public_information"])
    hetmyer, deshpande = snaps["Shimron Hetmyer|bat"], snaps["Tushar Deshpande|bowl"]
    jadeja = next(p for p in d["squad"] if p["name"] == "Ravindra Jadeja")
    bishnoi = next(p for p in d["squad"] if p["name"] == "Ravi Bishnoi")
    rashid_bowl = next(r for r in bowl if r["name"] == "Rashid Khan")
    rashid_bat = next(r for r in bat if r["name"] == "Rashid Khan")
    kuldeep = next(r for r in bowl if r["name"] == "Kuldeep Yadav")

    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<title>Who holds their nerve? SupeRR Selector Round 1, {E(d['author'])}</title>
<meta name="author" content="{E(d['author'])}"><style>{CSS}</style></head><body>

<div class="title"><h1>Who holds their nerve?</h1>
<div class="sub">SupeRR Selector Season 2, Round 1. Rajasthan Royals, IPL 2027 auction.<br>
{E(d['author'])} &middot; Data: the RR ball-by-ball pack, IPL and T20I, 2022 to 2026 &middot; Squad facts as of {d['as_of']}</div></div>

<h2>Why I chose this approach</h2>
<p>When I started, my first instinct was to sort players by strike rate and economy in the last five overs. It did not take long to see why that would not work. A batter coming in at 140 for 3 needing 30 off 18 is in a completely different spot from one walking out at 90 for 6 needing 80. Raw death-overs numbers mix the two together, and they also reward players who only ever bat in easy chases.</p>
<p>So I built the analysis around one simple question. On a ball where the match was genuinely on the line, did this player do better than an average player would have done in exactly that situation? Everything else in this report follows from that: a ball-by-ball pressure score, a fair expected value for every ball, and then a lot of checking to see whether the answer holds up when I cut the data differently.</p>

<h3>The short version</h3>
<p>I looked at {s['matches']} matches ({s['ipl_matches']} IPL, {s['t20i_matches']} T20I) and {s['balls']:,} deliveries. {s['pressure_balls']:,} of those balls ({100 * s['pressure_share']:.1f}%) count as high pressure. On those balls batters get out about {lift_risk}% more often than usual ({bs['pressure']['dismissal_pct']} per 100 balls against {bs['ordinary']['dismissal_pct']}), which told me the definition was picking up something real. {s['eligible_batters']} batters and {s['eligible_bowlers']} bowlers have enough pressure balls to judge.</p>
<p>The most dependable names are {names(steady)}: each of them stays in the top 10 in at least 70% of my resampled datasets. The catch for RR is that most of the twenty are retained by other franchises. Only {names(pool)} are in the auction pool, so the last section turns the rankings into a shortlist RR can actually bid for.</p>
<div class="two lists"><div><h3>Top 10 batters</h3><ol>{''.join(f"<li>{E(r['name'])} <span class=small>({r['boot_top10_pct']}%)</span></li>" for r in bat)}</ol></div>
<div><h3>Top 10 bowlers</h3><ol>{''.join(f"<li>{E(r['name'])} <span class=small>({r['boot_top10_pct']}%)</span></li>" for r in bowl)}</ol></div></div>
<p class="small">The percentage is how often the player made the top 10 across 200 resamples of the matches.</p>

<h2 class="pb">1. What I mean by pressure</h2>
<p>Pressure is about the state of the game when the ball is bowled, so I score every delivery using only what was known before it: the required rate, balls and wickets left, the score compared with par, and whether it was a knockout. What happened on the ball itself never feeds into its pressure score. The result is a number from 0 to 1.</p>
<p>For the chasing side the score grows with the required rate and with wickets lost, and both matter more as the innings runs out. Some situations are obviously tense, so they get a minimum score whatever the formula says: the last four overs with nine or more needed an over; 30 or fewer needed off the last 18 balls with six or fewer wickets left; the tail exposed late on; and steep chases of 12 an over or more with ten overs to go. For the side batting first, pressure comes from the death overs, collapses and being below the usual score for that point of the innings. Par is the median first-innings score at that ball count in this data. Knockout games get a small uplift, and once a chase is won the pressure is zero.</p>
<p>One choice needs explaining. In my first version, a lot of the "pressure" balls in chases came when the game was already gone. Without any correction the typical required rate on those balls was {nf['median_rrr']}, {100 * nf['share_rrr18']:.0f}% of them came at 18 or more an over, and the chasing side won only {100 * nf['win_rate_rrr18']:.1f}% of those. That is slogging in a lost cause. It flattered lower-order hitters and handed bowlers easy credit. So the chase score now fades from full at a required rate of 15 to nothing at 21. After the fade the typical required rate is {cp['median_rrr']}.</p>
<p>A ball counts as pressure at {st['pressure_threshold']} or above and as ordinary at {st['ordinary_threshold']} or below. The balls in between are left out of both, so the comparison is between clearly tense and clearly calm cricket. Rain-shortened innings use their revised length, and the death overs are counted back from the end of the shortened innings.</p>
{img('band')}
<div class="two"><div>{img('phase')}</div><div>{img('fade')}</div></div>
<p class="small">Chasing sides went on to win {100 * cp['chase_win_rate']:.0f}% of the games behind these pressure balls, against {100 * d['chase_ordinary_win_rate']:.0f}% for ordinary chase balls. Almost all of the pressure sits in overs 13 to 20. Early collapses in the powerplay are rarely flagged, which I come back to under limitations.</p>

<h2 class="pb">2. How I measure a player</h2>
<p>The heart of the method is an expected value for every ball. I group balls by format, innings, phase, wickets down, required-rate band and pace or spin, and take the average outcome in each group. If a group has fewer than 200 balls I step back to a broader one so the averages are not noise. That gives me what an average batter scores and how often he gets out in that exact spot, and what an average bowler concedes and how often he takes a wicket. A finisher at 6 down needing 13 an over is therefore compared only with other batters in that position, not with an opener in the powerplay.</p>
<p>From there, a batter's value under pressure is runs above expected per ball, plus dismissals avoided. A bowler's value is runs saved per ball, plus wickets above expected, where one wicket is worth ten runs. I also compare each player's pressure value with his own value on ordinary balls, because I wanted to know who lifts and who shrinks when it matters. And I look at his worst quarter of pressure matches. A player whose bad days are still acceptable is more useful to a captain than one who wins two games a season and goes missing in the rest.</p>
<p>Small samples get shrunk. Each value is multiplied by n / (n + k), where k is {st['bat_prior_balls']:.0f} balls for batters and {st['bowl_prior_balls']:.0f} for bowlers, so a batter with 180 pressure balls keeps half of his raw edge. Recent seasons count for more, rising from 0.70 for 2022 to 1.35 for 2026, since RR are buying for 2027.</p>
<p>The four parts are turned into z-scores within the qualifying group and combined. For batting the weights are {st['bat_weights'][0]} scoring, {st['bat_weights'][1]} survival, {st['bat_weights'][2]} lift over his own ordinary level and {st['bat_weights'][3]} worst-quarter matches. For bowling they are {st['bowl_weights'][0]}, {st['bowl_weights'][1]}, {st['bowl_weights'][2]} and {st['bowl_weights'][3]}. The index is shown on a 50 plus or minus 12 scale. These weights are my judgment, which is exactly why I test equal weights later on.</p>
<p>The final order does not come from a single run. I resample the matches 200 times, rebuild the whole ranking each time, and order players by their average position (anyone outside the top 10 in a resample counts as 11th). A player cannot get in on the back of one freak innings, because in many resamples that innings simply is not there.</p>

<h2>3. Keeping the comparison fair</h2>
<p>I set sample rules before looking at any results, and none of them depends on how well a player did. He needs 150 pressure balls if he has evidence from both the IPL and T20Is, 200 if nearly all of it is IPL, and 280 if nearly all of it is T20I. The higher bars exist because doing well against one pool is weaker evidence, and T20I cricket includes Associate teams. He also needs at least 8 matches with 6 or more pressure balls, at least 40 pressure balls in 2025 or 2026, and to have played in 2025 or later.</p>
<p>Format sits inside every expected-value group, so an IPL ball is only ever compared with IPL balls. I also cleaned up some things that would otherwise distort the numbers. No-result and abandoned games are removed, and super overs are dropped. Wides are not counted as balls faced but are charged to the bowler. Byes, leg-byes and penalty runs are not charged to the bowler, and run-outs are not bowler wickets. Revised targets and revised innings lengths are applied for rain games. That last one surprised me: the revised-overs column in the pack is stored in balls, not overs.</p>
<p>The rules leave {s['eligible_batters']} batters and {s['eligible_bowlers']} bowlers. That is a small group, and it is small for a reason. Only finishers and death bowlers face enough pressure balls to judge, so an opener such as Jaiswal, with 12 pressure balls, cannot be rated this way at all.</p>

<h2 class="pb">4. Top 10 batters</h2>
{top_table(bat, 'bat')}
{img('top_bat', '96%')}
<p class="small">Expected = the strike rate an average batter would have had on exactly the same balls. Good matches = share of his pressure matches with a positive value. Variants = how many of the 7 versions of the model put him in the top 10.</p>

<h2 class="pb">5. Top 10 bowlers</h2>
{top_table(bowl, 'bowl')}
{img('top_bowl', '92%')}
<h3>Match by match, top three in each list</h3>
{img('series', '92%')}
<p class="small">Each bar is one match with pressure balls; pink means he beat the expected outcome that day. The dashboard has this chart for all twenty players.</p>

<h2 class="pb">6. How much I trust it</h2>
<div class="two"><div>{img('heat_bat')}</div><div>{img('heat_bowl')}</div></div>
<p>I re-ran the model seven ways, changing one thing each time: IPL balls only, equal weights, no recency weighting, the pressure line at 0.50 and at 0.60, and the ball minimums cut by 20%. Pink cells are top-10 finishes. {names(steady)} hold up under almost every version. The shakier places are {names(shaky)}. I would read batting places 7 to 10 and bowling places 8 to 10 as a group rather than an exact order.</p>
<p>The players just outside are worth knowing. Among those who qualify, the next batters in line are {names(next_in_line('bat', bat_ids))} and the next bowlers are {names(next_in_line('bowl', bowl_ids))}. Some players who miss the sample rules still turn up in plenty of resamples: batters {names(near_misses('bat'))}; bowlers {names(near_misses('bowl')) or 'none'}.</p>
<div class="two"><div>{img('reliab')}</div><div>
<h3>The finding that surprised me most</h3>
<p>I split the data in half twice, odd against even matches and 2022-24 against 2025-26, and checked whether a player's value in one half predicts it in the other. General skill repeats quite well: across all balls the correlation is between {min(rel('bat', 'all_balls_by_time_300'), rel('bowl', 'all_balls_by_time_300')):.2f} and {max(rel('bat', 'all_balls_odd_even_300'), rel('bowl', 'all_balls_odd_even_300')):.2f}. Pressure-only value repeats much less, between {min(rel('bat', 'pressure_by_time_60'), rel('bat', 'pressure_odd_even_60')):.2f} and {max(rel('bat', 'pressure_by_time_30'), rel('bat', 'pressure_odd_even_30')):.2f} for batters and {min(rel('bowl', 'pressure_odd_even_30'), rel('bowl', 'pressure_odd_even_60')):.2f} to {rel('bowl', 'pressure_by_time_60'):.2f} for bowlers, depending on the split.</p>
<p>I did not expect clutch to be this noisy. It is the reason the model shrinks small samples so hard, leans on the worst-quarter matches, and reports stability instead of one confident list. These rankings say who has delivered under pressure in 2022-26 once luck is accounted for. They are not a guarantee about 2027.</p></div></div>

<h3>Two calls I made that someone could disagree with</h3>
<p>Rashid Khan is No. {rashid_bowl['final_rank']} among bowlers in all seven versions, but only No. {rashid_bat['final_rank']} among batters, and he makes the batting top 10 in just {rashid_bat['boot_top10_pct']}% of resamples. I was tempted to swap him out of the batting list for someone who looks more like a specialist. I did not, because I had decided the order would come from the method and not from me. The same goes for Kuldeep Yadav, No. {kuldeep['final_rank']} on the numbers even though his IPL 2026 was poor. I kept the model's answer, but if I were in RR's auction room I would not pay top price for him on this report alone.</p>
<p>The fade on hopeless chases is also my call. The 15 and 21 cut-offs are a judgment, not something the data hands you. I checked what happens if the pressure line moves by 0.05. At 0.50, {sum(1 for r in bat if (r['variant_ranks']['pressure_t_0.5'] or 99) <= 10)} of my 10 batters and {sum(1 for r in bowl if (r['variant_ranks']['pressure_t_0.5'] or 99) <= 10)} of my 10 bowlers stay in the top 10. At 0.60 the samples get so small that only {d['variant_pool_sizes']['pressure_t_0.6']['bat']} batters and {d['variant_pool_sizes']['pressure_t_0.6']['bowl']} bowlers still qualify, which tells me 0.55 is about as strict as this data allows.</p>

<h3>Limitations</h3>
<p>Pressure in the powerplay, such as an early collapse in a big chase, is rarely flagged. The expected values are built from all players, including the player being rated, which has a small in-sample effect. The T20I pool includes Associate sides, and the groups only partly adjust for the gap in quality. Fitness and availability are not in the data at all. I report them separately and they never change a rank.</p>

<h2 class="pb">7. What this means for RR</h2>
{img('squad')}
<p>Of the 19 players RR have kept or traded for, only Jadeja (batting, No. {jadeja['bat_rank']} of {s['eligible_batters']}) and Bishnoi (bowling, No. {bishnoi['bowl_rank']} of {s['eligible_bowlers']}) meet the sample rules, and neither ranks well. Most of the core is young or bats at the top, so they rarely see these situations. After releasing Hetmyer, Deshpande, Maphaka and Milne, the squad has no proven pressure finisher and no proven death bowler. RR have six places to fill, three of them overseas. {E(board['purse_note'])}</p>
<div class="aside">Do the numbers back RR's own releases? Yes. Hetmyer: {E(evidence(hetmyer))}. Deshpande: {E(evidence(deshpande))}.</div>
<h3>Who I would bid for</h3>
<table><tr><th>Order</th><th>Player</th><th>Under pressure</th><th>Why</th><th>Risk</th></tr>{targets}</table>
<div class="two"><div><h3>Ones I would avoid</h3><ul>{avoid}</ul></div><div><h3>Good numbers, but not really available</h3><ul>{elsewhere}</ul></div></div>
<p class="small">Everyone else in the two lists is retained by another team, so RR could only get them by trade before the window closes on 9 December.</p>

<h3>Players I checked but didn't pick</h3>
{checked_table(d['checked_not_picked'])}

<h2>8. Reproducing this</h2>
<p>All the numbers in this report come from the data pack through the scripts in the code folder: pressure_model.py builds the pressure score, expected values and rankings; robustness.py runs the seven versions and the 200 resamples (seeded 0 to 199, so the result is the same every time); build_report_data.py, make_figures.py, make_report.py and make_dashboard.py produce the outputs. The whole run takes five to ten minutes on a laptop, most of it the resamples. Player names match the data pack exactly, for example "Namboori Tilak Varma".</p>
<h3>Public information used</h3>
<p class="small">The brief allows public information to be combined with the data. I used it only for squad status, fitness and availability, never inside the model.</p>
<ul class="small">{public}</ul>
</body></html>"""


def find_chrome():
    for name in ("google-chrome", "google-chrome-stable", "chromium", "chromium-browser"):
        path = shutil.which(name)
        if path:
            return path
    return None


def print_pdf(html_path, pdf_path, author, title):
    chrome = find_chrome()
    if not chrome:
        print("Chrome or Chromium not found; open output/report.html and print it to PDF instead.")
        return
    subprocess.run([chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--no-pdf-header-footer",
                    f"--print-to-pdf={pdf_path}", html_path.as_uri()],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        import logging
        logging.getLogger("pypdf").setLevel(logging.ERROR)
        from pypdf import PdfReader, PdfWriter
    except ImportError:
        return
    writer = PdfWriter(clone_from=PdfReader(pdf_path))
    writer.add_metadata({"/Author": author, "/Title": title, "/Creator": author, "/Producer": author})
    with open(pdf_path, "wb") as f:
        writer.write(f)


def main():
    d = json.loads((C.OUTPUT_DIR / "report_data.json").read_text())
    html_path = C.OUTPUT_DIR / "report.html"
    html_path.write_text(build_html(d))
    print_pdf(html_path, C.OUTPUT_DIR / PDF_NAME, d["author"],
              "Who holds their nerve? SupeRR Selector Season 2, Round 1")
    print("Report written to", C.OUTPUT_DIR / PDF_NAME)


if __name__ == "__main__":
    main()
