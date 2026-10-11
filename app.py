import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(page_title="NEXUS Industrial | V1.2", page_icon="🏭", layout="wide")

DB_PATH = Path(__file__).parent / "nexus_industrial_demo_v1_1.sqlite"

st.title("🏭 NEXUS Industrial")
st.caption("Tableau de bord de pilotage industriel — V1.2 · données synthétiques")

st.warning(
    "Démonstrateur pédagogique : les données et les gains sont fictifs. "
    "Ne pas utiliser cette version pour piloter une production réelle."
)

if not DB_PATH.exists():
    st.error(
        "Base de données introuvable. Le fichier `nexus_industrial_demo_v1_1.sqlite` "
        "doit être présent à la racine du dépôt, à côté de `app.py`."
    )
    st.stop()


@st.cache_data
def read_table(table_name):
    # Tables are selected from a fixed list in this app.
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        return pd.read_sql_query(f'SELECT * FROM "{table_name}"', con)


@st.cache_data
def get_table_names():
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        rows = con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    return {row[0] for row in rows}


TABLES = get_table_names()


def load(name):
    return read_table(name) if name in TABLES else pd.DataFrame()


def parse_dates(df, columns):
    for col in columns:
        if col in df.columns:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df


orders = load("production_orders")
ops = load("planned_operations")
executions = load("operation_executions")
events = load("production_events")
deviations = load("deviation_records")
inspections = load("inspections")
ncs = load("nonconformities")
actions = load("action_items")
benefits = load("benefit_measurements")

if orders.empty:
    st.error("La table `production_orders` est vide ou absente.")
    st.stop()

orders = parse_dates(
    orders.copy(),
    ["planned_start_at", "planned_end_at", "actual_start_at", "actual_end_at"],
)
events = parse_dates(events.copy(), ["started_at", "ended_at"])
deviations = parse_dates(deviations.copy(), ["detected_at"])
ncs = parse_dates(ncs.copy(), ["detected_at"])
inspections = parse_dates(inspections.copy(), ["started_at", "completed_at"])

# Derive lateness and durations only where the required timestamps exist.
now = pd.Timestamp.now(tz="UTC")
orders["planned_duration_h"] = (
    (orders["planned_end_at"] - orders["planned_start_at"]).dt.total_seconds() / 3600
)
orders["actual_duration_h"] = (
    (orders["actual_end_at"] - orders["actual_start_at"]).dt.total_seconds() / 3600
)
orders["end_variance_h"] = (
    (orders["actual_end_at"] - orders["planned_end_at"]).dt.total_seconds() / 3600
)
orders["late"] = (
    (orders["actual_end_at"].notna() & orders["planned_end_at"].notna() &
     (orders["actual_end_at"] > orders["planned_end_at"])) |
    (orders["actual_end_at"].isna() & orders["planned_end_at"].notna() &
     (orders["planned_end_at"] < now) &
     (orders["status"].astype(str).str.lower() != "completed"))
)

# Filters
st.sidebar.header("Filtres")
date_col = "planned_start_at"
valid_dates = orders[date_col].dropna()
if valid_dates.empty:
    min_date, max_date = pd.Timestamp("2026-01-01", tz="UTC"), pd.Timestamp.now(tz="UTC")
else:
    min_date = valid_dates.min().normalize()
    max_date = valid_dates.max().normalize()

date_range = st.sidebar.date_input(
    "Période (date de début planifiée)",
    value=(min_date.date(), max_date.date()),
    min_value=min_date.date(),
    max_value=max_date.date(),
)
statuses = sorted(orders["status"].dropna().astype(str).unique().tolist()) if "status" in orders else []
selected_statuses = st.sidebar.multiselect("Statut des ordres", options=statuses, default=statuses)
st.sidebar.caption("Les filtres s'appliquent aux ordres et aux indicateurs qui leur sont rattachés.")

if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
    start_date, end_date = date_range
else:
    start_date, end_date = min_date.date(), max_date.date()

start_ts = pd.Timestamp(start_date, tz="UTC")
end_ts = pd.Timestamp(end_date, tz="UTC") + pd.Timedelta(days=1)
filtered_orders = orders[
    orders["planned_start_at"].ge(start_ts) &
    orders["planned_start_at"].lt(end_ts)
].copy()
if selected_statuses and "status" in filtered_orders:
    filtered_orders = filtered_orders[filtered_orders["status"].astype(str).isin(selected_statuses)]
elif not selected_statuses:
    filtered_orders = filtered_orders.iloc[0:0]

