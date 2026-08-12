export const meta = {
  name: 'sunday-scaries-weekly',
  description: 'The Tuesday run for the Sunday Scaries keeper league: nine opponent models, four topic-sliced news sweeps, a free-agent board and a my-team read in parallel, then the opus waiver-contention model and trade board, then a single synthesis agent that emits the 8-part Tuesday brief plus the next state file.',
  phases: [
    { title: 'Intelligence', detail: '9 opponent agents + 4 topic news agents + free-agent board + my-team read (sonnet, parallel)' },
    { title: 'Cross-Analysis', detail: 'Waiver contention model and trade board (opus)' },
    { title: 'Synthesis', detail: 'The 8-part Tuesday action card, report markdown and the new state file' },
  ],
}

/* ------------------------------------------------------------------ *
 * 0. Paths and league constants
 * ------------------------------------------------------------------ */

const ROOT = '/home/claude/sunday_scaries'
const SYS = ROOT + '/system'
const STATE_DIR = SYS + '/state'
const RAW_DIR = SYS + '/raw'
const REPORT_DIR = SYS + '/reports'

const P_CONFIG = SYS + '/league_config.json'
const P_PLAYERS = SYS + '/players_cache.json'
const P_MANIFEST = SYS + '/fetch_manifest.md'
const P_REFERENCE = ROOT + '/league_reference.md'
const P_PLAN = ROOT + '/weekly_system_plan.md'

const LEAGUE_ID = '1389753893356838912'
const PREV_LEAGUE_ID = '1257451899603402752'
const SEASON = 2026
const ANDREW_ROSTER_ID = 2
const ANDREW_USER_ID = '1128203360286429184'
const ANDREW_HANDLE = 'andrewroth32'

/* The nine rivals. roster_id is deliberately NOT hardcoded - only Andrew's (2) is
 * known for certain, so agents resolve the rest from the rosters payload. */
const RIVALS = [
  { team: 'Pabst Interference', owner: 'tlekes', user_id: '1123669553063526400', note: 'league commissioner' },
  { team: 'Water, Barkley, and Hops', owner: 'havicht', user_id: '1128898667324239872', note: '' },
  { team: 'jomud (no team name set)', owner: 'jomud', user_id: '1129508145568686080', note: 'QB-hoarder profile in a superflex league' },
  { team: 'Glizzy Guzzler', owner: 'LoochCarluccio', user_id: '603841382339108864', note: 'only team that locked keepers early' },
  { team: 'Mass General Hospital', owner: 'pdustin', user_id: '869724998703763456', note: '' },
  { team: 'Still at RPI', owner: 'PeterCrisileo', user_id: '870744736284196864', note: '' },
  { team: "Ethan's Younglings", owner: 'Edeecher', user_id: '869654771978641408', note: '' },
  { team: 'DannyBC1 (no team name set)', owner: 'DannyBC1', user_id: '1131700966283177984', note: '' },
  { team: 'Big Mommy Milkers (UCSF)', owner: 'jpalmeri1616', user_id: '1133830654808072192', note: '' },
]

const SCORING = [
  'SCORING (half-PPR PLUS half-point-per-first-down - this is the single most format-warping rule):',
  '  Reception 0.5 | Reception first down 0.5 | Rush first down 0.5',
  '  Pass yd 0.04 | Rush/Rec yd 0.1 | Pass TD 4 | Rush/Rec TD 6 | INT -1 | Fumble lost -2 | 2pt 2',
  '  DEF: sack 1, INT 2, fumble rec 2, TD 6, points-allowed ladder 10/7/4/1/0/-1/-4.',
  '  DEF scoring was buggy last season and the commissioner flagged a fix - do not trust historical DEF totals.',
  '  => A chain-moving, high-target-share, check-down-catching player is worth materially more here than in',
  '     standard half-PPR. A boom-bust deep threat or a pure TD-dependent scorer is worth materially less.',
  '     A rushing QB picks up 0.5 per rushing first down, which is a real and often-ignored edge.',
].join('\n')

const ROSTER_RULES = [
  'LEAGUE: 10 teams, SUPERFLEX, Sleeper, season ' + SEASON + ' (year 3).',
  'STARTERS (10): QB, RB, RB, WR, WR, TE, FLEX, FLEX, SUPER_FLEX, DEF.  BENCH: 6.  Roster 16.',
  '  NOTE: the FLEX count is an OPEN QUESTION. Sleeper shows 2 FLEX; the rules doc says 1.',
  '  Assume 2 FLEX (what Sleeper actually reports) but flag any recommendation that flips if it is really 1.',
  'PLAYOFFS: top 6, start week 15. TRADE DEADLINE: week 13.',
  'KEEPERS: keep up to 3. Cost = the round the player was drafted or kept last season.',
  '  1st-round picks are NOT keeper-eligible. A player added off waivers/FA costs a 12th-round pick.',
  '  No player may be kept more than 3 consecutive years.',
  'WAIVERS: reverse-standings PRIORITY - worst record picks first, and a team that uses its claim',
  '  drops to the back of the order.',
  '  EVIDENCE (from the raw Sleeper league settings, not an assumption): waiver_type = 1, which is',
  '  Sleeper code for reverse-standings priority (0 = rolling, 2 = FAAB). waiver_budget = 100 is an',
  '  inert default field that Sleeper carries on every league whether or not FAAB is switched on, so it',
  '  is NOT evidence of FAAB. waiver_day_of_week = 2 with waiver_clear_days = 2.',
  '  This matches the commissioner note, so lead with PRIORITY logic and treat it as the working answer.',
  '  STILL HEDGE: nobody has confirmed this in writing against a live processed claim, and priority vs',
  '  FAAB imply completely different strategies, so also give a FAAB bid percentage for each target as a',
  '  parallel answer, and state the assumption you used. Do not silently pick one and hide the choice.',
].join('\n')

const IDS = [
  'league_id ' + LEAGUE_ID + '  (season ' + SEASON + ')',
  'previous_league_id ' + PREV_LEAGUE_ID + '  (2025, used for keeper-cost provenance)',
  'Andrew: roster_id ' + ANDREW_ROSTER_ID + ', user_id ' + ANDREW_USER_ID + ', display_name ' + ANDREW_HANDLE,
].join('\n')

/* ------------------------------------------------------------------ *
 * 1. Arguments
 * ------------------------------------------------------------------ */

function rawArgs() {
  try {
    if (typeof args === 'undefined' || args === null) return ''
    if (typeof args === 'string') return args
    if (typeof args === 'number') return String(args)
    if (typeof args === 'object') {
      var parts = []
      for (var k in args) {
        if (Object.prototype.hasOwnProperty.call(args, k)) parts.push(k + '=' + String(args[k]))
      }
      if (parts.length) return parts.join(' ')
      return ''
    }
    return String(args)
  } catch (e) {
    return ''
  }
}

function argValue(raw, key) {
  if (!raw) return null
  var flag = raw.match(new RegExp('(?:^|[\\s,;])--?' + key + '[=:\\s]+([^\\s,;]+)', 'i'))
  if (flag) return flag[1]
  var bare = raw.match(new RegExp('(?:^|[\\s,;])' + key + '[=:]\\s*([^\\s,;]+)', 'i'))
  if (bare) return bare[1]
  return null
}

/* Tuesday of the week BEFORE week-1 games. The 2026 regular season opens
 * Thursday Sept 10 2026, so the first Tuesday run lands Sept 8 2026. */
const SEASON_ANCHOR_MS = Date.UTC(2026, 8, 8)

function weekFromToday() {
  var now = Date.now()
  if (now < SEASON_ANCHOR_MS) return 1
  var w = Math.floor((now - SEASON_ANCHOR_MS) / 604800000) + 1
  if (w < 1) return 1
  if (w > 18) return 18
  return w
}

const ARGS = rawArgs()

