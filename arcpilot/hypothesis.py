"""Hypothesis ledger: propose -> test -> confirm/refute, with evidence citations.

Mirrors the project's core discipline (prove-then-act): every belief about the
game carries the frame guids that support it, and no belief is acted on until
its discriminating test has passed.
"""

from __future__ import annotations

ACTIVE = "active"
CONFIRMED = "confirmed"
REFUTED = "refuted"


class Hypothesis:
    __slots__ = ("hid", "claim", "test_action", "expected_signature", "evidence",
                 "status", "tests_run")

    def __init__(self, hid, claim, test_action, expected_signature):
        self.hid = hid                # stable id
        self.claim = claim            # human-readable statement
        self.test_action = test_action  # action id that discriminates this hypothesis
        self.expected_signature = expected_signature  # diff signature expected if true
        self.evidence = []            # list of (guid, observed_signature)
        self.status = ACTIVE
        self.tests_run = 0

    def record_test(self, guid, observed_signature):
        self.tests_run += 1
        self.evidence.append((guid, observed_signature))
        if observed_signature == self.expected_signature:
            if self.tests_run >= 2:  # require two consistent observations
                self.status = CONFIRMED
        else:
            self.status = REFUTED

    def __repr__(self):
        return "H(%s %s tests=%d ev=%d)" % (self.hid, self.status, self.tests_run, len(self.evidence))


class HypothesisLedger:
    def __init__(self):
        self._items = {}
        self._seq = 0

    def propose(self, claim, test_action, expected_signature):
        self._seq += 1
        hid = "h%d" % self._seq
        self._items[hid] = Hypothesis(hid, claim, test_action, expected_signature)
        return hid

    def get(self, hid):
        return self._items[hid]

    def record(self, hid, guid, observed_signature):
        self._items[hid].record_test(guid, observed_signature)

    def by_status(self, status):
        return [h for h in self._items.values() if h.status == status]

    def pending_tests(self):
        """Active hypotheses that still need their discriminating test run."""
        return [h for h in self._items.values() if h.status == ACTIVE and h.tests_run == 0]

    def confirmed_actions(self):
        """Action ids backed by at least one confirmed hypothesis."""
        return {h.test_action for h in self.by_status(CONFIRMED)}

    def report(self):
        return "\n".join(repr(h) + " " + h.claim for h in self._items.values())
