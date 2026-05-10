# QoSBuddy — System Documentation

QoSBuddy is a network quality-of-service analysis platform. It provides eight ML/AI-powered features — persona classification, anomaly detection, root cause analysis, SLA violation detection, traffic forecasting, agent-based simulation, multi-agent incident investigation (Green Auto-Pilot), and an autonomous NOC agent (SLA Guardian) — all exposed through a React dashboard talking to a set of FastAPI microservices.

---

## Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Service Map](#service-map)
3. [Backend Services](#backend-services)
4. [NOC Autopilot — SLA Guardian](#noc-autopilot--sla-guardian)
5. [Green Auto-Pilot — Multi-Agent Investigation](#green-auto-pilot--multi-agent-investigation)
6. [Frontend Pages](#frontend-pages)
7. [Frontend Design System](#frontend-design-system)
8. [Data Flow — Feature by Feature](#data-flow-feature-by-feature)
9. [The LLM / Agent Layer](#the-llm--agent-layer)
10. [CSV Formats](#csv-formats)
11. [Artifacts and Models](#artifacts-and-models)
12. [Environment and Configuration](#environment-and-configuration)
13. [Running the Stack](#running-the-stack)

---

## Architecture Overview

```
┌──────────────────────────────────────────────────────────┐
│              React Frontend (port 3000)                  │
│  Outfit font · Video background · Frosted glass UI       │
│  src/api/client.js — all HTTP calls live here            │
└──────┬──────┬──────┬──────┬──────┬──────────────────────┘
       │      │      │      │      │
  port 8000  8001  8002   8003   8004        port 8005
  Persona  Anomaly  RCA    SLA  Forecast   MCP/Simulation
  main.py  anomaly main_  sla_  forecast     mcp_api
            _api   RCA    api    _api          │
                                 │       ┌─────┼──────────┐
                            sla_pipeline │     │          │
                            sla_preproc  │   agent_    noc_agent
                                         │   routes       │
                                         │     │     ┌────┴────┐
                                    simulation │   Kimi K2.6  Slack
                                      _api   Gemini  (Moonshot  Webhook
                                              API     API)
```

All services share the same Python virtual environment and the same `utils/` directory. The React frontend communicates only via HTTP.

---

## Service Map

| Port | Entry Point | Title | Responsibility |
|------|------------|-------|----------------|
| 3000 | `frontend/` | React Dashboard | User interface |
| 8000 | `main.py` | Persona Classification API | Classify traffic type per IP |
| 8001 | `utils/anomaly_api.py` | Anomaly Detection API | Detect anomalous IPs with Isolation Forest |
| 8002 | `utils/main_RCA.py` | Root Cause Analysis API | K-Means cluster to root cause label |
| 8003 | `utils/sla_api.py` | SLA Detection API | XGBoost-based SLA violation prediction (55 features) |
| 8004 | `utils/forecasting_api.py` | Traffic Forecasting API | LSTM per-IP 6-hour traffic forecast |
| 8005 | `utils/mcp_api.py` | MCP / Simulation / NOC API | Agent simulation, LLM what-if scenarios, NOC autopilot |

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

Predicts whether an SLA violation will occur in the next time window. Uses an XGBoost classifier with 55 engineered features. Accepts **raw** CESNET rows and runs the full feature engineering pipeline server-side before inference.

**Endpoint:** `POST /predict_sla`
**Input:**
```json
{
  "rows": [ { "n_bytes": ..., "n_packets": ..., ... } ],
  "input_row_count": 24,
  "times_rows": [ { "TIME_START": "...", ... } ]
}
```

**Pipeline steps (all inside the endpoint):**

1. Build DataFrame from `rows`
2. If `times_rows` provided: call `merge_cesnet_times_1h()` to attach timestamps, then check clock with `df_has_resolvable_clock()`
3. `ensure_subnet_key(df, "default")` — adds `subnet_id` if absent
4. `engineer_sla_features(df, feature_cols)` — computes all 55 features:
   - Rolling statistics (24h and 6h windows)
   - Lag features (1h, 2h, 3h)
   - Cyclical time encoding (sin/cos of hour, day-of-week)
   - Peak-hour ratios
   - Cross-feature interactions
5. Run XGBoost model on the 55-feature vector
6. Return `{ "prediction": int, "probability": float, "label": str }`

**Supporting modules:**
- `utils/sla_pipeline.py` — `engineer_sla_features()`: computes all 55 features
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
2. Log-transform high-magnitude columns (indices 0-8, 14)
3. Standardize with pre-fitted scaler params from `model_export/scaler_params.pkl`
4. Feed 24-step sequence + IP embedding into LSTM (`model_export/lstm_embedding_model.keras`)
5. Inverse-transform the 6-step output back to raw byte scale
6. Return `{ "forecast": [f1, f2, f3, f4, f5, f6] }` (6 hourly values)

**Endpoint:** `POST /explain`
Accepts historical and forecast byte arrays. Calls Gemini to generate a plain-English explanation of the forecast trends.

**Endpoint:** `GET /ip-id?filename=...`
Returns the IP embedding index for a given filename.

---

### Port 8005 — MCP / Simulation API (`utils/mcp_api.py`)

Combines multiple responsibilities in one FastAPI app:

**1. Agent-Based Simulation** — `POST /api/simulate_agents`
Accepts one CSV file per user (multipart form). Builds a `SmartAgent` for each, runs `N` simulation passes through the `Network` model, and returns averaged traffic timeseries.

**2. Persona Simulation** — `POST /api/simulate_persona`
Accepts a list of existing user profiles + a natural language persona description. Calls Gemini to convert the description into a traffic profile, injects the new agent, runs the simulation before and after, and returns both timeseries plus an impact summary and ACCEPT/REJECT QoS decision.

**3. LLM Agent Endpoint** — `POST /agent-run`
Accepts a natural language `prompt` (form field) and optional CSV files. Passes everything to `agent_runner.run_agent()` which orchestrates a Gemini tool-calling loop. Returns `{ agent_called_tool, tool_args, simulation_result, summary }`.

**4. Incident Analysis** — `POST /incident-analyze`
Used by the Green Auto-Pilot page. Accepts a CSV file and runs a multi-agent LangGraph investigation with 4 Gemini agents in parallel.

**5. NOC Autopilot Endpoints** — `GET /noc/status`, `GET /noc/history`, `POST /noc/trigger`
Controls the autonomous SLA Guardian agent loop. See [NOC Autopilot](#noc-autopilot--sla-guardian) section below.

**MCP Tool Discovery** (optional): If `fastapi_mcp` is installed, the `/mcp` SSE endpoint is mounted for external MCP clients.

---

## NOC Autopilot — SLA Guardian

The NOC Autopilot (`utils/noc_agent.py`) is a fully autonomous agent that continuously monitors network SLA compliance. It runs on a configurable interval (default: every 10 minutes) and executes a 7-phase investigation loop.

### Agent Loop Phases

```
OBSERVE → ATTRIBUTE → PLAN → SIMULATE → VERIFY → ITERATE → SYNTHESIZE
```

| Phase | Purpose |
|-------|---------|
| **OBSERVE** | Generate 48-hour synthetic traffic window, run XGBoost SLA predictions, compute breach probability |
| **ATTRIBUTE** | If breach detected, identify root cause via anomaly scores and feature analysis |
| **PLAN** | Generate mitigation plan (QoS throttling, load balancing, traffic shaping) |
| **SIMULATE** | Apply mitigation scenario to synthetic data, re-run predictions to measure improvement |
| **VERIFY** | Check if post-mitigation probability dropped below SLA threshold |
| **ITERATE** | If not resolved after first attempt, try alternative mitigation strategies (up to 3 iterations) |
| **SYNTHESIZE** | Call Kimi K2.6 to generate an executive summary report with root cause, impact, and recommendations |

### Kimi K2.6 Integration

The SYNTHESIZE phase uses Moonshot's Kimi K2.6 reasoning model to generate concise JSON reports:

- **API:** OpenAI SDK pointed at `https://api.moonshot.ai/v1`
- **Model:** `kimi-k2-0711`
- **Thinking mode:** Disabled via `extra_body={"thinking": {"type": "disabled"}}`
- **Temperature:** 0.6
- **Output:** Structured JSON with `executive_summary`, `root_cause`, `business_impact`, `recommendations[]`

### Slack Alert Integration

After each cycle, the agent sends a formatted alert to Slack via Incoming Webhooks:

| Alert Type | Color | Trigger |
|------------|-------|---------|
| Green | `#36a64f` | Nominal — no SLA breach detected |
| Yellow | `#f2c744` | Breach detected but resolved by agent mitigation |
| Red | `#e01e5a` | Breach detected, unresolved — requires human intervention |

Alerts include: severity level, breach probability, mitigation scenario attempted, iteration count, and executive summary.

### API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/noc/status` | GET | Current scheduler state, phase progress, latest cycle result |
| `/noc/history?limit=N` | GET | Last N completed cycles with full phase details |
| `/noc/trigger?inject_breach=bool` | POST | Manually trigger a cycle (optionally inject artificial breach) |

### Cycle Output Structure

```json
{
  "severity": "HIGH",
  "breach_detected": true,
  "resolved": true,
  "iterations": 2,
  "mitigation_scenario": "qos_throttling",
  "breach_summary": { "max_prob": 0.87, "breach_count": 3 },
  "phases": [
    { "name": "OBSERVE", "status": "done", "detail": "..." },
    { "name": "ATTRIBUTE", "status": "done", "detail": "..." }
  ],
  "report": {
    "executive_summary": "...",
    "root_cause": "...",
    "business_impact": "...",
    "recommendations": ["...", "..."],
    "source": "kimi-k2.6"
  }
}
```

---

## Green Auto-Pilot — Multi-Agent Investigation

The Green Auto-Pilot (`/auto-pilot` page) uses a LangGraph fan-out architecture with 4 parallel Gemini 2.0 Flash agents to investigate network incidents from uploaded CSV data.

### Agent Architecture

```
                    ┌─── Traffic Analyst ───┐
                    │                       │
CSV Upload ──► Orchestrator ─┤                       ├──► Synthesized Report
                    │                       │
                    ├─── Anomaly Profiler ──┤
                    │                       │
                    ├─── SLA Assessor ──────┤
                    │                       │
                    └─── Persona Classifier ┘
```

Each agent receives the same dataset and produces domain-specific analysis. The orchestrator merges all findings into a unified incident report with severity assessment, root cause analysis, and recommended actions.

### API

**Endpoint:** `POST /incident-analyze` (port 8005)
**Input:** Multipart form with CSV file
**Output:** Combined analysis from all 4 agents plus synthesis

---

## Frontend Pages

All API calls go through `frontend/src/api/client.js`. Two helper functions exist: `post(url, body)` for JSON endpoints and `postForm(url, formData)` for multipart uploads.

### Dashboard (`/`)
Landing page with gradient mesh hero, 4 stat cards (models, APIs, features, cycle interval), live NOC status widget, recent NOC activity feed, and an 8-card feature grid linking to all pages.

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
Uploads a CESNET features CSV (and optionally a times CSV). Calls `POST :8003/predict_sla`. The backend runs the full 55-feature engineering pipeline before prediction. Displays violation probability and label.
**CSV needed:** CESNET feature columns + optionally a separate times file with `TIME_START`

### Traffic Forecasting (`/forecast`)
Uploads 24 rows of CESNET data plus an IP ID. Calls `POST :8004/forecast`. Displays a 6-hour forecast chart with optional Gemini-powered explanation.
**CSV needed:** 15 CESNET feature columns, 24 rows minimum, `id_ip`

### Network Simulation (`/simulation`)
Two-step workflow:
1. Upload one CSV per user to `POST :8005/api/simulate_agents` for traffic timeline + QoS metrics
2. Type a persona description to `POST :8005/agent-run` for before/after comparison + QoS verdict

**CSV needed (per user):** `hour`, `n_bytes`, `n_packets`, `n_flows`

### Green Auto-Pilot (`/auto-pilot`)
Upload a CSV for multi-agent incident investigation. 4 Gemini agents analyze the data in parallel and produce a unified report.

### MCP Demo (`/mcp`)
Single text prompt to `POST :8005/agent-run`. The Gemini agent decides which tool to call (simulation, health check, or RCA). Shows tool invocation, arguments, and plain-English summary in an agent console.

### NOC Autopilot (`/noc`)
Real-time dashboard for the autonomous SLA Guardian. Shows:
- Scheduler status (running/idle), current phase, risk level
- Live 7-phase agent loop visualization with animated phase progression
- Incident report card with severity banner, executive summary, root cause, recommendations
- Cycle history with clickable entries to review past investigations
- Manual trigger buttons: Run Cycle (normal) and Inject Breach (for testing)

---

## Frontend Design System

The frontend uses a custom dark theme with the Outfit font family and an ambient video background.

### Theme
- **Canvas:** `#08090D` (deep dark base)
- **Surfaces:** `#12141C`, `#181A24`, `#1E2130` (layered depth)
- **Borders:** `#262938` (subtle), `#1C1F2E` (extra subtle)
- **Text:** `#EAEDF3` (primary), `#B0B8C8` (secondary), `#6B7280` (muted), `#3D4455` (faint)
- **Accent palette:** Teal (`#00E8C6`), Red, Purple, Cyan, Magenta, Blue, Green, Orange, Amber

### Layout
- **Sidebar:** Collapsible (240px expanded, 68px collapsed), frosted glass (`backdrop-blur-xl`), icon-only mode when collapsed
- **TopBar:** Fixed height (56px), page title breadcrumb, sidebar toggle button, live status indicator, dataset chip, notification bell
- **Video Background:** Looping MP4 at 15% opacity behind all pages with dark overlay for readability

### Components
- `PageHeader` — Page title with icon, subtitle, and gradient divider
- `MetricCard` — Stat display with icon, value, and sublabel
- `ProgressBar` — Animated gradient progress indicator
- `SeverityBadge` — Color-coded severity labels with dot indicators
- `DatasetBanner` — Shows loaded dataset info or upload prompt
- `ToastProvider` — Toast notification system (success, error, info, warning)

---

## Data Flow — Feature by Feature

### Persona Classification

```
CSV rows (n_bytes, tcp_udp_ratio_packets, avg_duration, sum_n_dest_ip)
  -> POST :8000/classify_content
  -> scaler.transform()
  -> persona_model.predict()
  -> label_encoder.inverse_transform()
  -> [ "streamer", "gamer", ... ]
```

### Anomaly Detection

```
Single observation (5 features)
  -> POST :8001/predict
  -> anomaly_scaler.transform()
  -> isolation_forest.predict() + decision_function()
  -> shap.TreeExplainer -> feature importances
  -> { score, label, is_anomaly, explanation }
```

### Root Cause Analysis

```
IP feature row (id_ip + up to 12 metrics)
  -> POST :8002/rca
  -> align to PROFILE_FEATURES order
  -> rca_scaler.transform()
  -> kmeans.predict() -> cluster_id
  -> CAUSE_DESCRIPTIONS[cluster_id]
  -> build_report() -> human-readable report
```

### SLA Detection

```
Raw CESNET rows + optional times rows
  -> POST :8003/predict_sla
  -> ensure_subnet_key(df, "default")
  -> merge_cesnet_times_1h(df, times_df)
  -> engineer_sla_features(df, feature_cols)   # 55 features
  -> xgboost_model.predict()
  -> { prediction, probability, label }
```

### Traffic Forecasting

```
24-row CESNET sequence + ip_id
  -> POST :8004/forecast
  -> log-transform high-magnitude columns
  -> standardize with (feat_mean, feat_std)
  -> LSTM(sequence_input, embedding(ip_id))
  -> inverse-transform output
  -> 6 hourly forecasted n_bytes values
```

### Agent-Based Simulation

```
N CSV files + capacity + simulations
  -> POST :8005/api/simulate_agents
  -> extract_profile(df) per file
  -> SmartAgent(profile) per file
  -> Network(capacity_bytes)
  -> run_multiple_simulations()
  -> { traffic: [...], logs, profiles, capacity }
```

### Persona What-If Simulation

```
Existing user profiles + persona text description
  -> POST :8005/api/simulate_persona
  -> build_prompt(description)
  -> Gemini API -> JSON traffic profile
  -> llm_to_profile()
  -> SmartAgent("Persona")
  -> run_multiple_simulations(existing + persona) -> new_result
  -> impact = { max_load_increase, latency_increase }
  -> decision = "ACCEPT" if max_load < 0.85 else "REJECT"
```

### NOC Autopilot Cycle

```
Timer fires every N minutes (or manual trigger)
  -> generate_synthetic_traffic(48 hours)
  -> OBSERVE: run XGBoost SLA predictions on synthetic data
  -> if breach_prob > threshold:
       ATTRIBUTE: identify root cause features
       PLAN: select mitigation strategy
       SIMULATE: apply mitigation, re-predict
       VERIFY: check if prob dropped below threshold
       ITERATE: try alternatives if still breaching (max 3)
  -> SYNTHESIZE: Kimi K2.6 generates executive report
  -> _send_slack_alert(cycle)  # green/yellow/red
  -> store cycle in history
```

---

## The LLM / Agent Layer

### Gemini API (`utils/persona.py`)

Used for persona profile generation. Accepts a natural language description and returns a structured JSON traffic profile. Uses `google.genai.Client` with model fallback chain: `gemini-2.5-flash` -> `gemini-2.0-flash` -> `gemini-1.5-flash`.

**Input:** Free-text description ("a gamer who plays at night")
**Output:** `{ bytes_mean, bytes_std, peak_hours, traffic_type, burstiness }`

### LangChain Agent (`utils/agent_runner.py`)

Powers the `/agent-run` endpoint. Uses a manual tool-calling loop (no `AgentExecutor`) that works with any `langchain_core` version:

```
user_prompt + csv_bytes_list
  -> SystemMessage (describes all 3 tools)
  -> HumanMessage (user prompt)
  -> llm.bind_tools([run_network_simulation, check_network_health, classify_ip_root_cause])
  -> loop (max 6 iterations):
      response = llm.invoke(messages)
      if response has tool_calls:
          execute each tool -> ToolMessage
      else:
          break
  -> return { agent_called_tool, tool_args, simulation_result, summary }
```

**Tools available to the agent:**

| Tool | Module | What it does |
|------|--------|-------------|
| `run_network_simulation` | `agent_runner.py` | Calls `/api/simulate_agents` or `/api/simulate_persona` on port 8005 |
| `check_network_health` | `mcp_client.py` | Calls `GET :8002/health` — returns RCA system status |
| `classify_ip_root_cause` | `mcp_client.py` | Calls `POST :8002/rca` — returns root cause for an IP |

### Kimi K2.6 (`utils/noc_agent.py`)

Powers the NOC Autopilot report synthesis. Uses the OpenAI Python SDK pointed at Moonshot's API:

```python
client = OpenAI(api_key=MOONSHOT_KEY, base_url="https://api.moonshot.ai/v1")
resp = client.chat.completions.create(
    model="kimi-k2-0711",
    messages=[...],
    max_tokens=1024,
    temperature=0.6,
    extra_body={"thinking": {"type": "disabled"}},
)
```

Thinking mode is explicitly disabled to get concise JSON output instead of chain-of-thought reasoning.

### LangGraph Multi-Agent (`utils/incident_agent.py`)

Powers the Green Auto-Pilot. Uses LangGraph's fan-out pattern to run 4 Gemini agents in parallel, each analyzing a different aspect of the uploaded incident data.

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

Minimum columns: `hour` (0-23), `n_bytes`, `n_packets`, `n_flows`. One row per hourly observation. Each file = one user.

### CESNET Feature CSV (ports 8000, 8001, 8002, 8003, 8004)

Standard CESNET-TimeSeries24 format. Not all columns are needed by every service.

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
| `artifacts/label_encoder.joblib` | port 8000 | Label decoder (streamer/gamer/...) |
| `artifacts/anomaly_model.pkl` | port 8001 | Isolation Forest |
| `artifacts/anomaly_scaler.pkl` | port 8001 | Feature scaler for anomaly |
| `artifacts/rca_model.pkl` | port 8002 | K-Means RCA clustering model |
| `artifacts/rca_scaler.pkl` | port 8002 | Feature scaler for RCA |
| `artifacts/ip_profiles.pkl` | port 8002 | Pre-computed per-IP feature vectors |
| `artifacts/sla_model.pkl` | port 8003 | XGBoost SLA violation predictor (55 features) |
| `artifacts/sla_scaler.pkl` | port 8003 | Scaler for the 55 SLA features |
| `model_export/lstm_embedding_model.keras` | port 8004 | Per-IP LSTM forecasting model |
| `model_export/config.pkl` | port 8004 | Feature list, SEQ_LEN=24, HORIZON=6 |
| `model_export/scaler_params.pkl` | port 8004 | Forecasting scaler (mean/std per feature) |
| `model_export/ip_to_id.pkl` | port 8004 | IP-to-embedding-index mapping |

---

## Environment and Configuration

All configuration lives in a single `.env` file at the repository root. It is gitignored.

```env
GOOGLE_API_KEY=your_gemini_api_key_here
MOONSHOT_API_KEY=your_kimi_api_key_here
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/...
NOC_INTERVAL_MINUTES=10
```

| Variable | Used By | Purpose |
|----------|---------|---------|
| `GOOGLE_API_KEY` | `persona.py`, `agent_routes.py`, `agent_runner.py`, `incident_agent.py` | Gemini API access for persona generation, agent tool-calling, and multi-agent investigation |
| `MOONSHOT_API_KEY` | `noc_agent.py` | Kimi K2.6 API access for NOC report synthesis |
| `SLACK_WEBHOOK_URL` | `noc_agent.py` | Slack Incoming Webhook URL for NOC cycle alerts |
| `NOC_INTERVAL_MINUTES` | `noc_agent.py` | Interval between autonomous NOC cycles (default: 10) |
| `RCA_API_URL` | `mcp_client.py` | RCA service URL (default: `http://127.0.0.1:8002`) |

Legacy `GEMINI_API_KEY` is accepted as a fallback in Gemini-dependent files.

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

# Terminal 6 — MCP / Simulation / NOC Agent (port 8005)
uvicorn utils.mcp_api:app --host 127.0.0.1 --port 8005 --reload

# Terminal 7 — React frontend (port 3000)
cd frontend && npm run dev
```

Open `http://localhost:3000` in your browser.

**Important:** Start terminal 6 (port 8005) after the `.env` file exists. The `--reload` flag only watches `.py` files — if you add or change `.env` while uvicorn is running, restart the process for the new key to take effect. The NOC Autopilot scheduler starts automatically when port 8005 boots and will begin its first cycle after the configured interval.
