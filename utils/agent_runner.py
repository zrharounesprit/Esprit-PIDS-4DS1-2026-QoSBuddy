"""
agent_runner.py — LangChain + Kimi K2.6 agent for QoSBuddy simulation.

Uses a manual tool-calling loop (langchain_core only) so it works with
any langchain version that has bind_tools / ToolMessage support.
No dependency on AgentExecutor or create_tool_calling_agent.

The LLM is Moonshot's Kimi K2.6 (kimi-k2-0711), accessed via the
OpenAI-compatible API at https://api.moonshot.ai/v1.
"""

import os
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, ToolMessage, AIMessage
from langchain_core.tools import tool

from utils.mcp_client import get_mcp_tools
from utils.agent import extract_profile


# ── Module-level state shared between the @tool and run_agent ─────────────────
_csv_bytes_list: list = []
_agent_names: list    = []


@tool
def run_network_simulation(
    injection_prompt: Optional[str] = None,
    capacity_gb: float = 10.0,
) -> str:
    """
    Run a network simulation for the uploaded users and optionally add a new one.

    Call this tool when the user asks to:
    - Simulate a network or analyse its capacity
    - Test what happens if a new user joins the network
    - Check if the network can handle an additional user type

    Args:
        injection_prompt: Natural language description of a new user to add,
                          e.g. 'a gamer who plays at night' or 'a streamer'.
                          Leave empty or None if no new user is being added.
        capacity_gb: Total network capacity in GB per hour. Default is 10.

    Returns:
        A plain text summary of simulation results including peak capacity usage.
    """
    if not injection_prompt or not injection_prompt.strip():
        injection_prompt = None

    result = _execute_tool(
        injection_prompt=injection_prompt,
        capacity_gb=float(capacity_gb),
        csv_bytes_list=_csv_bytes_list,
        agent_names=_agent_names,
    )

    run_network_simulation._last_result = result
    return _build_result_summary(result)


run_network_simulation._last_result = None


def _execute_tool(
    injection_prompt: Optional[str],
    capacity_gb: float,
    csv_bytes_list: list,
    agent_names: list,
) -> dict:
    import requests
    import io
    import pandas as pd

    # Guard: agent-based simulation requires CSV files
    if not injection_prompt and not csv_bytes_list:
        return {
            "error": (
                "No CSV files were uploaded. To simulate existing users, upload their "
                "traffic CSV files on the Simulation page. "
                "To add a new persona without existing users, describe the new user "
                "(e.g. 'a gamer who plays at night') and I will use the persona tool."
            )
        }

    profiles = []
    for csv_bytes, name in zip(csv_bytes_list, agent_names):
        df = pd.read_csv(io.BytesIO(csv_bytes))
        profiles.append(extract_profile(df))

    if injection_prompt:
        response = requests.post(
            "http://127.0.0.1:8005/api/simulate_persona",
            json={
                "profiles": profiles,
                "prompt": injection_prompt,
                "capacity": capacity_gb,
                "simulations": 1,
            },
            timeout=60,
        )
        result = response.json()
        return {
            "agents": [{"agent_name": n, "mean_bytes": 0} for n in agent_names],
            "network_before": result.get("before", []),
            "network_after":  result.get("after",  []),
            "injected_agent": {"prompt": injection_prompt},
            "summary": {
                "num_agents":      len(agent_names),
                "capacity_gb":     capacity_gb,
                "peak_before_pct": max((r.get("load", 0) * 100 for r in result.get("before", [])), default=0),
                "peak_after_pct":  max((r.get("load", 0) * 100 for r in result.get("after",  [])), default=0),
                "exceeded_before": [],
                "exceeded_after":  [],
                "injection_prompt": injection_prompt,
            },
        }
    else:
        response = requests.post(
            "http://127.0.0.1:8005/api/simulate_agents",
            files=[("files", (n + ".csv", d, "text/csv")) for n, d in zip(agent_names, csv_bytes_list)],
            data={"capacity": capacity_gb, "simulations": 1},
            timeout=60,
        )
        result = response.json()
        traffic = result.get("traffic", [])
        return {
            "agents":         [{"agent_name": n, "mean_bytes": 0} for n in agent_names],
            "network_before": traffic,
            "network_after":  None,
            "injected_agent": None,
            "summary": {
                "num_agents":      len(agent_names),
                "capacity_gb":     capacity_gb,
                "peak_before_pct": max((r.get("load", 0) * 100 for r in traffic), default=0),
                "peak_after_pct":  None,
                "exceeded_before": [],
                "exceeded_after":  [],
                "injection_prompt": None,
            },
        }


