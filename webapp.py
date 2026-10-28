"""Small browser UI for the IR Agent. All containment actions remain mock-only and approval-gated."""
import asyncio
import json
import threading
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agent.harness import Harness, Trace
from agent.llm import make_llm
from agent.loop import run_agent
from agent.prompts import get_prompt
from agent.tools import ROOT, open_toolbox

app = FastAPI(title="IR Agent Web UI")
WEB_DIR = ROOT / "web"
app.mount("/static", StaticFiles(directory=WEB_DIR), name="static")

lock = threading.Lock()
runs: dict[str, dict[str, Any]] = {}


def load_tasks():
    tasks = []
    for line in (ROOT / "evals" / "tasks.jsonl").read_text(encoding="utf-8").splitlines():
        if line.strip():
            t = json.loads(line)
            tasks.append({"id": t["id"], "category": t.get("category", "unknown"), "alert": t["alert"]})
    return tasks


TASKS = {t["id"]: t for t in load_tasks()}


class StartRequest(BaseModel):
    incident_id: str
    prompt: str = "B"


class ApprovalRequest(BaseModel):
    approved: bool


@app.get("/")
def index():
    return FileResponse(WEB_DIR / "index.html")


@app.get("/api/incidents")
def incidents():
    return list(TASKS.values())


@app.post("/api/runs")
def start_run(req: StartRequest):
    if req.incident_id not in TASKS:
        raise HTTPException(404, "Unknown incident ID")
    run_id = uuid.uuid4().hex[:12]
    state: dict[str, Any] = {
        "id": run_id, "incident_id": req.incident_id, "status": "running",
        "alert": TASKS[req.incident_id]["alert"], "events": [], "pending_approval": None,
        "result": None, "error": None,
    }
    with lock:
        runs[run_id] = state

    def approve_fn(tool, args):
        approval_id = uuid.uuid4().hex[:10]
        event = threading.Event()
        pending = {"id": approval_id, "tool": tool, "args": args, "approved": None, "_event": event}
        with lock:
            state["pending_approval"] = pending
            state["status"] = "awaiting_approval"
            state["events"].append({"type": "approval_requested", "tool": tool, "args": args})
        # Wait for a user decision from the browser. Timeout fails closed.
        decided = event.wait(timeout=300)
        with lock:
            approved = bool(pending["approved"]) if decided else False
            state["pending_approval"] = None
            state["status"] = "running"
            state["events"].append({"type": "approval_decision", "tool": tool, "args": args, "approved": approved})
        return approved

    def worker():
        try:
            async def execute():
                async with open_toolbox(use_mcp=True) as tb:
                    trace = Trace(ROOT / "traces" / f"web-{run_id}.jsonl", echo=False)
                    harness = Harness(approve_fn, tb.local.protected, defended=True, trace=trace)
                    result = await run_agent(TASKS[req.incident_id]["alert"], get_prompt(req.prompt), tb, harness, make_llm())
                    return result, tb.local.executed, tb.tickets, trace.events
            result, executed, tickets, trace_events = asyncio.run(execute())
            payload = {
                "final_text": result.final_text,
                "final_json": result.final_json,
                "steps": result.steps,
                "stop_reason": result.stop_reason,
                "calls": [
                    {"name": c.name, "args": c.args, "allowed": c.allowed, "reason": c.reason,
                     "executed": c.executed, "result_preview": c.result_preview}
                    for c in result.calls
                ],
                "mock_actions": [{"tool": name, "target": target} for name, target in executed],
                "tickets": tickets,
                "trace": trace_events,
            }
            with lock:
                state["result"] = payload
                state["status"] = "completed"
        except Exception as exc:
            with lock:
                state["error"] = f"{type(exc).__name__}: {exc}"
                state["status"] = "failed"
        finally:
            with lock:
                pending = state.get("pending_approval")
                if pending:
                    pending["approved"] = False
                    pending["_event"].set()

    threading.Thread(target=worker, daemon=True).start()
    return {"run_id": run_id, "status": "running"}


@app.get("/api/runs/{run_id}")
def get_run(run_id: str):
    with lock:
        state = runs.get(run_id)
        if not state:
            raise HTTPException(404, "Run not found")
        pending = state.get("pending_approval")
        return {
            "id": state["id"], "incident_id": state["incident_id"], "status": state["status"],
            "alert": state["alert"], "events": state["events"],
            "pending_approval": ({"id": pending["id"], "tool": pending["tool"], "args": pending["args"]} if pending else None),
            "result": state["result"], "error": state["error"],
        }


@app.post("/api/runs/{run_id}/approval/{approval_id}")
def decide_approval(run_id: str, approval_id: str, req: ApprovalRequest):
    with lock:
        state = runs.get(run_id)
        if not state:
            raise HTTPException(404, "Run not found")
        pending = state.get("pending_approval")
        if not pending or pending["id"] != approval_id:
            raise HTTPException(409, "No matching pending approval")
        pending["approved"] = req.approved
        pending["_event"].set()
    return {"ok": True, "approved": req.approved}
