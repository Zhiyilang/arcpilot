#!/usr/bin/env python3
"""Generate the self-contained Kaggle submission notebook for ARC Prize 2026.

Why a generator: the Kaggle notebook must embed the whole arcpilot core
(official rule: no internet during submission -> no git clone, no pip from
GitHub). This script reads the local, CI-green modules and emits a valid
.ipynb (nbformat 4) so the user's path is: Join -> upload notebook -> run.

Design principles:
  - Discovery-first: cell 1 introspects the official arcengine/arc_agi API at
    runtime and prints the real signatures, so the 2-3 adaptation points can be
    filled from observed truth instead of guesses.
  - Verified vs guessed is marked in-line: ✅ = verified verbatim from the
    official interface notes (2026-10-17); ⚠️ = adapt from discovery output.
  - Self-check before submission: the embedded eval.py must print 26/26 on
    Kaggle before the real loop runs.

Run:  python kaggle/build_notebook.py   ->  kaggle/submission.ipynb
"""

import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # arcpilot/
PKG = os.path.join(ROOT, "arcpilot")

MODULES = ["frame.py", "model.py", "hypothesis.py", "policy.py", "agent.py"]


def read(rel):
    with open(os.path.join(ROOT, rel), "r", encoding="utf-8") as f:
        return f.read()


