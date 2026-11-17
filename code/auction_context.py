"""Auction context that is not in the data pack.

Retention status, fitness news and the role each player would fill at RR
come from public reporting around the IPL 2027 retention day
(17 Nov 2026). None of it changes a model rank; it only decides who RR can
actually bid for and what the risk is.
"""

AS_OF = "17 Nov 2026"

# Role at RR and current status for every player in the two top-10 lists.
# Keys are names exactly as they appear in the data pack.
PICKS = {
    "David Miller": dict(
        status="Retained by DC", pool=False,
        fit="A left-handed finisher, which is the exact job RR lost when they let Hetmyer go.",
        flag="Still playing T20s, but no longer on a South Africa central contract."),
    "Namboori Tilak Varma": dict(
        status="Retained by MI", pool=False,
        fit="Indian left-hander for No. 4 or 5, and he would not take an overseas slot."),
    "Tim David": dict(
        status="Retained by RCB", pool=False,
        fit="Pure death-overs hitting. Nobody in the current RR batting group has the pressure sample to compare."),
    "Tristan Stubbs": dict(
        status="Retained by DC", pool=False,
        fit="Overseas middle-order option, though he would be competing with Ferreira and Pretorius for a slot."),
    "Romario Shepherd": dict(
        status="Retained by RCB", pool=False,
        fit="Seam-bowling all-rounder who bats at the death. Most of his evidence is T20I (only 44 IPL pressure balls)."),
    "Shivam Dube": dict(
        status="Retained by CSK", pool=False,
        fit="Indian left-hand hitter for overs 12 to 20."),
    "Rovman Powell": dict(
        status="Retained by KKR", pool=False,
        fit="Another overseas finisher option, but his place in the list is shaky."),
    "Rinku Singh": dict(
        status="Retained by KKR", pool=False,
        fit="Indian finisher. Good overall numbers, yet positive in only 39% of his pressure matches."),
    "Rashid Khan": dict(
        status="Retained by GT", pool=False,
        fit="The only player in both lists: elite leg-spin plus useful lower-order hitting.",
        flag="Plays T20s but has been kept out of Tests to manage his back."),
    "Suryakumar Yadav": dict(
        status="Retained by MI", pool=False,
        fit="Indian 360-degree batter who can lift the scoring rate from any position."),
    "Varun Chakravarthy": dict(
        status="Retained by KKR", pool=False,
        fit="Mystery spin to pair with Bishnoi, who ranks last of 24 bowlers here."),
    "Kuldeep Yadav": dict(
        status="Retained by LSG (traded from DC in June 2026)", pool=False,
        fit="Indian wrist-spinner who takes wickets in tight games.",
        flag="His IPL 2026 was poor (10 wickets at an economy of 10.29), which sits uneasily with his No. 2 rank here."),
    "Mustafizur Rahman": dict(
        status="In the auction pool (released by KKR)", pool=True,
        fit="Left-arm cutters at the death. Would take an overseas slot.",
        flag="KKR released him in January 2026 at the BCCI's request and he played no IPL 2026. Availability for 2027 is unclear."),
    "Matheesha Pathirana": dict(
        status="In the auction pool (released by KKR)", pool=True,
        fit="A specialist death bowler next to Sandeep Sharma, now that Deshpande, Maphaka and Milne have gone.",
        flag="Had hamstring surgery in June 2026; expected back around February 2027."),
    "Jason Holder": dict(
        status="Retained by GT", pool=False,
        fit="Overseas seam all-rounder whose value comes more from wickets than from economy."),
    "Jasprit Bumrah": dict(
        status="Retained by MI", pool=False,
        fit="A proven death bowler to sit alongside Archer.",
        flag="Back from a knee problem; his workload is managed."),
    "Mitchell Santner": dict(
        status="Retained by MI", pool=False,
        fit="Left-arm spin that keeps the run rate down. Shaky spot in the list."),
    "Bhuvneshwar Kumar": dict(
        status="Retained by RCB", pool=False,
        fit="Indian swing bowler for the powerplay and the death. Shaky spot in the list."),
    "Avesh Khan": dict(
        status="In the auction pool (released by LSG)", pool=True,
        fit="Indian death-overs quick, so no overseas slot needed. Shaky spot in the list."),
}

# My shortlist of players RR can actually buy on 16 December.
TARGETS = [
    dict(priority="1", name="Matheesha Pathirana", key="Matheesha Pathirana|bowl", slot="Overseas",
         role="Death bowler",
         why="Bowler No. 5 on my list and in the top 10 in 75% of resamples. He fills the biggest hole in the squad.",
         risk="Coming back from hamstring surgery. I would only bid after seeing the medical report."),
    dict(priority="2", name="Avesh Khan", key="Avesh Khan|bowl", slot="Indian", role="Death bowler",
         why="Bowler No. 10 on my list, with 295 pressure balls. An Indian quick keeps the overseas slots free.",
         risk="Only 36% stable, and his economy is just a little better than expected."),
    dict(priority="3", name="Gudakesh Motie", key="Gudakesh Motie|bowl", slot="Overseas",
         role="Left-arm spinner who bats",
         why="My hidden gem. Under pressure he goes at 7.00 an over against 7.91 expected, with 13 wickets in 96 balls, and he bats at a strike rate of 151 against 124 expected. He went unsold last year, so he should be cheap, and he would replace the spin depth RR lost with Vignesh Puthur.",
         risk="All of it is T20I evidence and the sample is small. He is below my own sample rules, so this is a judgment call, not a model pick."),
    dict(priority="4", name="Nehal Wadhera", key="Nehal Wadhera|bat", slot="Indian", role="Left-hand finisher",
         why="85 pressure balls at a strike rate of 174 against 160 expected, and positive in two out of three pressure matches. Released by PBKS, so a cheap Indian replacement for Hetmyer.",
         risk="Below the sample rules (85 balls)."),
    dict(priority="5", name="M Shahrukh Khan", key="M Shahrukh Khan|bat", slot="Indian", role="Finisher",
         why="100 IPL pressure balls at a strike rate of 182 against 165 expected. Released by GT.",
         risk="Below the sample rules, and positive in 57% of pressure matches."),
    dict(priority="Backup", name="Mustafizur Rahman", key="Mustafizur Rahman|bowl", slot="Overseas",
         role="Left-arm death bowler",
         why="Bowler No. 3 on my list: 7.38 an over against 9.26 expected over 386 pressure balls, 94% stable. On the numbers alone he is the best player in the pool.",
         risk="Only worth a bid if the BCCI confirms he can play."),
]

