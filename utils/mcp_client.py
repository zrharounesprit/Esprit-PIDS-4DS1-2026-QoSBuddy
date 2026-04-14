import os
import requests
from typing import Optional
from langchain_core.tools import tool


MCP_SERVER_URL = os.getenv("MCP_SERVER_URL", "http://127.0.0.1:8000/mcp")


def discover_mcp_tools() -> list:
    try:
        response = requests.post(
            MCP_SERVER_URL,
            json={"jsonrpc": "2.0", "method": "tools/list", "id": 1},
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'  # ← ADD THIS
            },
            timeout=5,
        )
        if response.status_code == 200:
            data = response.json()
            tools = data.get("result", {}).get("tools", [])
            print(f"MCP: discovered {len(tools)} tool(s) from {MCP_SERVER_URL}")
            return tools
        else:
            print(f"MCP: server returned {response.status_code}")
            return []
    except Exception as e:
        print(f"MCP: could not connect to {MCP_SERVER_URL} — {e}")
        return []



def call_mcp_tool(tool_name: str, arguments: dict) -> str:
    try:
        response = requests.post(
            MCP_SERVER_URL,
            json={
                "jsonrpc": "2.0",
                "method": "tools/call",
                "id": 1,
                "params": {
                    "name": tool_name,
                    "arguments": arguments,
                },
            },
            headers={
                'Content-Type': 'application/json',
                'Accept': 'application/json, text/event-stream'  # ← ADD THIS
            },
            timeout=30,
        )
        if response.status_code == 200:
            result = response.json()
            content = result.get("result", {}).get("content", [])
            return " ".join(c.get("text", "") for c in content if c.get("type") == "text")
        else:
            return f"MCP tool call failed: HTTP {response.status_code}"
    except Exception as e:
        return f"MCP tool call error: {str(e)}"



@tool
def check_network_health() -> str:
    """
    Check the current status of the QoSBuddy RCA system via MCP.
    Returns information about the loaded model, number of IP profiles,
    and which cause types the system can classify.
    Call this when the user asks about system status or what the system knows.
    """
    return call_mcp_tool("health", {})


@tool
def classify_ip_root_cause(
    id_ip: int,
    n_bytes: float = 248592,
    n_packets: float = 1289,
    n_flows: float = 82,
    tcp_udp_ratio_packets: float = 0.94,
    dir_ratio_packets: float = 0.52,
    sum_n_dest_ip: float = 68,
    sum_n_dest_ports: float = 70,
) -> str:
    """
    Classify the root cause of a network issue for a specific IP address via MCP.
    Returns a human-readable RCA report explaining why this IP is behaving unusually.
    Call this when the user asks about a specific IP address or wants to know
    the root cause of a network problem for a particular device.

    Args:
        id_ip: The IP address identifier from the dataset
        n_bytes: Total bytes transmitted in the hour
        n_packets: Total packets transmitted
        n_flows: Number of distinct network flows
        tcp_udp_ratio_packets: Ratio of TCP to UDP (1=all TCP, 0=all UDP)
        dir_ratio_packets: Direction ratio (1=all outgoing, 0=all incoming)
        sum_n_dest_ip: Number of unique destination IPs contacted
        sum_n_dest_ports: Number of unique destination ports contacted
    """
    return call_mcp_tool("rca", {
        "id_ip"                : id_ip,
        "n_bytes"              : n_bytes,
        "n_packets"            : n_packets,
        "n_flows"              : n_flows,
        "tcp_udp_ratio_packets": tcp_udp_ratio_packets,
        "dir_ratio_packets"    : dir_ratio_packets,
        "sum_n_dest_ip"        : sum_n_dest_ip,
        "sum_n_dest_ports"     : sum_n_dest_ports,
    })



def get_mcp_tools() -> list:
    """
    Returns the list of LangChain tool objects that wrap MCP endpoints.
    Called once from agent_runner.py at agent startup.

    If MCP is unreachable, returns an empty list so the agent works
    without MCP — it just loses access to the RCA and health tools.
    """
    mcp_tools = []

    available = discover_mcp_tools()
    tool_names = [t.get("name", "") for t in available]

    if "health" in tool_names:
        mcp_tools.append(check_network_health)

    if "rca" in tool_names:
        mcp_tools.append(classify_ip_root_cause)

    if mcp_tools:
        print(f"MCP: {len(mcp_tools)} tool(s) added to agent via MCP protocol")
    else:
        print("MCP: no tools available (server may be offline) — agent continues without MCP tools")

    return mcp_tools
