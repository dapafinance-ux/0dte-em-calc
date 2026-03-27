import streamlit as st
import numpy as np
import plotly.graph_objects as go
from scipy.stats import norm
from datetime import datetime, time

# =============================================================================
# APP CONFIG
# =============================================================================
st.set_page_config(page_title="0DTE EM Pro", layout="wide")

# =============================================================================
# AUTO-TIME LOGIC (unchanged — this was correct)
# =============================================================================
now = datetime.now().time()
market_open = time(9, 30)
market_close = time(16, 0)

if now < market_open:
    auto_t = 0.0
elif now > market_close:
    auto_t = 1.0
else:
    elapsed = (
        datetime.combine(datetime.today(), now)
        - datetime.combine(datetime.today(), market_open)
    ).seconds / 60
    auto_t = min(elapsed / 390, 1.0)

# =============================================================================
# SIDEBAR INPUTS
# =============================================================================
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

# =============================================================================
# CORE MATH — FIXED
# =============================================================================

# --- FIX 1: σ estimate ---
# BEFORE: w_calc = (0.6 * a) + (0.3 * b) + (0.1 * c)
# PROBLEM: Linear blending of ATM vol + OTM skew premium into a single σ number
#          is unjustified. OTM legs price different parts of the vol surface
#          (skew, wings, tail risk). Blending them inflates w and overstates the
#          expected move, which makes every downstream σ-distance calculation
#          understate how far a strike really is from the current price.
#
# FIX: Use ATM straddle alone as the 1σ estimate — this IS the market's
#      consensus σ for the remaining DTE. Use OTM strangles as skew/wing
#      diagnostics only. They tell you about distribution shape, not about σ.

w_sigma = a  # ATM straddle = market's 1σ estimate (clean, uncontaminated)
w_final  = w_sigma if w_anchor_manual == 0 else w_anchor_manual

# Skew diagnostics (not mixed into σ — used separately for regime context)
# skew_ratio > 1.3 → elevated skew, puts expensive relative to ATM
# wing_ratio > 1.6 → fat tails priced in, tail risk elevated
skew_ratio = (b / a) if a > 0 else 1.0   # OTM1 / ATM
wing_ratio  = (c / a) if a > 0 else 1.0  # OTM2 / ATM

# Remaining expected move: σ scales with √(time remaining)
# At t=0 (open): full expected move = w_final
# At t=1 (close): no expected move remains = 0
t_remaining   = max(1 - t, 0.0)
d_remaining   = w_final * np.sqrt(t_remaining)

# Current z-score: how many σ has price moved from anchor?
z_score = abs(s_live - s0) / w_final if w_final > 0 else 0.0

# =============================================================================
# STRIKE SAFETY (sidebar)
# =============================================================================
st.sidebar.header("🛡️ Strike Safety Check")
target_strike = st.sidebar.number_input(
    "Target Strike to Sell", value=float(round(s0 + w_final * 1.5))
)

# σ-distance from LIVE price, adjusted for time remaining
# BEFORE: dividing by (w_final * sqrt(1-t)) — this was actually structurally correct
# The only fix here is that w_final is now clean (ATM only), so the number is trustworthy
denom_strike = (w_final * np.sqrt(t_remaining)) if (w_final * t_remaining) > 0 else 1e-9
dist_sigma   = abs(target_strike - s_live) / denom_strike

st.sidebar.subheader("Risk Result")
st.sidebar.write(f"This strike is **{dist_sigma:.2f}σ** away from live price.")
safety_text = (
    "✅ HIGH"      if dist_sigma > 2.0 else
    "⚠️ MODERATE" if dist_sigma > 1.5 else
    "🚨 HIGH RISK"
)
st.sidebar.info(f"Safety Rating: {safety_text}")

# =============================================================================
# UI HEADER
# =============================================================================
is_over = s_live > (s0 + w_final) or s_live < (s0 - w_final)
status_color = "red" if is_over else "green"
st.markdown(
    f"<h2 style='text-align:center;color:{status_color};'>"
    f"{'🚨 OUTSIDE EXPECTED RANGE' if is_over else '✅ WITHIN EXPECTED RANGE'}</h2>",
    unsafe_allow_html=True,
)

