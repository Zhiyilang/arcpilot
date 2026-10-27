"""Offline ablation harness: measure what each policy gate contributes.

The Kaggle leaderboard needs the real environment; this harness answers the
paper's Theory question offline — *why* the four gates exist — on deterministic
synthetic games with hidden semantics:

  maze_clean   4x4 open field, two secret movement actions, five decoy no-ops.
  corridor     1x13 corridor, one movement action, budget 30 (exploitation is
               necessary: blind probing burns ~7 actions per cell).
  noisy        maze_clean plus a stochastic action (moves right with p=0.5) —
               the regime where single-observation confirmation mislearns.
  decoy_home   maze_clean plus a "step toward start" action with the LOWEST
               action id: once confirmed it outranks the movement actions in
               the exploit gate and walks the player home.
  two_level    maze_clean with a mid-grid checkpoint (levels_completed moves),
               so the progress signal is live while the tail arrives.

Configurations (gate flags, everything else identical):
  full           the shipped agent
  no_test_first  test_first=False
  confirm_n1     confirm_threshold=1
  no_repeat_off  no_repeat=False
  reserve_off    reserve=0

Run:  python ablation.py          -> markdown tables + a per-gate summary
     python ablation.py --json    -> machine-readable rows
"""

from __future__ import annotations

import json
import random
import sys

from arcpilot.agent import ArcPilotAgent
from arcpilot.frame import make_frame, frame_signature, grids_equal
from arcpilot.hypothesis import HypothesisLedger

TERMINAL = ("WIN", "WON", "GAME_OVER", "LOSE", "LOST")


class SyntheticGame:
    """Deterministic hidden-semantics game in the arcpilot frame shape.

    The agent sees only frames. Which action moves which way, which action is a
    decoy, which one steps home — all private to the game object.
    """

    def __init__(self, name, rows, cols, start, goal, moves, decoys=(),
                 home=None, flaky=None, flaky_p=0.5, checkpoints=(), seed=7,
                 budget=80):
        self.name = name
        self.rows, self.cols = rows, cols
        self.start, self.goal = start, goal
        self.moves = dict(moves)            # action_id -> (dr, dc)
        self.decoys = list(decoys)          # actions that never change anything
        self.home = home                    # action stepping one cell toward start
        self.flaky = flaky                  # stochastic action
        self.flaky_p = flaky_p
        self.checkpoints = list(checkpoints)
        self.seed = seed
        self.budget = budget                # per-game action cap
        self.rng = random.Random(seed)
        self.pos = start
        self._reached = set()
        self.steps = 0
        ids = set(self.moves) | set(self.decoys)
        if self.home is not None:
            ids.add(self.home)
        if self.flaky is not None:
            ids.add(self.flaky)
        self.actions = sorted(ids)

    def reset(self):
        self.rng = random.Random(self.seed)
        self.pos = self.start
        self._reached = set()
        self.steps = 0
        return self._frame("PLAYING")

    def _frame(self, state):
        grid = [[0] * self.cols for _ in range(self.rows)]
        r, c = self.pos
        grid[r][c] = 1
        gr, gc = self.goal
        grid[gr][gc] = 5
        return make_frame(grid, state=state,
                          levels_completed=len(self._reached),
                          game_id=self.name,
                          guid="%s#%d" % (self.name, self.steps))

    def step(self, frame, action_id):
        """Apply an action; return the next frame. Walls/edges are no-ops."""
        self.steps += 1
        r, c = self.pos
        nr, nc = r, c
        if action_id in self.moves:
            dr, dc = self.moves[action_id]
            nr, nc = r + dr, c + dc
        elif self.home is not None and action_id == self.home:
            if r > 0:
                nr = r - 1
            elif c > 0:
                nc = c - 1
        elif self.flaky is not None and action_id == self.flaky:
            if self.rng.random() < self.flaky_p:
                dr, dc = self.moves.get(self.flaky, (0, 1))
                nr, nc = r + dr, c + dc
        if not (0 <= nr < self.rows and 0 <= nc < self.cols):
            nr, nc = r, c  # edge: the action does nothing here
        self.pos = (nr, nc)
        state = "PLAYING"
        if self.pos in self.checkpoints and self.pos not in self._reached:
            self._reached.add(self.pos)
        if self.pos == self.goal:
            state = "WIN"
            self._reached.add(self.goal)
        return self._frame(state)