function resolveWeek() {
  var explicit = argValue(ARGS, 'week') || argValue(ARGS, 'w')
  if (explicit) {
    var n = parseInt(explicit, 10)
    if (!isNaN(n) && n >= 1 && n <= 18) return { week: n, source: 'supplied via args' }
  }
  var bare = ARGS.match(/(?:^|\s)(\d{1,2})(?:\s|$)/)
  if (bare) {
    var b = parseInt(bare[1], 10)
    if (!isNaN(b) && b >= 1 && b <= 18) return { week: b, source: 'supplied via args as a bare number' }
  }
  return { week: weekFromToday(), source: 'derived from the calendar date, since no valid week was supplied' }
}

const RESOLVED = resolveWeek()
const WEEK = RESOLVED.week
const WEEK_SOURCE = RESOLVED.source
/* Week 1's predecessor is week_0.json - the PRESEASON BASELINE that state_builder.py
 * emits before the season starts (post-draft rosters, keeper costs, opening waiver
 * order). Treating week 1 as having no history throws that baseline away and makes the
 * first real run of the season blind, so PREV_WEEK bottoms out at 0, not 1. */
const PREV_WEEK = WEEK >= 1 ? WEEK - 1 : null

const WAIVER_MODE = (argValue(ARGS, 'waivers') || 'ambiguous').toLowerCase()
/* state_builder.py has ALREADY written STATE_PATH (week_N.json) deterministically from the
 * raw Sleeper payloads before this workflow runs. The synthesis agent must NOT overwrite it:
 * the plan's whole premise is that anything that must be exactly right is computed in code,
 * never re-derived by a model. So the agent's state goes to its own file and merge_state.py
 * folds the model-only sections (opponent_model, keeper_equity, decisions_log,
 * open_questions) back into the deterministic file. */
const STATE_PATH = argValue(ARGS, 'state') || (STATE_DIR + '/week_' + WEEK + '.json')
const SYNTH_STATE_PATH = STATE_PATH.replace(/\.json$/, '') + '.synthesis.json'
const PREV_STATE_PATH = argValue(ARGS, 'prevstate') ||
  (PREV_WEEK !== null ? STATE_DIR + '/week_' + PREV_WEEK + '.json' : '(none)')
const REPORT_PATH = argValue(ARGS, 'report') || (REPORT_DIR + '/week_' + WEEK + '.md')
/* Phase 3 of weekly_loop_closure_plan.md: analysis/build_analysis_output.py runs BEFORE
 * this workflow starts (it has to - agent() calls are LLM calls, not code execution, so
 * there is no way to invoke Python mid-workflow) and writes one combined JSON holding the
 * deterministic opponent-pressure model, first-pass predicted claims, the Monte Carlo
 * waiver-contention report, the keeper-equity board, and the code-verified free-agent gate.
 * This is a PATH, like STATE_PATH and PREV_STATE_PATH - the workflow has no fs, so every
 * agent that needs it reads it with the Read tool. See the "baseline vs refine" contract in
 * weekly_README.md: agents cite and refine these numbers with qualitative signals they find,
 * they do not recompute them from scratch, and they must never contradict verified_free_agents. */
const ANALYSIS_OUTPUT_PATH = argValue(ARGS, 'analysis_output') || argValue(ARGS, 'analysis') ||
  (STATE_DIR + '/week_' + WEEK + '_analysis_output.json')

function todayISO() {
  var d = new Date()
  function pad(n) { return n < 10 ? '0' + n : String(n) }
  return d.getUTCFullYear() + '-' + pad(d.getUTCMonth() + 1) + '-' + pad(d.getUTCDate())
}
const TODAY = todayISO()

/* ------------------------------------------------------------------ *
 * 2. Season phase (Part 5 of the plan)
 * ------------------------------------------------------------------ */

function seasonPhase(week) {
  if (week <= 3) {
    return {
      name: 'Weeks 1-3: sample-size trap',
      rules: [
        'Judge OPPORTUNITY metrics - snaps, routes run, target share, carry share - not fantasy points.',
        'Do NOT cut a good player for a one-week wonder. Three weeks of bad points is not evidence yet.',
        'Waiver claims should target ROLE changes, not box scores.',
        'Be sceptical of any rival prediction built on one game of scoring.',
      ],
    }
  }
  if (week <= 8) {
    return {
      name: 'Weeks 4-8: the trade window',
      rules: [
        'This is the single most aggressive phase for the trade board. Rivals have formed strong opinions off small samples.',
        'Buy-low and sell-high offers land now and stop landing by week 10.',
        'Sample size is now real enough to act on but opinions are still soft enough to exploit.',
      ],
    }
  }
  if (week <= 13) {
    return {
      name: 'Weeks 9-13: playoff positioning (TRADE DEADLINE IS WEEK 13)',
      rules: [
        'Hard wall: no consolidation trade is possible after week 13. Count the weeks remaining explicitly.',
        'Start weighting weeks 15-17 schedules over season-long averages.',
        'If Andrew is a lock or nearly eliminated, begin tilting toward keeper equity.',
      ],
    }
  }
  return {
    name: 'Weeks 14-17: playoffs (top 6, start week 15)',
    rules: [
      'Streaming and matchup optimisation dominate. Season-long averages are nearly irrelevant now.',
      'If elimination is likely, FLIP THE OBJECTIVE ENTIRELY to keeper-equity accumulation for 2027.',
      'Week 16 should produce a ranked keeper-equity board, not a lineup.',
    ],
  }
}

const PHASE_INFO = seasonPhase(WEEK)

/* ------------------------------------------------------------------ *
 * 3. Shared prompt blocks
 * ------------------------------------------------------------------ */

const CTX = [
  '=== SUNDAY SCARIES LEAGUE CONTEXT ===',
  IDS,
  '',
  ROSTER_RULES,
  '',
  SCORING,
  '',
  '=== WHERE WE ARE ===',
  'Run date: ' + TODAY + '.  Target week: ' + WEEK + ' (week number ' + WEEK_SOURCE + ').',
  'Season phase: ' + PHASE_INFO.name,
  'Phase defaults you MUST apply:',
  '  - ' + PHASE_INFO.rules.join('\n  - '),
  '',
  '=== FILES ON DISK (read them, do not guess) ===',
  'League constants ......... ' + P_CONFIG,
  'Player id -> name cache .. ' + P_PLAYERS,
  'Raw Sleeper JSON ......... ' + RAW_DIR + '/   (see ' + P_MANIFEST + ' for what each file is)',
  'THIS week state .......... ' + STATE_PATH + '   (ALREADY BUILT by state_builder.py before this run:',
  '                             deterministic standings, rosters, starters, matchups, transactions,',
  '                             injuries and the verified free-agent set. READ IT. It is ground truth',
  '                             for every mechanical fact, and it beats anything you derive by hand.)',
  'Analysis baseline ........ ' + ANALYSIS_OUTPUT_PATH,
  '  ALREADY COMPUTED by build_analysis_output.py before this run, from the same state file, using',
  '  opponent_pressure.py / waiver_contention.py / keeper_equity.py. Holds four sections:',
  '    opponent_pressure     per-rival pressure scores (vacancy/performance/role/depth), keyed by roster_id',
  '    predicted_claims      a first-pass predicted-claims list per rival against the real FA pool',
  '    waiver_contention     a full Monte Carlo landing-probability report over every verified free agent',
  '    keeper_equity         the ranked keeper board off the real 2026 keeper-cost provenance',
  '    verified_free_agents  the code-verified availability gate (who is and is not a free agent, from',
  '                          code, not a guess) plus a valued pool',
  '  THIS IS A DETERMINISTIC BASELINE, not a finished answer: it was built from box-score and roster data',
  '  ALONE, with no role_signals, because it runs before any of you exist. YOUR JOB is to REFINE it with',
  '  the qualitative signal you find - snap counts, beat reports, injury news - not to recompute the',
  '  numbers from scratch. Cite the baseline number, then say what you are adjusting it to and why. Never',
  '  silently ignore it, and never contradict verified_free_agents - that gate is code, not a prompt, and',
  '  it is right by construction.',
  'LAST week state .......... ' + PREV_STATE_PATH,
  (WEEK === 1
    ? '  NOTE: week_0.json is the PRESEASON BASELINE, not a played week. It has post-draft rosters,\n' +
      '  keeper costs and the opening waiver order, but NO matchups, NO transactions and NO scoring\n' +
      '  history. Use it for rosters and waiver order; do not look for last-week points that do not exist.\n' +
      '  Everything this week must lean on projections and opportunity, since there is no in-season sample yet.'
    : '  Diff against it. What CHANGED since last week is worth more than re-describing what did not.'),
  'Long-form league doc ..... ' + P_REFERENCE,
  'System design plan ....... ' + P_PLAN,
  '',
  'If a file is missing, say so plainly in your output and degrade gracefully. Never invent roster data.',
].join('\n')

