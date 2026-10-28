"""Run the eval: configs A vs B, k trials per task, automatic graders.
   uv run python -m evals.run_eval --configs A B --k 2
Tip: the LLM cache makes re-runs free. If you hit a rate limit, just run it again."""
import argparse
import asyncio
import json
from collections import Counter
from pathlib import Path

from agent.harness import Harness, Trace
from agent.llm import make_llm
from agent.loop import run_agent
from agent.prompts import get_prompt
from agent.tools import LocalTools, open_toolbox
from evals.graders import grade

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "evals" / "results"


def load_tasks(ids=None, limit=None):
    tasks = [json.loads(l) for l in (ROOT / "evals" / "tasks.jsonl").read_text(encoding="utf-8").splitlines()]
    if ids:
        tasks = [t for t in tasks if t["id"] in ids]
    return tasks[:limit] if limit else tasks


def summarize(rows):
    out = {}
    for cfg in sorted({r["config"] for r in rows}):
        rs = [r for r in rows if r["config"] == cfg]
        by_task = {}
        for r in rs:
            by_task.setdefault(r["task"], []).append(r["passed"])
        out[cfg] = {
            "tasks": len(by_task), "trials": len(rs),
            "pass_rate": sum(r["passed"] for r in rs) / len(rs),
            "pass_k": sum(all(v) for v in by_task.values()) / len(by_task),
            "inj_attempted": sum(r["injection_attempted"] for r in rs),
            "inj_executed": sum(r["injection_executed"] for r in rs),
            "avg_steps": sum(r["steps"] for r in rs) / len(rs),
            "errors": dict(Counter(e for r in rs for e in r["errors"])),
        }
    return out


def to_markdown(summary, k):
    lines = [f"| Config | Tasks | Trials | Pass rate | pass^{k} | Injection attempted | Injection executed | Avg steps |",
             "|---|---|---|---|---|---|---|---|"]
    for cfg, s in summary.items():
        lines.append(f"| {cfg} | {s['tasks']} | {s['trials']} | {s['pass_rate']:.0%} | {s['pass_k']:.0%} | "
                     f"{s['inj_attempted']} | {s['inj_executed']} | {s['avg_steps']:.1f} |")
    labels = sorted({e for s in summary.values() for e in s["errors"]})
    if labels:
        lines += ["", "| Error label | " + " | ".join(summary) + " |", "|---|" + "---|" * len(summary)]
        for lab in labels:
            lines.append(f"| {lab} | " + " | ".join(str(s["errors"].get(lab, 0)) for s in summary.values()) + " |")
    return "\n".join(lines)


async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--configs", nargs="+", default=["A", "B"])
    p.add_argument("--k", type=int, default=2, help="trials per task")
    p.add_argument("--limit", type=int)
    p.add_argument("--ids", nargs="+")
    p.add_argument("--no-cache", action="store_true")
    a = p.parse_args()
    tasks = load_tasks(a.ids, a.limit)
    rows = []
    OUT.mkdir(parents=True, exist_ok=True)
    async with open_toolbox(use_mcp=True) as tb:
        for cfg in a.configs:
            system = get_prompt(cfg)
            for task in tasks:
                for trial in range(a.k):
                    tb.local = LocalTools()
                    h = Harness(lambda t, args: True,      # simulated human: approves; protected assets still blocked
                                tb.local.protected, defended=True,
                                trace=Trace(ROOT / "traces" / f"{cfg}-{task['id']}-t{trial}.jsonl"))
                    res = await run_agent(task["alert"], system, tb, h, make_llm(trial, not a.no_cache))
                    g = grade(task, res)
                    rows.append({"config": cfg, "task": task["id"], "category": task["category"],
                                 "trial": trial, "steps": res.steps, "tokens": res.est_tokens,
                                 "final": res.final_json, **g})
                    print(f"{cfg} {task['id']} t{trial}: {'PASS' if g['passed'] else 'FAIL ' + ','.join(g['errors'])}")
    summary = summarize(rows)
    (OUT / "results.json").write_text(json.dumps({"rows": rows, "summary": summary}, indent=2, ensure_ascii=False), encoding="utf-8")
    md = to_markdown(summary, a.k)
    (OUT / "results.md").write_text(md + "\n", encoding="utf-8")
    print("\n" + md)


if __name__ == "__main__":
    asyncio.run(main())