selected_order_ids = set(filtered_orders["id"].astype(str))
filtered_ops = ops[ops["production_order_id"].astype(str).isin(selected_order_ids)].copy() if not ops.empty and "production_order_id" in ops else pd.DataFrame()
selected_op_ids = set(filtered_ops["id"].astype(str)) if not filtered_ops.empty and "id" in filtered_ops else set()

filtered_events = events[events["planned_operation_id"].astype(str).isin(selected_op_ids)].copy() if not events.empty and "planned_operation_id" in events else pd.DataFrame()
filtered_deviations = deviations[deviations["planned_operation_id"].astype(str).isin(selected_op_ids)].copy() if not deviations.empty and "planned_operation_id" in deviations else pd.DataFrame()
filtered_inspections = inspections[inspections["production_order_id"].astype(str).isin(selected_order_ids)].copy() if not inspections.empty and "production_order_id" in inspections else pd.DataFrame()
filtered_ncs = ncs[ncs["production_order_id"].astype(str).isin(selected_order_ids)].copy() if not ncs.empty and "production_order_id" in ncs else pd.DataFrame()

pages = ["Vue générale", "Production & retards", "Arrêts", "Qualité", "Amélioration continue", "Données brutes"]
page = st.sidebar.radio("Navigation", pages)

def fmt_num(value, digits=1):
    if pd.isna(value):
        return "—"
    return f"{value:,.{digits}f}".replace(",", " ").replace(".", ",")

def safe_average(series):
    numeric = pd.to_numeric(series, errors="coerce").dropna()
    return numeric.mean() if not numeric.empty else float("nan")

def duration_minutes(df):
    if df.empty or not {"started_at", "ended_at"}.issubset(df.columns):
        return pd.Series(dtype=float)
    return ((df["ended_at"] - df["started_at"]).dt.total_seconds() / 60).clip(lower=0)

if page == "Vue générale":
    st.subheader("Vue générale")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ordres filtrés", len(filtered_orders))
    c2.metric("Ordres terminés", int((filtered_orders["status"].astype(str).str.lower() == "completed").sum()))
    c3.metric("Ordres en retard", int(filtered_orders["late"].sum()))
    c4.metric("Non-conformités liées", len(filtered_ncs))

    c5, c6, c7 = st.columns(3)
    c5.metric("Durée planifiée moyenne", f"{fmt_num(filtered_orders['planned_duration_h'].mean())} h")
    c6.metric("Durée réelle moyenne", f"{fmt_num(filtered_orders['actual_duration_h'].mean())} h")
    stop_min = duration_minutes(filtered_events)
    c7.metric("Durée d'arrêt cumulée", f"{fmt_num(stop_min.sum(), 0)} min" if not stop_min.empty else "—")

    left, right = st.columns(2)
    with left:
        st.markdown("#### Ordres par statut")
        if not filtered_orders.empty:
            status_df = filtered_orders["status"].fillna("Non renseigné").value_counts().rename_axis("Statut").to_frame("Nombre")
            st.bar_chart(status_df)
        else:
            st.info("Aucun ordre pour ces filtres.")
    with right:
        st.markdown("#### Arrêts par motif")
        if not filtered_events.empty and "reason_code" in filtered_events.columns:
            reason_df = filtered_events["reason_code"].fillna("Non renseigné").value_counts().rename_axis("Motif").to_frame("Nombre")
            st.bar_chart(reason_df)
        else:
            st.info("Aucun arrêt lié aux ordres filtrés.")

    st.markdown("#### Liste des ordres")
    show_cols = [c for c in ["order_number", "status", "planned_quantity", "unit_code", "planned_start_at", "planned_end_at", "actual_start_at", "actual_end_at"] if c in filtered_orders.columns]
    st.dataframe(filtered_orders[show_cols].sort_values("planned_start_at"), use_container_width=True, hide_index=True)