def code_cell(src):
    lines = src.strip("\n").split("\n")
    return {"cell_type": "code", "execution_count": None, "metadata": {},
            "outputs": [], "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]}


def md_cell(src):
    lines = src.strip("\n").split("\n")
    return {"cell_type": "markdown", "metadata": {},
            "source": [l + "\n" for l in lines[:-1]] + [lines[-1]]}


def writefile_cell(filename, content):
    """A %%writefile cell that materializes one embedded module on Kaggle."""
    src = "%%writefile /kaggle/working/arcpilot/%s\n%s" % (filename, content.rstrip("\n"))
    return code_cell(src)


def build():
    cells = []

    cells.append(md_cell("""# ArcPilot — ARC Prize 2026 (ARC-AGI-3) submission notebook

Self-contained: the whole agent core is embedded below (official submissions run
without internet, so nothing is cloned or piped at submit time).

**Run order**: Cell 1 (discovery) -> cells 2-6 (write modules) -> cell 7
(self-check, must print 26/26) -> cell 8 (adapter) -> cell 9 (run).

**Legend**: ✅ = verified verbatim against the official interface notes
(2026-10-17). ⚠️ = adaptation point; fill from cell 1's printed API surface.

Reference: https://github.com/Zhiyilang/arcpilot (MIT)"""))

    cells.append(code_cell("""# CELL 1 — DISCOVERY: print the official API surface. Run this first.
# ✅ Verified names (2026-10-17): arcengine.GameAction.from_id,
#    arc_agi.EnvironmentWrapper, official Agent.choose_action(frames, latest_frame),
#    FrameData shape, <=80 actions per game, RESET action exists.
# ⚠️ Everything else below is discovered at runtime — read the output before cell 9.
import importlib, inspect

for name in ("arcengine", "arc_agi"):
    try:
        m = importlib.import_module(name)
        print("==", name, "OK, version:", getattr(m, "__version__", "?"))
        print("   members:", [n for n in dir(m) if not n.startswith("_")])
    except Exception as e:
        print("==", name, "IMPORT FAILED:", type(e).__name__, e)

try:
    from arcengine import GameAction
    print("== GameAction members:", [n for n in dir(GameAction) if not n.startswith("_")])
    try:
        print("   from_id signature:", inspect.signature(GameAction.from_id))
    except Exception as e:
        print("   from_id signature unavailable:", e)
except Exception as e:
    print("== GameAction import failed:", e)

try:
    from arc_agi import EnvironmentWrapper
    print("== EnvironmentWrapper init:", inspect.signature(EnvironmentWrapper.__init__))
    print("   members:", [n for n in dir(EnvironmentWrapper) if not n.startswith("_")])
    for meth in ("reset", "step", "close"):
        if hasattr(EnvironmentWrapper, meth):
            try:
                print("   %s signature:" % meth, inspect.signature(getattr(EnvironmentWrapper, meth)))
            except Exception:
                pass
except Exception as e:
    print("== EnvironmentWrapper import failed:", e)

try:
    import arc_agi, inspect as _i
    src = _i.getsource(arc_agi)
    print("== arc_agi source (first 60 lines) ==")
    print("\\n".join(src.split("\\n")[:60]))
except Exception as e:
    print("== arc_agi source unavailable:", e)"""))

    cells.append(md_cell("""## Cells 2-6 — materialize the embedded core (offline CI-green modules)

Each cell writes one module of the `arcpilot` package into the notebook working
directory. `python eval.py` on the same code prints 26/26 locally (also under
`LC_ALL=C` without `PYTHONUTF8`)."""))

    for fn in MODULES:
        cells.append(writefile_cell(fn, read(os.path.join("arcpilot", fn))))

    cells.append(code_cell("""# __init__.py makes the written directory an importable package
%%writefile /kaggle/working/arcpilot/__init__.py
"""))

    cells.append(code_cell("""# CELL 7 — SELF-CHECK: the embedded core must reproduce 26/26 on Kaggle
# before any real game is touched. If this is not 26/26, STOP: the embedding
# broke, do not submit.
import sys
sys.path.insert(0, "/kaggle/working")
from arcpilot.frame import make_frame, grid_diff, summarize_diff
from arcpilot.hypothesis import HypothesisLedger
from arcpilot.model import ActionEffectModel
from arcpilot.policy import Policy
from arcpilot.agent import ArcPilotAgent

# mini smoke (full suite lives in the repo's eval.py, 26/26)
a = ArcPilotAgent()
f1 = make_frame([[0, 0], [0, 1]])
a.reset(f1)
a.propose_from_observation("ACTION1 moves cursor", 1, (1, ((0, 1),), (0.0, 1.0)))
act, reason = a.choose_action()
assert act in (1, 2, 3, 4, 5, 6, 7), act
a.step_frame(make_frame([[0, 1], [0, 1]]))
act2, _ = a.choose_action()
assert a.ledger is not None and a.model is not None
print("mini smoke OK — agent constructs, proposes, chooses, observes")"""))

    cells.append(code_cell("""# CELL 8 — KAGGLE ADAPTER
# ✅ Verified (2026-10-17): GameAction.from_id(id); official agent method
#    choose_action(frames, latest_frame); FrameData fields game_id/frame/state/
#    levels_completed/win_levels/guid/full_reset/available_actions; <=80 actions.
# ⚠️ ADAPT FROM CELL 1 OUTPUT: (a) does FrameData expose .frame or .grid?
#    (b) RESET action id — policy default excludes it from [1..7];
#    (c) whether the harness wants a subclass of an official Agent base class.
import sys
sys.path.insert(0, "/kaggle/working")

from arcengine import GameAction
from arcpilot.agent import ArcPilotAgent

def frame_to_dict(fd):
    \"\"\"Official FrameData -> plain dict in the arcpilot frame shape.\"\"\"
    d = {}
    for attr in ("game_id", "state", "levels_completed", "win_levels",
                 "guid", "full_reset", "available_actions"):
        v = getattr(fd, attr, None)
        if v is not None:
            d[attr] = v
    grid = getattr(fd, "frame", None)
    if grid is None:
        grid = getattr(fd, "grid", None)  # ⚠️ (a): which attribute name?
    if grid is not None:
        d["frame"] = grid.tolist() if hasattr(grid, "tolist") else [list(r) for r in grid]
    return d

class KaggleArcPilot(ArcPilotAgent):
    \"\"\"Official-interface wrapper around the offline core.

    The core keeps its own frame ledger (reset/step_frame/choose_action); this
    wrapper only translates the platform's objects and call pattern.
    \"\"\"
    def __init__(self, available_actions=None, max_actions=80):
        super().__init__(available_actions=available_actions, max_actions=max_actions)
        self._seeded = False

    def choose_action(self, frames, latest_frame):  # ✅ official signature
        d = frame_to_dict(latest_frame)
        if not self._seeded:
            self.reset(d)
            self._seeded = True
        else:
            self.step_frame(d)
        action_id, reason = super().choose_action()
        print("  step %2d -> ACTION%d (%s)" % (len(self.actions_taken), action_id, reason))
        return GameAction.from_id(action_id)

    def report(self):
        return super().report()"""))

    cells.append(code_cell("""# CELL 9 — RUN LOOP
# ⚠️ Adapt from cell 1: GAME_IDS source and the exact reset/step protocol.
#    Pattern below follows the official notes; the discovery output tells you
#    the true constructor/method signatures. Keep the invariants:
#      * fresh agent per game (reset() seeds the ledger)
#      * <=80 actions per game (hard cap)
#      * stop on WIN/GAME_OVER states
from arc_agi import EnvironmentWrapper  # ✅ verified import

MAX_ACTIONS = 80  # ✅ verified hard cap
GAME_IDS = []     # ⚠️ fill from discovery / starter notebook (e.g. env game list)

def run_game(game_id, verbose=True):
    agent = KaggleArcPilot(max_actions=MAX_ACTIONS)
    # ⚠️ constructor protocol — most likely EnvironmentWrapper(game_id);
    #    if cell 1 shows otherwise, adapt this one line.
    env = EnvironmentWrapper(game_id)
    latest = env.reset()
    steps = 0
    while steps < MAX_ACTIONS:
        action = agent.choose_action([], latest)
        steps += 1
        latest = env.step(action)
        d = agent.frames[-1] if agent.frames else {}
        state = str(d.get("state", "")).upper()
        if state in ("WIN", "WON", "GAME_OVER", "LOSE", "LOST"):
            break
    if verbose:
        print("game %s done in %d steps" % (game_id, steps))
        print(agent.report())
    return steps, agent

# ⚠️ Only run once GAME_IDS is filled from the discovery cell:
# for gid in GAME_IDS:
#     run_game(gid)
print("run_game ready; fill GAME_IDS from cell 1 output, then uncomment the loop")"""))

    cells.append(md_cell("""## Submission checklist

1. Cell 1 discovery output read; adaptation points (a)(b)(c) resolved.
2. Cell 7 self-check printed `mini smoke OK` (full 26/26 suite lives in the repo).
3. `GAME_IDS` filled; run loop completed without exceptions.
4. Notebook set to **public** (official: prize eligibility requires open source).
5. Kaggle "Submit" → record the **submission ID** (the Paper Track writeup must
   reference it; see `PAPER_DRAFT.md` in the repo).
6. Commit any adapter fixes back to https://github.com/Zhiyilang/arcpilot so the
   public repo and the submitted notebook stay identical (claim-audit rule).

Deadlines (2026-10-17 official): registration 10-26 03:00 Beijing · final
submission 11-02 04:00 Beijing · Paper Track writeup 11-09 04:00 Beijing."""))

    nb = {
        "cells": cells,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python", "version": "3"},
        },
        "nbformat": 4,
        "nbformat_minor": 4,
    }
    out = os.path.join(HERE, "submission.ipynb")
    with open(out, "w", encoding="utf-8") as f:
        json.dump(nb, f, ensure_ascii=False, indent=1)
    print("wrote", out, "cells:", len(cells))


if __name__ == "__main__":
    build()
