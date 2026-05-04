@echo off
REM ============================================================
REM  QoSBuddy — Dev Start Script (Windows)
REM  Opens each service in its own terminal window.
REM  Run from the project root:  start_dev.bat
REM ============================================================

echo Starting QoSBuddy dev stack...

REM Persona Classification — port 8000
start "QoSBuddy | Persona :8000" cmd /k ".venv\Scripts\activate && uvicorn main:app --host 127.0.0.1 --port 8000 --reload"

REM Anomaly Detection — port 8001
start "QoSBuddy | Anomaly :8001" cmd /k ".venv\Scripts\activate && uvicorn utils.anomaly_api:app --host 127.0.0.1 --port 8001 --reload"

REM Root Cause Analysis — port 8002
start "QoSBuddy | RCA :8002" cmd /k ".venv\Scripts\activate && uvicorn utils.main_RCA:app --host 127.0.0.1 --port 8002 --reload"

REM SLA Detection — port 8003
start "QoSBuddy | SLA :8003" cmd /k ".venv\Scripts\activate && uvicorn utils.sla_api:app --host 127.0.0.1 --port 8003 --reload"

REM Traffic Forecasting — port 8004
start "QoSBuddy | Forecasting :8004" cmd /k ".venv\Scripts\activate && uvicorn utils.forecasting_api:app --host 127.0.0.1 --port 8004 --reload"

REM MCP / Simulation + Agent — port 8005
start "QoSBuddy | MCP+Sim :8005" cmd /k ".venv\Scripts\activate && uvicorn utils.mcp_api:app --host 127.0.0.1 --port 8005 --reload"

REM React Frontend — port 3000
start "QoSBuddy | Frontend :3000" cmd /k "cd frontend && npm run dev"

echo.
echo All services started in separate windows.
echo.
echo   Persona Classification  ->  http://127.0.0.1:8000
echo   Anomaly Detection       ->  http://127.0.0.1:8001
echo   Root Cause Analysis     ->  http://127.0.0.1:8002
echo   SLA Detection           ->  http://127.0.0.1:8003
echo   Traffic Forecasting     ->  http://127.0.0.1:8004
echo   MCP / Simulation        ->  http://127.0.0.1:8005
echo   React Frontend          ->  http://localhost:3000
echo.
echo Close each terminal window to stop that service.
pause
