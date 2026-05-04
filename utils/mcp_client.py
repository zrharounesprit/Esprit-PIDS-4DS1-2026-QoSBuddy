import os
import requests
from langchain_core.tools import tool

# RCA API runs on port 8002
RCA_API_URL = os.getenv("RCA_API_URL", "http://127.0.0.1:8002")


@tool
def check_network_health() -> str:
    """
    Check the current health and status of the QoSBuddy RCA system.
    Returns information about the loaded model, number of IP profiles in the
    dataset, and which root-cause types the system can classify.
    Call this when the user asks about system status, network health, or
    what the RCA system knows about the network.
    """
    try:
        response = requests.get(f"{RCA_API_URL}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            return (
                f"RCA system status: {data.get('status', 'unknown')}. "
                f"Model: {data.get('model', 'unknown')}. "
                f"IP profiles in dataset: {data.get('ips_in_profiles', 'unknown')}. "
                f"Cause types: {data.get('cause_types', [])}."
            )
        else:
            return f"RCA health check returned HTTP {response.status_code}. Is the RCA API running on port 8002?"
    except Exception as e:
        return f"Could not reach RCA API at {RCA_API_URL}: {e}. Make sure the RCA service is running (port 8002)."


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
    Classify the root cause of a network anomaly for a specific IP address.
    Returns a human-readable RCA report explaining why this IP is behaving
    unusually (e.g., DDoS attack, port scan, heavy usage, normal behaviour).
    Call this when the user asks about a specific IP, wants to diagnose a
    network problem, or wants to classify anomalous behaviour for a device.

    Args:
        id_ip: The IP address identifier from the dataset
        n_bytes: Total bytes transmitted in the observation window
        n_packets: Total packets transmitted
        n_flows: Number of distinct network flows
        tcp_udp_ratio_packets: Ratio of TCP to UDP packets (1=all TCP, 0=all UDP)
        dir_ratio_packets: Direction ratio (1=all outgoing, 0=all incoming)
        sum_n_dest_ip: Number of unique destination IPs contacted
        sum_n_dest_ports: Number of unique destination ports contacted
    """
    try:
        payload = {
            "id_ip"                : id_ip,
            "n_bytes"              : n_bytes,
            "n_packets"            : n_packets,
            "n_flows"              : n_flows,
            "tcp_udp_ratio_packets": tcp_udp_ratio_packets,
            "dir_ratio_packets"    : dir_ratio_packets,
            "sum_n_dest_ip"        : sum_n_dest_ip,
            "sum_n_dest_ports"     : sum_n_dest_ports,
        }
        response = requests.post(f"{RCA_API_URL}/rca", json=payload, timeout=30)
        if response.status_code == 200:
            data = response.json()
            cause   = data.get("cause_label", "unknown")
            title   = data.get("cause_title", cause)
            meaning = data.get("what_it_means", "")
            return f"Root cause for IP {id_ip}: {title} ({cause}). {meaning}".strip()
        else:
            return f"RCA classification returned HTTP {response.status_code}: {response.text[:300]}"
    except Exception as e:
        return f"Could not reach RCA API at {RCA_API_URL}: {e}. Make sure the RCA service is running (port 8002)."



def get_mcp_tools() -> list:
    """
    Returns the list of LangChain tool objects that wrap MCP endpoints.
    Called once from agent_runner.py at agent startup.

    The RCA and health tools are always included — they are pre-defined as
    LangChain @tool wrappers and don't require live MCP discovery.

    Dynamic MCP discovery is attempted as a bonus (for additional tools
    registered by third-party MCP servers). If the MCP server is offline
    or fastapi_mcp is not installed, the hardcoded tools still work.

    NOTE: The agent itself runs ON the same port as the MCP server (8005),
    so calling discover_mcp_tools() from within a request would be a
    circular call and time out. We skip that here — the hardcoded tools
    are sufficient.
    """
    # Always include the hardcoded LangChain-wrapped MCP tools
    mcp_tools = [check_network_health, classify_ip_root_cause]
    print(f"MCP: {len(mcp_tools)} built-in tool(s) loaded (check_network_health, classify_ip_root_cause)")
    return mcp_tools
