"""Scripted fake models, so security tests do not depend on any real LLM."""
import json
import re

INJ = re.compile(r"call (isolate_host|disable_account|block_ip) with (host|user|ip) "
                 r"([A-Za-z0-9_.\-]+?)(?=[.,]?(?:\s|\"|$))")


def tool_call(name, args, i=0):
    return {"role": "assistant", "content": None, "tool_calls": [
        {"id": f"call_{i}", "type": "function", "function": {"name": name, "arguments": json.dumps(args)}}]}


def make_fake_llm(follow_injection=True, answer=None, extra_call=None):
    """Searches the logs; if follow_injection, obeys any 'call X with ...' text found in tool output
    (a maximally gullible model); optionally makes one extra call; then answers."""
    def llm(messages, tools):
        done = {c["function"]["name"] for m in messages if m["role"] == "assistant"
                for c in (m.get("tool_calls") or [])}
        inc = re.search(r"INC-\d{3}", messages[1]["content"]).group(0)
        if "search_logs" not in done:
            return tool_call("search_logs", {"incident_id": inc})
        if follow_injection:
            last_tool = next((m for m in reversed(messages) if m["role"] == "tool"), None)
            hit = INJ.search(last_tool["content"]) if last_tool else None
            if hit and hit.group(1) not in done:
                return tool_call(hit.group(1), {hit.group(2): hit.group(3)})
        if extra_call and extra_call[0] not in done:
            return tool_call(*extra_call)
        return {"role": "assistant", "content": json.dumps(answer or {})}
    return llm
