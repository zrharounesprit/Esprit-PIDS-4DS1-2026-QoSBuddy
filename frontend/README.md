# QoSBuddy React Frontend

A dark-mode React SPA replacing the Streamlit dashboard.

## Stack
- **React 18** + **React Router v6** — client-side routing
- **Vite** — build tooling
- **Tailwind CSS** — utility-first styling with custom design tokens
- **Recharts** — charts (line, composed, scatter)
- **Lucide React** — icons

## Getting Started

```bash
cd frontend
npm install
npm run dev
```

The app runs at **http://localhost:3000**

> Make sure all backend APIs are running first (see the root README).

## Build for production

```bash
npm run build    # outputs to dist/
npm run preview  # preview the production build locally
```

## Design System

Custom Tailwind tokens are defined in `tailwind.config.js`:

| Token | Value | Usage |
|-------|-------|-------|
| `canvas` | `#0D1117` | Page background |
| `surface` | `#161B22` | Cards, sidebar |
| `surface-2` | `#1C2128` | Hover states, nested cards |
| `border` | `#30363D` | Card borders |
| `text-primary` | `#E6EDF3` | Main text |
| `text-muted` | `#7D8590` | Labels, captions |
| `accent-teal` | `#00FFD5` | Simulation, primary brand |
| `accent-red` | `#F04444` | Anomaly detection |
| `accent-purple` | `#8B7CF8` | Root Cause Analysis |
| `accent-cyan` | `#22D3EE` | SLA Detection |
| `accent-magenta` | `#E040FB` | Persona Classification |
| `accent-blue` | `#3B82F6` | Traffic Forecasting |
| `accent-green` | `#22C55E` | Upload, success states |

## Pages

| Route | Component | API Port |
|-------|-----------|----------|
| `/` | Home | — |
| `/upload` | Upload | — (client-side CSV parse) |
| `/anomaly` | Anomaly Detection | 8001 |
| `/rca` | Root Cause Analysis | 8002 |
| `/sla` | SLA Detection | 8003 |
| `/persona` | Persona Classification | 8000 |
| `/forecast` | Traffic Forecasting | 8004 |
| `/simulation` | Network Simulation | 8000 |
| `/mcp` | MCP Demo | 8000 |

## Project Structure

```
src/
├── api/
│   └── client.js          # All API calls, one function per endpoint
├── components/
│   ├── DatasetBanner.jsx   # Global dataset status in topbar
│   ├── Layout.jsx          # Sidebar + topbar shell
│   ├── MetricCard.jsx      # KPI display card
│   ├── PageHeader.jsx      # Page title + accent gradient
│   ├── ProgressBar.jsx     # Animated progress bar
│   ├── Sidebar.jsx         # Navigation with active indicators
│   └── SeverityBadge.jsx   # Color-coded severity labels
├── context/
│   └── DatasetContext.jsx  # Global CSV dataset state (React Context)
├── hooks/
│   └── useToast.jsx        # Toast notification system
├── pages/
│   ├── Home.jsx
│   ├── Upload.jsx
│   ├── AnomalyDetection.jsx
│   ├── RootCauseAnalysis.jsx
│   ├── SLADetection.jsx
│   ├── PersonaClassification.jsx
│   ├── Forecasting.jsx
│   ├── Simulation.jsx
│   └── MCPDemo.jsx
├── App.jsx                 # Router
├── main.jsx                # Entry point
└── index.css               # Tailwind directives + base styles
```
