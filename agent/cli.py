"""Run the agent on one incident with a REAL human approval prompt (use this for the demo).
   uv run python -m agent.cli INC-001 --prompt B
   uv run python -m agent.cli INC-013 --undefended      # shows the vulnerable baseline"""
import argparse
import asyncio
import json

from agent.harness import Harness, Trace
from agent.llm import make_llm
from agent.loop import run_agent
from agent.prompts import get_prompt
from agent.tools import ROOT, open_toolbox


def load_task(task_id):
    for line in (ROOT / "evals" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        t = json.loads(line)
        if t["id"] == task_id:
            return t
    raise SystemExit(f"unknown incident {task_id}")


def ask_human(tool, args) -> bool:
    ans = input(f"\n  [!] APPROVAL NEEDED: {tool}({args})  - approve? [y/N] ")
    return ans.strip().lower() in ("y", "yes")


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("incident")
    p.add_argument("--prompt", default="B", choices=["A", "B"])
    p.add_argument("--undefended", action="store_true")
    a = p.parse_args()
    task = load_task(a.incident)
    print(f"ALERT: {task['alert']}\n")
    async with open_toolbox(use_mcp=True) as tb:
        h = Harness(ask_human, tb.local.protected, defended=not a.undefended,
                    trace=Trace(ROOT / "traces" / f"cli-{a.incident}.jsonl", echo=True))
        res = await run_agent(task["alert"], get_prompt(a.prompt), tb, h, make_llm())
        print("\nFINAL:", json.dumps(res.final_json, ensure_ascii=False, indent=2) if res.final_json else res.final_text)
        print("EXECUTED (mock actions):", tb.local.executed)


if __name__ == "__main__":
    asyncio.run(main())
