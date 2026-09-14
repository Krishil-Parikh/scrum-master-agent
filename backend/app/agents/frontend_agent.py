"""Frontend Developer Agent (PRD §7)."""

from app.agents.base import BaseAgent
from app.agents.profiles import PROFILES
from app.schemas.agent import AgentSpecialty


class FrontendAgent(BaseAgent):
    def __init__(self):
        super().__init__(PROFILES[AgentSpecialty.FRONTEND])