WATCH = [
    dict(name="Gerald Coetzee", key="Gerald Coetzee|bowl",
         note="Released by SRH. Economy 7.68 against 10.17 expected, but only 68 pressure balls, so I would keep an eye on him rather than chase him."),
]

AVOID = [
    dict(name="Shimron Hetmyer", key="Shimron Hetmyer|bat",
         note="The numbers agree with RR letting him go: strike rate 160.8 against 156.6 expected, positive in only 43% of pressure matches, and he drops below his own ordinary level."),
    dict(name="Tushar Deshpande", key="Tushar Deshpande|bowl",
         note="Also a fair release: 11.71 an over under pressure against 10.77 expected."),
    dict(name="Wanindu Hasaranga", key="Wanindu Hasaranga|bowl",
         note="Economy 8.08 against 7.64 expected, so worse than average, and he missed IPL 2026 injured. He finished 11th once I used the bootstrap order."),
    dict(name="Lockie Ferguson", key="Lockie Ferguson|bowl",
         note="Positive in only 18% of his pressure matches. Big days and bad days, not much in between."),
]

UNAVAILABLE = [
    dict(name="Andre Russell", key="Andre Russell|bat",
         note="Strike rate 174.7 against 143.1 expected, but he has retired from the IPL."),
    dict(name="Adam Zampa", key="Adam Zampa|bowl",
         note="Economy 6.70 against 7.85 expected, but he chose the PSL over IPL 2026 and may not register."),
    dict(name="Mohammad Nabi", key="Mohammad Nabi|bat",
         note="Strike rate 164.5 against 140.2 in T20Is, but he is 41 and went unsold in 2025 and 2026."),
]

# Well-known names I looked at but did not pick, and why in one line.
CHECKED_NOT_PICKED = [
    dict(name="Shreyas Iyer", kind="bat",
         reason="Strong when he does face pressure, but 117 pressure balls over 7 qualifying matches is short of the 150 and 8 I asked for."),
    dict(name="Yashasvi Jaiswal", kind="bat",
         reason="An opener almost never bats in these situations. 12 pressure balls says nothing either way."),
    dict(name="Andre Russell", kind="bat",
         reason="Great numbers, but only 37 pressure balls in 2025-26 (40 needed), and he has retired from the IPL anyway."),
    dict(name="Heinrich Klaasen", kind="bat",
         reason="The closest miss. 188 pressure balls when an IPL-only record needs 200. On the numbers he would be in the conversation."),
    dict(name="Sunil Narine", kind="bowl",
         reason="Economy 5.05 against 8.01 expected is outstanding, but 145 pressure balls is under the 200 an IPL-only record needs."),
    dict(name="Axar Patel", kind="bat",
         reason="He qualifies with both bat and ball but ranks in the bottom half of both lists. Steady, not a pressure specialist."),
    dict(name="Kagiso Rabada", kind="bowl",
         reason="He qualifies, but his economy under pressure (10.00) is right at what an average bowler would concede (9.97)."),
    dict(name="Jofra Archer", kind="bowl",
         reason="Already at RR. 139 pressure balls with a good economy, just short of the 150 needed, so the data cannot call him proven yet."),
]

PURSE_NOTE = ("RR's remaining purse is reported as Rs 27.05 crore by ESPNcricinfo and the Times of India, "
              "but India Today lists Rs 22.05 crore. I have used 27.05 and would confirm it before the auction.")

# Outlets used for the status facts above (named, not linked).
PUBLIC_INFORMATION = [
    "IPL 2027 retention and release lists, purse figures and the auction date: India Today, ESPNcricinfo, Cricbuzz and the Times of India (17 Nov 2026).",
    "Mustafizur Rahman's release at the BCCI's request: BBC Sport (Jan 2026).",
    "Matheesha Pathirana's hamstring surgery and expected return: Cricbuzz and RevSportz.",
    "Kuldeep Yadav's trade to LSG and his IPL 2026 figures: ESPN.",
    "David Miller's contract status: ESPNcricinfo. Jasprit Bumrah's fitness: Sportstar. Rashid Khan's Test absence: ICC.",
    "Andre Russell's IPL retirement and Wanindu Hasaranga's IPL 2026 injury: ESPNcricinfo.",
    "Gudakesh Motie going unsold: Rediff. Mohammad Nabi's auction history: The Cricscope. Adam Zampa choosing the PSL: Times of India.",
]