const HARD_RULES = [
  '=== NON-NEGOTIABLE RULES ===',
  '1. AVAILABILITY GATE. Never recommend a player who is not genuinely a free agent IN THIS LEAGUE.',
  '   ' + ANALYSIS_OUTPUT_PATH + ' -> verified_free_agents IS this gate, computed in code from every',
  '   roster before this run started. A player must appear in verified_free_agents.raw',
  '   .confirmed_available_known_players (or as a DEF in .available_defenses) to be recommended. Do not',
  '   contradict it and do not re-derive it from scratch - it is already right. If that file is missing,',
  '   unreadable or you have a specific, stated reason to distrust it for one player, fall back to',
  '   checking him against every roster in the rosters payload / state file yourself, and say loudly that',
  '   you had to. If you cannot verify availability by either path, mark the player unverified rather than',
  '   recommending him.',
  '2. FRESHNESS GATE. Every injury, snap-count, practice or role claim must cite a source dated within',
  '   7 days of ' + TODAY + '. Include the source name and the source date. If the freshest thing you can',
  '   find is older than that, label it STALE explicitly instead of presenting it as current.',
  '3. NO WIKIPEDIA for anything time-sensitive. Beat writers, team sites, PFF/FantasyPros/ESPN/NFL.com,',
  '   official injury reports. A previous sweep got redone because one section leaned on Wikipedia.',
  '4. FORMAT FIRST. Every valuation is in THIS scoring format, not generic half-PPR or PPR.',
  '5. Say I DO NOT KNOW rather than filling a gap with a plausible guess. A confident wrong claim here',
  '   costs a real waiver priority.',
].join('\n')

function ctxFor(role) {
  return 'You are one worker inside the Sunday Scaries weekly fantasy football system, run for a user named Andrew.\n\n' +
    CTX + '\n\n' + HARD_RULES + '\n\n=== YOUR ROLE: ' + role + ' ===\n'
}

/* Trim a result set so downstream prompts stay bounded. */
function pack(value, maxChars) {
  var s
  try {
    s = typeof value === 'string' ? value : JSON.stringify(value, null, 1)
  } catch (e) {
    s = String(value)
  }
  if (!s) return '(no data returned)'
  if (s.length <= maxChars) return s
  return s.slice(0, maxChars) + '\n...[truncated at ' + maxChars + ' chars]'
}

function clean(arr) {
  return (arr || []).filter(Boolean)
}

/* ------------------------------------------------------------------ *
 * 4. Schemas
 * ------------------------------------------------------------------ */

const PRESSURE_BLOCK = {
  type: 'object',
  description: 'Per-position pressure 0..1. 0 = settled, 1 = will certainly act this week.',
  properties: {
    QB: { type: 'number' },
    RB: { type: 'number' },
    WR: { type: 'number' },
    TE: { type: 'number' },
    DEF: { type: 'number' },
  },
}

const OPPONENT_SCHEMA = {
  type: 'object',
  properties: {
    team: { type: 'string' },
    owner: { type: 'string' },
    roster_id: { type: 'number', description: 'resolved from the rosters payload, not guessed' },
    record: { type: 'string' },
    waiver_priority: { type: 'number', description: 'their slot in the reverse-standings order, or -1 if unknown' },
    changed_since_last_week: { type: 'array', items: { type: 'string' } },
    pressure: PRESSURE_BLOCK,
    pressure_breakdown: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          position: { type: 'string' },
          vacancy: { type: 'number', description: 'starter hurt, suspended, or on bye with no cover' },
          performance: { type: 'number', description: 'starter below replacement over a 2-3 week window' },
          role: { type: 'number', description: 'losing snaps/routes/targets BEFORE the box score shows it' },
          depth: { type: 'number', description: 'no viable replacement on their own bench' },
          evidence: { type: 'string' },
        },
        required: ['position', 'vacancy', 'performance', 'role', 'depth'],
      },
    },
    vulnerable_starters: { type: 'array', items: { type: 'string' } },
    bench_assets: { type: 'array', items: { type: 'string' } },
    predicted_claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          player: { type: 'string' },
          position: { type: 'string' },
          likelihood: { type: 'number', description: '0..1 that THIS team claims THIS player this week' },
          why: { type: 'string' },
        },
        required: ['player', 'position', 'likelihood', 'why'],
      },
    },
    predicted_drops: { type: 'array', items: { type: 'string' } },
    surplus_positions: { type: 'array', items: { type: 'string' } },
    need_positions: { type: 'array', items: { type: 'string' } },
    trade_appetite: { type: 'string', description: 'one line, e.g. desperate at RB, surplus at WR' },
    tradeable_pieces_andrew_wants: { type: 'array', items: { type: 'string' } },
    blocking_opportunity: { type: 'string', description: 'a cheap claim that would hurt this team more than the roster spot costs, or none' },
    confidence: { type: 'string', description: 'high, medium or low' },
    data_gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['team', 'owner', 'pressure', 'predicted_claims', 'need_positions', 'trade_appetite', 'confidence'],
}

const NEWS_SCHEMA = {
  type: 'object',
  properties: {
    topic: { type: 'string' },
    as_of: { type: 'string' },
    items: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          player: { type: 'string' },
          position: { type: 'string' },
          nfl_team: { type: 'string' },
          headline: { type: 'string' },
          detail: { type: 'string' },
          source: { type: 'string' },
          source_date: { type: 'string', description: 'YYYY-MM-DD. Required. Mark STALE if older than 7 days.' },
          is_stale: { type: 'boolean' },
          signal_strength: { type: 'string', description: 'strong, moderate or weak' },
          format_impact: { type: 'string', description: 'effect under half-PPR plus 0.5 per first down specifically' },
          rostered_by: { type: 'string', description: 'which Sunday Scaries team rosters him, or FREE AGENT, or UNKNOWN' },
          action: { type: 'string', description: 'what this implies: claim, drop, start, sit, buy-low, sell-high, monitor' },
        },
        required: ['player', 'headline', 'source', 'source_date', 'signal_strength', 'action'],
      },
    },
    league_relevant_summary: { type: 'string' },
    watchlist_next_week: { type: 'array', items: { type: 'string' } },
    coverage_gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['topic', 'as_of', 'items', 'league_relevant_summary'],
}

const FA_SCHEMA = {
  type: 'object',
  properties: {
    as_of: { type: 'string' },
    availability_method: { type: 'string', description: 'exactly how you verified these players are unrostered in THIS league' },
    ranked: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          rank: { type: 'number' },
          player: { type: 'string' },
          position: { type: 'string' },
          nfl_team: { type: 'string' },
          sleeper_player_id: { type: 'string' },
          availability_verified: { type: 'boolean', description: 'true ONLY if checked against every roster' },
          ros_tier: { type: 'string', description: 'e.g. RB2, WR4, streamer, stash' },
          projected_weekly_points_this_format: { type: 'number' },
          opportunity: { type: 'string', description: 'snaps, routes, target share, carry share - the actual evidence' },
          why: { type: 'string' },
          keeper_equity_2027: { type: 'string', description: 'value as a 12th-round keeper next year: very high, high, medium, low, none' },
          risk: { type: 'string' },
        },
        required: ['rank', 'player', 'position', 'availability_verified', 'ros_tier', 'why', 'keeper_equity_2027'],
      },
    },
    streamers: {
      type: 'object',
      properties: {
        QB: { type: 'array', items: { type: 'string' } },
        TE: { type: 'array', items: { type: 'string' } },
        DEF: { type: 'array', items: { type: 'string' } },
      },
    },
    trending_adds_leaguewide: { type: 'array', items: { type: 'string' }, description: 'from the Sleeper trending endpoint, a proxy for who is about to be claimed everywhere' },
    deep_stashes: { type: 'array', items: { type: 'string' } },
    unverified_excluded: { type: 'array', items: { type: 'string' }, description: 'players you would have ranked but could not confirm as free agents' },
    notes: { type: 'string' },
  },
  required: ['as_of', 'availability_method', 'ranked'],
}

