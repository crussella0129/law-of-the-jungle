"""Main game loop — orchestrates rounds, resolves actions, tracks deaths."""

from __future__ import annotations
import random
import time
from typing import Optional

from .world import AgentState, WorldState
from .combat import resolve_combat
from .actions import parse_agent_response, ActionValidationError
from .prompts import build_system_prompt
from .logger import SimulationLogger
from .agents.base import BaseAgent
from .events import roll_event, IslandEvent


def distribute_gathered_resources(
    gatherers: list[str],
    pool: int,
    agents: dict[str, AgentState],
) -> dict[str, int]:
    """
    Decide how many resources each gathering agent receives from the island pool.

    Parameters:
        gatherers  — names of agents who chose to gather this resource this round
        pool       — total units available in the island pool right now
        agents     — full agent state dict (access influence, hp, etc. as needed)

    Returns:
        A dict mapping each gatherer's name to the units they receive.
        The sum of values MUST NOT exceed pool (you can't create resources).

    TODO: Implement your allocation strategy.

    Consider the trade-offs:
        - Equal split:          simple, fair, no strategic depth
        - Influence-weighted:   rewards high-influence agents (rich get richer)
        - Diminishing returns:  first gatherer gets most, others fight over scraps
        - Random lottery:       pure luck, maximizes variance across runs
        - Proportional to HP:   starving agents gather more (survival mechanic)

    5–10 lines of code. Your choice shapes how the scarcity phase plays out.
    """
    # Equal split — neutral baseline for alignment research.
    # Keeps economics independent of combat dominance so survival rank
    # reflects strategic choices, not a rich-get-richer feedback loop.
    if not gatherers or pool <= 0:
        return {name: 0 for name in gatherers}
    per_agent = pool // len(gatherers)
    remainder = pool - per_agent * len(gatherers)
    # Give the remainder to a random gatherer (small fairness noise)
    allocation = {name: per_agent for name in gatherers}
    if remainder > 0:
        allocation[random.choice(gatherers)] += remainder
    return allocation


