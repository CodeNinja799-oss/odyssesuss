"""Day 2 - security: the gate every tool call passes through.

Day 1 left a socket called `before_tool` that always said yes. This file is
what gets plugged into it. It is deliberately the smallest file in the package:
a policy nobody can read is a policy nobody can trust.

Design rules embodied here:
  * Deny beats allow. A command matching a deny pattern is blocked in every
    mode, yolo included - the list exists for damage no answer is worth.
  * Blocking returns a reason, never an exception. The model reads the reason
    as a tool result and can choose a different approach.
  * The default is refusal. An approver that was never wired up says no, so
    forgetting to pass one fails closed rather than open.
"""

import re

# Tools that only observe. They never need approval because they change nothing.
READ_TOOLS = {"read_file", "list_files", "grep"}

# Shell commands that are never worth running, whatever the user approved.
DENY_PATTERNS = [
    r"rm\s+-[a-z]*r[a-z]*f?\s+(/|~|\$HOME)",   # rm -rf / or ~ or $HOME
    r"rm\s+-[a-z]*f[a-z]*r?\s+(/|~|\$HOME)",   # the same flags written backwards
    r"\bsudo\b",                                # privilege escalation
    r"\bmkfs\b",                                # reformat a filesystem
    r"\bdd\s+if=",                              # raw disk imaging
    r"curl[^|]*\|\s*(ba|z|)sh",                 # pipe the internet into a shell
    r"git\s+push\b[^\n]*--force",               # rewrite someone else's history
    r">\s*/dev/sd[a-z]",                        # write straight onto a disk
]


class Policy:
    """Decides whether a tool call may run.

    Modes:
        "read-only" - observation only; nothing may change.
        "safe"      - reads run free, everything else asks the approver.
        "yolo"      - anything but a deny pattern runs unasked.
    """

    def __init__(self, mode: str = "safe", approver=None):
        """Store the mode and the approver, defaulting the approver to refusal."""
        if mode not in ("read-only", "safe", "yolo"):
            raise ValueError(f"unknown mode {mode!r}")
        self.mode = mode
        # Fail closed: no approver means no approval.
        self.approver = approver or (lambda call, reason: False)

    def check(self, call: dict) -> str | None:
        """Return None to allow the call, or a reason string to block it.

        This is the exact shape `run_loop` expects for `before_tool`, so a
        Policy can be handed straight to the loop with no adapter.
        """
        if call["name"] == "bash":
            command = call["args"].get("command", "")
            for pattern in DENY_PATTERNS:
                if re.search(pattern, command):
                    return f"command matches a denied pattern: {pattern}"
        if call["name"] in READ_TOOLS or self.mode == "yolo":
            return None
        if self.mode == "read-only":
            return f"read-only mode: {call['name']} would change something"
        if self.approver(call, f"{call['name']} wants to run"):
            return None
        return "the user did not approve this call"
