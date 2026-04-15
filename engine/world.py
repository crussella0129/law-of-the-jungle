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

    # Base per-round island resource generation.
    # 8 food for 6 agents needing 12/round = genuine scarcity.
    FOOD_PER_ROUND: int = 8
    MATERIALS_PER_ROUND: int = 5

    # Food spoilage cap: excess food above this per-agent threshold rots.
    FOOD_SPOILAGE_CAP: int = 8

    # Base food consumption per round (can be multiplied by famine events).
    FOOD_CONSUMPTION: int = 2

    def alive_agents(self) -> list[AgentState]:
        return [a for a in self.agents.values() if a.alive]

    def generate_resources(self, food_mult: float = 1.0, mat_mult: float = 1.0) -> None:
        """Add per-round resources to the island pool, scaled by event multipliers."""
        self.island_food      += int(self.FOOD_PER_ROUND * food_mult)
        self.island_materials += int(self.MATERIALS_PER_ROUND * mat_mult)

    def apply_food_spoilage(self) -> list[str]:
        """Cap each agent's food at FOOD_SPOILAGE_CAP. Return spoilage event strings."""
        events = []
        for agent in self.alive_agents():
            cap = self.FOOD_SPOILAGE_CAP
            if agent.food > cap:
                lost = agent.food - cap
                agent.food = cap
                events.append(f"{agent.name}'s food stockpile spoiled ({lost} units rotted)")
        return events

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