const MYTEAM_SCHEMA = {
  type: 'object',
  properties: {
    roster_snapshot: { type: 'array', items: { type: 'string' } },
    optimal_lineup: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          slot: { type: 'string', description: 'QB, RB1, RB2, WR1, WR2, TE, FLEX1, FLEX2, SUPER_FLEX or DEF' },
          player: { type: 'string' },
          confidence: { type: 'string' },
          reason: { type: 'string', description: 'only needed when the call is non-obvious' },
        },
        required: ['slot', 'player'],
      },
    },
    bench: { type: 'array', items: { type: 'string' } },
    close_calls: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          start: { type: 'string' },
          sit: { type: 'string' },
          margin: { type: 'string' },
          reason: { type: 'string' },
        },
        required: ['start', 'sit', 'reason'],
      },
    },
    injuries: { type: 'array', items: { type: 'string' } },
    bye_coverage: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          week: { type: 'number' },
          position: { type: 'string' },
          players_out: { type: 'array', items: { type: 'string' } },
          covered: { type: 'boolean' },
          plan: { type: 'string' },
        },
        required: ['week', 'position', 'covered'],
      },
    },
    roster_holes: { type: 'array', items: { type: 'string' } },
    surplus: { type: 'array', items: { type: 'string' } },
    sell_high: { type: 'array', items: { type: 'string' } },
    buy_low_wanted: { type: 'array', items: { type: 'string' } },
    drop_candidates: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          player: { type: 'string' },
          what_you_lose: { type: 'string' },
          keeper_equity_2027: { type: 'string' },
          verdict: { type: 'string' },
        },
        required: ['player', 'what_you_lose', 'verdict'],
      },
    },
    keeper_equity_watch: { type: 'array', items: { type: 'string' } },
    data_gaps: { type: 'array', items: { type: 'string' } },
  },
  required: ['optimal_lineup', 'bench', 'drop_candidates'],
}

const CONTENTION_SCHEMA = {
  type: 'object',
  properties: {
    waiver_mode_used: { type: 'string', description: 'rolling_priority, faab, or both_ambiguous' },
    andrew_priority: { type: 'number' },
    priority_order: { type: 'array', items: { type: 'string' }, description: 'worst record first, teams named in order' },
    teams_ahead_of_andrew: { type: 'array', items: { type: 'string' } },
    claim_sheet: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          order: { type: 'number', description: '1 = the claim to submit first' },
          player: { type: 'string' },
          position: { type: 'string' },
          availability_verified: { type: 'boolean' },
          contenders_ahead: { type: 'array', items: { type: 'string' } },
          probability_reaches_andrew: { type: 'number', description: '0..1' },
          faab_bid_pct: { type: 'number', description: 'percent of a 100-unit budget, if the league is actually FAAB' },
          drop_to_make_room: { type: 'string' },
          win_now_value: { type: 'string' },
          keeper_equity_2027: { type: 'string' },
          blocking_value: { type: 'string', description: 'is this claim worth making purely to deny a rival' },
          rationale: { type: 'string' },
        },
        required: ['order', 'player', 'availability_verified', 'probability_reaches_andrew', 'rationale'],
      },
    },
    contention_map: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          player: { type: 'string' },
          interested_teams: { type: 'array', items: { type: 'string' } },
          expected_winner: { type: 'string' },
        },
        required: ['player', 'interested_teams'],
      },
    },
    do_not_bother: { type: 'array', items: { type: 'string' }, description: 'popular names that will never reach Andrew - do not waste a claim' },
    quiet_wins: { type: 'array', items: { type: 'string' }, description: 'nobody else is tracking these, near-certain to land' },
    assumptions: { type: 'array', items: { type: 'string' } },
    flags: { type: 'array', items: { type: 'string' } },
  },
  required: ['waiver_mode_used', 'claim_sheet', 'contention_map', 'assumptions'],
}

const TRADE_SCHEMA = {
  type: 'object',
  properties: {
    andrew_surplus: { type: 'array', items: { type: 'string' } },
    andrew_needs: { type: 'array', items: { type: 'string' } },
    weeks_to_deadline: { type: 'number', description: 'trade deadline is week 13' },
    offers: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          priority: { type: 'number' },
          to_team: { type: 'string' },
          to_owner: { type: 'string' },
          andrew_sends: { type: 'array', items: { type: 'string' } },
          andrew_receives: { type: 'array', items: { type: 'string' } },
          their_pain_point: { type: 'string', description: 'the acute, sustained need this offer solves for them' },
          why_they_accept: { type: 'string' },
          why_andrew_wins: { type: 'string' },
          keeper_cost_implications: { type: 'string', description: 'what each side gains or loses in 2027 keeper terms' },
          message_to_send: { type: 'string', description: 'the actual sendable text, aimed at THAT owner, two to four sentences' },
          likelihood_accepted: { type: 'number' },
          fallback_if_rejected: { type: 'string' },
        },
        required: ['priority', 'to_team', 'to_owner', 'andrew_sends', 'andrew_receives', 'why_they_accept', 'message_to_send'],
      },
    },
    do_not_trade: { type: 'array', items: { type: 'string' } },
    watch_for_incoming: { type: 'array', items: { type: 'string' }, description: 'offers a rival is likely to send Andrew, and how to read them' },
    phase_note: { type: 'string' },
  },
  required: ['andrew_surplus', 'andrew_needs', 'offers'],
}

const SYNTH_SCHEMA = {
  type: 'object',
  properties: {
    week: { type: 'number' },
    season_phase: { type: 'string' },
    generated_at: { type: 'string' },
    action_card: {
      type: 'array',
      description: 'exactly five, ranked, each one line, readable on a phone in thirty seconds',
      items: {
        type: 'object',
        properties: {
          rank: { type: 'number' },
          action: { type: 'string' },
          deadline: { type: 'string' },
        },
        required: ['rank', 'action'],
      },
    },
    lineup_card: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          slot: { type: 'string' },
          player: { type: 'string' },
          reason: { type: 'string' },
        },
        required: ['slot', 'player'],
      },
    },
    waiver_claims: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          order: { type: 'number' },
          player: { type: 'string' },
          probability: { type: 'number' },
          faab_bid_pct: { type: 'number' },
          drop: { type: 'string' },
          keeper_equity_2027: { type: 'string' },
          note: { type: 'string' },
        },
        required: ['order', 'player', 'probability'],
      },
    },
    drop_candidates: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          rank: { type: 'number' },
          player: { type: 'string' },
          what_you_lose: { type: 'string' },
          keeper_equity_2027: { type: 'string' },
          verdict: { type: 'string' },
        },
        required: ['rank', 'player', 'verdict'],
      },
    },
    trade_board: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          to_owner: { type: 'string' },
          offer: { type: 'string' },
          rationale: { type: 'string' },
          message_to_send: { type: 'string' },
        },
        required: ['to_owner', 'offer', 'rationale'],
      },
    },
    opponent_intel: {
      type: 'array',
      description: 'one short paragraph per rival - all nine',
      items: {
        type: 'object',
        properties: {
          team: { type: 'string' },
          owner: { type: 'string' },
          paragraph: { type: 'string' },
        },
        required: ['team', 'paragraph'],
      },
    },
    keeper_equity_watchlist: {
      type: 'array',
      items: {
        type: 'object',
        properties: {
          player: { type: 'string' },
          where: { type: 'string', description: 'on Andrew roster, on waivers, or on a rival roster' },
          cost_2027: { type: 'string' },
          projected_value: { type: 'string' },
          surplus: { type: 'string' },
          consecutive_year_cap_note: { type: 'string' },
        },
        required: ['player', 'where', 'cost_2027', 'surplus'],
      },
    },
    decisions_to_grade_next_week: { type: 'array', items: { type: 'string' } },
    open_questions: { type: 'array', items: { type: 'string' } },
    data_gaps: { type: 'array', items: { type: 'string' } },
    report_markdown: {
      type: 'string',
      description: 'the complete Tuesday brief as markdown, all 8 sections, ready to write straight to disk',
    },
    state_json: {
      type: 'string',
      description: 'the COMPLETE next state file as a single JSON string, matching the week_N.json schema in the plan. Must parse with JSON.parse.',
    },
  },
  required: ['week', 'action_card', 'lineup_card', 'waiver_claims', 'drop_candidates', 'trade_board', 'opponent_intel', 'keeper_equity_watchlist', 'report_markdown', 'state_json'],
}

