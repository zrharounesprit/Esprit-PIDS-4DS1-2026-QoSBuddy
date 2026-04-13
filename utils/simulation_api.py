from fastapi import FastAPI, UploadFile, File
import pandas as pd
import io

from pydantic import BaseModel
from typing import List, Dict

from agent import SmartAgent, extract_profile
from network import Network
from simulator import run_multiple_simulations
from persona import build_prompt, query_llm, llm_to_profile

app = FastAPI()

class PersonaRequest(BaseModel):
    profiles: List[Dict]
    prompt: str
    capacity: float
    simulations: int


def serialize_profile(profile):
    profile["hourly_mean"] = profile["hourly_mean"].to_dict()
    profile["hourly_std"] = profile["hourly_std"].to_dict()
    profile["corr"] = profile["corr"].to_dict()
    return profile

def deserialize_profile(profile):
    profile["hourly_mean"] = pd.Series(profile["hourly_mean"])
    profile["hourly_std"] = pd.Series(profile["hourly_std"])
    profile["corr"] = pd.DataFrame(profile["corr"])
    return profile

@app.post("/simulate_agents")
async def simulate_agents(
    files: list[UploadFile] = File(...),
    capacity: float = 4, 
    simulations: int = 1
):
    agents = []
    profiles = []

    for idx, file in enumerate(files):
        content = await file.read()
        df = pd.read_csv(io.BytesIO(content))
        
        profile = extract_profile(df)
        profiles.append(profile)
        
        agent = SmartAgent(profile=profile, name=f"Agent_{idx+1}")
        agents.append(agent)
        profiles.append(serialize_profile(profile.copy()))

    capacity_bytes = (capacity * 1e6) / 8
    network = Network(capacity_bytes)

    result, logs = run_multiple_simulations(agents, network, simulations)

    return {
        "traffic": result.to_dict(orient="records"),
        "logs": logs.to_dict(orient="records"),
        "profiles": profiles,
        "capacity": capacity
    }

@app.post("/simulate_persona")
def simulate_persona(req: PersonaRequest):
    
    agents = [
    SmartAgent(profile=deserialize_profile(p), name=f"Agent_{i+1}")
    for i, p in enumerate(req.profiles)
    ]
    
    persona_profile = llm_to_profile(query_llm(build_prompt(req.prompt)))
    persona_agent = SmartAgent(profile=persona_profile, name="Persona")
    
    capacity_bytes = (req.capacity * 1e6) / 8
    network = Network(capacity_bytes)
    
    base_result, _ = run_multiple_simulations(agents, network, req.simulations)
    
    new_agents = agents + [persona_agent]
    new_result, new_logs = run_multiple_simulations(new_agents, network, req.simulations)
    
    impact = {
        "max_load_increase": new_result["load"].max() - base_result["load"].max(),
        "latency_increase": new_result["latency"].mean() - base_result["latency"].mean(),
        "congestion_time": int((new_result["load"] > 1).sum())
    }

    decision = "REJECT" if new_result["load"].max() > 0.85 else "ACCEPT"

    return {
        "before": base_result.to_dict(orient="records"),
        "after": new_result.to_dict(orient="records"),
        "logs": new_logs.to_dict(orient="records"),
        "impact": impact,
        "decision": decision
    }