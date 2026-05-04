# QoSBuddy — System Documentation

QoSBuddy is a network quality-of-service analysis platform. It provides six machine-learning-powered features — persona classification, anomaly detection, root cause analysis, SLA violation detection, traffic forecasting, and an LLM-driven simulation agent — all exposed through a React dashboard talking to a set of FastAPI microservices.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Service Map](#service-map)
3. [Backend Services](#backend-services)
4. [Frontend Pages](#frontend-pages)
5. [Data Flow — Feature by Feature](#data-flow-feature-by-feature)
6. [The LLM / Agent Layer](#the-llm--agent-layer)
7. [CSV Formats](#csv-formats)
8. [Artifacts and Models](#artifacts-and-models)
9. [Environment and Configuration](#environment-and-configuration)
10. [Running the Stack](#running-the-stack)

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                 React Frontend (port 3000)           │
│  src/api/client.js — all HTTP calls live here       │
└───────────┬──────────┬──────────┬──────────┬────────┘
            │          │          │          │
     port 8000   port 8001   port 8002   port 8003
     Persona     Anomaly      RCA          SLA
     main.py   anomaly_api  main_RCA    sla_api
                                           │
                                     sla_pipeline
                                     sla_preprocess
            │          │
     port 8004   port 8005
   Forecasting  MCP/Simulation
  forecasting    mcp_api ──┬── simulation_api
     _api.py               ├── agent_routes ──► agent_runner
                           └── (fastapi_mcp)        │
                                                ┌───┴───┐
                                           mcp_client  Gemini API
                                           (port 8002   (google-genai)
                                            RCA tools)
```

All services share the same Python virtual environment (`.venv`) and the same `utils/` directory. The React frontend communicates only via HTTP — it never imports Python directly.

---

## Service Map

| Port | Entry Point | Title | Responsibility |
|------|------------|-------|----------------|
| 3000 | `frontend/` | React Dashboard | User interface |
| 8000 | `main.py` | Persona Classification API | Classify traffic type per IP |
| 8001 | `utils/anomaly_api.py` | Anomaly Detection API | Detect anomalous IPs with Isolation Forest |
| 8002 | `utils/main_RCA.py` | Root Cause Analysis API | K-Means cluster → root cause label |
| 8003 | `utils/sla_api.py` | SLA Detection API | LSTM-based SLA violation prediction |
| 8004 | `utils/forecasting_api.py` | Traffic Forecasting API | LSTM per-IP 6-hour traffic forecast |
| 8005 | `utils/mcp_api.py` | MCP / Simulation API | Agent simulation + LLM what-if scenarios |

---

## Backend Services

### Port 8000 — Persona Classification (`main.py`)

Classifies a list of hourly traffic observations into one of five user types: **streamer, gamer, scroller, researcher, connector**.

**Endpoint:** `POST /classify_content`  
**Input:** JSON array of objects with `n_bytes`, `tcp_udp_ratio_packets`, `avg_duration`, `sum_n_dest_ip`  
**Model:** Random Forest / SVM from `artifacts/persona_model.pkl`, scaled by `artifacts/scaler.joblib`, labels decoded by `artifacts/label_encoder.joblib`  
**Output:** `{ "predicted_labels": [...], "confidence_scores": [...] }`

---

### Port 8001 — Anomaly Detection (`utils/anomaly_api.py`)

Scores each IP observation against a trained Isolation Forest. Returns an anomaly label and a SHAP explanation showing which features drove the score.

**Endpoint:** `POST /predict`  
**Input:** JSON with `n_bytes`, `n_packets`, `n_flows`, `tcp_udp_ratio_packets`, `dir_ratio_packets`  
**Models:** `artifacts/anomaly_model.pkl` (Isolation Forest), `artifacts/anomaly_scaler.pkl`  
**Output:** `{ "score": float, "label": int, "is_anomaly": bool, "explanation": {...} }`

**Endpoint:** `GET /health`  
Returns model load status.

---

### Port 8002 — Root Cause Analysis (`utils/main_RCA.py`)

Given one row of raw network features for an IP, identifies its traffic cluster via K-Means and maps the cluster to a human-readable root cause (e.g., port scan, heavy uploader, DDoS victim).

**Endpoint:** `POST /rca`  
**Input:** JSON matching the `IPRow` schema — `id_ip` is required, all other fields optional with defaults:

```
id_ip, n_flows, n_packets, n_bytes, sum_n_dest_ip, sum_n_dest_ports,
std_n_dest_ip, tcp_udp_ratio_packets, tcp_udp_ratio_bytes,
dir_ratio_packets, dir_ratio_bytes, avg_duration, avg_ttl
```

**Output:** Full RCA report including `cause_label`, `cause_title`, `what_it_means`, evidence bullets.

**Endpoint:** `GET /rca/ip/{id_ip}`  
Looks up a pre-profiled IP directly from the training dataset.

**Endpoint:** `GET /health`  
Returns `{ status, model, ips_in_profiles, cause_types, features_expected }`.

---

### Port 8003 — SLA Detection (`utils/sla_api.py`)

Predicts whether an SLA violation will occur in the next time window. Accepts **raw** CESNET rows and runs the full feature engineering pipeline server-side before inference.

**Endpoint:** `POST /predict_sla`  
**Input:**
```json
{
  "rows": [ { "n_bytes": ..., "n_packets": ..., ... } ],
  "input_row_count": 24,
  "times_rows": [ { "TIME_START": "...", ... } ]   // optional
}
```

**Pipeline steps (all inside the endpoint):**

1. Build DataFrame from `rows`
2. If `times_rows` provided: call `merge_cesnet_times_1h()` to attach timestamps, then check clock with `df_has_resolvable_clock()`
3. `ensure_subnet_key(df, "default")` — adds `subnet_id` if absent
4. `engineer_sla_features(df, feature_cols)` — computes all 37 time-series features:
   - Rolling statistics (24h and 6h windows)
   - Lag features (1h, 2h, 3h)
   - Cyclical time encoding (sin/cos of hour, day-of-week)
   - Peak-hour ratios
5. Run LSTM model on the 37-feature vector
6. Return `{ "prediction": int, "probability": float, "label": str }`

**Supporting modules:**
- `utils/sla_pipeline.py` — `engineer_sla_features()`: computes all 37 features
- `utils/sla_preprocess.py` — `ensure_subnet_key()`, `merge_cesnet_times_1h()`, `df_has_resolvable_clock()`

---

### Port 8004 — Traffic Forecasting (`utils/forecasting_api.py`)

Forecasts the next 6 hours of `n_bytes` traffic for a given IP using a per-IP LSTM model with learned embeddings.

**Endpoint:** `POST /forecast`  
**Input:**
```json
{
  "rows": [ { /* 24 rows of CESNET features */ } ],
  "ip_id": 42
}
```

**Pipeline:**
1. Extract the 15 CESNET feature columns
2. Log-transform high-magnitude columns (indices 0–8, 14)
3. Standardize with pre-fitted scaler params from `model_export/scaler_params.pkl`
4. Feed 24-step sequence + IP embedding into LSTM (`model_export/lstm_embedding_model.keras`)
5. Inverse-transform the 6-step output back to raw byte scale
6. Return `{ "forecast": [f1, f2, f3, f4, f5, f6] }` (6 hourly values)

---

### Port 8005 — MCP / Simulation API (`utils/mcp_api.py`)

Combines three responsibilities in one FastAPI app:

**1. Agent-Based Simulation** — `POST /api/simulate_agents`  
Accepts one CSV file per user (multipart form). Builds a `SmartAgent` for each, runs `N` simulation passes through the `Network` model, and returns averaged traffic timeseries.

**2. Persona Simulation** — `POST /api/simulate_persona`  
Accepts a list of existing user profiles + a natural language persona description. Calls Gemini to convert the description into a traffic profile, injects the new agent, runs the simulation before and after, and returns both timeseries plus an impact summary and ACCEPT/REJECT QoS decision.

**3. LLM Agent Endpoint** — `POST /agent-run`  
Accepts a natural language `prompt` (form field) and optional CSV files. Passes everything to `agent_runner.run_agent()` which orchestrates a Gemini tool-calling loop. Returns `{ agent_called_tool, tool_args, simulation_result, summary }`.

**MCP Tool Discovery** (optional): If `fastapi_mcp` is installed, the `/mcp` SSE endpoint is mounted for external MCP clients. This is separate from the agent's own tools.

---

## Frontend Pages

All API calls go through `frontend/src/api/client.js`. Two helper functions exist: `post(url, body)` for JSON endpoints and `postForm(url, formData)` for multipart uploads.

### Upload (`/upload`)
Dataset-level CSV uploader. Stores rows in `DatasetContext` (React context) for reuse across pages.

### Persona Classification (`/persona`)
Sends CESNET rows to `POST :8000/classify_content`. Displays the predicted user type per-IP with confidence scores.
**CSV needed:** `n_bytes`, `tcp_udp_ratio_packets`, `avg_duration`, `sum_n_dest_ip`

### Anomaly Detection (`/anomaly`)
Sends a single observation to `POST :8001/predict`. Displays anomaly score, label, and SHAP feature importance bars.
**CSV needed:** `n_bytes`, `n_packets`, `n_flows`, `tcp_udp_ratio_packets`, `dir_ratio_packets`

### Root Cause Analysis (`/rca`)
Form for entering IP traffic features manually, or uploading a CSV. Calls `POST :8002/rca`. Displays the cause title, plain-English explanation, and evidence bullets.
**CSV needed:** `id_ip`, `n_bytes`, `n_packets`, `n_flows`, `sum_n_dest_ip`, `sum_n_dest_ports`, `avg_duration`, `avg_ttl`

### SLA Detection (`/sla`)
Uploads a CESNET features CSV (and optionally a times CSV). Calls `POST :8003/predict_sla`. The backend runs the full 37-feature engineering pipeline before prediction. Displays violation probability and label.
**CSV needed:** CESNET feature columns + optionally a separate times file with `TIME_START`

### Traffic Forecasting (`/forecasting`)
Uploads 24 rows of CESNET data plus an IP ID. Calls `POST :8004/forecast`. Displays a 6-hour forecast chart.
**CSV needed:** 15 CESNET feature columns, 24 rows minimum, `id_ip`

### Network Simulation (`/simulation`)
Two-step workflow:
1. Upload one CSV per user → `POST :8005/api/simulate_agents` → traffic timeline + QoS metrics
2. Type a persona description → `POST :8005/agent-run` → before/after comparison + QoS verdict

**CSV needed (per user):** `hour`, `n_bytes`, `n_packets`, `n_flows`

### MCP Demo (`/mcp-demo`)
Single text prompt → `POST :8005/agent-run`. The Gemini agent decides which tool to call (simulation, health check, or RCA). Shows tool invocation, arguments, and plain-English summary in an agent console.

---

## Data Flow — Feature by Feature

### Persona Classification

```
CSV rows (n_bytes, tcp_udp_ratio_packets, avg_duration, sum_n_dest_ip)
  → POST :8000/classify_content
  → scaler.transform()
  → persona_model.predict()
  → label_encoder.inverse_transform()
  → [ "streamer", "gamer", ... ]
```

### Anomaly Detection

```
Single observation (5 features)
  → POST :8001/predict
  → anomaly_scaler.transform()
  → isolation_forest.predict() + decision_function()
  → shap.TreeExplainer → feature importances
  → { score, label, is_anomaly, explanation }
```

### Root Cause Analysis

```
IP feature row (id_ip + up to 12 metrics)
  → POST :8002/rca
  → align to PROFILE_FEATURES order
  → rca_scaler.transform()
  → kmeans.predict() → cluster_id
  → CAUSE_DESCRIPTIONS[cluster_id]
  → build_report() → human-readable report
```

### SLA Detection

```
Raw CESNET rows + optional times rows
  → POST :8003/predict_sla
  → ensure_subnet_key(df, "default")           # add subnet_id if missing
  → merge_cesnet_times_1h(df, times_df)        # attach timestamps (if times provided)
  → engineer_sla_features(df, feature_cols)    # 37 features: rolling, lag, cyclical
  → sla_scaler.transform()
  → lstm_model.predict()
  → { prediction, probability, label }
```

### Traffic Forecasting

```
24-row CESNET sequence + ip_id
  → POST :8004/forecast
  → log-transform high-magnitude columns
  → standardize with (feat_mean, feat_std)
  → LSTM(sequence_input, embedding(ip_id))
  → inverse-transform output
  → 6 hourly forecasted n_bytes values
```

### Agent-Based Simulation

```
N CSV files + capacity + simulations
  → POST :8005/api/simulate_agents
  → extract_profile(df) per file    # mean, std, quartiles, hourly pattern, correlations
  → SmartAgent(profile) per file    # stateful agent with Markov-like state transitions
  → Network(capacity_bytes)         # queuing model: load → latency, packet_loss
  → run_multiple_simulations()      # 144 10-minute timesteps × N runs → averaged
  → { traffic: [...], logs, profiles, capacity }
```

### Persona What-If Simulation

```
Existing user profiles + persona text description
  → POST :8005/api/simulate_persona
  → build_prompt(description)
  → Gemini API → JSON traffic profile
  → llm_to_profile() → { bytes_mean, bytes_std, peak_hours, type, burstiness }
  → SmartAgent("Persona")
  → run_multiple_simulations(existing_agents) → base_result
  → run_multiple_simulations(existing_agents + persona_agent) → new_result
  → impact = { max_load_increase, latency_increase, congestion_time }
  → decision = "ACCEPT" if max_load < 0.85 else "REJECT"
```

---

## The LLM / Agent Layer

### Gemini API (`utils/persona.py`)

Used for persona profile generation. Accepts a natural language description and returns a structured JSON traffic profile. Uses `google.genai.Client` with model fallback chain: `gemini-2.5-flash` → `gemini-2.0-flash` → `gemini-1.5-flash`.

**Input:** Free-text description ("a gamer who plays at night")  
**Output:** `{ bytes_mean, bytes_std, peak_hours, traffic_type, burstiness }`

### LangChain Agent (`utils/agent_runner.py`)

Powers the `/agent-run` endpoint. Uses a manual tool-calling loop (no `AgentExecutor`) that works with any `langchain_core` version:

```
user_prompt + csv_bytes_list
  → SystemMessage (describes all 3 tools)
  → HumanMessage (user prompt)
  → llm.bind_tools([run_network_simulation, check_network_health, classify_ip_root_cause])
  → loop (max 6 iterations):
      response = llm.invoke(messages)
      if response has tool_calls:
          execute each tool → ToolMessage
      else:
          break
  → return { agent_called_tool, tool_args, simulation_result, summary }
```

**Tools available to the agent:**

| Tool | Module | What it does |
|------|--------|-------------|
| `run_network_simulation` | `agent_runner.py` | Calls `/api/simulate_agents` or `/api/simulate_persona` on port 8005 |
| `check_network_health` | `mcp_client.py` | Calls `GET :8002/health` — returns RCA system status |
| `classify_ip_root_cause` | `mcp_client.py` | Calls `POST :8002/rca` — returns root cause for an IP |

### Agent Decision Logic

The agent uses these rules (enforced via system prompt):

- Prompt mentions a new user type → `run_network_simulation(injection_prompt=...)`
- No CSVs uploaded AND no persona → skip simulation tool, explain CSVs are needed
- "health check" or "system status" → `check_network_health()`
- Specific IP address or anomaly diagnosis → `classify_ip_root_cause(id_ip=...)`

---

## CSV Formats

### Simulation CSVs (one file per user, port 8005)

```csv
hour,n_bytes,n_packets,n_flows
0,125000,800,45
1,98000,620,38
...
23,145000,900,52
```

Minimum columns: `hour` (0–23), `n_bytes`, `n_packets`, `n_flows`. One row per hourly observation. More rows = better profile. Each file = one user.

### CESNET Feature CSV (ports 8000, 8001, 8002, 8003, 8004)

Standard CESNET-TimeSeries24 format. Not all columns are needed by every service — each page lists the specific ones it uses.

| Column | Type | Description |
|--------|------|-------------|
| `id_ip` | int | IP identifier |
| `n_bytes` | float | Bytes in the hour |
| `n_packets` | float | Packets in the hour |
| `n_flows` | int | Distinct flows |
| `avg_duration` | float | Average flow duration (seconds) |
| `avg_ttl` | float | Average time-to-live |
| `tcp_udp_ratio_packets` | float | 1 = all TCP, 0 = all UDP |
| `tcp_udp_ratio_bytes` | float | Same but by bytes |
| `dir_ratio_packets` | float | 1 = all outgoing, 0 = all incoming |
| `dir_ratio_bytes` | float | Same but by bytes |
| `sum_n_dest_ip` | int | Unique destination IPs |
| `sum_n_dest_ports` | int | Unique destination ports |
| `std_n_dest_ip` | float | Std dev of destination IPs |
| `TIME_START` | str | ISO timestamp (SLA only, separate file) |

---

## Artifacts and Models

| File | Service | Description |
|------|---------|-------------|
| `artifacts/persona_model.pkl` | port 8000 | Traffic persona classifier |
| `artifacts/scaler.joblib` | port 8000 | Feature scaler for persona |
| `artifacts/label_encoder.joblib` | port 8000 | Label decoder (streamer/gamer/…) |
| `artifacts/anomaly_model.pkl` | port 8001 | Isolation Forest |
| `artifacts/anomaly_scaler.pkl` | port 8001 | Feature scaler for anomaly |
| `artifacts/rca_model.pkl` | port 8002 | K-Means RCA clustering model |
| `artifacts/rca_scaler.pkl` | port 8002 | Feature scaler for RCA |
| `artifacts/ip_profiles.pkl` | port 8002 | Pre-computed per-IP feature vectors |
| `artifacts/sla_model.pkl` | port 8003 | LSTM SLA violation predictor |
| `artifacts/sla_scaler.pkl` | port 8003 | Scaler for the 37 SLA features |
| `model_export/lstm_embedding_model.keras` | port 8004 | Per-IP LSTM forecasting model |
| `model_export/config.pkl` | port 8004 | Feature list, SEQ_LEN=24, HORIZON=6 |
| `model_export/scaler_params.pkl` | port 8004 | Forecasting scaler (mean/std per feature) |
| `model_export/ip_to_id.pkl` | port 8004 | IP-to-embedding-index mapping |

---

## Environment and Configuration

All configuration lives in a single `.env` file at the repository root. It is gitignored.

```env
GOOGLE_API_KEY=your_gemini_api_key_here
```

`GOOGLE_API_KEY` is read by:
- `utils/persona.py` — for persona text → profile generation
- `utils/agent_routes.py` — for the `/agent-run` LLM agent
- `utils/agent_runner.py` — passes to `ChatGoogleGenerativeAI`

Legacy `GEMINI_API_KEY` is accepted as a fallback in all three files.

`RCA_API_URL` (optional env var, default `http://127.0.0.1:8002`) controls where `mcp_client.py` sends health and RCA requests.

---

## Running the Stack

Open 7 terminals from the project root with the virtual environment activated (`source .venv/bin/activate` or `.venv\Scripts\activate` on Windows).

```bash
# Terminal 1 — Persona Classification (port 8000)
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — Anomaly Detection (port 8001)
uvicorn utils.anomaly_api:app --host 127.0.0.1 --port 8001 --reload

# Terminal 3 — Root Cause Analysis (port 8002)
uvicorn utils.main_RCA:app --host 127.0.0.1 --port 8002 --reload

# Terminal 4 — SLA Detection (port 8003)
uvicorn utils.sla_api:app --host 127.0.0.1 --port 8003 --reload

# Terminal 5 — Traffic Forecasting (port 8004)
uvicorn utils.forecasting_api:app --host 127.0.0.1 --port 8004 --reload

# Terminal 6 — MCP / Simulation + Agent (port 8005)
uvicorn utils.mcp_api:app --host 127.0.0.1 --port 8005 --reload

# Terminal 7 — React frontend (port 3000)
cd frontend && npm run dev
```

Open `http://localhost:3000` in your browser.

**Important:** Start terminal 6 (port 8005) after the `.env` file exists. The `--reload` flag only watches `.py` files — if you add or change `.env` while uvicorn is running, restart the process for the new key to take effect.
