import streamlit as st
import pandas as pd
import numpy as np
import time
import requests
import plotly.graph_objects as go
from collections import deque

# --- Streamlit Configuration ---
st.set_page_config(page_title="Neonatal Monitoring Dashboard", layout="wide", initial_sidebar_state="collapsed")

# Custom CSS for Dark Theme and Premium Look
st.markdown("""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Outfit:wght@300;400;600;800&family=JetBrains+Mono&display=swap');

    /* Real Medical System Theme */
    .stApp {
        background: radial-gradient(circle at top right, #0F172A, #020617);
        color: #F8FAFC !important;
        font-family: 'Outfit', sans-serif;
    }
    
    /* Command Center Header */
    .main-header {
        position: relative;
        text-align: left;
        padding: 40px 50px;
        background: rgba(30, 41, 59, 0.4);
        backdrop-filter: blur(12px);
        margin: -30px -50px 40px -50px;
        border-bottom: 2px solid rgba(56, 189, 248, 0.3);
        box-shadow: 0 10px 50px rgba(0,0,0,0.6);
    }
    .main-header h1 {
        color: #F8FAFC !important;
        font-size: 3rem !important;
        font-weight: 800 !important;
        margin: 0;
        letter-spacing: -1px;
    }
    .system-status-pill {
        display: inline-block;
        padding: 5px 15px;
        background: rgba(16, 185, 129, 0.2);
        color: #10B981;
        border: 1px solid #10B981;
        border-radius: 50px;
        font-size: 0.9rem;
        font-weight: 600;
        margin-top: 10px;
    }
    
    /* High-Fidelity Clinical Cards */
    .status-card {
        background: rgba(30, 41, 59, 0.5) !important;
        backdrop-filter: blur(10px);
        padding: 35px !important;
        border-radius: 24px !important;
        text-align: left !important;
        border: 1px solid rgba(255, 255, 255, 0.1) !important;
        margin-bottom: 25px !important;
        transition: all 0.3s ease;
        box-shadow: 0 20px 40px rgba(0,0,0,0.3);
    }
    .status-card:hover {
        transform: translateY(-5px);
        border-color: rgba(56, 189, 248, 0.5) !important;
    }
    .status-card h2 {
        color: #94A3B8 !important;
        font-size: 1.1rem !important;
        font-weight: 600 !important;
        text-transform: uppercase;
        letter-spacing: 2px;
        margin-bottom: 8px !important;
    }
    .status-value {
        color: #F8FAFC !important;
        font-size: 3.2rem !important;
        font-weight: 800 !important;
        line-height: 1;
        margin-bottom: 15px;
        text-shadow: 0 0 20px rgba(56, 189, 248, 0.2);
    }
    .status-unit {
        font-size: 1.2rem;
        color: #64748B;
        font-weight: 400;
        margin-left: 8px;
    }
    
    /* Dynamic Indicators */
    .vital-stat {
        display: flex;
        align-items: center;
        gap: 15px;
        background: rgba(15, 23, 42, 0.5);
        padding: 12px 20px;
        border-radius: 12px;
        margin-top: 15px;
    }
    .vital-stat b { color: #38BDF8; font-size: 1rem; }
    .vital-pulse {
        width: 10px;
        height: 10px;
        background: #10B981;
        border-radius: 50%;
        box-shadow: 0 0 10px #10B981;
        animation: heartbeat 1.5s infinite;
    }
    @keyframes heartbeat {
        0% { transform: scale(1); opacity: 1; }
        50% { transform: scale(1.5); opacity: 0.5; }
        100% { transform: scale(1); opacity: 1; }
    }
    
    /* Medical Alert States */
    .alert-card {
        background: linear-gradient(145deg, rgba(127, 29, 29, 0.4), rgba(69, 10, 10, 0.6)) !important;
        border: 2px solid #EF4444 !important;
    }
    .alert-card .status-value { color: #FECACA !important; }
    .alert-card .vital-pulse { background: #EF4444; box-shadow: 0 0 15px #EF4444; }
    
    /* Video Feed Container */
    .video-container {
        border: 4px solid #38BDF8;
        border-radius: 28px;
        overflow: hidden;
        background: #000;
        box-shadow: 0 0 20px rgba(56, 189, 248, 0.3), 0 30px 60px rgba(0,0,0,0.5);
        margin-bottom: 25px;
        position: relative;
    }
    .video-container::before {
        content: "LIVE FEED";
        position: absolute;
        top: 15px;
        left: 15px;
        background: rgba(56, 189, 248, 0.8);
        color: white;
        padding: 4px 10px;
        border-radius: 6px;
        font-size: 0.7rem;
        font-weight: 800;
        z-index: 10;
    }
    </style>
    """, unsafe_allow_html=True)

# Dashboard Structure
st.markdown(f'''
    <div class="main-header">
        <h1>Clinical Command Center</h1>
        <div class="system-status-pill">● PERSISTENT TELEMETRY ACTIVE</div>
    </div>
''', unsafe_allow_html=True)

# --- Data Caching & Global State ---
if 'history' not in st.session_state:
    st.session_state['history'] = {
        'time': deque(maxlen=50),
        'breathing_rate': deque(maxlen=50),
        'movement': deque(maxlen=50),
        'noise': deque(maxlen=50),
        'respiration': deque(maxlen=50)
    }

# Defensive key check
for key in ['time', 'breathing_rate', 'movement', 'noise', 'respiration']:
    if key not in st.session_state['history']:
        st.session_state['history'][key] = deque(maxlen=50)

