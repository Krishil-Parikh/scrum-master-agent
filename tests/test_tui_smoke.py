"""The dashboard must mount and render without a live project or network."""

import pytest

from aamt.tui.app import AgentOSApp
from aamt.tui.widgets import LogView, Menu, Sparkline, TaskBars


@pytest.mark.asyncio
async def test_app_mounts_and_has_panels(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # no .aamt state here -> exercises the empty path
    app = AgentOSApp()
    async with app.run_test() as pilot:
        assert app.query_one("#agents")
        assert app.query_one("#logs")
        assert app.query_one("#system")
        assert isinstance(app.query_one("#menu"), Menu)
        assert isinstance(app.query_one("#spark-cpu"), Sparkline)
        # menu navigation
        menu = app.query_one("#menu", Menu)
        start = menu.selected
        await pilot.press("down")
        assert menu.selected == (start + 1) % len(menu.options)
        await pilot.press("up", "up")
        await pilot.pause()
        assert "agent-os" in str(app.query_one("#topbar").render())
        assert "GOOD BUILDERS SHIP" in str(app.query_one("#statusbar").render())


@pytest.mark.asyncio
async def test_build_dialog_opens_and_launches(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from aamt.tui.app import AgentOSApp, BuildPrompt

    app = AgentOSApp()
    launched: dict = {}

    async with app.run_test(size=(150, 44)) as pilot:
        await pilot.pause()
        # intercept the worker so no orchestrator actually runs
        monkeypatch.setattr(
            app, "_job_build",
            lambda problem, repo: launched.update(problem=problem, repo=repo),
        )
        await pilot.press("enter")                       # menu -> "Build something"
        await pilot.pause()
        assert isinstance(app.screen, BuildPrompt)

        # empty submit must NOT close the dialog
        await pilot.press("ctrl+s")
        await pilot.pause()
        assert isinstance(app.screen, BuildPrompt)
        assert "problem statement" in str(app.screen.query_one("#err").render()).lower()

        for ch in "make a thing":
            await pilot.press("space" if ch == " " else ch)
        await pilot.press("enter")                       # problem -> repo
        for ch in "myrepo":
            await pilot.press(ch)
        await pilot.press("ctrl+s")                      # start
        await pilot.pause()

        assert not isinstance(app.screen, BuildPrompt)   # dialog closed
        assert launched == {"problem": "make a thing", "repo": "myrepo"}


@pytest.mark.asyncio
async def test_sparkline_history_and_taskbars():
    app = AgentOSApp()
    async with app.run_test():
        sp = app.query_one("#spark-cpu", Sparkline)
        for v in (10, 50, 90, 200, -5):
            sp.push(v)
        assert len(sp._hist) == sp.width
        assert "CPU" in sp.render().plain

        tb = app.query_one("#tasks", TaskBars)
        tb.set_tasks([("build the api", 42), ("write tests", 100)])
        rendered = str(tb.render())
        assert "42%" in rendered and "100%" in rendered


@pytest.mark.asyncio
async def test_copy_logs_button_and_binding(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)  # isolate from any real project state on disk
    app = AgentOSApp()
    async with app.run_test(size=(150, 44)) as pilot:
        log = app.query_one("#logs", LogView)
        log.append_line("12:00:00", "system", "hello")
        log.append_line("12:00:01", "orchestrator", "world")

        copied: dict = {}
        monkeypatch.setattr(app, "copy_to_clipboard", lambda text: copied.setdefault("text", text))

        await pilot.click("#copy-logs")
        await pilot.pause()
        assert copied["text"] == (
            "[12:00:00] [system] hello\n[12:00:01] [orchestrator] world"
        )

        copied.clear()
        app.action_copy_logs()          # the "c" keybinding path
        assert copied["text"]
