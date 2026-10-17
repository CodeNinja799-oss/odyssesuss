"""Day 3 - memory: what the agent knows before it reads a single file.

A fresh conversation starts with no transcript, so anything the agent must
"remember" across runs has to live somewhere a transcript doesn't: on disk, in
the directory it works in. ODYSSEUS.md is that somewhere - a plain file the
agent writes to and the system prompt reads from, every single run.

Design rules embodied here:
  * Memory is a file, not a database. A project's memory should be as
    readable and editable by a human as anything else the agent touches.
  * The system prompt is rebuilt every run. Durability comes from re-reading
    ODYSSEUS.md each time, not from carrying state in the process.
  * Writing a memory never fails loudly. `remember` appends one line; it has
    nothing to validate and nothing worth raising an exception over.
"""

import os
import sys

MEMORY_FILE = "ODYSSEUS.md"

BASE_PROMPT = (
    "You are Odysseus, a small, sharp coding agent working inside one directory "
    "with the tools you have been given.\n\n"
    "Act, don't narrate. Inspect before assuming - read a file before changing "
    "it, list before guessing what's there. Prefer edit_file for small changes "
    "over rewriting a whole file with write_file. Verify after you build "
    "something, by running it or re-reading it, before claiming it works. "
    "Never repeat a failing call unchanged - if a tool call fails, change your "
    "approach, not just your luck. When the task is complete, reply with a "
    "short summary and stop calling tools."
)


def build_system_prompt(workdir: str, extra: str = "") -> str:
    """Assemble the system prompt: base rules, where we are, what we remember.

    Called fresh at the start of every conversation, so a fact written to
    ODYSSEUS.md in one run is simply *there* the next time this is called -
    memory needs no transport of its own, only a file and a re-read.
    """
    root = os.path.realpath(workdir)
    parts = [BASE_PROMPT, f"Platform: {sys.platform}. Working directory: {root}."]
    memory_path = os.path.join(root, MEMORY_FILE)
    if os.path.exists(memory_path):
        with open(memory_path, encoding="utf-8") as handle:
            parts.append(f"Project memory ({MEMORY_FILE}):\n{handle.read()}")
    if extra:
        parts.append(extra)
    return "\n\n".join(parts)


def remember(workdir: str, note: str) -> str:
    """Append `note` to ODYSSEUS.md as a bullet point, creating the file if needed."""
    path = os.path.join(os.path.realpath(workdir), MEMORY_FILE)
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(f"- {note}\n")
    return f"Remembered in {MEMORY_FILE}"