def _build_result_summary(result: dict) -> str:
    if not result or "error" in result:
        return f"Simulation failed: {result.get('error', 'unknown error')}"

    s        = result.get("summary", {})
    agents   = result.get("agents", [])
    injected = result.get("injected_agent")

    lines = [
        f"Simulation ran for {s.get('num_agents', 0)} user(s) over 24 hours.",
        f"Network capacity: {s.get('capacity_gb', 10)} GB/hour.",
        f"Peak usage before injection: {s.get('peak_before_pct', 0):.1f}% of capacity.",
    ]
    for agent in agents:
        gb = agent.get("mean_bytes", 0) / (1024 ** 3)
        lines.append(f"User '{agent['agent_name']}' averages {gb:.2f} GB/hour.")

    if injected:
        lines.append(f"New user injected: '{injected.get('prompt', '')}'")
        peak_after = s.get("peak_after_pct")
        if peak_after is not None:
            lines.append(f"Peak usage after injection: {peak_after:.1f}%.")
        if s.get("exceeded_after"):
            lines.append(f"CAPACITY EXCEEDED at: {', '.join(s['exceeded_after'])}")
        else:
            lines.append("Capacity was NOT exceeded after injection.")

    if s.get("exceeded_before"):
        lines.append(f"Already exceeded before injection: {', '.join(s['exceeded_before'])}")

    return "\n".join(lines)


# ── Agent entry point ─────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are QoSBuddy, an intelligent network analysis and simulation agent.
Your job is to help network engineers understand network capacity, diagnose anomalies,
and classify root causes of unusual traffic behaviour.

You have THREE tools — choose the most appropriate one:

1. run_network_simulation
   Use when the user wants to:
   - Simulate the network with the uploaded user CSVs
   - Add a new user (gamer, streamer, etc.) and check capacity impact
   - Run a what-if scenario
   Rules:
   - If the user describes a new person → set injection_prompt to that description.
   - If the user mentions a specific capacity → use as capacity_gb (default 10).
   - If no new user → leave injection_prompt empty.
   - IMPORTANT: if no CSV files have been uploaded AND no persona is described,
     do NOT call this tool. Instead, explain that CSV files are needed and suggest
     the user upload them on the Simulation page, or describe a persona to simulate.

2. check_network_health
   Use when the user asks about:
   - System status, health check, what models are loaded
   - What cause types can be classified
   - Whether the RCA service is online

3. classify_ip_root_cause
   Use when the user asks about:
   - A specific IP address or device
   - Root cause of a network anomaly or unusual traffic
   - Diagnosing why a particular IP is misbehaving
   Provide reasonable defaults for any unspecified traffic metrics.

After any tool call, explain the results clearly in plain English.
If a tool returns an error about a service being offline, report that clearly to the user.
"""


def run_agent(
    user_prompt: str,
    csv_bytes_list: list,
    agent_names: list,
    gemini_api_key: str = "",
) -> dict:
    """
    Run the Kimi K2.6 tool-calling agent.

    Uses a manual tool-calling loop (bind_tools + ToolMessage) so it works
    with any langchain version — no AgentExecutor required.

    Returns:
        agent_called_tool  — bool
        tool_args          — dict
        simulation_result  — raw simulation output dict or None
        summary            — plain English explanation
        agent_thoughts     — [] (kept for UI compatibility)
    """

    global _csv_bytes_list, _agent_names
    _csv_bytes_list = csv_bytes_list
    _agent_names    = agent_names
    run_network_simulation._last_result = None

    files_context = (
        f"The user has uploaded {len(agent_names)} CSV file(s): {', '.join(agent_names)}."
        if agent_names
        else "No CSV files have been uploaded yet."
    )

    moonshot_key = os.getenv("MOONSHOT_API_KEY", "")
    llm = ChatOpenAI(
        model="kimi-k2-0711",
        api_key=moonshot_key,
        base_url="https://api.moonshot.ai/v1",
        temperature=0.6,
        max_tokens=1024,
        model_kwargs={"thinking": {"type": "disabled"}},
    )

    all_tools   = [run_network_simulation] + get_mcp_tools()
    tool_map    = {t.name: t for t in all_tools}
    llm_w_tools = llm.bind_tools(all_tools)

    messages: list = [
        SystemMessage(content=f"{_SYSTEM_PROMPT}\n\n{files_context}"),
        HumanMessage(content=user_prompt),
    ]

    try:
        for _ in range(6):          # max 6 iterations
            response = llm_w_tools.invoke(messages)
            messages.append(response)

            # No tool calls → agent is done
            if not getattr(response, "tool_calls", None):
                break

            # Execute each tool call and append the result
            for tc in response.tool_calls:
                tool_fn = tool_map.get(tc["name"])
                if tool_fn is None:
                    tool_output = f"Unknown tool: {tc['name']}"
                else:
                    try:
                        tool_output = tool_fn.invoke(tc["args"])
                    except Exception as e:
                        tool_output = f"Tool error: {e}"

                messages.append(
                    ToolMessage(content=str(tool_output), tool_call_id=tc["id"])
                )

        simulation_result = run_network_simulation._last_result
        agent_called_tool = simulation_result is not None

        inj         = simulation_result.get("injected_agent") if simulation_result else None
        sim_summary = simulation_result.get("summary", {})    if simulation_result else {}
        final_text  = getattr(response, "content", "") or "No summary available."

        return {
            "agent_called_tool": agent_called_tool,
            "tool_args": {
                "injection_prompt": inj.get("prompt") if inj else None,
                "capacity_gb":      sim_summary.get("capacity_gb", 10),
            },
            "simulation_result": simulation_result,
            "summary":           final_text,
            "agent_thoughts":    [],
        }

    except Exception as e:
        return {
            "agent_called_tool": False,
            "tool_args":         {},
            "simulation_result": None,
            "summary":           f"Agent error: {e}",
            "agent_thoughts":    [],
        }
