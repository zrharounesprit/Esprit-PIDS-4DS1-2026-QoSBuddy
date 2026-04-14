from typing import Optional

from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_classic.agents import create_tool_calling_agent, AgentExecutor
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.tools import tool

from mcp_client import get_mcp_tools

from agent import extract_profile



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
        injection_prompt = injection_prompt,
        capacity_gb      = float(capacity_gb),
        csv_bytes_list   = _csv_bytes_list,
        agent_names      = _agent_names,
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
    """
    Calls your friend's simulation API.
    Assumes the FastAPI server is running on port 8000.
    """
    import requests
    import io
    import pandas as pd
    
    agents_data = []
    profiles = []
    
    for csv_bytes, name in zip(csv_bytes_list, agent_names):
        df = pd.read_csv(io.BytesIO(csv_bytes))
        profile = extract_profile(df)
        profiles.append(profile)
    
    if injection_prompt:
        response = requests.post(
            "http://127.0.0.1:8000/simulate_persona",
            json={
                "profiles": profiles,
                "prompt": injection_prompt,
                "capacity": capacity_gb,
                "simulations": 1
            },
            timeout=300
        )
        result = response.json()
        
        # Convert to format your agent expects
        return {
            "agents": [{"agent_name": name, "mean_bytes": 0} for name in agent_names],
            "network_before": result.get("before", []),
            "network_after": result.get("after", []),
            "injected_agent": {"prompt": injection_prompt, "prompt": injection_prompt},
            "summary": {
                "num_agents": len(agent_names),
                "capacity_gb": capacity_gb,
                "peak_before_pct": max([r.get("load", 0) * 100 for r in result.get("before", [])]) if result.get("before") else 0,
                "peak_after_pct": max([r.get("load", 0) * 100 for r in result.get("after", [])]) if result.get("after") else 0,
                "exceeded_before": [],
                "exceeded_after": [],
                "injection_prompt": injection_prompt
            }
        }
    else:
        response = requests.post(
            "http://127.0.0.1:8000/simulate_agents",
            files=[("files", (name + ".csv", data, "text/csv")) 
                   for name, data in zip(agent_names, csv_bytes_list)],
            data={"capacity": capacity_gb, "simulations": 1},
            timeout=300
        )
        result = response.json()
        
        return {
            "agents": [{"agent_name": name, "mean_bytes": 0} for name in agent_names],
            "network_before": result.get("traffic", []),
            "network_after": None,
            "injected_agent": None,
            "summary": {
                "num_agents": len(agent_names),
                "capacity_gb": capacity_gb,
                "peak_before_pct": max([r.get("load", 0) * 100 for r in result.get("traffic", [])]) if result.get("traffic") else 0,
                "peak_after_pct": None,
                "exceeded_before": [],
                "exceeded_after": [],
                "injection_prompt": None
            }
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
        lines.append(
            f"New user injected from {injected.get('injection_hour', 0):02d}:00 "
            f"({injected.get('estimated_gb', 0):.2f} GB/hour estimated) "
            f"based on: '{injected.get('prompt', '')}'"
        )
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


def run_agent(
    user_prompt: str,
    csv_bytes_list: list,
    agent_names: list,
    gemini_api_key: str,
) -> dict:
    """
    Run the LangChain + Gemini agent with the user's natural language prompt.

    Returns a dict with:
        agent_called_tool  — did the agent decide to run the simulation?
        tool_args          — parameters the agent chose
        simulation_result  — the raw simulation output dict
        summary            — plain English explanation from the agent
        agent_thoughts     — empty list (kept for UI compatibility)
    """

    global _csv_bytes_list, _agent_names
    _csv_bytes_list = csv_bytes_list
    _agent_names    = agent_names
    run_network_simulation._last_result = None

    llm = ChatGoogleGenerativeAI(
        model          = "models/gemini-2.5-flash-lite",
        google_api_key = gemini_api_key,
        temperature    = 0.3,
    )

    files_context = (
        f"The user has uploaded {len(agent_names)} CSV file(s) representing "
        f"network users: {', '.join(agent_names)}."
        if agent_names
        else "No CSV files have been uploaded yet."
    )

    prompt = ChatPromptTemplate.from_messages([
        (
            "system",
            f"""You are QoSBuddy, an intelligent network simulation agent.
Your job is to help network engineers understand how users affect network capacity.

{files_context}

You have access to these tools:
- run_network_simulation: simulate the network with uploaded users, optionally adding a new one
- check_network_health: check the RCA system status (call if user asks about system status)
- classify_ip_root_cause: get root cause analysis for a specific IP (call if user asks about a specific IP)

When asked to simulate a network, analyse capacity, or test a new user joining,
call run_network_simulation.

Rules for parameter extraction:
- If the user describes a new person (a gamer, a streamer, etc.) → use as injection_prompt
- If the user mentions a specific capacity (5GB, 15GB, etc.) → use as capacity_gb
- If no capacity is mentioned → default to 10
- If no new user is mentioned → leave injection_prompt empty

After any tool runs, explain the results clearly in plain English.""",
        ),
        ("human", "{input}"),
        MessagesPlaceholder(variable_name="agent_scratchpad"),
    ])

    
    all_tools = [run_network_simulation] + get_mcp_tools()

    agent = create_tool_calling_agent(
        llm    = llm,
        tools  = all_tools,
        prompt = prompt,
    )

    executor = AgentExecutor(
        agent                = agent,
        tools                = all_tools,
        verbose              = True,   # shows reasoning steps in terminal
        handle_parsing_errors= True,
        max_iterations       = 5,
    )

    
    try:
        result            = executor.invoke({"input": user_prompt})
        simulation_result = run_network_simulation._last_result
        agent_called_tool = simulation_result is not None

        inj = simulation_result.get("injected_agent") if simulation_result else None
        sim_summary = simulation_result.get("summary", {}) if simulation_result else {}

        return {
            "agent_called_tool": agent_called_tool,
            "tool_args": {
                "injection_prompt": inj.get("prompt") if inj else None,
                "capacity_gb"     : sim_summary.get("capacity_gb", 10),
            },
            "simulation_result": simulation_result,
            "summary"          : result.get("output", "No summary available."),
            "agent_thoughts"   : [],
        }

    except Exception as e:
        return {
            "agent_called_tool": False,
            "tool_args"        : {},
            "simulation_result": None,
            "summary"          : f"Agent error: {str(e)}",
            "agent_thoughts"   : [],
        }
