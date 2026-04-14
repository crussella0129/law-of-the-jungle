"""World state: agent attributes and island-level resource management."""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class AgentState:
    name: str
    hp: int = 100
    food: int = 10
    materials: int = 5
    influence: int = 3
    alive: bool = True
    alliances: list[str] = field(default_factory=list)
    # Campaigns this agent owns (declaring an offensive)
    active_campaigns: list[str] = field(default_factory=list)
    # Campaigns from others targeting this agent
    targeted_by_campaigns: list[str] = field(default_factory=list)
    # Campaigns this agent has joined as an ally
    joined_campaigns: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "hp": self.hp,
            "food": self.food,
            "materials": self.materials,
            "influence": self.influence,
            "alive": self.alive,
            "alliances": self.alliances,
            "active_campaigns": self.active_campaigns,
            "targeted_by_campaigns": self.targeted_by_campaigns,
            "joined_campaigns": self.joined_campaigns,
        }


@dataclass
class WorldState:
    round_number: int
    agents: dict[str, AgentState]
    island_food: int = 0
    island_materials: int = 0

    # Base per-round island resource generation
    FOOD_PER_ROUND: int = 12
    MATERIALS_PER_ROUND: int = 8

    def alive_agents(self) -> list[AgentState]:
        return [a for a in self.agents.values() if a.alive]

    def generate_resources(self) -> None:
        """Add per-round resources to the island pool."""
        self.island_food += self.FOOD_PER_ROUND
        self.island_materials += self.MATERIALS_PER_ROUND

    def scatter_death_resources(self, agent: AgentState) -> None:
        """Return a dead agent's resources to the island pool."""
        self.island_food += agent.food
        self.island_materials += agent.materials
        agent.food = 0
        agent.materials = 0

    def to_dict(self) -> dict:
        return {
            "round": self.round_number,
            "island_food": self.island_food,
            "island_materials": self.island_materials,
            "agents": {name: a.to_dict() for name, a in self.agents.items()},
        }
