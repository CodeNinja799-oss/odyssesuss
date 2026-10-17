"""Day 4 - sub-agents: delegating a task to a fresh, blank context.

A sub-agent is not a different kind of agent - it is this same harness,
constructed again with an empty message list. spawn_agent is the one tool
that creates another Harness instead of touching a file or a shell.

Design rule embodied here:
  * Depth is enforced where the call happens, not where the harness is built.
    A model that nests delegation too deep gets a plain refusal it can read
    and recover from, not a stack overflow three levels down.
"""

from .tools import tool

DESCRIPTION = ("Delegate a self-contained task to a fresh sub-agent with its own "
              "clean context. The child cannot see this conversation - give it "
              "everything it needs in the task text. Returns the child's final report.")


def subagent_tool(make_harness, depth: int = 0, max_depth: int = 2):
    """Build the spawn_agent Tool; refuses once `depth` reaches `max_depth`."""

    @tool(DESCRIPTION, task="The self-contained task to hand the sub-agent")
    def spawn_agent(task):
        if depth >= max_depth:
            return "ERROR: sub-agent depth limit reached; do this task yourself"
        child = make_harness(depth + 1)
        return child.run(task)

    return spawn_agent
