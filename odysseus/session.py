"""Day 4 - sessions: a transcript that survives the process dying.

Every message lands on disk, one JSON line at a time, the instant it lands in
memory - no separate "save" step, nothing to replay from a database. Resuming
a conversation means reading the same file a crash interrupted.

Design rules embodied here:
  * A write is not done until it is on disk. Every append flushes and fsyncs,
    because the entire point of this file is to survive a kill -9 landing the
    instant after a write() call returns.
  * A torn last line is expected, not an error. A process can die mid-write;
    load() treats a line it cannot parse as the crash point, not a bug.
  * Repair restores an invariant, not history. A tool call the process never
    got to run did not happen - repair says so, rather than pretending it did
    or silently dropping the call it can no longer account for.
"""

import glob
import json
import os
import re
import time

SESSION_DIR = ".odysseus/sessions"


def new_session(workdir: str, label: str = "session") -> str:
    """Build a fresh session path, named by the time and a slug of `label`."""
    root = os.path.join(os.path.realpath(workdir), SESSION_DIR)
    os.makedirs(root, exist_ok=True)
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", label).strip("-")[:40].lower() or "session"
    return os.path.join(root, f"{int(time.time())}-{slug}.jsonl")


def append(path: str, message: dict) -> None:
    """Write one message as a JSON line, flushed and fsynced before returning."""
    # A kill -9 only loses data never handed to the OS; flush()+fsync() close
    # that gap at the cost of a syscall per message - the price of the feature.
    with open(path, "a", encoding="utf-8") as handle:
        handle.write(json.dumps(message, ensure_ascii=False) + "\n")
        handle.flush()
        os.fsync(handle.fileno())


def load(path: str) -> list:
    """Read a session log, stopping at the first line a crash left torn."""
    messages = []
    with open(path, encoding="utf-8") as handle:
        for line in handle:
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                break
    return _repair(messages)


def latest(workdir: str):
    """Return the newest session file in `workdir`, or None if there is none."""
    root = os.path.join(os.path.realpath(workdir), SESSION_DIR)
    sessions = sorted(glob.glob(os.path.join(root, "*.jsonl")))
    return sessions[-1] if sessions else None


def _repair(messages: list) -> list:
    """Synthesize a result for any tool call the process died before running."""
    # Only the last assistant message can have this problem - everything
    # before it already has its matching results, or load() would have
    # stopped there. Counting the tool messages already present after it says
    # how many of its tool_calls were actually answered before the crash.
    last = next((i for i in range(len(messages) - 1, -1, -1)
                if messages[i]["role"] == "assistant"), None)
    if last is None:
        return messages
    calls = messages[last].get("tool_calls") or []
    answered = sum(1 for m in messages[last + 1:] if m["role"] == "tool")
    for call in calls[answered:]:
        messages.append({"role": "tool", "name": call["name"],
                         "text": "Interrupted before this ran (process restarted)."})
    return messages