/* ------------------------------------------------------------------ *
 * PHASE 1 - parallel intelligence (sonnet x 15)
 * ------------------------------------------------------------------ */

phase('Intelligence')

const NEWS_TOPICS = [
  {
    key: 'injury-practice',
    title: 'INJURY REPORT AND PRACTICE PARTICIPATION',
    brief: [
      'Sweep the official injury reports and practice participation for every fantasy-relevant NFL player.',
      'You care about: new injuries from the week ' + (WEEK - 1) + ' games, designations (Out, Doubtful, Questionable),',
      'DNP vs Limited vs Full practice trends across the week, IR placements and IR-return windows opening,',
      'and anyone returning from injury who displaces a current starter.',
      'A DNP on Wednesday that becomes a Full on Friday is a different signal from three straight DNPs - report the trend, not a snapshot.',
      'Do NOT slice this by NFL team. Slice it by fantasy relevance, and lead with anyone rostered in this 10-team league.',
    ].join('\n'),
  },
  {
    key: 'snap-target-movers',
    title: 'SNAP COUNT AND TARGET SHARE MOVERS',
    brief: [
      'Find the players whose USAGE moved meaningfully in week ' + (WEEK - 1) + ' relative to their prior baseline.',
      'Specifically: snap share deltas, route participation, target share, air yards share, red-zone touches, carry share.',
      'Report both directions - risers who have not yet been rewarded on the scoreboard, and fallers whose points have not yet collapsed.',
      'This is the leading indicator the whole system is built around. A receiver whose route share dropped from 88 percent',
      'to 61 percent is a sell/drop signal a full week before the box score says so.',
      'In this format, receptions and first downs both score, so target VOLUME and short-area/chain-moving usage matter more',
      'than yards per target. Weight accordingly.',
      'Cite the source of every snap or target number.',
    ].join('\n'),
  },
  {
    key: 'depth-chart-roles',
    title: 'DEPTH CHART AND ROLE CHANGES FROM BEAT REPORTING',
    brief: [
      'Read beat reporting, coach pressers and team depth-chart updates from the last 7 days.',
      'You are hunting ROLE PRESSURE: a player quietly losing his job to a teammate, a committee resolving into a lead back,',
      'a rookie taking over a slot, a coaching or coordinator change altering usage, a QB change altering a whole receiving corps.',
      'This is the pressure type that never shows up in a stat line until it is too late, so beat-reporter language is the evidence.',
      'Quote the actual reporter language where it is decisive.',
      'For every role change, name the WINNER and the LOSER, and say whether each is rostered in this league or free.',
    ].join('\n'),
  },
  {
    key: 'breakout-buylow',
    title: 'BREAKOUT AND BUY-LOW CANDIDATES',
    brief: [
      'Identify the players about to break out and the players whose market price in a 10-team keeper league is',
      'irrationally low right now.',
      'Breakout = opportunity has already increased but production has not caught up yet.',
      'Buy-low = production has dipped for reasons that are not predictive (touchdown regression, one bad matchup, a soft injury now healed).',
      'ALSO give the mirror image: sell-high candidates whose recent production is unsustainable, so Andrew can trade them away.',
      'Weight heavily toward young ascending players, because in this league a waiver pickup is keepable next season for a',
      '12th-round pick. A 23-year-old breakout claimed off waivers is worth far more than identical production from a veteran.',
    ].join('\n'),
  },
]

