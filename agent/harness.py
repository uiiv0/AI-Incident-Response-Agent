"""Harness: rules enforced in CODE (not in the prompt): allowlist, human approval,
protected assets, step budget, context budget/compaction, tracing."""
import json
import time
from dataclasses import dataclass
from pathlib import Path

from agent.tools import GATED

ALLOWED_TOOLS = {"search_logs", "lookup_ip_reputation", "get_asset_info", "create_ticket",
                 "isolate_host", "disable_account", "block_ip"}


@dataclass
class Decision:
    allowed: bool
    reason: str


def est_tokens(messages) -> int:
    return len(json.dumps(messages, ensure_ascii=False)) // 4


class Trace:
    def __init__(self, path=None, echo=False):
        self.path = Path(path) if path else None
        self.echo = echo
        self.events = []
        if self.path:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.path.write_text("", encoding="utf-8")

    def log(self, event, **data):
        rec = {"t": round(time.time(), 3), "event": event, **data}
        self.events.append(rec)
        if self.path:
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        if self.echo:
            print(f"  [{event}] " + json.dumps(data, ensure_ascii=False)[:220])


class Harness:
    def __init__(self, approve_fn, protected, defended=True, max_steps=12,
                 max_result_chars=2500, max_context_tokens=6000, trace=None):
        self.approve_fn = approve_fn          # (tool, args) -> bool  (the human)
        self.protected = {                    # never touched, even if a human says yes
            "isolate_host": {h.lower() for h in protected["hosts"]},
            "disable_account": {u.lower() for u in protected["users"]},
            "block_ip": {i.lower() for i in protected["ips"]},
        }
        self.defended = defended              # False = vulnerable baseline for the attack demo
        self.max_steps = max_steps
        self.max_result_chars = max_result_chars
        self.max_context_tokens = max_context_tokens
        self.trace = trace or Trace()

    def authorize(self, tool, args) -> Decision:
        if tool not in ALLOWED_TOOLS:
            return Decision(False, "tool not in allowlist")
        if not isinstance(args, dict):
            return Decision(False, "arguments must be an object")
        if tool not in GATED:
            return Decision(True, "read-only/low-risk tool")
        if not self.defended:
            return Decision(True, "UNDEFENDED: executed with no checks")
        target = str(args.get(GATED[tool], "")).strip()
        if not target:
            return Decision(False, "missing target")
        if target.lower() in self.protected[tool]:
            return Decision(False, f"protected asset: {target}")
        if not self.approve_fn(tool, args):
            return Decision(False, "human rejected")
        return Decision(True, "approved by human")

    def wrap_result(self, text) -> str:
        text = str(text)
        if len(text) > self.max_result_chars:
            text = text[: self.max_result_chars] + "\n…[truncated]"
        # Marking data as untrusted is a mitigation only. The real defence is authorize().
        return f"<untrusted_tool_output>\n{text}\n</untrusted_tool_output>"

    def compact(self, messages) -> bool:
        if est_tokens(messages) <= self.max_context_tokens:
            return False
        tool_idx = [i for i, m in enumerate(messages) if m["role"] == "tool"]
        for i in tool_idx[:-2]:               # keep the 2 most recent tool results intact
            c = messages[i]["content"]
            if len(c) > 200:
                messages[i]["content"] = c[:200] + " …[compacted]"
        self.trace.log("compaction", tokens_after=est_tokens(messages))
        return True
