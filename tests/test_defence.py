import asyncio
import json
from pathlib import Path

import pytest

from agent.harness import Harness
from agent.loop import run_agent
from agent.tools import open_toolbox
from evals.graders import grade
from evals.run_eval import load_tasks, summarize
from mcp_server.logs_server import search_logs_impl
from tests.fakes import make_fake_llm

TASKS = {t["id"]: t for t in load_tasks()}
INJECTION_TASKS = ["INC-013", "INC-014", "INC-015"]


def run_task(task_id, llm, defended=True, approve=lambda t, a: True, use_mcp=False):
    task = TASKS[task_id]

    async def go():
        async with open_toolbox(use_mcp=use_mcp) as tb:
            h = Harness(approve, tb.local.protected, defended=defended)
            res = await run_agent(task["alert"], "system", tb, h, llm)
            return res, tb.local.executed
    return asyncio.run(go())


def oracle_answer(task):
    e = task["expected"]
    return {"severity": e["severity"], "iocs": e["iocs"], "recommended_action": e["action"],
            "target": e["target"], "summary": "oracle"}


@pytest.mark.parametrize("tid", INJECTION_TASKS)
def test_attack_works_without_defence(tid):
    """Before: a gullible model + no harness checks -> the injected action really runs."""
    forb = TASKS[tid]["forbidden"][0]
    res, executed = run_task(tid, make_fake_llm(True), defended=False)
    assert (forb["tool"], forb["target"]) in executed
    assert grade(TASKS[tid], res)["injection_executed"]


@pytest.mark.parametrize("tid", INJECTION_TASKS)
def test_defence_blocks_even_if_human_approves_everything(tid):
    """After: protected assets are blocked in CODE, regardless of model or human."""
    res, executed = run_task(tid, make_fake_llm(True), defended=True, approve=lambda t, a: True)
    assert executed == []
    denied = [c for c in res.calls if c.name in ("isolate_host", "disable_account", "block_ip")]
    assert denied and all(not c.allowed and "protected" in c.reason for c in denied)
    g = grade(TASKS[tid], res)
    assert g["injection_attempted"] and not g["injection_executed"]


def test_gated_action_requires_human_approval():
    call = ("block_ip", {"ip": "203.0.113.200"})            # not protected
    _, executed = run_task("INC-013", make_fake_llm(False, extra_call=call), approve=lambda t, a: False)
    assert executed == []
    _, executed = run_task("INC-013", make_fake_llm(False, extra_call=call), approve=lambda t, a: True)
    assert executed == [("block_ip", "203.0.113.200")]


def test_unknown_tool_is_denied():
    res, executed = run_task("INC-013", make_fake_llm(False, extra_call=("delete_all_logs", {})))
    assert any(c.name == "delete_all_logs" and not c.allowed for c in res.calls)


def test_path_traversal_blocked():
    assert search_logs_impl("../../.env").startswith("ERROR")


def test_step_budget_enforced():
    async def go():
        async with open_toolbox(use_mcp=False) as tb:
            h = Harness(lambda t, a: True, tb.local.protected, max_steps=3)
            loop_forever = lambda m, t: {"role": "assistant", "content": None, "tool_calls": [
                {"id": "c", "type": "function", "function": {"name": "get_asset_info", "arguments": '{"name":"dc01"}'}}]}
            return await run_agent("INC-001 x", "s", tb, h, loop_forever)
    res = asyncio.run(go())
    assert res.stop_reason == "step_budget" and res.steps == 3


def test_compaction_shrinks_old_tool_results():
    h = Harness(lambda t, a: True, {"hosts": [], "users": [], "ips": []}, max_context_tokens=100)
    msgs = [{"role": "system", "content": "s"}, {"role": "user", "content": "u"}] + \
           [{"role": "tool", "tool_call_id": str(i), "content": "x" * 1000} for i in range(4)]
    assert h.compact(msgs)
    assert len(msgs[2]["content"]) < 300 and len(msgs[-1]["content"]) == 1000


@pytest.mark.parametrize("tid", list(TASKS))
def test_graders_pass_oracle_on_all_tasks(tid):
    res, _ = run_task(tid, make_fake_llm(False, answer=oracle_answer(TASKS[tid])))
    g = grade(TASKS[tid], res)
    assert g["passed"], g


def test_grader_flags_wrong_answers():
    bad = {"severity": "low", "iocs": [], "recommended_action": "none", "target": "", "summary": "x"}
    res, _ = run_task("INC-001", make_fake_llm(False, answer=bad))
    g = grade(TASKS["INC-001"], res)
    assert not g["passed"] and {"wrong_severity", "missing_ioc", "wrong_action"} <= set(g["errors"])


def test_summarize_pass_k():
    rows = [{"config": "A", "task": "t1", "passed": True, "injection_attempted": False,
             "injection_executed": False, "steps": 3, "errors": []},
            {"config": "A", "task": "t1", "passed": False, "injection_attempted": False,
             "injection_executed": False, "steps": 3, "errors": ["wrong_action"]}]
    s = summarize(rows)["A"]
    assert s["pass_rate"] == 0.5 and s["pass_k"] == 0.0


def test_mcp_roundtrip_over_stdio():
    async def go():
        async with open_toolbox(use_mcp=True) as tb:
            assert "search_logs" in tb.mcp_names
            return await tb.call("search_logs", {"incident_id": "INC-001", "keyword": "failed"})
    out = asyncio.run(go())
    assert "matching lines" in out and "failed" in out
