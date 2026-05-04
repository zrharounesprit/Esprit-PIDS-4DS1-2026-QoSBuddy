# =============================================================================
# agent_routes.py — FastAPI Agent Endpoint
#
# Registers POST /agent-run on your FastAPI app.
# Called by the Streamlit agent page.
#
# HOW TO PLUG INTO main_RCA.py:
#   from agent_routes import add_agent_routes
#   add_agent_routes(app)
#
# Place this file in utils/ next to main_RCA.py
# =============================================================================

import os
import io
from typing import Optional, List
from fastapi import APIRouter, UploadFile, File, Form, HTTPException
from dotenv import load_dotenv

# Load .env from repository root — one level up from utils/
load_dotenv(os.path.join(
    os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"
))

# Support both GOOGLE_API_KEY (new .env standard) and GEMINI_API_KEY (legacy)
GEMINI_API_KEY = os.getenv("GOOGLE_API_KEY") or os.getenv("GEMINI_API_KEY")

from utils.agent_runner import run_agent

router = APIRouter()


@router.post(
    "/agent-run",
    summary="Run the QoSBuddy agent with a natural language prompt",
    description="""
    The user provides a natural language prompt and optionally uploads CSV files.
    The Gemini agent decides whether to run a simulation based on the prompt,
    executes the simulation tool if appropriate, and returns a plain English summary.

    This is the agentic endpoint — the agent decides what to do,
    not the caller.
    """
)
async def agent_run(
    prompt: str = Form(
        ...,
        description="Natural language instruction, e.g. 'Simulate a gamer joining the network'"
    ),
    files: Optional[List[UploadFile]] = File(
        default=None,
        description="Optional CSV files — each represents one existing network user"
    ),
):
    """
    Agent endpoint. Receives a prompt + optional CSV files.
    The agent decides whether to call the simulation tool.
    """
    if not GEMINI_API_KEY:
        raise HTTPException(
            status_code=503,
            detail="GOOGLE_API_KEY not found. Add GOOGLE_API_KEY=your-key to the .env file in the project root."
        )

    # Read CSV file bytes if provided
    csv_bytes_list = []
    agent_names    = []

    if files:
        for file in files:
            try:
                contents = await file.read()
                csv_bytes_list.append(contents)
                agent_names.append(
                    os.path.splitext(file.filename)[0]
                )
            except Exception as e:
                pass   # skip unreadable files silently

    # Run the agent
    try:
        result = run_agent(
            user_prompt    = prompt,
            csv_bytes_list = csv_bytes_list,
            agent_names    = agent_names,
            gemini_api_key = GEMINI_API_KEY,
        )
        return result

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Agent error: {str(e)}"
        )


def add_agent_routes(app):
    app.include_router(router, tags=["Agent"])
