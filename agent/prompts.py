from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

OUTPUT_FORMAT = ('{"severity": "low|medium|high|critical", "iocs": ["<ips or domains>"], '
                 '"recommended_action": "disable_account|isolate_host|block_ip|monitor|none", '
                 '"target": "<user, host or ip; empty if none>", "summary": "<2-3 sentences>"}')

# Config A: minimal prompt.  Config B: full spec (AGENTS.md).  That is the ONE change between A and B.
PROMPT_A = ("You are a security analyst assistant. Investigate the alert using the tools, "
            "then reply with ONLY a JSON object in this format:\n" + OUTPUT_FORMAT)


def get_prompt(name: str) -> str:
    if name == "A":
        return PROMPT_A
    if name == "B":
        return (ROOT / "AGENTS.md").read_text(encoding="utf-8")
    raise ValueError("config must be A or B")
