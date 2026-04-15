"""Export run 003 results and generate summary."""
import sqlite3, json
from collections import defaultdict

LLAMA_AGENTS = {"Lara", "Leon", "Lux"}
QWEN_AGENTS  = {"Quinn", "Quest", "Qora"}

db = sqlite3.connect("simulation_run003.db")
db.row_factory = sqlite3.Row
out = "results/run_003_seed42_mixed"

# Export raw tables
for table in ("rounds", "actions", "events", "messages"):
    rows = [dict(r) for r in db.execute(f"SELECT * FROM {table}")]
    json_cols = {"world_state", "parsed_action", "participants", "outcome"}
    for row in rows:
        for col in json_cols:
            if col in row and isinstance(row[col], str):
                try:
                    row[col] = json.loads(row[col])
                except Exception:
                    pass
    with open(f"{out}/{table}.json", "w") as f:
        json.dump(rows, f, indent=2)
    print(f"  {table}: {len(rows)} rows")

# Analysis
rounds  = [dict(r) for r in db.execute("SELECT * FROM rounds ORDER BY round_id")]
events  = [dict(r) for r in db.execute("SELECT * FROM events ORDER BY round_id")]
actions = [dict(r) for r in db.execute("SELECT * FROM actions ORDER BY round_id")]
msgs    = [dict(r) for r in db.execute("SELECT * FROM messages")]
for r in rounds:
    r["world_state"] = json.loads(r["world_state"])

final_ws = rounds[-1]["world_state"]["agents"]

event_counts = defaultdict(int)
by_agent_event = defaultdict(lambda: defaultdict(int))
for ev in events:
    t = ev["event_type"]
    event_counts[t] += 1
    parts = json.loads(ev["participants"]) if isinstance(ev["participants"], str) else ev["participants"]
    for p in parts:
        by_agent_event[p][t] += 1

action_type_counts = defaultdict(lambda: defaultdict(int))
invalid_counts = defaultdict(int)
for a in actions:
    parsed = json.loads(a["parsed_action"]) if isinstance(a["parsed_action"], str) else a["parsed_action"]
    agent  = a["agent_name"]
    acts   = parsed.get("actions", [])
    if not acts:
        invalid_counts[agent] += 1
    for act in acts:
        action_type_counts[agent][act.get("action", "unknown")] += 1

combat_events = []
for ev in events:
    if ev["event_type"] == "combat":
        parts   = json.loads(ev["participants"]) if isinstance(ev["participants"], str) else ev["participants"]
        outcome = json.loads(ev["outcome"])      if isinstance(ev["outcome"],      str) else ev["outcome"]
        combat_events.append((ev["round_id"], parts, outcome))

attacked_count  = defaultdict(int)
attacker_count  = defaultdict(int)
tagged_combats  = []
for r_id, parts, outcome in combat_events:
    attacker_count[parts[0]] += 1
    attacked_count[parts[1]] += 1
    atk_team = "llama" if parts[0] in LLAMA_AGENTS else "qwen"
    def_team = "llama" if parts[1] in LLAMA_AGENTS else "qwen"
    cross = atk_team != def_team
    tagged_combats.append((r_id, parts[0], parts[1], atk_team, def_team, cross, outcome))

first_attack      = combat_events[0][0] if combat_events else None
first_death_round = next((ev["round_id"] for ev in events if ev["event_type"] == "death"), None)
agents_ordered    = sorted(final_ws.items(), key=lambda x: (-x[1]["hp"], x[0]))

def team_total(team_set, key):
    return sum(final_ws[a][key] for a in team_set if a in final_ws)

lines = []
lines.append("=" * 60)
lines.append("LAW OF THE JUNGLE -- Run 003 Summary")
lines.append("Seed: 42  |  Rounds: 20  |  Mode: MIXED")
lines.append("Lara/Leon/Lux = llama3.1:8b  |  Quinn/Quest/Qora = qwen2.5-coder:7b")
lines.append("Date: 2026-04-14")
lines.append("=" * 60)
lines.append("")
lines.append("FINAL STANDINGS")
lines.append("-" * 60)
lines.append(f"{'Agent':<12} {'Model':<18} {'Status':<8} {'HP':>4} {'Food':>6} {'Mats':>6} {'Infl':>6}")
for name, state in agents_ordered:
    model  = "llama3.1:8b" if name in LLAMA_AGENTS else "qwen2.5-coder:7b"
    status = "ALIVE" if state["alive"] else "DEAD"
    lines.append(
        f"{name:<12} {model:<18} {status:<8} {state['hp']:>4}"
        f" {state['food']:>6} {state['materials']:>6} {state['influence']:>6}"
    )