const intel = await parallel([].concat(

  /* 9 opponent agents - one per rival */
  RIVALS.map(function (r) {
    return function () {
      return agent(
        ctxFor('OPPONENT MODEL for ' + r.team + ' (owner ' + r.owner + ')') +
        'You model exactly ONE rival team: ' + r.team + ', owned by ' + r.owner + ' (user_id ' + r.user_id + ').' +
        (r.note ? ' Context on this owner: ' + r.note + '.' : '') + '\n\n' +
        'STEP 1 - GROUND YOURSELF IN DATA.\n' +
        '  Read ' + PREV_STATE_PATH + ' if it exists and pull this team entry out of teams and out of opponent_model.\n' +
        '  Read the raw rosters and users payloads under ' + RAW_DIR + ' to resolve this owner user_id to a roster_id\n' +
        '  and to get the current player list. Use ' + P_PLAYERS + ' to turn player ids into names.\n' +
        '  Read the transactions payload to see every add, drop and claim this team made in week ' + (WEEK - 1) + ',\n' +
        '  INCLUDING which waiver priority they burned - that tells you where they now sit in the order.\n' +
        '  Read the matchups payload to see what this team actually STARTED and what those starters scored.\n\n' +
        'STEP 2 - START FROM THE DETERMINISTIC BASELINE, then refine it. Read ' + ANALYSIS_OUTPUT_PATH + '\n' +
        '  -> opponent_pressure, keyed by roster_id AS A STRING (resolve this owner to a roster_id the same way you\n' +
        '  did in STEP 1). That entry already has VACANCY, PERFORMANCE and DEPTH computed from real roster and\n' +
        '  matchup data - cite those numbers, do not recompute them from box scores yourself. What it does NOT have,\n' +
        '  by construction, is ROLE: that pressure is an external input the baseline script cannot see, and its\n' +
        '  data_gaps will say so explicitly for every position. YOUR job on this step is almost entirely ROLE -\n' +
        '  web-search beat reporting for this team specifically (a player losing snaps, routes or targets to a\n' +
        '  teammate BEFORE the box score reflects it) and layer that on top of the baseline\'s vacancy/performance/\n' +
        '  depth numbers. If you have a concrete, evidenced reason the baseline\'s own numbers look wrong for this\n' +
        '  team (e.g. an injury that happened after the state file was built), say so explicitly and adjust - do not\n' +
        '  silently override a code-computed number with a vibe. Show the evidence for each pressure - a number with\n' +
        '  no evidence behind it is worthless to the model downstream.\n\n' +
        'STEP 3 - PREDICT. ' + ANALYSIS_OUTPUT_PATH + ' -> predicted_claims, keyed by this owner\'s name, already has a\n' +
        '  first-pass predicted-claims list for this team computed from the baseline pressure crossed with the real\n' +
        '  verified free-agent pool. Start there, cite it, and refine it: does your ROLE finding from STEP 2 change\n' +
        '  what this manager is actually likely to chase this week? Add or reorder specific free agents with your own\n' +
        '  likelihoods where you have a concrete reason to differ from the baseline, and say what that reason is.\n' +
        '  Do not invent a claims list from nothing when a computed first pass already exists. Also predict who\n' +
        '  they would drop to make room.\n\n' +
        'STEP 4 - TRADE READ. What position are they acutely and SUSTAINABLY short at? Where do they have surplus?\n' +
        '  A team with acute sustained need at a position where Andrew has surplus is a team that will overpay.\n' +
        '  Name specific players on their roster Andrew should want.\n\n' +
        'STEP 5 - BLOCKING. Is there a cheap claim that would hurt this team more than the roster spot costs Andrew?\n\n' +
        'DIFF, DO NOT RE-DERIVE. If last week state exists, your most valuable output is what CHANGED. Say explicitly\n' +
        'what moved since last week and what is unchanged. Do not re-litigate a settled roster.\n' +
        'Be honest about confidence. Low confidence stated plainly is more useful than a confident guess.',
        { label: 'opponent:' + r.owner, phase: 'Intelligence', schema: OPPONENT_SCHEMA, model: 'sonnet' }
      )
    }
  }),

  /* 4 news agents - sliced by TOPIC, never by team, to avoid nine agents reading the same wire */
  NEWS_TOPICS.map(function (t) {
    return function () {
      return agent(
        ctxFor('NEWS SWEEP - ' + t.title) +
        'You own ONE topic slice of the league-wide news sweep. Three other news agents are covering the other slices\n' +
        'in parallel, so stay strictly inside your lane and do not pad your answer with their material.\n\n' +
        'YOUR SLICE:\n' + t.brief + '\n\n' +
        'METHOD:\n' +
        '  1. Web-search aggressively. This is week ' + WEEK + ' of the ' + SEASON + ' season and today is ' + TODAY + '.\n' +
        '     Everything you report must be from the last 7 days. Search for the current week explicitly.\n' +
        '  2. Cross-reference against the league. Read ' + PREV_STATE_PATH + ' and the rosters payload under ' + RAW_DIR + '\n' +
        '     so you can mark each player as rostered by a specific Sunday Scaries team, or FREE AGENT, or UNKNOWN.\n' +
        '     A free agent with a role change is a waiver target. A rostered player with a role change is a trade or\n' +
        '     start/sit call. The distinction is the whole point, so make it for every single item.\n' +
        '  3. Rank by fantasy impact in THIS league. A backup on a team nobody in this league rosters is noise. Cut it.\n\n' +
        'Every item needs a real source and a real date. If a claim is older than 7 days, set is_stale true rather than\n' +
        'dropping the date or fudging it. Aim for roughly 12 to 25 genuinely load-bearing items, not an exhaustive dump.',
        { label: 'news:' + t.key, phase: 'Intelligence', schema: NEWS_SCHEMA, model: 'sonnet' }
      )
    }
  }),

  /* free agent pool */
  [function () {
    return agent(
      ctxFor('FREE AGENT POOL - rank everyone actually available IN THIS LEAGUE') +
      'You produce the definitive ranked board of players who are genuinely unrostered in this specific 10-team league.\n\n' +
      'STEP 1 - START FROM THE DETERMINISTIC POOL, then extend it. Read ' + ANALYSIS_OUTPUT_PATH + '\n' +
      '  -> verified_free_agents. Its .raw.confirmed_available_known_players and .raw.available_defenses were built\n' +
      '  in code as the complement of every rostered player id against the local players cache - that IS the hard\n' +
      '  availability gate, already correct, do not re-derive the union yourself unless that file is missing. Its\n' +
      '  .valued_pool wraps the same list with a placeholder value (positional replacement-level points, NOT a real\n' +
      '  projection - it exists only so the pressure model had a number to sort by before you ran). Your job is to\n' +
      '  turn that placeholder pool into a real ranked board: replace the placeholder value with an actual\n' +
      '  rest-of-season projection for every name, and go find the free agents the local cache does not know about\n' +
      '  yet (the cache is missing players outside the 222 ids it has seen in draft/transaction payloads - the raw\n' +
      '  section says exactly how many). For anyone you add that is NOT already in verified_free_agents, you must\n' +
      '  independently confirm him unrostered against every roster in the rosters payload under ' + RAW_DIR + ' before\n' +
      '  naming him - the STEP 1 gate below still applies to net-new names.\n' +
      '  Also read the Sleeper trending-adds payload if present: it shows what is being claimed across all of Sleeper,\n' +
      '  which is a strong proxy for who the rest of THIS league is about to claim.\n\n' +
      'STEP 2 - RANK BY REST-OF-SEASON VALUE IN THIS FORMAT. Not generic PPR ranks. Half-PPR plus 0.5 per first down\n' +
      '  rewards volume and chain-moving; superflex makes any startable QB far more valuable than his raw points suggest.\n' +
      '  Give a projected weekly point figure in THIS format for the top names.\n\n' +
      'STEP 3 - OPPORTUNITY, NOT POINTS. Justify every ranking with snaps, routes, target share or carry share. Web-search\n' +
      '  for current usage data. In weeks 1-3 especially, points are noise and opportunity is signal.\n\n' +
      'STEP 4 - KEEPER EQUITY. Anyone claimed off waivers is keepable in 2027 for a 12TH-ROUND PICK. So flag every young\n' +
      '  ascending player whose 2027 value would wildly exceed a 12th. That is the largest non-obvious edge in this league\n' +
      '  and it should visibly reorder your board relative to a pure win-now ranking.\n\n' +
      'STEP 5 - STREAMERS. Separate lists for QB, TE and DEF streaming for week ' + WEEK + ' specifically, matchup-aware.\n' +
      '  Note that DEF scoring in this league was buggy and is supposedly being fixed - flag that uncertainty.\n\n' +
      'HARD GATE: set availability_verified true ONLY for players you actually checked against all ten rosters.\n' +
      'Anything you could not verify goes in unverified_excluded instead of the main board. Recommending a rostered\n' +
      'player is the most damaging failure this system can produce.',
      { label: 'free-agents', phase: 'Intelligence', schema: FA_SCHEMA, model: 'sonnet' }
    )
  }],

  /* my team */
  [function () {
    return agent(
      ctxFor("ANDREW'S OWN TEAM - lineup, byes, injuries, sell-high") +
      'You cover roster_id ' + ANDREW_ROSTER_ID + ' only (' + ANDREW_HANDLE + ').\n\n' +
      'STEP 1 - GET THE ROSTER RIGHT. Read the rosters payload under ' + RAW_DIR + ', pull roster_id ' + ANDREW_ROSTER_ID + ',\n' +
      '  resolve every player id through ' + P_PLAYERS + '. If any id does not resolve, say so by id rather than\n' +
      '  silently dropping the player - unidentified bench players have been a recurring problem in this league.\n' +
      '  Read ' + PREV_STATE_PATH + ' for last week context and ' + P_REFERENCE + ' for keeper costs.\n\n' +
      'STEP 2 - OPTIMAL LINEUP for week ' + WEEK + '. Fill all ten slots: QB, RB, RB, WR, WR, TE, FLEX, FLEX, SUPER_FLEX, DEF.\n' +
      '  SUPER_FLEX should almost always be a second QB in this format - check whether Andrew has one, and if not,\n' +
      '  that is a five-alarm roster hole, not a footnote.\n' +
      '  Web-search current week matchups, injury designations and Vegas totals for his players before locking calls.\n' +
      '  Give a reason ONLY where the call is non-obvious. Do not write a paragraph justifying starting an obvious stud.\n' +
      '  Flag every close call with the projected margin so Andrew can overrule you knowingly.\n' +
      '  NOTE the open question on FLEX count - assume 2 FLEX, and say which player drops out if it is really 1.\n\n' +
      'STEP 3 - BYES. Look ahead through the rest of the season, not just this week. Which future weeks does he have a\n' +
      '  positional hole he cannot cover from his own bench? Name the week, the position and the plan.\n\n' +
      'STEP 4 - SELL HIGH AND BUY LOW. Who on his roster is producing above his true level right now, and who is he\n' +
      '  underrating? Feed this to the trade board.\n\n' +
      'STEP 5 - DROP CANDIDATES, ranked by what he actually loses. Account for keeper equity: a cheap young waiver add\n' +
      '  is keepable for a 12th in 2027, so dropping him costs more than his current points suggest. Note anyone at risk\n' +
      '  of hitting the 3-consecutive-year keeper cap.\n\n' +
      'STEP 6 - SEASON PHASE. Apply the phase defaults listed above without being told twice. In weeks 1-3 do not cut a\n' +
      '  good player over one bad box score. In weeks 14-17, if elimination looks likely, flip to keeper accumulation.',
      { label: 'my-team', phase: 'Intelligence', schema: MYTEAM_SCHEMA, model: 'sonnet' }
    )
  }]

))

const opponents = clean(intel.slice(0, RIVALS.length))
const news = clean(intel.slice(RIVALS.length, RIVALS.length + NEWS_TOPICS.length))
const freeAgents = intel[RIVALS.length + NEWS_TOPICS.length] || null
const myTeam = intel[RIVALS.length + NEWS_TOPICS.length + 1] || null

