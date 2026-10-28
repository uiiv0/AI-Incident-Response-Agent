"""MCP server: read-only log search for the IR agent (stdio transport)."""
import re
from pathlib import Path

from mcp.server.fastmcp import FastMCP

LOGS_DIR = Path(__file__).resolve().parents[1] / "data" / "logs"
ID_RE = re.compile(r"^INC-\d{3}$")   # also blocks path traversal like ../../.env
MAX_LINES = 25


def search_logs_impl(incident_id: str, keyword: str = "") -> str:
    if not ID_RE.match(incident_id or ""):
        return "ERROR: incident_id must look like INC-001"
    path = LOGS_DIR / f"{incident_id}.log"
    if not path.exists():
        return f"ERROR: no logs for {incident_id}"
    kw = (keyword or "").lower()
    lines = [l for l in path.read_text(encoding="utf-8").splitlines() if kw in l.lower()]
    note = ""
    if len(lines) > MAX_LINES:
        note = f"\n[{len(lines) - MAX_LINES} more lines not shown; narrow with a keyword]"
    return f"{len(lines)} matching lines\n" + "\n".join(lines[:MAX_LINES]) + note


mcp = FastMCP("ir-logs", log_level="WARNING")


@mcp.tool()
def search_logs(incident_id: str, keyword: str = "") -> str:
    """Search the log file of an incident (id like INC-001). Returns up to 25 matching
    lines. Optional keyword filters lines (e.g. 'failed', 'success', an IP or a username)."""
    return search_logs_impl(incident_id, keyword)


if __name__ == "__main__":
    mcp.run()
