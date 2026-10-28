"""The agent loop: model -> tool calls -> harness.authorize -> tools -> repeat."""
import asyncio
import json
import re
from dataclasses import dataclass, field

from agent.harness import Harness, est_tokens
from agent.tools import GATED, Toolbox

THINK = re.compile(r"<think>.*?</think>", re.S)


@dataclass
class ToolCallRecord:
    name: str
    args: dict
    allowed: bool
    reason: str
    executed: bool
    result_preview: str


@dataclass
class RunResult:
    final_text: str = ""
    final_json: dict | None = None
    steps: int = 0
    stop_reason: str = "final"          # final | step_budget
    calls: list = field(default_factory=list)
    est_tokens: int = 0

    @property
    def gated_requests(self):
        return [(c.name, str(c.args.get(GATED[c.name], "")).lower())
                for c in self.calls if c.name in GATED and isinstance(c.args, dict)]


def extract_json(text):
    text = THINK.sub("", text or "")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        return None
    try:
        obj = json.loads(m.group(0))
        return obj if isinstance(obj, dict) else None
    except json.JSONDecodeError:
        return None


def _parse_args(raw):
    if isinstance(raw, dict):
        return raw
    try:
        v = json.loads(raw or "{}")
        return v if isinstance(v, dict) else {}
    except json.JSONDecodeError:
        return {}


async def run_agent(alert: str, system_prompt: str, toolbox: Toolbox, harness: Harness, llm) -> RunResult:
    messages = [{"role": "system", "content": system_prompt}, {"role": "user", "content": alert}]
    res = RunResult()
    for step in range(1, harness.max_steps + 1):
        res.steps = step
        harness.compact(messages)
        msg = await asyncio.to_thread(llm, messages, toolbox.schemas)
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        harness.trace.log("model", step=step, content=(msg.get("content") or "")[:300],
                          tool_calls=[c["function"]["name"] for c in calls])
        if not calls:
            res.final_text = msg.get("content") or ""
            res.final_json = extract_json(res.final_text)
            res.est_tokens = est_tokens(messages)
            return res
        for c in calls:
            name = c["function"]["name"]
            args = _parse_args(c["function"].get("arguments"))
            d = harness.authorize(name, args)
            executed = False
            if d.allowed:
                try:
                    result = await toolbox.call(name, args)
                    executed = name in GATED
                except Exception as e:      # bad args from a small model, tool crash...
                    result = f"ERROR: {type(e).__name__}: {e}"
            else:
                result = f"DENIED by harness: {d.reason}"
            harness.trace.log("tool", name=name, args=args, allowed=d.allowed, reason=d.reason,
                              executed=executed, result=str(result)[:200])
            res.calls.append(ToolCallRecord(name, args, d.allowed, d.reason, executed, str(result)[:200]))
            messages.append({"role": "tool", "tool_call_id": c["id"],
                             "content": harness.wrap_result(result)})
    res.stop_reason = "step_budget"
    res.est_tokens = est_tokens(messages)
    return res