def game_family():
    """The fixed game family every configuration is measured on.

    Movement games use the full four directions (like real ARC-AGI-3 action
    sets), so the agent can return to earlier states and the no-repeat
    covering design is exercisable; interior goals (not just corners) are the
    hard case. Regime games then stress one mechanism each.
    """
    return [
        # capability baseline: interior goal, four directions, three decoys
        SyntheticGame("maze_clean", 4, 4, (0, 0), (2, 2),
                      moves={2: (0, -1), 3: (0, 1), 5: (-1, 0), 6: (1, 0)},
                      decoys=[1, 4, 7]),
        # exploitation regime: one movement action, tight budget (blind
        # probing burns ~7 actions per cell; the budget only fits a sweep)
        SyntheticGame("corridor", 1, 13, (0, 0), (0, 12),
                      moves={3: (0, 1)}, decoys=[1, 2, 4, 5, 6, 7],
                      budget=30),
        # long-horizon version of the same regime (budget 80, tail reachable)
        SyntheticGame("long_corridor", 1, 25, (0, 0), (0, 24),
                      moves={3: (0, 1)}, decoys=[1, 2, 4, 5, 6, 7]),
        # resistant decoy: a "step toward start" action whose effect signature
        # varies with direction, so it resists the consistency gate
        SyntheticGame("decoy_home", 4, 4, (0, 0), (2, 2),
                      moves={2: (0, -1), 3: (0, 1), 5: (-1, 0), 6: (1, 0)},
                      decoys=[1, 7], home=4),
        # live progress signal: a mid-grid checkpoint moves levels_completed,
        # so the stall trigger and the exploitation reserve both engage
        SyntheticGame("two_level", 4, 4, (0, 0), (2, 2),
                      moves={2: (0, -1), 3: (0, 1), 5: (-1, 0), 6: (1, 0)},
                      decoys=[1, 4, 7], checkpoints=[(1, 1)]),
        # stochastic regime: the ONLY movement action is a coin flip — the
        # agent cannot avoid using it, so stochastic effects enter the ledger
        # and the confirmation threshold is what stands between the agent and
        # a half-true belief (20 seeds)
        SyntheticGame("stochastic_corridor", 1, 13, (0, 0), (0, 12),
                      moves={}, decoys=[1, 2, 4, 5, 6, 7],
                      flaky=3, flaky_p=0.5),
    ]


CONFIGS = {
    "full": {},
    "no_test_first": {"test_first": False},
    "confirm_n1": {"confirm_threshold": 1},
    "no_repeat_off": {"no_repeat": False},
    "reserve_off": {"reserve": 0},
}

STOCHASTIC_SEEDS = 20  # seeds averaged for games with a stochastic action

MOVE_SIG = (2, ((0, 1), (1, 0)), ((0.0, -0.5), (0.0, 0.5)))  # one-cell horizontal move
NO_OP_SIG = (0, (), ())                                        # nothing changed


def confirmation_calibration(p=0.5, trials=2000, seed=11):
    """P(a coin-flip action ends up CONFIRMED) under n=1 vs n=2.

    Direct measurement of the confirmation-threshold tradeoff, isolated from
    every other mechanism: a synthetic action whose effect is MOVE with
    probability p and no-op otherwise, driven through the REAL
    HypothesisLedger. The model's consistency gate proposes only after two
    consistent observations (probability p^2); the ledger then confirms after
    `threshold` further consistent tests (probability p^t) or refutes on the
    first mismatch. Hence P(confirm) = p^(2+t): for a fair coin, 12.5% at
    n=1 versus 6.25% at n=2 — the two-observation rule halves the rate at
    which a coin flip hardens into a belief the agent will act on.
    """
    rng = random.Random(seed)
    out = {}
    for threshold in (1, 2):
        confirmed = 0
        proposed = 0
        for _ in range(trials):
            led = HypothesisLedger(confirm_threshold=threshold)
            first = MOVE_SIG if rng.random() < p else NO_OP_SIG
            second = MOVE_SIG if rng.random() < p else NO_OP_SIG
            if first != MOVE_SIG or second != MOVE_SIG:
                continue  # the consistency gate never proposes
            proposed += 1
            hid = led.propose("flaky action moves", 3, MOVE_SIG)
            for _ in range(1000):  # a.s. terminates for 0 < p < 1
                if led.get(hid).status != "active":
                    break
                obs = MOVE_SIG if rng.random() < p else NO_OP_SIG
                led.record(hid, "g", obs)
            if led.get(hid).status == "confirmed":
                confirmed += 1
        out[threshold] = {"p_confirm": confirmed / trials,
                          "p_confirm_given_proposed": (confirmed / proposed) if proposed else 0.0,
                          "analytic": p ** (2 + threshold)}
    return out


