"""Policy: hypothesis-driven action selection with loop avoidance and budgeting.

Decision priority each step:
 1. If a pending hypothesis has an untested discriminating action -> run it
    (cheapest knowledge first; RESET excluded).
 2. Else if a confirmed action exists and the game is not yet progressing ->
    re-apply the confirmed action (exploit).
 3. Else explore: prefer actions never tried from the current grid state;
    among those, prefer ones with high model consistency.
Hard rules (the "gate"):
 - never repeat (grid_signature, action) pair: a repeated state-action with no
   new information is a loop, and loops burn the 80-action budget for nothing.
 - reserve the final EXPLOIT_RESERVE actions: stop pure exploration so the tail
   of the budget is spent applying confirmed knowledge.
"""

from __future__ import annotations

from .frame import frame_signature

EXPLOIT_RESERVE = 12  # actions kept for exploitation at the tail
MAX_ACTIONS = 80


class Policy:
    def __init__(self, available_actions=None, max_actions=MAX_ACTIONS):
        self.available = list(available_actions) if available_actions else [1, 2, 3, 4, 5, 6, 7]
        self.max_actions = max_actions
        self._state_action_seen = set()
        self._action_tried_ever = set()

    def _mark(self, frame, action_id):
        self._state_action_seen.add((frame_signature(frame), action_id))

    def untried_actions(self, frame):
        sig = frame_signature(frame)
        return [a for a in self.available if (sig, a) not in self._state_action_seen]

    def choose(self, step_index, frame, ledger, model, is_progressing):
        """Return (action_id, reason)."""
        # Gate 0: budget reserve -> exploit only
        remaining = self.max_actions - step_index
        exploit_only = remaining <= EXPLOIT_RESERVE

        # 1. run pending discriminating tests
        if not exploit_only:
            for h in ledger.pending_tests():
                a = h.test_action
                if a in self.available:
                    self._mark(frame, a)
                    return a, "test %s (%s)" % (h.hid, h.claim)

        # 2. exploit confirmed knowledge when not progressing
        if is_progressing is False:
            confirmed = sorted(ledger.confirmed_actions())
            for a in confirmed:
                if a in self.available:
                    self._mark(frame, a)
                    return a, "exploit confirmed action"

        # 3. explore
        untried = self.untried_actions(frame)
        pool = untried if untried else [a for a in self.available if a not in self._action_tried_ever]
        if not pool:
            # everything tried from this state: re-try least-recently-used by model order
            pool = [a for a in self.available if not model.is_no_effect(a)] or list(self.available)
        # prefer high-consistency actions (deterministic effects are more informative)
        pool.sort(key=lambda a: (-model.consistency(a), a))
        a = pool[0]
        self._mark(frame, a)
        self._action_tried_ever.add(a)
        return a, "explore (untried=%d)" % len(untried)
