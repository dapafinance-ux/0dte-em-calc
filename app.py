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

if now < market_open:
    auto_t = 0.0
elif now > market_close:
    auto_t = 1.0
else:
    elapsed = (datetime.combine(datetime.today(), now) - datetime.combine(datetime.today(), market_open)).seconds / 60
    auto_t = min(elapsed / 390, 1.0)

# --- SIDEBAR INPUTS ---
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

# --- CORE MATH ---
w_calc = (0.6 * a) + (0.3 * b) + (0.1 * c)
w_final = w_calc if w_anchor_manual == 0 else w_anchor_manual
d_remaining = w_final * np.sqrt(1 - t)
z_score = abs(s_live - s0) / w_final if w_final > 0 else 0

# --- DELTA NEUTRAL RECOMMENDATIONS ---
# Targeting ~0.05 Delta (approx 2-Sigma)
call_strike_suggest = round((s_live + (w_final * 2)) / 5) * 5
put_strike_suggest = round((s_live - (w_final * 2)) / 5) * 5

# --- STRIKE HUNTER SIDEBAR ---
st.sidebar.header("🛡️ Strike Safety Check")
target_strike = st.sidebar.number_input("Target Strike to Sell", value=call_strike_suggest)
dist_sigma = abs(target_strike - s_live) / (w_final * np.sqrt(1 - t)) if (w_final * np.sqrt(1-t)) > 0 else 0

st.sidebar.subheader("Risk Result")
st.sidebar.write(f"This strike is **{dist_sigma:.2f}σ** away from live price.")
safety_text = "✅ HIGH" if dist_sigma > 2 else "⚠️ MODERATE" if dist_sigma > 1.5 else "🚨 HIGH RISK"
st.sidebar.info(f"Safety Rating: {safety_text}")

# --- UI HEADER ---
is_over = s_live > (s0 + w_final) or s_live < (s0 - w_final)
status_color = "red" if is_over else "green"
st.markdown(f"<h2 style='text-align: center; color: {status_color};'>{'🚨 OUTSIDE EXPECTED RANGE' if is_over else '✅ WITHIN EXPECTED RANGE'}</h2>", unsafe_allow_html=True)

# --- THE CHART ---
y_min = min(s0 - w_final, s_live - d_remaining, put_strike_suggest) - 20
y_max = max(s0 + w_final, s_live + d_remaining, call_strike_suggest) + 20
fig = go.Figure()
fig.add_shape(type="rect", y0=s0-w_final, y1=s0+w_final, x0=0, x1=1, fillcolor="gray", opacity=0.2, line_width=0)
fig.add_shape(type="rect", y0=s_live-d_remaining, y1=s_live+d_remaining, x0=0.2, x1=0.8, fillcolor="purple", opacity=0.4)
fig.add_hline(y=s_live, line_dash="dash", line_color="white", annotation_text=f"LIVE: {s_live}")
fig.add_hline(y=s0, line_color="yellow", opacity=0.5, annotation_text="OPEN ANCHOR")
# Recommended Strike Lines
fig.add_hline(y=call_strike_suggest, line_color="red", opacity=0.3, line_dash="dot", annotation_text="Suggested Call")
fig.add_hline(y=put_strike_suggest, line_color="green", opacity=0.3, line_dash="dot", annotation_text="Suggested Put")

fig.update_layout(yaxis_range=[y_min, y_max], template="plotly_dark", height=500, margin=dict(l=20, r=20, t=20, b=20))
st.plotly_chart(fig, use_container_width=True)

# --- DELTA NEUTRAL OUTPUTS ---
st.divider()
st.subheader("⚖️ Delta-Neutral Recommendations")
st.write("These strikes target the **2-Sigma ($2\sigma$)** boundary for maximum safety.")
col_d1, col_d2 = st.columns(2)
with col_d1:
    st.success(f"Suggested Put Strike: {put_strike_suggest}")
with col_d2:
    st.error(f"Suggested Call Strike: {call_strike_suggest}")

# --- PROBABILITY OF TOUCH (PoT) ---
st.divider()
st.subheader("⚠️ Probability of Touch (PoT)")
col_pot1, col_pot2 = st.columns(2)
with col_pot1:
    touch_prob = min(99.0, (100 * (1 - (0.68 if z_score < 1 else 0.95 if z_score < 2 else 0.99))) * 2)
    st.metric("Prob. of Touching Gray Box", f"{touch_prob:.1f}%")
with col_pot2:
    target_sigma_dist = abs(target_strike - s0) / w_final if w_final > 0 else 1
    current_pot = min(100.0, (z_score / target_sigma_dist) * 100) if target_sigma_dist > 0 else 100
    st.metric("Current Proximity to Target Strike", f"{current_pot:.1f}%")

# --- STATS TABLE ---
st.divider()
st.subheader("📊 Statistical Context")
col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Move from Anchor", f"{s_live - s0:+.2f} pts")
with col_b:
    st.metric("Standard Deviations", f"{z_score:.2f} σ")
with col_c:
    prob_range = "68%" if z_score <= 1 else "95%" if z_score <= 2 else "99.7%"
    st.metric("Confidence Level", prob_range)

