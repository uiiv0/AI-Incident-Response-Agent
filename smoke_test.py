"""Step 1 check: does your model reach the server AND call a tool correctly?
   uv run python smoke_test.py"""
from agent.llm import make_llm
from agent.tools import LOCAL_SCHEMAS

tools = [s for s in LOCAL_SCHEMAS if s["function"]["name"] == "get_asset_info"]
msg = make_llm(use_cache=False)([{"role": "user", "content": "Use the tool to get info about host dc01."}], tools)
calls = msg.get("tool_calls") or []
if calls and calls[0]["function"]["name"] == "get_asset_info":
    print("PASS: model called the tool ->", calls[0]["function"]["arguments"])
else:
    print("FAIL: model did not call the tool. Reply was:", (msg.get("content") or "")[:200])
    print("-> Try a bigger model that supports tools (check the 'Tools' filter on ollama.com/search).")
