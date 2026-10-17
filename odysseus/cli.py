"""Day 5 - cli.py: python3 -m odysseus, the front door to the whole week.

Every capability from days 1-4 already lives inside Harness; this file's
entire job is translating a command line into one and showing what it does
as it works. Two shapes, one object: -p runs a single task and exits; no
prompt starts a REPL that keeps driving the same Harness turn after turn.

Design rules embodied here:
  * The CLI owns the terminal; nothing else does. Harness never prints and
    never reads stdin - the printer and the approver are the only two places
    this file reaches into the harness's callbacks.
  * A crash here is not a crash there. Ctrl-C during a run stops this
    process; the session log it was writing is already durable, and saying
    so plainly beats pretending the interruption never happened.
"""

import argparse

from .harness import Harness
from .security import Policy

DIM, RESET = "\033[2m", "\033[0m"


def _clip(value, limit=80):
    """Flatten and truncate anything bound for the terminal to one line."""
    text = str(value).replace("\n", "\\n")
    return text if len(text) <= limit else text[:limit] + "..."


def _printer(kind, payload):
    """Print the conversation as it happens: text plain, calls and results compact."""
    if kind == "assistant":
        if payload["text"]:
            print(payload["text"])
        for call in payload["tool_calls"]:
            print(f"-> {call['name']}({_clip(call['args'])})")
    elif kind == "tool_end":
        result = payload["result"]
        first_line = str(result).splitlines()[0] if result else ""
        print(f"{DIM}   {_clip(first_line)}{RESET}")


def _approver(call, reason):
    """Show one tool call and ask the terminal for a yes before it runs."""
    print(f"   {call['name']}({_clip(call['args'])})")
    return input(f"approve {reason}? [y/N] ").strip().lower() == "y"


def main(argv=None) -> int:
    """Parse arguments and either run one headless task or start a REPL."""
    parser = argparse.ArgumentParser(prog="odysseus", description="A small, sharp coding agent.")
    parser.add_argument("-p", "--prompt", help="Run one task headlessly and exit")
    parser.add_argument("-d", "--workdir", default=".", help="Directory to work in")
    parser.add_argument("-m", "--model", help="Override the default model")
    parser.add_argument("--mode", choices=["safe", "yolo", "read-only"])
    parser.add_argument("--resume", action="store_true", help="Resume the latest session")
    parser.add_argument("--max-turns", type=int, default=120)
    args = parser.parse_args(argv)

    mode = args.mode or ("yolo" if args.prompt else "safe")
    policy = Policy(mode, approver=_approver)
    harness = Harness(workdir=args.workdir, model=args.model, policy=policy,
                      on_event=_printer, max_turns=args.max_turns)
    if args.resume:
        harness.resume()

    if args.prompt:
        print(harness.run(args.prompt))
        return 0

    print(f"Odysseus - model={harness.model} mode={mode} jail={harness.workdir}")
    while True:
        try:
            task = input("> ")
        except EOFError:
            print()
            return 0
        if not task.strip():
            continue
        try:
            print(harness.run(task))
        except KeyboardInterrupt:
            print("\nInterrupted - the session log is safe. Resume with --resume.")
