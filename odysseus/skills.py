"""Day 3 - skills: changing behavior by adding a file, not editing code.

A skill is a SKILL.md with instructions in it. Nothing here executes code or
imports anything dynamic - the whole mechanism is "read a file, hand its text
to the model as an instruction." That is deliberate: the ceiling on what a
skill can do is the same as the ceiling on what a well-written prompt can do,
and no more.

Design rules embodied here:
  * Discovery is just a directory listing. Adding a skill means adding a
    folder; the harness never needs to know a skill exists in advance.
  * The catalog is cheap, the content is lazy. catalog() reads only enough of
    each file to describe it; the full text loads only once something asks
    for that skill by name, through read_skill.
  * A miss is still useful. read_skill's error names what *does* exist, so
    the model can recover without another round trip.
"""

import os

SKILLS_DIR = "skills"


def catalog(workdir: str) -> dict:
    """Return {name: {"description", "path"}} for every skill under workdir/skills/."""
    root = os.path.join(os.path.realpath(workdir), SKILLS_DIR)
    found = {}
    if os.path.isdir(root):
        for name in sorted(os.listdir(root)):
            path = os.path.join(root, name, "SKILL.md")
            if os.path.isfile(path):
                found[name] = {"description": _description(path), "path": path}
    return found


def _description(path: str) -> str:
    """Pull a "description:" line out of a SKILL.md's --- front matter, if any."""
    with open(path, encoding="utf-8") as handle:
        text = handle.read()
    if text.startswith("---"):
        end = text.find("\n---", 3)
        for line in text[3:end if end != -1 else 0].splitlines():
            if line.strip().lower().startswith("description:"):
                return line.split(":", 1)[1].strip()
    return "(no description)"


def catalog_prompt(workdir: str) -> str:
    """Render the catalog as a system-prompt section, or "" when there are no skills."""
    skills = catalog(workdir)
    if not skills:
        return ""
    lines = [f"- {name}: {info['description']}" for name, info in skills.items()]
    return "Skills available (load one with the use_skill tool when relevant):\n" + "\n".join(lines)


def read_skill(workdir: str, name: str) -> str:
    """Return a skill's full SKILL.md text, or a miss naming what is available."""
    skills = catalog(workdir)
    if name not in skills:
        available = ", ".join(skills) or "(none)"
        return f"ERROR: no skill named {name}. Available: {available}"
    with open(skills[name]["path"], encoding="utf-8") as handle:
        return handle.read()
