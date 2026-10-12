import sqlite3
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from supabase import create_client
except ImportError:
    create_client = None

st.set_page_config(page_title="NEXUS Industrial | PILOT + Q-TRACE V1.6", page_icon="🏭", layout="wide")

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
st.caption("PILOT + Q-TRACE V1.6  •  PRODUCTION & QUALITY CONTROL")

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

pages = ["Vue générale", "PILOT · Production", "Retards & écarts", "Arrêts", "Q-TRACE · Qualité", "Données brutes"]
page = st.sidebar.radio("Navigation", pages)

if page == "Vue générale":
    st.subheader("Vue générale")
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
    st.caption("Le registre est consultable publiquement pour la démonstration. Les modifications sont réservées à l'administrateur.")

    supabase_client = None
    try:
        if create_client is not None and "supabase" in st.secrets:
            sb_url = st.secrets["supabase"]["url"]
            sb_key = st.secrets["supabase"]["service_role_key"]
            if sb_url and sb_key:
                supabase_client = create_client(sb_url, sb_key)
    except Exception:
        supabase_client = None

    live_rows = []
    if supabase_client is None:
        st.warning("Registre persistant non connecté. Configure les secrets Supabase et le mot de passe administrateur dans Streamlit Cloud.")
    else:
        try:
            live_result = supabase_client.table("nexus_nonconformities").select("*").order("created_at", desc=True).execute()
            live_rows = live_result.data or []
            if live_rows:
                live_df = pd.DataFrame(live_rows)
                st.dataframe(live_df.drop(columns=["id"], errors="ignore"), use_container_width=True, hide_index=True)
                st.download_button("Exporter le registre NEXUS en CSV", live_df.to_csv(index=False).encode("utf-8"), "nexus_nonconformites.csv", "text/csv")
            else:
                st.info("Aucune fiche NEXUS créée pour le moment.")
        except Exception:
            st.error("Impossible de lire le registre NEXUS. Vérifie que le script SQL a été exécuté et que les secrets sont corrects.")

    st.markdown("#### Espace administrateur")
    if "nexus_admin_authenticated" not in st.session_state:
        st.session_state.nexus_admin_authenticated = False
    if not st.session_state.nexus_admin_authenticated:
        with st.form("nexus_admin_login"):
            admin_password = st.text_input("Mot de passe administrateur", type="password")
            login_clicked = st.form_submit_button("Déverrouiller les modifications")
        if login_clicked:
            try:
                expected_password = st.secrets["admin"]["password"]
            except Exception:
                expected_password = None
            if expected_password and admin_password == expected_password:
                st.session_state.nexus_admin_authenticated = True
                st.rerun()
            else:
                st.error("Mot de passe incorrect ou secret admin non configuré.")
    else:
        if st.button("Verrouiller l'espace administrateur"):
            st.session_state.nexus_admin_authenticated = False
            st.rerun()

        st.markdown("##### Créer une non-conformité")
        if supabase_client is None:
            st.warning("Enregistrement désactivé tant que la connexion Supabase n'est pas configurée.")
        else:
            with st.form("create_nc_form", clear_on_submit=True):
                a, b = st.columns(2)
                nc_ref = a.text_input("Référence", placeholder="Ex. NC-2026-001", max_chars=40)
                nc_severity = b.selectbox("Gravité", ["Faible", "Moyenne", "Élevée", "Critique"])
                nc_desc = st.text_area("Description du défaut", placeholder="Décrire le défaut observé…", max_chars=2000)
                c, d = st.columns(2)
                nc_origin = c.text_input("Origine / atelier", placeholder="Ex. Atelier A, contrôle final")
                nc_owner = d.text_input("Responsable", placeholder="Nom ou fonction")
                e, f = st.columns(2)
                nc_due = e.date_input("Échéance de traitement")
                nc_status = f.selectbox("Statut initial", ["Ouverte", "En cours", "En attente"])
                nc_action = st.text_area("Action corrective prévue", placeholder="Action immédiate ou investigation à lancer…", max_chars=2000)
                submitted = st.form_submit_button("Enregistrer la non-conformité")
            if submitted:
                if not nc_ref.strip() or not nc_desc.strip():
                    st.error("La référence et la description sont obligatoires.")
                else:
                    payload = {"reference_code": nc_ref.strip(), "severity": nc_severity, "description": nc_desc.strip(), "origin": nc_origin.strip() or None, "owner": nc_owner.strip() or None, "due_date": nc_due.isoformat(), "status": nc_status, "corrective_action": nc_action.strip() or None}
                    try:
                        supabase_client.table("nexus_nonconformities").insert(payload).execute()
                        st.success("Non-conformité enregistrée dans Supabase.")
                        st.rerun()
                    except Exception:
                        st.error("Échec de l'enregistrement. Vérifie le SQL et les secrets Supabase; la référence doit être unique.")

            if live_rows:
                st.markdown("##### Mettre à jour le suivi")
                options = {f"{r['reference_code']} — {r['description'][:55]}": r["id"] for r in live_rows}
                selected_label = st.selectbox("Fiche à modifier", list(options.keys()))
                selected_row = next(r for r in live_rows if r["id"] == options[selected_label])
                with st.form("update_nc_form"):
                    u1, u2 = st.columns(2)
                    statuses = ["Ouverte", "En cours", "En attente", "Résolue", "Clôturée"]
                    current_status = selected_row.get("status") if selected_row.get("status") in statuses else "Ouverte"
                    upd_status = u1.selectbox("Nouveau statut", statuses, index=statuses.index(current_status))
                    upd_owner = u2.text_input("Responsable", value=selected_row.get("owner") or "")
                    upd_action = st.text_area("Action corrective / commentaire", value=selected_row.get("corrective_action") or "")
                    upd_done = st.form_submit_button("Enregistrer le suivi")
                if upd_done:
                    try:
                        update_payload = {"status": upd_status, "owner": upd_owner.strip() or None, "corrective_action": upd_action.strip() or None}
                        if upd_status in ["Résolue", "Clôturée"]:
                            from datetime import datetime, timezone
                            update_payload["closed_at"] = datetime.now(timezone.utc).isoformat()
                        else:
                            update_payload["closed_at"] = None
                        supabase_client.table("nexus_nonconformities").update(update_payload).eq("id", options[selected_label]).execute()
                        st.success("Suivi mis à jour.")
                        st.rerun()
                    except Exception:
                        st.error("La mise à jour a échoué. Vérifie la configuration Supabase.")

else:
    st.subheader("Explorateur de données")
    tables = [t for t in ["production_orders","planned_operations","operation_executions","time_records","quantity_records","production_events","deviation_records"] if t in TABLES]
    chosen = st.selectbox("Choisir une table",tables)
    df = load(chosen)
    st.caption(f"{len(df)} lignes · {len(df.columns)} colonnes")
    st.dataframe(df,use_container_width=True,hide_index=True)
    st.download_button("Télécharger en CSV",df.to_csv(index=False).encode("utf-8"),f"{chosen}.csv","text/csv")

st.divider()
st.caption("NEXUS Industrial · PILOT + Q-TRACE V1.6 · Données de démonstration synthétiques · Indicateurs calculés à partir des enregistrements disponibles")
