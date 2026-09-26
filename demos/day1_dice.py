"""Day 1 demo - one hand-written tool, driven by the loop.

Concept: a tool is not a framework object. It is anything with a `.spec` the
provider can advertise and a `.run` the loop can call. Here that is fifteen
lines of plain Python, written by hand, so the shape is visible before day 2
generates it automatically.

Design rules embodied here:
  * The schema is the model's only documentation - if a field is not described
    there, the model cannot be expected to fill it.
  * Arguments arrive as strings. JSON schema is a request, not a guarantee, so
    the tool coerces rather than trusts.
  * The demo owns the policy and the printing; the loop owns neither.

Run:  source odysseus-key.sh && python demos/day1_dice.py
"""

import os
import random
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import loop, provider


class RollDice:
    """Roll a handful of six-sided dice."""

    spec = {"schema": {
        "name": "roll_dice",
        "description": "Roll count six-sided dice",
        "parameters": {
            "type": "object",
            "properties": {"count": {"type": "string", "description": "How many dice"}},
            "required": ["count"],
        },
    }}

    def run(self, count):
        """Return the individual rolls. `count` arrives as a string from JSON."""
        return [random.randint(1, 6) for _ in range(int(count))]


def on_event(kind, payload):
    """Print the transcript as it happens - the harness's only UI today."""
    if kind == "assistant":
        if payload["text"]:
            print(f"\n[assistant] {payload['text']}")
        for call in payload["tool_calls"]:
            print(f"[tool call] {call['name']}({call['args']})")
    elif kind == "tool_end":
        print(f"[tool result] {payload['result']}")


def before_tool(call):
    """Allow everything. Day 5 replaces this with a real policy gate."""
    return None


def main():
    """Ask the model to roll three dice and judge the total."""
    task = "Roll 3 dice and tell me whether the total beats 10"
    messages = [{"role": "user", "text": task}]
    print(f"[user] {task}")
    # ODYSSEUS_MODEL lets a key without preview-model quota still run the demo.
    model = os.environ.get("ODYSSEUS_MODEL", provider.DEFAULT_MODEL)
    answer = loop.run_loop(
        model=model,
        system="You are a dice assistant. Use the roll_dice tool; never invent rolls.",
        messages=messages,
        tools={"roll_dice": RollDice()},
        on_event=on_event,
        before_tool=before_tool,
    )
    print(f"\n[final] {answer}")


if __name__ == "__main__":
    main()
