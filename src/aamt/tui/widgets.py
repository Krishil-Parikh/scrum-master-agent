"""Custom widgets for the AGENT.OS dashboard."""

from __future__ import annotations

from collections import deque

from rich.text import Text
from textual.containers import Vertical
from textual.widgets import RichLog, Static

_SPARK = "▁▁▂▃▄▅▆▇█"


class Panel(Vertical):
    """A titled, bordered box — the `[ TITLE ]` frames in the design."""

    def __init__(self, title: str, *children, **kwargs) -> None:
        super().__init__(*children, **kwargs)
        self.border_title = f" {title} "


class KeyValue(Static):
    """Two-column aligned key/value block (the SYSTEM panel)."""

    def set_rows(self, rows: list[tuple[str, str]]) -> None:
        width = max((len(k) for k, _ in rows), default=0)
        t = Text()
        for i, (k, v) in enumerate(rows):
            if i:
                t.append("\n")
            t.append(f"{k.upper():<{width}}  ", style="dim green")
            t.append(v, style="bright_green")
        self.update(t)


class AgentRows(Static):
    """`● name        status` list with colour-coded state."""

    WIDTH = 26  # inner width of the AGENTS panel

    def set_agents(self, agents: list[tuple[str, str]], selected: int = 0) -> None:
        colours = {
            "online": "bright_green", "idle": "grey58", "thinking": "yellow",
            "working": "bright_cyan", "blocked": "red", "failed": "red",
            "paused": "grey58",
        }
        t = Text()
        for i, (name, status) in enumerate(agents):
            if i:
                t.append("\n")
            dot = "●" if status in ("online", "working", "thinking") else "○"
            col = colours.get(status, "green")
            left = f" {dot} {name[:14]}"
            gap = max(1, self.WIDTH - len(left) - len(status))
            if i == selected:
                t.append(left + " " * gap + status, style="bright_green on #123a24")
            else:
                t.append(left + " " * gap, style="green")
                t.append(status, style=col)
        self.update(t)


class SimpleList(Static):
    """Bulleted list with an optional highlighted row (PROJECTS / QUICK ACTIONS)."""

    def set_items(self, items: list[str], selected: int = -1, marker: str = "▸") -> None:
        t = Text()
        for i, item in enumerate(items):
            if i:
                t.append("\n")
            sel = i == selected
            t.append(f" {marker if sel else ' '} ", style="bright_green")
            t.append(item, style="bright_green on #10331e" if sel else "green")
        self.update(t)


class KeyActions(Static):
    """`n  New Task` style shortcut list."""

    def set_actions(self, actions: list[tuple[str, str]]) -> None:
        t = Text()
        for i, (key, label) in enumerate(actions):
            if i:
                t.append("\n")
            t.append(f" {key} ", style="black on bright_green")
            t.append(f"  {label}", style="green")
        self.update(t)


class Menu(Static):
    """The centred 'What do you want to do?' option list."""

    can_focus = True

    def __init__(self, options: list[tuple[str, str]], **kwargs) -> None:
        super().__init__(**kwargs)
        self.options = options
        self.selected = 0

    def on_mount(self) -> None:
        self._paint()

    def _paint(self) -> None:
        t = Text()
        t.append(" > What do you want to do?\n\n", style="bright_green bold")
        label_w = max(len(a) for a, _ in self.options)
        for i, (label, desc) in enumerate(self.options):
            sel = i == self.selected
            style = "bright_green on #10331e" if sel else "green"
            t.append(" ▸ " if sel else "   ", style="bright_green")
            t.append(f"{label:<{label_w}}   ", style=style + (" bold" if sel else ""))
            t.append(f"{desc:<34}", style="grey58" if not sel else "bright_green")
            t.append(" →\n", style="bright_green" if sel else "grey42")
        self.update(t)

    def move(self, delta: int) -> None:
        self.selected = (self.selected + delta) % len(self.options)
        self._paint()


