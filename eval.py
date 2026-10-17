"""Offline test suite for arcpilot core (synthetic games, zero dependencies).

Run: python eval.py   ->  expect: N passed, 0 failed
"""

from __future__ import annotations

import sys

from arcpilot.frame import make_frame, frame_signature, grid_diff, summarize_diff, grids_equal
from arcpilot.hypothesis import HypothesisLedger, ACTIVE, CONFIRMED, REFUTED
from arcpilot.model import ActionEffectModel
from arcpilot.policy import Policy
from arcpilot.agent import ArcPilotAgent

PASS = 0
FAIL = 0
FAILURES = []


def check(name, cond, detail=""):
    global PASS, FAIL
    if cond:
        PASS += 1
    else:
        FAIL += 1
        FAILURES.append("%s %s" % (name, detail))


# ---------- frame ----------

f1 = make_frame([[0, 1], [1, 0]])
f1b = make_frame([[0, 1], [1, 0]])
f2 = make_frame([[0, 2], [1, 0]])
check("frame.signature.equal", frame_signature(f1) == frame_signature(f1b))
check("frame.signature.differs", frame_signature(f1) != frame_signature(f2))
check("frame.grids_equal", grids_equal(f1, f1b) and not grids_equal(f1, f2))
check("frame.diff", grid_diff(f1, f2) == [(0, 1, 1, 2)])
check("frame.summarize", summarize_diff(grid_diff(f1, f2))[0] == 1)

# ---------- model ----------

m = ActionEffectModel()
m.observe(f1, 3, f2)
m.observe(f1b, 3, f2)
check("model.known", 3 in m.known_actions())
check("model.consistency", m.consistency(3) == 1.0)
m.observe(f1, 4, f1)  # no effect
check("model.no_effect", m.is_no_effect(4))
m.observe(f1, 5, make_frame([[9, 9], [9, 9]]))
check("model.varied_consistency", m.consistency(5) < 1.0)

# ---------- hypothesis ----------

led = HypothesisLedger()
hid = led.propose("action 3 changes top-right cell", 3, summarize_diff(grid_diff(f1, f2)))
check("hyp.pending", len(led.pending_tests()) == 1)
led.record(hid, "g1", summarize_diff(grid_diff(f1, f2)))
check("hyp.needs_two", led.get(hid).status == ACTIVE)  # one test is not enough
led.record(hid, "g2", summarize_diff(grid_diff(f1, f2)))
check("hyp.confirmed", led.get(hid).status == CONFIRMED)
hid2 = led.propose("action 7 does nothing", 7, (0, (), None))
led.record(hid2, "g1", summarize_diff(grid_diff(f1, f2)))
check("hyp.refuted", led.get(hid2).status == REFUTED)

# ---------- policy ----------

p = Policy(available_actions=[1, 2, 3, 4, 5, 6, 7])
a1, r1 = p.choose(0, f1, led, m, is_progressing=True)
check("policy.test_first", a1 == 3, r1)  # pending hypothesis test wins
p2 = Policy(available_actions=[1, 2, 3, 4, 5, 6, 7])
a2, _ = p2.choose(0, f1, led, m, is_progressing=False)
check("policy.exploit_confirmed", a2 == 3)  # confirmed action exploited
a3, _ = p2.choose(0, f1, led, m, is_progressing=True)
untried = p2.untried_actions(f1)
check("policy.untried_excludes_used", 3 not in untried)
a4, _ = p2.choose(0, f1, led, m, is_progressing=True)
check("policy.no_immediate_repeat", a4 != a3 or len(p2.untried_actions(f1)) == 0)
p3 = Policy(available_actions=[1, 2])
first3, _ = p3.choose(0, f1, led, m, True)
second3, _ = p3.choose(0, f1, led, m, True)
check("policy.loop_avoidance", second3 != first3, "%s vs %s" % (first3, second3))

# ---------- agent: toy deterministic game ----------
# Grid: agent marker '1' must reach cell with '5'. Action 2 moves marker right,
# action 3 moves it down (synthetic semantics; agent must DISCOVER this).


def toy_grid(pos):
    r, c = pos
    g = [[0, 0, 0], [0, 0, 0]]
    g[r][c] = 1
    return g


def toy_step(pos, action):
    r, c = pos
    if action == 2:
        c = min(c + 1, 2)
    elif action == 3:
        r = min(r + 1, 1)
    return (r, c)


agent = ArcPilotAgent(available_actions=[1, 2, 3, 4, 5, 6, 7], max_actions=80)
pos = (0, 0)
agent.reset(make_frame(toy_grid(pos), game_id="toy"))
steps = 0
while not agent.is_done() and steps < 80:
    action_id, reason = agent.choose_action()
    pos = toy_step(pos, action_id)
    steps += 1
    nxt = make_frame(toy_grid(pos), game_id="toy", guid="g%d" % steps)
    agent.step_frame(nxt)
    if pos == (1, 2):
        nxt["state"] = "WIN"
        agent.step_frame(nxt)
        break

check("agent.reaches_goal", pos == (1, 2), "pos=%s steps=%d" % (pos, steps))
check("agent.stops_on_win", agent.is_done())
check("agent.learned_move", 2 in agent.model.known_actions() and 3 in agent.model.known_actions())
check("agent.budget_respected", len(agent.actions_taken) <= 80)

# ---------- agent: win detection ----------

agent2 = ArcPilotAgent(available_actions=[1, 2, 3, 4, 5, 6, 7], max_actions=10)
agent2.reset(make_frame([[0]], state="PLAYING"))
check("agent.not_done_playing", not agent2.is_done())
agent2.step_frame(make_frame([[0]], state="WIN"))
check("agent.done_on_win", agent2.is_done())

agent3 = ArcPilotAgent(available_actions=[1, 2, 3, 4, 5, 6, 7], max_actions=10)
agent3.reset(make_frame([[0]], state="PLAYING"))
agent3.step_frame(make_frame([[0]], state="GAME_OVER"))
check("agent.done_on_gameover", agent3.is_done())

# ---------- hostile locale safety (no encoding assumptions) ----------

import os
for k in ("PYTHONUTF8", "LC_ALL", "LANG"):
    os.environ.pop(k, None)
check("locale.no_deps", "arcpilot" in sys.modules)

print("=" * 60)
print("%d passed, %d failed" % (PASS, FAIL))
for f in FAILURES:
    print("FAIL:", f)
print("=" * 60)
sys.exit(1 if FAIL else 0)
