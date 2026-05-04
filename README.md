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
Start each API in a separate terminal, then launch the dashboard:

```bash
# Terminal 1 — Simulation + Persona Classification API (port 8000)
uvicorn main:app --host 127.0.0.1 --port 8000

# Terminal 2 — Anomaly Detection API (port 8001)
uvicorn utils.anomaly_api:app --host 127.0.0.1 --port 8001

# Terminal 3 — Root Cause Analysis API (port 8002)
uvicorn utils.main_RCA:app --host 127.0.0.1 --port 8002

# Terminal 4 — SLA Detection API (port 8003)
uvicorn utils.sla_api:app --host 127.0.0.1 --port 8003

# Terminal 5 — Traffic Forecasting API (port 8004)
uvicorn utils.forecasting_api:app --host 127.0.0.1 --port 8004

# Terminal 6 — Streamlit Dashboard
streamlit run app.py
```
