"""A path-jailed working copy of the shared repository for one agent.

Every filesystem and git operation is confined to ``root``; attempts to escape
via ``..`` or absolute paths raise :class:`WorkspaceError`. This is the
least-privilege boundary from PRD §33 — an agent can only touch its worktree.
"""

from __future__ import annotations

import functools
import os
import shlex
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path


class WorkspaceError(RuntimeError):
    pass


@dataclass
class CommandResult:
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_s: float
    timed_out: bool = False

    @property
    def ok(self) -> bool:
        return self.exit_code == 0 and not self.timed_out

    def render(self, limit: int = 6000) -> str:
        body = (
            f"$ {self.command}\n"
            f"exit={self.exit_code} duration={self.duration_s:.1f}s"
            f"{' TIMED_OUT' if self.timed_out else ''}\n"
        )
        out = (self.stdout or "").strip()
        err = (self.stderr or "").strip()
        if out:
            body += f"\n--- stdout ---\n{out[:limit]}\n"
        if err:
            body += f"\n--- stderr ---\n{err[:limit]}\n"
        return body


# Commands an agent is never allowed to run (defence in depth; the real
# isolation is the worktree + no credentials in env).
_SHELL_DENYLIST = (
    "rm -rf /",
    "sudo ",
    "shutdown",
    "reboot",
    "mkfs",
    ":(){",
    "curl ",
    "wget ",
    "nc ",
    "ssh ",
)


@functools.lru_cache(maxsize=1)
def _find_bash() -> str | None:
    """Locate a POSIX shell on Windows (git-bash ships with Git for Windows).

    ``subprocess.run(cmd, shell=True)`` launches ``cmd.exe`` on Windows, but
    check/test commands in this codebase — and ones an LLM writes — are POSIX
    shell (single quotes, ``&&``/``||`` with sh semantics, ``grep``, etc.).
    Those silently fail under cmd.exe even when the underlying claim they
    check is true. Route through bash when it's available; fall back to
    cmd.exe only if it genuinely isn't installed.
    """
    if os.name != "nt":
        return None
    found = shutil.which("bash")
    if found:
        return found
    for candidate in (
        r"C:\Program Files\Git\bin\bash.exe",
        r"C:\Program Files\Git\usr\bin\bash.exe",
        r"C:\Program Files (x86)\Git\bin\bash.exe",
    ):
        if Path(candidate).exists():
            return candidate
    return None


def _kill_process_tree(proc: subprocess.Popen) -> None:
    """Kill ``proc`` and every process it spawned.

    ``Popen.kill()`` alone only terminates the immediate process — on Windows
    especially, a shelled-out script that starts a server or reloader (e.g. a
    Flask dev server) leaves orphaned grandchildren running (and holding the
    stdout/stderr pipes open) even after the "timed out" process is killed,
    which then hangs the *next* ``communicate()`` call forever. Kill the whole
    tree instead.
    """
    try:
        if os.name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(proc.pid), "/T", "/F"],
                capture_output=True, timeout=10,
            )
        else:
            import signal

            try:
                os.killpg(os.getpgid(proc.pid), signal.SIGKILL)
            except (ProcessLookupError, PermissionError, OSError):
                proc.kill()
    except Exception:  # noqa: BLE001 - best-effort; never let cleanup raise
        try:
            proc.kill()
        except Exception:  # noqa: BLE001
            pass


