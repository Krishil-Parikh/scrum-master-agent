"""AGENT.OS — a Textual dashboard for the autonomous Agile team.

Recreates the reference terminal UI: a three-column phosphor-green console with
a live agent roster, project list, quick actions, an action menu, a scrolling
log, and system / resource / task panels.
"""

from __future__ import annotations

import time
from pathlib import Path

from textual import work
from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import Button, Input, Static

from . import banner
from .data import load_state, resource_sample, system_info
from .widgets import (
    AgentRows,
    Banner,
    KeyActions,
    KeyValue,
    LogView,
    Menu,
    Panel,
    SimpleList,
    Sparkline,
    TaskBars,
)

MENU_OPTIONS = [
    ("Build something", "Turn ideas into reality"),
    ("Work on a task", "Use your agents"),
]

QUICK_ACTIONS = [
    ("n", "New Task"), ("t", "Open Terminal"), ("c", "Copy Logs"), ("q", "Quit"),
]


class BuildPrompt(ModalScreen[tuple[str, str] | None]):
    """Collect a problem statement + repo for 'Build something' / 'Work on a task'."""

    BINDINGS = [
        Binding("escape", "cancel", "Cancel"),
        Binding("ctrl+s", "start", "Start"),
    ]

    CSS = """
    BuildPrompt { align: center middle; background: $background 60%; }
    #box {
        width: 86; height: auto; border: solid #1f6f3f; background: #0a0f0a; padding: 1 2;
    }
    #box Static { color: #33ff99; }
    #box .label { color: #6effb0; margin-top: 1; }
    #box #err { color: #ff6b6b; }
    #box Input {
        border: solid #1f6f3f; background: #061006; color: #baffd9;
    }
    #buttons { height: auto; margin-top: 1; align-horizontal: right; }
    #buttons Button { margin-left: 2; }
    """

    def __init__(self, title: str, *, default_repo: str) -> None:
        super().__init__()
        self._title = title
        self._default_repo = default_repo

    def compose(self) -> ComposeResult:
        with Vertical(id="box"):
            yield Static(f"> {self._title}", classes="label")
            yield Static("Problem statement (what should the team build?):", classes="label")
            yield Input(placeholder="Build a REST API for a task list with auth…", id="problem")
            yield Static("Repo — local path or git URL (blank = scratch dir):", classes="label")
            yield Input(placeholder=self._default_repo, id="repo")
            yield Static("", id="err")
            with Horizontal(id="buttons"):
                yield Button("Cancel", id="cancel")
                yield Button("▶ Start", id="start", variant="success")

    def on_mount(self) -> None:
        self.call_after_refresh(self.query_one("#problem", Input).focus)

    # Enter in the problem field jumps to repo; Enter in repo starts.
    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "problem":
            self.query_one("#repo", Input).focus()
        else:
            self.action_start()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "start":
            self.action_start()
        else:
            self.action_cancel()

    def action_start(self) -> None:
        problem = self.query_one("#problem", Input).value.strip()
        if not problem:
            self.query_one("#err", Static).update("Enter a problem statement first.")
            self.query_one("#problem", Input).focus()
            return
        repo = self.query_one("#repo", Input).value.strip() or self._default_repo
        self.dismiss((problem, repo))

    def action_cancel(self) -> None:
        self.dismiss(None)


