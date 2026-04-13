import pandas as pd
import json
import os
import re
from google import genai
from dotenv import load_dotenv

load_dotenv()
API_KEY = os.getenv("GEMINI_API_KEY")

def build_prompt(description):
    return f"""
    You are a network behavior expert, refer to CESNET-TimeSeries24: Time Series Dataset for Network Traffic Anomaly Detection and Forecasting for context.

    Convert this user description into a traffic profile.

    Description:
    {description}

    Output ONLY a valid JSON object with no explanation, no markdown, no code blocks.
    The JSON must contain exactly these fields:
    - bytes_mean (integer) (should be between 1e4 and 1e7)
    - bytes_std (integer) (should be between 1e3 and 1e6)
    - peak_hours (list of integers 0-23)
    - traffic_type (one of: streamer/gamer/scroller/researcher/connector)
    - burstiness (one of: low/medium/high)
    """

def query_llm(prompt):
    client = genai.Client(api_key=API_KEY)
    print("API Key:", API_KEY)
    try:
        response = client.models.generate_content(
            model="gemini-2.5-flash",  
            contents=prompt,
        )
        print("LLM Response:", response.text)
        return response.text
    except Exception as e:
        raise RuntimeError(f"Error querying LLM: {str(e)}")

def extract_json(text):
    """Strip markdown fences and extract the first JSON object found."""
    if not text or not text.strip():
        raise ValueError("LLM returned an empty response.")

    text = re.sub(r"```(?:json)?\s*", "", text).replace("```", "").strip()

    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError(f"No JSON object found in LLM response:\n{text}")

    return match.group()

def llm_to_profile(llm_output):
    clean = extract_json(llm_output)
    data = json.loads(clean)

    required = {"bytes_mean", "bytes_std", "peak_hours", "traffic_type", "burstiness"}
    missing = required - data.keys()
    if missing:
        raise KeyError(f"LLM JSON is missing fields: {missing}")

    hours = range(24)

    hourly_mean = pd.Series({
        h: data["bytes_mean"] * (1.5 if h in data["peak_hours"] else 0.6)
        for h in hours
    })

    hourly_std = pd.Series({
        h: data["bytes_std"] for h in hours
    })

    burst_map = {"high": 2, "medium": 1.5, "low": 1.2}
    burst_factor = burst_map.get(data["burstiness"].lower(), 1.2)

    corr = pd.DataFrame(
        [[1.0, 0.8, 0.6],
         [0.8, 1.0, 0.7],
         [0.6, 0.7, 1.0]],
        columns=["n_bytes", "n_packets", "n_flows"],
        index=["n_bytes", "n_packets", "n_flows"]
    )

    return {
        "bytes": None,
        "bytes_mean": data["bytes_mean"],
        "bytes_std": data["bytes_std"],
        "hourly_mean": hourly_mean,
        "hourly_std": hourly_std,
        "corr": corr,
        "burst_factor": burst_factor,
        "type": data["traffic_type"]
    }