import { useState, useRef } from 'react'
import { useToast } from '../hooks/useToast'
import { simulationApi } from '../api/client'
import PageHeader from '../components/PageHeader'
import { Radio, Send, Terminal, CheckCircle, XCircle, Upload, X, FileText } from 'lucide-react'

const ACCENT = '#0097a7'

const EXAMPLE_PROMPTS = [
  'Simulate a network with 3 users at 4Gb capacity and check for congestion',
  'Add a heavy video streamer and assess QoS impact',
  'Run a health check on the network and classify any anomalous IPs',
]

export default function MCPDemo() {
  const toast = useToast()
  const [prompt, setPrompt] = useState('')
  const [result, setResult] = useState(null)
  const [loading, setLoading] = useState(false)
  const [log, setLog] = useState([])
  const [csvFiles, setCsvFiles] = useState([])
  const fileInputRef = useRef(null)

  function handleFileChange(e) {
    const incoming = Array.from(e.target.files || []).filter(f => f.name.endsWith('.csv'))
    if (incoming.length === 0) return
    setCsvFiles(prev => {
      const existing = new Set(prev.map(f => f.name))
      const fresh = incoming.filter(f => !existing.has(f.name))
      return [...prev, ...fresh]
    })
    // reset input so same file can be re-selected after removal
    e.target.value = ''
  }

  function removeFile(name) {
    setCsvFiles(prev => prev.filter(f => f.name !== name))
  }

  async function runAgent() {
    if (!prompt.trim()) return
    setLoading(true)
    setLog(prev => [...prev, { type: 'input', text: prompt, ts: new Date().toLocaleTimeString() }])
    if (csvFiles.length > 0) {
      setLog(prev => [...prev, {
        type: 'system',
        text: `Attaching ${csvFiles.length} CSV file(s): ${csvFiles.map(f => f.name).join(', ')}`,
        ts: new Date().toLocaleTimeString(),
      }])
    }

    try {
      const fd = new FormData()
      fd.append('prompt', prompt)
      csvFiles.forEach(f => fd.append('files', f))
      const res = await simulationApi.agentRun(fd)
      setResult(res)
      setLog(prev => [
        ...prev,
        {
          type: res.agent_called_tool ? 'tool' : 'response',
          text: res.agent_called_tool
            ? `Tool called: ${JSON.stringify(res.tool_args ?? {})}`
            : 'No tool was invoked',
          ts: new Date().toLocaleTimeString(),
        },
        { type: 'response', text: res.summary ?? '(no summary)', ts: new Date().toLocaleTimeString() },
      ])
      toast('Agent run complete', 'success')
    } catch (e) {
      setLog(prev => [...prev, { type: 'error', text: e.message, ts: new Date().toLocaleTimeString() }])
      toast(`Agent error: ${e.message}`, 'error')
    } finally {
      setLoading(false)
      setPrompt('')
    }
  }

  const LOG_STYLE = {
    input:    'text-accent-teal',
    tool:     'text-purple-400',
    response: 'text-text-primary',
    error:    'text-red-400',
    system:   'text-text-faint',
  }

  return (
    <div className="max-w-3xl animate-fade-in">
      <PageHeader
        title="MCP Demo"
        subtitle="Live demonstration of the MCP bridge and LangChain + Kimi K2.6 agent orchestration layer. Type a natural language command and watch the agent decide which tools to invoke."
        accent={ACCENT}
      />

      {/* Architecture badge */}
      <div className="flex items-center gap-3 mb-6 p-4 bg-surface border border-border rounded-sm">
        <Radio size={14} style={{ color: ACCENT }} className="shrink-0" />
        <div className="text-xs text-text-muted">
          <span className="font-semibold text-text-primary">Architecture:</span>
          {' '}React → FastAPI /agent-run → LangChain Agent → Kimi K2.6 (Moonshot) → MCP Tools
          (simulate_agents, check_network_health, classify_ip_root_cause)
        </div>
      </div>

      {/* CSV Upload */}
      <div className="card p-4 mb-4">
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <Upload size={13} style={{ color: ACCENT }} />
            <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">
              Upload CSV Files
            </span>
          </div>
          <span className="text-xs text-text-faint">
            Each file represents one network user (columns: hour, n_bytes, n_packets, n_flows)
          </span>
        </div>

        {/* Drop zone */}
        <label
          className="flex flex-col items-center justify-center gap-2 border-2 border-dashed border-border rounded-sm p-5 cursor-pointer hover:border-accent-teal-border transition-colors mb-3"
          style={{ minHeight: 80 }}
        >
          <input
            ref={fileInputRef}
            type="file"
            accept=".csv"
            multiple
            className="hidden"
            onChange={handleFileChange}
          />
          <Upload size={18} className="text-text-faint" />
          <span className="text-xs text-text-faint text-center">
            Click or drag &amp; drop CSV files here<br />
            <span className="text-text-faint opacity-60">(multiple files accepted)</span>
          </span>
        </label>

        {/* File chips */}
        {csvFiles.length > 0 && (
          <div className="flex flex-wrap gap-2">
            {csvFiles.map(f => (
              <div
                key={f.name}
                className="flex items-center gap-1.5 px-2.5 py-1 bg-surface-2 border border-border rounded-sm text-xs text-text-muted"
              >
                <FileText size={11} style={{ color: ACCENT }} />
                <span className="font-mono">{f.name}</span>
                <span className="text-text-faint ml-1">({(f.size / 1024).toFixed(1)} KB)</span>
                <button
                  onClick={() => removeFile(f.name)}
                  className="ml-1 text-text-faint hover:text-red-400 transition-colors"
                  title="Remove"
                >
                  <X size={11} />
                </button>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Terminal / log */}
      <div className="card overflow-hidden mb-4">
        <div className="flex items-center justify-between px-4 py-2 bg-surface-2 border-b border-border">
          <div className="flex items-center gap-2">
            <Terminal size={13} style={{ color: ACCENT }} />
            <span className="text-xs font-semibold text-text-muted uppercase tracking-wider">Agent Console</span>
          </div>
          <button onClick={() => setLog([])} className="btn-ghost text-xs">Clear</button>
        </div>
        <div className="bg-canvas p-4 font-mono text-xs leading-relaxed min-h-[220px] max-h-[360px] overflow-y-auto">
          {log.length === 0 ? (
            <span className="text-text-faint">Waiting for agent input…</span>
          ) : (
            log.map((entry, i) => (
              <div key={i} className="mb-2">
                <span className="text-text-faint mr-2">[{entry.ts}]</span>
                <span className={LOG_STYLE[entry.type] || 'text-text-primary'}>
                  {entry.type === 'input' && '> '}
                  {entry.type === 'tool' && '⚙ '}
                  {entry.type === 'error' && '✖ '}
                  {entry.text}
                </span>
              </div>
            ))
          )}
          {loading && (
            <div className="flex items-center gap-2 text-text-faint">
              <span className="animate-pulse">● ● ●</span>
              <span>Agent thinking…</span>
            </div>
          )}
        </div>
      </div>

      {/* Input */}
      <div className="flex gap-3 mb-5">
        <input
          className="input flex-1"
          placeholder="Describe a scenario for the agent…"
          value={prompt}
          onChange={e => setPrompt(e.target.value)}
          onKeyDown={e => e.key === 'Enter' && !loading && runAgent()}
        />
        <button
          onClick={runAgent}
          disabled={loading || !prompt.trim()}
          className="flex items-center gap-2 px-4 py-2 font-semibold text-sm transition-all"
          style={{
            background: loading || !prompt.trim() ? '#1C2128' : ACCENT,
            color: loading || !prompt.trim() ? '#484F58' : '#0D1117',
          }}
        >
          <Send size={13} />
          {loading ? 'Running…' : 'Run'}
        </button>
      </div>

      {/* Example prompts */}
      <div className="mb-6">
        <div className="label">Example prompts</div>
        <div className="flex flex-col gap-2">
          {EXAMPLE_PROMPTS.map((p, i) => (
            <button
              key={i}
              onClick={() => setPrompt(p)}
              className="text-left px-3 py-2 bg-surface-2 border border-border hover:border-accent-teal-border text-xs text-text-muted hover:text-text-primary transition-colors rounded-sm font-mono"
            >
              {p}
            </button>
          ))}
        </div>
      </div>

      {/* Last result detail */}
      {result && (
        <div className="card p-5 animate-fade-in">
          <div className="section-title">Last Agent Run</div>
          <div className="flex items-center gap-3 mb-4">
            {result.agent_called_tool
              ? <><CheckCircle size={14} className="text-green-400" /><span className="text-xs text-green-400 font-semibold">Tool was invoked</span></>
              : <><XCircle size={14} className="text-text-muted" /><span className="text-xs text-text-muted">No tool invoked (answered from context)</span></>
            }
          </div>
          {result.tool_args && (
            <div className="mb-4">
              <div className="label">Tool Arguments</div>
              <pre className="text-xs font-mono text-text-muted bg-canvas border border-border p-3 rounded-sm overflow-x-auto">
                {JSON.stringify(result.tool_args, null, 2)}
              </pre>
            </div>
          )}
          {result.simulation_result && (
            <div className="mb-4">
              <div className="label">Simulation Result</div>
              <pre className="text-xs font-mono text-text-muted bg-canvas border border-border p-3 rounded-sm overflow-x-auto max-h-40">
                {JSON.stringify(result.simulation_result, null, 2)}
              </pre>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
