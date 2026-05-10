# ─────────────────────────────────────────────────────────────────────────────
# utils/mcp_api.py — MCP / Agent Simulation API  (port 8005)
#
# Routes:
#   POST /api/simulate_agents   — run multi-agent simulation from CSV files
#   POST /api/simulate_persona  — run persona-based simulation
#   POST /agent-run             — LLM-driven what-if scenario (LangChain + Gemini)
#   POST /incident-analyze      — Autopilot: multi-model investigation + Kimi K2.6
#   GET  /noc/status            — NOC Autopilot live status
#   GET  /noc/history           — NOC cycle history
#   POST /noc/trigger           — Manual NOC cycle trigger
#
# Run:
#   uvicorn utils.mcp_api:app --host 127.0.0.1 --port 8005 --reload
# ─────────────────────────────────────────────────────────────────────────────

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from utils.simulation_api import router as simulation_api_router
from utils.agent_routes import add_agent_routes
from utils.incident_routes import add_incident_routes
from utils.noc_routes import add_noc_routes
from utils.noc_scheduler import start_noc_scheduler, stop_noc_scheduler

try:
    from fastapi_mcp import FastApiMCP
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    print("fastapi-mcp not installed — MCP tool discovery disabled. "
          "Run: pip install fastapi-mcp  to enable it.")


@asynccontextmanager
async def lifespan(app: FastAPI):
    start_noc_scheduler()
    yield
    stop_noc_scheduler()


app = FastAPI(
    title="QoSBuddy MCP / Simulation API",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# 1. Simulation routes
app.include_router(simulation_api_router, prefix="/api", tags=["Simulation"])

# 2. Agent routes (LLM-driven what-if)
add_agent_routes(app)

# 3. Autopilot incident investigation
add_incident_routes(app)

# 4. NOC Autopilot status/history/trigger
add_noc_routes(app)

# 5. Mount MCP for tool discovery (must be after all routes are added)
if _MCP_AVAILABLE:
    mcp = FastApiMCP(app)
    mcp.mount()
    print("MCP tool discovery mounted.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8005)
