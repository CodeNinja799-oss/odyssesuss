"""Day 4 demo - the same task, interrupted and resumed.

Concept: there is no special "resume mode" in the harness - resume() just
loads whatever the session log already has, repaired for any call the
process died mid-execute, and run() continues appending to the same file.
Kill this script partway through, then run it again with --resume: the
transcript it continues from is exactly what was on disk.

Run:
  python demos/day4_resume.py             # start the task
  <kill the process partway through>
  python demos/day4_resume.py --resume    # pick up where it left off
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import Harness

TASK = "Create part1.txt through part5.txt one at a time, then SUMMARY.md describing each"
WORKDIR = "scratch/day4_resume"


def on_event(kind, payload):
    if kind == "assistant":
        calls = [c["name"] for c in payload["tool_calls"]]
        text = f" text={payload['text'][:80]!r}" if payload["text"] else ""
        print(f"[assistant] tool_calls={calls}{text}", flush=True)
    elif kind == "tool_end":
        print(f"[tool result] {payload['call']['name']} -> {str(payload['result'])[:80]}", flush=True)


def main():
    os.makedirs(WORKDIR, exist_ok=True)
    harness = Harness(workdir=WORKDIR, on_event=on_event)
    if "--resume" in sys.argv:
        found = harness.resume()
        print(f"[resume] loaded previous session: {found}", flush=True)
        # Surface any call the process died before answering - the point of
        # the whole exercise is that this is visible, not inferred.
        for message in harness.messages:
            if message.get("role") == "tool" and "Interrupted before this ran" in message.get("text", ""):
                print(f"[repaired] {message['name']}: {message['text']}", flush=True)
        answer = harness.run("continue the task")
    else:
        answer = harness.run(TASK)
    print(f"\n[final] {answer}")


if __name__ == "__main__":
    main()
