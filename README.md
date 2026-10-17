# ArcPilot 🧭 — a hypothesis-driven agent scaffold for ARC Prize 2026 (ARC-AGI-3)

ArcPilot is the agent scaffold for the **ARC Prize 2026** Kaggle competitions
(ARC-AGI-3 + Paper Track). It encodes one engineering belief — *scaffolding
beats model upgrades* — into a concrete agent loop:

> **propose hypotheses about what each generic action does → run the cheapest
> discriminating test → confirm only on repeated consistent evidence → exploit
> confirmed knowledge → never repeat a state-action pair that taught nothing.**

That loop is exactly the "propose / decide / gate" discipline used across the
author's other open-source projects, applied to the one benchmark that rewards
*learning what to do when the problem changes*.

## Status

- `python eval.py` → **26/26 offline assertions pass** (zero dependencies,
  synthetic games; also green under `LC_ALL=C` without `PYTHONUTF8`).
- The core is **stdlib-only** and operates on plain frame dicts in the official
  `FrameData` JSON shape — no `arcengine` import required for development.
- Entry deadline **2026-10-26**, final submission **2026-11-02** (23:59 UTC).
  Paper Track writeup deadline **2026-11-09**.

## Layout

```
arcpilot/
  frame.py       # FrameData-shaped dicts, grid diff/signature utilities
  model.py       # ActionEffectModel: learns each action's empirical effect
  hypothesis.py  # HypothesisLedger: propose/test/confirm/refute with evidence
  policy.py      # Policy: test-first → exploit → explore, with loop & budget gates
  agent.py       # ArcPilotAgent: the full loop + Kaggle adapter notes
eval.py          # 26 offline assertions (synthetic games)
```

## The loop

```
reset(frame)
while not done and steps < MAX_ACTIONS (80):
    action, reason = choose_action()      # test-first / exploit / explore
    frame = environment.step(action)      # on Kaggle: arc_agi.EnvironmentWrapper
    step_frame(frame)                     # model.observe + hypothesis matching
```

Gates enforced by `policy.py`:

1. **Test-first** — an untested hypothesis's discriminating action runs before
   anything else (cheapest knowledge first).
2. **Exploit** — when progress stalls, re-apply confirmed actions.
3. **Loop avoidance** — a `(grid signature, action)` pair is never repeated:
   a repeat teaches nothing and burns the 80-action budget.
4. **Budget reserve** — the final 12 actions are exploitation-only.

## Kaggle adapter (the ONLY platform-specific code)

Official interface (`arcprize/ARC-AGI-3-Agents/agents/agent.py`):
agents subclass `Agent` and implement `choose_action(frames, latest_frame) -> GameAction`.
On Kaggle, wrap this core:

```python
from arcengine import GameAction

class KaggleArcPilot(ArcPilotAgent):
    def to_game_action(self, action_id):
        return GameAction.from_id(action_id)
```

then drive it with `EnvironmentWrapper.step(...)` and convert raw frames with
`_convert_raw_frame_data(...)` — everything else (model, ledger, policy) is
unchanged and already tested here.

Competition constraints honored: notebook-only submission, ≤9 h runtime,
internet disabled, pre-trained public models allowed, open-source release
required for prize eligibility (MIT).

## License

MIT
