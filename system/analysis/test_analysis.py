#!/usr/bin/env python3
"""
test_analysis.py -- unittest coverage for the deterministic analysis layer.

Run:  python3 test_analysis.py                      (from system/analysis)
      python3 -m unittest discover -s <dir> -t <dir> -p 'test_*.py'
      (-t is required: system/analysis is a plain directory, not a package, so
       unittest needs it named as the top-level dir too.)

Fixtures are deliberately realistic: Andrew's actual roster, the actual 10-team
priority order, the actual keeper costs from league_config.json. Where the real
state file exists on disk it is loaded and exercised too, so a schema drift in
state_builder.py breaks a test here rather than breaking a Tuesday.

No network. No non-stdlib imports.
"""

from __future__ import annotations

import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import scoring  # noqa: E402
import opponent_pressure as op  # noqa: E402
import waiver_contention as wc  # noqa: E402
import keeper_equity as ke  # noqa: E402

STATE_PATH = os.path.join(HERE, "..", "state", "week_0.json")
CONFIG_PATH = os.path.join(HERE, "..", "league_config.json")


def load_json(path):
    try:
        with open(path) as fh:
            return json.load(fh)
    except (IOError, OSError, ValueError):
        return None


# ==========================================================================
# Fixtures
# ==========================================================================

# A rival whose RB1 is out and whose bench is bare. This is the archetype the
# whole opponent model exists to catch.
DESPERATE_TEAM = {
    "roster_id": 9,
    "owner": "DannyBC1",
    "team_name": None,
    "waiver_priority": 1,
    "starters": [
        {"slot": "QB", "player_id": "q1", "name": "Caleb Williams", "pos": "QB", "injury_status": None},
        {"slot": "RB", "player_id": "r1", "name": "Broken Back", "pos": "RB", "injury_status": "Out"},
        {"slot": "RB", "player_id": "r2", "name": "Steady Back", "pos": "RB", "injury_status": None},
        {"slot": "WR", "player_id": "w1", "name": "Good Wideout", "pos": "WR", "injury_status": None},
        {"slot": "WR", "player_id": "w2", "name": "Fine Wideout", "pos": "WR", "injury_status": None},
        {"slot": "TE", "player_id": "t1", "name": "A Tight End", "pos": "TE", "injury_status": None},
        {"slot": "DEF", "player_id": "CHI", "name": "Chicago Bears", "pos": "DEF", "injury_status": None},
    ],
    "bench": [
        {"player_id": "w3", "name": "Spare Wideout", "pos": "WR", "injury_status": None},
        {"player_id": "q2", "name": "Backup QB", "pos": "QB", "injury_status": None},
    ],
}

# Same injury, but they have a genuine replacement sitting on the bench. External
# pressure should be materially lower -- they fix it in house.
COVERED_TEAM = json.loads(json.dumps(DESPERATE_TEAM))
COVERED_TEAM["owner"] = "havicht"
COVERED_TEAM["roster_id"] = 3
COVERED_TEAM["bench"].append(
    {"player_id": "r3", "name": "Excellent Handcuff", "pos": "RB", "injury_status": None})

HEALTHY_TEAM = json.loads(json.dumps(DESPERATE_TEAM))
HEALTHY_TEAM["owner"] = "tlekes"
HEALTHY_TEAM["roster_id"] = 1
HEALTHY_TEAM["starters"][1] = {"slot": "RB", "player_id": "r0", "name": "Healthy Back",
                               "pos": "RB", "injury_status": None}
HEALTHY_TEAM["bench"].append(
    {"player_id": "r3", "name": "Excellent Handcuff", "pos": "RB", "injury_status": None})

RECENT_SCORING = {
    "r0": [13.0, 11.5, 12.4],   # the healthy team's RB1, comfortably above replacement
    "q1": [21.4, 24.0, 19.8],
    "r1": [4.1, 2.0, 0.0],
    "r2": [12.5, 14.1, 11.0],
    "w1": [16.2, 18.9, 14.4],
    "w2": [11.0, 9.8, 12.2],
    "t1": [8.1, 7.9, 9.4],
    "w3": [6.2, 4.1, 5.0],
    "q2": [0.0, 0.0, 0.0],
    "r3": [13.8, 15.1, 12.9],   # the handcuff is legitimately good
}

PRIORITY_ORDER = ["DannyBC1", "jpalmeri1616", "LoochCarluccio", "andrewroth32",
                  "PeterCrisileo", "havicht", "pdustin", "jomud", "Edeecher", "tlekes"]

FA_POOL = [
    {"player": "Dylan Sampson", "position": "RB", "value": 13.5, "available": True},
    {"player": "Keon Coleman", "position": "WR", "value": 11.8, "available": True},
    {"player": "Michael Penix", "position": "QB", "value": 17.2, "available": True},
    {"player": "Jack Bech", "position": "WR", "value": 8.4, "available": True},
]


# ==========================================================================
# scoring.py
# ==========================================================================

