import streamlit as st
import pandas as pd
import numpy as np
import requests
import os
import pickle

API_URL = "http://127.0.0.1:8006"
BASE    = os.path.join(os.path.dirname(__file__),
                       '..', 'artifacts')

def load(name):
    with open(os.path.join(BASE, name), 'rb') as f:
        return pickle.load(f)

def badge(level, score):
    colors = {
        "CRITICAL": ("#E74C3C", "#3a1010"),
        "HIGH":     ("#E67E22", "#3a2010"),
        "MEDIUM":   ("#F1C40F", "#3a3010"),
        "LOW":      ("#5DCAA5", "#0a3a2a")
    }
    fg, bg = colors.get(level, ("#888", "#222"))
    return (
        f"<span style='background:{bg};color:{fg};"
        f"padding:3px 10px;border-radius:20px;"
        f"font-size:11px;font-weight:700;"
        f"border:1px solid {fg}44'>"
        f"{level} · {score}%</span>"
    )

def safe_val(bl, key, field='median'):
    try:
        return float(bl[key][field])
    except Exception:
        try:
            return float(bl[key]['mean'])
        except Exception:
            return 0.0

def show():
    st.markdown("""
        <div style='padding:1rem 0 0.5rem'>
            <span style='color:#5DCAA5;font-size:11px;
                         letter-spacing:2px'>
                BO2 · ROOT CAUSE ANALYSIS
            </span>
            <h2 style='color:white;margin:4px 0 2px'>
                Correlation Impact Simulator
            </h2>
            <p style='color:#666;font-size:13px;
                      margin:0'>
                Input new network KPI data and see how
                it affects correlations and triggers
                root causes
            </p>
        </div>
        <hr style='border-color:#2a2a2a;
                   margin:0.5rem 0 1rem'>
    """, unsafe_allow_html=True)

    # ── API health check ───────────────────────────────────
    try:
        health = requests.get(
            f"{API_URL}/health", timeout=2
        )
        api_ok = health.status_code == 200
    except Exception:
        api_ok = False

    if not api_ok:
        st.error(
            "FastAPI is not running. "
            "Open a terminal and run: "
            "uvicorn fastapi_endpoint:app "
            "--reload --port 8000"
        )
        return

    st.markdown(
        "<div style='color:#5DCAA5;font-size:11px;"
        "margin-bottom:1rem'>● API connected</div>",
        unsafe_allow_html=True
    )

    tab1, tab2, tab3 = st.tabs([
        "Manual Input",
        "Upload CSV",
        "Baseline Explorer"
    ])

    # ══════════════════════════════════════════════════════
    # TAB 1 — Manual Input
    # ══════════════════════════════════════════════════════
    with tab1:
        st.markdown("#### Enter KPI values manually")
        st.markdown(
            "<p style='color:#666;font-size:12px'>"
            "Adjust the values to simulate different "
            "network conditions. Default values "
            "represent typical normal traffic.</p>",
            unsafe_allow_html=True
        )

        # ── Quick guide ────────────────────────────────────
        st.markdown("""
            <div style='background:#0d1f0d;
                border:1px solid #1a3a1a;
                border-radius:8px;
                padding:12px 16px;
                margin-bottom:1.2rem;
                font-size:12px;
                line-height:1.8'>
                <div style='color:#5DCAA5;
                    font-weight:600;
                    margin-bottom:4px'>
                    Quick guide — how to reach
                    each risk level
                </div>
                <div style='color:#9FE1CB'>
                    🟢 <b>LOW</b> — keep all values
                    at default
                </div>
                <div style='color:#F1C40F'>
                    🟡 <b>MEDIUM</b> — set
                    dir_ratio_packets=0.70,
                    dir_ratio_bytes=0.65,
                    avg_ttl=35,
                    avg_duration=0.8
                </div>
                <div style='color:#E67E22'>
                    🟠 <b>HIGH</b> — set
                    sum_n_dest_ports=320,
                    sum_n_dest_ip=380,
                    dir_ratio_packets=0.88,
                    avg_duration=0.4,
                    avg_ttl=48
                </div>
                <div style='color:#E74C3C'>
                    🔴 <b>CRITICAL</b> — set
                    n_flows=45000,
                    n_packets=9200000,
                    n_bytes=520000000,
                    tcp_udp_ratio_packets=0.02,
                    dir_ratio_packets=0.97,
                    sum_n_dest_ip=4
                </div>
            </div>
        """, unsafe_allow_html=True)

        try:
            bl = requests.get(
                f"{API_URL}/baseline", timeout=3
            ).json()['kpis']
        except Exception:
            st.error("Cannot load baseline from API")
            return

        scenario = st.text_input(
            "Scenario name",
            value="My simulation"
        )

        # ── Volumetric KPIs ────────────────────────────────
        st.markdown("**Volumetric KPIs**")
        st.markdown(
            "<p style='color:#555;font-size:11px'>"
            "How much traffic this device generated "
            "in the time window.</p>",
            unsafe_allow_html=True
        )
        c1, c2, c3 = st.columns(3)

        n_flows = c1.number_input(
            "n_flows",
            min_value=0.0,
            value=safe_val(bl, 'n_flows'),
            step=10.0,
            help="Number of separate connections"
        )
        n_packets = c2.number_input(
            "n_packets",
            min_value=0.0,
            value=safe_val(bl, 'n_packets'),
            step=100.0,
            help="Total packets sent and received"
        )
        n_bytes = c3.number_input(
            "n_bytes",
            min_value=0.0,
            value=safe_val(bl, 'n_bytes'),
            step=1000.0,
            help="Total bytes transferred"
        )

        # ── Destination KPIs ───────────────────────────────
        st.markdown("**Destination KPIs**")
        st.markdown(
            "<p style='color:#555;font-size:11px'>"
            "How many different places this device "
            "communicated with. High values relative "
            "to flows suggest scanning.</p>",
            unsafe_allow_html=True
        )
        c4, c5, c6 = st.columns(3)

        sum_n_dest_ip = c4.number_input(
            "sum_n_dest_ip",
            min_value=0.0,
            value=safe_val(bl, 'sum_n_dest_ip'),
            step=1.0,
            help="Total unique destination IPs"
        )
        average_n_dest_ip = c5.number_input(
            "average_n_dest_ip",
            min_value=0.0,
            value=safe_val(bl, 'average_n_dest_ip'),
            step=0.1,
            help="Average unique IPs per flow"
        )
        sum_n_dest_ports = c6.number_input(
            "sum_n_dest_ports",
            min_value=0.0,
            value=safe_val(bl, 'sum_n_dest_ports'),
            step=1.0,
            help="Total unique ports contacted"
        )

        c7, c8, c9 = st.columns(3)
        average_n_dest_ports = c7.number_input(
            "average_n_dest_ports",
            min_value=0.0,
            value=safe_val(bl,
                           'average_n_dest_ports'),
            step=0.1,
            help="Average unique ports per flow"
        )
        sum_n_dest_asn = c8.number_input(
            "sum_n_dest_asn",
            min_value=0.0,
            value=safe_val(bl, 'sum_n_dest_asn'),
            step=1.0,
            help="Total unique organizations reached"
        )
        average_n_dest_asn = c9.number_input(
            "average_n_dest_asn",
            min_value=0.0,
            value=safe_val(bl, 'average_n_dest_asn'),
            step=0.1,
            help="Average unique ASNs per flow"
        )

        # ── Protocol & Direction Ratios ────────────────────
        st.markdown("**Protocol & Direction Ratios**")
        st.markdown(
            "<p style='color:#555;font-size:11px'>"
            "All values 0–1. TCP/UDP: 1=all TCP, "
            "0=all UDP. Direction: 1=all outgoing, "
            "0=all incoming.</p>",
            unsafe_allow_html=True
        )
        c10, c11, c12 = st.columns(3)

        tcp_udp_ratio_packets = c10.slider(
            "tcp_udp_ratio_packets",
            0.0, 1.0,
            safe_val(bl, 'tcp_udp_ratio_packets'),
            step=0.01,
            help="1=all TCP · 0=all UDP (packets)"
        )
        tcp_udp_ratio_bytes = c11.slider(
            "tcp_udp_ratio_bytes",
            0.0, 1.0,
            safe_val(bl, 'tcp_udp_ratio_bytes'),
            step=0.01,
            help="1=all TCP · 0=all UDP (bytes)"
        )
        dir_ratio_packets = c12.slider(
            "dir_ratio_packets",
            0.0, 1.0,
            safe_val(bl, 'dir_ratio_packets'),
            step=0.01,
            help="1=all outgoing · 0=all incoming"
        )

        c13, c14, c15 = st.columns(3)
        dir_ratio_bytes = c13.slider(
            "dir_ratio_bytes",
            0.0, 1.0,
            safe_val(bl, 'dir_ratio_bytes'),
            step=0.01,
            help="1=all outgoing · 0=all incoming"
        )
        avg_duration = c14.number_input(
            "avg_duration (seconds)",
            min_value=0.0,
            value=safe_val(bl, 'avg_duration'),
            step=0.5,
            help="Average flow duration in seconds"
        )
        avg_ttl = c15.number_input(
            "avg_ttl",
            min_value=0.0,
            value=safe_val(bl, 'avg_ttl'),
            step=1.0,
            help=(
                "Average Time To Live. "
                "Low values suggest spoofed or "
                "far-origin traffic"
            )
        )

        # ── Temporal ───────────────────────────────────────
        st.markdown("**Temporal context**")
        ct1, ct2, ct3 = st.columns(3)
        hour = ct1.slider(
            "Hour of day", 0, 23, 12,
            help="0=midnight · 12=noon · 23=11pm"
        )
        dayofweek = ct2.selectbox(
            "Day of week",
            [0, 1, 2, 3, 4, 5, 6],
            format_func=lambda x: [
                "Monday", "Tuesday", "Wednesday",
                "Thursday", "Friday",
                "Saturday", "Sunday"
            ][x]
        )
        is_weekend = 1 if dayofweek >= 5 else 0
        ct3.metric(
            "Weekend",
            "Yes" if is_weekend else "No"
        )

        if st.button(
            "Analyse this input", type="primary"
        ):
            payload = {"rows": [{
                "scenario":
                    scenario,
                "n_flows":
                    float(n_flows),
                "n_packets":
                    float(n_packets),
                "n_bytes":
                    float(n_bytes),
                "sum_n_dest_ip":
                    float(sum_n_dest_ip),
                "average_n_dest_ip":
                    float(average_n_dest_ip),
                "sum_n_dest_ports":
                    float(sum_n_dest_ports),
                "average_n_dest_ports":
                    float(average_n_dest_ports),
                "sum_n_dest_asn":
                    float(sum_n_dest_asn),
                "average_n_dest_asn":
                    float(average_n_dest_asn),
                "tcp_udp_ratio_packets":
                    float(tcp_udp_ratio_packets),
                "tcp_udp_ratio_bytes":
                    float(tcp_udp_ratio_bytes),
                "dir_ratio_packets":
                    float(dir_ratio_packets),
                "dir_ratio_bytes":
                    float(dir_ratio_bytes),
                "avg_duration":
                    float(avg_duration),
                "avg_ttl":
                    float(avg_ttl),
                "hour":
                    float(hour),
                "dayofweek":
                    float(dayofweek),
                "is_weekend":
                    float(is_weekend)
            }]}

            with st.spinner("Analysing..."):
                try:
                    resp = requests.post(
                        f"{API_URL}/predict",
                        json=payload,
                        timeout=15
                    )
                    if resp.status_code == 200:
                        _render_results(
                            resp.json()['results']
                        )
                    else:
                        st.error(
                            f"API error: {resp.text}"
                        )
                except Exception as e:
                    st.error(
                        f"Request failed: {e}"
                    )

    # ══════════════════════════════════════════════════════
    # TAB 2 — Upload CSV
    # ══════════════════════════════════════════════════════
    with tab2:
        st.markdown(
            "#### Upload a CSV file to analyse"
        )
        st.markdown(
            "<p style='color:#666;font-size:12px'>"
            "Use the example_input.csv file to see "
            "8 different scenarios covering all risk "
            "levels, or upload your own CSV.</p>",
            unsafe_allow_html=True
        )

        uploaded = st.file_uploader(
            "Upload CSV", type=['csv']
        )

        if st.button("Load example_input.csv"):
            example_path = os.path.join(
                os.path.dirname(__file__),
                '..', 'example_input.csv'
            )
            if os.path.exists(example_path):
                st.session_state['example_df'] = (
                    pd.read_csv(example_path)
                )
                st.success(
                    "Example data loaded — "
                    "8 scenarios covering LOW, "
                    "MEDIUM, HIGH and CRITICAL"
                )
            else:
                st.error(
                    "example_input.csv not found. "
                    "Run Cell 20 in your notebook."
                )

        df_to_use = None
        if uploaded:
            df_to_use = pd.read_csv(uploaded)
        elif 'example_df' in st.session_state:
            df_to_use = (
                st.session_state['example_df']
            )

        if df_to_use is not None:
            st.markdown(
                f"**{len(df_to_use)} rows loaded**"
            )
            st.dataframe(
                df_to_use,
                use_container_width=True,
                height=220
            )

            if st.button(
                "Analyse all rows", type="primary"
            ):
                rows = df_to_use.to_dict(
                    orient='records'
                )
                for r in rows:
                    r.setdefault('scenario', 'row')
                    r.setdefault('hour',      12.0)
                    r.setdefault('dayofweek',  0.0)
                    r.setdefault('is_weekend', 0.0)
                    for k, v in r.items():
                        if k != 'scenario':
                            try:
                                r[k] = float(v)
                            except Exception:
                                r[k] = 0.0

                payload = {"rows": rows}

                with st.spinner(
                    f"Analysing {len(rows)} rows..."
                ):
                    try:
                        resp = requests.post(
                            f"{API_URL}/predict",
                            json=payload,
                            timeout=30
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            _render_summary_table(
                                data
                            )
                            st.markdown("---")
                            st.markdown(
                                "#### Detailed "
                                "results per row"
                            )
                            for res in (
                                data['results']
                            ):
                                with st.expander(
                                    f"{res['scenario']}"
                                    f" — "
                                    f"{res['risk_level']}"
                                    f" ("
                                    f"{res['risk_score']}"
                                    f"%)"
                                ):
                                    _render_results(
                                        [res]
                                    )
                        else:
                            st.error(
                                "API error: "
                                f"{resp.text}"
                            )
                    except Exception as e:
                        st.error(
                            f"Request failed: {e}"
                        )

    # ══════════════════════════════════════════════════════
    # TAB 3 — Baseline Explorer
    # ══════════════════════════════════════════════════════
    with tab3:
        st.markdown(
            "#### What does normal look like?"
        )
        st.markdown(
            "<p style='color:#666;font-size:12px'>"
            "Statistics learned from real network "
            "traffic. Values outside the normal range "
            "are flagged as anomalous. The model uses "
            "the median as the default value because "
            "network data is heavily skewed by a few "
            "high-traffic servers.</p>",
            unsafe_allow_html=True
        )

        try:
            bl_resp = requests.get(
                f"{API_URL}/baseline", timeout=3
            ).json()['kpis']

            bl_rows = []
            for kpi, vals in bl_resp.items():
                bl_rows.append({
                    'KPI':
                        kpi,
                    'Median':
                        f"{float(vals.get('median', vals.get('mean', 0))):.3f}",
                    'Mean':
                        f"{float(vals['mean']):.3f}",
                    'Std':
                        f"{float(vals['std']):.3f}",
                    'Normal Min':
                        f"{float(vals['normal_min']):.3f}",
                    'Normal Max':
                        f"{float(vals['normal_max']):.3f}"
                })

            bl_df = pd.DataFrame(bl_rows)
            st.dataframe(
                bl_df,
                use_container_width=True,
                height=520
            )
        except Exception as e:
            st.error(
                f"Cannot load baseline: {e}"
            )

        st.markdown("---")
        st.markdown(
            "#### Correlation pairs — "
            "learned KPI relationships"
        )
        st.markdown(
            "<p style='color:#666;font-size:12px'>"
            "These are the relationships the model "
            "learned from training data. When new data "
            "breaks these relationships, it signals a "
            "root cause event.</p>",
            unsafe_allow_html=True
        )

        try:
            threshold = st.slider(
                "Correlation threshold",
                0.5, 1.0, 0.65, step=0.05,
                key="corr_threshold"
            )
            corr_resp = requests.get(
                f"{API_URL}/correlations"
                f"?threshold={threshold}",
                timeout=3
            ).json()

            corr_df = pd.DataFrame(
                corr_resp['pairs']
            )
            if not corr_df.empty:

                def color_r(val):
                    try:
                        v = abs(float(val))
                        if v >= 0.9:
                            return (
                                'background-color:'
                                '#0a3a2a;'
                                'color:#5DCAA5;'
                                'font-weight:bold'
                            )
                        elif v >= 0.75:
                            return (
                                'background-color:'
                                '#3a3010;'
                                'color:#F1C40F'
                            )
                        return 'color:#ccc'
                    except Exception:
                        return ''

                styled_corr = (
                    corr_df.style
                    .map(color_r,
                         subset=['pearson_r'])
                    .set_properties(**{
                        'background-color':
                            '#1a1a1a',
                        'color': '#ccc',
                        'border':
                            '1px solid #2a2a2a'
                    })
                )
                st.dataframe(
                    styled_corr,
                    use_container_width=True,
                    height=420
                )
                st.caption(
                    f"{corr_resp['total_pairs']} "
                    f"pairs above "
                    f"threshold {threshold}"
                )
            else:
                st.info(
                    "No pairs above this threshold."
                    " Try lowering it."
                )
        except Exception as e:
            st.error(
                f"Cannot load correlations: {e}"
            )

        st.markdown("---")
        st.markdown(
            "#### Saved model visualizations"
        )

        img1, img2 = st.columns(2)
        hm_path = os.path.join(
            BASE, 'correlation_heatmap.png'
        )
        dg_path = os.path.join(
            BASE, 'dependency_graph.png'
        )


        if os.path.exists(hm_path):
            img1.markdown(
                "**Correlation Heatmap**"
            )
            img1.image(
                hm_path,
                use_container_width=True
            )
        if os.path.exists(dg_path):
            img2.markdown("**Dependency Graph**")
            img2.image(
                dg_path,
                use_container_width=True
            )

        img3, img4 = st.columns(2)
        if os.path.exists(sh_path):
            img3.markdown(
                "**SHAP Feature Importance**"
            )
            img3.image(
                sh_path,
                use_container_width=True
            )
        if os.path.exists(cl_path):
            img4.markdown(
                "**Spatio-Temporal Clusters**"
            )
            img4.image(
                cl_path,
                use_container_width=True
            )


# ══════════════════════════════════════════════════════════
# Shared render functions
# ══════════════════════════════════════════════════════════

def _render_summary_table(data):
    st.markdown("### Summary — All Scenarios")

    # ── Risk level legend ──────────────────────────────────
    st.markdown("""
        <div style='display:flex;gap:16px;
            margin-bottom:12px;font-size:11px'>
            <span style='color:#5DCAA5'>
                🟢 LOW &lt;8%
            </span>
            <span style='color:#F1C40F'>
                🟡 MEDIUM 8–18%
            </span>
            <span style='color:#E67E22'>
                🟠 HIGH 18–32%
            </span>
            <span style='color:#E74C3C'>
                🔴 CRITICAL ≥32%
            </span>
        </div>
    """, unsafe_allow_html=True)

    rows = []
    for r in data['results']:
        icon = {
            "CRITICAL": "🔴",
            "HIGH":     "🟠",
            "MEDIUM":   "🟡",
            "LOW":      "🟢"
        }.get(r['risk_level'], "⚪")

        rows.append({
            "Scenario":
                r['scenario'],
            "Risk":
                f"{icon} {r['risk_level']}",
            "Score %":
                r['risk_score'],
            "ΣZ Deviation":
                r.get('sum_abs_z', 0),
            "Cluster":
                r['cluster'],
            "Cluster Conf.":
                f"{r['cluster_confidence']}%",
            "Anomalous KPIs":
                len(r['anomalous_kpis']),
            "Broken Corr.":
                len(r['broken_correlations']),
            "Predicted Bytes":
                f"{r['predicted_n_bytes']:,.0f}",
            "Actual Bytes":
                f"{r['actual_n_bytes']:,.0f}",
        })

    summary_df = pd.DataFrame(rows)

    def highlight_risk(val):
        s = str(val)
        if "CRITICAL" in s:
            return (
                'background-color:#3a1010;'
                'color:#E74C3C;font-weight:bold'
            )
        elif "HIGH" in s:
            return (
                'background-color:#3a2010;'
                'color:#E67E22'
            )
        elif "MEDIUM" in s:
            return (
                'background-color:#3a3010;'
                'color:#F1C40F'
            )
        elif "LOW" in s:
            return (
                'background-color:#0a3a2a;'
                'color:#5DCAA5'
            )
        return ''

    def highlight_score(val):
        try:
            v = float(val)
            if v >= 32:
                return (
                    'background-color:#3a1010;'
                    'color:#E74C3C;font-weight:bold'
                )
            elif v >= 18:
                return (
                    'background-color:#3a2010;'
                    'color:#E67E22'
                )
            elif v >= 8:
                return (
                    'background-color:#3a3010;'
                    'color:#F1C40F'
                )
            return (
                'background-color:#0a3a2a;'
                'color:#5DCAA5'
            )
        except Exception:
            return ''

    def highlight_z(val):
        try:
            v = float(val)
            if v >= 32:
                return (
                    'background-color:#3a1010;'
                    'color:#E74C3C;font-weight:bold'
                )
            elif v >= 18:
                return (
                    'background-color:#3a2010;'
                    'color:#E67E22'
                )
            elif v >= 8:
                return (
                    'background-color:#3a3010;'
                    'color:#F1C40F'
                )
            return (
                'background-color:#0a3a2a;'
                'color:#5DCAA5'
            )
        except Exception:
            return ''

    styled = (
        summary_df.style
        .map(highlight_risk,  subset=['Risk'])
        .map(highlight_score, subset=['Score %'])
        .map(highlight_z,
             subset=['ΣZ Deviation'])
        .set_properties(**{
            'background-color': '#1a1a1a',
            'color':            '#cccccc',
            'border':           '1px solid #2a2a2a'
        })
    )

    st.dataframe(styled, use_container_width=True)

    # ── Summary metric cards ───────────────────────────────
    m1, m2, m3, m4, m5 = st.columns(5)
    m1.metric("Total rows",   data['total_rows'])
    m2.metric(
        "🔴 Critical",
        data['critical_count']
    )
    m3.metric("🟠 High",      data['high_count'])
    m4.metric(
        "Safe (LOW+MED)",
        data['total_rows']
        - data['critical_count']
        - data['high_count']
    )
    avg_z = round(
        sum(
            r.get('sum_abs_z', 0)
            for r in data['results']
        ) / max(data['total_rows'], 1),
        1
    )
    m5.metric("Avg ΣZ", avg_z)


def _render_results(results):
    for r in results:

        # ── Risk header ────────────────────────────────────
        st.markdown(f"""
            <div style='background:#1a1a1a;
                border:1px solid #2a2a2a;
                border-radius:10px;
                padding:1rem;
                margin-bottom:1rem'>
                <div style='display:flex;
                    justify-content:space-between;
                    align-items:center'>
                    <div>
                        <div style='color:white;
                            font-size:15px;
                            font-weight:600'>
                            {r['scenario']}
                        </div>
                        <div style='color:#888;
                            font-size:12px;
                            margin-top:3px'>
                            Cluster {r['cluster']} ·
                            Fit:
                            {r['cluster_confidence']}%
                            · ΣZ deviation:
                            {r.get('sum_abs_z', 0):.1f}
                        </div>
                    </div>
                    {badge(r['risk_level'],
                           r['risk_score'])}
                </div>
            </div>
        """, unsafe_allow_html=True)

        # ── Metric cards ───────────────────────────────────
        col_a, col_b, col_c, col_d, col_e = (
            st.columns(5)
        )
        col_a.metric(
            "Predicted bytes",
            f"{r['predicted_n_bytes']:,.0f}"
        )
        col_b.metric(
            "Actual bytes",
            f"{r['actual_n_bytes']:,.0f}"
        )
        col_c.metric(
            "Anomalous KPIs",
            len(r['anomalous_kpis'])
        )
        col_d.metric(
            "Broken corr.",
            len(r['broken_correlations'])
        )
        col_e.metric(
            "ΣZ deviation",
            f"{r.get('sum_abs_z', 0):.1f}"
        )

        # ── Anomalous KPIs ─────────────────────────────────
        if r['anomalous_kpis']:
            st.markdown(
                "**Anomalous KPIs** "
                "— values outside the normal range"
            )
            anom_rows = []
            for a in r['anomalous_kpis']:
                anom_rows.append({
                    'KPI':
                        a['kpi'],
                    'Raw Value':
                        f"{a['raw_value']:,.4f}",
                    'Z-Score':
                        f"{a['z_score']:+.2f}σ"
                })
            anom_df = pd.DataFrame(anom_rows)

            def color_z(val):
                try:
                    v = float(
                        str(val).replace('σ', '')
                    )
                    if abs(v) > 3:
                        return (
                            'color:#E74C3C;'
                            'font-weight:bold'
                        )
                    elif abs(v) > 2:
                        return 'color:#E67E22'
                    return 'color:#F1C40F'
                except Exception:
                    return ''

            styled_anom = (
                anom_df.style
                .map(color_z, subset=['Z-Score'])
                .set_properties(**{
                    'background-color': '#111111',
                    'color':            '#cccccc',
                    'border':
                        '1px solid #2a2a2a'
                })
            )
            st.dataframe(
                styled_anom,
                use_container_width=True
            )
        else:
            st.markdown(
                "<div style='color:#5DCAA5;"
                "font-size:12px;padding:6px 0'>"
                "✓ All KPIs within normal range"
                "</div>",
                unsafe_allow_html=True
            )

        # ── Broken correlations ────────────────────────────
        if r['broken_correlations']:
            st.markdown(
                "**Broken correlations** "
                "— expected relationships diverging"
            )
            for bc in r['broken_correlations']:
                sev_color = (
                    "#E74C3C"
                    if bc['severity'] > 2
                    else "#E67E22"
                )
                st.markdown(f"""
                    <div style='background:#1e1010;
                        border-left:3px solid
                            {sev_color};
                        border-radius:4px;
                        padding:8px 12px;
                        margin-bottom:6px;
                        font-size:12px'>
                        <span style='color:
                            {sev_color};
                            font-weight:600'>
                            ⚠ Severity
                            {bc['severity']:.1f}σ
                        </span>
                        <span style='color:#ccc;
                            margin-left:8px'>
                            {bc['message']}
                        </span>
                    </div>
                """, unsafe_allow_html=True)
        else:
            st.markdown(
                "<div style='color:#5DCAA5;"
                "font-size:12px;padding:6px 0'>"
                "✓ No correlation breakdowns"
                "</div>",
                unsafe_allow_html=True
            )

        # ── SHAP drivers ───────────────────────────────────
        if r['top_shap_drivers']:
            st.markdown(
                "**Top root cause drivers** (SHAP)"
                " — which KPIs most influenced "
                "the prediction"
            )
            shap_rows = []
            for s in r['top_shap_drivers']:
                shap_rows.append({
                    'KPI':    s['kpi'],
                    'Impact': f"{s['impact']:+.4f}",
                    'Effect': s['direction']
                })
            shap_df = pd.DataFrame(shap_rows)

            def color_impact(val):
                try:
                    v = float(str(val))
                    if v > 0:
                        return 'color:#E74C3C'
                    return 'color:#5DCAA5'
                except Exception:
                    return ''

            styled_shap = (
                shap_df.style
                .map(color_impact,
                     subset=['Impact'])
                .set_properties(**{
                    'background-color': '#111111',
                    'color':            '#cccccc',
                    'border':
                        '1px solid #2a2a2a'
                })
            )
            st.dataframe(
                styled_shap,
                use_container_width=True
            )

        # ── Full deviation table ───────────────────────────
        with st.expander(
            "Full KPI deviation table "
            "(all 15 features)"
        ):
            dev_rows = []
            for feat, d in (
                r['kpi_deviations'].items()
            ):
                dev_rows.append({
                    'KPI':
                        d.get('display_name', feat),
                    'Raw Value':
                        f"{d.get('raw_value', 0):,.4f}",
                    'Log Value':
                        f"{d.get('log_value', 0):.4f}",
                    'Z-Score':
                        f"{d.get('z_score', 0):+.2f}σ",
                    'Normal Min':
                        f"{d['normal_range'][0]:.3f}",
                    'Normal Max':
                        f"{d['normal_range'][1]:.3f}",
                    'Status':
                        "⚠ ANOMALOUS"
                        if d['is_anomalous']
                        else "✓ Normal"
                })

            dev_df = pd.DataFrame(dev_rows)

            def color_status(val):
                if "ANOMALOUS" in str(val):
                    return (
                        'color:#E74C3C;'
                        'font-weight:bold'
                    )
                return 'color:#5DCAA5'

            def color_dev_z(val):
                try:
                    v = float(
                        str(val).replace('σ', '')
                    )
                    if abs(v) > 3:
                        return (
                            'color:#E74C3C;'
                            'font-weight:bold'
                        )
                    elif abs(v) > 2:
                        return 'color:#E67E22'
                    elif abs(v) > 1:
                        return 'color:#F1C40F'
                    return 'color:#5DCAA5'
                except Exception:
                    return ''

            styled_dev = (
                dev_df.style
                .map(color_status,
                     subset=['Status'])
                .map(color_dev_z,
                     subset=['Z-Score'])
                .set_properties(**{
                    'background-color': '#111111',
                    'color':            '#cccccc',
                    'border':
                        '1px solid #2a2a2a'
                })
            )
            st.dataframe(
                styled_dev,
                use_container_width=True
            )

        st.markdown(
            "<hr style='border-color:#2a2a2a;"
            "margin:1rem 0'>",
            unsafe_allow_html=True
        )