# Project Title
QoS Buddy
## Overview  
This project is an agent-based network traffic simulation designed to model and analyze data flow in a virtual environment (e.g., a smart town or warehouse system). It simulates user behavior, network congestion, and Quality of Service (QoS) metrics, with the goal of enabling prediction and optimization using machine learning.

## Features  
- Agent-based simulation of network traffic  
- Real-time congestion modeling  
- QoS metrics tracking (latency, throughput, packet loss)  
- Scenario-based simulation (varying loads and behaviors)  
- Data collection for analysis and model training  
- Machine learning integration for prediction and optimization  

## Tech Stack  

### Frontend  
- Dashboard for visualization (charts, metrics, simulation state)  
- Tools: React, Plotly (or similar)

### Backend  
- Simulation engine (agent logic + environment)  
- Data processing and storage  
- ML model integration  
- Tools: Python, Flask/FastAPI, TensorFlow/PyTorch  

## Architecture  
The system follows a modular architecture:  
- **Agents Layer**: Simulates users/devices generating traffic  
- **Environment Layer**: Models the network (nodes, links, congestion)  
- **Simulation Engine**: Handles interactions and time-based events  
- **Data Layer**: Collects and stores QoS metrics  
- **ML Layer**: Predicts congestion and suggests optimizations  
- **Visualization Layer**: Displays results and insights  

## Contributors  
- Haroun Zriba  
- Muaadh AlSoumhi
- Rayen Krimi
- Omar Mezoughi
- Mohamed Ayman Hamzaoui
- Fares Hasni
- Zayneb Maatoug

## Academic Context  
This project was developed as part of the PIDS – 4th Year Engineering Program at Esprit School of Engineering (Academic Year 2025–2026).

## Getting Started  

### Prerequisites  
- Python 3.10+  

### Installation  
```bash
git clone https://github.com/zrharounesprit/Esprit-PIDS-4DS1-2026-QoSBuddy.git
cd Esprit-PIDS-4DS1-2026-QoSBuddy
pip install -r requirements.txt
```

### Environment setup
```bash
cp .env.example .env
# Edit .env and add your GOOGLE_API_KEY
```
### Start frontend   

```bash
cd frontend
npm install
npm run dev   # → http://localhost:3000
```

### Running

Start each service in a **separate terminal** from the repo root, then open the React frontend:

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

# Terminal 6 — MCP / Simulation API (port 8005)
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
| MCP / Simulation | `utils.mcp_api:app` | 8005 |
| React Frontend | `npm run dev` (in `frontend/`) | 3000 |

### Testing each model

| Page | Minimum CSV columns needed |
|---|---|
| Anomaly Detection | `n_bytes`, `n_packets`, `n_flows`, `tcp_udp_ratio_packets`, `dir_ratio_packets` |
| Root Cause Analysis | `id_ip`, `n_flows`, `n_packets`, `n_bytes`, `sum_n_dest_ip`, `sum_n_dest_ports`, `avg_duration`, `avg_ttl`, ratio cols |
| SLA Detection | All CESNET cols + `datetime`/`timestamp` (or `id_time` + upload `times_1_hour.csv`) |
| Traffic Forecasting | All 15 CESNET feature cols — needs ≥ 24 consecutive hourly rows |
| Persona Classification | `n_bytes`, `tcp_udp_ratio_packets`, `avg_duration`, `sum_n_dest_ip` |
| Simulation | Per-user CSV with `n_bytes`, `n_packets`, `n_flows`, `avg_duration` |
