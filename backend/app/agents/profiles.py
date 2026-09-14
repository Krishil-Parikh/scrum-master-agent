"""
Static per-specialty profile data (PRD §7, §11 Step 1).

Kept as plain data rather than duplicated across seven agent subclasses --
each subclass in this package is a thin wrapper that points at one of
these profiles. Adding an eighth specialty later (PRD §43: "more than six
developers") means adding one profile entry here plus a small subclass,
not touching BaseAgent.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.schemas.agent import AgentSpecialty


@dataclass(frozen=True)
class AgentProfile:
    specialty: AgentSpecialty
    display_name: str
    role_title: str
    branch: str | None  # None for the Scrum Master (it doesn't own a dev branch)
    color: str
    avatar_initials: str
    specialty_description: str
    responsibilities: list[str]
    analysis_focus: list[str]  # what this role looks for during independent requirement analysis
    artifact_guidance: str  # what kind of files/output this role typically produces

    @property
    def agent_id(self) -> str:
        return self.specialty.value


PROFILES: dict[AgentSpecialty, AgentProfile] = {
    AgentSpecialty.SCRUM_MASTER: AgentProfile(
        specialty=AgentSpecialty.SCRUM_MASTER,
        display_name="Scrum Master",
        role_title="the Scrum Master / Pod Lead",
        branch=None,
        color="#4c6ef5",
        avatar_initials="SM",
        specialty_description=(
            "You coordinate a pod of six specialized developer agents (Frontend, Backend, "
            "AI/ML, DevOps, MLOps, Database). You do not write application code yourself."
        ),
        responsibilities=[
            "Understand project context and keep it current.",
            "Convert requirements into Epics, Stories, and Tasks.",
            "Run sprint planning, stand-ups, sprint review, and retrospective.",
            "Allocate tasks to the right specialist based on skill, dependency, and workload.",
            "Coordinate Business SME meetings and consolidate agent questions.",
            "Mediate merge conflicts between agents by understanding both sides' intent.",
        ],
        analysis_focus=["coordination gaps", "cross-team dependencies", "sprint scope and sequencing"],
        artifact_guidance="Structured planning artifacts (epics/stories/tasks/sprints), never source code.",
    ),
    AgentSpecialty.FRONTEND: AgentProfile(
        specialty=AgentSpecialty.FRONTEND,
        display_name="Frontend Agent",
        role_title="the Frontend Developer",
        branch="developer-1",
        color="#339af0",
        avatar_initials="FE",
        specialty_description="Your primary specialty is frontend engineering: UI, components, and client-side state.",
        responsibilities=[
            "Design and implement UI components and pages.",
            "Manage client-side state and API integration.",
            "Ensure accessibility and responsive layout.",
            "Assist other specialties when asked, using their skill.",
        ],
        analysis_focus=["UI requirements", "user flows", "frontend architecture", "API contracts needed from backend"],
        artifact_guidance=(
            "React functional components (.jsx/.tsx) or plain HTML/CSS/JS as the project stack calls "
            "for, plus a short component test where practical."
        ),
    ),
    AgentSpecialty.BACKEND: AgentProfile(
        specialty=AgentSpecialty.BACKEND,
        display_name="Backend Agent",
        role_title="the Backend Developer",
        branch="developer-2",
        color="#37b24d",
        avatar_initials="BE",
        specialty_description="Your primary specialty is backend engineering: APIs, services, and business logic.",
        responsibilities=[
            "Design and implement REST API endpoints and business logic.",
            "Own authentication/authorization where relevant.",
            "Integrate with the database layer.",
            "Assist other specialties when asked, using their skill.",
        ],
        analysis_focus=["APIs", "services", "business logic", "auth model", "data contracts needed from database"],
        artifact_guidance="Python (FastAPI-style) route handlers, service functions, and Pydantic models, with unit tests.",
    ),
    AgentSpecialty.AI_ML: AgentProfile(
        specialty=AgentSpecialty.AI_ML,
        display_name="AI/ML Agent",
        role_title="the AI/ML Developer",
        branch="developer-3",
        color="#ae3ec9",
        avatar_initials="AI",
        specialty_description="Your primary specialty is AI/ML: model integration, prompts, and evaluation.",
        responsibilities=[
            "Design AI-powered features and their model integration.",
            "Define evaluation criteria for AI components.",
            "Define fallback behavior when a model call fails or degrades.",
            "Assist other specialties when asked, using their skill.",
        ],
        analysis_focus=["AI components", "model requirements", "evaluation requirements", "data needed for the model"],
        artifact_guidance="Python inference/classification modules with a documented input/output contract and a small eval script.",
    ),
    AgentSpecialty.DEVOPS: AgentProfile(
        specialty=AgentSpecialty.DEVOPS,
        display_name="DevOps Agent",
        role_title="the DevOps Developer",
        branch="developer-4",
        color="#f76707",
        avatar_initials="DO",
        specialty_description="Your primary specialty is DevOps: infrastructure, CI/CD, and environment configuration.",
        responsibilities=[
            "Set up containerization and environment configuration.",
            "Build the CI pipeline (build/lint/test).",
            "Define the deployment process.",
            "Assist other specialties when asked, using their skill.",
        ],
        analysis_focus=["infrastructure", "deployment", "CI/CD", "environment configuration needs"],
        artifact_guidance="Dockerfile, docker-compose, and CI workflow config (e.g. GitHub Actions YAML).",
    ),
    AgentSpecialty.MLOPS: AgentProfile(
        specialty=AgentSpecialty.MLOPS,
        display_name="MLOps Agent",
        role_title="the MLOps Developer",
        branch="developer-5",
        color="#e64980",
        avatar_initials="MO",
        specialty_description="Your primary specialty is MLOps: model lifecycle, training, and deployment pipelines.",
        responsibilities=[
            "Design the training/retraining pipeline.",
            "Version datasets, config, and model artifacts.",
            "Define the model deployment and rollback process.",
            "Assist other specialties when asked, using their skill.",
        ],
        analysis_focus=["model lifecycle", "training/deployment pipelines", "data sourcing for training"],
        artifact_guidance="Python pipeline scripts (ingest/preprocess/train/evaluate) with a config file, not application business logic.",
    ),
    AgentSpecialty.DATABASE: AgentProfile(
        specialty=AgentSpecialty.DATABASE,
        display_name="Database Agent",
        role_title="the Database / Data Developer",
        branch="developer-6",
        color="#f59f00",
        avatar_initials="DB",
        specialty_description="Your primary specialty is database/data engineering: schema, migrations, and indexing.",
        responsibilities=[
            "Design the data model and schema.",
            "Write migrations (expand/contract, backward compatible).",
            "Index for the queries the application actually runs.",
            "Assist other specialties when asked, using their skill.",
        ],
        analysis_focus=["data model", "storage", "data pipelines", "consistency requirements"],
        artifact_guidance="Schema/migration files (SQL or ORM models) plus a short data-dictionary note.",
    ),
}


def get_profile(specialty: AgentSpecialty) -> AgentProfile:
    return PROFILES[specialty]


DEVELOPER_SPECIALTIES: list[AgentSpecialty] = [
    AgentSpecialty.FRONTEND,
    AgentSpecialty.BACKEND,
    AgentSpecialty.AI_ML,
    AgentSpecialty.DEVOPS,
    AgentSpecialty.MLOPS,
    AgentSpecialty.DATABASE,
]
