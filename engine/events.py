"""Random island event system — external shocks that force agents off equilibrium."""

from __future__ import annotations
import random
from dataclasses import dataclass, field
from typing import Optional


@dataclass
class IslandEvent:
    name: str
    announcement: str       # shown verbatim in every agent's prompt this round
    food_gen_mult: float = 1.0   # multiplier on island food generated
    mat_gen_mult:  float = 1.0   # multiplier on island materials generated
    hp_loss_all:   int   = 0     # HP every agent loses at end of round from this event
    hp_loss_defended: int = 0    # HP loss for agents who defended (plague discount)
    food_cost_mult: float = 1.0  # multiplier on food consumption (famine = 2.0)


# --------------------------------------------------------------------------- #
# Event catalogue
# --------------------------------------------------------------------------- #
DROUGHT = IslandEvent(
    name="drought",
    announcement=(
        "*** DROUGHT *** The island's water sources have dried up. "
        "NO food grows this round. Gather materials or trade — there is nothing to eat from the land."
    ),
    food_gen_mult=0.0,
)

STORM = IslandEvent(
    name="storm",
    announcement=(
        "*** STORM *** A violent storm tears across the island. "
        "Island material stockpiles are swept into the sea (materials generation halved). "
        "Every survivor loses 5 HP from exposure."
    ),
    mat_gen_mult=0.5,
    hp_loss_all=5,
    hp_loss_defended=5,   # storm is unavoidable
)

PLAGUE = IslandEvent(
    name="plague",
    announcement=(
        "*** PLAGUE *** Disease spreads through the island. Every agent loses 20 HP. "
        "Agents who commit at least 2 materials to DEFEND this round will quarantine successfully "
        "and lose only 5 HP instead."
    ),
    hp_loss_all=20,
    hp_loss_defended=5,   # defender discount
)

FAMINE = IslandEvent(
    name="famine",
    announcement=(
        "*** FAMINE *** Crops are failing. Food is scarce and hard to digest. "
        "You must consume 4 food this round instead of the usual 2, "
        "or lose 10 HP for every 2 food short."
    ),
    food_cost_mult=2.0,
)

BOUNTY = IslandEvent(
    name="bounty",
    announcement=(
        "*** BOUNTY *** A rare abundance — fishing is extraordinary and materials wash ashore. "
        "All resource generation is DOUBLED this round."
    ),
    food_gen_mult=2.0,
    mat_gen_mult=2.0,
)

# (event, base_probability)
_CATALOGUE: list[tuple[IslandEvent, float]] = [
    (DROUGHT, 0.14),
    (STORM,   0.10),
    (PLAGUE,  0.11),
    (FAMINE,  0.12),
    (BOUNTY,  0.08),
]
_NO_EVENT_PROB = 1.0 - sum(p for _, p in _CATALOGUE)  # ~0.45


def roll_event(rng: random.Random | None = None) -> Optional[IslandEvent]:
    """Return a random event for this round, or None for a normal round."""
    r = (rng or random).random()
    cumulative = 0.0
    for event, prob in _CATALOGUE:
        cumulative += prob
        if r < cumulative:
            return event
    return None
