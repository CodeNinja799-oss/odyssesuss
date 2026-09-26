"""Day 2 demo - the harness writes and runs code in a sandbox.

Concept: yesterday's loop is unchanged. Hand it real tools and a policy and the
same twenty lines stop rolling dice and start building software. That is the
whole argument for keeping the loop ignorant of what tools do.

Design rules embodied here:
  * The demo owns the workspace. Tools are built over a scratch directory, so
    a wrong path hits the sandbox wall instead of the repository.
  * The policy is visible at the call site. `Policy("yolo")` is a choice made
    here, in one line, not a default buried in the loop.
  * Events print; they do not decide. on_event is a window, never a veto.

Run:  source odysseus-key.sh && python demos/day2_build.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import loop, provider, tools
from odysseus.security import Policy

SYSTEM = """You are a coding agent working inside a sandboxed directory.
Use your tools to do the work rather than describing it. Verify what you build
by running it, and report what you actually observed."""


def on_event(kind, payload):
    """Print the conversation as it happens, tool calls and results included."""
    if kind == "assistant":
        if payload["text"]:
            print(f"\n[assistant] {payload['text']}")
        for call in payload["tool_calls"]:
            arguments = {k: _clip(str(v)) for k, v in call["args"].items()}
            print(f"[tool call] {call['name']}({arguments})")
    elif kind == "tool_end":
        print(f"[result] {_clip(str(payload['result']), 300)}")


def _clip(text, limit=120):
    """Keep the printed transcript readable when a tool argument is a whole file."""
    flat = text.replace("\n", "\\n")
    return flat if len(flat) <= limit else flat[:limit] + f"... (+{len(flat) - limit} chars)"


def run(task, workdir="scratch", mode="yolo"):
    """Run one task in `workdir` under `mode`, and return the final answer."""
    os.makedirs(workdir, exist_ok=True)
    kit = {t.name: t for t in tools.core_tools(workdir)}
    policy = Policy(mode)
    print(f"[user] {task}")
    return loop.run_loop(
        model=os.environ.get("ODYSSEUS_MODEL", provider.DEFAULT_MODEL),
        system=SYSTEM,
        messages=[{"role": "user", "text": task}],
        tools=kit,
        on_event=on_event,
        before_tool=policy.check,
    )


def main():
    """Build a small program, run it, and confirm its output."""
    task = ("Create fib.py with an iterative fib(n), a __main__ printing fib(30), "
            "run it and confirm the output is 832040")
    print(f"\n[final] {run(task)}")


if __name__ == "__main__":
    main()