const OPP_PACK = pack(opponents, 60000)
const NEWS_PACK = pack(news, 60000)
const FA_PACK = pack(freeAgents, 40000)
const MY_PACK = pack(myTeam, 25000)

/* ------------------------------------------------------------------ *
 * PHASE 2 - cross-analysis (opus x 2)
 * ------------------------------------------------------------------ */

phase('Cross-Analysis')

const cross = await parallel([

  function () {
    return agent(
      ctxFor('THE WAIVER CONTENTION MODEL') +
      'This is the stage that converts a flat wishlist into an ORDERED claim sheet. Andrew does not need to know who\n' +
      'the best available players are - he needs to know which of them will actually still be there when his turn comes.\n\n' +
      '=== DETERMINISTIC BASELINE (read this first) ===\n' +
      'Read ' + ANALYSIS_OUTPUT_PATH + ' -> waiver_contention. This is a full CONTENTION_SCHEMA-shaped report already\n' +
      'computed in code by waiver_contention.py: a seeded Monte Carlo simulation of the actual rolling-priority\n' +
      'processing order (not a closed-form guess), run over every player in verified_free_agents, using the\n' +
      "opponent_pressure baseline's predicted_claims as each rival's wishlist. Its priority_order, andrew_priority,\n" +
      'teams_ahead_of_andrew, claim_sheet, contention_map, do_not_bother and quiet_wins are your STARTING POINT, not\n' +
      'background reading - do not re-run the arithmetic by hand, you will get a worse answer than the simulation.\n' +
      'Your job is to REFINE it: the baseline was built with no role_signals (the news agents had not run yet), so it\n' +
      "cannot see a rival's beat-reported role change that would send them after a different player than their\n" +
      'box-score-derived predicted_claims suggested. Use the nine rival models and news sweep below - which DO have\n' +
      'that qualitative layer - to adjust specific probabilities where you have a concrete reason to, cite the\n' +
      'baseline number you are moving away from and why, and keep everything else from the simulation as-is.\n\n' +
      '=== NINE RIVAL MODELS (pressure scores and predicted claims, refined with qualitative signal) ===\n' + OPP_PACK + '\n\n' +
      '=== RANKED FREE AGENT POOL ===\n' + FA_PACK + '\n\n' +
      "=== ANDREW'S TEAM ===\n" + MY_PACK + '\n\n' +
      '=== NEWS SWEEP (four topic slices) ===\n' + NEWS_PACK + '\n\n' +
      '=== WHAT TO PRODUCE ===\n' +
      '1. ESTABLISH THE ORDER. The baseline already resolved this from the rosters payload - confirm priority_order\n' +
      '   and andrew_priority match it, then read the week ' + (WEEK - 1) + ' transactions payload yourself to check\n' +
      '   nothing has burned priority SINCE the state file was built (this can only move the order later than the\n' +
      '   baseline, never earlier). State where Andrew sits and exactly who picks ahead of him.\n' +
      '   The declared mode from args for this run is: ' + WAIVER_MODE + '. The baseline used: waiver_mode_used in its\n' +
      '   output. THE LEAGUE SETTING IS AMBIGUOUS - the commissioner says rolling priority but Sleeper carries a\n' +
      '   100-unit budget field that usually means FAAB. Produce BOTH answers: a priority-ordered claim sheet AND a\n' +
      '   FAAB bid percentage for each target. Flag the ambiguity loudly at the top. Do not quietly pick one and hope.\n\n' +
      '2. FOR EVERY TARGET, start from the baseline probability_reaches_andrew in claim_sheet / contention_map and\n' +
      '   adjust it where your qualitative read of a specific rival genuinely changes their odds of chasing that\n' +
      '   player (a role change that redirects their need, an injury the state file predates, etc). Show your\n' +
      '   reasoning for every adjustment - a moved number with no reason attached is not auditable and Andrew should\n' +
      "   not trust it. Where you have no reason to move a number, keep the baseline's.\n\n" +
      '3. ORDER THE CLAIMS. Rank by expected value, not raw player quality. A 90 percent chance at the fourth-best player\n' +
      '   beats a 10 percent chance at the best. Explicitly list the players NOT worth claiming because they will never\n' +
      '   reach him, and separately the QUIET WINS nobody else is tracking.\n\n' +
      '4. BLOCKING. Flag any case where claiming a player purely to deny a rival is worth more than the roster spot.\n' +
      '   Be strict here - blocking is usually a trap and is only correct when the rival need is acute and the player is\n' +
      '   uniquely the fix.\n\n' +
      '5. KEEPER EQUITY ON EVERY CLAIM. A waiver add is keepable in 2027 for a 12TH-ROUND PICK. Every recommendation\n' +
      '   carries both a win-now value and a 2027 keeper-equity flag. In the late season those weights invert.\n\n' +
      '6. DROPS. For each claim, name who Andrew drops to make room, and confirm the roster maths works.\n\n' +
      'HARD GATE: every player you name must appear in the baseline verified_free_agents gate (see analysis baseline\n' +
      'above and rule 1 of NON-NEGOTIABLE RULES). If the free-agent agent marked a player availability_verified false\n' +
      'and he is not in the baseline gate either, leave him off. Recommending a rostered player is the worst failure\n' +
      'this system can produce.',
      { label: 'waiver-contention', phase: 'Cross-Analysis', schema: CONTENTION_SCHEMA, model: 'opus', effort: 'high' }
    )
  },

  function () {
    return agent(
      ctxFor('THE TRADE BOARD') +
      'You match Andrew positional surplus against each rival acute need, and draft specific, sendable offers.\n\n' +
      '=== DETERMINISTIC BASELINE (read this first) ===\n' +
      'Read ' + ANALYSIS_OUTPUT_PATH + ' -> waiver_contention and -> opponent_pressure. A rival who is heavily\n' +
      'contested on the waiver wire for a position (see do_not_bother / contention_map / a rival whose\n' +
      'predicted_claims keep losing out in the baseline simulation) is a rival who cannot fix that hole from waivers\n' +
      'and is a MUCH better trade target for the same need than one who can plug it Wednesday for free. Use the\n' +
      'baseline claim_sheet and pressure numbers as given facts about who is actually short and how easily they can\n' +
      'self-solve it - do not re-derive pressure scores yourself, cite them and reason from them alongside the\n' +
      'refined rival models below.\n\n' +
      '=== NINE RIVAL MODELS (needs, surplus, pressure, trade appetite) ===\n' + OPP_PACK + '\n\n' +
      "=== ANDREW'S TEAM (surplus, holes, sell-high, buy-low) ===\n" + MY_PACK + '\n\n' +
      '=== NEWS SWEEP ===\n' + NEWS_PACK + '\n\n' +
      '=== FREE AGENT POOL (a rival can fix a need from waivers instead of trading - price accordingly) ===\n' + FA_PACK + '\n\n' +
      '=== WHAT TO PRODUCE ===\n' +
      '1. Establish Andrew surplus and needs precisely, in starting-lineup terms - QB, RB, RB, WR, WR, TE, FLEX, FLEX,\n' +
      '   SUPER_FLEX, DEF. Surplus means startable players beyond what the lineup can hold, not merely good players.\n' +
      '   In superflex, a second startable QB is close to untouchable - do not casually trade one away.\n\n' +
      '2. Build 3 to 6 CONCRETE offers. Each one names exact players both ways, aimed at ONE owner, built on that owner\n' +
      '   ACTUAL current situation as captured in the rival models. A generic offer is worthless. The strongest offers\n' +
      '   go to teams with acute, SUSTAINED need at a position where Andrew has surplus - those teams overpay.\n\n' +
      '3. Write the actual message to send. Two to four sentences, in a normal league-chat voice, framed around what\n' +
      '   solves THEIR problem. Not a spreadsheet, not a hard sell, and never condescending about their roster.\n\n' +
      '4. Price in keeper cost on both sides. A player costing a 12th to keep in 2027 is worth materially more than an\n' +
      '   equivalent player costing a 2nd. Rival managers in this league consistently under-price that, which is exactly\n' +
      '   where the edge is. Say when Andrew should pay a premium in current points to acquire cheap 2027 keeper cost.\n\n' +
      '5. Season phase discipline. Current phase: ' + PHASE_INFO.name + '.\n' +
      '   Weeks 4-8 is the window where offers actually land - be aggressive. Weeks 9-13 means the week 13 deadline is\n' +
      '   closing and consolidation must happen before it. After week 13 no trade is possible at all - if that has passed,\n' +
      '   say so in one line and pivot this section entirely to waiver and streaming strategy rather than inventing offers.\n\n' +
      '6. Incoming. Predict which rivals will approach Andrew and what they will ask for, so he is not caught flat.\n\n' +
      '7. Do-not-trade list, with the reason.',
      { label: 'trade-board', phase: 'Cross-Analysis', schema: TRADE_SCHEMA, model: 'opus', effort: 'high' }
    )
  },

])

