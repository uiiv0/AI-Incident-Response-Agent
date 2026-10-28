"""Tools: local (mock) tools + MCP toolbox. Dangerous tools are MOCKS: they only record."""
import json
import sys
from contextlib import asynccontextmanager
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from mcp_server.logs_server import search_logs_impl

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SERVER = ROOT / "mcp_server" / "logs_server.py"

# gated tool -> name of its target argument
GATED = {"isolate_host": "host", "disable_account": "user", "block_ip": "ip"}


def _fn(name, description, props, required):
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": props, "required": required}}}


S = {"type": "string"}
LOCAL_SCHEMAS = [
    _fn("lookup_ip_reputation", "Look up the reputation of an IP address.", {"ip": S}, ["ip"]),
    _fn("get_asset_info", "Get info about a host or a user (role, critical, authorized_scanner...).",
        {"name": S}, ["name"]),
    _fn("create_ticket", "Create an incident ticket.", {"summary": S, "severity": S}, ["summary", "severity"]),
    _fn("isolate_host", "Isolate a host from the network. REQUIRES human approval.", {"host": S}, ["host"]),
    _fn("disable_account", "Disable a user account. REQUIRES human approval.", {"user": S}, ["user"]),
    _fn("block_ip", "Block an IP address at the firewall. REQUIRES human approval.", {"ip": S}, ["ip"]),
]
SEARCH_LOGS_SCHEMA = _fn(
    "search_logs", "Search the log file of an incident (id like INC-001). Optional keyword filter.",
    {"incident_id": S, "keyword": S}, ["incident_id"])


class LocalTools:
    def __init__(self, data_dir: Path = DATA):
        self.assets = json.loads((data_dir / "assets.json").read_text(encoding="utf-8"))
        self.reputation = json.loads((data_dir / "ip_reputation.json").read_text(encoding="utf-8"))
        self.protected = self.assets["protected"]
        self.executed = []   # (tool, target) of dangerous MOCK actions that really "ran"
        self.tickets = []

    def call(self, name, args):
        if name == "lookup_ip_reputation":
            ip = args["ip"]
            return json.dumps({"ip": ip, **self.reputation.get(ip, {"reputation": "unknown"})})
        if name == "get_asset_info":
            key = args["name"]
            info = self.assets["hosts"].get(key) or self.assets["users"].get(key)
            return json.dumps({"name": key, **info} if info else {"name": key, "found": False})
        if name == "create_ticket":
            self.tickets.append(args)
            return f"TCK-{len(self.tickets):03d} created"
        if name in GATED:
            target = args[GATED[name]]
            self.executed.append((name, str(target)))
            return f"[MOCK] {name}({target}) executed"
        raise ValueError(f"unknown local tool {name}")


class Toolbox:
    """One place the loop calls tools through (MCP tools + local tools)."""

    def __init__(self, local: LocalTools, session=None, mcp_tools=()):
        self.local, self.session = local, session
        self.mcp_names = {t.name for t in mcp_tools}
        if session is not None:
            mcp_schemas = [{"type": "function", "function": {
                "name": t.name, "description": t.description or "", "parameters": t.inputSchema}}
                for t in mcp_tools]
        else:
            mcp_schemas = [SEARCH_LOGS_SCHEMA]   # fallback without MCP (fast unit tests)
        self.schemas = mcp_schemas + LOCAL_SCHEMAS

    async def call(self, name, args):
        if self.session is not None and name in self.mcp_names:
            res = await self.session.call_tool(name, args)
            text = "\n".join(c.text for c in res.content if getattr(c, "type", "") == "text")
            return text or "(empty)"
        if name == "search_logs":
            return search_logs_impl(**args)
        return self.local.call(name, args)


@asynccontextmanager
async def open_toolbox(use_mcp: bool = True):
    local = LocalTools()
    if not use_mcp:
        yield Toolbox(local)
        return
    params = StdioServerParameters(command=sys.executable, args=[str(SERVER)])
    async with stdio_client(params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tools = (await session.list_tools()).tools
            yield Toolbox(local, session, tools)
