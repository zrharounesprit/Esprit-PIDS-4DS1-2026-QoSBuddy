// Centralised API client for all QoSBuddy backend services
// Ports: anomaly=8001, rca=8002, sla=8003, forecast=8004, simulation/persona=8000

const BASE = {
  simulation: 'http://127.0.0.1:8000',
  anomaly:    'http://127.0.0.1:8001',
  rca:        'http://127.0.0.1:8002',
  sla:        'http://127.0.0.1:8003',
  forecast:   'http://127.0.0.1:8004',
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
  classify: (payload) => post(`${BASE.simulation}/classify_content`, payload),
}

// ── Network Simulation ────────────────────────────────────────────────────────
export const simulationApi = {
  runAgents:  (payload) => post(`${BASE.simulation}/simulate_agents`, payload),
  runPersona: (payload) => post(`${BASE.simulation}/simulate_persona`, payload),
  agentRun:   (payload) => post(`${BASE.simulation}/agent-run`, payload),
}
