// Centralised API client for all QoSBuddy backend services
// Ports:
//   8000 → Persona Classification (main.py)
//   8001 → Anomaly Detection      (utils/anomaly_api.py)
//   8002 → Root Cause Analysis    (utils/main_RCA.py)
//   8003 → SLA Detection          (utils/sla_api.py)
//   8004 → Traffic Forecasting    (utils/forecasting_api.py)
//   8005 → MCP / Simulation       (utils/mcp_api.py)

const BASE = {
  persona:    'http://127.0.0.1:8000',
  anomaly:    'http://127.0.0.1:8001',
  rca:        'http://127.0.0.1:8002',
  sla:        'http://127.0.0.1:8003',
  forecast:   'http://127.0.0.1:8004',
  simulation: 'http://127.0.0.1:8005',
}

async function post(url, body) {
  const res = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

async function get(url) {
  const res = await fetch(url)
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

// multipart/form-data — do NOT set Content-Type; browser adds the boundary automatically
async function postForm(url, formData) {
  const res = await fetch(url, { method: 'POST', body: formData })
  if (!res.ok) {
    const text = await res.text()
    throw new Error(`${res.status}: ${text}`)
  }
  return res.json()
}

// ── Anomaly Detection ─────────────────────────────────────────────────────────
export const anomalyApi = {
  predict: (payload) => post(`${BASE.anomaly}/predict_anomaly`, payload),
}

// ── Root Cause Analysis ───────────────────────────────────────────────────────
export const rcaApi = {
  analyse: (payload) => post(`${BASE.rca}/rca`, payload),
  getByIp: (id_ip)  => get(`${BASE.rca}/rca/ip/${id_ip}`),
  health:  ()        => get(`${BASE.rca}/health`),
}

// ── SLA Detection ─────────────────────────────────────────────────────────────
export const slaApi = {
  metadata: () => get(`${BASE.sla}/sla_metadata`),
  predict:  (payload) => post(`${BASE.sla}/predict_sla`, payload),
}

// ── Traffic Forecasting ───────────────────────────────────────────────────────
export const forecastApi = {
  run: (rows, ip_id = 0) => post(`${BASE.forecast}/forecast`, { rows, ip_id }),
}

// ── Persona Classification ────────────────────────────────────────────────────
export const personaApi = {
  classify: (payload) => post(`${BASE.persona}/classify_content`, payload),
}

// ── Network Simulation / MCP ──────────────────────────────────────────────────
// Both runAgents and agentRun use multipart/form-data (FastAPI Form/File fields)
// runPersona uses JSON body (Pydantic BaseModel)
export const simulationApi = {
  runAgents:  (formData) => postForm(`${BASE.simulation}/api/simulate_agents`, formData),
  runPersona: (payload)  => post(`${BASE.simulation}/api/simulate_persona`, payload),
  agentRun:   (formData) => postForm(`${BASE.simulation}/agent-run`, formData),
}

// ── Autopilot — multi-model incident investigation ────────────────────────────
export const autopilotApi = {
  analyze: (formData) => postForm(`${BASE.simulation}/incident-analyze`, formData),
}

// ── NOC Autopilot — SLA Guardian agentic loop ─────────────────────────────────
export const nocApi = {
  status:  ()                    => get(`${BASE.simulation}/noc/status`),
  history: (limit = 10)          => get(`${BASE.simulation}/noc/history?limit=${limit}`),
  trigger: (inject_breach = false) =>
    post(`${BASE.simulation}/noc/trigger?inject_breach=${inject_breach}`, {}),
}

