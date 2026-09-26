# Odysseus

A minimal agent harness in Python, built one day at a time. Standard library
only, no third-party packages, Python 3.10+.

The point of this repository is that the whole thing is readable. An agent is a
loop around a model call; a tool is an object with a schema and a method. Every
file names the day it belongs to and the concept it teaches.

## Setup

Put your Gemini API key in `odysseus-key.sh` (get one at
https://aistudio.google.com/apikey), then load it into your shell:

```sh
source odysseus-key.sh
```

`odysseus-key.sh` is gitignored. Never commit a key.

## Day 1 - the provider seam and the loop

```sh
python demos/day1_dice.py
```

- `odysseus/provider.py` - the only file that speaks Gemini's wire format.
  Neutral messages in, `{text, tool_calls, usage}` out.
- `odysseus/loop.py` - call the model, run the tools it asks for, call again.
- `demos/day1_dice.py` - one hand-written tool, start to finish.

To run against a different model (for example if your key has no quota for the
default preview model):

```sh
ODYSSEUS_MODEL=gemini-3-flash-preview python demos/day1_dice.py
```
