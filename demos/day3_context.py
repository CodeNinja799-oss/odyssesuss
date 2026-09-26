"""Day 3 demo - a task long enough to need compaction.

Concept: the loop is unchanged again. Day 1 left `before_turn` unused; today a
compactor is plugged into it, and a run that would outgrow its budget finishes
anyway. The model never learns this happened - it simply finds the distant past
replaced by a summary of itself.

Design rules embodied here:
  * The budget is a choice made at the call site, not a constant in the engine.
  * Compaction is observable. It rewrites the model's memory, so a run that
    compacts silently is a run you cannot debug.

Run:  source odysseus-key.sh && python demos/day3_context.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import context, loop, provider, tools
from odysseus.security import Policy
from demos.day2_build import SYSTEM, on_event

TASK = ("Create five files one.txt through five.txt, each with 20 lines of the word ping, "
        "one write_file at a time with a read back after each; then MANIFEST.md listing "
        "each file and its line count verified with wc -l")


def compactor(model, budget_tokens):
    """Return a before_turn hook that compacts and announces when it does."""
    def before_turn(messages):
        before = context.estimate_tokens(messages)
        kept = context.compact(model, messages, budget_tokens)
        # Identity, not equality: compact returns the same list when it declines.
        if kept is not messages:
            print(f"\n[compacted] {len(messages)} messages / ~{before} tokens"
                  f" -> {len(kept)} messages / ~{context.estimate_tokens(kept)} tokens\n")
        return kept
    return before_turn


def main():
    """Run the five-file task under a budget small enough to force compaction."""
    workdir, budget = "scratch/day3", 1500
    os.makedirs(workdir, exist_ok=True)
    model = os.environ.get("ODYSSEUS_MODEL", provider.DEFAULT_MODEL)
    print(f"[user] {TASK}\n[budget] {budget} tokens")
    answer = loop.run_loop(
        model=model,
        system=SYSTEM,
        messages=[{"role": "user", "text": TASK}],
        tools={t.name: t for t in tools.core_tools(workdir)},
        on_event=on_event,
        before_tool=Policy("yolo").check,
        before_turn=compactor(model, budget),
    )
    print(f"\n[final] {answer}")


if __name__ == "__main__":
    main()