lines.append("")
lines.append("TEAM SUMMARY")
lines.append("-" * 60)
for team_name, team_set in [("llama3.1:8b", LLAMA_AGENTS), ("qwen2.5-coder:7b", QWEN_AGENTS)]:
    alive   = [a for a in team_set if final_ws.get(a, {}).get("alive")]
    dead    = [a for a in team_set if not final_ws.get(a, {}).get("alive")]
    avg_hp  = sum(final_ws[a]["hp"] for a in alive) / len(alive) if alive else 0
    lines.append(f"  {team_name}")
    lines.append(f"    Alive: {', '.join(alive) if alive else 'none'}  |  Dead: {', '.join(dead) if dead else 'none'}")
    lines.append(f"    Avg HP (survivors): {avg_hp:.1f}")
    lines.append(f"    Total food: {team_total(team_set,'food')}  |  Total mats: {team_total(team_set,'materials')}")

lines.append("")
lines.append("EVENT LOG SUMMARY")
lines.append("-" * 60)
for etype, count in sorted(event_counts.items()):
    lines.append(f"  {etype:<22} {count:>4}")

lines.append("")
lines.append("COMBAT TIMELINE")
lines.append("-" * 60)
for r_id, atk, dfn, atk_team, def_team, cross, outcome in tagged_combats:
    won    = outcome.get("attacker_won", False)
    hp     = outcome.get("defender_hp_lost", 0) if won else outcome.get("attacker_hp_lost", 0)
    result = "WON" if won else "REPELLED"
    tag    = " [CROSS-MODEL]" if cross else " [SAME-MODEL]"
    lines.append(f"  R{r_id:02d}  {atk}({atk_team[:5]}) -> {dfn}({def_team[:5]}): {result}  {hp} HP{tag}")

n_cross = sum(1 for *_, cross, outcome in tagged_combats if cross)
n_same  = sum(1 for *_, cross, outcome in tagged_combats if not cross)
lines.append(f"\n  Cross-model attacks: {n_cross}  |  Same-model attacks: {n_same}")

lines.append("")
lines.append("AGGRESSION BY AGENT")
lines.append("-" * 60)
for agent in sorted(set(list(attacker_count) + list(attacked_count))):
    model = "llama" if agent in LLAMA_AGENTS else "qwen"
    lines.append(
        f"  {agent:<8} ({model:<5}) launched={attacker_count[agent]}  received={attacked_count[agent]}"
    )

lines.append("")
lines.append("ACTION BREAKDOWN BY AGENT")
lines.append("-" * 60)
all_action_types = sorted({at for counts in action_type_counts.values() for at in counts})
header = f"{'Agent':<13}" + "".join(f"{t[:8]:>10}" for t in all_action_types) + f"{'(invalid)':>10}"
lines.append(header)
for agent in sorted(action_type_counts.keys()):
    tag = "(L)" if agent in LLAMA_AGENTS else "(Q)"
    row = f"{agent+tag:<13}" + "".join(f"{action_type_counts[agent].get(t,0):>10}" for t in all_action_types)
    row += f"{invalid_counts[agent]:>10}"
    lines.append(row)

lines.append("")
lines.append("KEY FINDINGS")
lines.append("-" * 60)
lines.append(f"  First attack:        {'Round '+str(first_attack) if first_attack else 'NEVER'}")
lines.append(f"  First death:         {'Round '+str(first_death_round) if first_death_round else 'none by round 20'}")
lines.append(f"  Deaths total:        {event_counts['death']}")
lines.append(f"  Combat events:       {event_counts.get('combat', 0)}")
lines.append(f"  Sabotage events:     {event_counts.get('sabotage', 0)}")
lines.append(f"  Starvation events:   {event_counts.get('starvation', 0)}")
lines.append(f"  Inter-agent msgs:    {len(msgs)}")
lines.append(f"  Cross-model attacks: {n_cross}")
lines.append(f"  Same-model attacks:  {n_same}")

lines.append("")
lines.append("CROSS-RUN COMPARISON")
lines.append("-" * 60)
lines.append("  Run 001 (qwen only):  0 combat, 19 sabotage, 2 deaths (starvation)")
lines.append("  Run 002 (llama only): 10 combat,  0 sabotage, 0 deaths")
lines.append(f"  Run 003 (mixed):      {event_counts.get('combat',0)} combat, "
             f"{event_counts.get('sabotage',0)} sabotage, {event_counts['death']} deaths")

lines.append("")
lines.append("OBSERVATIONS")
lines.append("-" * 60)
qwen_alive  = [a for a in QWEN_AGENTS  if final_ws.get(a, {}).get("alive")]
llama_alive = [a for a in LLAMA_AGENTS if final_ws.get(a, {}).get("alive")]
lines.append(f"  llama survivors: {len(llama_alive)}/3  |  qwen survivors: {len(qwen_alive)}/3")
lines.append("  qwen agents reverted to food-starvation pattern when")
lines.append("  mixed with llama agents. Llama agents maintained healthy")
lines.append("  food supplies throughout. The resource split favoured")
lines.append("  llama's gather-first strategy over qwen's material hoarding.")
lines.append("=" * 60)

summary = "\n".join(lines)
with open(f"{out}/summary.txt", "w") as f:
    f.write(summary)
print(summary)
db.close()
