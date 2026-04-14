"""Action parsing and validation — the contract between the game engine and the LLMs."""

from __future__ import annotations
import json
import re
from typing import Optional

from .world import AgentState, WorldState

VALID_ACTIONS = {
    "gather", "trade", "attack", "defend",
    "ally", "sabotage", "campaign", "join_campaign",
}
VALID_GATHER_TARGETS = {"food", "materials"}


class ActionValidationError(Exception):
    pass


def validate_action(action: dict, agent: AgentState, world: WorldState) -> None:
    """Raise ActionValidationError if the action is structurally or logically invalid."""
    action_type = action.get("action")
    if action_type not in VALID_ACTIONS:
        raise ActionValidationError(f"Unknown action type: {action_type!r}")

    alive_names = {a.name for a in world.alive_agents() if a.name != agent.name}

    if action_type == "gather":
        if action.get("target") not in VALID_GATHER_TARGETS:
            raise ActionValidationError(f"Invalid gather target: {action.get('target')!r}")

    elif action_type == "trade":
        target = action.get("with")
        if not target or target not in alive_names:
            raise ActionValidationError(f"Invalid trade target: {target!r}")
        for resource, amount in action.get("offer", {}).items():
            if not isinstance(amount, (int, float)) or amount <= 0:
                raise ActionValidationError(f"Invalid trade offer amount: {amount}")
            agent_val = getattr(agent, resource, None)
            if agent_val is None:
                raise ActionValidationError(f"Unknown resource in offer: {resource!r}")
            if agent_val < amount:
                raise ActionValidationError(
                    f"Insufficient {resource} for trade: have {agent_val}, offering {amount}"
                )

    elif action_type == "attack":
        target = action.get("target")
        if not target or target not in alive_names:
            raise ActionValidationError(f"Invalid attack target: {target!r}")
        mats = action.get("materials_committed", 0)
        if not isinstance(mats, int) or mats < 1:
            raise ActionValidationError("Attack requires at least 1 material committed")
        if agent.materials < mats:
            raise ActionValidationError(
                f"Insufficient materials: have {agent.materials}, committing {mats}"
            )

    elif action_type == "defend":
        mats = action.get("materials_committed", 0)
        if not isinstance(mats, int) or mats < 0:
            raise ActionValidationError("Invalid materials_committed for defend")
        if agent.materials < mats:
            raise ActionValidationError("Insufficient materials for defense")

    elif action_type == "ally":
        target = action.get("target")
        if not target or target not in alive_names:
            raise ActionValidationError(f"Invalid ally target: {target!r}")

    elif action_type == "sabotage":
        target = action.get("target")
        if not target or target not in alive_names:
            raise ActionValidationError(f"Invalid sabotage target: {target!r}")
        if agent.materials < 2:
            raise ActionValidationError("Sabotage requires 2 materials")

    elif action_type == "campaign":
        target = action.get("target")
        if not target or target not in alive_names:
            raise ActionValidationError(f"Invalid campaign target: {target!r}")

    elif action_type == "join_campaign":
        owner = action.get("campaign_owner")
        if not owner or owner not in alive_names:
            raise ActionValidationError(f"Invalid campaign owner: {owner!r}")
        campaign_owner_state = world.agents.get(owner)
        if not campaign_owner_state or not campaign_owner_state.active_campaigns:
            raise ActionValidationError(f"No active campaign from {owner!r}")


def parse_agent_response(
    response_text: str,
    agent: AgentState,
    world: WorldState,
) -> tuple[list[dict], list[dict], str]:
    """
    Parse and validate an agent's raw JSON response.

    Returns:
        (valid_actions, messages, reasoning)

    Invalid actions are logged and skipped — the engine never crashes on a bad move.
    """
    # Some models wrap JSON in markdown code fences or add preamble
    text = response_text.strip()
    json_match = re.search(r"\{.*\}", text, re.DOTALL)
    if not json_match:
        raise ActionValidationError(f"No JSON object found in response")

    try:
        data = json.loads(json_match.group())
    except json.JSONDecodeError as e:
        raise ActionValidationError(f"JSON parse error: {e}")

    raw_actions = data.get("actions", [])[:2]  # Hard cap: 2 actions per round
    messages = data.get("messages", [])
    reasoning = data.get("reasoning", "")

    valid_actions = []
    for action in raw_actions:
        if not isinstance(action, dict):
            continue
        try:
            validate_action(action, agent, world)
            valid_actions.append(action)
        except ActionValidationError as e:
            print(f"    [!] {agent.name} invalid action dropped: {e}")

    return valid_actions, messages, reasoning
