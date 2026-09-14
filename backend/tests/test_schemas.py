from app.schemas.agent import AgentSpecialty, AgentState, AgentStatus
from app.schemas.task import Backlog, Epic, Task, TaskRisk, TaskStatus, UserStory


def test_agent_status_defaults_and_touch():
    status = AgentStatus(agent_id="frontend")
    assert status.state == AgentState.IDLE
    before = status.last_active_at
    status.touch()
    assert status.last_active_at >= before


def test_backlog_roundtrip_json():
    backlog = Backlog()
    epic = Epic(epic_id="epic_1", title="Auth")
    story = UserStory(story_id="story_1", epic_id="epic_1", title="Login", i_want="to log in", so_that="I can access my data")
    task = Task(
        task_id="task_1",
        story_id="story_1",
        title="Build login API",
        specialty=AgentSpecialty.BACKEND,
        risk=TaskRisk.MEDIUM,
        status=TaskStatus.READY,
    )
    epic.story_ids.append(story.story_id)
    story.task_ids.append(task.task_id)
    backlog.epics[epic.epic_id] = epic
    backlog.stories[story.story_id] = story
    backlog.tasks[task.task_id] = task

    raw = backlog.model_dump_json()
    restored = Backlog.model_validate_json(raw)

    assert restored.tasks["task_1"].specialty == AgentSpecialty.BACKEND
    assert restored.tasks["task_1"].status == TaskStatus.READY
    assert restored.stories["story_1"].statement == "As a user, I want to log in, so that I can access my data"


def test_task_risk_is_independent_of_status():
    task = Task(task_id="t1", story_id="s1", title="x", specialty=AgentSpecialty.DATABASE, risk=TaskRisk.HIGH)
    assert task.risk == TaskRisk.HIGH
    assert task.status == TaskStatus.BACKLOG  # default