class TestScoring(unittest.TestCase):

    def test_first_down_bonus_is_exact(self):
        line = {"rec": 7, "rec_yd": 84, "rec_fd": 5}
        # 7*0.5 + 84*0.1 + 5*0.5
        self.assertAlmostEqual(scoring.score_stat_line(line, position="WR"), 14.4, places=3)
        self.assertAlmostEqual(scoring.first_down_bonus(line), 2.5, places=3)
        self.assertAlmostEqual(scoring.half_ppr_points(line), 11.9, places=3)

    def test_rushing_first_downs_score_too(self):
        line = {"rush_att": 18, "rush_yd": 92, "rush_fd": 6, "rush_td": 1}
        # 9.2 + 6.0 + 3.0 ; rush_att is not itself a scoring category
        self.assertAlmostEqual(scoring.score_stat_line(line, position="RB"), 18.2, places=3)

    def test_possession_receiver_gains_more_than_deep_threat(self):
        """The single most exploitable quirk of this league: same half-PPR, very
        different league points."""
        slot = {"rec": 8, "rec_yd": 70, "rec_fd": 6}
        deep = {"rec": 3, "rec_yd": 95, "rec_fd": 2}
        self.assertAlmostEqual(scoring.half_ppr_points(slot), 11.0, places=3)
        self.assertAlmostEqual(scoring.half_ppr_points(deep), 11.0, places=3)
        self.assertGreater(scoring.score_stat_line(slot), scoring.score_stat_line(deep))
        self.assertAlmostEqual(
            scoring.score_stat_line(slot) - scoring.score_stat_line(deep), 2.0, places=3)

    def test_interception_is_minus_one_not_minus_two(self):
        line = {"pass_yd": 250, "pass_td": 2, "pass_int": 2}
        # 10 + 8 - 2
        self.assertAlmostEqual(scoring.score_stat_line(line, position="QB"), 16.0, places=3)

    def test_unknown_keys_are_reported_not_crashed(self):
        out = scoring.score_breakdown({"rec": 2, "bogus_new_sleeper_key": 9}, position="WR")
        self.assertIn("bogus_new_sleeper_key", out["unscored_keys"])
        self.assertAlmostEqual(out["total"], 1.0, places=3)

    def test_def_scoring_carries_the_unverified_warning(self):
        out = scoring.score_breakdown({"sack": 3, "int": 1, "pts_allow": 10}, position="DEF")
        self.assertTrue(out["warnings"])
        self.assertIn("provisional", out["warnings"][0])
        # 3 sacks + 1 int + the 7-13 points-allowed bucket
        self.assertAlmostEqual(out["total"], 3 + 2 + 4, places=3)

    def test_estimate_first_downs_prefers_explicit_then_volume(self):
        explicit = scoring.estimate_first_downs({"rec": 6, "rec_fd": 4}, "WR")
        self.assertEqual(explicit["rec_fd"], 4.0)
        self.assertEqual(explicit["method"], "explicit")
        derived = scoring.estimate_first_downs({"rec": 6}, "WR")
        self.assertEqual(derived["method"], "per_reception_rate")
        self.assertAlmostEqual(derived["rec_fd"], 6 * 0.62, places=2)

    def test_half_ppr_projection_converts_upward(self):
        conv = scoring.league_points_from_half_ppr(12.0, "WR", rec=6)
        self.assertGreater(conv["league_points"], 12.0)
        self.assertAlmostEqual(conv["first_down_points"], 0.5 * round(6 * 0.62, 2), places=2)

    def test_qb_projection_gains_back_the_interception_difference(self):
        conv = scoring.league_points_from_half_ppr(18.0, "QB", pass_int=1.0)
        self.assertAlmostEqual(conv["interception_adjustment"], 1.0, places=3)

    def test_rank_projections_moves_the_chain_mover_up(self):
        players = [
            {"name": "Deep Threat", "position": "WR", "half_ppr_ppg": 12.5, "rec_pg": 3.5,
             "profile": "deep_threat"},
            {"name": "Chain Mover", "position": "WR", "half_ppr_ppg": 12.0, "rec_pg": 7.0,
             "profile": "possession"},
        ]
        ranked = scoring.rank_projections(players)
        self.assertEqual(ranked[0]["name"], "Chain Mover")
        self.assertEqual(ranked[0]["rank_delta"], 1)  # rose one spot vs half-PPR

    def test_load_scoring_reads_the_real_config_if_present(self):
        table = scoring.load_scoring(CONFIG_PATH)
        self.assertEqual(table["rec_fd"], 0.5)
        self.assertEqual(table["rush_fd"], 0.5)
        self.assertEqual(table["rec"], 0.5)

    def test_load_scoring_survives_a_missing_config(self):
        table = scoring.load_scoring("/nonexistent/league_config.json")
        self.assertEqual(table["rec_fd"], 0.5)


# ==========================================================================
# opponent_pressure.py
# ==========================================================================

