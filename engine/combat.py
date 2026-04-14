"""Combat resolution — Risk-inspired probabilistic combat."""

from __future__ import annotations
import random
from dataclasses import dataclass


@dataclass
class CombatResult:
    attacker: str
    defender: str
    attacker_strength: float
    defender_strength: float
    attacker_won: bool
    defender_hp_lost: int
    attacker_hp_lost: int
    attacker_influence_gained: int
    defender_influence_gained: int
    materials_consumed_attacker: int


def resolve_combat(
    attacker_name: str,
    defender_name: str,
    attacker_materials: int,
    attacker_influence: float,
    defender_materials: int,
    defender_influence: float,
    campaign_bonus: int = 0,
    attacker_ally_count: int = 0,
    defender_ally_count: int = 0,
) -> CombatResult:
    """
    Resolve combat between attacker and defender.

    Strength formula:
        attacker = materials * (1 + 0.1 * influence) + d6 + ally_bonus + campaign_bonus
        defender = materials * (1 + 0.1 * influence) + d6 + 2 + ally_bonus   (defender advantage)

    If attacker > defender:
        defender loses (delta * 3) HP, attacker gains 1 influence
    Else:
        attacker loses (delta * 2) HP, defender gains 1 influence

    All committed materials are consumed regardless of outcome.
    """
    atk_str = (
        attacker_materials * (1 + 0.1 * attacker_influence)
        + random.randint(1, 6)
        + attacker_ally_count
        + campaign_bonus
    )
    def_str = (
        defender_materials * (1 + 0.1 * defender_influence)
        + random.randint(1, 6)
        + 2  # defender advantage
        + defender_ally_count
    )

    if atk_str > def_str:
        delta = atk_str - def_str
        return CombatResult(
            attacker=attacker_name,
            defender=defender_name,
            attacker_strength=atk_str,
            defender_strength=def_str,
            attacker_won=True,
            defender_hp_lost=int(delta * 3),
            attacker_hp_lost=0,
            attacker_influence_gained=1,
            defender_influence_gained=0,
            materials_consumed_attacker=attacker_materials,
        )
    else:
        delta = def_str - atk_str
        return CombatResult(
            attacker=attacker_name,
            defender=defender_name,
            attacker_strength=atk_str,
            defender_strength=def_str,
            attacker_won=False,
            defender_hp_lost=0,
            attacker_hp_lost=int(delta * 2),
            attacker_influence_gained=0,
            defender_influence_gained=1,
            materials_consumed_attacker=attacker_materials,
        )
