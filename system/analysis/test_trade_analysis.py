#!/usr/bin/env python3
"""
test_trade_analysis.py -- unittest coverage for trade_analysis.py.

Run:  python3 test_trade_analysis.py                (from system/analysis)

Synthetic mini-leagues only (no network, no files needed). The point of each
test is a fact about fantasy that must never regress: a lineup that fills its
slots correctly, a bye week that costs a team a player, a trade that helps both
sides being found, and one that helps only one side being rejected.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import trade_analysis as ta  # noqa: E402


def make_snapshot(rosters, players, points=None, byes=None, weeks_played=(1, 2, 3)):
    return ta.Snapshot(rosters=rosters, players=players, points=points or {},
                       byes=byes or {}, weeks_played=list(weeks_played),
                       reg_last=14, last_week=17, trade_deadline=13)


def roster(owner, pids, reserve=None, w=1, l=1, fpts=250.0):
    return {"owner": owner, "team": owner, "players": list(pids), "reserve": list(reserve or []),
            "wins": w, "losses": l, "ties": 0, "fpts": fpts}


def pl(name, pos, team="AAA", rnd=6, kept=False):
    return {"name": name, "pos": pos, "team": team, "draft_round": rnd, "kept": kept}


class TestLineup(unittest.TestCase):
    def test_fills_every_slot_once(self):
        pool = [(20, "QB"), (15, "QB"), (18, "RB"), (12, "RB"), (10, "RB"),
                (17, "WR"), (11, "WR"), (9, "WR"), (8, "TE")]
        pts, used = ta.lineup_points(pool)
        # QB20 RB18 RB12 WR17 WR11 TE8 + SUPER_FLEX QB15 + FLEX best left (RB10)
        self.assertAlmostEqual(pts, 20 + 18 + 12 + 17 + 11 + 8 + 15 + 10)
        self.assertEqual(len(used), 8)

    def test_superflex_takes_second_qb_only_when_better_than_flex(self):
        pool = [(20, "QB"), (8, "QB"), (18, "RB"), (12, "RB"), (10, "RB"),
                (17, "WR"), (11, "WR"), (9, "WR"), (8, "TE")]
        pts, _ = ta.lineup_points(pool)
        # QB2 (8) loses the SUPER_FLEX to RB10; FLEX then goes to WR9
        self.assertAlmostEqual(pts, 20 + 18 + 12 + 17 + 11 + 8 + 10 + 9)

    def test_empty_slots_score_replacement_not_zero(self):
        pts, _ = ta.lineup_points([(20, "QB")])
        expected = 20 + ta.REPLACEMENT_PPG["RB"] * 2 + ta.REPLACEMENT_PPG["WR"] * 2 \
            + ta.REPLACEMENT_PPG["TE"] + ta.REPLACEMENT_PPG["RB"] * 2
        self.assertAlmostEqual(pts, expected)


class TestValues(unittest.TestCase):
    def test_prior_uses_market_table_and_kept_floor(self):
        self.assertGreater(ta.prior_ppg("RB", 1), ta.prior_ppg("RB", 6))
        self.assertGreater(ta.prior_ppg("RB", 6), ta.prior_ppg("RB", 12))
        # Bo Nix style: kept at R11 must not be priced as an R11 QB
        self.assertGreaterEqual(ta.prior_ppg("QB", 11, kept=True), ta.KEPT_PRIOR_FLOOR["QB"])
        self.assertLess(ta.prior_ppg("QB", 11, kept=False), ta.prior_ppg("QB", 11, kept=True))
        # undrafted pickup is roughly replacement level
        self.assertAlmostEqual(ta.prior_ppg("WR", None), ta.REPLACEMENT_PPG["WR"] + 0.5)

    def test_zero_week_is_did_not_play_not_a_bad_game(self):
        snap = make_snapshot({1: roster("a", ["p1"])}, {"p1": pl("Star", "WR", rnd=2)},
                             points={"p1": {1: 20.0, 2: 0.0, 3: 20.0}})
        p = ta.build_player(snap, "p1", {})
        self.assertEqual(p.n_obs, 2)
        self.assertEqual(p.missed, 1)
        self.assertAlmostEqual(p.obs_mean, 20.0)

    def test_shrinkage_moves_toward_results(self):
        snap = make_snapshot({1: roster("a", ["p1", "p2"])},
                             {"p1": pl("Hot", "WR", rnd=12), "p2": pl("Cold", "WR", rnd=2)},
                             points={"p1": {1: 25.0, 2: 25.0, 3: 25.0}, "p2": {1: 4.0, 2: 4.0, 3: 4.0}})
        hot, cold = ta.build_player(snap, "p1", {}), ta.build_player(snap, "p2", {})
        self.assertGreater(hot.ppg, hot.prior)
        self.assertLess(cold.ppg, cold.prior)
        self.assertLess(hot.ppg, 25.0)   # shrunk, not taken at face value
        self.assertGreater(cold.ppg, 4.0)

    def test_bye_week_and_flags_remove_availability(self):
        snap = make_snapshot({1: roster("a", ["p1"])}, {"p1": pl("X", "RB", team="KC")},
                             byes={"KC": 6})
        p = ta.build_player(snap, "p1", {"p1": {"out_weeks": [4, 5]}})
        self.assertFalse(p.avail[6])
        self.assertFalse(p.avail[4])
        self.assertFalse(p.avail[5])
        self.assertTrue(p.avail[7])

    def test_ir_defaults_to_out_and_flag_overrides(self):
        snap = make_snapshot({1: roster("a", ["p1"], reserve=["p1"])}, {"p1": pl("X", "WR")})
        default = ta.build_player(snap, "p1", {}, is_ir=True)
        self.assertFalse(default.avail[4])
        self.assertTrue(default.avail[snap.from_week + ta.IR_DEFAULT_OUT_WEEKS])
        flagged = ta.build_player(snap, "p1", {"p1": {"out_through": 5}}, is_ir=True)
        self.assertFalse(flagged.avail[5])
        self.assertTrue(flagged.avail[6])

    def test_season_ending_flag_out_every_week(self):
        snap = make_snapshot({1: roster("a", ["p1"])}, {"p1": pl("X", "RB")})
        p = ta.build_player(snap, "p1", {"p1": {"season_ending": True}})
        self.assertFalse(any(p.avail.values()))

    def test_bye_hole_costs_lineup_points(self):
        # A team with one QB loses the QB slot to replacement level on his bye week.
        snap = make_snapshot({1: roster("a", ["q"])}, {"q": pl("QB1", "QB", team="KC", rnd=2)},
                             byes={"KC": 6})
        plist = ta.build_teams(snap, {})[1]
        _, weekly = ta.roster_value(plist, snap)
        self.assertLess(weekly[6], weekly[5])


def league_needing_a_trade():
    """Andrew (rid 1) is deep at RB and thin at WR; Bea (rid 2) is the reverse.
    A RB-for-WR swap must help both. Cara (rid 3) is a bystander."""
    P = {}
    R1 = ["a_qb", "a_rb1", "a_rb2", "a_rb3", "a_rb4", "a_wr1", "a_wr2", "a_te", "a_qb2"]
    R2 = ["b_qb", "b_rb1", "b_wr1", "b_wr2", "b_wr3", "b_wr4", "b_te", "b_qb2"]
    R3 = ["c_qb", "c_rb1", "c_rb2", "c_wr1", "c_wr2", "c_te", "c_qb2"]
    spec = {
        "a_qb": ("QB", 2), "a_qb2": ("QB", 7), "a_rb1": ("RB", 1), "a_rb2": ("RB", 2),
        "a_rb3": ("RB", 3), "a_rb4": ("RB", 4), "a_wr1": ("WR", 9), "a_wr2": ("WR", 12), "a_te": ("TE", 5),
        "b_qb": ("QB", 2), "b_qb2": ("QB", 7), "b_rb1": ("RB", 8), "b_wr1": ("WR", 1), "b_wr2": ("WR", 2),
        "b_wr3": ("WR", 3), "b_wr4": ("WR", 4), "b_te": ("TE", 5),
        "c_qb": ("QB", 2), "c_qb2": ("QB", 7), "c_rb1": ("RB", 3), "c_rb2": ("RB", 4),
        "c_wr1": ("WR", 3), "c_wr2": ("WR", 4), "c_te": ("TE", 5),
    }
    for pid, (pos, rnd) in spec.items():
        P[pid] = pl(pid, pos, team=pid[:1].upper() * 3, rnd=rnd)
    return make_snapshot({1: roster("Andrew", R1, w=0, l=2), 2: roster("Bea", R2, w=2, l=0),
                          3: roster("Cara", R3)}, P)


class TestTradeSearch(unittest.TestCase):
    def setUp(self):
        self.snap = league_needing_a_trade()
        self.teams = ta.build_teams(self.snap, {})
        self.summ = ta.team_summaries(self.snap, self.teams)

    def test_need_index_points_at_the_thin_position(self):
        a, b = self.summ[1]["need"], self.summ[2]["need"]
        self.assertGreater(a["WR"], a["RB"])   # Andrew is thin at WR, deep at RB
        self.assertGreater(b["RB"], b["WR"])   # Bea is the mirror image

    def test_finds_a_rb_for_wr_swap_that_helps_both(self):
        trades, _sw, _ = ta.find_trades(self.snap, self.teams, self.summ, me=1)
        with_bea = [t for t in trades if t["partner_rid"] == 2]
        self.assertTrue(with_bea, "expected at least one trade with the mirror-image team")
        best = with_bea[0]
        self.assertGreater(best["my_ros_gain"], 0)
        self.assertGreaterEqual(best["partner_ros_gain"], 0)
        self.assertEqual(best["tier"], "A")
        self.assertEqual([p["pos"] for p in best["give"]][0], "RB")
        self.assertIn("WR", [p["pos"] for p in best["get"]])

    def test_nobody_proposes_a_trade_that_hurts_the_partner(self):
        trades, _sw, _ = ta.find_trades(self.snap, self.teams, self.summ, me=1)
        for t in trades:
            self.assertGreaterEqual(t["partner_ros_gain"], ta.MIN_PARTNER_GAIN)
            self.assertGreaterEqual(t["my_ros_gain"], ta.MIN_MY_GAIN)

    def test_untouchable_is_never_offered(self):
        flags = {"a_rb1": {"untouchable": True}, "a_rb2": {"untouchable": True},
                 "a_rb3": {"untouchable": True}}
        teams = ta.build_teams(self.snap, flags)
        summ = ta.team_summaries(self.snap, teams)
        trades, _sw, _ = ta.find_trades(self.snap, teams, summ, me=1)
        offered = set(p["pid"] for t in trades for p in t["give"])
        self.assertFalse(offered & {"a_rb1", "a_rb2", "a_rb3"})

    def test_injured_target_is_priced_in(self):
        # If Bea's best WR is out for the season, getting him must not look like a gain.
        flags = {"b_wr1": {"season_ending": True}}
        teams = ta.build_teams(self.snap, flags)
        summ = ta.team_summaries(self.snap, teams)
        trades, _sw, _ = ta.find_trades(self.snap, teams, summ, me=1)
        for t in trades:
            got = [p["pid"] for p in t["get"]]
            if got == ["b_wr1"]:
                self.fail("proposed trading for a season-ending injury as a solo return")

    def test_roster_limit_forces_a_named_drop(self):
        # Fill Andrew's roster to the limit and ask for two players for one.
        extra = ["a_x%d" % i for i in range(5)]  # 9 + 5 = 14 non-DEF + DEF = the 15 limit
        P = dict(self.snap.players)
        for e in extra:
            P[e] = pl(e, "WR", team="AAA", rnd=15)
        snap = make_snapshot({1: roster("Andrew", self.snap.rosters[1]["players"] + extra, w=0, l=2),
                              2: self.snap.rosters[2], 3: self.snap.rosters[3]}, P)
        teams = ta.build_teams(snap, {})
        mine = teams[1]
        give = [p for p in mine if p.pid == "a_rb1"]
        get = [p for p in teams[2] if p.pid in ("b_wr1", "b_wr2")]
        new_mine, dropped = ta._forced_drop(ta._apply(mine, give, get), snap)
        self.assertIsNotNone(dropped)
        self.assertEqual(len(new_mine), len(mine) - 1 + 2 - 1)


class TestDepthAndSwaps(unittest.TestCase):
    def test_depth_is_worth_something(self):
        # Same starting lineup; one roster has a solid backup RB, the other does not.
        P = {"qb": pl("QB", "QB", rnd=2), "qb2": pl("QB2", "QB", rnd=6),
             "r1": pl("R1", "RB", rnd=2), "r2": pl("R2", "RB", rnd=3), "r3": pl("R3", "RB", rnd=15),
             "w1": pl("W1", "WR", rnd=2), "w2": pl("W2", "WR", rnd=3), "w3": pl("W3", "WR", rnd=6),
             "t": pl("T", "TE", rnd=6), "bench_rb": pl("BenchRB", "RB", rnd=10)}
        thin = ["qb", "qb2", "r1", "r2", "r3", "w1", "w2", "w3", "t"]
        deep = thin + ["bench_rb"]
        snap = make_snapshot({1: roster("thin", thin), 2: roster("deep", deep)}, P)
        teams = ta.build_teams(snap, {})
        thin_v = ta.roster_value(teams[1], snap)[0]
        deep_v = ta.roster_value(teams[2], snap)[0]
        self.assertGreater(deep_v, thin_v)
        # ...and without the injury adjustment the extra bench player is worth nothing
        self.assertAlmostEqual(ta.roster_value(teams[1], snap, injury_adjust=False)[0],
                               ta.roster_value(teams[2], snap, injury_adjust=False)[0] , places=6)

    def test_swap_sections_are_reported_for_both_directions(self):
        snap = league_needing_a_trade()
        result = ta.analyze(snap, me=1)
        self.assertIn("RB>WR", result["swaps"])
        self.assertIn("WR>RB", result["swaps"])
        rb_for_wr = result["swaps"]["RB>WR"]
        self.assertTrue(rb_for_wr)
        for t in rb_for_wr:
            self.assertEqual(t["shape"], "1-for-1")
            self.assertEqual(t["give"][0]["pos"], "RB")
            self.assertEqual(t["get"][0]["pos"], "WR")
        # Andrew is deep at RB, so trading a WR for an RB should not be on offer
        self.assertFalse(result["swaps"]["WR>RB"])
        text = ta.render_markdown(result)
        self.assertIn("Straight swaps: your RB for their WR", text)
        self.assertIn("Straight swaps: your WR for their RB", text)


class TestOutputs(unittest.TestCase):
    def test_analyze_render_and_decisions_roundtrip(self):
        snap = league_needing_a_trade()
        result = ta.analyze(snap, me=1)
        text = ta.render_markdown(result)
        self.assertIn("Trade board", text)
        json.dumps(result, default=str)  # must serialise
        decs = ta.decisions_from(result)
        for d in decs:
            self.assertEqual(d["type"], "trade")
            self.assertIsNone(d["outcome"])

    def test_posture_reflects_standings(self):
        snap = league_needing_a_trade()
        post = ta.standings_posture(snap, me=1)
        self.assertEqual(post["rank"], 3)
        self.assertEqual(post["label"], "contender")  # 3rd of 3; rank<=3 -> contender in this tiny league
        self.assertGreater(post["weeks_until_deadline"], 0)

    def test_flag_candidates_list_the_zero_week_players(self):
        snap = league_needing_a_trade()
        snap.points = {"b_wr1": {1: 18.0, 2: 0.0, 3: 0.0}}
        teams = ta.build_teams(snap, {})
        names = [c["pid"] for c in ta.flag_candidates(snap, teams)]
        self.assertIn("b_wr1", names)

    def test_loader_reads_sleeper_shaped_files(self):
        with tempfile.TemporaryDirectory() as d:
            raw = os.path.join(d, "raw")
            os.makedirs(raw)
            with open(os.path.join(raw, "rosters.json"), "w") as fh:
                json.dump([{"roster_id": 1, "owner_id": "u1", "players": ["10", "20", "KC"], "reserve": ["20"],
                            "settings": {"wins": 1, "losses": 2, "fpts": 300, "fpts_decimal": 50}}], fh)
            with open(os.path.join(raw, "users.json"), "w") as fh:
                json.dump([{"user_id": "u1", "display_name": "andrew", "metadata": {"team_name": "Pabst"}}], fh)
            with open(os.path.join(raw, "draft_2026_picks.json"), "w") as fh:
                json.dump({"10": ["Some Back", "RB", "KC", 3, 1], "20": ["Some Wideout", "WR", "KC", 9, 0]}, fh)
            for wk, pts in ((1, 12.5), (2, 0.0), (3, 30.0)):
                with open(os.path.join(raw, "matchups_week%d.json" % wk), "w") as fh:
                    json.dump([{"roster_id": 1, "points": pts + 1, "players_points": {"10": pts, "20": 5.0}}], fh)
            with open(os.path.join(raw, "matchups_week4.json"), "w") as fh:  # scaffolded future week
                json.dump([{"roster_id": 1, "points": 0.0, "players_points": {"10": 0.0}}], fh)
            with open(os.path.join(d, "league_config.json"), "w") as fh:
                json.dump({"nfl_bye_weeks_2026": {"byes": {"KC": 5}},
                           "calendar": {"last_regular_season_week": 14, "playoff_weeks": [15, 16, 17],
                                        "trade_deadline_week": 13}}, fh)
            snap = ta.load_snapshot(raw)
            self.assertEqual(snap.weeks_played, [1, 2, 3])       # week 4 (all zeros) ignored
            self.assertEqual(snap.from_week, 4)
            self.assertEqual(snap.rosters[1]["team"], "Pabst")
            self.assertAlmostEqual(snap.rosters[1]["fpts"], 300.5)
            self.assertEqual(snap.players["10"]["draft_round"], 3)
            self.assertTrue(snap.players["10"]["kept"])
            self.assertEqual(snap.players["KC"]["pos"], "DEF")
            self.assertEqual(snap.byes["KC"], 5)
            p = ta.build_player(snap, "10", {})
            self.assertEqual(p.n_obs, 2)     # the 0.0 week is a DNP
            self.assertEqual(p.missed, 1)


if __name__ == "__main__":
    unittest.main(verbosity=2)