def run_agent(game, max_actions=None, config="custom", **kwargs):
    """Run the agent on one game; return the metrics the paper reports."""
    if max_actions is None:
        max_actions = game.budget
    agent = ArcPilotAgent(available_actions=game.actions,
                          max_actions=max_actions, **kwargs)
    frame = game.reset()
    agent.reset(frame)
    trace = []
    noops = 0
    exploits = 0
    steps = 0
    while steps < max_actions and not agent.is_done():
        sig = frame_signature(agent.frames[-1])
        action_id, reason = agent.choose_action()
        steps += 1
        prev = agent.frames[-1]
        frame = game.step(frame, action_id)
        agent.step_frame(frame)
        trace.append((sig, action_id))
        if grids_equal(prev, frame):
            noops += 1
        if reason.startswith("exploit"):
            exploits += 1
    last = agent.frames[-1]
    repeats = len(trace) - len(set(trace))
    return {
        "game": game.name,
        "config": config,
        "win": str(last.get("state", "")).upper() in ("WIN", "WON"),
        "steps": steps,
        "levels": int(last.get("levels_completed", 0) or 0),
        "noop_actions": noops,
        "repeat_pairs": repeats,
        "confirmed": len(agent.ledger.by_status("confirmed")),
        "refuted": len(agent.ledger.by_status("refuted")),
        "exploit_actions": exploits,
    }


def run_random(game, max_actions=None, seed=0):
    """Seeded random-action baseline (the efficiency reference point)."""
    if max_actions is None:
        max_actions = game.budget
    rng = random.Random(seed)
    frame = game.reset()
    steps = 0
    while steps < max_actions and str(frame.get("state", "")).upper() not in TERMINAL:
        action_id = rng.choice(game.actions)
        steps += 1
        frame = game.step(frame, action_id)
    return {
        "game": game.name,
        "config": "random(seed=%d)" % seed,
        "win": str(frame.get("state", "")).upper() in ("WIN", "WON"),
        "steps": steps,
        "levels": int(frame.get("levels_completed", 0) or 0),
    }


def _mean(rows, key):
    vals = [r[key] for r in rows if key in r]
    return sum(vals) / len(vals) if vals else 0.0


def _aggregate(game, config, max_actions, kwargs):
    """One (game, config) cell: single run for deterministic games,
    seed-averaged run for stochastic ones."""
    if game.flaky is None:
        row = run_agent(game, max_actions=max_actions, config=config, **kwargs)
        row["seeds"] = 1
        return row
    runs = []
    for seed in range(STOCHASTIC_SEEDS):
        g = SyntheticGame(game.name, game.rows, game.cols, game.start, game.goal,
                          moves=game.moves, decoys=game.decoys, home=game.home,
                          flaky=game.flaky, flaky_p=game.flaky_p,
                          checkpoints=game.checkpoints, seed=seed,
                          budget=game.budget)
        runs.append(run_agent(g, max_actions=max_actions, config=config, **kwargs))
    return {
        "game": game.name, "config": config, "seeds": len(runs),
        "win": _mean(runs, "win"),
        "steps": _mean(runs, "steps"),
        "levels": _mean(runs, "levels"),
        "noop_actions": _mean(runs, "noop_actions"),
        "repeat_pairs": _mean(runs, "repeat_pairs"),
        "confirmed": _mean(runs, "confirmed"),
        "refuted": _mean(runs, "refuted"),
        "exploit_actions": _mean(runs, "exploit_actions"),
    }