class Workspace:
    def __init__(
        self,
        root: str | Path,
        *,
        allow_network: bool = False,
        default_timeout: int = 300,
    ):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.allow_network = allow_network
        self.default_timeout = default_timeout

    # --- path handling ---------------------------------------------
    def resolve(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if p != self.root and self.root not in p.parents:
            raise WorkspaceError(f"path escapes workspace: {rel!r}")
        return p

    def _rel(self, p: Path) -> str:
        return str(p.relative_to(self.root)).replace(os.sep, "/")

    # --- filesystem ---------------------------------------------
    def read_file(self, rel: str, max_bytes: int = 200_000) -> str:
        p = self.resolve(rel)
        if not p.is_file():
            raise WorkspaceError(f"not a file: {rel}")
        data = p.read_bytes()[:max_bytes]
        return data.decode("utf-8", errors="replace")

    def write_file(self, rel: str, content: str) -> str:
        p = self.resolve(rel)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return self._rel(p)

    def list_dir(self, rel: str = ".") -> list[str]:
        p = self.resolve(rel)
        if not p.is_dir():
            raise WorkspaceError(f"not a directory: {rel}")
        out = []
        for child in sorted(p.iterdir()):
            name = self._rel(child)
            out.append(name + "/" if child.is_dir() else name)
        return out

    def tree(self, max_entries: int = 400) -> list[str]:
        entries: list[str] = []
        for dirpath, dirnames, filenames in os.walk(self.root):
            dirnames[:] = [
                d for d in sorted(dirnames)
                if d not in {".git", "__pycache__", ".venv", "node_modules", ".aamt"}
            ]
            for fn in sorted(filenames):
                entries.append(self._rel(Path(dirpath) / fn))
                if len(entries) >= max_entries:
                    return entries
        return entries

    def search(self, pattern: str, *, glob: str = "**/*", max_hits: int = 100) -> list[str]:
        import re

        rx = re.compile(pattern)
        hits: list[str] = []
        for p in self.root.glob(glob):
            if not p.is_file() or ".git" in p.parts:
                continue
            try:
                text = p.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            for i, line in enumerate(text.splitlines(), 1):
                if rx.search(line):
                    hits.append(f"{self._rel(p)}:{i}: {line.strip()[:200]}")
                    if len(hits) >= max_hits:
                        return hits
        return hits

    # --- shell -------------------------------------------------
    def _exec(
        self,
        argv_or_cmd: str | list[str],
        *,
        shell: bool,
        env: dict[str, str],
        timeout: float,
        display: str,
    ) -> CommandResult:
        """Run a command, guaranteeing we never block past ``timeout`` twice.

        Uses ``Popen`` directly (not ``subprocess.run``) because on a
        timeout, the stdlib helper kills only the immediate process and then
        retries an *unbounded* ``communicate()`` to drain output — which
        hangs forever if a grandchild the command spawned (a dev server, a
        reloader) is still alive and holding the pipes open. We kill the
        whole process tree first, then drain with a short bounded retry.
        """
        import time

        start = time.time()
        try:
            proc = subprocess.Popen(
                argv_or_cmd,
                cwd=self.root,
                shell=shell,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                env=env,
                start_new_session=(os.name != "nt"),
            )
        except OSError as exc:
            return CommandResult(
                command=display, exit_code=127, stdout="", stderr=str(exc),
                duration_s=time.time() - start,
            )

        try:
            stdout, stderr = proc.communicate(timeout=timeout)
            return CommandResult(
                command=display,
                exit_code=proc.returncode,
                stdout=stdout,
                stderr=stderr,
                duration_s=time.time() - start,
            )
        except subprocess.TimeoutExpired:
            _kill_process_tree(proc)
            try:
                stdout, stderr = proc.communicate(timeout=10)
            except Exception:  # noqa: BLE001 - never block a second time
                stdout, stderr = "", ""
            return CommandResult(
                command=display,
                exit_code=124,
                stdout=stdout or "",
                stderr=(stderr or "") + f"\n[timed out after {timeout}s — process tree killed]",
                duration_s=time.time() - start,
                timed_out=True,
            )

    def run(self, command: str, *, timeout: int | None = None) -> CommandResult:
        lowered = command.lower()
        for bad in _SHELL_DENYLIST:
            if bad in lowered and not (bad in ("curl ", "wget ", "nc ", "ssh ") and self.allow_network):
                raise WorkspaceError(f"command blocked by policy: contains {bad!r}")

        env = dict(os.environ)
        # never expose provider keys / secrets to shelled-out processes
        for k in list(env):
            if any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
                env.pop(k, None)
        if not self.allow_network:
            env["NO_PROXY"] = "*"
            env["PIP_NO_INPUT"] = "1"

        # Scaffolded projects put code under src/ (see Orchestrator._seed_repo);
        # pytest picks that up via conftest.py, but a bare `python -c '...'`
        # acceptance-criteria check — the shape an LLM writes by default — has
        # no such hook and gets a bare ModuleNotFoundError. Mirror conftest.py.
        src_dir = self.root / "src"
        if src_dir.is_dir():
            existing = env.get("PYTHONPATH", "")
            env["PYTHONPATH"] = str(src_dir) + (os.pathsep + existing if existing else "")

        # Windows' shell=True launches cmd.exe; route through git-bash when
        # available so POSIX-style commands (single quotes, &&, grep, ...)
        # — what an LLM writes by default — actually run as intended.
        bash = _find_bash()
        argv_or_cmd: str | list[str] = [bash, "-lc", command] if bash else command

        return self._exec(
            argv_or_cmd,
            shell=(bash is None),
            env=env,
            timeout=timeout or self.default_timeout,
            display=command,
        )

    # --- argv runner (no shell — safe for paths with spaces/quotes) ----
    def run_argv(self, argv: list[str], *, timeout: int | None = None) -> CommandResult:
        env = dict(os.environ)
        for k in list(env):
            if any(s in k.upper() for s in ("API_KEY", "TOKEN", "SECRET", "PASSWORD")):
                env.pop(k, None)
        return self._exec(
            argv,
            shell=False,
            env=env,
            timeout=timeout or self.default_timeout,
            display=" ".join(argv),
        )

    # --- git --------------------------------------------------
    def git(self, args: str, *, timeout: int | None = None) -> CommandResult:
        return self.run_argv(["git", *shlex.split(args, posix=True)], timeout=timeout or 120)

    def ensure_git_repo(self) -> None:
        if not (self.root / ".git").exists():
            self.git("init -q")
            self.git('config user.email "agent@aamt.local"')
            self.git('config user.name "aamt-agent"')
        gitignore = self.root / ".gitignore"
        if not gitignore.exists():
            gitignore.write_text(
                "__pycache__/\n*.pyc\n.venv/\nvenv/\nnode_modules/\n"
                ".pytest_cache/\n.aamt/\n.env\n*.egg-info/\ndist/\nbuild/\n",
                encoding="utf-8",
            )

    def current_branch(self) -> str:
        res = self.git("rev-parse --abbrev-ref HEAD")
        return res.stdout.strip() or "HEAD"

    def create_branch(self, name: str) -> CommandResult:
        return self.run_argv(["git", "checkout", "-b", name])

    def status_porcelain(self) -> str:
        return self.git("status --porcelain").stdout

    def diff(self, *, staged: bool = False) -> str:
        return self.git(f"diff{' --staged' if staged else ''}").stdout

    def commit_all(self, message: str, *, trailer: str | None = None) -> CommandResult:
        self.run_argv(["git", "add", "-A"])
        full = message if not trailer else f"{message}\n\n{trailer}"
        # message via a file + argv (no shell) to avoid cross-platform quoting bugs
        msg_path = self.root / ".git" / "AAMT_COMMIT_MSG"
        msg_path.write_text(full, encoding="utf-8")
        try:
            return self.run_argv(["git", "commit", "-F", str(msg_path)])
        finally:
            msg_path.unlink(missing_ok=True)

    def last_commit_hash(self) -> str | None:
        res = self.git("rev-parse HEAD")
        return res.stdout.strip() if res.ok else None
