from simulation_api import router as simulation_api_router
from agent_routes import add_agent_routes
from fastapi_mcp import FastApiMCP
from fastapi import FastAPI

app = FastAPI()
app.include_router(simulation_api_router, prefix="/api", tags=["Simulation"])

# 2. Your agent routes
add_agent_routes(app)

# 3. Mount MCP for tool discovery (must be after all routes are added)
mcp = FastApiMCP(app)
mcp.mount()

