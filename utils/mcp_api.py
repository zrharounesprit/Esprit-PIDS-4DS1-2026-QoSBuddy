# ─────────────────────────────────────────────────────────────────────────────
# utils/mcp_api.py — MCP / Agent Simulation API
#
# Routes:
#   POST /api/simulate_agents   — run multi-agent simulation from CSV files
#   POST /api/simulate_persona  — run persona-based simulation
#   POST /agent-run             — LLM-driven what-if scenario (LangChain + Gemini)
#
# Run:
#   uvicorn utils.mcp_api:app --host 127.0.0.1 --port 8005 --reload
# ─────────────────────────────────────────────────────────────────────────────

from utils.simulation_api import router as simulation_api_router
from utils.agent_routes import add_agent_routes
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

try:
    from fastapi_mcp import FastApiMCP
    _MCP_AVAILABLE = True
except ImportError:
    _MCP_AVAILABLE = False
    print("⚠️  fastapi-mcp not installed — MCP tool discovery disabled. "
          "Run: pip install fastapi-mcp  to enable it.")

app = FastAPI(title="QoSBuddy MCP / Simulation API")
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

# 3. Mount MCP for tool discovery (must be after all routes are added)
if _MCP_AVAILABLE:
    mcp = FastApiMCP(app)
    mcp.mount()
    print("✅ MCP tool discovery mounted.")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8005)

