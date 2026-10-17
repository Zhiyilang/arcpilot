"""Action-effect model: learn what each generic action does, empirically.

ARC-AGI-3 exposes 7 generic actions (ACTION1..ACTION7 + RESET) whose meaning is
game-specific and NOT documented to the agent. The agent must discover effects
by observing grid deltas. This module records, per action id, the diff signatures
observed so far, and exposes consistency scores used by the hypothesis ledger.
"""

from __future__ import annotations

from .frame import summarize_diff, grid_diff


class ActionEffectModel:
    """Empirical model of action -> grid diff signature.

    A signature is (n_changed, value-pairs, centroid). Actions whose observed
    signatures are tightly clustered are "understood"; actions with wildly
    different effects are "context-dependent" (still usable, lower confidence).
    """

    def __init__(self):
        # action_id -> list of signatures
        self._observations = {}
        self._no_effect = set()  # actions observed to change nothing

    def observe(self, prev_frame, action_id, next_frame):
        diff = grid_diff(prev_frame, next_frame)
        sig = summarize_diff(diff)
        self._observations.setdefault(action_id, []).append(sig)
        if not diff:
            self._no_effect.add(action_id)
        else:
            self._no_effect.discard(action_id)
        return sig

    def observations(self, action_id):
        return self._observations.get(action_id, [])

    def known_actions(self):
        return sorted(self._observations.keys())

    def is_no_effect(self, action_id):
        return action_id in self._no_effect

    def consistency(self, action_id):
        """1.0 = all observations share one signature; lower = more varied."""
        sigs = self._observations.get(action_id, [])
        if len(sigs) < 2:
            return 0.0
        first = sigs[0]
        same = sum(1 for s in sigs[1:] if s == first)
        return same / (len(sigs) - 1)

    def dominant_signature(self, action_id):
        sigs = self._observations.get(action_id, [])
        if not sigs:
            return None
        return max(set(sigs), key=sigs.count)

    def report(self):
        lines = []
        for aid in self.known_actions():
            sigs = self._observations[aid]
            lines.append(
                "action %s: n=%d consistency=%.2f dominant=%s%s" % (
                    aid, len(sigs), self.consistency(aid),
                    self.dominant_signature(aid),
                    " NO-EFFECT" if self.is_no_effect(aid) else "",
                )
            )
        return "\n".join(lines)