# --- Layout ---
history = st.session_state['history']
col_left, col_right = st.columns([1, 1.2])

# --- Fetch Data ---
def fetch_data():
    try:
        response = requests.get("http://localhost:5000/data", timeout=0.1)
        if response.status_code == 200:
            return response.json()
    except:
        return {"connected": False, "error": "Backend Unreachable"}

# --- Plotting Helpers ---
def create_line_chart(title, x, y, color, fill=False):
    fig = go.Figure()
    if not x or not y:
        return fig
        
    fill_mode = 'toself' if fill else None
    fig.add_trace(go.Scatter(
        x=list(x), y=list(y), name=title, mode='lines', 
        line=dict(color=color, width=3, shape='spline'),
        fill=fill_mode,
        fillcolor=f"rgba{tuple(int(color.lstrip('#')[i:i+2], 16) for i in (0, 2, 4)) + (0.2,)}" if fill else None
    ))
    fig.update_layout(
        title=dict(text=title, font=dict(size=16, color="#CBD5E1")),
        template="plotly_dark",
        margin=dict(l=0, r=0, t=30, b=0),
        height=180,
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        xaxis=dict(showgrid=False, showticklabels=False, zeroline=False),
        yaxis=dict(showgrid=False, zeroline=False),
        showlegend=False
    )
    return fig

# --- App Layout Setup ---
with col_left:
    st.subheader("Live Monitoring Feed")
    video_placeholder = st.empty()
    status_placeholder = st.empty()

with col_right:
    chart_breathing = st.empty()
    chart_motion = st.empty()
    chart_noise = st.empty()
    chart_respiration = st.empty()

# --- Main App Loop ---
while True:
    data = fetch_data()
    
    # Check if hardware is detected
    if not data.get("connected", False):
        with status_placeholder:
            st.error("🔴 HARDWARE DISCONNECTED: Please check ESP32 USB connection.")
        time.sleep(1)
        continue

    # Telemetry check
    required_keys = ['breathing_rate', 'movement', 'noise', 'respiration']
    if not all(k in data for k in required_keys):
        st.warning("Synchronizing Telemetry...")
        time.sleep(1)
        continue
    
    now = time.strftime("%H:%M:%S")
    # Ultra-defensive state check for session closure
    if 'history' not in st.session_state: continue
    
    st.session_state['history']['time'].append(now)
    st.session_state['history']['breathing_rate'].append(data['breathing_rate'])
    st.session_state['history']['movement'].append(float(data['movement']))
    st.session_state['history']['noise'].append(data['noise'])
    st.session_state['history']['respiration'].append(data['respiration'])

    with video_placeholder:
        # Using a direct HTML img tag is often more robust for MJPEG streams in Streamlit
        st.markdown(f"""
            <div class="video-container">
                <img src="http://127.0.0.1:5000/video_feed" style="width:100%; border-radius:24px;">
            </div>
        """, unsafe_allow_html=True)
             
    with status_placeholder:
        # Medical condition logic
        sound_level = float(data.get('noise', 0))
        br_rate = float(data.get('breathing_rate', 0))
        has_movement = float(data.get('movement', 0)) > 0.5 or data.get('motion_detected', False)
        
        if sound_level > 100:
            alert_text = "NEONATAL AGITATION / TUP"
            status_class = "status-card" # Changed from alert-card to normal status
        elif br_rate < 5.0:
            alert_text = "APNEA ALERT / RESPIRATORY ARREST"
            status_class = "status-card alert-card" # Apnea remains a critical alert
        elif has_movement and br_rate >= 10.0:
            alert_text = "EUSTHENIC STATE (NORMAL)"
            status_class = "status-card"
        elif not has_movement and br_rate >= 10.0:
            alert_text = "STABLE CLINICAL STATE"
            status_class = "status-card"
        else:
            alert_text = "CLINICAL OBSERVATION"
            status_class = "status-card"

        st.markdown(f"""<div class="{status_class}">
<h2>Patient Clinical Status</h2>
<div class="status-value">{alert_text}</div>
<div class="vital-stat">
<div class="vital-pulse"></div>
<div><b>RHYTHM:</b> {br_rate:.1f} <span class="status-unit">BPM</span></div>
</div>
<div class="vital-stat">
<div class="vital-pulse"></div>
<div><b>AMPLITUDE:</b> {sound_level:.0f} <span class="status-unit">RMS</span></div>
</div>
<div class="vital-stat">
<div class="vital-pulse" style="animation-delay: 0.5s;"></div>
<div><b>KINESIS:</b> {("ACTIVE" if has_movement else "REPOSE")}</div>
</div>
</div>""", unsafe_allow_html=True)

    # Update Charts using direct session state
    chart_breathing.plotly_chart(create_line_chart("Breathing Rhythm (BPM)", st.session_state['history']['time'], st.session_state['history']['breathing_rate'], "#10B981"), use_container_width=True)
    chart_motion.plotly_chart(create_line_chart("Motion Detection Signal", st.session_state['history']['time'], st.session_state['history']['movement'], "#3B82F6", fill=True), use_container_width=True)
    chart_noise.plotly_chart(create_line_chart("Environmental Noise (dB)", st.session_state['history']['time'], st.session_state['history']['noise'], "#F59E0B"), use_container_width=True)
    chart_respiration.plotly_chart(create_line_chart("Respiratory Depth Index", st.session_state['history']['time'], st.session_state['history']['respiration'], "#8B5CF6"), use_container_width=True)

    time.sleep(0.5)