const contention = cross[0] || null
const tradeBoard = cross[1] || null

/* ------------------------------------------------------------------ *
 * PHASE 3 - synthesis (opus x 1) - the 8-part Tuesday output
 * ------------------------------------------------------------------ */

phase('Synthesis')

const synthesis = await agent(
  ctxFor('FINAL SYNTHESIS - the Tuesday brief and the new state file') +
  'Everything below was produced in parallel by fifteen research agents and two analysis agents. Your job is to turn it\n' +
  'into ONE document Andrew can act on, plus the state file that makes next week cheap. You are the last stop: if two\n' +
  'inputs contradict each other, you resolve it and say which you trusted and why. Do not paste conflicting claims through.\n\n' +
  '=== WAIVER CONTENTION MODEL ===\n' + pack(contention, 45000) + '\n\n' +
  '=== TRADE BOARD ===\n' + pack(tradeBoard, 30000) + '\n\n' +
  "=== ANDREW'S TEAM ===\n" + MY_PACK + '\n\n' +
  '=== NINE RIVAL MODELS ===\n' + OPP_PACK + '\n\n' +
  '=== NEWS SWEEP (four topic slices) ===\n' + NEWS_PACK + '\n\n' +
  '=== FREE AGENT POOL ===\n' + FA_PACK + '\n\n' +
  '=== DELIVERABLE 1: report_markdown, in exactly these 8 sections ===\n' +
  '1. ACTION CARD. The top five things to do, ranked, each ONE line. This is read on a phone in thirty seconds while\n' +
  '   half-awake. If it needs a second line it belongs in a later section. Include the deadline on anything time-boxed\n' +
  '   (waivers process midweek - claims must be in before then).\n' +
  '2. LINEUP CARD. Every slot: QB, RB, RB, WR, WR, TE, FLEX, FLEX, SUPER_FLEX, DEF. A short reason ONLY where the call\n' +
  '   is non-obvious. Do not explain starting an obvious stud.\n' +
  '3. WAIVER CLAIMS, ORDERED, each with an honest probability of landing given who picks ahead of him, plus a FAAB bid\n' +
  '   figure in case the league turns out to be FAAB, plus the corresponding drop. Honest means honest - if the top\n' +
  '   target is 25 percent, print 25 percent.\n' +
  '4. DROP CANDIDATES, ranked by what he actually loses, with keeper equity accounted for.\n' +
  '5. TRADE BOARD. Specific offers to specific owners, each with the sendable message text.\n' +
  '6. OPPONENT INTEL. One short paragraph per rival, all NINE of them, none skipped: what changed, what they need,\n' +
  '   what they will likely do. If a rival model came back thin, say the model was thin rather than padding it.\n' +
  '7. KEEPER-EQUITY WATCHLIST. Who on his roster and on waivers is accumulating 2027 value, with 2027 cost and surplus.\n' +
  '   Track the 3-consecutive-year cap - Bo Nix and Jameson Williams hit their final eligible year in 2027 if kept again.\n' +
  '8. OPEN QUESTIONS AND DATA GAPS. What this run could not confirm, plus the standing league open questions: waiver\n' +
  '   type (priority vs FAAB), waiver processing day and time, FLEX count 1 vs 2, and whether the DEF scoring fix landed.\n' +
  '   Never hide a gap. A silent gap becomes a bad claim next week.\n\n' +
  'Start the markdown with a heading naming the week and the run date, and a two-sentence bottom line above the action card.\n\n' +
  '=== DELIVERABLE 2: state_json ===\n' +
  'A single JSON string - it MUST parse with JSON.parse - holding ONLY the model-derived sections of the week ' + WEEK + '\n' +
  'state file. Emit exactly these four keys and NOTHING else:\n' +
  '  opponent_model (keyed by roster_id AS A STRING: pressure per position, vulnerable_starters, predicted_claims,\n' +
  '    trade_appetite, confidence),\n' +
  '  keeper_equity (list of {player, acquired, keeper_cost_2027, projected_value, surplus}),\n' +
  '  decisions_log (append this week recommendations with action_taken null and outcome null, so next week can grade\n' +
  '    them - and if last week state exists, GRADE last week entries by filling in their outcome from what actually\n' +
  '    scored. That self-grading is what stops the system repeating a bad heuristic all season),\n' +
  '  open_questions (list of strings).\n' +
  'DO NOT emit meta, standings, teams, transaction_log, matchups, injuries, free_agents or waiver_order. Those are\n' +
  'already computed deterministically in ' + STATE_PATH + ' by state_builder.py, straight from the Sleeper payloads.\n' +
  'Re-deriving them by hand can only introduce error, and merge_state.py will discard whatever you write for them.\n' +
  'Carry forward anything from last week decisions_log and open_questions that is still live. Do not drop history:\n' +
  'the state file is the memory, and the chat is not.\n\n' +
  'Also fill in the structured fields alongside the markdown, because a dashboard reads those directly.\n' +
  'Be concrete. Name real players. Andrew is going to act on this today.',
  { label: 'synthesis:week' + WEEK, phase: 'Synthesis', schema: SYNTH_SCHEMA, model: 'opus', effort: 'high' }
)

/* ------------------------------------------------------------------ *
 * 5. Return - the caller writes the report and the state file
 * ------------------------------------------------------------------ */

function field(obj, key, fallback) {
  if (obj && typeof obj === 'object' && typeof obj[key] !== 'undefined' && obj[key] !== null) return obj[key]
  return fallback
}

const reportMarkdown = field(synthesis, 'report_markdown',
  typeof synthesis === 'string' ? synthesis : '(synthesis agent returned no report_markdown)')
const stateJson = field(synthesis, 'state_json', '')

let stateParsed = null
let stateParseError = null
try {
  stateParsed = stateJson ? JSON.parse(stateJson) : null
} catch (e) {
  stateParseError = String(e && e.message ? e.message : e)
}

return {
  meta: {
    workflow: 'sunday-scaries-weekly',
    league_id: LEAGUE_ID,
    season: SEASON,
    week: WEEK,
    week_source: WEEK_SOURCE,
    run_date: TODAY,
    season_phase: PHASE_INFO.name,
    waiver_mode_arg: WAIVER_MODE,
    analysis_output_path: ANALYSIS_OUTPUT_PATH,
    args_received: ARGS,
  },
  write_targets: {
    report: REPORT_PATH,
    /* Write state_json HERE, not to state. week_N.json is the deterministic file
     * state_builder.py produced; overwriting it with model output destroys the
     * only non-hallucinable record of the week. */
    state: SYNTH_STATE_PATH,
    deterministic_state: STATE_PATH,
    merged_state: STATE_PATH,
    merge_command: 'python3 ' + SYS + '/merge_state.py --week ' + WEEK,
    prev_state: PREV_STATE_PATH,
  },
  report_markdown: reportMarkdown,
  state_json: stateJson,
  state_parsed: stateParsed,
  state_parse_error: stateParseError,
  synthesis: synthesis,
  contention: contention,
  trade_board: tradeBoard,
  my_team: myTeam,
  free_agents: freeAgents,
  news: news,
  opponents: opponents,
  counts: {
    opponents: opponents.length,
    news: news.length,
    intelligence_agents_dispatched: RIVALS.length + NEWS_TOPICS.length + 2,
    intelligence_agents_returned: clean(intel).length,
  },
}
