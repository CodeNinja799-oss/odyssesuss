# Odysseus

The smallest agent harness that still does real work. Ten files, zero
dependencies, standard library only. Everything that makes an AI model able
to act instead of only talk - tool calling, a sandbox, durable memory, crash
recovery, sub-agents - fits in about a thousand lines you can read in an
afternoon, built up one day at a time so each file's reason for existing is
still visible in it.

This is the reference implementation: the build students keep for years, not
scratch code. Every file opens with a docstring naming what it teaches and the
design rules it embodies. Where behavior is subtle, a comment says why.

## Setup

Put a Gemini API key in `odysseus-key.sh` (get one at
https://aistudio.google.com/apikey), then load it into your shell:

```sh
source odysseus-key.sh
```

`ODYSSEUS_API_KEY` is read first; `GEMINI_API_KEY` is the fallback, for a key
already set up some other way. Never commit `odysseus-key.sh` - it's
gitignored for exactly that reason.

## Running it

Three forms, all the same underlying `Harness`:

```sh
# One task, headlessly - runs, prints the answer, exits 0.
python3 -m odysseus -d my-project -p "Add a /health endpoint and test it"

# Interactive - a prompt loop over the same Harness, Ctrl-D to exit.
python3 -m odysseus -d my-project

# Pick up exactly where a crashed or interrupted run left off.
python3 -m odysseus -d my-project --resume -p "continue"
```

`--mode` is `safe` by default when you're typing (asks before anything but a
read), `yolo` by default when you pass `-p` (headless has no one to ask), or
`read-only` to guarantee nothing changes. `-m/--model` overrides the model;
`--max-turns` caps how long one task can run before the harness insists on an
answer.

## Anatomy, day by day

| Day | Files | What it adds |
|---|---|---|
| 1 | `provider.py`, `loop.py` | Talk to Gemini; the whole agent loop - call the model, run what it asks for, call again |
| 2 | `tools.py`, `security.py` | Six sandboxed tools built from plain functions; a policy gate every call passes through |
| 3 | `context.py`, `memory.py`, `skills.py` | Compact a transcript that outgrows its budget; a project's durable memory; behavior you change by adding a file, not editing code |
| 4 | `session.py`, `subagent.py`, `harness.py` | A crash-safe session log; delegating a task to a fresh sub-agent; `Harness`, composing all of it into one object |
| 5 | `cli.py`, `fleet.py` | `python3 -m odysseus`; running many harnesses at once, each in its own directory |

`__init__.py` exports the five names you need from outside: `Harness`,
`Policy`, `Tool`, `tool`, `run_fleet`. Everything else is reached by its own
module name.

## Composing it

A `Harness` is just a constructor call. Give it a tool and it has a tool -
nothing in `loop.py`, `tools.py`, or the CLI needs to know this one exists:

```python
import random
from odysseus import Harness, tool

@tool("Roll count six-sided dice", count="How many dice")
def roll_dice(count):
    return [random.randint(1, 6) for _ in range(int(count))]

harness = Harness(workdir=".", extra_tools={"roll_dice": roll_dice})
print(harness.run("Roll 3 dice and tell me whether the total beats 10"))
```

That is day 1's demo tool, registered on the finished harness in four lines.
`extra_tools` is merged in last, so it can add a capability or override one
`core_tools` already provides - the same mechanism `remember`, `use_skill`,
and `spawn_agent` are built from internally.

## Demos

Each day's folder in `demos/` is a runnable proof of that day's claim, not
just an example - `day1_dice.py` through `day4_subagents.py` are what this
README's own claims were checked against before being written down.
