import streamlit as st
import numpy as np
import plotly.graph_objects as go

# --- APP CONFIG ---
st.set_page_config(page_title="0DTE Weighted EM Cockpit", layout="wide")
st.title("🎯 0DTE Expected Move Dashboard")

# --- SIDEBAR INPUTS ---
st.sidebar.header("10:00 AM Anchor")
s0 = st.sidebar.number_input("Anchor Price (S0)", value=6500.0)
a = st.sidebar.number_input("ATM Straddle (a)", value=22.5)
b = st.sidebar.number_input("OTM1 Strangle (b)", value=28.0)
c = st.sidebar.number_input("OTM2 Strangle (c)", value=35.0)

st.sidebar.header("Live Market Data")
s_live = st.sidebar.number_input("Current Price (Slive)", value=6520.0)
t = st.sidebar.slider("Time Elapsed (t)", 0.0, 1.0, 0.6)

# --- MATH LOGIC ---
w_anchor = (0.6 * a) + (0.3 * b) + (0.1 * c)
d_remaining = w_anchor * np.sqrt(1 - t)

upper_anchor, lower_anchor = s0 + w_anchor, s0 - w_anchor
upper_live, lower_live = s_live + d_remaining, s_live - d_remaining

# --- STATUS INDICATORS ---
col1, col2, col3 = st.columns(3)
with col1:
    st.metric("Weighted EM (Anchor)", f"{w_anchor:.2f}")
with col2:
    st.metric("Remaining Vol (D)", f"{d_remaining:.2f}")
with col3:
    status = "⚠️ OVER-EXTENDED" if s_live > upper_anchor or s_live < lower_anchor else "✅ WITHIN RANGE"
    st.subheader(status)

# --- THE VISUAL CHART ---
fig = go.Figure()

# Gray Box (Anchor Range)
fig.add_shape(type="rect", y0=lower_anchor, y1=upper_anchor, x0=0, x1=1, fillcolor="LightGray", opacity=0.3, layer="below")
# Purple Box (Live Risk)
fig.add_shape(type="rect", y0=lower_live, y1=upper_live, x0=0.3, x1=0.7, fillcolor="Purple", opacity=0.5)
# Live Price Line
fig.add_hline(y=s_live, line_dash="dash", line_color="black", annotation_text=f"Live: {s_live}")

fig.update_layout(yaxis_range=[s0-60, s0+60], title="Volatility Cloud vs. Daily Anchor", xaxis_showticklabels=False)
st.plotly_chart(fig, use_container_width=True)