class AgentOSApp(App):
    TITLE = "AGENT.OS"
    CSS = """
    Screen { background: #0a0f0a; color: #33ff99; }

    #topbar { height: 1; background: #0a0f0a; color: #33ff99; padding: 0 1; }
    #topbar .accent { color: #47e0e0; }

    #body { height: 1fr; }
    #left  { width: 34; }
    #center { width: 1fr; }
    #right { width: 44; }
    #globe { width: 16; color: #2f9f5f; content-align: center top; }

    Panel {
        border: solid #1f6f3f;
        border-title-color: #6effb0;
        border-title-align: left;
        height: auto;
        padding: 0 1;
        margin: 0 1 1 1;
        background: #0a0f0a;
    }
    #agents-panel { height: 1fr; }
    #projects-panel { height: auto; }
    #logs-panel { height: 1fr; }
    #menu-panel { height: auto; }
    #banner-panel { height: auto; }
    #banner-panel Horizontal { height: auto; }
    #banner { width: 1fr; height: auto; }
    #res-panel Sparkline { height: 1; }
    #system-panel { height: auto; }
    #tasks-panel { height: auto; }
    #motiv-panel { height: auto; }

    Static { color: #33ff99; }
    Menu { padding: 1 0; }
    Menu:focus { }
    LogView { height: 1fr; background: #0a0f0a; scrollbar-size: 1 1; }
    #logs-toolbar { height: 1; margin-bottom: 1; }
    #logs-spacer { width: 1fr; }
    #copy-logs {
        min-width: 10; height: 1; border: none; padding: 0 1;
        background: #123a1f; color: #7dcfa0; text-style: none;
    }
    #copy-logs:hover { background: #1f6f3f; color: #baffd9; }

    #statusbar { height: 1; background: #0a0f0a; color: #7dcfa0; padding: 0 1; }
    #statusbar .ok { color: #33ff99; }
    #statusbar .err { color: #ff5f5f; }
    #statusbar .accent { color: #47e0e0; }
    """

    BINDINGS = [
        Binding("q", "quit", "Quit"),
        Binding("up,k", "menu_up", "Up", show=False),
        Binding("down,j", "menu_down", "Down", show=False),
        Binding("enter", "menu_select", "Select", show=False),
        Binding("n", "new_task", "New Task"),
        Binding("t", "open_terminal", "Terminal"),
        Binding("r", "refresh_now", "Refresh"),
        Binding("c", "copy_logs", "Copy Logs"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self._job_running = False

    # --- layout ---------------------------------------------------
    def compose(self) -> ComposeResult:
        yield Static(id="topbar")

        with Horizontal(id="body"):
            with Vertical(id="left"):
                yield Panel("AGENTS", AgentRows(id="agents"), id="agents-panel")
                yield Panel("PROJECT", SimpleList(id="projects"), id="projects-panel")
                yield Panel("QUICK ACTIONS", KeyActions(id="quick"), id="quick-panel")

            with Vertical(id="center"):
                with Panel("", id="banner-panel"):
                    with Horizontal():
                        yield Banner(id="banner")
                        yield Static(id="globe")
                yield Panel("", Menu(MENU_OPTIONS, id="menu"), id="menu-panel")
                with Panel("LOGS", id="logs-panel"):
                    with Horizontal(id="logs-toolbar"):
                        yield Static("", id="logs-spacer")
                        yield Button("⧉ Copy", id="copy-logs")
                    yield LogView(id="logs")

            with Vertical(id="right"):
                yield Panel("SYSTEM", KeyValue(id="system"), id="system-panel")
                yield Panel(
                    "RESOURCES",
                    Sparkline("CPU", "bright_green", width=34, id="spark-cpu"),
                    Sparkline("MEM", "bright_cyan", width=34, id="spark-mem"),
                    Sparkline("GPU", "yellow", width=34, id="spark-gpu"),
                    id="res-panel",
                )
                yield Panel("ACTIVE TASKS", TaskBars(id="tasks"), id="tasks-panel")
                yield Panel("MOTIVATION", Static(id="motivation"), id="motiv-panel")

        yield Static(id="statusbar")

    # --- lifecycle ---------------------------------------------
    def on_mount(self) -> None:
        self.query_one("#banner", Banner).show(
            banner.wordmark(), banner.TAGLINE, banner.SUBQUOTE
        )
        self.query_one("#globe", Static).update(banner.GLOBE)
        self.query_one("#quick", KeyActions).set_actions(QUICK_ACTIONS)
        self.query_one("#motivation", Static).update(
            f'{banner.MOUNTAINS}\n\n     "Build the life\n      you want."'
        )
        try:
            si = system_info()

            def clip(v: str, n: int = 26) -> str:
                return v if len(v) <= n else v[: n - 1] + "…"

            self.query_one("#system", KeyValue).set_rows([
                ("os", clip(si.os)), ("kernel", clip(si.kernel)), ("uptime", si.uptime),
                ("shell", si.shell), ("terminal", si.terminal),
                ("cpu", clip(si.cpu)), ("gpu", clip(si.gpu)),
                ("mem", si.mem), ("disk", si.disk),
            ])
        except Exception as exc:  # noqa: BLE001
            self.query_one("#system", KeyValue).set_rows([("system", f"n/a ({exc})")])

        self._tick_clock()
        self._tick_resources()
        self._refresh_state()
        self.set_interval(1.0, self._tick_clock)
        self.set_interval(1.0, self._tick_resources)
        self.set_interval(3.0, self._refresh_state)
        # the menu is the primary control — keep it focused so arrows/enter work
        self.call_after_refresh(self.query_one("#menu", Menu).focus)

    # --- periodic updates ------------------------------------
    def _tick_clock(self) -> None:
        now = time.strftime("%a, %d %b %Y  %H:%M:%S")
        bar = self.query_one("#topbar", Static)
        bar.update(
            f"[b #47e0e0]krishil@orion[/]   [#7dcfa0]~/projects/agent-os[/]"
            f"{' ' * 6}{now}   |   ⚡ 100%   |   🌐 online"
        )

    def _tick_resources(self) -> None:
        try:
            r = resource_sample()
        except Exception:  # noqa: BLE001
            return
        self.query_one("#spark-cpu", Sparkline).push(r.cpu)
        self.query_one("#spark-mem", Sparkline).push(r.mem)
        self.query_one("#spark-gpu", Sparkline).push(r.gpu)

    def _refresh_state(self) -> None:
        st = load_state()
        self.query_one("#agents", AgentRows).set_agents(st.agents)
        self.query_one("#projects", SimpleList).set_items(
            st.projects, selected=0 if st.projects else -1, marker="▸"
        )
        self.query_one("#tasks", TaskBars).set_tasks(st.active_tasks)
        # while a job runs, its live event subscriber owns the log feed
        if not self._job_running:
            self.query_one("#logs", LogView).set_lines(st.logs)

        health_class = "ok" if st.errors == 0 else "err"
        self.query_one("#statusbar", Static).update(
            f"[#7dcfa0]⎇ {st.branch}[/]   [#7dcfa0]◇ {len(st.logs)}[/]"
            f"{' ' * 6}[#7dcfa0]{st.active_task_line}[/]  |  "
            f"[{'#33ff99' if st.errors == 0 else '#ff5f5f'}]{st.errors} errors[/]  |  "
            f"[{'#33ff99' if st.errors == 0 else '#ffcf5f'}]● {st.health}[/]"
            f"{' ' * 6}[#47e0e0]>[/]   GOOD BUILDERS SHIP."
        )

    def action_refresh_now(self) -> None:
        self._refresh_state()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "copy-logs":
            self.action_copy_logs()

    def action_copy_logs(self) -> None:
        """Copy the LOGS panel to the system clipboard (OSC 52 — works over SSH too)."""
        text = self.query_one("#logs", LogView).plain_text()
        if not text:
            self.notify("no logs yet", severity="warning")
            return
        self.copy_to_clipboard(text)
        self.notify(f"copied {text.count(chr(10)) + 1} log line(s) to clipboard", timeout=3)

    # --- menu navigation ------------------------------------
    @property
    def _modal_open(self) -> bool:
        return len(self.screen_stack) > 1

    def action_menu_up(self) -> None:
        if not self._modal_open:
            self.query_one("#menu", Menu).move(-1)

    def action_menu_down(self) -> None:
        if not self._modal_open:
            self.query_one("#menu", Menu).move(1)

    def action_menu_select(self) -> None:
        if self._modal_open:
            return
        label = MENU_OPTIONS[self.query_one("#menu", Menu).selected][0]
        if label == "Build something":
            self._prompt_and_run("Build something", single_task=False)
        else:
            self._prompt_and_run("Work on a task", single_task=True)

    def action_new_task(self) -> None:
        self._prompt_and_run("Work on a task", single_task=True)

    def action_open_terminal(self) -> None:
        self.notify("run `aamt build` / `aamt run-task` in a shell", severity="information")

    # --- jobs --------------------------------------------
    def _log_line(self, src: str, msg: str) -> None:
        """Main-thread log append (safe target for call_from_thread)."""
        try:
            self.query_one("#logs", LogView).append_line(
                time.strftime("%H:%M:%S"), src, msg
            )
        except Exception:  # noqa: BLE001
            pass

    def _from_thread_log(self, src: str, msg: str) -> None:
        self.call_from_thread(self._log_line, src, msg)

    @staticmethod
    def _default_repo() -> str:
        from ..config import get_settings

        return str((get_settings().workspace_dir / "tui-project").resolve())

    def _prepare_repo(self, repo: str) -> str:
        """Resolve a local path (create it) or clone a git URL. Runs in the worker."""
        import subprocess

        from ..config import get_settings

        if repo.endswith(".git") or repo.startswith(("http://", "https://", "git@")):
            name = repo.rstrip("/").split("/")[-1].removesuffix(".git") or "cloned"
            dest = (get_settings().workspace_dir / name).resolve()
            if dest.exists() and any(dest.iterdir()):
                self._from_thread_log("orchestrator", f"using existing clone {dest}")
            else:
                dest.parent.mkdir(parents=True, exist_ok=True)
                self._from_thread_log("orchestrator", f"cloning {repo} …")
                subprocess.run(["git", "clone", repo, str(dest)], check=True,
                               capture_output=True, text=True)
            return str(dest)
        p = Path(repo).expanduser().resolve()
        p.mkdir(parents=True, exist_ok=True)
        return str(p)

    def _prompt_and_run(self, title: str, *, single_task: bool) -> None:
        if self._job_running:
            self.notify("a job is already running — wait for it to finish", severity="warning")
            self._log_line("tui", "ignored: a job is already running")
            return
        self._log_line("tui", f"opening “{title}” dialog…")

        def _got(res: tuple[str, str] | None) -> None:
            if not res:
                self._log_line("tui", "cancelled")
                return
            problem, repo = res
            self._job_running = True
            self._log_line("orchestrator", f"queued: {problem[:70]}")
            self.notify("started — watch the LOGS panel", timeout=4)
            if single_task:
                self._job_single_task(problem, repo)
            else:
                self._job_build(problem, repo)

        self.push_screen(BuildPrompt(title, default_repo=self._default_repo()), _got)

    @work(thread=True, group="job", exclusive=True)
    def _job_build(self, problem: str, repo: str) -> None:
        from ..orchestrator import Orchestrator

        try:
            self._from_thread_log("orchestrator", "preparing repository…")
            repo_path = self._prepare_repo(repo)
            self._from_thread_log("orchestrator", f"repo ready: {repo_path}")

            orch = Orchestrator()
            orch.bus.subscribe(
                lambda e: self._from_thread_log(
                    e.agent_id or "orchestrator",
                    e.type.value.replace("_", " ").lower()
                    + (f" · {e.payload.get('title') or e.payload.get('goal') or e.payload.get('reason') or ''}"
                       if isinstance(e.payload, dict) else ""),
                )
            )
            self._from_thread_log("orchestrator", "running: team → backlog → sprints")
            project = orch.run(
                name="tui-build", problem_statement=problem,
                repo_path=repo_path, max_sprints=3,
            )
            self._from_thread_log("orchestrator", f"finished: {project.status.value}")
            self.call_from_thread(self.notify, f"build finished: {project.status.value}")
            orch.close()
        except Exception as exc:  # noqa: BLE001
            self._from_thread_log("system", f"BUILD FAILED: {type(exc).__name__}: {exc}")
            self.call_from_thread(self.notify, f"build failed: {exc}", severity="error")
        finally:
            self._job_running = False
            self.call_from_thread(self._refresh_state)

    @work(thread=True, group="job", exclusive=True)
    def _job_single_task(self, problem: str, repo: str) -> None:
        from ..models.task import Task
        from ..runtime.task_graph import run_task

        try:
            self._from_thread_log("orchestrator", "preparing repository…")
            repo_path = self._prepare_repo(repo)
            self._from_thread_log("backend", f"working the task in {repo_path}")
            res = run_task(
                Task(title=problem[:80], description=problem, role="backend"),
                workspace_root=repo_path, agent_role="backend",
            )
            for line in res.log:
                self._from_thread_log("backend", line)
            self._from_thread_log(
                "backend", f"outcome: {res.outcome.upper()} after {res.attempts} attempt(s)"
                + (f" · commit {res.commit_hash[:10]}" if res.commit_hash else "")
            )
            self.call_from_thread(
                self.notify, f"task {res.outcome.upper()} ({res.attempts} attempt/s)"
            )
        except Exception as exc:  # noqa: BLE001
            self._from_thread_log("system", f"TASK FAILED: {type(exc).__name__}: {exc}")
            self.call_from_thread(self.notify, f"task failed: {exc}", severity="error")
        finally:
            self._job_running = False
            self.call_from_thread(self._refresh_state)

def main() -> None:
    AgentOSApp().run()


if __name__ == "__main__":
    main()
