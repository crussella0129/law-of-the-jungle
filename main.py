#!/usr/bin/env python3
"""Law of the Jungle — CLI entry point."""

from __future__ import annotations
import argparse
import os
import sys

from dotenv import load_dotenv

from engine.agents import AnthropicAgent, OpenAIAgent, GoogleAgent, OllamaAgent
from engine.game import GameEngine
from engine.logger import SimulationLogger


load_dotenv()


def build_agents(mixed: bool = False) -> list:
    agents = []

    ak = os.getenv("ANTHROPIC_API_KEY")
    ok = os.getenv("OPENAI_API_KEY")
    gk = os.getenv("GOOGLE_API_KEY")
    ollama_url = os.getenv("OLLAMA_URL", "http://localhost:11434")
    ollama_model = os.getenv("OLLAMA_MODEL", "llama3.1:8b")

    if ak:
        agents.append(AnthropicAgent("Claudia", model_id="claude-sonnet-4-6", api_key=ak))
    if ok:
        agents.append(OpenAIAgent("Geppetto", model_id="gpt-4o", api_key=ok))
    if gk:
        agents.append(GoogleAgent("Gemini", model_id="gemini-1.5-pro", api_key=gk))

    if mixed and not agents:
        # 3 llama3.1:8b + 3 qwen2.5-coder:7b, named to encode model family
        llama_names = ["Lara", "Leon", "Lux"]
        qwen_names  = ["Quinn", "Quest", "Qora"]
        for name in llama_names:
            agents.append(OllamaAgent(name, model_id="llama3.1:8b", base_url=ollama_url))
        for name in qwen_names:
            agents.append(OllamaAgent(name, model_id="qwen2.5-coder:7b", base_url=ollama_url))
    else:
        # Fill remaining slots with the default model
        island_names = ["Rex", "Vex", "Mox", "Zara", "Kira", "Dax"]
        local_count = max(0, 6 - len(agents))
        for i in range(local_count):
            name = island_names[i % len(island_names)]
            agents.append(OllamaAgent(name, model_id=ollama_model, base_url=ollama_url))

    return agents


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Law of the Jungle -- Multi-Agent LLM Survival Simulation"
    )
    parser.add_argument("--rounds", type=int, default=50, help="Max rounds (default 50, recommend 50+ with events)")
    parser.add_argument("--seed",   type=int, default=None, help="RNG seed for reproducibility")
    parser.add_argument("--db",     type=str, default="simulation.db", help="SQLite log path")
    parser.add_argument("--mixed",  action="store_true",
                        help="Mixed roster: 3x llama3.1:8b (Lara/Leon/Lux) vs 3x qwen2.5-coder:7b (Quinn/Quest/Qora)")
    args = parser.parse_args()

    agents = build_agents(mixed=args.mixed)
    if len(agents) < 2:
        print("ERROR: Need at least 2 agents. Set API keys in .env or run Ollama locally.")
        return 1

    print(f"Agents ({len(agents)}): {', '.join(a.name for a in agents)}")

    logger = SimulationLogger(db_path=args.db)
    engine = GameEngine(agents=agents, logger=logger, seed=args.seed)

    try:
        engine.run(max_rounds=args.rounds)
    finally:
        logger.close()

    return 0


if __name__ == "__main__":
    sys.exit(main())
