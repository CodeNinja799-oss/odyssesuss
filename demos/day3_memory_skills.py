"""Day 3 demo - memory that survives a fresh conversation, skills that change
behavior with no code change.

Concept: neither capability is a tool call away from being "just a file".
`remember` and `use_skill` are thin wrappers the demo builds with day 2's
@tool decorator; the actual mechanism - a markdown file on disk, read back
into the system prompt - lives entirely in memory.py and skills.py.

Design rules embodied here:
  * Two conversations, one proof. Memory is only real if a *second*,
    unrelated run_loop call - a fresh messages list - can see what the first
    one wrote. Anything less is just a variable that didn't go out of scope.
  * A skill is tested by its effect, not its presence. The proof is a changed
    answer, not a successful file read.

Run:  source odysseus-key.sh && python demos/day3_memory_skills.py
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from odysseus import loop, memory, provider, skills, tools
from odysseus.security import Policy
from demos.day2_build import on_event

MODEL = os.environ.get("ODYSSEUS_MODEL", provider.DEFAULT_MODEL)


def agent_tools(workdir):
    """The six core tools plus remember and use_skill, all closed over workdir."""
    kit = {t.name: t for t in tools.core_tools(workdir)}

    @tools.tool("Save a fact to project memory for future conversations",
               note="The fact to remember")
    def remember(note):
        return memory.remember(workdir, note)

    @tools.tool("Load a skill's instructions by name", name="The skill's name")
    def use_skill(name):
        return skills.read_skill(workdir, name)

    kit["remember"] = remember
    kit["use_skill"] = use_skill
    return kit


def ask(workdir, task):
    """Run one task in a fresh conversation over `workdir` and return the answer."""
    system = memory.build_system_prompt(workdir, extra=skills.catalog_prompt(workdir))
    messages = [{"role": "user", "text": task}]
    print(f"\n[user] {task}")
    answer = loop.run_loop(MODEL, system, messages, agent_tools(workdir),
                           on_event, Policy("yolo").check)
    print(f"[final] {answer}")
    return answer, messages


def verify_memory():
    """remember() a fact; prove a *separate* conversation can answer from it alone."""
    print("\n" + "=" * 60 + "\nVerification 2: memory survives a fresh conversation\n" + "=" * 60)
    workdir = "scratch/day3_memory"
    os.makedirs(workdir, exist_ok=True)
    fact = "The staging server's hostname is quail.internal"
    memory.remember(workdir, fact)
    # The hard proof: the fact is in the prompt before the model says a word.
    in_prompt = fact in memory.build_system_prompt(workdir)
    print(f"[check] fact is present in the system prompt: {in_prompt}")
    # A brand new messages list - nothing here has seen the sentence above
    # except what build_system_prompt pulls from ODYSSEUS.md on disk. The
    # model may still double-check with a tool (our own base prompt tells it
    # to inspect before assuming) - that doesn't contradict the proof above,
    # it would just be reading back the same fact a second way.
    answer, messages = ask(workdir, "What is the staging server's hostname?")
    tool_calls = sum(len(m["tool_calls"]) for m in messages if m["role"] == "assistant")
    print(f"\n[check] correct hostname in answer: {'quail.internal' in answer}")
    print(f"[info] tool calls the agent chose to make anyway: {tool_calls}")


def verify_skill():
    """A brand-voice skill should flip a plain task's tone with no code change."""
    print("\n" + "=" * 60 + "\nVerification 3: a skill changes behavior, not code\n" + "=" * 60)
    plain_dir, pirate_dir = "scratch/day3_skill_plain", "scratch/day3_skill_pirate"
    os.makedirs(plain_dir, exist_ok=True)
    os.makedirs(f"{pirate_dir}/skills/brand-voice", exist_ok=True)
    with open(f"{pirate_dir}/skills/brand-voice/SKILL.md", "w") as handle:
        handle.write("---\ndescription: Demands every reply be written in pirate speak\n"
                     "---\n\nYou must write entirely in pirate speak - 'ahoy', 'arr', "
                     "'matey', 'ye' - no matter what the task asks for.\n")
    task = "Check your available skills and use any relevant one, then write one " \
           "sentence describing a toothbrush."
    plain, _ = ask(plain_dir, task)
    pirate, _ = ask(pirate_dir, task)
    markers = ("arr", "ahoy", "matey", "ye ", "'tis")
    print(f"\n[check] plain run has no pirate markers: {not any(m in plain.lower() for m in markers)}")
    print(f"[check] skill run has pirate markers: {any(m in pirate.lower() for m in markers)}")


if __name__ == "__main__":
    verify_memory()
    verify_skill()