class Sparkline(Static):
    """A single labelled unicode bar chart with a rolling history."""

    def __init__(self, label: str, colour: str = "bright_green", width: int = 30, **kwargs) -> None:
        super().__init__(**kwargs)
        self.label = label
        self.colour = colour
        self.width = width
        self._hist: deque[float] = deque([0.0] * width, maxlen=width)

    def on_mount(self) -> None:
        self._paint()

    def push(self, value: float) -> None:
        self._hist.append(max(0.0, min(100.0, value)))
        self._paint()

    def _paint(self) -> None:
        cur = self._hist[-1] if self._hist else 0.0
        bars = "".join(
            _SPARK[min(len(_SPARK) - 1, int(v / 100 * (len(_SPARK) - 1)))] for v in self._hist
        )
        t = Text()
        t.append(f"{self.label:<4}", style="dim green")
        t.append(f"{cur:>3.0f}%  ", style="bright_green")
        t.append(bars, style=self.colour)
        self.update(t)

    def render(self) -> Text:  # kept for tests / direct inspection
        cur = self._hist[-1] if self._hist else 0.0
        bars = "".join(
            _SPARK[min(len(_SPARK) - 1, int(v / 100 * (len(_SPARK) - 1)))] for v in self._hist
        )
        return Text(f"{self.label:<4}{cur:>3.0f}%  {bars}")


class TaskBars(Static):
    """`name            42% [████░░░]` progress rows."""

    def set_tasks(self, tasks: list[tuple[str, int]], bar_w: int = 12) -> None:
        t = Text()
        if not tasks:
            self.update(Text(" (no active tasks)", style="grey42"))
            return
        name_w = 26
        for i, (name, pct) in enumerate(tasks):
            if i:
                t.append("\n")
            filled = round(pct / 100 * bar_w)
            t.append(f"{name[:name_w]:<{name_w}} ", style="green")
            t.append(f"{pct:>3}% ", style="bright_green")
            t.append("█" * filled, style="bright_green")
            t.append("░" * (bar_w - filled), style="grey30")
        self.update(t)


_SRC_COLOUR = {
    "orchestrator": "bright_green", "scrum-master": "cyan", "coder": "red",
    "backend": "bright_cyan", "frontend": "magenta", "qa": "yellow",
    "database": "green", "devops": "bright_yellow",
    "system": "grey58", "tui": "grey42",
}


class LogView(RichLog):
    """Timestamped `[hh:mm:ss] [source] message` feed (newest at the bottom)."""

    MAX_HISTORY = 600

    def __init__(self, **kwargs) -> None:
        super().__init__(highlight=False, markup=False, wrap=False, max_lines=600, **kwargs)
        self._seen: set[tuple[str, str, str]] = set()
        # ordered, mirrors what's on screen — `_seen` alone can't reproduce order.
        self._history: list[tuple[str, str, str]] = []

    def _line(self, ts: str, src: str, msg: str) -> Text:
        t = Text()
        t.append(f"[{ts}] ", style="grey42")
        t.append(f"[{src}] ", style=_SRC_COLOUR.get(src, "green"))
        t.append(msg, style="green")
        return t

    def _record(self, key: tuple[str, str, str]) -> None:
        self._seen.add(key)
        self._history.append(key)
        if len(self._history) > self.MAX_HISTORY:
            del self._history[: -self.MAX_HISTORY]

    def set_lines(self, lines: list[tuple[str, str, str]]) -> None:
        # append only rows we haven't shown yet (keeps the scroll position sane)
        new = [ln for ln in lines if ln not in self._seen]
        if not self._seen and lines:
            self.clear()
        for ln in new:
            self._record(ln)
            self.write(self._line(*ln))

    def append_line(self, ts: str, src: str, msg: str) -> None:
        key = (ts, src, msg)
        self._record(key)
        self.write(self._line(*key))

    def plain_text(self) -> str:
        """Everything currently shown, as copyable plain text."""
        return "\n".join(f"[{ts}] [{src}] {msg}" for ts, src, msg in self._history)


class Banner(Static):
    def show(self, art: str, tagline: str, subquote: str) -> None:
        t = Text()
        t.append(art + "\n", style="bright_green bold")
        t.append("        " + tagline + "\n\n", style="bright_green")
        t.append("        " + subquote, style="grey62 italic")
        self.update(t)
