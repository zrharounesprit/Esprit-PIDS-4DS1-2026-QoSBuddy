# QoSBuddy
**Intelligent Network Quality-of-Service Analysis & Autonomous Monitoring Platform**

## Overview
QoSBuddy is a full-stack network traffic analysis platform that combines six ML-powered features with an autonomous NOC (Network Operations Center) agent. It simulates, detects, and mitigates QoS issues using a suite of microservices, LLM-driven agents, and a modern React dashboard.

Built by **Team VizBiz** at Esprit School of Engineering (4DS1 — 2025/2026).

## Features

| Feature | Model / Engine | Description |
|---------|---------------|-------------|
| Persona Classification | Random Forest / SVM | Classifies IPs into user types (streamer, gamer, scroller, researcher, connector) |
| Anomaly Detection | Isolation Forest + SHAP | Detects anomalous traffic patterns with explainable feature importance |
| Root Cause Analysis | K-Means Clustering | Maps anomalies to human-readable root causes (port scan, DDoS, etc.) |
| SLA Detection | XGBoost (55 features) | Predicts SLA violations using 55 engineered time-series features |
| Traffic Forecasting | LSTM + IP Embeddings | Forecasts 6-hour traffic per-IP from 24-hour sliding windows |
| Network Simulation | Agent-Based + Gemini LLM | Simulates multi-user traffic with what-if persona injection |
| Green Auto-Pilot | LangGraph + 4 Gemini Agents | Multi-agent incident investigation with fan-out architecture |
| NOC Autopilot (SLA Guardian) | 7-phase Agent Loop + Kimi K2.6 | Autonomous SLA monitoring with breach detection, mitigation simulation, and Slack alerts |

## Tech Stack

### Frontend
- **React 18** + Vite + Tailwind CSS
- Outfit font, dark theme with ambient video background
- Recharts for data visualization
- Lucide icons, frosted glass UI components

### Backend
- **FastAPI** microservices (6 ports: 8000–8005)
- Python 3.10+, scikit-learn, TensorFlow/Keras, XGBoost
- LangChain + Google Gemini for agent orchestration
- Kimi K2.6 (Moonshot API) for NOC report synthesis
- Slack Incoming Webhooks for alert delivery

## Architecture

```
                        React Frontend (port 3000)
                        Outfit font · Video BG · Frosted glass UI
                               │
       ┌───────────┬───────────┼───────────┬───────────┬───────────┐
       │           │           │           │           │           │
   port 8000   port 8001   port 8002   port 8003   port 8004   port 8005
   Persona     Anomaly      RCA         SLA       Forecast    MCP/Sim
   main.py   anomaly_api  main_RCA    sla_api   forecast    mcp_api
                                         │        _api        │
                                    sla_pipeline          ┌───┴───┐
                                    sla_preprocess     agent_   noc_
                                                      routes   agent
                                                        │       │
                                                    Gemini    Kimi K2.6
                                                      API    + Slack
```

## Getting Started

### Prerequisites
- Python 3.10+
- Node.js 18+
- npm

### Installation
```bash
git clone https://github.com/zrharounesprit/Esprit-PIDS-4DS1-2026-QoSBuddy.git
cd Esprit-PIDS-4DS1-2026-QoSBuddy
pip install -r requirements.txt
```

### Environment setup
```bash
cp .env.example .env
# Edit .env and add your API keys:
#   GOOGLE_API_KEY        — Gemini API key (agent simulation, auto-pilot)
#   MOONSHOT_API_KEY      — Kimi K2.6 key (NOC report synthesis)
#   SLACK_WEBHOOK_URL     — Slack Incoming Webhook (NOC alerts)
#   NOC_INTERVAL_MINUTES  — NOC cycle interval (default: 10)
```

### Start frontend
```bash
cd frontend
npm install
npm run dev   # → http://localhost:3000
```

### Running all services

Start each service in a **separate terminal** from the repo root:

```bash
# Terminal 1 — Persona Classification API (port 8000)
uvicorn main:app --host 127.0.0.1 --port 8000 --reload

# Terminal 2 — Anomaly Detection API (port 8001)
uvicorn utils.anomaly_api:app --host 127.0.0.1 --port 8001 --reload

# Terminal 3 — Root Cause Analysis API (port 8002)
uvicorn utils.main_RCA:app --host 127.0.0.1 --port 8002 --reload

# Terminal 4 — SLA Detection API (port 8003)
uvicorn utils.sla_api:app --host 127.0.0.1 --port 8003 --reload

# Terminal 5 — Traffic Forecasting API (port 8004)
uvicorn utils.forecasting_api:app --host 127.0.0.1 --port 8004 --reload

# Terminal 6 — MCP / Simulation / NOC API (port 8005)
uvicorn utils.mcp_api:app --host 127.0.0.1 --port 8005 --reload

# Terminal 7 — React Frontend (port 3000)
cd frontend && npm install && npm run dev
```

Open **http://localhost:3000** in your browser.

### Service port map

| Service | Entrypoint | Port |
|---|---|---|
| Persona Classification | `main:app` | 8000 |
| Anomaly Detection | `utils.anomaly_api:app` | 8001 |
| Root Cause Analysis | `utils.main_RCA:app` | 8002 |
| SLA Detection | `utils.sla_api:app` | 8003 |
| Traffic Forecasting | `utils.forecasting_api:app` | 8004 |
| MCP / Simulation / NOC | `utils.mcp_api:app` | 8005 |
| React Frontend | `npm run dev` (in `frontend/`) | 3000 |

### Testing each model

| Page | Minimum CSV columns needed |
|---|---|
| Anomaly Detection | `n_bytes`, `n_packets`, `n_flows`, `tcp_udp_ratio_packets`, `dir_ratio_packets` |
| Root Cause Analysis | `id_ip`, `n_flows`, `n_packets`, `n_bytes`, `sum_n_dest_ip`, `sum_n_dest_ports`, `avg_duration`, `avg_ttl`, ratio cols |
| SLA Detection | All CESNET cols + `datetime`/`timestamp` (or `id_time` + upload `times_1_hour.csv`) |
| Traffic Forecasting | All 15 CESNET feature cols — needs 24+ consecutive hourly rows |
| Persona Classification | `n_bytes`, `tcp_udp_ratio_packets`, `avg_duration`, `sum_n_dest_ip` |
| Simulation | Per-user CSV with `n_bytes`, `n_packets`, `n_flows`, `avg_duration` |
| Green Auto-Pilot | Uses uploaded dataset from context — no separate CSV needed |
| NOC Autopilot | Fully autonomous — generates synthetic traffic internally |

## Contributors
- Haroun Zriba
- Muaadh AlSoumhi
- Rayen Krimi
- Omar Mezoughi
- Mohamed Ayman Hamzaoui
- Fares Hasni
- Zayneb Maatoug

## Academic Context
This project was developed as part of the PIDS program, 4th Year Engineering at Esprit School of Engineering (Academic Year 2025-2026).