class TestOpponentPressure(unittest.TestCase):

    def test_injury_severity_mapping(self):
        self.assertEqual(op.injury_severity("Out"), 1.0)
        self.assertEqual(op.injury_severity("IR"), 1.0)
        self.assertEqual(op.injury_severity("Questionable"), 0.35)
        self.assertEqual(op.injury_severity(None), 0.0)
        self.assertEqual(op.injury_severity(""), 0.0)
        # an unrecognised flag is still a flag
        self.assertEqual(op.injury_severity("Some-New-Sleeper-Status"), 0.5)

    def test_vacancy_two_questionables_beat_one(self):
        one, _ = op.vacancy_pressure([{"player_id": "a", "injury_status": "Questionable"}])
        two, _ = op.vacancy_pressure([{"player_id": "a", "injury_status": "Questionable"},
                                      {"player_id": "b", "injury_status": "Questionable"}])
        self.assertGreater(two, one)
        self.assertLessEqual(two, 1.0)

    def test_vacancy_bye_counts_as_a_hole(self):
        v, ev = op.vacancy_pressure([{"player_id": "a", "name": "Guy", "injury_status": None}],
                                    bye_player_ids={"a"})
        self.assertAlmostEqual(v, op.BYE_SEVERITY, places=3)
        self.assertTrue(any("bye" in e for e in ev))

    def test_no_starter_at_all_is_total_vacancy(self):
        v, _ = op.vacancy_pressure([])
        self.assertEqual(v, 1.0)

    def test_healthy_settled_team_has_near_zero_pressure(self):
        block = op.compute_team_pressure(HEALTHY_TEAM, recent_scoring=RECENT_SCORING, week=8)
        for pos, val in block["pressure"].items():
            self.assertLess(val, 0.3, "%s should be quiet, got %.2f" % (pos, val))
        self.assertEqual(block["need_positions"], [])

    def test_injured_rb_with_empty_bench_is_high_pressure(self):
        block = op.compute_team_pressure(DESPERATE_TEAM, recent_scoring=RECENT_SCORING, week=8)
        self.assertGreater(block["pressure"]["RB"], 0.4)
        self.assertIn("RB", block["need_positions"])
        self.assertIn("Broken Back", block["vulnerable_starters"])

    def test_depth_is_the_multiplier_that_separates_need_from_action(self):
        """Identical injury, different bench. The covered team should be much
        less likely to hit the wire -- that is the entire point of the depth
        term being multiplicative rather than additive."""
        desperate = op.compute_team_pressure(DESPERATE_TEAM, recent_scoring=RECENT_SCORING, week=8)
        covered = op.compute_team_pressure(COVERED_TEAM, recent_scoring=RECENT_SCORING, week=8)
        d_row = next(r for r in desperate["pressure_breakdown"] if r["position"] == "RB")
        c_row = next(r for r in covered["pressure_breakdown"] if r["position"] == "RB")
        self.assertAlmostEqual(d_row["vacancy"], c_row["vacancy"], places=3)  # same injury
        self.assertGreater(d_row["depth"], c_row["depth"])                    # different bench
        self.assertGreater(desperate["pressure"]["RB"], covered["pressure"]["RB"] * 1.3)

    def test_role_pressure_is_external_and_moves_the_score(self):
        """Role pressure cannot be derived from Sleeper data, so it must be
        supplied. Supplying it must actually change the answer, and its absence
        must be reported as a data gap rather than silently scored as zero."""
        base = op.compute_team_pressure(HEALTHY_TEAM, recent_scoring=RECENT_SCORING, week=8)
        with_signal = op.compute_team_pressure(
            HEALTHY_TEAM, recent_scoring=RECENT_SCORING, week=8,
            role_signals={"WR": {"score": 0.8, "evidence": "beat writer: routes down 22%"}})
        self.assertGreater(with_signal["pressure"]["WR"], base["pressure"]["WR"])
        wr_row = next(r for r in with_signal["pressure_breakdown"] if r["position"] == "WR")
        self.assertEqual(wr_row["role"], 0.8)
        self.assertIn("routes down 22%", wr_row["evidence"])
        self.assertTrue(any("no role signal" in g for g in base["data_gaps"]))

    def test_role_signal_accepted_keyed_by_player_id_or_as_a_list(self):
        by_pid = op.compute_team_pressure(HEALTHY_TEAM, recent_scoring=RECENT_SCORING,
                                          week=8, role_signals={"w1": 0.7})
        as_list = op.compute_team_pressure(
            HEALTHY_TEAM, recent_scoring=RECENT_SCORING, week=8,
            role_signals=[{"player_id": "w1", "score": 0.7, "evidence": "snaps down"}])
        self.assertAlmostEqual(by_pid["pressure"]["WR"], as_list["pressure"]["WR"], places=3)
        self.assertGreater(by_pid["pressure"]["WR"], 0.0)

    def test_performance_pressure_is_damped_in_small_sample_weeks(self):
        weak = {"r2": [3.0, 2.5, 4.0], "r1": [3.0, 2.0, 1.0]}
        team = json.loads(json.dumps(HEALTHY_TEAM))
        early = op.compute_position_pressure("RB", team["starters"][1:3], team["bench"],
                                             recent_scoring=weak, week=2)
        late = op.compute_position_pressure("RB", team["starters"][1:3], team["bench"],
                                            recent_scoring=weak, week=9)
        self.assertGreater(late["performance"], early["performance"])
        self.assertAlmostEqual(early["performance"], late["performance"] * 0.6, places=3)

    def test_injured_starters_do_not_double_count_into_performance(self):
        """A player who is Out already scores as vacancy. Counting his zeroes as
        performance too would charge the same hole twice."""
        row = op.compute_position_pressure(
            "RB", DESPERATE_TEAM["starters"][1:3], DESPERATE_TEAM["bench"],
            recent_scoring=RECENT_SCORING, week=8)
        # r1 is Out and awful; r2 is healthy and above replacement -> ~no perf pressure
        self.assertLess(row["performance"], 0.15)
        self.assertGreaterEqual(row["vacancy"], 1.0)

    def test_pressure_is_always_bounded(self):
        nightmare = {
            "roster_id": 99, "owner": "nobody",
            "starters": [{"slot": "RB", "player_id": "x", "name": "X", "pos": "RB",
                          "injury_status": "IR"},
                         {"slot": "RB", "player_id": "y", "name": "Y", "pos": "RB",
                          "injury_status": "Out"}],
            "bench": [],
        }
        block = op.compute_team_pressure(nightmare, recent_scoring={"x": [0.0], "y": [0.0]},
                                         role_signals={"RB": 1.0}, week=10)
        for val in block["pressure"].values():
            self.assertGreaterEqual(val, 0.0)
            self.assertLessEqual(val, 1.0)
        self.assertGreater(block["pressure"]["RB"], 0.9)

    def test_confidence_tracks_what_data_actually_arrived(self):
        blind = op.compute_team_pressure(DESPERATE_TEAM)
        partial = op.compute_team_pressure(DESPERATE_TEAM, recent_scoring=RECENT_SCORING)
        full = op.compute_team_pressure(DESPERATE_TEAM, recent_scoring=RECENT_SCORING,
                                        role_signals={"RB": 0.5})
        self.assertEqual(blind["confidence"], "low")
        self.assertEqual(partial["confidence"], "medium")
        self.assertEqual(full["confidence"], "high")

    def test_predicted_claims_are_ordered_and_positionally_relevant(self):
        block = op.compute_team_pressure(DESPERATE_TEAM, recent_scoring=RECENT_SCORING, week=8)
        claims = op.predicted_claims_from_pressure(block, FA_POOL, top_n=3)
        self.assertTrue(claims)
        self.assertEqual(claims[0]["position"], "RB")
        likelihoods = [c["likelihood"] for c in claims]
        self.assertEqual(likelihoods, sorted(likelihoods, reverse=True))
        for c in claims:
            self.assertTrue(0.0 <= c["likelihood"] <= 1.0)
            self.assertTrue(c["why"])

    def test_output_matches_the_weekly_js_opponent_schema(self):
        block = op.compute_team_pressure(DESPERATE_TEAM, recent_scoring=RECENT_SCORING, week=8)
        for key in ("pressure", "pressure_breakdown", "need_positions",
                    "surplus_positions", "vulnerable_starters", "confidence", "data_gaps"):
            self.assertIn(key, block)
        for row in block["pressure_breakdown"]:
            for key in ("position", "vacancy", "performance", "role", "depth", "evidence"):
                self.assertIn(key, row)

    @unittest.skipUnless(os.path.exists(STATE_PATH), "state/week_0.json not built yet")
    def test_runs_against_the_real_state_file(self):
        state = load_json(STATE_PATH)
        out = op.compute_league_pressure(state)
        self.assertEqual(len(out), len(state["teams"]))
        for rid, block in out.items():
            self.assertIn("pressure", block)
            for pos, val in block["pressure"].items():
                self.assertTrue(0.0 <= val <= 1.0, "%s %s = %s" % (rid, pos, val))


