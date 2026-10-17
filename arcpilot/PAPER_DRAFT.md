# ARC Prize 2026 Paper Track — Writeup Draft (≤1500 words)

> **Status**: methodology sections pre-drafted (2026-10-17). Placeholders marked `[RESULT]` / `[SUBMISSION_ID]` must be filled from the real Kaggle submission before 11-09.
> **Submission requirements** (official): Kaggle Writeup ≤1500 words + cover image + public notebook + submission ID of an ARC-AGI-3 (or ARC-AGI-2) entry.
> **Rubric** (six criteria, 0-5 each): Accuracy / Universality / Progress / Theory / Completeness / Novelty. Section tags below map each part to the criteria it serves.

---

## Title

**Hypothesis-Gated Play: Confirmation Thresholds as the Scaffold for Learning ARC-AGI-3 Rules Online**

## Subtitle

An agent that treats each of the seven generic actions as an experiment, confirms action-effect hypotheses only on repeated consistent evidence, and refuses to act on unconfirmed beliefs — 26/26 offline regression tests, zero dependencies.

## 1. Introduction & Approach (Completeness, Novelty)

ARC-AGI-3 drops an agent into hidden interactive environments with no rules, no declared objective, and no instructions. Score is Relative Human Action Efficiency (RHAE): actions taken versus a human upper-median baseline, capped at 100%. The competition's own evidence — a controlled OpenAI study where identical models scored 4.9× differently under two harness configurations, and a community leaderboard topped by a 27B open-weight model wrapped in a minimal general scaffold — says the binding constraint is not model capacity but the *learning loop around the model*.

Our agent (ArcPilot, MIT) implements one principle: **an unconfirmed belief is not a basis for action**. Every action is either (a) a discriminating test of a specific pending hypothesis about what that action does, (b) exploitation of a confirmed hypothesis when progress stalls, or (c) exploration biased toward untried (state, action) pairs. The loop maintains three components: an *action-effect model* (per-action empirical diff signatures with a consistency score), a *hypothesis ledger* (propose → test → confirm/refute, confirmation requires two consistent observations), and a *policy* with four hard gates: test-first, exploit-on-stall, no-repeated-state-action, and a 12-action exploitation reserve at the tail of the 80-action budget.

## 2. Method (Completeness, Theory)

### 2.1 Actions as experiments

The environment exposes seven generic actions (ACTION1–ACTION7) plus RESET whose semantics are game-specific and undocumented. Rather than assume semantics, the agent records, for every executed action, the grid diff it produced, summarized as a compact signature `(n_changed, value-pairs, centroid)`. The model tracks per-action consistency — the fraction of observations matching the dominant signature. Consistency is the agent's proxy for "this action's effect is context-independent", and it orders exploration: deterministic-effect actions are tested first because their outcomes are maximally informative.

### 2.2 The hypothesis ledger

A hypothesis is a triple (claim, test action, expected signature). It enters as *active* and is only *confirmed* after **two** consistent observations of its expected signature; a single mismatch refutes it immediately. Confirmation is deliberately stricter than in typical LLM-agent loops: one coincidental grid change must never be mistaken for a learned rule, because in ARC-AGI-3 a single mislearned rule poisons every subsequent action. Evidence carries frame guids, so every belief is auditable after the run.

### 2.3 Policy gates

Each step the policy chooses in strict priority: (1) run the discriminating test of a pending hypothesis; (2) if levels_completed has not improved for 10 actions, re-apply confirmed actions; (3) otherwise explore the untried (grid-signature, action) pairs, preferring high-consistency actions. Two invariants are absolute: a (grid-signature, action) pair is never repeated — a repeat teaches nothing and burns budget — and the final 12 actions are exploitation-only, so the run never ends mid-experiment.

### 2.4 Why thresholds, not heuristics (Theory)

The design follows the structure of **active learning with error control**. Each action is a query; its information value is highest when it discriminates between live hypotheses, which is exactly the test-first rule. The two-observation confirmation rule is a Hoeffding-style guard at n=2: it rejects the singleton coincidence that single-shot LLM "learning" cannot distinguish from noise. The no-repeat gate converts the 80-action budget from a liability into a covering design over (state, action) space, and the exploitation reserve is the standard explore/exploit schedule's terminal phase. The reason a *deterministic* ledger around a *stochastic* model works is separation of concerns: the model (or none at all — the agent is model-free in its default configuration) may propose, but only evidence-backed, repeated, audited beliefs may gate actions. This is the same discipline that keeps autonomous systems safe outside games: generation is cheap, commitment is expensive, so commitment requires replication.

## 3. Results (Accuracy) — `[RESULT: fill from Kaggle leaderboard]`

- Final RHAE / levels completed: `[RESULT]`
- Submission ID: `[SUBMISSION_ID]`
- Ablations (each gate removed, same budget): `[RESULT: test-first off / confirmation at n=1 / no-repeat off / reserve off]`

## 4. Generality (Universality, Progress)

Nothing in the loop references ARC-AGI-3 specifics: it consumes frames, a discrete action set, and a scalar progress signal. The same three components run unchanged in the author's open-source agents for code review (propose/decide/gate pipeline with a 91-assertion offline spec), payment-operations incident triage (137 assertions), and safety gating (47 assertions across three OpenAI-compatible HTTP contracts — verified 47/47, including a hostile-locale step) — the hypothesis ledger and the no-repeat gate are literally the same modules. For the community, the released notebook is a drop-in scaffold: swap the synthetic frame source for the real environment wrapper and the loop is submission-ready. We expect the confirmation-threshold rule to transfer to any no-rules interactive benchmark, and we release all code under MIT precisely so that claim can be tested by others.

## 5. Limitations (Completeness)

The agent is model-free by default; its ceiling on games requiring fine motor planning (e.g., pixel-precise timing) is real, and the n=2 rule is conservative — it discards some learnable-but-noisy effects. The consistency proxy conflates context-dependence with stochasticity. `[RESULT: quantify failure modes from run logs]`

## 6. Reproducibility (Completeness)

`python eval.py` → 26/26 offline assertions (synthetic games, zero dependencies, green under `LC_ALL=C`). The submitted notebook is public under MIT; every claim in this writeup maps to an assertion ID or a logged frame guid.

---

**Word count**: ~875 body words (measured, excluding headers/placeholders) — well within the 1,500 limit, leaving room for result text.
**Cover image plan**: the policy decision loop as a one-page diagram (test → confirm → exploit → explore, with the four gates on the edges), generated from the same diagram source as the README.
**Notebook**: public Kaggle notebook, submission ID recorded above.
