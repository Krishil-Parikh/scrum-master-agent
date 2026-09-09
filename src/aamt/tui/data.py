"""Live data providers for the dashboard — system metrics + project state."""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
import time
from dataclasses import dataclass, field

from ..config import get_settings


# --------------------------------------------------------------------------
# system / resources
# --------------------------------------------------------------------------
@dataclass
class SystemInfo:
    os: str
    kernel: str
    uptime: str
    shell: str
    terminal: str
    cpu: str
    gpu: str
    mem: str
    disk: str


def _fmt_bytes(n: float) -> str:
    for unit in ("B", "K", "M", "G", "T"):
        if n < 1024:
            return f"{n:.0f}{unit}" if unit in "BK" else f"{n:.1f}{unit}"
        n /= 1024
    return f"{n:.1f}P"


def _gpu_name() -> str:
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.run(
                [smi, "--query-gpu=name", "--format=csv,noheader"],
                capture_output=True, text=True, timeout=3,
            ).stdout.strip()
            if out:
                return out.splitlines()[0]
        except Exception:  # noqa: BLE001
            pass
    return platform.processor().split()[0] if platform.processor() else "integrated"


def system_info() -> SystemInfo:
    import psutil

    vm = psutil.virtual_memory()
    du = psutil.disk_usage(os.path.abspath(os.sep))
    boot = psutil.boot_time()
    secs = int(time.time() - boot)
    h, m = divmod(secs // 60, 60)
    up = f"{h // 24}d {h % 24}h {m}m" if h >= 24 else f"{h}h {m}m"

    cpu_raw = (platform.processor() or platform.machine() or "cpu").split(",")[0]
    cpu = " ".join(cpu_raw.split()[:3])
    return SystemInfo(
        os=f"{platform.system()} {platform.release()}",
        kernel=platform.version().split(" ")[0] or platform.release(),
        uptime=up,
        shell=os.environ.get("SHELL", os.environ.get("COMSPEC", "sh")).replace("\\", "/").split("/")[-1],
        terminal=os.environ.get("TERM_PROGRAM") or os.environ.get("TERM", "xterm"),
        cpu=f"{cpu} ({psutil.cpu_count()})",
        gpu=_gpu_name()[:22],
        mem=f"{_fmt_bytes(vm.used)} / {_fmt_bytes(vm.total)} ({vm.percent:.0f}%)",
        disk=f"{_fmt_bytes(du.used)} / {_fmt_bytes(du.total)} ({du.percent:.0f}%)",
    )


@dataclass
class ResourceSample:
    cpu: float = 0.0
    mem: float = 0.0
    gpu: float = 0.0


def resource_sample() -> ResourceSample:
    import psutil

    gpu = 0.0
    smi = shutil.which("nvidia-smi")
    if smi:
        try:
            out = subprocess.run(
                [smi, "--query-gpu=utilization.gpu", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=2,
            ).stdout.strip()
            gpu = float(out.splitlines()[0]) if out else 0.0
        except Exception:  # noqa: BLE001
            gpu = 0.0
    return ResourceSample(
        cpu=psutil.cpu_percent(interval=None),
        mem=psutil.virtual_memory().percent,
        gpu=gpu,
    )


# --------------------------------------------------------------------------
# project state
# --------------------------------------------------------------------------
@dataclass
class DashboardState:
    project_name: str = "—"
    project_status: str = "no project"
    sprint_goal: str = ""
    branch: str = "main"
    agents: list[tuple[str, str]] = field(default_factory=list)      # (name, status)
    projects: list[str] = field(default_factory=list)
    active_tasks: list[tuple[str, int]] = field(default_factory=list)  # (title, pct)
    logs: list[tuple[str, str, str]] = field(default_factory=list)   # (hhmmss, source, msg)
    errors: int = 0
    active_task_line: str = "no active task"
    health: str = "all systems operational"


_DEFAULT_AGENTS = [
    ("orchestrator", "online"), ("scrum-master", "online"),
    ("backend", "idle"), ("frontend", "idle"), ("database", "idle"),
    ("ml", "idle"), ("qa", "idle"), ("devops", "idle"),
    ("memory", "online"), ("tools", "online"),
]

_ROLE_SRC = {"scrum-master": "scrum-master"}


def _status_pct(status: str) -> int:
    return {
        "BACKLOG": 5, "READY": 10, "ASSIGNED": 20, "IN_PROGRESS": 55,
        "IN_REVIEW": 75, "TESTING": 85, "DONE": 100, "BLOCKED": 40, "REOPENED": 45,
    }.get(status, 0)


def load_state(max_logs: int = 200) -> DashboardState:
    s = get_settings()
    st = DashboardState()
    try:
        from ..events.bus import EventBus
        from ..models.enums import BacklogItemKind, TaskStatus
        from ..state.store import ProjectStore

        if not s.state_db_path.exists():
            st.agents = list(_DEFAULT_AGENTS)
            st.projects = ["(no project yet — pick 'Build something')"]
            return st

        store = ProjectStore(s.state_db_path)
        bus = EventBus(s.data_dir / "events.db")
        project = store.get_project()

        if project:
            st.project_name = project.name
            st.project_status = project.status.value
            st.branch = "main"
            sp = store.current_sprint()
            st.sprint_goal = sp.goal if sp else ""

        agents = store.list_agents()
        if agents:
            live = {a.role: a.status.value.lower() for a in agents}
            st.agents = [("orchestrator", "online")] + [
                (a.role, a.status.value.lower()) for a in sorted(agents, key=lambda x: x.role)
            ] + [("memory", "online"), ("tools", "online")]
        else:
            st.agents = list(_DEFAULT_AGENTS)

        # aamt runs one project at a time (ProjectStore is a singleton) — show
        # that project's real status rather than an unrelated directory listing.
        st.projects = (
            [f"{project.name}  ·  {project.status.value}"] if project
            else ["(no project yet — pick 'Build something')"]
        )

        tasks = store.list_tasks()
        active = [
            t for t in tasks
            if t.kind is BacklogItemKind.TASK
            and t.status in (TaskStatus.IN_PROGRESS, TaskStatus.ASSIGNED,
                             TaskStatus.TESTING, TaskStatus.IN_REVIEW, TaskStatus.REOPENED)
        ]
        st.active_tasks = [(t.title, _status_pct(t.status.value)) for t in active[:5]]
        in_prog = [t for t in tasks if t.status is TaskStatus.IN_PROGRESS]
        st.active_task_line = (
            f"{in_prog[0].title[:40]}" if in_prog else "no active task"
        )

        events = bus.query(project_id=project.id if project else None)[-max_logs:]
        for e in events:
            src = e.agent_id or (e.payload.get("role") if isinstance(e.payload, dict) else None) or "system"
            msg = e.type.value.replace("_", " ").lower()
            extra = ""
            if isinstance(e.payload, dict):
                for k in ("title", "goal", "reason", "note", "hash", "number"):
                    if e.payload.get(k):
                        extra = f" {e.payload[k]}"
                        break
            st.logs.append((time.strftime("%H:%M:%S", time.localtime(e.ts)), src, msg + extra))
        st.errors = sum(
            1 for e in events
            if e.type.value in ("AGENT_FAILED", "TEST_FAILED", "MERGE_CONFLICT")
        )
        st.health = (
            "all systems operational" if st.errors == 0 else f"{st.errors} issue(s) — see logs"
        )
        store.close(); bus.close()
    except Exception as exc:  # noqa: BLE001 - dashboard must never crash the UI
        st.logs.append((time.strftime("%H:%M:%S"), "tui", f"state load error: {exc}"))
        if not st.agents:
            st.agents = list(_DEFAULT_AGENTS)
    return st