# ==========================================================================
# waiver_contention.py
# ==========================================================================

class TestWaiverContention(unittest.TestCase):

    def setUp(self):
        self.targets = [dict(t) for t in FA_POOL]
        self.rivals = {
            "DannyBC1": [{"player": "Dylan Sampson", "likelihood": 0.9}],
            "jpalmeri1616": [{"player": "Dylan Sampson", "likelihood": 0.7},
                             {"player": "Michael Penix", "likelihood": 0.4}],
            "LoochCarluccio": [{"player": "Keon Coleman", "likelihood": 0.5}],
            # behind Andrew -- must not affect anything
            "tlekes": [{"player": "Jack Bech", "likelihood": 1.0}],
        }

    def test_normalise_handles_every_upstream_shape(self):
        a = wc.normalise_rival_claims({"t": ["Guy A", "Guy B"]})
        self.assertEqual(a["t"][0][0], "Guy A")
        self.assertAlmostEqual(a["t"][0][1], 0.6)
        b = wc.normalise_rival_claims({"t": [{"player": "Guy A", "likelihood": 0.3}]})
        self.assertEqual(b["t"], [("Guy A", 0.3)])
        c = wc.normalise_rival_claims([{"team": "t", "predicted_claims":
                                        [{"player": "Guy A", "likelihood": 0.9}]}])
        self.assertEqual(c["t"], [("Guy A", 0.9)])

    def test_normalise_is_idempotent(self):
        once = wc.normalise_rival_claims(self.rivals)
        twice = wc.normalise_rival_claims(once)
        self.assertEqual(once, twice)

    def test_teams_ahead_from_order_and_from_priority_number(self):
        ahead, idx = wc.teams_ahead(PRIORITY_ORDER, "andrewroth32")
        self.assertEqual(ahead, PRIORITY_ORDER[:3])
        self.assertEqual(idx, 3)
        ahead2, idx2 = wc.teams_ahead(PRIORITY_ORDER, None, andrew_priority=4)
        self.assertEqual(ahead2, ahead)
        self.assertEqual(idx2, 3)

    def test_uncontested_player_always_survives(self):
        probs = wc.simulate_rolling_priority(self.targets, PRIORITY_ORDER, self.rivals,
                                             andrew="andrewroth32", trials=800)
        self.assertEqual(probs["Jack Bech"], 1.0)

    def test_heavily_contested_player_rarely_survives(self):
        probs = wc.simulate_rolling_priority(self.targets, PRIORITY_ORDER, self.rivals,
                                             andrew="andrewroth32", trials=2000)
        # 1 - 0.9 = 0.10 from DannyBC1 alone, before jpalmeri
        self.assertLess(probs["Dylan Sampson"], 0.12)
        self.assertGreater(probs["Dylan Sampson"], 0.0)

    def test_single_rival_single_target_matches_the_closed_form_exactly(self):
        targets = [{"player": "Solo", "position": "RB", "value": 10.0, "available": True}]
        rivals = {"DannyBC1": [{"player": "Solo", "likelihood": 0.4}]}
        sim = wc.simulate_rolling_priority(targets, PRIORITY_ORDER, rivals,
                                           andrew="andrewroth32", trials=6000)
        closed = wc.survival_closed_form(targets, PRIORITY_ORDER, rivals, andrew="andrewroth32")
        self.assertAlmostEqual(closed["Solo"], 0.6, places=3)
        self.assertAlmostEqual(sim["Solo"], 0.6, delta=0.03)

    def test_teams_behind_andrew_cannot_take_his_target(self):
        """tlekes wants Jack Bech with certainty but picks 10th. He is irrelevant,
        and a model that says otherwise would misorder the whole sheet."""
        probs = wc.simulate_rolling_priority(self.targets, PRIORITY_ORDER, self.rivals,
                                             andrew="andrewroth32", trials=800)
        self.assertEqual(probs["Jack Bech"], 1.0)

    def test_first_priority_means_everything_survives(self):
        order = ["andrewroth32"] + [t for t in PRIORITY_ORDER if t != "andrewroth32"]
        probs = wc.simulate_rolling_priority(self.targets, order, self.rivals,
                                             andrew="andrewroth32", trials=500)
        self.assertTrue(all(p == 1.0 for p in probs.values()), probs)

    def test_survival_is_monotonic_in_rival_appetite(self):
        low = wc.simulate_rolling_priority(
            self.targets, PRIORITY_ORDER,
            {"DannyBC1": [{"player": "Keon Coleman", "likelihood": 0.2}]},
            andrew="andrewroth32", trials=3000)["Keon Coleman"]
        high = wc.simulate_rolling_priority(
            self.targets, PRIORITY_ORDER,
            {"DannyBC1": [{"player": "Keon Coleman", "likelihood": 0.8}]},
            andrew="andrewroth32", trials=3000)["Keon Coleman"]
        self.assertGreater(low, high)

    def test_a_rival_spending_priority_elsewhere_frees_up_the_board(self):
        """The coupling a closed-form product cannot see: if DannyBC1 burns his
        claim on Sampson, his interest in Coleman stops mattering."""
        coupled = wc.simulate_rolling_priority(
            self.targets, PRIORITY_ORDER,
            {"DannyBC1": [{"player": "Dylan Sampson", "likelihood": 1.0},
                          {"player": "Keon Coleman", "likelihood": 1.0}]},
            andrew="andrewroth32", trials=1500, allow_multiple_wins=False)["Keon Coleman"]
        self.assertEqual(coupled, 1.0)

    def test_simulation_is_deterministic_for_a_given_seed(self):
        a = wc.simulate_rolling_priority(self.targets, PRIORITY_ORDER, self.rivals,
                                         andrew="andrewroth32", trials=500, seed=42)
        b = wc.simulate_rolling_priority(self.targets, PRIORITY_ORDER, self.rivals,
                                         andrew="andrewroth32", trials=500, seed=42)
        self.assertEqual(a, b)

    def test_availability_gate_rejects_unverified_players(self):
        """Plan Part 7's most damaging failure mode: recommending a player who is
        not actually a free agent. The gate lives in code, not in a prompt."""
        targets = self.targets + [{"player": "Ghost Player", "position": "WR", "value": 99.0}]
        rep = wc.contention_report(targets, PRIORITY_ORDER, self.rivals,
                                   andrew="andrewroth32", trials=300)
        names = [r["player"] for r in rep["claim_sheet"]]
        self.assertNotIn("Ghost Player", names)
        self.assertEqual(rep["rejected_unverified"][0]["player"], "Ghost Player")
        self.assertTrue(any("Hard gate" in f for f in rep["flags"]))

    def test_claim_sheet_is_ordered_and_complete(self):
        rep = wc.contention_report(self.targets, PRIORITY_ORDER, self.rivals,
                                   andrew="andrewroth32", trials=800)
        sheet = rep["claim_sheet"]
        self.assertEqual([r["order"] for r in sheet], list(range(1, len(sheet) + 1)))
        scores = [r["priority_score"] for r in sheet]
        self.assertEqual(scores, sorted(scores, reverse=True))
        self.assertEqual(rep["waiver_mode_used"], "rolling_priority")
        self.assertEqual(rep["andrew_priority"], 4)
        self.assertEqual(rep["teams_ahead_of_andrew"], PRIORITY_ORDER[:3])

    def test_unreachable_player_is_demoted_and_flagged(self):
        rep = wc.contention_report(self.targets, PRIORITY_ORDER, self.rivals,
                                   andrew="andrewroth32", trials=2000)
        order = {r["player"]: r["order"] for r in rep["claim_sheet"]}
        # Sampson is the most valuable RB on the board but essentially unreachable
        self.assertGreater(order["Dylan Sampson"], 1)
        self.assertIn("Dylan Sampson", rep["do_not_bother"])
        self.assertIn("Jack Bech", rep["quiet_wins"])

    def test_keeper_surplus_lifts_a_claim_up_the_sheet(self):
        plain = wc.contention_report(self.targets, PRIORITY_ORDER, {}, andrew="andrewroth32",
                                     trials=300)
        boosted_targets = [dict(t) for t in self.targets]
        for t in boosted_targets:
            if t["player"] == "Jack Bech":
                t["keeper_surplus_rounds"] = 9
        boosted = wc.contention_report(boosted_targets, PRIORITY_ORDER, {},
                                       andrew="andrewroth32", trials=300)
        before = {r["player"]: r["order"] for r in plain["claim_sheet"]}["Jack Bech"]
        after = {r["player"]: r["order"] for r in boosted["claim_sheet"]}["Jack Bech"]
        self.assertLess(after, before)

    def test_contention_map_names_the_expected_winner(self):
        rep = wc.contention_report(self.targets, PRIORITY_ORDER, self.rivals,
                                   andrew="andrewroth32", trials=500)
        row = next(r for r in rep["contention_map"] if r["player"] == "Dylan Sampson")
        self.assertEqual(row["expected_winner"], "DannyBC1")
        self.assertIn("jpalmeri1616", row["interested_teams"])

    # ---- FAAB mode -------------------------------------------------------

    def test_faab_bids_scale_with_contention(self):
        """Note the mode difference this test pins down: under FAAB there is no
        priority order, so tlekes -- irrelevant in the rolling-priority model
        because he picks 10th -- becomes a real bidder on Jack Bech."""
        targets = self.targets + [{"player": "Nobody Wants Him", "position": "WR",
                                   "value": 7.0, "available": True}]
        rec = wc.faab_recommendations(targets, self.rivals, andrew="andrewroth32",
                                      trials=1500)
        self.assertGreater(rec["Dylan Sampson"]["bid_pct"], rec["Jack Bech"]["bid_pct"])
        self.assertEqual(rec["Jack Bech"]["interested_teams"], ["tlekes"])
        self.assertEqual(rec["Nobody Wants Him"]["bid_pct"], 1)
        self.assertEqual(rec["Nobody Wants Him"]["interested_teams"], [])
        self.assertIn("no rival", rec["Nobody Wants Him"]["notes"])

    def test_faab_respects_a_drained_rival_budget(self):
        rich = wc.faab_recommendations(self.targets, self.rivals, andrew="andrewroth32",
                                       budgets={"DannyBC1": 100, "jpalmeri1616": 100},
                                       trials=1500)["Dylan Sampson"]
        broke = wc.faab_recommendations(self.targets, self.rivals, andrew="andrewroth32",
                                        budgets={"DannyBC1": 2, "jpalmeri1616": 3},
                                        trials=1500)["Dylan Sampson"]
        self.assertLess(broke["bid_pct"], rich["bid_pct"])
        self.assertLess(broke["expected_top_rival_bid"], rich["expected_top_rival_bid"])

    def test_faab_bid_is_capped_by_budget_policy(self):
        rec = wc.faab_recommendations(
            self.targets,
            {"a": [{"player": "Dylan Sampson", "likelihood": 1.0}],
             "b": [{"player": "Dylan Sampson", "likelihood": 1.0}]},
            andrew="andrewroth32", andrew_budget=100, max_share_of_budget=0.25,
            trials=1000)
        self.assertLessEqual(rec["Dylan Sampson"]["bid_pct"], 25)

    def test_both_mode_runs_both_models_and_flags_the_ambiguity(self):
        rep = wc.contention_report(self.targets, PRIORITY_ORDER, self.rivals,
                                   andrew="andrewroth32", mode="both", trials=500)
        self.assertEqual(rep["waiver_mode_used"], "both_ambiguous")
        self.assertIn("faab_fallback", rep)
        self.assertTrue(any("AMBIGUOUS" in f for f in rep["flags"]))
        for row in rep["claim_sheet"]:
            self.assertIsNotNone(row["faab_bid_pct"])

    def test_faab_mode_uses_win_probability_as_the_probability(self):
        rep = wc.contention_report(self.targets, PRIORITY_ORDER, self.rivals,
                                   andrew="andrewroth32", mode="faab", trials=800)
        self.assertEqual(rep["waiver_mode_used"], "faab")
        for row in rep["claim_sheet"]:
            self.assertTrue(0.0 <= row["probability_reaches_andrew"] <= 1.0)

    def test_missing_andrew_in_the_order_is_flagged_not_silently_wrong(self):
        rep = wc.contention_report(self.targets, PRIORITY_ORDER, self.rivals,
                                   andrew="someone_who_left_the_league", trials=300)
        self.assertTrue(any("could not be located" in f for f in rep["flags"]))

    def test_priority_disagreement_is_flagged(self):
        rep = wc.contention_report(self.targets, PRIORITY_ORDER, self.rivals,
                                   andrew="andrewroth32", andrew_priority=7, trials=300)
        self.assertTrue(any("disagrees" in f for f in rep["flags"]))
        self.assertEqual(rep["andrew_priority"], 4)  # priority_order wins

    def test_rival_missing_from_the_priority_order_is_flagged(self):
        rivals = dict(self.rivals)
        rivals["mystery_team"] = [{"player": "Keon Coleman", "likelihood": 1.0}]
        rep = wc.contention_report(self.targets, PRIORITY_ORDER, rivals,
                                   andrew="andrewroth32", trials=300)
        self.assertTrue(any("mystery_team" in f for f in rep["flags"]))
        self.assertTrue(any("optimistic" in f for f in rep["flags"]))

    def test_empty_inputs_do_not_explode(self):
        rep = wc.contention_report([], PRIORITY_ORDER, {}, andrew="andrewroth32", trials=50)
        self.assertEqual(rep["claim_sheet"], [])
        self.assertEqual(rep["do_not_bother"], [])


