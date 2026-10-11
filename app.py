import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

st.set_page_config(
    page_title="NEXUS Industrial | Démonstrateur",
    page_icon="🏭",
    layout="wide",
)

DB_PATH = Path(__file__).parent / "nexus_industrial_demo_v1_1.sqlite"

st.title("🏭 NEXUS Industrial")
st.caption("Démonstrateur de pilotage industriel — données entièrement synthétiques")

st.info(
    "Version de démonstration : les ordres, arrêts, non-conformités et gains affichés "
    "sont fictifs. Ils servent à tester l'application, pas à représenter des résultats réels."
)

if not DB_PATH.exists():
    st.error(
        "La base SQLite est introuvable. Vérifie que le fichier "
        "`nexus_industrial_demo_v1_1.sqlite` se trouve dans le même dossier que `app.py`."
    )
    st.stop()

@st.cache_data
def read_table(table_name):
    # Table names are fixed in this app, not provided by user input.
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        return pd.read_sql_query(f'SELECT * FROM "{table_name}"', con)

@st.cache_data
def table_exists(table_name):
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        result = con.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,)
        ).fetchone()
        return result is not None

def load(table_name):
    return read_table(table_name) if table_exists(table_name) else pd.DataFrame()

orders = load("production_orders")
ops = load("planned_operations")
executions = load("operation_executions")
events = load("production_events")
deviations = load("deviation_records")
inspections = load("inspections")
ncs = load("nonconformities")
actions = load("action_items")
benefits = load("benefit_measurements")

# Sidebar filters
st.sidebar.header("Navigation")
page = st.sidebar.radio(
    "Choisir un module",
    ["Vue générale", "Production & retards", "Arrêts", "Qualité", "Amélioration continue", "Données brutes"],
)
st.sidebar.caption("NEXUS Industrial • V1.1 • Données fictives")

if page == "Vue générale":
    st.subheader("Vue générale")
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Ordres de fabrication", f"{len(orders):,}".replace(",", " "))
    c2.metric("Opérations planifiées", f"{len(ops):,}".replace(",", " "))
    c3.metric("Événements de production", f"{len(events):,}".replace(",", " "))
    c4.metric("Non-conformités", f"{len(ncs):,}".replace(",", " "))

    left, right = st.columns(2)
    with left:
        st.markdown("#### Statut des ordres")
        if not orders.empty and "status" in orders:
            status_df = orders["status"].fillna("Non renseigné").value_counts().rename_axis("Statut").reset_index(name="Nombre")
            st.bar_chart(status_df.set_index("Statut"))
        else:
            st.warning("Aucune donnée de statut disponible.")
    with right:
        st.markdown("#### Types d'événements")
        if not events.empty and "event_type" in events:
            event_df = events["event_type"].fillna("Non renseigné").value_counts().rename_axis("Type").reset_index(name="Nombre")
            st.bar_chart(event_df.set_index("Type"))
        else:
            st.warning("Aucun événement disponible.")

    st.markdown("#### Derniers ordres de fabrication")
    display_cols = [c for c in ["order_number", "status", "planned_quantity", "unit_code", "planned_start_at", "planned_end_at"] if c in orders.columns]
    st.dataframe(orders[display_cols].sort_values(display_cols[-2] if len(display_cols) >= 2 else display_cols[0], ascending=False), use_container_width=True, hide_index=True)

elif page == "Production & retards":
    st.subheader("Production & retards")
    c1, c2, c3 = st.columns(3)
    c1.metric("Ordres", len(orders))
    completed = int((orders["status"].astype(str).str.lower() == "completed").sum()) if not orders.empty and "status" in orders else 0
    c2.metric("Ordres terminés", completed)
    c3.metric("Écarts de production", len(deviations))

    if not deviations.empty:
        st.markdown("#### Écarts enregistrés")
        cols = [c for c in ["detected_at", "planned_operation_id", "deviation_type", "reference_value", "observed_value", "deviation_value", "unit_code", "severity", "status"] if c in deviations.columns]
        st.dataframe(deviations[cols].sort_values("detected_at", ascending=False), use_container_width=True, hide_index=True)
        if {"deviation_type", "deviation_value"}.issubset(deviations.columns):
            chart = deviations.groupby("deviation_type", dropna=False)["deviation_value"].mean().reset_index()
            st.markdown("#### Écart moyen par type")
            st.bar_chart(chart.set_index("deviation_type"))
    else:
        st.info("Aucun écart enregistré.")

    st.markdown("#### Ordres de fabrication")
    st.dataframe(orders, use_container_width=True, hide_index=True)

