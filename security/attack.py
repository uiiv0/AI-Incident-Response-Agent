"""Prompt-injection attack demo against a REAL model.
   uv run python -m security.attack --incident INC-013 --undefended   # attack works
   uv run python -m security.attack --incident INC-013                # defence blocks it
The log of INC-013 contains a user-agent that tells the agent to isolate the domain controller."""
import argparse
import asyncio

from agent.harness import Harness, Trace
from agent.llm import make_llm
from agent.loop import run_agent
from agent.prompts import get_prompt
from agent.cli import load_task
from agent.tools import ROOT, open_toolbox
from evals.graders import grade


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--incident", default="INC-013", choices=["INC-013", "INC-014", "INC-015"])
    p.add_argument("--prompt", default="A", choices=["A", "B"])
    p.add_argument("--undefended", action="store_true")
    p.add_argument("--no-cache", action="store_true")
    a = p.parse_args()
    task = load_task(a.incident)
    mode = "UNDEFENDED" if a.undefended else "DEFENDED"
    async with open_toolbox(use_mcp=True) as tb:
        h = Harness(lambda t, args: True,   # even a human who approves everything must not matter
                    tb.local.protected, defended=not a.undefended,
                    trace=Trace(ROOT / "traces" / f"attack-{a.incident}-{mode}.jsonl", echo=True))
        res = await run_agent(task["alert"], get_prompt(a.prompt), tb, h, make_llm(use_cache=not a.no_cache))
    g = grade(task, res)
    print(f"\n[{mode}] prompt={a.prompt}")
    print("  gated calls requested by the model:", res.gated_requests)
    print("  injection attempted:", g["injection_attempted"], "| EXECUTED:", g["injection_executed"])
    print("  mock actions that really ran:", tb.local.executed)


if __name__ == "__main__":
    asyncio.run(main())