# =============================================================================
# SKEW & WING REGIME BANNER
# Moved here so it's visible before the chart — regime context should precede signal
# =============================================================================
col_sk1, col_sk2, col_sk3 = st.columns(3)
with col_sk1:
    st.metric("1σ Expected Move (ATM)", f"±{w_final:.1f} pts")
with col_sk2:
    skew_label = (
        "🔴 Elevated" if skew_ratio > 1.35 else
        "🟡 Moderate" if skew_ratio > 1.15 else
        "🟢 Flat"
    )
    st.metric("Skew (OTM1/ATM)", f"{skew_ratio:.2f}  {skew_label}")
with col_sk3:
    wing_label = (
        "🔴 Fat Tails" if wing_ratio > 1.65 else
        "🟡 Moderate"  if wing_ratio > 1.35 else
        "🟢 Normal"
    )
    st.metric("Wing (OTM2/ATM)", f"{wing_ratio:.2f}  {wing_label}")

# =============================================================================
# CHART
# =============================================================================
y_min = min(s0 - w_final, s_live - d_remaining) - 20
y_max = max(s0 + w_final, s_live + d_remaining) + 20

fig = go.Figure()

# Gray box: full-day ±1σ from anchor
fig.add_shape(
    type="rect",
    y0=s0 - w_final, y1=s0 + w_final,
    x0=0, x1=1,
    fillcolor="gray", opacity=0.2, line_width=0,
)

# Purple box: remaining expected move from live price
fig.add_shape(
    type="rect",
    y0=s_live - d_remaining, y1=s_live + d_remaining,
    x0=0.2, x1=0.8,
    fillcolor="purple", opacity=0.4,
)

fig.add_hline(y=s_live, line_dash="dash", line_color="white",
              annotation_text=f"LIVE: {s_live}")
fig.add_hline(y=s0, line_color="yellow", opacity=0.5,
              annotation_text="OPEN ANCHOR")

fig.update_layout(
    yaxis_range=[y_min, y_max],
    template="plotly_dark",
    height=500,
    margin=dict(l=20, r=20, t=20, b=20),
)
st.plotly_chart(fig, use_container_width=True)

# =============================================================================
# DELTA-NEUTRAL RECOMMENDATIONS (2σ boundaries)
# =============================================================================
st.divider()
st.subheader("⚖️ Delta-Neutral Recommendations")
st.caption("These strikes target the 2σ boundary for maximum safety.")

# Skew adjustment: put side gets a wider buffer when skew is elevated
# The market is pricing downside tails more expensively — your put strike
# should be further OTM to maintain equivalent protection
put_skew_adj  = 1.0 + max(0, (skew_ratio - 1.0) * 0.5)
suggested_put  = s0 - (w_final * 2 * put_skew_adj)
suggested_call = s0 + (w_final * 2)

col_p, col_c = st.columns(2)
with col_p:
    st.success(f"Suggested Put Strike: {suggested_put:.0f}")
with col_c:
    st.error(f"Suggested Call Strike: {suggested_call:.0f}")

# =============================================================================
# PROBABILITY OF TOUCH (PoT) — FIXED
# =============================================================================
st.divider()
st.subheader("⚠️ Probability of Touch (PoT)")

# BEFORE: step-function heuristic producing a cliff at σ boundaries
# PROBLEM: Produces 64% inside 1σ, drops to 10% just past it — discontinuous
#          and completely disconnected from time remaining or actual barrier distance.
#
# FIX: Reflection principle for standard Brownian motion.
#
# For a process starting at 0 with σ=1, the probability of touching a
# one-sided barrier B > 0 before time T is:
#
#   PoT = 2 × Φ(−B / √T)
#
# where Φ is the standard normal CDF.
#
# In our model:
#   - B = (barrier in σ units) = distance from s_live to barrier / w_final
#   - T = t_remaining (fraction of trading day left)
#   - We treat the two-sided gray box as two independent one-sided barriers
#     and take P(touch either) ≈ min(P_upper + P_lower, 1.0)
#     (exact formula requires correlation; this is a conservative upper bound)
#
# NOTE: This assumes log-normal diffusion with constant vol — no jumps, no skew.
# It will UNDERSTATE PoT when vol is elevated or tails are fat (see wing_ratio).

