from fastapi import FastAPI, UploadFile, File, APIRouter, Form
import pandas as pd
import io

from pydantic import BaseModel
from typing import List, Dict

from agent import SmartAgent, extract_profile
from network import Network
from simulator import run_multiple_simulations
from persona import build_prompt, query_llm, llm_to_profile

router = APIRouter()

class PersonaRequest(BaseModel):
    profiles: List[Dict]
    prompt: str
    capacity: float
    simulations: int


import json
import numpy as np

class _NumpyEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, np.integer):
            return int(obj)
        if isinstance(obj, np.floating):
            return float(obj)
        if isinstance(obj, np.ndarray):
            return obj.tolist()
        if isinstance(obj, pd.Timestamp):
            return obj.isoformat()
        if isinstance(obj, pd.Series):
            return obj.to_dict()
        if isinstance(obj, pd.DataFrame):
            return obj.to_dict()
        return super().default(obj)

def df_to_records(df: pd.DataFrame):
    return json.loads(json.dumps(df.to_dict(orient="records"), cls=_NumpyEncoder))

def serialize_profile(profile):
    return json.loads(json.dumps(profile, cls=_NumpyEncoder))

def deserialize_profile(profile):
    profile["bytes"] = pd.Series(profile["bytes"]) if profile.get("bytes") else None
    profile["hourly_mean"] = pd.Series(profile["hourly_mean"])
    profile["hourly_std"] = pd.Series(profile["hourly_std"])
    profile["corr"] = pd.DataFrame(profile["corr"])
    return profile

@router.post("/simulate_agents")
async def simulate_agents(
    files: list[UploadFile] = File(...),
    capacity: float = Form(4),
    simulations: int = Form(1)
):
    agents = []
    profiles = []

    for idx, file in enumerate(files):
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        
        profile = extract_profile(df)
        
        agent = SmartAgent(profile=profile, name=f"Agent_{idx+1}")
        agents.append(agent)
        profiles.append(serialize_profile(profile.copy()))

    capacity_bytes = (capacity * 1e8) / 8
    network = Network(capacity_bytes)

    result, logs = run_multiple_simulations(agents, network, simulations)

    return {
        "traffic": df_to_records(result),
        "logs": df_to_records(logs),
        "profiles": profiles,
        "capacity": capacity
    }

@router.post("/simulate_persona")
def simulate_persona(req: PersonaRequest):
    
    agents = [
    SmartAgent(profile=deserialize_profile(p), name=f"Agent_{i+1}")
    for i, p in enumerate(req.profiles)
    ]
    
    persona_profile = llm_to_profile(query_llm(build_prompt(req.prompt)))
    persona_agent = SmartAgent(profile=persona_profile, name="Persona")
    
    capacity_bytes = (req.capacity * 1e8) / 8
    network = Network(capacity_bytes)
    
    base_result, _ = run_multiple_simulations(agents, network, req.simulations)
    
    new_agents = agents + [persona_agent]
    new_result, new_logs = run_multiple_simulations(new_agents, network, req.simulations)
    
    impact = {
        "max_load_increase": float(new_result["load"].max() - base_result["load"].max()),
        "latency_increase": float(new_result["latency"].mean() - base_result["latency"].mean()),
        "congestion_time": int((new_result["load"] > 1).sum())
    }

    decision = "REJECT" if new_result["load"].max() > 0.85 else "ACCEPT"

    return {
        "Persona": persona_profile["type"].capitalize(),
        "before": df_to_records(base_result),
        "after": df_to_records(new_result),
        "logs": df_to_records(new_logs),
        "impact": impact,
        "decision": decision
    }