# Scoring — half-PPR **plus 0.5 per first down**

This is the single most format-warping rule in the league, and the most exploitable. Every
projection you will find on the internet is priced in standard or half-PPR. None of them price the
first-down bonus.

**Nothing anywhere in this system should say "points" without having gone through
`system/analysis/scoring.py`.**

## The table (pulled from Sleeper)

| Category | Value |
|---|---|
| Reception | 0.5 |
| **Reception first down** | **0.5** |
| **Rush first down** | **0.5** |
| Pass yard | 0.04 (25 yds = 1 pt) |
| Rush / Rec yard | 0.1 (10 yds = 1 pt) |
| Pass TD | 4 |
| Rush / Rec TD | 6 |
| Interception thrown | -1 |
| Fumble lost | -2 |
| 2-pt conversion (any) | 2 |

**DEF:** sack 1, INT 2, fumble recovery 2, DEF/ST TD 6, and a points-allowed ladder:

| Points allowed | 0 | 1–6 | 7–13 | 14–20 | 21–27 | 28–34 | 35+ |
|---|---|---|---|---|---|---|---|
| Points | 10 | 7 | 4 | 1 | 0 | -1 | -4 |

> **Do not trust historical DEF totals.** DEF scoring was overpowered/buggy in 2025 and the
> commissioner flagged a fix as TBD. Not confirmed applied. Treat DEF as a streaming slot.

## What the bonus actually does

A possession receiver with 6 catches and 5 first downs gains **+2.5 pts/gm** over his half-PPR
price. A two-catch deep threat with a 75-yard touchdown gains **+0.5**. Over a season that is a full
tier of positional value.

Consequences, applied consistently:

- **Up:** high-target-share possession receivers, slot men, chain-moving check-down backs,
  possession tight ends, anyone converting on 3rd-and-short.
- **Down:** boom-bust vertical threats and pure TD-dependent scorers. Their price in this league is
  lower than their ADP implies, which also makes them the right kind of player to *sell*.
- **Rushing QBs quietly gain a lot** — every rushing first down is +0.5, and QB scrambles on
  3rd down convert at a high rate. This is routinely ignored by outside rankings.
- **Goal-line backs are worth less than they look**; volume backs who move the chains are worth
  more. A 1-yard TD plunge is 6 points and one first down; a 12-play drive of 5-yard gains is
  several.
- Andrew's own roster fits this format well at DeVonta Smith and Tetairoa McMillan; it fits poorly
  at contested-catch/TD-dependent types like Mike Evans.

## Using the module

```bash
echo '{"stats": {"rec": 7, "rec_yd": 84, "rec_fd": 5}}' | python3 system/analysis/scoring.py
python3 system/analysis/scoring.py --demo
```

```python
from analysis.scoring import (
    score_stat_line,            # stats -> exact league points
    score_breakdown,            # + per-category contributions, first_down_premium
    half_ppr_points,            # what an outside projection would have said
    estimate_first_downs,       # stats + position -> {rec_fd, rush_fd} when the box score lacks them
    league_points_from_half_ppr,# convert a published half-PPR projection into this format
    first_down_premium,         # pts/gm a profile gains, given rec/gm and rush att/gm
    REPLACEMENT_PPG,            # replacement level BY POSITION, in this format
)
```

`league_points_from_half_ppr` is the workhorse: when a source gives you a half-PPR projection,
convert it before comparing two players. `REPLACEMENT_PPG` is what "below replacement level" means
here — it is the basis for the *performance pressure* term in the opponent model, so use it rather
than eyeballing.