class GameEngine:
    def __init__(
        self,
        agents: list[BaseAgent],
        logger: SimulationLogger,
        seed: Optional[int] = None,
    ):
        self.agents = {a.name: a for a in agents}
        self.logger = logger

        if seed is not None:
            random.seed(seed)

        agent_states = {name: AgentState(name=name) for name in self.agents}
        self.world = WorldState(round_number=0, agents=agent_states)

        self.last_events: list[str] = []
        self.private_messages: dict[str, list[str]] = {name: [] for name in self.agents}
        # campaign_rounds[owner] = (target_name, rounds_remaining)
        self.campaign_rounds: dict[str, tuple[str, int]] = {}

    # ── Public API ──────────────────────────────────────────────────────────

    def run(self, max_rounds: int = 50) -> None:
        print(f"\n{'='*60}")
        print("LAW OF THE JUNGLE -- Simulation start")
        print(f"Agents: {', '.join(self.agents)}")
        print(f"{'='*60}\n")

        for round_num in range(1, max_rounds + 1):
            self.world.round_number = round_num
            alive = self.world.alive_agents()

            if len(alive) <= 1:
                print(f"\n{'='*60}")
                if alive:
                    print(f"WINNER: {alive[0].name} survives after {round_num - 1} rounds!")
                else:
                    print("All agents perished. No winner.")
                print(f"{'='*60}")
                break

            sep = "-" * 60
            print(f"\n{sep}")
            print(f"ROUND {round_num}  --  {len(alive)} agents alive")
            print(sep)
            self._run_round(round_num)

    # ── Private helpers ──────────────────────────────────────────────────────

    def _run_round(self, round_num: int) -> None:
        world = self.world

        # ── Roll this round's event ────────────────────────────────────────
        event: IslandEvent | None = roll_event()
        food_mult = event.food_gen_mult if event else 1.0
        mat_mult  = event.mat_gen_mult  if event else 1.0
        food_consumption = int(world.FOOD_CONSUMPTION * (event.food_cost_mult if event else 1.0))

        world.generate_resources(food_mult=food_mult, mat_mult=mat_mult)

        if event:
            print(f"  [EVENT] {event.name.upper()}: {event.announcement[:80]}")
            self.logger.log_event(round_num, f"event_announced", [],
                                  {"event": event.name, "announcement": event.announcement})

        self.logger.log_round(round_num, world.to_dict())

        all_actions: dict[str, list[dict]] = {}
        all_messages: dict[str, list[dict]] = {}

        # ── Collect decisions ──────────────────────────────────────────────
        for agent_state in world.alive_agents():
            name = agent_state.name
            api = self.agents[name]
            prompt = build_system_prompt(
                agent_state, world,
                self.last_events,
                self.private_messages.get(name, []),
                current_event=event,
                food_consumption=food_consumption,
            )

            print(f"  [{name}] thinking...")
            try:
                raw, latency_ms = api.get_response(prompt)
                actions, messages, reasoning = parse_agent_response(raw, agent_state, world)
            except Exception as exc:
                print(f"  [{name}] ERROR: {exc}")
                raw, latency_ms = "", 0
                actions, messages, reasoning = [], [], f"ERROR: {exc}"

            all_actions[name] = actions
            all_messages[name] = messages
            self.logger.log_action(round_num, name, prompt, raw, {"actions": actions}, latency_ms)
            print(f"  [{name}] reasoning: {reasoning[:120]!r}")

        # Clear private inboxes (consumed this round)
        self.private_messages = {n: [] for n in self.agents}

        # ── Deliver messages ───────────────────────────────────────────────
        round_events: list[str] = []
        for sender_name, messages in all_messages.items():
            for msg in messages:
                if not isinstance(msg, dict) or "message" not in msg:
                    continue
                payload = msg["message"]
                recipient = payload.get("to", "all")
                content = payload.get("content", "")
                is_private = recipient != "all"

                self.logger.log_message(round_num, sender_name, recipient, content, is_private)

                if recipient == "all":
                    round_events.append(f'{sender_name} broadcasts: "{content}"')
                    for other in world.alive_agents():
                        if other.name != sender_name:
                            self.private_messages[other.name].append(
                                f"[broadcast from {sender_name}]: {content}"
                            )
                else:
                    if recipient in self.private_messages:
                        self.private_messages[recipient].append(
                            f"[private from {sender_name}]: {content}"
                        )

        # ── Bucket actions by type ─────────────────────────────────────────
        food_gatherers: list[str] = []
        mat_gatherers: list[str] = []
        attack_actions: list[tuple[str, dict]] = []
        defend_mats: dict[str, int] = {}
        ally_proposals: list[tuple[str, str]] = []
        sabotage_actions: list[tuple[str, str]] = []

        for agent_name, actions in all_actions.items():
            agent_state = world.agents[agent_name]
            if not agent_state.alive:
                continue
            for action in actions:
                t = action.get("action")
                if t == "gather":
                    (food_gatherers if action.get("target") == "food" else mat_gatherers).append(agent_name)
                elif t == "attack":
                    attack_actions.append((agent_name, action))
                elif t == "defend":
                    mats = action.get("materials_committed", 0)
                    agent_state.materials -= mats
                    defend_mats[agent_name] = mats
                elif t == "ally":
                    ally_proposals.append((agent_name, action.get("target", "")))
                elif t == "sabotage":
                    sabotage_actions.append((agent_name, action.get("target", "")))
                elif t == "campaign":
                    target = action.get("target", "")
                    self.campaign_rounds[agent_name] = (target, 3)
                    world.agents[agent_name].active_campaigns.append(target)
                    if agent_name not in world.agents[target].targeted_by_campaigns:
                        world.agents[target].targeted_by_campaigns.append(agent_name)
                    ev = f"{agent_name} declares a campaign against {target}!"
                    round_events.append(ev)
                    print(f"  CAMPAIGN: {ev}")
                elif t == "join_campaign":
                    owner = action.get("campaign_owner", "")
                    agent_state.joined_campaigns.append(owner)
                    ev = f"{agent_name} joins {owner}'s campaign"
                    round_events.append(ev)

        # ── Resolve gathering ──────────────────────────────────────────────
        for resource_name, gatherers, pool_attr in [
            ("food", food_gatherers, "island_food"),
            ("materials", mat_gatherers, "island_materials"),
        ]:
            if not gatherers:
                continue
            pool = getattr(world, pool_attr)
            allocation = distribute_gathered_resources(gatherers, pool, world.agents)
            total_given = sum(allocation.values())
            setattr(world, pool_attr, pool - total_given)
            for gname, amount in allocation.items():
                setattr(world.agents[gname], resource_name,
                        getattr(world.agents[gname], resource_name) + amount)
                round_events.append(f"{gname} gathered {amount} {resource_name}")
                print(f"  GATHER: {gname} +{amount} {resource_name}")

        # ── Resolve alliances ──────────────────────────────────────────────
        proposals_by_pair: dict[frozenset, list[str]] = {}
        for proposer, target in ally_proposals:
            key = frozenset([proposer, target])
            proposals_by_pair.setdefault(key, []).append(proposer)

        for key, proposers in proposals_by_pair.items():
            a, b = list(key)
            if len(proposers) == 2:
                if b not in world.agents[a].alliances:
                    world.agents[a].alliances.append(b)
                if a not in world.agents[b].alliances:
                    world.agents[b].alliances.append(a)
                ev = f"{a} and {b} formed an alliance"
                round_events.append(ev)
                print(f"  ALLIANCE: {ev}")
            else:
                proposer = proposers[0]
                ev = f"{proposer} proposed alliance to {[n for n in [a, b] if n != proposer][0]} (pending)"
                round_events.append(ev)

        # ── Resolve sabotage ───────────────────────────────────────────────
        for attacker_name, target_name in sabotage_actions:
            attacker = world.agents[attacker_name]
            target = world.agents.get(target_name)
            if not target or not target.alive:
                continue
            attacker.materials -= 2
            food_hit = min(3, target.food)
            mats_hit = min(2, target.materials)
            target.food -= food_hit
            target.materials -= mats_hit
            ev = f"{attacker_name} sabotaged {target_name}: -{food_hit} food, -{mats_hit} materials"
            round_events.append(ev)
            print(f"  SABOTAGE: {ev}")
            self.logger.log_event(round_num, "sabotage", [attacker_name, target_name],
                                  {"food_destroyed": food_hit, "mats_destroyed": mats_hit})

        # ── Resolve combat ─────────────────────────────────────────────────
        for attacker_name, action in attack_actions:
            target_name = action.get("target", "")
            attacker = world.agents[attacker_name]
            target = world.agents.get(target_name)
            if not target or not target.alive:
                continue

            mats_committed = min(action.get("materials_committed", 1), attacker.materials)
            attacker.materials -= mats_committed

            campaign_bonus = 0
            if attacker_name in self.campaign_rounds:
                ct, _ = self.campaign_rounds[attacker_name]
                if ct == target_name:
                    campaign_bonus = 2

            atk_allies = sum(1 for a in attacker.alliances if a in all_actions)
            def_allies = sum(1 for a in target.alliances if a in all_actions)

            result = resolve_combat(
                attacker_name, target_name,
                mats_committed, attacker.influence,
                defend_mats.get(target_name, 0), target.influence,
                campaign_bonus=campaign_bonus,
                attacker_ally_count=atk_allies,
                defender_ally_count=def_allies,
            )

            if result.attacker_won:
                target.hp -= result.defender_hp_lost
                attacker.influence += 1
                ev = (f"{attacker_name} -> {target_name}: WON "
                      f"(atk={result.attacker_strength:.1f} vs def={result.defender_strength:.1f}) "
                      f"| {target_name} -{result.defender_hp_lost} HP -> {target.hp}")
            else:
                attacker.hp -= result.attacker_hp_lost
                target.influence += 1
                ev = (f"{attacker_name} -> {target_name}: REPELLED "
                      f"(atk={result.attacker_strength:.1f} vs def={result.defender_strength:.1f}) "
                      f"| {attacker_name} -{result.attacker_hp_lost} HP -> {attacker.hp}")

            round_events.append(ev)
            print(f"  COMBAT: {ev}")
            self.logger.log_event(round_num, "combat", [attacker_name, target_name], {
                "attacker_won": result.attacker_won,
                "defender_hp_lost": result.defender_hp_lost,
                "attacker_hp_lost": result.attacker_hp_lost,
                "atk_str": result.attacker_strength,
                "def_str": result.defender_strength,
            })

        # ── Tick down campaigns ────────────────────────────────────────────
        finished = [o for o, (_, r) in self.campaign_rounds.items() if r - 1 <= 0]
        for owner in finished:
            target, _ = self.campaign_rounds.pop(owner)
            world.agents[owner].active_campaigns = [
                c for c in world.agents[owner].active_campaigns if c != target
            ]
            world.agents[target].targeted_by_campaigns = [
                c for c in world.agents[target].targeted_by_campaigns if c != owner
            ]
            round_events.append(f"{owner}'s campaign against {target} ended")
        for owner in list(self.campaign_rounds):
            if owner not in finished:
                t, r = self.campaign_rounds[owner]
                self.campaign_rounds[owner] = (t, r - 1)

        # ── Event HP damage (storm / plague) ──────────────────────────────
        if event and (event.hp_loss_all > 0):
            for agent_state in world.alive_agents():
                defended = agent_state.name in defend_mats and defend_mats[agent_state.name] >= 2
                hp_hit = event.hp_loss_defended if defended else event.hp_loss_all
                if hp_hit > 0:
                    agent_state.hp -= hp_hit
                    shield = " (defended)" if defended else ""
                    ev = f"{event.name.upper()}: {agent_state.name} loses {hp_hit} HP{shield} -> {agent_state.hp}"
                    round_events.append(ev)
                    print(f"  EVENT DMG: {ev}")
                    self.logger.log_event(round_num, f"event_{event.name}", [agent_state.name],
                                          {"hp_lost": hp_hit, "defended": defended})

        # ── Food consumption ───────────────────────────────────────────────
        for agent_state in world.alive_agents():
            food_needed = food_consumption
            if agent_state.food >= food_needed:
                agent_state.food -= food_needed
            else:
                shortfall  = food_needed - agent_state.food
                hp_penalty = (shortfall // 2 + (1 if shortfall % 2 else 0)) * 10
                agent_state.food = 0
                agent_state.hp  -= hp_penalty
                ev = (f"{agent_state.name} {'starved' if food_consumption == 2 else 'famine-starved'}!"
                      f" (needed {food_needed}, had {agent_state.food + food_needed - shortfall})"
                      f" -{hp_penalty} HP -> {agent_state.hp}")
                round_events.append(ev)
                print(f"  STARVE: {ev}")
                self.logger.log_event(round_num, "starvation", [agent_state.name],
                                      {"hp": agent_state.hp, "food_needed": food_needed})

        # ── Food spoilage ──────────────────────────────────────────────────
        for ev in world.apply_food_spoilage():
            round_events.append(ev)
            print(f"  SPOIL: {ev}")

        # ── Process deaths ─────────────────────────────────────────────────
        for agent_state in list(world.alive_agents()):
            if agent_state.hp <= 0:
                agent_state.alive = False
                world.scatter_death_resources(agent_state)
                ev = f"[DEAD] {agent_state.name} has DIED. Resources returned to island."
                round_events.append(ev)
                print(f"  DEATH: {agent_state.name}")
                self.logger.log_event(round_num, "death", [agent_state.name], {
                    "hp": agent_state.hp
                })

        self.last_events = round_events

        # ── Round summary ──────────────────────────────────────────────────
        print(f"\n  End of round {round_num}:")
        for a in world.agents.values():
            status = "alive" if a.alive else "DEAD"
            print(f"    {a.name:12s} {status:5s}  HP={a.hp:3d}  Food={a.food:2d}  "
                  f"Mats={a.materials:2d}  Influence={a.influence}")
