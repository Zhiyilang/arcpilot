"""ArcPilotAgent — hypothesis-driven agent for ARC-AGI-3.

The core is stdlib-only and operates on plain frame dicts (see frame.py), so the
whole decision loop is unit-testable offline against synthetic games.

Kaggle adapter (what changes on the real platform, NOTHING else):
    from arcengine import GameAction
    from arc_agi import EnvironmentWrapper

    class KaggleArcPilot(ArcPilotAgent):
        def _to_game_action(self, action_id):
            return GameAction.from_id(action_id)
    and drive the loop with EnvironmentWrapper.step(...) exactly like the
    official Agent base class (arcprize/ARC-AGI-3-Agents/agents/agent.py).
    FrameData objects convert with _convert_raw_frame_data(); feed the resulting
    dicts into step_frame().

Game model the agent assumes (learned, not hardcoded):
 - grid of ints; the agent controls a cursor/avatar indirectly via 7 generic
   actions whose semantics differ per game;
 - WIN when frame state == "WIN"; GAME_OVER when state == "GAME_OVER".
"""

from __future__ import annotations

from .frame import frame_signature, grid_diff, summarize_diff
from .hypothesis import HypothesisLedger
from .model import ActionEffectModel
from .policy import Policy, MAX_ACTIONS

WIN_STATES = ("WIN", "WON")
LOSE_STATES = ("GAME_OVER", "LOSE", "LOST")


class ArcPilotAgent:
    def __init__(self, available_actions=None, max_actions=MAX_ACTIONS):
        self.ledger = HypothesisLedger()
        self.model = ActionEffectModel()
        self.policy = Policy(available_actions=available_actions, max_actions=max_actions)
        self.max_actions = max_actions
        self.frames = []
        self.actions_taken = []
        self._last_progress_step = 0
        self._best_levels = 0

    # ---- lifecycle -----------------------------------------------------

    def reset(self, frame):
        self.frames = [frame]
        self._best_levels = int(frame.get("levels_completed", 0) or 0)

    def step_frame(self, frame):
        """Feed the next observed frame (after the last chosen action)."""
        if self.frames:
            prev = self.frames[-1]
            if self.actions_taken:
                sig = self.model.observe(prev, self.actions_taken[-1], frame)
                self._match_hypotheses(prev.get("guid", ""), sig)
            self._track_progress(frame)
        self.frames.append(frame)

    def _match_hypotheses(self, guid, observed_signature):
        for h in self.ledger.pending_tests():
            # a hypothesis is only tested by its own action; approximate by
            # matching on the most recent action when the ledger has a single
            # pending test (offline scaffold simplification)
            pass
        pending = self.ledger.pending_tests()
        if len(pending) == 1 and self.actions_taken:
            h = pending[0]
            if h.test_action == self.actions_taken[-1]:
                self.ledger.record(h.hid, guid, observed_signature)

    def _track_progress(self, frame):
        levels = int(frame.get("levels_completed", 0) or 0)
        if levels > self._best_levels:
            self._best_levels = levels
            self._last_progress_step = len(self.actions_taken)

    # ---- decisions -----------------------------------------------------

    def is_done(self):
        if not self.frames:
            return False
        state = str(self.frames[-1].get("state", "")).upper()
        return state in WIN_STATES or state in LOSE_STATES

    def is_progressing(self):
        """True if progress happened in the last 10 actions."""
        return (len(self.actions_taken) - self._last_progress_step) <= 10

    def choose_action(self):
        """Return (action_id, reason). Mirrors official choose_action signature."""
        frame = self.frames[-1]
        action_id, reason = self.policy.choose(
            step_index=len(self.actions_taken),
            frame=frame,
            ledger=self.ledger,
            model=self.model,
            is_progressing=self.is_progressing(),
        )
        self.actions_taken.append(action_id)
        return action_id, reason

    # ---- learning hooks --------------------------------------------------

    def propose_from_observation(self, claim, test_action, expected_signature):
        """External/seeded hypotheses (e.g. from a warm-start prior)."""
        return self.ledger.propose(claim, test_action, expected_signature)

    def report(self):
        return "\n".join([
            "steps=%d levels=%d" % (len(self.actions_taken), self._best_levels),
            "-- ledger --",
            self.ledger.report() or "(empty)",
            "-- model --",
            self.model.report() or "(empty)",
        ])