# ==========================================================================
# keeper_equity.py
# ==========================================================================

class TestKeeperEquity(unittest.TestCase):

    def test_waiver_add_costs_a_twelfth(self):
        cost = ke.keeper_cost({"acquisition": "waiver"})
        self.assertEqual(cost["cost_round"], 12)
        self.assertTrue(cost["eligible"])
        self.assertIn("12th", cost["notes"][0])

    def test_kept_round_escalates_n_minus_1(self):
        # A repeat keep costs one round cheaper in NUMBER than last year (N-1).
        cost = ke.keeper_cost({"acquisition": "keeper", "kept_at_round": 12,
                               "draft_round": 3})
        self.assertEqual(cost["cost_round"], 11)

    def test_n_minus_1_floors_at_r1_and_stays_eligible(self):
        # Kept @R2 last year -> escalates to R1: still valid, but final eligible year.
        cost = ke.keeper_cost({"acquisition": "keeper", "kept_at_round": 2,
                               "consecutive_years_kept": 1})
        self.assertEqual(cost["cost_round"], 1)
        self.assertTrue(cost["eligible"])
        self.assertTrue(cost["is_final_eligible_year"])

    def test_first_rounders_are_never_keepable(self):
        cost = ke.keeper_cost({"acquisition": "draft", "draft_round": 1})
        self.assertFalse(cost["eligible"])
        self.assertIn("1st-round", cost["ineligible_reason"])

    def test_three_consecutive_year_cap_is_enforced(self):
        ok = ke.keeper_cost({"acquisition": "keeper", "kept_at_round": 12,
                             "consecutive_years_kept": 2})
        self.assertTrue(ok["eligible"])
        self.assertTrue(ok["is_final_eligible_year"])
        self.assertEqual(ok["consecutive_years_if_kept"], 3)
        capped = ke.keeper_cost({"acquisition": "keeper", "kept_at_round": 12,
                                 "consecutive_years_kept": 3})
        self.assertFalse(capped["eligible"])
        self.assertIn("cap", capped["ineligible_reason"])

    def test_forfeited_pick_matches_the_real_league_config_numbers(self):
        """Slot 8, 10 teams, snake. league_config records Walker R4 -> pick 33,
        Nix R12 -> 113, Jameson Williams R14 -> 133. If this drifts, the whole
        keeper board is quoting the wrong picks."""
        self.assertEqual(ke.forfeited_overall_pick(4, 8), 33)
        self.assertEqual(ke.forfeited_overall_pick(12, 8), 113)
        self.assertEqual(ke.forfeited_overall_pick(14, 8), 133)
        self.assertEqual(ke.forfeited_overall_pick(1, 8), 8)     # odd round: straight
        self.assertEqual(ke.forfeited_overall_pick(2, 8), 13)    # even round: reversed

    def test_market_round_from_ppg_and_from_tier(self):
        self.assertEqual(ke.market_round("RB", tier="RB2"), 5)
        self.assertEqual(ke.market_round("QB", projected_ppg=18.4), 5)
        self.assertEqual(ke.market_round("WR", projected_ppg=25.0), 1)
        # unprojected player is worse than the last pick, so no keeper cost is a bargain
        self.assertGreater(ke.market_round("WR"), ke.DRAFT_ROUNDS)

    def test_superflex_prices_quarterbacks_aggressively(self):
        """With ~17 starting QBs in a 10-team superflex, a QB and a WR of the
        same raw ppg are not remotely the same asset. A generic ADP table would
        get Bo Nix's keeper value badly wrong."""
        self.assertLess(ke.market_round("QB", projected_ppg=19.0),
                        ke.market_round("WR", projected_ppg=19.0) + 4)
        self.assertLessEqual(ke.market_round("QB", projected_ppg=18.0), 5)

    def test_the_headline_case_breakout_waiver_rb(self):
        """A Week-7 waiver claim who finishes as an RB2: keepable for a 12th
        against a 5th-round market price."""
        row = ke.waiver_add_equity({"player": "Breakout Back", "position": "RB",
                                    "projected_ppg": 13.2})
        self.assertEqual(row["keeper_cost_round"], 12)
        self.assertEqual(row["market_round"], 5)
        self.assertEqual(row["surplus_rounds"], 7)
        self.assertEqual(row["surplus"], "very high")
        self.assertEqual(row["keeper_equity_2027"], "very high")

    def test_same_production_from_an_early_pick_has_no_surplus(self):
        drafted = ke.evaluate_keeper({"player": "Same Guy", "position": "RB",
                                      "draft_round": 3, "acquisition": "draft",
                                      "projected_ppg": 13.2})
        self.assertEqual(drafted["surplus_rounds"], -2)
        self.assertEqual(drafted["surplus"], "none")

    def test_unprojected_player_reports_unknown_not_a_fake_negative(self):
        """The dangerous failure: with no projection, market_round falls to the
        end of the draft, which would make every keeper look like negative
        surplus and tell the synthesis agent to drop Travis Kelce."""
        row = ke.evaluate_keeper({"player": "Travis Kelce", "position": "TE",
                                  "draft_round": 7, "acquisition": "draft"})
        self.assertIsNone(row["surplus_rounds"])
        self.assertEqual(row["surplus"], "unknown")
        self.assertFalse(row["valued"])
        self.assertIsNone(row["market_round"])
        self.assertTrue(any("NO PROJECTION" in n for n in row["notes"]))
        # and the cost side is still known and correct
        self.assertEqual(row["keeper_cost_round"], 7)
        self.assertEqual(row["forfeits_overall_pick"], 68)

    def test_unprojected_players_are_held_back_from_the_slate(self):
        players = [
            {"player": "Projected Gem", "position": "RB", "acquisition": "waiver",
             "projected_ppg": 14.0},
            {"player": "Unknown A", "position": "WR", "kept_at_round": 14},
            {"player": "Unknown B", "position": "WR", "kept_at_round": 2},
        ]
        slate = ke.optimal_keeper_slate(players)
        self.assertEqual([r["player"] for r in slate["keep"]], ["Projected Gem"])
        self.assertTrue(slate["provisional"])
        self.assertEqual(len(slate["needs_projection"]), 2)
        # among unprojected players the cheapest keeper cost sorts first
        self.assertEqual(slate["needs_projection"][0]["player"], "Unknown A")

    def test_ineligible_players_score_no_surplus_and_sort_last(self):
        board = ke.build_keeper_board([
            {"player": "R1 Stud", "position": "RB", "draft_round": 1, "projected_ppg": 20.0},
            {"player": "Waiver Gem", "position": "WR", "acquisition": "waiver",
             "projected_ppg": 14.5},
        ])
        self.assertEqual(board[0]["player"], "Waiver Gem")
        self.assertFalse(board[-1]["eligible"])
        self.assertEqual(board[-1]["surplus_rounds"], 0)

    def test_optimal_slate_takes_the_best_three_legal_keepers(self):
        players = [
            {"player": "A", "position": "RB", "acquisition": "waiver", "projected_ppg": 15.0},
            {"player": "B", "position": "QB", "kept_at_round": 12, "acquisition": "keeper",
             "consecutive_years_kept": 1, "projected_ppg": 20.6},
            {"player": "C", "position": "WR", "kept_at_round": 14, "acquisition": "keeper",
             "consecutive_years_kept": 1, "projected_ppg": 13.0},
            {"player": "D", "position": "TE", "draft_round": 7, "projected_ppg": 8.0},
            {"player": "E", "position": "RB", "draft_round": 1, "projected_ppg": 22.0},
        ]
        slate = ke.optimal_keeper_slate(players)
        self.assertEqual(slate["slots_used"], 3)
        self.assertEqual(slate["slots_available"], 3)
        kept = [r["player"] for r in slate["keep"]]
        self.assertEqual(set(kept), {"A", "B", "C"})
        self.assertNotIn("E", kept)  # 1st rounder, ineligible
        self.assertEqual(slate["total_surplus_rounds"],
                         sum(r["surplus_rounds"] for r in slate["keep"]))
        # greedy really is the max here
        self.assertGreaterEqual(slate["total_surplus_rounds"],
                                sum(r["surplus_rounds"] for r in slate["next_in_line"][:3]))

    def test_slate_reports_who_is_about_to_age_out(self):
        players = [
            {"player": "Final Year Guy", "position": "QB", "kept_at_round": 12,
             "acquisition": "keeper", "consecutive_years_kept": 2, "projected_ppg": 19.0},
            {"player": "Fresh Guy", "position": "RB", "acquisition": "waiver",
             "projected_ppg": 14.0},
        ]
        slate = ke.optimal_keeper_slate(players)
        self.assertIn("Final Year Guy", slate["aging_out"])
        self.assertNotIn("Fresh Guy", slate["aging_out"])

    def test_unknown_acquisition_assumes_a_twelfth_but_says_so(self):
        cost = ke.keeper_cost({"player": "Mystery"})
        self.assertEqual(cost["cost_round"], 12)
        self.assertTrue(any("VERIFY" in n for n in cost["notes"]))

    def test_season_phase_flips_the_objective_when_eliminated(self):
        early = ke.keeper_vs_winnow_weight(2)
        mid = ke.keeper_vs_winnow_weight(6)
        dead = ke.keeper_vs_winnow_weight(12, elimination_likely=True)
        self.assertLess(early["keeper_weight"], mid["keeper_weight"] + 0.11)
        self.assertGreater(dead["keeper_weight"], 0.8)
        self.assertEqual(dead["phase"], "salvage")
        self.assertEqual(early["phase"], "small_sample")

    def test_andrew_roster_loads_from_the_real_config_board(self):
        roster = ke.andrew_roster_from_config(CONFIG_PATH)
        if not roster:
            self.skipTest("league_config.json not present")
        by_name = {r["player"]: r for r in roster}
        self.assertIn("Bo Nix", by_name)
        self.assertEqual(by_name["Bo Nix"]["kept_at_round"], 12)
        # Puka was kept in 2025, so he already has a year on the 3-year clock
        self.assertEqual(by_name["Puka Nacua"]["consecutive_years_kept"], 1)
        self.assertEqual(by_name["Kenneth Walker"]["consecutive_years_kept"], 0)
        board = ke.build_keeper_board(roster, draft_slot=8, season=2026)
        nix = next(r for r in board if r["player"] == "Bo Nix")
        # N-1: Bo Nix kept @R12 in 2025 -> R11 for 2026 (forfeits pick 108, not 113).
        self.assertEqual(nix["keeper_cost_2026"], "R11")
        self.assertEqual(nix["forfeits_overall_pick"], 108)
        # config records consecutive_years_if_kept == 2 for the 2026 keep
        self.assertEqual(nix["consecutive_years_if_kept"], 2)
        self.assertFalse(nix["is_final_eligible_year"])

    def test_year_frame_is_explicit_and_the_cap_advances_correctly(self):
        """config says Bo Nix's final eligible year is 2027 if kept in 2026.
        Rolling the board forward a year has to reproduce that, and it must not
        quote a 2027 cost for players who are not being kept in 2026."""
        roster = ke.andrew_roster_from_config(CONFIG_PATH, season=2027)
        if not roster:
            self.skipTest("league_config.json not present")
        by_name = {r["player"]: r for r in roster}
        nix = by_name["Bo Nix"]
        self.assertEqual(nix["consecutive_years_kept"], 2)
        self.assertNotIn("cost_basis_unknown", nix)
        row = ke.evaluate_keeper(nix, draft_slot=8, season=2027)
        self.assertTrue(row["is_final_eligible_year"])
        self.assertEqual(row["consecutive_years_if_kept"], 3)
        # Puka is not in the 2026 keeper plan, so his 2027 cost is genuinely unknown
        self.assertIn("cost_basis_unknown", by_name["Puka Nacua"])

    def test_load_rules_reads_the_real_config(self):
        rules = ke.load_rules(CONFIG_PATH)
        self.assertEqual(rules["max_keepers"], 3)
        self.assertEqual(rules["undrafted_pickup_cost_round"], 12)
        self.assertEqual(rules["max_consecutive_years"], 3)
        self.assertTrue(rules["first_round_ineligible"])
        self.assertEqual(rules["draft_slot"], 8)

    def test_andrews_real_keeper_plan_reproduces_from_the_config(self):
        """N-1 corrected plan: Walker (first-time keep) R4/pick 33; Bo Nix (repeat,
        kept @R12) -> R11/pick 108; Jameson Williams (repeat, kept @R14) -> R13/pick
        128. Recompute from the rules using each player's real keep-type and check
        the config's recorded cost + forfeited pick match exactly."""
        cfg = load_json(CONFIG_PATH)
        if not cfg:
            self.skipTest("league_config.json not present")
        plan = {k["name"]: k for k in cfg["andrew"]["keeper_plan"]["keeping"]}

        # inputs = each player's real keep-type (first-time -> draft_round, no N-1;
        # repeat -> kept_at_round = last year's keep round, N-1 applies).
        cases = [
            ("Kenneth Walker", {"draft_round": 4, "acquisition": "draft",
                                "consecutive_years_kept": 0}, 4, 33),
            ("Bo Nix", {"kept_at_round": 12, "acquisition": "keeper",
                        "consecutive_years_kept": 1}, 11, 108),
            ("Jameson Williams", {"kept_at_round": 14, "acquisition": "keeper",
                                  "consecutive_years_kept": 1}, 13, 128),
        ]
        for name, inp, exp_round, exp_pick in cases:
            row = ke.evaluate_keeper(dict(inp, player=name), draft_slot=8)
            self.assertEqual(row["keeper_cost_round"], exp_round, "cost wrong for %s" % name)
            self.assertEqual(row["forfeits_overall_pick"], exp_pick, "pick wrong for %s" % name)
            # and it must agree with what the config records
            self.assertEqual(plan[name]["cost_round"], exp_round, "config cost drift for %s" % name)
            self.assertEqual(plan[name]["forfeits_overall_pick"], exp_pick, "config pick drift for %s" % name)


