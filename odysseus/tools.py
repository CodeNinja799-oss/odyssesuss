"""Day 2 - tools: the hands. What the model can actually reach.

Yesterday a tool was hand-written; today a decorator reads a plain function and
builds its schema, so a new capability costs one function, not one class.

Design rules embodied here:
  * Every parameter is a string - schema types are a hint the model may ignore,
    so tools coerce at the door instead of trusting the wire.
  * One gate for every path: `resolve` is the only way a path becomes real, so
    the sandbox cannot be enforced in five tools and forgotten in the sixth.
  * Output is bounded - a gigabyte of output destroys the context window.
  * Failure is a sentence, not an exception, wherever the model could fix it:
    a bad edit snippet is advice, not a traceback.
"""

import fnmatch
import inspect
import os
import re
import subprocess
from dataclasses import dataclass
from typing import Callable

IGNORE = {".git", "node_modules", "__pycache__", ".venv"}
MAX_LINES = 4000       # read_file: lines before truncation
MAX_OUTPUT = 12000     # bash: characters before the middle is cut
MAX_ENTRIES = 500      # list_files: paths listed
MAX_HITS = 200         # grep: matches reported


@dataclass
class Tool:
    """A capability the model can call: a name, a schema, and something to run."""
    name: str
    spec: dict
    run: Callable


def tool(description: str, **params: str) -> Callable:
    """Decorator turning a function into a Tool by reading its signature.

    Argument names become schema properties, `params` describes them, and an
    argument without a default is required - so a schema cannot drift from the
    code it advertises.
    """
    def decorate(fn: Callable) -> Tool:
        arguments = inspect.signature(fn).parameters
        return Tool(fn.__name__, {"schema": {
            "name": fn.__name__,
            "description": description,
            "parameters": {
                "type": "object",
                "properties": {name: {"type": "string", "description": params.get(name, name)}
                               for name in arguments},
                "required": [name for name, arg in arguments.items()
                             if arg.default is inspect.Parameter.empty],
            },
        }}, fn)
    return decorate


def core_tools(workdir: str) -> list:
    """Build the six file-and-shell tools, sandboxed to `workdir`.

    Each closes over its real path; none can reach a file outside it.
    """
    root = os.path.realpath(workdir)

    def resolve(path: str) -> str:
        """Turn a model-supplied path into a real one inside the sandbox."""
        # Checked after realpath, so "../.." and an outward symlink are one problem.
        full = os.path.realpath(os.path.join(root, path))
        if full != root and not full.startswith(root + os.sep):
            raise PermissionError(f"{path!r} escapes the working directory")
        return full

    def walk():
        """Yield every file under root, pruning noise directories as we go."""
        for folder, subfolders, files in os.walk(root):
            subfolders[:] = [d for d in subfolders if d not in IGNORE]
            for name in files:
                yield os.path.join(folder, name)

    def matches(relative: str, pattern: str) -> bool:
        """Match a glob against the relative path, or against the basename."""
        # fnmatch is not glob - `*` spans separators - so `**/*.py` alone would miss
        # top-level files; the basename is matched against the pattern's last segment.
        return (fnmatch.fnmatch(relative, pattern)
                or fnmatch.fnmatch(os.path.basename(relative), pattern.rsplit("/", 1)[-1]))

    @tool("Read a file, returned with line numbers", path="Path to the file")
    def read_file(path):
        """Return the file numbered "N<TAB>line", truncated if very long."""
        with open(resolve(path), encoding="utf-8", errors="replace") as handle:
            lines = handle.read().splitlines()
        body = "\n".join(f"{n}\t{line}" for n, line in enumerate(lines[:MAX_LINES], 1))
        if len(lines) > MAX_LINES:
            body += f"\n... truncated - {len(lines)} lines in total"
        return body

    @tool("Write a file, creating parent directories", path="Path to write",
          content="Full contents of the file")
    def write_file(path, content):
        """Overwrite the file at `path`, making its parent directories first."""
        full = resolve(path)
        os.makedirs(os.path.dirname(full) or root, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)
        return f"Wrote {len(content)} chars to {path}"

    @tool("Replace an exact snippet in a file",
          path="File to edit", old="Snippet to replace", new="Replacement text")
    def edit_file(path, old, new):
        """Replace `old` with `new`, but only when `old` occurs exactly once."""
        # Uniqueness is the whole safety property: an ambiguous match would silently
        # change the wrong line, so the tool refuses and says how to fix it.
        full = resolve(path)
        with open(full, encoding="utf-8") as handle:
            text = handle.read()
        found = text.count(old)
        if found == 0:
            return "ERROR: snippet not found - read the file and copy it exactly"
        if found > 1:
            return f"ERROR: snippet appears {found} times - include more context to make it unique"
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(text.replace(old, new, 1))
        return f"Edited {path}"

    @tool("Run a shell command in the working directory",
          command="The command line to run", timeout="Seconds before giving up")
    def bash(command, timeout="120"):
        """Run `command` and return its combined output, bounded and timed."""
        try:
            done = subprocess.run(command, shell=True, cwd=root, capture_output=True,
                                  text=True, timeout=float(timeout))
        except subprocess.TimeoutExpired:
            return f"ERROR: timed out after {timeout}s"
        output = (done.stdout + done.stderr).strip()
        if len(output) > MAX_OUTPUT:
            # Keep both ends: the command echo at the top, the error at the bottom.
            cut = len(output) - MAX_OUTPUT
            output = f"{output[:6000]}\n... [{cut} chars cut] ...\n{output[-6000:]}"
        return output or f"(exit {done.returncode}, no output)"

    @tool("List files in the working directory", pattern="Glob such as **/*.py")
    def list_files(pattern="**/*"):
        """Return matching paths, sorted, capped so a big tree cannot flood."""
        paths = (os.path.relpath(p, root).replace(os.sep, "/") for p in walk())
        hits = sorted(rel for rel in paths if matches(rel, pattern))
        body = "\n".join(hits[:MAX_ENTRIES])
        if len(hits) > MAX_ENTRIES:
            body += f"\n... and {len(hits) - MAX_ENTRIES} more"
        return body or "(no matches)"

    @tool("Search file contents with a regular expression",
          regex="Regular expression to find", pattern="Glob limiting which files")
    def grep(regex, pattern="*"):
        """Return "path:lineno: text" for each match, clipped and capped."""
        wanted = re.compile(regex)
        hits = []
        for path in walk():
            relative = os.path.relpath(path, root).replace(os.sep, "/")
            if not matches(relative, pattern):
                continue
            try:
                with open(path, encoding="utf-8", errors="replace") as handle:
                    lines = handle.read().splitlines()
            except OSError:
                continue  # unreadable file: skip it, never fail the whole search
            for number, line in enumerate(lines, 1):
                if wanted.search(line):
                    hits.append(f"{relative}:{number}: {line[:200]}")
                    if len(hits) >= MAX_HITS:
                        return "\n".join(hits)
        return "\n".join(hits) or "(no matches)"

    return [read_file, write_file, edit_file, bash, list_files, grep]
