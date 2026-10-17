"""Day 4 - the Harness: the whole week, composed into one object.

Every earlier day added a capability as a loose function you had to wire up
by hand - a provider call, a tool factory, a policy, a compactor, a memory
file, a skill loader. Harness is where those stop being separate things to
remember: construct one with a working directory and call .run(task).
Everything from days 1-4 is already inside it.

Design rules embodied here:
  * Construction decides what exists; run() only runs. Tools, the system
    prompt, and the session path are all settled before the first model call,
    so a task in progress never discovers a capability it didn't start with.
  * A child is not the parent. A sub-agent gets its own Harness, its own
    blank message list, and persist=False - its work must never land in the
    parent's session file or become something --resume could pick up.
  * The session log is the source of truth, written as it happens. run()
    records every message the moment it lands, because the end of the task
    is exactly the moment a crash cannot be relied on to wait for.
"""

import os

from . import context, loop, memory, provider, session, skills
from .security import Policy
from .subagent import subagent_tool
from .tools import core_tools, tool


class Harness:
    """Composes provider, tools, memory, skills, security and sessions into
    one object: the whole harness, driven by a single `.run(task)` call.
    """

    def __init__(self, workdir=".", model=None, policy=None, extra_tools=None,
                system_extra="", on_event=None, budget_tokens=600_000,
                max_turns=120, session_path=None, enable_subagents=True,
                persist=True, _depth=0):
        self.workdir = os.path.realpath(workdir)
        os.makedirs(self.workdir, exist_ok=True)
        self.model = model or os.environ.get("ODYSSEUS_MODEL", provider.DEFAULT_MODEL)
        self.policy = policy or Policy("yolo")
        self.on_event = on_event or (lambda kind, payload: None)
        self.budget_tokens = budget_tokens
        self.max_turns = max_turns
        self.session_path = session_path
        self.enable_subagents = enable_subagents
        self.persist = persist
        self.messages = []
        self._written = {}  # id(message) -> message, for every message on disk

        self.tools = {t.name: t for t in core_tools(self.workdir)}

        @tool("Save a fact to project memory for future conversations",
              note="The fact to remember")
        def remember(note):
            return memory.remember(self.workdir, note)
        self.tools["remember"] = remember

        if skills.catalog(self.workdir):
            @tool("Load a skill's instructions by name", name="The skill's name")
            def use_skill(name):
                return skills.read_skill(self.workdir, name)
            self.tools["use_skill"] = use_skill

        if enable_subagents:
            # Same workdir and policy as this Harness, but persist=False: a
            # child's session log must never hijack --resume for the parent.
            def make_child(depth):
                return Harness(workdir=self.workdir, model=self.model, policy=self.policy,
                               on_event=self.on_event, budget_tokens=self.budget_tokens,
                               max_turns=self.max_turns, enable_subagents=enable_subagents,
                               persist=False, _depth=depth)
            self.tools["spawn_agent"] = subagent_tool(make_child, depth=_depth)

        if extra_tools:
            self.tools.update(extra_tools)

        extra = "\n\n".join(p for p in (skills.catalog_prompt(self.workdir), system_extra) if p)
        self.system = memory.build_system_prompt(self.workdir, extra)

    def resume(self, path: str = None) -> bool:
        """Load a session's messages - `path`, or the newest one found.

        False only means there was nothing to resume; a session that loads
        with zero messages still counts.
        """
        target = path or session.latest(self.workdir)
        if not target:
            return False
        self.messages = session.load(target)
        self.session_path = target
        # Every loaded message is already on disk - mark it so, by identity,
        # or run() would rewrite the whole history back into its own file.
        self._written = {id(m): m for m in self.messages}
        return True

    def run(self, task: str) -> str:
        """Run one task to completion and return the model's final text."""
        if self.persist and not self.session_path:
            self.session_path = session.new_session(self.workdir, label=task[:32])
        self.messages.append({"role": "user", "text": task})
        self._record_new()

        def before_turn(messages):
            return context.compact(self.model, messages, self.budget_tokens)

        def on_event(kind, payload):
            # Record first, forward second: the caller's printer should never
            # see a message appear in self.messages before it is durable.
            self._record_new()
            self.on_event(kind, payload)

        answer = loop.run_loop(self.model, self.system, self.messages, self.tools,
                               on_event, self.policy.check, self.max_turns, before_turn)
        self._record_new()
        return answer

    def _record_new(self):
        """Persist any message in self.messages not yet written to disk.

        Tracked by identity, not position. compact() can shrink the list
        between calls - it keeps the exact same objects for the tail it
        retains and prepends one new summary - so an index into "how many
        were recorded" stops meaning anything the moment the list is shorter
        than it was, while identity survives the shrink intact: the kept
        tail is still recognized as already-written, and only the summary
        (and whatever comes after it) is new.
        """
        if not (self.persist and self.session_path):
            return
        for message in self.messages:
            if id(message) not in self._written:
                session.append(self.session_path, message)
                self._written[id(message)] = message  # keeps it alive: id() is never reused
