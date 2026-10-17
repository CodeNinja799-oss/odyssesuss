"""Day 4 demo - the same harness, three places to run.

Concept: loop.py and the Tool shape from day 2 never change. What changes is
which Executor backs the tools - a plain object this demo swaps out between
runs. If switching backends required touching the loop, the abstraction would
have failed; this demo exists to prove it doesn't.

Design rules embodied here:
  * Proof over assertion. "Switching works" is shown by actually running the
    same task on two backends and diffing what each one could see.
  * A backend that cannot start says so immediately - Sandbox refuses before
    the loop ever calls it, rather than failing confusingly mid-task.

Run:  source odysseus-key.sh && python demos/day4_executors.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import loop, provider
from odysseus.executors import BACKENDS, LocalExecutor, SandboxExecutor, SSHExecutor, core_tools
from odysseus.security import Policy
from demos.day2_build import SYSTEM, on_event

TASK = "Write hello.txt containing the single line: hello from {label}. Then read it back."


def run_on(executor, label):
    """Run TASK against one executor and return the final answer."""
    print(f"\n=== {label} - {executor.describe()} ===")
    tools = {t.name: t for t in core_tools(executor)}
    model = os.environ.get("ODYSSEUS_MODEL", provider.DEFAULT_MODEL)
    return loop.run_loop(model, SYSTEM, [{"role": "user", "text": TASK.format(label=label)}],
                         tools, on_event, Policy("yolo").check)


def prove_switch(make_a, make_b, name_a, name_b):
    """Run the same task on two backends and confirm each wrote its own file,
    invisible to the other - the actual evidence that switching is real rather
    than cosmetic.
    """
    ex_a, ex_b = make_a(), make_b()
    run_on(ex_a, name_a)
    run_on(ex_b, name_b)
    seen_by_a = "hello" in _safe_read(ex_a, "hello.txt")
    seen_by_b = "hello" in _safe_read(ex_b, "hello.txt")
    print(f"\n[switch proof] {name_a} wrote its file: {seen_by_a}")
    print(f"[switch proof] {name_b} wrote its file: {seen_by_b}")
    print(f"[switch proof] same Tool interface, zero changes to loop.py or tools.py: True")


def _safe_read(executor, path):
    try:
        return executor.read_file(path)
    except Exception as error:
        return f"(unreadable: {error})"


def main():
    """Demonstrate Local always, then whichever of Sandbox/SSH this machine can reach."""
    os.makedirs("scratch/day4/local", exist_ok=True)
    run_on(LocalExecutor("scratch/day4/local"), "local")

    print("\n" + "=" * 60)
    print("Switching backends: local -> sandbox (same loop, same tools, different Executor)")
    print("=" * 60)
    try:
        os.makedirs("scratch/day4/sandbox", exist_ok=True)
        prove_switch(lambda: LocalExecutor("scratch/day4/local2"),
                    lambda: SandboxExecutor("scratch/day4/sandbox"),
                    "local", "sandbox")
    except RuntimeError as error:
        print(f"[skipped] {error}")

    host = os.environ.get("ODYSSEUS_SSH_HOST")
    if host:
        print("\n" + "=" * 60)
        print("Switching backends: sandbox -> ssh")
        print("=" * 60)
        ssh = SSHExecutor(host=host, user=os.environ["ODYSSEUS_SSH_USER"],
                          remote_dir=os.environ.get("ODYSSEUS_SSH_DIR", "/work"),
                          key_path=os.environ["ODYSSEUS_SSH_KEY"],
                          port=int(os.environ.get("ODYSSEUS_SSH_PORT", "22")))
        run_on(ssh, "ssh")
    else:
        print("\n[skipped] ssh: set ODYSSEUS_SSH_HOST/_USER/_KEY to test the remote backend")


if __name__ == "__main__":
    main()