def prob_of_touch_one_sided(barrier_sigma_distance: float, time_remaining: float) -> float:
    """
    Probability of touching a one-sided barrier before expiry.
    Uses the reflection principle: PoT = 2 * Φ(-d)
    where d = barrier_distance_in_sigma / sqrt(time_remaining)

    Args:
        barrier_sigma_distance: Distance to barrier in σ units (must be > 0)
        time_remaining: Fraction of day remaining (0 to 1)

    Returns:
        Probability in [0, 1]
    """
    if time_remaining <= 0:
        return 0.0
    if barrier_sigma_distance <= 0:
        return 1.0
    d = barrier_sigma_distance / np.sqrt(time_remaining)
    return float(2 * norm.cdf(-d))

# Distance from LIVE price to gray box boundaries (in σ units, using clean w_final)
upper_barrier_sigma = (s0 + w_final - s_live) / w_final  # distance to top of gray box
lower_barrier_sigma = (s_live - (s0 - w_final)) / w_final  # distance to bottom

# Clamp to 0 if already outside
upper_barrier_sigma = max(upper_barrier_sigma, 0.0)
lower_barrier_sigma = max(lower_barrier_sigma, 0.0)

pot_upper = prob_of_touch_one_sided(upper_barrier_sigma, t_remaining)
pot_lower = prob_of_touch_one_sided(lower_barrier_sigma, t_remaining)

# P(touch either boundary) = P(touch upper) + P(touch lower) - P(touch both)
# P(touch both) is very small for reasonable moves — approximate as union
pot_either = min(pot_upper + pot_lower, 1.0)

# Current proximity to target strike (how close is live price to the strike you're selling?)
target_sigma_dist = abs(target_strike - s_live) / (w_final * np.sqrt(t_remaining)) \
    if (w_final * t_remaining) > 0 else 0.0
pot_to_target = prob_of_touch_one_sided(
    abs(target_strike - s_live) / w_final, t_remaining
)

col_pot1, col_pot2 = st.columns(2)
with col_pot1:
    st.metric("Prob. of Touching Gray Box", f"{pot_either * 100:.1f}%")
    st.caption(f"Upper boundary: {pot_upper*100:.1f}%  |  Lower boundary: {pot_lower*100:.1f}%")
with col_pot2:
    st.metric("Prob. of Touching Target Strike", f"{pot_to_target * 100:.1f}%")
    st.caption(f"Based on reflection principle, {t_remaining*100:.0f}% of day remaining")

# =============================================================================
# STATISTICAL CONTEXT — FIXED
# =============================================================================
st.divider()
st.subheader("📊 Statistical Context")

col_a, col_b, col_c = st.columns(3)
with col_a:
    st.metric("Move from Anchor", f"{s_live - s0:+.2f} pts")
with col_b:
    st.metric("Standard Deviations", f"{z_score:.2f} σ")
with col_c:
    # Use actual two-tailed normal probability, not the empirical rule buckets
    # This tells you: what % of days see a move THIS LARGE OR LARGER from anchor
    prob_exceed = float(2 * norm.cdf(-z_score)) * 100
    st.metric("Prob. of Move This Large", f"{prob_exceed:.1f}%")

# BEFORE: 100 * exp(-0.5 * z²) — this is the unnormalized Gaussian kernel, NOT a probability
# For z=0 it returns 100%, for z=1 it returns 60.7% — neither is meaningful
#
# FIX: Two-tailed survival probability from the standard normal distribution
# P(|Z| > z) = 2 * Φ(-z)
# For z=0: 100% (price is exactly at anchor, any move qualifies)
# For z=1: 31.7% (a 1σ or larger move happens ~32% of days)
# For z=2: 4.6% (a 2σ or larger move happens ~5% of days)

st.info(
    f"A move of {z_score:.2f}σ or larger from the anchor occurs on approximately "
    f"**{prob_exceed:.1f}%** of 0DTE days under the normal distribution assumption. "
    f"Note: SPX has fat left tails — true downside probability exceeds this estimate."
)

# Fat tail caveat: display wing_ratio as a tail risk flag
if wing_ratio > 1.5:
    st.warning(
        f"⚠️ Wing ratio is {wing_ratio:.2f}x — the market is pricing significant tail risk. "
        f"Normal-distribution PoT estimates above are likely understating true touch probability."
    )
