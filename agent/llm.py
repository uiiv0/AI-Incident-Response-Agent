"""LLM client (OpenAI-compatible: Ollama or OpenRouter) with an on-disk cache.
The cache makes re-runs free, so a rate-limited eval can simply be re-run to resume."""
import hashlib
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()
CACHE_DIR = Path(__file__).resolve().parents[1] / ".cache" / "llm"


def make_llm(trial: int = 0, use_cache: bool = True, temperature: float = 0.2):
    client = OpenAI(base_url=os.getenv("LLM_BASE_URL", "http://localhost:11434/v1"),
                    api_key=os.getenv("LLM_API_KEY", "ollama"), timeout=300)
    model = os.getenv("LLM_MODEL", "qwen3:8b")
    CACHE_DIR.mkdir(parents=True, exist_ok=True)

    def chat(messages, tools):
        key = hashlib.sha256(json.dumps(
            {"model": model, "trial": trial, "messages": messages, "tools": tools},
            sort_keys=True, ensure_ascii=False).encode()).hexdigest()
        path = CACHE_DIR / f"{key}.json"
        if use_cache and path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
        for attempt in range(4):              # simple backoff for rate limits
            try:
                r = client.chat.completions.create(model=model, messages=messages, tools=tools,
                                                   temperature=temperature)
                break
            except Exception as e:
                if attempt == 3:
                    raise
                wait = 5 * 2 ** attempt
                print(f"  LLM error ({type(e).__name__}); retry in {wait}s")
                time.sleep(wait)
        m = r.choices[0].message
        out = {"role": "assistant", "content": m.content or ("" if not m.tool_calls else None)}
        if m.tool_calls:
            out["tool_calls"] = [{"id": tc.id or f"call_{i}", "type": "function",
                                  "function": {"name": tc.function.name,
                                               "arguments": tc.function.arguments}}
                                 for i, tc in enumerate(m.tool_calls)]
        path.write_text(json.dumps(out, ensure_ascii=False), encoding="utf-8")
        return out

    return chat
