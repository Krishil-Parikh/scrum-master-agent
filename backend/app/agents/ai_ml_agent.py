"""AI/ML Developer Agent (PRD §7)."""

from app.agents.base import BaseAgent
from app.agents.profiles import PROFILES
from app.schemas.agent import AgentSpecialty


class AiMlAgent(BaseAgent):
    def __init__(self):
        super().__init__(PROFILES[AgentSpecialty.AI_ML])
