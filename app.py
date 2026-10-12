import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from supabase import create_client
except ImportError:
    create_client = None

st.set_page_config(page_title="NEXUS Industrial | PILOT + Q-TRACE + CAPAX + ORION V2.0", page_icon="🏭", layout="wide")

# Futuristic NEXUS theme
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800&display=swap');
.stApp{background:radial-gradient(ellipse at 78% 0%,rgba(20,105,220,.23),transparent 38%),radial-gradient(ellipse at 0% 75%,rgba(0,198,255,.09),transparent 32%),linear-gradient(135deg,#030914 0%,#061326 54%,#030914 100%);color:#eaf4ff}
[data-testid="stHeader"]{background:rgba(3,9,20,.72)}
[data-testid="stSidebar"]{background:linear-gradient(180deg,#07172c,#040b17);border-right:1px solid rgba(20,200,255,.3)}
[data-testid="stSidebar"] *{color:#d9ecff}
h1,h2,h3{color:#f1f8ff!important;letter-spacing:-.03em}
h1{font-weight:800!important;background:linear-gradient(90deg,#f6fbff,#13caff 48%,#9b5cff);-webkit-background-clip:text;-webkit-text-fill-color:transparent}
p,label{color:#a9c3df}
div[data-testid="stMetric"]{background:linear-gradient(145deg,rgba(10,32,60,.96),rgba(6,16,33,.96));border:1px solid rgba(20,200,255,.4);border-radius:16px;padding:17px;box-shadow:0 0 22px rgba(0,153,255,.09);transition:transform .18s ease,box-shadow .18s ease}
div[data-testid="stMetric"]:hover{transform:translateY(-2px);box-shadow:0 0 24px rgba(0,190,255,.2)}
div[data-testid="stMetricLabel"]{color:#9db9d8!important}
div[data-testid="stMetricValue"]{color:#f6fbff!important;font-weight:800}
.stButton>button,.stDownloadButton>button{border:1px solid #138dff;border-radius:12px;color:#f2f8ff;background:linear-gradient(110deg,#0865d8,#4938d9);box-shadow:0 0 16px rgba(0,133,255,.2);font-weight:700}
.stButton>button:hover,.stDownloadButton>button:hover{border-color:#28d6ff;color:white;background:linear-gradient(110deg,#0788ed,#6846ed);box-shadow:0 0 22px rgba(20,200,255,.35)}
div[data-baseweb="select"]>div,div[data-baseweb="input"]>div,div[data-testid="stDateInput"] input{background:#07172c!important;border-color:rgba(20,200,255,.38)!important;border-radius:10px!important;color:#f1f8ff!important}
div[data-testid="stDataFrame"],div[data-testid="stTable"]{border:1px solid rgba(20,200,255,.24);border-radius:12px;overflow:hidden}
div[data-testid="stAlert"]{border-radius:12px;border:1px solid rgba(20,200,255,.3);background:rgba(10,32,60,.72)}
hr{border-color:rgba(20,200,255,.22)}
</style>
""", unsafe_allow_html=True)

DB_PATH = Path(__file__).parent / "nexus_industrial_demo_v1_1.sqlite"

st.markdown("### N E X U S  /  INDUSTRIAL INTELLIGENCE")
st.title("NEXUS INDUSTRIAL")
st.caption("PILOT + Q-TRACE + CAPAX + ORION V2.0  •  PRODUCTION • QUALITY • MAINTENANCE • ANALYTICS")

st.warning("Démonstrateur pédagogique : les données sont synthétiques. Les indicateurs sont calculés à partir des enregistrements disponibles et ne doivent pas servir au pilotage d'une production réelle.")

if not DB_PATH.exists():
    st.error("Base de données introuvable. Vérifie que `nexus_industrial_demo_v1_1.sqlite` est à la racine du dépôt, à côté de `app.py`.")
    st.stop()

@st.cache_data
def get_tables():
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        return {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table'")}

@st.cache_data
def read_table(table):
    with sqlite3.connect(f"file:{DB_PATH}?mode=ro", uri=True) as con:
        return pd.read_sql_query(f'SELECT * FROM "{table}"', con)

TABLES = get_tables()
def load(name):
    return read_table(name) if name in TABLES else pd.DataFrame()

def parse_dates(df, cols):
    for col in cols:
        if col in df:
            df[col] = pd.to_datetime(df[col], errors="coerce", utc=True)
    return df

def duration_seconds(df, start, end):
    if df.empty or start not in df or end not in df:
        return pd.Series(dtype=float, index=df.index)
    return (df[end] - df[start]).dt.total_seconds().clip(lower=0)

def fmt(value, decimals=1):
    if value is None or pd.isna(value):
        return "—"
    return f"{value:,.{decimals}f}".replace(",", " ").replace(".", ",")

orders = load("production_orders")
ops = load("planned_operations")
executions = load("operation_executions")
events = load("production_events")
time_records = load("time_records")
qty_records = load("quantity_records")
deviations = load("deviation_records")
workshops = load("workshops")
islands = load("production_islands")
workstations = load("workstations")
inspections = load("inspections")
inspection_results = load("inspection_results")
nonconformities = load("nonconformities")
dispositions = load("dispositions")
action_items = load("action_items")

if orders.empty:
    st.error("La table `production_orders` est absente ou vide.")
    st.stop()

orders = parse_dates(orders, ["planned_start_at","planned_end_at","actual_start_at","actual_end_at"])
ops = parse_dates(ops, ["planned_start_at","planned_end_at"])
executions = parse_dates(executions, ["started_at","ended_at"])
events = parse_dates(events, ["started_at","ended_at"])
deviations = parse_dates(deviations, ["detected_at"])
inspections = parse_dates(inspections, ["started_at", "completed_at", "inspected_at"])
nonconformities = parse_dates(nonconformities, ["detected_at", "created_at", "closed_at", "due_date"])
action_items = parse_dates(action_items, ["start_date", "due_date", "completed_at"])
time_records = parse_dates(time_records, ["started_at","ended_at"])
qty_records = parse_dates(qty_records, ["recorded_at"])

# Enrich planned operations with workshop / island from workstation.
if not ops.empty and not workstations.empty:
    station_cols = [c for c in ["id","island_id","code","name"] if c in workstations]
    op_enriched = ops.merge(workstations[station_cols], left_on="workstation_id", right_on="id", how="left", suffixes=("","_station"))
    if not islands.empty and "island_id" in op_enriched:
        island_cols = [c for c in ["id","workshop_id","code","name"] if c in islands]
        op_enriched = op_enriched.merge(islands[island_cols], left_on="island_id", right_on="id", how="left", suffixes=("","_island"))
        if not workshops.empty and "workshop_id" in op_enriched:
            workshop_cols = [c for c in ["id","name","code"] if c in workshops]
            op_enriched = op_enriched.merge(workshops[workshop_cols], left_on="workshop_id", right_on="id", how="left", suffixes=("","_workshop"))
    ops_enriched = op_enriched
else:
    ops_enriched = ops.copy()

# Planned and actual time calculations at order level.
if not ops.empty:
    ops["planned_seconds_calc"] = pd.to_numeric(ops.get("planned_setup_seconds", 0), errors="coerce").fillna(0) + pd.to_numeric(ops.get("planned_run_seconds", 0), errors="coerce").fillna(0)
    planned_by_order = ops.groupby("production_order_id")["planned_seconds_calc"].sum()
else:
    planned_by_order = pd.Series(dtype=float)

if not executions.empty:
    executions["actual_seconds_calc"] = duration_seconds(executions, "started_at", "ended_at")
    actual_by_op = executions.groupby("planned_operation_id")["actual_seconds_calc"].sum()
    op_to_order = ops.set_index("id")["production_order_id"] if not ops.empty else pd.Series(dtype=object)
    executions["production_order_id"] = executions["planned_operation_id"].map(op_to_order)
    actual_by_order = executions.groupby("production_order_id")["actual_seconds_calc"].sum()
else:
    actual_by_order = pd.Series(dtype=float)

orders["planned_operation_seconds"] = orders["id"].map(planned_by_order)
orders["actual_execution_seconds"] = orders["id"].map(actual_by_order)
orders["planned_operation_hours"] = orders["planned_operation_seconds"] / 3600
orders["actual_execution_hours"] = orders["actual_execution_seconds"] / 3600
orders["duration_variance_hours"] = (orders["actual_execution_seconds"] - orders["planned_operation_seconds"]) / 3600

now = pd.Timestamp.now(tz="UTC")
orders["is_late"] = (
    orders["planned_end_at"].notna() &
    (
        (orders["actual_end_at"].notna() & (orders["actual_end_at"] > orders["planned_end_at"])) |
        (orders["actual_end_at"].isna() & (orders["planned_end_at"] < now) & (orders["status"].astype(str).str.lower() != "completed"))
    )
)

# Aggregate quantities from recorded quantity entries via execution -> planned operation -> order.
if not qty_records.empty and not executions.empty and not ops.empty and "execution_id" in qty_records:
    qty_join = qty_records.merge(executions[["id","planned_operation_id"]], left_on="execution_id", right_on="id", how="left", suffixes=("","_exec"))
    qty_join = qty_join.merge(ops[["id","production_order_id"]], left_on="planned_operation_id", right_on="id", how="left", suffixes=("","_op"))
    qty_join["quantity"] = pd.to_numeric(qty_join["quantity"], errors="coerce").fillna(0)
    qty_pivot = qty_join.pivot_table(index="production_order_id", columns="quantity_type", values="quantity", aggfunc="sum", fill_value=0)
else:
    qty_pivot = pd.DataFrame()

for qtype, outcol in [("good","good_quantity"),("scrap","scrap_quantity"),("produced","produced_quantity")]:
    orders[outcol] = orders["id"].map(qty_pivot[qtype]) if qtype in qty_pivot.columns else 0.0

# Production workshop labels via order -> planned operations -> workstation / island / workshop.
if not ops_enriched.empty:
    order_workshop = {}
    if "production_order_id" in ops_enriched:
        workshop_name_col = "name_workshop" if "name_workshop" in ops_enriched else ("name_workshop" if "name_workshop" in ops_enriched.columns else None)
        # Determine merged workshop name robustly.
        candidates = [c for c in ops_enriched.columns if c.startswith("name") and "workshop" in c]
        if not candidates:
            candidates = [c for c in ops_enriched.columns if c.endswith("_workshop")]
        if candidates:
            order_workshop = ops_enriched.groupby("production_order_id")[candidates[0]].first().to_dict()
        else:
            # Fallback to island label if available.
            candidates = [c for c in ops_enriched.columns if c.endswith("_island")]
            if candidates:
                order_workshop = ops_enriched.groupby("production_order_id")[candidates[0]].first().to_dict()
    orders["workshop_label"] = orders["id"].map(order_workshop).fillna("Non renseigné")
else:
    orders["workshop_label"] = "Non renseigné"

# Sidebar: range and status / workshop filters.
st.sidebar.markdown("## CENTRE DE CONTRÔLE")
st.sidebar.caption("Filtres PILOT")
date_series = orders["planned_start_at"].dropna()
if date_series.empty:
    dmin, dmax = pd.Timestamp("2026-01-01", tz="UTC").date(), pd.Timestamp.now(tz="UTC").date()
else:
    dmin, dmax = date_series.min().date(), date_series.max().date()
picked_dates = st.sidebar.date_input("Période de début planifié", value=(dmin,dmax), min_value=dmin, max_value=dmax)
if isinstance(picked_dates, (tuple,list)) and len(picked_dates) == 2:
    date_start, date_end = picked_dates
else:
    date_start = date_end = picked_dates
status_options = sorted(orders["status"].dropna().astype(str).unique())
picked_status = st.sidebar.multiselect("Statut", status_options, default=status_options)
workshop_options = sorted(orders["workshop_label"].dropna().astype(str).unique())
picked_workshops = st.sidebar.multiselect("Atelier", workshop_options, default=workshop_options)

start_ts = pd.Timestamp(date_start, tz="UTC")
end_ts = pd.Timestamp(date_end, tz="UTC") + pd.Timedelta(days=1)
filtered = orders[orders["planned_start_at"].ge(start_ts) & orders["planned_start_at"].lt(end_ts)].copy()
filtered = filtered[filtered["status"].astype(str).isin(picked_status)] if picked_status else filtered.iloc[0:0]
filtered = filtered[filtered["workshop_label"].astype(str).isin(picked_workshops)] if picked_workshops else filtered.iloc[0:0]

order_ids = set(filtered["id"].astype(str))
filtered_ops = ops[ops["production_order_id"].astype(str).isin(order_ids)].copy() if not ops.empty else pd.DataFrame()
op_ids = set(filtered_ops["id"].astype(str)) if not filtered_ops.empty else set()
filtered_exec = executions[executions["planned_operation_id"].astype(str).isin(op_ids)].copy() if not executions.empty else pd.DataFrame()
filtered_events = events[events["planned_operation_id"].astype(str).isin(op_ids)].copy() if not events.empty else pd.DataFrame()
filtered_deviations = deviations[deviations["planned_operation_id"].astype(str).isin(op_ids)].copy() if not deviations.empty else pd.DataFrame()

def get_supabase_client():
    """Client Supabase avec la clé publishable; les droits sont définis par les policies RLS."""
    try:
        if create_client is not None and "supabase" in st.secrets:
            url = st.secrets["supabase"]["url"]
            key = st.secrets["supabase"]["publishable_key"]
            if url and key:
                return create_client(url, key)
    except Exception:
        return None
    return None

def audit_public_event(client, module, action, record_ref, details):
    """Journal d'audit best-effort. Le registre reste une démo publique, sans identité vérifiée."""
    try:
        if client is not None:
            client.table("nexus_audit_log").insert({
                "module": module,
                "action": action,
                "record_ref": str(record_ref),
                "details": str(details)[:1000]
            }).execute()
    except Exception:
        # Don't fail the user's primary action if the audit table is unavailable.
        pass

pages = ["Vue générale", "PILOT · Production", "Retards & écarts", "Arrêts", "Q-TRACE · Qualité", "CAPAX · Maintenance", "ORION · Analyse", "Actions & journal", "Données brutes"]
page = st.sidebar.radio("Navigation", pages)

if page == "Vue générale":
    st.subheader("Vue générale · Centre de pilotage intégré")
    st.caption("Vue consolidée PILOT + Q-TRACE + CAPAX + ORION. Les données restent synthétiques et publiques.")
    sb_global = get_supabase_client()
    global_nc, global_assets, global_jobs = [], [], []
    if sb_global is not None:
        try: global_nc = sb_global.table("nexus_nonconformities").select("*").execute().data or []
        except Exception: pass
        try: global_assets = sb_global.table("capax_equipment").select("*").execute().data or []
        except Exception: pass
        try: global_jobs = sb_global.table("capax_work_orders").select("*").execute().data or []
        except Exception: pass
    a,b,c,d = st.columns(4)
    a.metric("Ordres filtrés", len(filtered))
    b.metric("Terminés", int((filtered["status"].astype(str).str.lower()=="completed").sum()))
    c.metric("Ordres en retard", int(filtered["is_late"].sum()))
    d.metric("Écarts enregistrés", len(filtered_deviations))
    e,f,g,h = st.columns(4)
    e.metric("Quantité bonne", fmt(filtered["good_quantity"].sum(),0))
    f.metric("Rebuts enregistrés", fmt(filtered["scrap_quantity"].sum(),0))
    f1 = filtered["planned_operation_hours"].dropna()
    f2 = filtered["actual_execution_hours"].dropna()
    g.metric("Temps prévu (h)", fmt(f1.sum(),1) if not f1.empty else "—")
    h.metric("Temps réel enregistré (h)", fmt(f2.sum(),1) if not f2.empty else "—")
    st.markdown("#### État des modules connectés")
    q1,q2,q3,q4 = st.columns(4)
    q1.metric("Q-TRACE · Non-conformités", len(global_nc))
    q2.metric("CAPAX · Équipements", len(global_assets))
    q3.metric("CAPAX · Interventions", len(global_jobs))
    q4.metric("CAPAX · Interventions ouvertes", sum(1 for x in global_jobs if x.get("status") not in ["Terminée","Clôturée"]))
    left,right = st.columns(2)
    with left:
        st.markdown("#### Ordres par statut")
        if not filtered.empty:
            st.bar_chart(filtered["status"].fillna("Inconnu").value_counts().to_frame("Ordres"))
        else:
            st.info("Aucun ordre pour ces filtres.")
    with right:
        st.markdown("#### Temps prévu / réel par ordre (heures)")
        chart = filtered.set_index("order_number")[["planned_operation_hours","actual_execution_hours"]].rename(columns={"planned_operation_hours":"Prévu","actual_execution_hours":"Réel"})
        if not chart.empty:
            st.bar_chart(chart)
        else:
            st.info("Pas de temps disponible.")
    st.markdown("#### Ordres de fabrication")
    cols = ["order_number","status","workshop_label","planned_quantity","good_quantity","scrap_quantity","planned_start_at","planned_end_at","planned_operation_hours","actual_execution_hours","duration_variance_hours","is_late"]
    cols = [c for c in cols if c in filtered]
    st.dataframe(filtered[cols].sort_values("planned_start_at"), use_container_width=True, hide_index=True)

elif page == "PILOT · Production":
    st.subheader("PILOT · Production")
    st.markdown("Suivi des quantités enregistrées et des temps planifiés/réellement tracés.")
    a,b,c,d = st.columns(4)
    a.metric("Ordres",len(filtered))
    b.metric("Quantité planifiée",fmt(pd.to_numeric(filtered["planned_quantity"],errors="coerce").sum(),0))
    c.metric("Quantité bonne enregistrée",fmt(filtered["good_quantity"].sum(),0))
    d.metric("Rebuts enregistrés",fmt(filtered["scrap_quantity"].sum(),0))
    st.caption("Les quantités proviennent de `quantity_records` et sont rattachées aux ordres par les exécutions. Une valeur nulle signifie qu'aucune quantité de ce type n'est enregistrée, pas nécessairement zéro production.")
    cols = ["order_number","status","workshop_label","planned_quantity","good_quantity","scrap_quantity","unit_code","planned_operation_hours","actual_execution_hours","duration_variance_hours"]
    cols = [c for c in cols if c in filtered]
    st.dataframe(filtered[cols], use_container_width=True, hide_index=True)
    if not filtered.empty:
        chart = filtered.set_index("order_number")[["planned_operation_hours","actual_execution_hours"]].rename(columns={"planned_operation_hours":"Prévu (h)","actual_execution_hours":"Réel (h)"})
        st.markdown("#### Comparaison des temps")
        st.bar_chart(chart)
    st.download_button("Exporter les ordres filtrés en CSV",filtered.to_csv(index=False).encode("utf-8"),"nexus_pilot_orders.csv","text/csv")

elif page == "Retards & écarts":
    st.subheader("Retards & écarts")
    a,b,c = st.columns(3)
    a.metric("Ordres en retard",int(filtered["is_late"].sum()))
    b.metric("Écarts saisis",len(filtered_deviations))
    c.metric("Écart moyen de temps (h)",fmt(filtered["duration_variance_hours"].dropna().mean(),2))
    st.caption("Un ordre est considéré en retard si sa date de fin réelle dépasse la fin planifiée, ou si l'échéance est dépassée et l'ordre n'est pas terminé. Une échéance planifiée manquante n'est pas déclarée en retard.")
    cols = ["order_number","status","planned_end_at","actual_end_at","is_late","planned_operation_hours","actual_execution_hours","duration_variance_hours"]
    cols = [c for c in cols if c in filtered]
    st.dataframe(filtered[cols].sort_values(["is_late","planned_end_at"],ascending=[False,True]),use_container_width=True,hide_index=True)
    st.markdown("#### Écarts saisis dans le registre")
    if not filtered_deviations.empty:
        cols = [c for c in ["detected_at","deviation_type","reference_value","observed_value","deviation_value","unit_code","severity","status"] if c in filtered_deviations]
        st.dataframe(filtered_deviations[cols],use_container_width=True,hide_index=True)
    else:
        st.info("Aucun écart lié aux opérations filtrées.")

elif page == "Arrêts":
    st.subheader("Arrêts de production")
    if not filtered_events.empty:
        filtered_events = filtered_events.copy()
        filtered_events["duration_minutes"] = duration_seconds(filtered_events,"started_at","ended_at")/60
        total_min = filtered_events["duration_minutes"].sum()
        a,b = st.columns(2)
        a.metric("Événements",len(filtered_events))
        b.metric("Durée cumulée enregistrée",f"{fmt(total_min,1)} min")
        cols = [c for c in ["started_at","ended_at","duration_minutes","event_type","reason_code","description","impact_category"] if c in filtered_events]
        st.dataframe(filtered_events[cols].sort_values("started_at",ascending=False),use_container_width=True,hide_index=True)
        if "reason_code" in filtered_events:
            st.markdown("#### Durée cumulée par motif")
            st.bar_chart(filtered_events.groupby("reason_code")["duration_minutes"].sum().to_frame("Minutes"))
    else:
        st.info("Aucun événement d'arrêt associé aux ordres sélectionnés.")

elif page == "Q-TRACE · Qualité":
    st.subheader("Q-TRACE · Surveillance qualité")
    st.caption("Suivi des inspections et non-conformités enregistrées dans la base. Aucune donnée manquante n'est remplacée par une estimation.")

    # Optional filters use only columns present in the current schema.
    nc_view = nonconformities.copy()
    if not nc_view.empty:
        filter_cols = st.columns(3)
        status_col = "status" if "status" in nc_view.columns else None
        severity_col = "severity" if "severity" in nc_view.columns else None
        if status_col:
            status_values = sorted(nc_view[status_col].dropna().astype(str).unique())
            chosen_nc_status = filter_cols[0].multiselect("Statut de non-conformité", status_values, default=status_values)
            nc_view = nc_view[nc_view[status_col].astype(str).isin(chosen_nc_status)] if chosen_nc_status else nc_view.iloc[0:0]
        if severity_col:
            severity_values = sorted(nc_view[severity_col].dropna().astype(str).unique())
            chosen_severity = filter_cols[1].multiselect("Gravité", severity_values, default=severity_values)
            nc_view = nc_view[nc_view[severity_col].astype(str).isin(chosen_severity)] if chosen_severity else nc_view.iloc[0:0]
        date_candidates = [c for c in ["detected_at", "created_at"] if c in nc_view.columns]
        if date_candidates:
            dcol = date_candidates[0]
            valid = nc_view[dcol].dropna()
            if not valid.empty:
                qdate = filter_cols[2].date_input(
                    "Défauts détectés après le",
                    value=valid.min().date(),
                    min_value=valid.min().date(),
                    max_value=max(valid.max().date(), valid.min().date())
                )
                nc_view = nc_view[nc_view[dcol].isna() | (nc_view[dcol].dt.date >= qdate)]

    c1, c2, c3 = st.columns(3)
    c1.metric("Inspections enregistrées", len(inspections))
    c2.metric("Non-conformités visibles", len(nc_view))
    if not nc_view.empty and "status" in nc_view.columns:
        open_mask = ~nc_view["status"].astype(str).str.lower().isin(["closed", "closed - verified", "resolved", "cloturee", "clôturée", "terminee", "terminée"])
        c3.metric("Non-conformités non clôturées", int(open_mask.sum()))
    else:
        c3.metric("Non-conformités non clôturées", "—")

    st.markdown("#### Registre des non-conformités")
    if nc_view.empty:
        st.info("Aucune non-conformité ne correspond aux filtres, ou aucune donnée n'est enregistrée.")
    else:
        preferred = ["reference_code", "description", "severity", "status", "detected_at", "due_date", "closed_at", "origin_type"]
        cols = [c for c in preferred if c in nc_view.columns]
        cols += [c for c in nc_view.columns if c not in cols and c not in ["id"]]
        st.dataframe(nc_view[cols], use_container_width=True, hide_index=True)
        st.download_button("Exporter les non-conformités filtrées en CSV", nc_view.to_csv(index=False).encode("utf-8"), "nexus_qtrace_nonconformities.csv", "text/csv")

    st.markdown("#### Inspections")
    if inspections.empty:
        st.info("Aucune inspection disponible.")
    else:
        st.dataframe(inspections, use_container_width=True, hide_index=True)
        st.download_button("Exporter les inspections en CSV", inspections.to_csv(index=False).encode("utf-8"), "nexus_qtrace_inspections.csv", "text/csv")

    if not inspection_results.empty:
        st.markdown("#### Résultats de contrôle")
        st.dataframe(inspection_results, use_container_width=True, hide_index=True)

    if not dispositions.empty:
        st.markdown("#### Décisions et dispositions")
        st.dataframe(dispositions, use_container_width=True, hide_index=True)

    if not action_items.empty:
        st.markdown("#### Actions correctives associées au système")
        st.dataframe(action_items, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Registre persistant NEXUS")
    st.warning(
        "MODE TEST PUBLIC : toute personne qui visite cette application peut créer, modifier ou supprimer "
        "les fiches de démonstration. N'utilise aucune donnée personnelle, confidentielle ou industrielle réelle."
    )

    supabase_client = None
    try:
        if create_client is not None and "supabase" in st.secrets:
            sb_url = st.secrets["supabase"]["url"]
            # Public/publishable key; permissions are enforced by Supabase RLS.
            sb_key = st.secrets["supabase"]["publishable_key"]
            if sb_url and sb_key:
                supabase_client = create_client(sb_url, sb_key)
    except Exception:
        supabase_client = None

    live_rows = []
    if supabase_client is None:
        st.warning(
            "Registre persistant non connecté. Dans Streamlit Cloud > Settings > Secrets, configure "
            "[supabase] avec url et publishable_key. N'ajoute pas de service_role key."
        )
    else:
        try:
            live_result = supabase_client.table("nexus_nonconformities").select("*").order("created_at", desc=True).execute()
            live_rows = live_result.data or []
            if live_rows:
                live_df = pd.DataFrame(live_rows)
                st.dataframe(live_df.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)
                st.download_button("Exporter le registre NEXUS en CSV", live_df.to_csv(index=False).encode("utf-8"), "nexus_nonconformites.csv", "text/csv")
            else:
                st.info("Aucune fiche NEXUS créée pour le moment. Lance un essai avec le formulaire ci-dessous.")
        except Exception as exc:
            st.error(
                "Impossible de lire le registre. Vérifie que le nouveau script SQL a été exécuté et que "
                "la clé publishable est correcte. Détail technique : " + str(exc)
            )

    if supabase_client is not None:
        # Charger les équipements pour créer une vraie relation par identifiant, pas seulement un code texte.
        equipment_rows = []
        try:
            equipment_rows = supabase_client.table("capax_equipment").select("id,asset_code,name").order("asset_code").execute().data or []
        except Exception:
            equipment_rows = []
        equipment_options = {f"{r['asset_code']} — {r['name']}": r for r in equipment_rows}
        st.markdown("##### Créer une non-conformité")
        with st.form("create_nc_form", clear_on_submit=True):
            a, b = st.columns(2)
            nc_ref = a.text_input("Référence", placeholder="Ex. TEST-2026-001", max_chars=40)
            nc_severity = b.selectbox("Gravité", ["Faible", "Moyenne", "Élevée", "Critique"])
            nc_desc = st.text_area("Description du défaut", placeholder="Décrire le défaut fictif observé…", max_chars=2000)
            nc_equipment_label = st.selectbox("Équipement concerné (facultatif)", ["Aucun équipement lié"] + list(equipment_options.keys()))
            c, d = st.columns(2)
            nc_origin = c.text_input("Origine / atelier", placeholder="Ex. Atelier de démonstration")
            nc_owner = d.text_input("Responsable", placeholder="Nom ou fonction fictive")
            e, f = st.columns(2)
            nc_due = e.date_input("Échéance de traitement")
            nc_status = f.selectbox("Statut initial", ["Ouverte", "En cours", "En attente"])
            nc_action = st.text_area("Action corrective prévue", placeholder="Action à tester…", max_chars=2000)
            submitted = st.form_submit_button("Créer la fiche publique")
        if submitted:
            if not nc_ref.strip() or not nc_desc.strip():
                st.error("La référence et la description sont obligatoires.")
            else:
                payload = {
                    "reference_code": nc_ref.strip(),
                    "severity": nc_severity,
                    "description": nc_desc.strip(),
                    "origin": nc_origin.strip() or None,
                    "owner": nc_owner.strip() or None,
                    "due_date": nc_due.isoformat(),
                    "status": nc_status,
                    "corrective_action": nc_action.strip() or None,
                    "equipment_id": equipment_options[nc_equipment_label]["id"] if nc_equipment_label in equipment_options else None
                }
                try:
                    supabase_client.table("nexus_nonconformities").insert(payload).execute()
                    audit_public_event(supabase_client, "Q-TRACE", "CREATE", payload["reference_code"], payload["description"])
                    st.success("Fiche créée et enregistrée dans Supabase.")
                    st.rerun()
                except Exception as exc:
                    st.error("Création impossible. Vérifie que la référence est unique et que les règles SQL publiques sont activées. Détail : " + str(exc))

        if live_rows:
            st.markdown("##### Modifier une fiche existante")
            options = {f"{r['reference_code']} — {str(r['description'])[:55]}": r["id"] for r in live_rows}
            selected_label = st.selectbox("Fiche à modifier", list(options.keys()))
            selected_row = next(r for r in live_rows if r["id"] == options[selected_label])
            with st.form("update_nc_form"):
                u1, u2 = st.columns(2)
                statuses = ["Ouverte", "En cours", "En attente", "Résolue", "Clôturée"]
                current_status = selected_row.get("status") if selected_row.get("status") in statuses else "Ouverte"
                upd_status = u1.selectbox("Statut", statuses, index=statuses.index(current_status))
                severity_options = ["Faible", "Moyenne", "Élevée", "Critique"]
                current_severity = selected_row.get("severity") if selected_row.get("severity") in severity_options else "Moyenne"
                upd_severity = u2.selectbox("Gravité", severity_options, index=severity_options.index(current_severity))
                upd_desc = st.text_area("Description", value=selected_row.get("description") or "", max_chars=2000)
                upd_owner = st.text_input("Responsable", value=selected_row.get("owner") or "")
                upd_origin = st.text_input("Origine / atelier", value=selected_row.get("origin") or "")
                from datetime import date
                try:
                    current_due = date.fromisoformat(str(selected_row.get("due_date"))) if selected_row.get("due_date") else date.today()
                except Exception:
                    current_due = date.today()
                upd_due = st.date_input("Échéance", value=current_due, key="qtrace_due_edit")
                upd_action = st.text_area("Action corrective / commentaire", value=selected_row.get("corrective_action") or "", max_chars=2000)
                upd_done = st.form_submit_button("Enregistrer les modifications")
            if upd_done:
                try:
                    from datetime import datetime, timezone
                    update_payload = {
                        "status": upd_status,
                        "severity": upd_severity,
                        "description": upd_desc.strip(),
                        "owner": upd_owner.strip() or None,
                        "origin": upd_origin.strip() or None,
                        "due_date": upd_due.isoformat(),
                        "corrective_action": upd_action.strip() or None,
                        "closed_at": datetime.now(timezone.utc).isoformat() if upd_status in ["Résolue", "Clôturée"] else None
                    }
                    if not update_payload["description"]:
                        st.error("La description ne peut pas être vide.")
                    else:
                        supabase_client.table("nexus_nonconformities").update(update_payload).eq("id", options[selected_label]).execute()
                        audit_public_event(supabase_client, "Q-TRACE", "UPDATE", selected_row.get("reference_code", options[selected_label]), f"Statut={upd_status}; gravité={upd_severity}")
                        st.success("Fiche mise à jour.")
                        st.rerun()
                except Exception as exc:
                    st.error("La modification a échoué. Vérifie les règles SQL publiques. Détail : " + str(exc))

            st.markdown("##### Supprimer une fiche de test")
            st.caption("La suppression est définitive. N'utilise cette action que pour nettoyer des fiches fictives.")
            confirm_delete = st.checkbox("Je confirme vouloir supprimer cette fiche de démonstration.")
            if st.button("Supprimer la fiche sélectionnée", disabled=not confirm_delete):
                try:
                    supabase_client.table("nexus_nonconformities").delete().eq("id", options[selected_label]).execute()
                    audit_public_event(supabase_client, "Q-TRACE", "DELETE", selected_row.get("reference_code", options[selected_label]), "Suppression d'une fiche de démonstration")
                    st.success("Fiche supprimée.")
                    st.rerun()
                except Exception as exc:
                    st.error("La suppression a échoué. Vérifie les règles SQL publiques. Détail : " + str(exc))

elif page == "CAPAX · Maintenance":
    st.subheader("CAPAX · Maintenance & interventions")
    st.caption("Registre public de démonstration : les visiteurs peuvent créer et modifier des équipements et interventions fictifs.")
    st.warning("Données synthétiques uniquement. Tout visiteur peut ajouter, modifier ou supprimer les fiches visibles.")
    sb = get_supabase_client()
    if sb is None:
        st.error("Connexion Supabase indisponible. Vérifie Settings → Secrets.")
    else:
        assets, jobs = [], []
        try:
            assets = sb.table("capax_equipment").select("*").order("created_at", desc=True).execute().data or []
            jobs = sb.table("capax_work_orders").select("*").order("created_at", desc=True).execute().data or []
        except Exception as exc:
            st.error("Les tables CAPAX ne sont pas encore accessibles. Exécute `supabase_nexus_v2_0_migration.sql` dans Supabase. Détail : " + str(exc))
        m1,m2,m3 = st.columns(3)
        m1.metric("Équipements enregistrés", len(assets))
        m2.metric("Interventions", len(jobs))
        m3.metric("Interventions ouvertes", sum(1 for x in jobs if x.get("status") not in ["Terminée","Clôturée"]))
        st.markdown("#### Parc équipements")
        with st.form("capax_asset_create", clear_on_submit=True):
            c1,c2 = st.columns(2)
            asset_code = c1.text_input("Code équipement", placeholder="EQ-TEST-001")
            asset_name = c2.text_input("Nom de l'équipement", placeholder="Convoyeur de démonstration")
            c3,c4,c5 = st.columns(3)
            asset_area = c3.text_input("Atelier / zone", placeholder="Atelier A")
            asset_criticality = c4.selectbox("Criticité", ["Faible","Moyenne","Élevée","Critique"])
            asset_state = c5.selectbox("État", ["Opérationnel","Dégradé","À l'arrêt","En maintenance"])
            asset_note = st.text_area("Notes de maintenance", max_chars=1000)
            asset_submit = st.form_submit_button("Ajouter l'équipement")
        if asset_submit:
            if not asset_code.strip() or not asset_name.strip():
                st.error("Le code et le nom sont obligatoires.")
            else:
                try:
                    sb.table("capax_equipment").insert({
                        "asset_code":asset_code.strip(),"name":asset_name.strip(),"area":asset_area.strip() or None,
                        "criticality":asset_criticality,"status":asset_state,"notes":asset_note.strip() or None
                    }).execute()
                    audit_public_event(sb,"CAPAX","CREATE_ASSET",asset_code,asset_name)
                    st.success("Équipement ajouté."); st.rerun()
                except Exception as exc: st.error("Ajout impossible (code potentiellement déjà utilisé). Détail : "+str(exc))
        if assets:
            asset_df=pd.DataFrame(assets)
            st.dataframe(asset_df.drop(columns=["id"],errors="ignore"),use_container_width=True,hide_index=True)
            st.download_button("Exporter le parc équipements CSV",asset_df.to_csv(index=False).encode("utf-8"),"capax_equipements.csv","text/csv")
            labels={f"{x['asset_code']} — {x['name']}":x for x in assets}
            chosen_asset_label=st.selectbox("Équipement à modifier",list(labels.keys()),key="capax_asset_pick")
            chosen_asset=labels[chosen_asset_label]
            with st.form("capax_asset_update"):
                u1,u2=st.columns(2)
                updated_asset_state=u1.selectbox("Nouvel état",["Opérationnel","Dégradé","À l'arrêt","En maintenance"],index=["Opérationnel","Dégradé","À l'arrêt","En maintenance"].index(chosen_asset.get("status") if chosen_asset.get("status") in ["Opérationnel","Dégradé","À l'arrêt","En maintenance"] else "Opérationnel"))
                updated_asset_criticality=u2.selectbox("Nouvelle criticité",["Faible","Moyenne","Élevée","Critique"],index=["Faible","Moyenne","Élevée","Critique"].index(chosen_asset.get("criticality") if chosen_asset.get("criticality") in ["Faible","Moyenne","Élevée","Critique"] else "Moyenne"))
                updated_asset_notes=st.text_area("Notes",value=chosen_asset.get("notes") or "")
                update_asset_submit=st.form_submit_button("Enregistrer les modifications équipement")
            if update_asset_submit:
                try:
                    sb.table("capax_equipment").update({"status":updated_asset_state,"criticality":updated_asset_criticality,"notes":updated_asset_notes.strip() or None}).eq("id",chosen_asset["id"]).execute()
                    audit_public_event(sb,"CAPAX","UPDATE_ASSET",chosen_asset["asset_code"],updated_asset_state)
                    st.success("Équipement mis à jour."); st.rerun()
                except Exception as exc: st.error("Modification impossible : "+str(exc))
            delete_asset_confirm=st.checkbox("Confirmer la suppression de cet équipement fictif",key="capax_delete_asset_confirm")
            if st.button("Supprimer cet équipement",disabled=not delete_asset_confirm,key="capax_delete_asset_btn"):
                try:
                    sb.table("capax_equipment").delete().eq("id",chosen_asset["id"]).execute()
                    audit_public_event(sb,"CAPAX","DELETE_ASSET",chosen_asset["asset_code"],"Suppression équipement de démonstration")
                    st.success("Équipement supprimé."); st.rerun()
                except Exception as exc: st.error("Suppression impossible. Vérifie si des interventions y sont liées. Détail : "+str(exc))
        st.markdown("#### Interventions de maintenance")
        asset_choices={f"{x['asset_code']} — {x['name']}": x for x in assets}
        with st.form("capax_job_create",clear_on_submit=True):
            j1,j2=st.columns(2)
            job_ref=j1.text_input("Référence intervention",placeholder="WO-TEST-001")
            job_asset=j2.selectbox("Équipement associé",["Non affecté"]+list(asset_choices.keys()))
            j3,j4,j5=st.columns(3)
            job_type=j3.selectbox("Type",["Préventive","Corrective","Améliorative","Inspection"])
            job_priority=j4.selectbox("Priorité",["Basse","Normale","Haute","Urgente"])
            job_status=j5.selectbox("Statut",["À planifier","Planifiée","En cours","En attente","Terminée"])
            job_owner=st.text_input("Technicien / responsable",placeholder="Équipe maintenance")
            job_desc=st.text_area("Description / travail prévu",max_chars=2000)
            job_due=st.date_input("Date cible")
            job_submit=st.form_submit_button("Créer l'intervention")
        if job_submit:
            if not job_ref.strip() or not job_desc.strip():
                st.error("La référence et la description sont obligatoires.")
            else:
                try:
                    sb.table("capax_work_orders").insert({
                        "work_order_code":job_ref.strip(),
                        "asset_code":asset_choices.get(job_asset, {}).get("asset_code"),
                        "equipment_id":asset_choices.get(job_asset, {}).get("id"),
                        "work_type":job_type,"priority":job_priority,"status":job_status,
                        "owner":job_owner.strip() or None,"description":job_desc.strip(),"due_date":job_due.isoformat()
                    }).execute()
                    audit_public_event(sb,"CAPAX","CREATE_WORK_ORDER",job_ref,job_desc)
                    st.success("Intervention enregistrée."); st.rerun()
                except Exception as exc: st.error("Création impossible (référence potentiellement déjà utilisée). Détail : "+str(exc))
        if jobs:
            job_df=pd.DataFrame(jobs)
            st.dataframe(job_df.drop(columns=["id"],errors="ignore"),use_container_width=True,hide_index=True)
            st.download_button("Exporter les interventions CSV",job_df.to_csv(index=False).encode("utf-8"),"capax_interventions.csv","text/csv")
            job_labels={f"{x['work_order_code']} — {x['status']}":x for x in jobs}
            chosen_job_label=st.selectbox("Intervention à modifier",list(job_labels.keys()),key="capax_job_pick")
            chosen_job=job_labels[chosen_job_label]
            with st.form("capax_job_update"):
                new_job_status=st.selectbox("Nouveau statut",["À planifier","Planifiée","En cours","En attente","Terminée","Clôturée"],index=["À planifier","Planifiée","En cours","En attente","Terminée","Clôturée"].index(chosen_job.get("status") if chosen_job.get("status") in ["À planifier","Planifiée","En cours","En attente","Terminée","Clôturée"] else "À planifier"))
                new_job_owner=st.text_input("Responsable",value=chosen_job.get("owner") or "")
                new_job_note=st.text_area("Description",value=chosen_job.get("description") or "")
                update_job_submit=st.form_submit_button("Enregistrer l'intervention")
            if update_job_submit:
                try:
                    sb.table("capax_work_orders").update({"status":new_job_status,"owner":new_job_owner.strip() or None,"description":new_job_note.strip()}).eq("id",chosen_job["id"]).execute()
                    audit_public_event(sb,"CAPAX","UPDATE_WORK_ORDER",chosen_job["work_order_code"],new_job_status)
                    st.success("Intervention mise à jour."); st.rerun()
                except Exception as exc: st.error("Modification impossible : "+str(exc))
            delete_job_confirm=st.checkbox("Confirmer la suppression de cette intervention fictive",key="capax_delete_job_confirm")
            if st.button("Supprimer cette intervention",disabled=not delete_job_confirm,key="capax_delete_job_btn"):
                try:
                    sb.table("capax_work_orders").delete().eq("id",chosen_job["id"]).execute()
                    audit_public_event(sb,"CAPAX","DELETE_WORK_ORDER",chosen_job["work_order_code"],"Suppression intervention de démonstration")
                    st.success("Intervention supprimée."); st.rerun()
                except Exception as exc: st.error("Suppression impossible : "+str(exc))

elif page == "Actions & journal":
    st.subheader("Actions correctives & journal de traçabilité")
    st.caption("Registre public de démonstration : les actions et les événements sont visibles par tous.")
    st.warning("Les fiches peuvent être modifiées par tous les visiteurs. Le journal est utile pour la démonstration, mais n'est pas inviolable et n'identifie pas les auteurs.")
    sb = get_supabase_client()
    if sb is None:
        st.error("Connexion Supabase indisponible. Vérifie Settings → Secrets.")
    else:
        action_rows, audit_rows, nc_rows = [], [], []
        try:
            action_rows = sb.table("nexus_corrective_actions").select("*").order("created_at", desc=True).execute().data or []
        except Exception as exc:
            st.error("Table des actions indisponible. Exécute le SQL V1.8. Détail : " + str(exc))
        try:
            audit_rows = sb.table("nexus_audit_log").select("*").order("created_at", desc=True).limit(200).execute().data or []
        except Exception:
            audit_rows = []
        try:
            nc_rows = sb.table("nexus_nonconformities").select("id,reference_code,description,status").order("created_at", desc=True).execute().data or []
        except Exception:
            nc_rows = []
        a,b,c = st.columns(3)
        a.metric("Actions correctives", len(action_rows))
        b.metric("Actions non terminées", sum(1 for r in action_rows if r.get("status") not in ["Terminée","Clôturée"]))
        c.metric("Événements journalisés (200 max)", len(audit_rows))
        st.markdown("#### Créer une action corrective")
        nc_by_ref = {r.get("reference_code", ""): r for r in nc_rows}
        nc_refs = list(nc_by_ref.keys())
        with st.form("nexus_action_create", clear_on_submit=True):
            x1,x2 = st.columns(2)
            action_ref = x1.text_input("Référence action", placeholder="AC-TEST-001")
            linked_nc = x2.selectbox("Non-conformité liée", ["Aucune"] + nc_refs)
            action_title = st.text_input("Intitulé", placeholder="Vérifier le réglage de démonstration")
            action_desc = st.text_area("Description / preuve attendue", max_chars=2000)
            x3,x4,x5 = st.columns(3)
            action_owner = x3.text_input("Responsable", placeholder="Équipe de démonstration")
            action_status = x4.selectbox("Statut", ["À faire","En cours","En attente","Terminée","Clôturée"])
            action_priority = x5.selectbox("Priorité", ["Basse","Normale","Haute","Critique"])
            action_due = st.date_input("Échéance de l'action")
            action_create = st.form_submit_button("Créer l'action corrective")
        if action_create:
            if not action_ref.strip() or not action_title.strip():
                st.error("La référence et l'intitulé sont obligatoires.")
            else:
                try:
                    selected_nc = None if linked_nc == "Aucune" else nc_by_ref[linked_nc]
                    action_payload = {
                        "action_code": action_ref.strip(),
                        "nc_reference": selected_nc.get("reference_code") if selected_nc else None,
                        "nonconformity_id": selected_nc.get("id") if selected_nc else None,
                        "title": action_title.strip(),
                        "description": action_desc.strip() or None,
                        "owner": action_owner.strip() or None,
                        "status": action_status,
                        "priority": action_priority,
                        "due_date": action_due.isoformat()
                    }
                    created_action = sb.table("nexus_corrective_actions").insert(action_payload).select("id").execute().data or []
                    if selected_nc and created_action:
                        sb.table("nexus_action_links").insert({
                            "action_id": created_action[0]["id"],
                            "nonconformity_id": selected_nc["id"]
                        }).execute()
                    audit_public_event(sb,"ACTIONS","CREATE",action_ref,action_title)
                    st.success("Action corrective créée."); st.rerun()
                except Exception as exc:
                    st.error("Création impossible : vérifie l'unicité de la référence et les règles SQL. Détail : "+str(exc))
        if action_rows:
            st.markdown("#### Registre des actions")
            adf = pd.DataFrame(action_rows)
            st.dataframe(adf.drop(columns=["id"],errors="ignore"),use_container_width=True,hide_index=True)
            st.download_button("Exporter les actions en CSV",adf.to_csv(index=False).encode("utf-8"),"nexus_actions_correctives.csv","text/csv")
            alabels = {f"{r['action_code']} — {r['title']}":r for r in action_rows}
            alabel = st.selectbox("Action à mettre à jour",list(alabels.keys()))
            ar = alabels[alabel]
            with st.form("nexus_action_update"):
                status_opts=["À faire","En cours","En attente","Terminée","Clôturée"]
                pri_opts=["Basse","Normale","Haute","Critique"]
                oldst=ar.get("status") if ar.get("status") in status_opts else "À faire"
                oldpri=ar.get("priority") if ar.get("priority") in pri_opts else "Normale"
                newst=st.selectbox("Nouveau statut",status_opts,index=status_opts.index(oldst))
                newpri=st.selectbox("Nouvelle priorité",pri_opts,index=pri_opts.index(oldpri))
                newowner=st.text_input("Responsable",value=ar.get("owner") or "")
                newdesc=st.text_area("Description / preuve",value=ar.get("description") or "")
                update_action=st.form_submit_button("Enregistrer l'action")
            if update_action:
                try:
                    sb.table("nexus_corrective_actions").update({
                        "status":newst,"priority":newpri,"owner":newowner.strip() or None,"description":newdesc.strip() or None
                    }).eq("id",ar["id"]).execute()
                    audit_public_event(sb,"ACTIONS","UPDATE",ar["action_code"],newst)
                    st.success("Action mise à jour."); st.rerun()
                except Exception as exc: st.error("Modification impossible : "+str(exc))
        st.markdown("#### Journal de traçabilité")
        if audit_rows:
            audit_df=pd.DataFrame(audit_rows)
            st.dataframe(audit_df.drop(columns=["id"],errors="ignore"),use_container_width=True,hide_index=True)
            st.download_button("Exporter le journal CSV",audit_df.to_csv(index=False).encode("utf-8"),"nexus_journal.csv","text/csv")
        else:
            st.info("Aucun événement disponible ou la table du journal n'est pas accessible.")

elif page == "ORION · Analyse":
    st.subheader("ORION · Analyse industrielle")
    st.caption("Indicateurs calculés à partir des données synthétiques PILOT, événements, écarts et registres publics.")
    sb = get_supabase_client()
    live_nc, live_jobs = [], []
    if sb is not None:
        try: live_nc = sb.table("nexus_nonconformities").select("*").execute().data or []
        except Exception: pass
        try: live_jobs = sb.table("capax_work_orders").select("*").execute().data or []
        except Exception: pass
    total_orders = len(filtered)
    late_orders = int(filtered["is_late"].sum()) if "is_late" in filtered else 0
    completion_rate = (int((filtered["status"].astype(str).str.lower()=="completed").sum())/total_orders*100) if total_orders else 0
    stop_minutes = float(duration_seconds(filtered_events.copy(),"started_at","ended_at").sum()/60) if not filtered_events.empty and {"started_at","ended_at"}.issubset(filtered_events.columns) else 0
    nc_open = sum(1 for r in live_nc if r.get("status") not in ["Résolue","Clôturée"])
    jobs_open = sum(1 for r in live_jobs if r.get("status") not in ["Terminée","Clôturée"])
    k1,k2,k3,k4 = st.columns(4)
    k1.metric("Ordres suivis",total_orders)
    k2.metric("Taux terminés",f"{completion_rate:.1f}%")
    k3.metric("Ordres en retard",late_orders)
    k4.metric("Arrêts tracés",f"{stop_minutes:.0f} min")
    k5,k6,k7=st.columns(3)
    k5.metric("NC publiques ouvertes",nc_open)
    k6.metric("Interventions CAPAX ouvertes",jobs_open)
    k7.metric("Écarts PILOT",len(filtered_deviations))
    st.markdown("#### Priorités de démonstration")
    findings=[]
    if late_orders: findings.append(f"{late_orders} ordre(s) sont signalés en retard selon les dates disponibles.")
    if stop_minutes: findings.append(f"{stop_minutes:.0f} minute(s) d'arrêt sont calculées à partir des événements horodatés.")
    if nc_open: findings.append(f"{nc_open} non-conformité(s) publique(s) restent non clôturées.")
    if jobs_open: findings.append(f"{jobs_open} intervention(s) CAPAX restent ouvertes.")
    if not findings: findings.append("Aucun signal prioritaire détecté dans le périmètre filtré, ou données insuffisantes.")
    for finding in findings: st.info(finding)
    st.markdown("#### Retards par atelier")
    if not filtered.empty and "workshop_label" in filtered:
        late_by=filtered.groupby("workshop_label",dropna=False).agg(ordres=("id","count"),retards=("is_late","sum")).reset_index()
        st.bar_chart(late_by.set_index("workshop_label")[["ordres","retards"]])
        st.dataframe(late_by,use_container_width=True,hide_index=True)
    else: st.info("Pas de données d'atelier disponibles pour cette période.")
    st.caption("ORION est un moteur descriptif : les signaux sont des règles simples, pas une prédiction ni une décision automatique. Données de démonstration uniquement.")

else:
    st.subheader("Explorateur de données")
    tables = [t for t in ["production_orders","planned_operations","operation_executions","time_records","quantity_records","production_events","deviation_records"] if t in TABLES]
    chosen = st.selectbox("Choisir une table",tables)
    df = load(chosen)
    st.caption(f"{len(df)} lignes · {len(df.columns)} colonnes")
    st.dataframe(df,use_container_width=True,hide_index=True)
    st.download_button("Télécharger en CSV",df.to_csv(index=False).encode("utf-8"),f"{chosen}.csv","text/csv")

st.divider()
st.caption("NEXUS Industrial · PILOT + Q-TRACE + CAPAX + ORION V1.8 · Données de démonstration synthétiques · Indicateurs calculés à partir des enregistrements disponibles")
