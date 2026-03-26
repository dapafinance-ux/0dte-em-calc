import streamlit as st
import numpy as np
import plotly.graph_objects as go
from datetime import datetime, time

# --- APP CONFIG ---
st.set_page_config(page_title="0DTE EM Pro", layout="wide")

# --- AUTO-TIME LOGIC ---
now = datetime.now().time()
market_open = time(9, 30)
market_close = time(16, 0)

# Calculate decimal time (t) automatically
if now < market_open:
    auto_t = 0.0
elif now > market_close:
    auto_t = 1.0
else:
    # Calculate fraction of 390 minutes elapsed
    elapsed = (datetime.combine(datetime.today(), now) - datetime.combine(datetime.today(), market_open)).seconds / 60
    auto_t = min(elapsed / 390, 1.0)

# --- SIDEBAR ---
st.sidebar.header("🎯 10:00 AM Anchor")
s0 = st.sidebar.number_input("Anchor Price (S0)", value=6500.0, step=1.0)
w_anchor_manual = st.sidebar.number_input("Manual W_Anchor (Optional)", value=0.0)

st.sidebar.header("📊 Live Options Chain")
a = st.sidebar.number_input("ATM Straddle (a)", value=22.5)
b = st.sidebar.number_input("OTM1 Strangle (b)", value=28.0)
c = st.sidebar.number_input("OTM2 Strangle (c)", value=35.0)

st.sidebar.header("🕒 Market Clock")
s_live = st.sidebar.number_input("Current SPX Price", value=6520.0, step=0.5)
use_auto_time = st.sidebar.checkbox("Use Real-Time Clock", value=True)
t = auto_t if use_auto_time else st.sidebar.slider("Manual Time Slider", 0.0, 1.0, 0.5)

# --- MATH ---
w_calc = (0.6 * a) + (0.3 * b) + (0.1 * c)
w_final = w_calc if w_anchor_manual == 0 else w_anchor_manual
d_remaining = w_final * np.sqrt(1 - t)

# --- DYNAMIC Y-AXIS (Fixes the limitation) ---
y_min = min(s0 - w_final, s_live - d_remaining) - 20
y_max = max(s0 + w_final, s_live + d_remaining) + 20

# --- UI HEADER ---
is_over = s_live > (s0 + w_final) or s_live < (s0 - w_final)
status_color = "red" if is_over else "green"
st.markdown(f"<h2 style='text-align: center; color: {status_color};'>{'🚨 OUTSIDE EXPECTED RANGE' if is_over else '✅ WITHIN EXPECTED RANGE'}</h2>", unsafe_allow_html=True)

# --- PLOT ---
fig = go.Figure()
fig.add_shape(type="rect", y0=s0-w_final, y1=s0+w_final, x0=0, x1=1, fillcolor="gray", opacity=0.2, line_width=0)
fig.add_shape(type="rect", y0=s_live-d_remaining, y1=s_live+d_remaining, x0=0.2, x1=0.8, fillcolor="purple", opacity=0.4)
fig.add_hline(y=s_live, line_dash="dash", line_color="white", annotation_text=f"LIVE: {s_live}")
fig.add_hline(y=s0, line_color="yellow", opacity=0.5, annotation_text="OPEN ANCHOR")

fig.update_layout(yaxis_range=[y_min, y_max], template="plotly_dark", height=600)
st.plotly_chart(fig, use_container_width=True)

# --- STRIKE HUNTER ---
st.sidebar.header("🛡️ Strike Safety Check")
target_strike = st.sidebar.number_input("Target Strike to Sell", value=s0 + (w_final * 1.5))

# Calculate distance and PoT
dist_sigma = abs(target_strike - s_live) / (w_final * np.sqrt(1 - t)) if (w_final * np.sqrt(1-t)) > 0 else 0
pot = min(100.0, (1 - (z_score / (abs(target_strike-s0)/w_final if w_final > 0 else 1))) * 100) # Simple heuristic for PoT

st.sidebar.subheader("Risk Result")
if target_strike > s_live:
    st.sidebar.write(f"This strike is **{dist_sigma:.2f}σ** away from live price.")
else:
    st.sidebar.write(f"This strike is **{dist_sigma:.2f}σ** away from live price.")

# --- PROBABILITY OF TOUCH INDICATOR ---
st.divider()
st.subheader("⚠️ Probability of Touch (PoT)")
col_pot1, col_pot2 = st.columns(2)
with col_pot1:
    # Rule of 2: Prob of touching is ~2x Prob of expiring outside
    touch_prob = min(99.0, (100 * (1 - (0.68 if z_score < 1 else 0.95 if z_score < 2 else 0.99))) * 2)
    st.metric("Prob. of Touching Gray Box", f"{touch_prob:.1f}%")
with col_pot2:
    st.metric("Safety Rating", "HIGH" if dist_sigma > 2 else "MODERATE" if dist_sigma > 1.5 else "HIGH RISK")


# --- STATS TABLE ---
st.divider()
st.subheader("📊 Statistical Context")
z_score = abs(s_live - s0) / w_final if w_final > 0 else 0

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Move from Anchor", f"{s_live - s0:+.2f} pts")
with col_b:
    st.metric("Standard Deviations", f"{z_score:.2f} σ")
with col_c:
    prob = "68%" if z_score <= 1 else "95%" if z_score <= 2 else "99.7%"
    st.metric("Confidence Level", prob)

st.info(f"A {z_score:.2f} sigma move happens approximately {100*np.exp(-0.5*z_score**2):.1f}% of the time.")


