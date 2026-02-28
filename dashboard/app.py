"""
Streamlit dashboard — HRV, recovery, sleep, and workout trends.
Run: streamlit run dashboard/app.py
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st
from dotenv import load_dotenv

load_dotenv()

from db.database import get_db
from db.models import JournalEntry, WhoopRecovery, WhoopSleep, WhoopWorkout
from ai.context import get_hrv_baseline, get_rhr_baseline

st.set_page_config(page_title="Whoop Dashboard", page_icon="💚", layout="wide")

DAYS = st.sidebar.slider("Days to display", min_value=7, max_value=90, value=30)


@st.cache_data(ttl=300)
def load_data(days: int):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    with get_db() as db:
        recoveries = [
            {
                "date": r.created_at.date() if r.created_at else None,
                "recovery_score": r.recovery_score,
                "hrv_rmssd_milli": r.hrv_rmssd_milli,
                "resting_heart_rate": r.resting_heart_rate,
                "spo2_percentage": r.spo2_percentage,
                "skin_temp_celsius": r.skin_temp_celsius,
            }
            for r in db.query(WhoopRecovery)
            .filter(WhoopRecovery.created_at >= cutoff)
            .order_by(WhoopRecovery.created_at)
            .all()
        ]
        sleeps = [
            {
                "date": s.end.date() if s.end else None,
                "total_in_bed_milli": s.total_in_bed_milli,
                "slow_wave_milli": s.slow_wave_milli,
                "rem_sleep_milli": s.rem_sleep_milli,
                "light_sleep_milli": s.light_sleep_milli,
                "sleep_performance_pct": s.sleep_performance_pct,
                "sleep_debt_milli": s.sleep_debt_milli,
                "nap": s.nap,
            }
            for s in db.query(WhoopSleep)
            .filter(WhoopSleep.end >= cutoff)
            .order_by(WhoopSleep.end)
            .all()
        ]
        workouts = [
            {
                "date": w.start.date() if w.start else None,
                "sport_name": w.sport_name,
                "strain_score": w.strain_score,
            }
            for w in db.query(WhoopWorkout)
            .filter(WhoopWorkout.start >= cutoff)
            .order_by(WhoopWorkout.start)
            .all()
        ]
        journals = [
            {
                "date": j.date,
                "alcohol_units": j.alcohol_units or 0,
                "stress_level": j.stress_level or 0,
                "late_caffeine": int(j.late_caffeine or False),
            }
            for j in db.query(JournalEntry)
            .filter(JournalEntry.date >= cutoff.date())
            .order_by(JournalEntry.date)
            .all()
        ]
    return recoveries, sleeps, workouts, journals


recoveries, sleeps, workouts, journals = load_data(DAYS)
hrv_baseline = get_hrv_baseline()
rhr_baseline = get_rhr_baseline()

st.title("💚 Whoop Health Dashboard")
st.caption(f"Last {DAYS} days · HRV baseline: {hrv_baseline}ms · RHR baseline: {rhr_baseline}bpm")

# ---- KPI row ----
if recoveries:
    latest = recoveries[-1]
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Recovery", f"{latest['recovery_score']}%")
    hrv = latest['hrv_rmssd_milli']
    hrv_delta = f"{round(hrv - hrv_baseline, 1)}ms vs baseline" if hrv and hrv_baseline else None
    col2.metric("HRV", f"{hrv}ms", delta=hrv_delta)
    col3.metric("RHR", f"{latest['resting_heart_rate']}bpm")
    col4.metric("SpO2", f"{latest['spo2_percentage']}%")

st.divider()

# ---- Recovery + HRV ----
if recoveries:
    rec_df = pd.DataFrame([{
        "date": r["date"],
        "Recovery %": r["recovery_score"],
        "HRV (ms)": r["hrv_rmssd_milli"],
        "RHR (bpm)": r["resting_heart_rate"],
    } for r in recoveries])

    col_left, col_right = st.columns(2)

    with col_left:
        st.subheader("Recovery Score")
        fig = px.bar(rec_df, x="date", y="Recovery %",
                     color="Recovery %",
                     color_continuous_scale=["#e74c3c", "#f39c12", "#2ecc71"],
                     range_color=[0, 100])
        fig.update_layout(coloraxis_showscale=False, height=300)
        st.plotly_chart(fig, use_container_width=True)

    with col_right:
        st.subheader("HRV Trend")
        fig = go.Figure()
        fig.add_trace(go.Scatter(x=rec_df["date"], y=rec_df["HRV (ms)"],
                                 mode="lines+markers", name="HRV"))
        if hrv_baseline:
            fig.add_hline(y=hrv_baseline, line_dash="dash", line_color="gray",
                          annotation_text=f"Baseline {hrv_baseline}ms")
        fig.update_layout(height=300)
        st.plotly_chart(fig, use_container_width=True)

# ---- Sleep ----
if sleeps:
    sleep_df = pd.DataFrame([{
        "date": s["date"],
        "Total (h)": round((s["total_in_bed_milli"] or 0) / 3_600_000, 2),
        "Deep (h)": round((s["slow_wave_milli"] or 0) / 3_600_000, 2),
        "REM (h)": round((s["rem_sleep_milli"] or 0) / 3_600_000, 2),
        "Light (h)": round((s["light_sleep_milli"] or 0) / 3_600_000, 2),
        "Performance %": s["sleep_performance_pct"],
        "Nap": s["nap"],
    } for s in sleeps])

    st.subheader("Sleep Breakdown")
    fig = px.bar(sleep_df, x="date", y=["Deep (h)", "REM (h)", "Light (h)"],
                 barmode="stack",
                 color_discrete_map={"Deep (h)": "#1a237e", "REM (h)": "#7986cb", "Light (h)": "#c5cae9"})
    fig.add_hline(y=7.5, line_dash="dash", line_color="green", annotation_text="7.5h target")
    fig.update_layout(height=300)
    st.plotly_chart(fig, use_container_width=True)

# ---- Journal correlations ----
if journals and recoveries:
    st.subheader("Journal × Recovery Correlations")

    journal_df = pd.DataFrame(journals)
    rec_df2 = pd.DataFrame([{
        "date": r["date"],
        "next_hrv": r["hrv_rmssd_milli"],
        "next_recovery": r["recovery_score"],
    } for r in recoveries])

    merged = pd.merge(journal_df, rec_df2, on="date", how="inner")
    if not merged.empty:
        col1, col2 = st.columns(2)
        with col1:
            fig = px.scatter(merged, x="alcohol_units", y="next_hrv",
                             title="Alcohol → Next-day HRV",
                             trendline="ols" if len(merged) > 3 else None,
                             labels={"alcohol_units": "Alcohol units", "next_hrv": "Next-day HRV (ms)"})
            st.plotly_chart(fig, use_container_width=True)
        with col2:
            fig = px.scatter(merged, x="stress_level", y="next_recovery",
                             title="Stress → Next-day Recovery",
                             trendline="ols" if len(merged) > 3 else None,
                             labels={"stress_level": "Stress (1-5)", "next_recovery": "Next-day Recovery %"})
            st.plotly_chart(fig, use_container_width=True)

# ---- Workouts ----
if workouts:
    wk_df = pd.DataFrame([w for w in workouts if w["strain_score"]])
    if not wk_df.empty:
        st.subheader("Workout Strain")
        fig = px.bar(wk_df, x="date", y="strain_score", color="sport_name",
                     labels={"strain_score": "Strain", "sport_name": "Sport"},
                     height=250)
        st.plotly_chart(fig, use_container_width=True)
