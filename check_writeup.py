"""ARC Prize 2026 Paper Track writeup gate.

Official constraints (Kaggle competition page, verified 2026-10-19):
  * "Your Writeup should not exceed 1,500 words. Submissions over this limit
    may be subject to penalty."
  * Required attachment set: Kaggle Writeup + Media Gallery (a cover image is
    required) + a public Notebook (or a public PDF via Project Link).
  * Judged equally on six criteria: Accuracy / Universality / Progress /
    Theory / Completeness / Novelty.
  * "What to Include" (arcprize.org): Abstract, Intro, Prior work, Approach,
    Results, Conclusion.

This gate enforces what can be checked locally, so a violation is impossible
to ship by accident:

  1. body word count <= 1500 (blockquote ">" lines are local editor notes and
     are NOT part of the submitted text)
  2. every official "What to Include" section present
  3. no unfilled placeholders ([RESULT], [SUBMISSION_ID], ...) at submit time

Usage:
    python check_writeup.py                 # gate (fails on any violation)
    python check_writeup.py --allow-draft   # placeholders tolerated (drafting)
"""

from __future__ import annotations

import argparse
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, "PAPER_DRAFT.md")
WORD_LIMIT = 1500

# Official "What to Include" headings -> regexes that accept our section names.
REQUIRED_SECTIONS = [
    ("Abstract", r"(?i)^\s*#+\s*.*\babstract\b"),
    ("Intro", r"(?i)^\s*#+\s*.*(intro|introduction)"),
    ("Prior work", r"(?i)^\s*#+\s*.*(prior work|related work|background)"),
    ("Approach", r"(?i)^\s*#+\s*.*(approach|method)"),
    ("Results", r"(?i)^\s*#+\s*.*\bresults?\b"),
    ("Conclusion", r"(?i)^\s*#+\s*.*(conclusion|summary)"),
]

PLACEHOLDER = re.compile(r"\[[A-Z_0-9]{3,}\]")


def body_text(md: str) -> str:
    """Submitted text = everything except local editor notes (blockquote lines)."""
    return "\n".join(l for l in md.splitlines() if not l.lstrip().startswith(">"))


def words(text: str) -> int:
    return len(re.findall(r"\b[\w'-]+\b", text))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--allow-draft", action="store_true",
                    help="tolerate unfilled [RESULT]-style placeholders")
    ap.add_argument("--file", default=TARGET)
    args = ap.parse_args()

    md = open(args.file, encoding="utf-8").read()
    body = body_text(md)
    n = words(body)
    full = words(md)

    problems = []
    if n > WORD_LIMIT:
        problems.append(f"body word count {n} > limit {WORD_LIMIT} (over by {n - WORD_LIMIT})")

    for name, rx in REQUIRED_SECTIONS:
        if not re.search(rx, body, re.M):
            problems.append(f"missing required section: {name}")

    ph = sorted(set(PLACEHOLDER.findall(body)))
    if ph and not args.allow_draft:
        problems.append("unfilled placeholders present: " + ", ".join(ph))

    print(f"file              : {os.path.relpath(args.file, HERE)}")
    print(f"full word count   : {full}  (includes local notes)")
    print(f"body word count   : {n} / {WORD_LIMIT}  "
          f"({WORD_LIMIT - n} words of headroom)")
    print(f"required sections : "
          f"{sum(1 for _, rx in REQUIRED_SECTIONS if re.search(rx, body, re.M))}"
          f"/{len(REQUIRED_SECTIONS)}")
    print(f"placeholders      : {ph if ph else 'none'}")

    if problems:
        print("\n--- FAIL ---")
        for p in problems:
            print("  " + p)
        return 1
    print("\nRESULT: OK — writeup is submittable (modulo cover image + public notebook)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
