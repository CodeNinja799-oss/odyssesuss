"""Day 4 - the operation layer: where a command actually runs.

Through day 3 every tool was hardcoded to the local filesystem and a local
subprocess. This file pulls that assumption out into an `Executor` - run a
command, read a file, write a file - and gives three implementations: your own
machine, a remote machine over SSH, and a disposable Docker container. The six
tools are rewritten once, generically, against that interface, so switching
backends is "pass a different Executor" and nothing else changes - not
tools.py's original local-only core_tools, not loop.py, not the policy gate.

Design rules embodied here:
  * One interface, three blast radii. Local can touch your whole account;
    Sandbox can touch nothing outside a container Docker destroys when the
    command ends. The interface does not hide that difference - it exposes it
    through `describe()` so a harness can show the user which one is live.
  * No feature the local backend doesn't need. run / read_file / write_file is
    the whole contract, because every other tool (list_files, grep, edit_file)
    can be built out of those three without backend-specific code.
  * A sandbox that silently degrades is worse than no sandbox. SandboxExecutor
    refuses loudly when Docker is unreachable rather than quietly falling back
    to an unsandboxed shell.
  * Stdlib only. SSH shells out to the system `ssh` binary; no paramiko.
"""

import os
import posixpath
import shlex
import subprocess

IGNORE = {".git", "node_modules", "__pycache__", ".venv"}
MAX_OUTPUT = 12000


class Executor:
    """What every backend must provide: run a command, read a file, write a file."""

    def run(self, command: str, timeout: float = 120) -> tuple:
        """Execute `command`; return (combined stdout+stderr, exit code)."""
        raise NotImplementedError

    def read_file(self, path: str) -> str:
        """Return the file's contents, or raise if `path` escapes the sandbox."""
        raise NotImplementedError

    def write_file(self, path: str, content: str) -> None:
        """Create or overwrite the file, or raise if `path` escapes the sandbox."""
        raise NotImplementedError

    def describe(self) -> str:
        """One-line label identifying this backend - printed so a switch is visible."""
        raise NotImplementedError


class LocalExecutor(Executor):
    """Runs on this machine, jailed to `workdir` by realpath - same rule as day 2."""

    def __init__(self, workdir: str):
        self.root = os.path.realpath(workdir)
        os.makedirs(self.root, exist_ok=True)

    def _resolve(self, path: str) -> str:
        full = os.path.realpath(os.path.join(self.root, path))
        if full != self.root and not full.startswith(self.root + os.sep):
            raise PermissionError(f"{path!r} escapes the working directory")
        return full

    def run(self, command: str, timeout: float = 120) -> tuple:
        try:
            done = subprocess.run(command, shell=True, cwd=self.root,
                                  capture_output=True, text=True, timeout=timeout)
        except subprocess.TimeoutExpired:
            return f"ERROR: timed out after {timeout}s", -1
        return (done.stdout + done.stderr), done.returncode

    def read_file(self, path: str) -> str:
        with open(self._resolve(path), encoding="utf-8", errors="replace") as handle:
            return handle.read()

    def write_file(self, path: str, content: str) -> None:
        full = self._resolve(path)
        os.makedirs(os.path.dirname(full) or self.root, exist_ok=True)
        with open(full, "w", encoding="utf-8") as handle:
            handle.write(content)

    def describe(self) -> str:
        return f"local:{self.root}"


class SSHExecutor(Executor):
    """Runs on a remote host via the system `ssh` binary - no SSH library, stdlib only.

    The jail is enforced on the remote side: every call resolves the path with
    the remote `realpath -m` before touching it, because a lexical check run
    locally cannot see a symlink that escapes on a machine we aren't on.
    """

    def __init__(self, host: str, user: str, remote_dir: str, key_path: str, port: int = 22):
        self.target = f"{user}@{host}"
        self.remote_dir = remote_dir
        self.ssh_opts = ["-i", key_path, "-p", str(port), "-o", "StrictHostKeyChecking=no",
                         "-o", "ConnectTimeout=10", "-o", "BatchMode=yes"]

    def _ssh(self, remote_command: str, timeout: float, input_text: str = None) -> tuple:
        result = subprocess.run(["ssh", *self.ssh_opts, self.target, remote_command],
                                input=input_text, capture_output=True, text=True, timeout=timeout)
        return (result.stdout + result.stderr), result.returncode

    def _jailed(self, path: str, timeout: float = 10) -> str:
        """Ask the remote host to resolve `path` and refuse if it lands outside remote_dir."""
        check = f"cd {shlex.quote(self.remote_dir)} && realpath -m {shlex.quote(path)}"
        resolved, code = self._ssh(check, timeout)
        resolved = resolved.strip()
        if code != 0 or not (resolved == self.remote_dir or resolved.startswith(self.remote_dir + "/")):
            raise PermissionError(f"{path!r} escapes the working directory")
        return resolved

    def run(self, command: str, timeout: float = 120) -> tuple:
        try:
            return self._ssh(f"cd {shlex.quote(self.remote_dir)} && {command}", timeout)
        except subprocess.TimeoutExpired:
            return f"ERROR: timed out after {timeout}s", -1

    def read_file(self, path: str) -> str:
        resolved = self._jailed(path)
        output, code = self._ssh(f"cat {shlex.quote(resolved)}", 30)
        if code != 0:
            raise FileNotFoundError(output.strip())
        return output

    def write_file(self, path: str, content: str) -> None:
        resolved = self._jailed(path)
        parent = posixpath.dirname(resolved)
        command = f"mkdir -p {shlex.quote(parent)} && cat > {shlex.quote(resolved)}"
        _, code = self._ssh(command, 30, input_text=content)
        if code != 0:
            raise OSError(f"remote write failed for {path!r}")

    def describe(self) -> str:
        return f"ssh:{self.target}:{self.remote_dir}"