elif page == "Arrêts":
    st.subheader("Arrêts de production")
    if not events.empty:
        stops = events.copy()
        if "event_type" in stops.columns:
            stops = stops[stops["event_type"].astype(str).str.lower().str.contains("stop|arrêt|arret", regex=True)]
        if {"started_at", "ended_at"}.issubset(stops.columns):
            starts = pd.to_datetime(stops["started_at"], errors="coerce", utc=True)
            ends = pd.to_datetime(stops["ended_at"], errors="coerce", utc=True)
            stops["Durée (minutes)"] = ((ends - starts).dt.total_seconds() / 60).round(1)
        cols = [c for c in ["started_at", "ended_at", "Durée (minutes)", "reason_code", "description", "impact_category", "planned_operation_id"] if c in stops.columns]
        st.metric("Arrêts recensés", len(stops))
        if "Durée (minutes)" in stops.columns:
            st.metric("Durée cumulée (minutes)", f"{stops['Durée (minutes)'].fillna(0).sum():,.1f}".replace(",", " "))
        st.dataframe(stops[cols].sort_values("started_at", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Aucun événement d'arrêt n'est disponible.")

elif page == "Qualité":
    st.subheader("Qualité & non-conformités")
    c1, c2 = st.columns(2)
    c1.metric("Inspections", len(inspections))
    c2.metric("Non-conformités", len(ncs))
    if not ncs.empty:
        st.markdown("#### Registre des non-conformités")
        cols = [c for c in ["reference_code", "description", "severity", "detected_at", "status", "origin_type"] if c in ncs.columns]
        st.dataframe(ncs[cols].sort_values("detected_at", ascending=False), use_container_width=True, hide_index=True)
        if "status" in ncs.columns:
            status_df = ncs["status"].fillna("Non renseigné").value_counts().rename_axis("Statut").reset_index(name="Nombre")
            st.markdown("#### Répartition par statut")
            st.bar_chart(status_df.set_index("Statut"))
    else:
        st.success("Aucune non-conformité dans ce jeu de données.")

    if not inspections.empty:
        st.markdown("#### Inspections")
        st.dataframe(inspections, use_container_width=True, hide_index=True)

elif page == "Amélioration continue":
    st.subheader("Amélioration continue")
    c1, c2 = st.columns(2)
    c1.metric("Actions", len(actions))
    c2.metric("Mesures de bénéfices", len(benefits))

    if not actions.empty:
        st.markdown("#### Plan d'actions")
        cols = [c for c in ["title", "action_type", "priority", "status", "start_date", "due_date", "completed_at"] if c in actions.columns]
        st.dataframe(actions[cols], use_container_width=True, hide_index=True)

    if not benefits.empty:
        st.markdown("#### Mesures avant / après")
        cols = [c for c in ["reference_start", "reference_end", "evaluation_start", "evaluation_end", "baseline_value", "observed_value", "difference_value", "unit_code", "measurement_method"] if c in benefits.columns]
        st.dataframe(benefits[cols], use_container_width=True, hide_index=True)
        if {"baseline_value", "observed_value"}.issubset(benefits.columns):
            chart = benefits[["baseline_value", "observed_value"]].copy()
            chart.index = [f"Mesure {i+1}" for i in range(len(chart))]
            st.markdown("#### Comparaison des valeurs de référence et observées")
            st.bar_chart(chart)

    st.caption("Les valeurs avant/après sont simulées. Elles ne prouvent pas à elles seules la causalité d'une amélioration.")

elif page == "Données brutes":
    st.subheader("Explorateur des tables")
    tables = [
        "production_orders", "planned_operations", "operation_executions",
        "production_events", "deviation_records", "inspections",
        "nonconformities", "action_items", "benefit_measurements"
    ]
    table = st.selectbox("Choisir une table", tables)
    df = load(table)
    st.caption(f"{len(df)} ligne(s) • {len(df.columns)} colonne(s)")
    st.dataframe(df, use_container_width=True, hide_index=True)
    if not df.empty:
        csv = df.to_csv(index=False).encode("utf-8")
        st.download_button("Télécharger cette table en CSV", csv, file_name=f"{table}.csv", mime="text/csv")

st.divider()
st.caption("NEXUS Industrial — prototype de démonstration V1.1 • Données fictives uniquement")