def matrix(games=None, configs=None, max_actions=None, random_seeds=(0, 1, 2, 3, 4)):
    """Full (game x config) matrix plus a seeded random baseline.

    max_actions=None means every game runs at its OWN budget (the regime it
    was designed for), so the agent and the random baseline are compared at
    equal, per-game budget — corridor at 30, everything else at 80.
    """
    games = games if games is not None else game_family()
    configs = configs if configs is not None else CONFIGS
    rows = []
    for game in games:
        for name, kwargs in configs.items():
            rows.append(_aggregate(game, name, max_actions, kwargs))
        for seed in random_seeds:
            rows.append(run_random(game, max_actions=max_actions, seed=seed))
    return rows


def format_rows(rows):
    head = ("| game | config | win | steps | levels | no-ops | repeats "
            "| confirmed | refuted | exploits |")
    sep = "|---|---|---|---|---|---|---|---|---|---|"
    lines = [head, sep]
    for r in rows:
        if "noop_actions" in r:
            lines.append("| %s | %s | %s | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f | %.1f |" % (
                r["game"], r["config"], "yes" if r["win"] else "NO",
                r["steps"], r["levels"], r["noop_actions"], r["repeat_pairs"],
                r["confirmed"], r["refuted"], r["exploit_actions"]))
        else:
            lines.append("| %s | %s | %s | %d | %d | - | - | - | - | - |" % (
                r["game"], r["config"], "yes" if r["win"] else "NO",
                r["steps"], r["levels"]))
    return "\n".join(lines)


def summary(rows):
    """Per-gate verdict: does removing the gate hurt, and where?"""
    by_game = {}
    for r in rows:
        by_game.setdefault(r["game"], {})[r["config"]] = r
    lines = []
    for game, cfgs in by_game.items():
        full = cfgs.get("full")
        if not full:
            continue
        for name in CONFIGS:
            if name == "full" or name not in cfgs:
                continue
            ab = cfgs[name]
            notes = []
            if ab["win"] != full["win"]:
                notes.append("win %s->%s" % ("yes" if full["win"] else "no",
                                             "yes" if ab["win"] else "no"))
            if abs(ab["steps"] - full["steps"]) > 0.05:
                notes.append("steps %.1f->%.1f" % (full["steps"], ab["steps"]))
            if abs(ab.get("noop_actions", 0) - full.get("noop_actions", 0)) > 0.05:
                notes.append("noops %.1f->%.1f" % (full["noop_actions"],
                                                   ab["noop_actions"]))
            if abs(ab.get("repeat_pairs", 0) - full.get("repeat_pairs", 0)) > 0.05:
                notes.append("repeats %.1f->%.1f" % (full["repeat_pairs"],
                                                     ab["repeat_pairs"]))
            if abs(ab.get("confirmed", 0) - full.get("confirmed", 0)) > 0.05:
                notes.append("confirmed %.1f->%.1f" % (full["confirmed"],
                                                       ab["confirmed"]))
            if notes:
                lines.append("- **%s / %s**: %s" % (game, name, "; ".join(notes)))
    return "\n".join(lines) or "- (no measured differences)"


def main(argv):
    rows = matrix()
    if "--json" in argv:
        print(json.dumps(rows, indent=1))
        return 0
    print("# arcpilot gate ablation (offline, deterministic)\n")
    print(format_rows(rows))
    print("\n## Gate contributions (full -> ablated)\n")
    print(summary(rows))
    print("\n## Confirmation-threshold calibration (coin-flip action, p=0.5)\n")
    print("| threshold | P(confirm) | P(confirm \\| proposed) | analytic p^(2+t) |")
    print("|---|---|---|---|")
    cal = confirmation_calibration()
    for t in (1, 2):
        c = cal[t]
        print("| n=%d | %.4f | %.4f | %.4f |" % (
            t, c["p_confirm"], c["p_confirm_given_proposed"], c["analytic"]))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
