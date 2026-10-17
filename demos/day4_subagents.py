"""Day 4 demo - delegating to sub-agents, verifying they stay off the books.

Concept: spawn_agent hands a task to a brand new Harness with its own clean
context - the parent never sees the child's intermediate steps, only its
final report. Every child is built with persist=False, so none of that work
creates its own session file: only the top-level conversation the user is
actually having gets one.

Run:  source odysseus-key.sh && python demos/day4_subagents.py
"""

import glob
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import Harness

TASK = ("Use spawn_agent twice: delegate writing utils.py with a slugify(text) "
        "function to one child, and test_utils.py with five asserts to another; "
        "then run python3 test_utils.py yourself and report.")
WORKDIR = "scratch/day4_subagents"


def on_event(kind, payload):
    if kind == "assistant" and payload["tool_calls"]:
        print(f"[assistant] calls: {[c['name'] for c in payload['tool_calls']]}")
    elif kind == "tool_end":
        name = payload["call"]["name"]
        print(f"[tool result] {name} -> {str(payload['result'])[:200]}")


def main():
    os.makedirs(WORKDIR, exist_ok=True)
    harness = Harness(workdir=WORKDIR, on_event=on_event)
    answer = harness.run(TASK)
    print(f"\n[final] {answer}")

    sessions = glob.glob(os.path.join(WORKDIR, ".odysseus", "sessions", "*.jsonl"))
    print(f"\n[check] session files on disk: {len(sessions)} (expect exactly 1)")
    for path in sessions:
        print(f"  {path}")


if __name__ == "__main__":
    main()