elif page == "Production & retards":
    st.subheader("Production & retards")
    c1, c2, c3 = st.columns(3)
    c1.metric("Ordres", len(filtered_orders))
    c2.metric("En retard", int(filtered_orders["late"].sum()))
    c3.metric("Écarts enregistrés", len(filtered_deviations))

    st.caption("La durée réelle est calculée uniquement pour les ordres ayant une date de début et de fin réelles. Un ordre sans fin réelle n'est pas traité comme terminé.")
    if not filtered_orders.empty:
        cols = [c for c in ["order_number", "status", "planned_start_at", "planned_end_at", "actual_start_at", "actual_end_at", "planned_duration_h", "actual_duration_h", "end_variance_h", "late"] if c in filtered_orders.columns]
        view = filtered_orders[cols].copy()
        for c in ["planned_duration_h", "actual_duration_h", "end_variance_h"]:
            if c in view.columns:
                view[c] = view[c].round(2)
        st.dataframe(view, use_container_width=True, hide_index=True)
    else:
        st.info("Aucun ordre pour ces filtres.")

    st.markdown("#### Écarts enregistrés")
    if not filtered_deviations.empty:
        cols = [c for c in ["detected_at", "deviation_type", "reference_value", "observed_value", "deviation_value", "unit_code", "severity", "status"] if c in filtered_deviations.columns]
        st.dataframe(filtered_deviations[cols], use_container_width=True, hide_index=True)
    else:
        st.info("Aucun écart lié aux opérations sélectionnées.")

elif page == "Arrêts":
    st.subheader("Arrêts de production")
    if not filtered_events.empty:
        filtered_events = filtered_events.copy()
        filtered_events["duration_minutes"] = duration_minutes(filtered_events)
        total = filtered_events["duration_minutes"].sum()
        st.metric("Durée cumulée des événements (minutes)", fmt_num(total, 1))
        st.metric("Événements associés aux opérations filtrées", len(filtered_events))
        cols = [c for c in ["started_at", "ended_at", "duration_minutes", "reason_code", "description", "impact_category", "planned_operation_id"] if c in filtered_events.columns]
        st.dataframe(filtered_events[cols].sort_values("started_at", ascending=False), use_container_width=True, hide_index=True)
        if "reason_code" in filtered_events.columns:
            chart = filtered_events.groupby("reason_code", dropna=False)["duration_minutes"].sum().rename("Minutes").to_frame()
            st.markdown("#### Durée par motif")
            st.bar_chart(chart)
    else:
        st.info("Aucun événement pour les ordres sélectionnés.")

elif page == "Qualité":
    st.subheader("Qualité & non-conformités")
    c1, c2 = st.columns(2)
    c1.metric("Inspections liées aux ordres", len(filtered_inspections))
    c2.metric("Non-conformités liées aux ordres", len(filtered_ncs))
    if not filtered_ncs.empty:
        cols = [c for c in ["reference_code", "description", "severity", "detected_at", "status", "origin_type"] if c in filtered_ncs.columns]
        st.dataframe(filtered_ncs[cols].sort_values("detected_at", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Aucune non-conformité liée aux ordres sélectionnés.")
    if not filtered_inspections.empty:
        st.markdown("#### Inspections")
        st.dataframe(filtered_inspections, use_container_width=True, hide_index=True)
    st.caption("Aucun taux de conformité n'est affiché ici, car il faut des quantités contrôlées et des résultats de contrôle exploitables pour le calculer correctement.")

elif page == "Amélioration continue":
    st.subheader("Amélioration continue")
    c1, c2 = st.columns(2)
    c1.metric("Actions enregistrées", len(actions))
    c2.metric("Mesures de bénéfices enregistrées", len(benefits))
    if not actions.empty:
        st.markdown("#### Plan d'actions")
        cols = [c for c in ["title", "action_type", "priority", "status", "start_date", "due_date", "completed_at"] if c in actions.columns]
        st.dataframe(actions[cols], use_container_width=True, hide_index=True)
    if not benefits.empty:
        st.markdown("#### Mesures avant / après")
        cols = [c for c in ["reference_start", "reference_end", "evaluation_start", "evaluation_end", "baseline_value", "observed_value", "difference_value", "unit_code", "measurement_method"] if c in benefits.columns]
        st.dataframe(benefits[cols], use_container_width=True, hide_index=True)
        st.caption("Les valeurs sont synthétiques. Une comparaison avant/après ne démontre pas, à elle seule, que l'action est la cause du gain.")

else:
    st.subheader("Données brutes")
    available = [
        "production_orders", "planned_operations", "operation_executions",
        "production_events", "deviation_records", "inspections",
        "nonconformities", "action_items", "benefit_measurements"
    ]
    available = [t for t in available if t in TABLES]
    table = st.selectbox("Choisir une table", available)
    df = load(table)
    st.caption(f"{len(df)} ligne(s) · {len(df.columns)} colonne(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        st.download_button(
            "Télécharger la table filtrée en CSV",
            df.to_csv(index=False).encode("utf-8"),
            file_name=f"{table}.csv",
            mime="text/csv",
        )

st.divider()
st.caption("NEXUS Industrial V1.2 · Démonstrateur uniquement · Données fictives")