# ==========================================================================
# End-to-end: the modules have to fit together, not just work alone
# ==========================================================================

class TestPipelineIntegration(unittest.TestCase):

    def test_pressure_feeds_contention_feeds_keeper_equity(self):
        """The real Tuesday path: score rival pressure -> predict their claims ->
        compute what survives to Andrew -> price the survivors as 2027 keepers."""
        rivals = {"DannyBC1": DESPERATE_TEAM, "havicht": COVERED_TEAM, "tlekes": HEALTHY_TEAM}
        rival_claims = {}
        for owner, team in rivals.items():
            block = op.compute_team_pressure(team, recent_scoring=RECENT_SCORING, week=8)
            rival_claims[owner] = op.predicted_claims_from_pressure(block, FA_POOL, top_n=3)

        # the desperate team must be predicted to chase the RB
        self.assertTrue(any(c["position"] == "RB" for c in rival_claims["DannyBC1"]))

        targets = []
        for fa in FA_POOL:
            eq = ke.waiver_add_equity({"player": fa["player"], "position": fa["position"],
                                       "projected_ppg": fa["value"]})
            t = dict(fa)
            t["availability_verified"] = True
            t["keeper_surplus_rounds"] = eq["surplus_rounds"]
            t["keeper_equity_2027"] = eq["surplus"]
            targets.append(t)

        rep = wc.contention_report(targets, PRIORITY_ORDER, rival_claims,
                                   andrew="andrewroth32", mode="both", trials=800,
                                   roster_spots_open=1)

        self.assertEqual(len(rep["claim_sheet"]), len(FA_POOL))
        self.assertEqual(rep["andrew_priority"], 4)
        for row in rep["claim_sheet"]:
            self.assertTrue(row["availability_verified"])
            self.assertIsNotNone(row["keeper_equity_2027"])
            self.assertIsNotNone(row["faab_bid_pct"])
            self.assertTrue(0.0 <= row["probability_reaches_andrew"] <= 1.0)
        # Sampson is chased by the desperate team ahead of Andrew, so he should
        # not be the easiest add on the board
        p = {r["player"]: r["probability_reaches_andrew"] for r in rep["claim_sheet"]}
        self.assertLessEqual(p["Dylan Sampson"], p["Jack Bech"])

    def test_projections_reach_keeper_equity_in_league_points(self):
        """A projection must be converted to THIS league's points before it is
        priced as a keeper, or the first-down bonus silently disappears."""
        conv = scoring.league_points_from_half_ppr(12.4, "WR", rec=6.5, profile="possession")
        self.assertGreater(conv["league_points"], 12.4)
        generic = ke.waiver_add_equity({"player": "X", "position": "WR",
                                        "projected_ppg": 12.4})
        league = ke.waiver_add_equity({"player": "X", "position": "WR",
                                       "projected_ppg": conv["league_points"]})
        self.assertLessEqual(league["market_round"], generic["market_round"])

    @unittest.skipUnless(os.path.exists(STATE_PATH), "state/week_0.json not built yet")
    def test_real_state_andrew_roster_prices_as_keepers(self):
        state = load_json(STATE_PATH)
        andrew = state["teams"]["2"]
        players = []
        for p in (andrew.get("starters") or []) + (andrew.get("bench") or []):
            players.append({"player": p.get("name"), "player_id": p.get("player_id"),
                            "position": p.get("pos"), "acquisition": "draft",
                            "draft_round": 8})
        board = ke.build_keeper_board(players)
        self.assertEqual(len(board), len(players))
        self.assertTrue(all("keeper_cost_2027" in r for r in board))


if __name__ == "__main__":
    unittest.main(verbosity=2)
