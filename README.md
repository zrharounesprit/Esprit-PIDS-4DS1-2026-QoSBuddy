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

### Running  
Start each API in a separate terminal, then launch the dashboard:

```bash
# Terminal 1 — Anomaly Detection API
uvicorn utils.anomaly_api:app --host 127.0.0.1 --port 8001

# Terminal 2 — Root Cause Analysis API
uvicorn utils.main_RCA:app --host 127.0.0.1 --port 8002

# Terminal 3 — SLA Detection API
uvicorn utils.sla_api:app --host 127.0.0.1 --port 8003

# Terminal 4 — Streamlit Dashboard
streamlit run app.py
```