class SandboxExecutor(Executor):
    """Runs each command in its own disposable Docker container: no network, no
    capabilities, bounded memory and processes, destroyed the moment it ends.

    File reads and writes bypass the container - the mounted directory is an
    ordinary local directory, so they reuse LocalExecutor's realpath jail
    rather than re-deriving it. Only `run` differs: it is the one operation
    with a real blast radius to contain.
    """

    def __init__(self, workdir: str, image: str = "odysseus-sandbox:latest"):
        if subprocess.run(["docker", "info"], capture_output=True).returncode != 0:
            raise RuntimeError("Docker is not reachable - sandbox cannot start. "
                               "Start Docker Desktop and try again.")
        self.image = image
        self._files = LocalExecutor(workdir)

    def run(self, command: str, timeout: float = 120) -> tuple:
        docker_cmd = ["docker", "run", "--rm", "--network", "none", "--cap-drop", "ALL",
                     "--pids-limit", "128", "--memory", "256m",
                     "-v", f"{self._files.root}:/workspace", "-w", "/workspace",
                     self.image, "sh", "-c", command]
        try:
            # +5s slack: give Docker itself room to tear the container down cleanly.
            done = subprocess.run(docker_cmd, capture_output=True, text=True, timeout=timeout + 5)
        except subprocess.TimeoutExpired:
            return f"ERROR: timed out after {timeout}s", -1
        return (done.stdout + done.stderr), done.returncode

    def read_file(self, path: str) -> str:
        return self._files.read_file(path)

    def write_file(self, path: str, content: str) -> None:
        self._files.write_file(path, content)

    def describe(self) -> str:
        return f"sandbox:{self.image}@{self._files.root}"


BACKENDS = {"local": LocalExecutor, "ssh": SSHExecutor, "sandbox": SandboxExecutor}


def core_tools(executor: Executor) -> list:
    """Build the same six tools as tools.py's core_tools, generic over any Executor.

    list_files and grep shell out to `find`/`grep` through executor.run() rather
    than walking Python-side, which is what makes them backend-agnostic: the
    same command runs whether "the shell" is local, remote, or containerized.
    """
    from .tools import tool  # reuse day 2's decorator; no new schema-building logic

    prune = " ".join(f"-path '*/{name}' -prune -o" for name in IGNORE)

    @tool("Read a file, returned with line numbers", path="Path to the file")
    def read_file(path):
        lines = executor.read_file(path).splitlines()
        return "\n".join(f"{n}\t{line}" for n, line in enumerate(lines, 1))

    @tool("Write a file, creating parent directories",
          path="Path to write", content="Full contents of the file")
    def write_file(path, content):
        executor.write_file(path, content)
        return f"Wrote {len(content)} chars to {path}"

    @tool("Replace an exact snippet in a file",
          path="File to edit", old="Snippet to replace", new="Replacement text")
    def edit_file(path, old, new):
        text = executor.read_file(path)
        found = text.count(old)
        if found == 0:
            return "ERROR: snippet not found - read the file and copy it exactly"
        if found > 1:
            return f"ERROR: snippet appears {found} times - include more context to make it unique"
        executor.write_file(path, text.replace(old, new, 1))
        return f"Edited {path}"

    @tool("Run a shell command in the working directory",
          command="The command line to run", timeout="Seconds before giving up")
    def bash(command, timeout="120"):
        output, code = executor.run(command, float(timeout))
        output = output.strip()
        if len(output) > MAX_OUTPUT:
            cut = len(output) - MAX_OUTPUT
            output = f"{output[:6000]}\n... [{cut} chars cut] ...\n{output[-6000:]}"
        return output or f"(exit {code}, no output)"

    @tool("List files in the working directory", pattern="Glob such as *.py")
    def list_files(pattern="*"):
        output, _ = executor.run(f"find . {prune} -type f -name {shlex.quote(pattern)} -print", 30)
        # find prints "./path"; drop the prefix so output matches tools.py's bare paths.
        paths = sorted(line[2:] for line in output.splitlines() if line)
        return "\n".join(paths) or "(no matches)"

    @tool("Search file contents with a regular expression",
          regex="Regular expression to find", pattern="Glob limiting which files")
    def grep(regex, pattern="*"):
        find = f"find . {prune} -type f -name {shlex.quote(pattern)} -print0"
        command = f"{find} | xargs -0 grep -nE {shlex.quote(regex)}"
        output, _ = executor.run(command, 30)
        # grep -n gives "./path:line:text"; match tools.py's "path:line: text" shape.
        lines = []
        for line in output.strip().splitlines():
            path, lineno, text = line.split(":", 2)
            lines.append(f"{path[2:]}:{lineno}: {text}")
        return "\n".join(lines) or "(no matches)"

    return [read_file, write_file, edit_file, bash, list_files, grep]
