#!/usr/bin/env python3
"""Build NEXUS Industrial V1.1 hardened schema + six-week synthetic production fixture.
All people, sites, orders and results are fictional; this is a demo dataset only.
"""
from pathlib import Path
import sqlite3, uuid, json, datetime, zipfile, shutil, subprocess, sys
ROOT=Path(__file__).resolve().parent
SCHEMA_V1=ROOT/'nexus_industrial_schema_v1.sql'
SEED_V1=ROOT/'nexus_industrial_seed_v1.sql'
DB_V1=ROOT/'nexus_industrial_demo_v1.sqlite'
NS=uuid.UUID('68f41660-2342-43f5-9f30-ccb244a01ee2')
def uid(s): return str(uuid.uuid5(NS,'v11:'+s))
PATCH=r'''
-- NEXUS Industrial V1.1 hardening patch (SQLite)
-- Global role assignments: prevent duplicate global grants where scope_id is NULL.
CREATE UNIQUE INDEX IF NOT EXISTS ux_user_roles_global
ON user_roles(user_id, role_id) WHERE scope_type='global' AND scope_id IS NULL;
CREATE INDEX IF NOT EXISTS ix_orders_start_status ON production_orders(planned_start_at,status);
CREATE INDEX IF NOT EXISTS ix_planned_ops_order_status ON planned_operations(production_order_id,status,sequence_number);
CREATE INDEX IF NOT EXISTS ix_exec_started ON operation_executions(started_at,resource_id);
CREATE INDEX IF NOT EXISTS ix_time_records_category ON time_records(execution_id,time_category);
CREATE INDEX IF NOT EXISTS ix_events_started_type ON production_events(started_at,event_type,impact_category);
CREATE INDEX IF NOT EXISTS ix_deviations_status_severity ON deviation_records(status,severity,detected_at);
CREATE INDEX IF NOT EXISTS ix_inspections_order_status ON inspections(production_order_id,status,started_at);
CREATE INDEX IF NOT EXISTS ix_ncs_status_severity ON nonconformities(status,severity,detected_at);
CREATE INDEX IF NOT EXISTS ix_benefit_measurements_period ON benefit_measurements(evaluation_start,evaluation_end,case_id);

-- An inspection's plan, operation and order must refer to the same product version.
CREATE TRIGGER IF NOT EXISTS trg_inspection_product_version_insert
BEFORE INSERT ON inspections
WHEN NEW.production_order_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM production_orders po JOIN control_plans cp ON cp.id=NEW.control_plan_id
 WHERE po.id=NEW.production_order_id AND po.product_version_id<>cp.product_version_id
)
BEGIN SELECT RAISE(ABORT,'inspection control plan product version does not match production order'); END;
CREATE TRIGGER IF NOT EXISTS trg_inspection_product_version_update
BEFORE UPDATE OF control_plan_id,production_order_id ON inspections
WHEN NEW.production_order_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM production_orders po JOIN control_plans cp ON cp.id=NEW.control_plan_id
 WHERE po.id=NEW.production_order_id AND po.product_version_id<>cp.product_version_id
)
BEGIN SELECT RAISE(ABORT,'inspection control plan product version does not match production order'); END;

-- When both are provided, an inspection's operation must belong to the selected order.
CREATE TRIGGER IF NOT EXISTS trg_inspection_operation_order_insert
BEFORE INSERT ON inspections
WHEN NEW.planned_operation_id IS NOT NULL AND NEW.production_order_id IS NOT NULL
 AND NOT EXISTS (SELECT 1 FROM planned_operations p WHERE p.id=NEW.planned_operation_id AND p.production_order_id=NEW.production_order_id)
BEGIN SELECT RAISE(ABORT,'inspection operation does not belong to production order'); END;
CREATE TRIGGER IF NOT EXISTS trg_inspection_operation_order_update
BEFORE UPDATE OF planned_operation_id,production_order_id ON inspections
WHEN NEW.planned_operation_id IS NOT NULL AND NEW.production_order_id IS NOT NULL
 AND NOT EXISTS (SELECT 1 FROM planned_operations p WHERE p.id=NEW.planned_operation_id AND p.production_order_id=NEW.production_order_id)
BEGIN SELECT RAISE(ABORT,'inspection operation does not belong to production order'); END;

-- A nonconformity linked to an inspection result may not point to another order/operation.
CREATE TRIGGER IF NOT EXISTS trg_nc_inspection_link_insert
BEFORE INSERT ON nonconformities
WHEN NEW.inspection_result_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM inspection_results ir JOIN inspections i ON i.id=ir.inspection_id
 WHERE ir.id=NEW.inspection_result_id AND (
  (NEW.production_order_id IS NOT NULL AND i.production_order_id IS NOT NULL AND NEW.production_order_id<>i.production_order_id)
  OR (NEW.planned_operation_id IS NOT NULL AND i.planned_operation_id IS NOT NULL AND NEW.planned_operation_id<>i.planned_operation_id)
 )
)
BEGIN SELECT RAISE(ABORT,'nonconformity order/operation does not match inspection'); END;
CREATE TRIGGER IF NOT EXISTS trg_nc_inspection_link_update
BEFORE UPDATE OF inspection_result_id,production_order_id,planned_operation_id ON nonconformities
WHEN NEW.inspection_result_id IS NOT NULL AND EXISTS (
 SELECT 1 FROM inspection_results ir JOIN inspections i ON i.id=ir.inspection_id
 WHERE ir.id=NEW.inspection_result_id AND (
  (NEW.production_order_id IS NOT NULL AND i.production_order_id IS NOT NULL AND NEW.production_order_id<>i.production_order_id)
  OR (NEW.planned_operation_id IS NOT NULL AND i.planned_operation_id IS NOT NULL AND NEW.planned_operation_id<>i.planned_operation_id)
 )
)
BEGIN SELECT RAISE(ABORT,'nonconformity order/operation does not match inspection'); END;

INSERT INTO schema_migrations(version,name,checksum)
SELECT 2,'schema_v1_1_integrity_hardening','nexus-srp-v1.1-2026-10-11'
WHERE NOT EXISTS (SELECT 1 FROM schema_migrations WHERE version=2);
'''
# The V1 SQL ends with COMMIT; append patch after that transaction.
schema_v11=SCHEMA_V1.read_text(encoding='utf-8')+'\n'+PATCH
out_schema=ROOT/'nexus_industrial_schema_v1_1.sql'
out_schema.write_text(schema_v11,encoding='utf-8')
# Create a new DB by applying the V1.1 schema, then V1 seed data. Seed SQL has PRAGMA and transaction.
db=ROOT/'nexus_industrial_demo_v1_1.sqlite'
if db.exists(): db.unlink()
con=sqlite3.connect(db); con.execute('PRAGMA foreign_keys=ON')
con.executescript(schema_v11)
con.executescript(SEED_V1.read_text(encoding='utf-8'))
con.execute('PRAGMA foreign_keys=ON')
# Reference identifiers from existing fixture
get=lambda sql,args=(): con.execute(sql,args).fetchone()[0]
user=get("SELECT id FROM users WHERE username='demo.operator'")
version=get("SELECT id FROM product_versions WHERE version_code='V1' ORDER BY rowid LIMIT 1")
route=get("SELECT id FROM routes WHERE code='GAMME-DEMO'")
routeop=get("SELECT id FROM route_operations WHERE operation_code='OP-10'")
workstation=get("SELECT id FROM workstations WHERE code='POSTE-01'")
resource=get("SELECT id FROM resources WHERE code='MACHINE-01'")
unit_piece='piece'; unit_s='s'; unit_mm='mm'
control_plan=get("SELECT id FROM control_plans WHERE code='PC-DEMO'")
control_point=get("SELECT id FROM control_points WHERE code='CP-01'")
# Remove a stale V1 measurement from the baseline case? Keep it as initial seed evidence.
# Add a named improvement case and action for the six-week production period.
case_id=uid('case:setup-improvement')
action_id=uid('action:visual-setup-standard')
con.execute("INSERT INTO improvement_cases(id,case_number,title,description,origin_type,priority,status,owner_id,opened_at,target_date) VALUES(?,?,?,?,?,?,?,?,?,?)",
 (case_id,'AC-V11-001','Réduire le temps de préparation et les arrêts récurrents','Cas synthétique lié aux écarts de temps et aux arrêts de réglage observés sur six semaines.','production','high','closed',user,'2026-09-01T08:00:00Z','2026-09-25'))
con.execute("INSERT INTO action_items(id,case_id,title,description,action_type,owner_id,priority,status,start_date,due_date,completed_at,created_at,updated_at) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?)",
 (action_id,case_id,'Standardiser la préparation du poste','Fiche de réglage visuelle, rangement 5S et vérification avant lancement.','improvement',user,'high','completed','2026-09-21','2026-09-25','2026-09-25T16:00:00Z','2026-09-01T08:00:00Z','2026-09-25T16:00:00Z'))
# Six weeks: 30 weekdays from 2026-08-31 through 2026-10-09.
start=datetime.date(2026,8,31); end=datetime.date(2026,10,10)
days=[]; d=start
while d<end:
 if d.weekday()<5: days.append(d)
 d+=datetime.timedelta(days=1)
# Three-week baseline, then improvement period. Dates and results are entirely fabricated.
orders=[]; stats=[]
for i,day in enumerate(days,1):
 iso=day.isoformat(); dt=f'{iso}T08:00:00Z'; after=i>15
 oid=uid(f'order:{iso}'); pid=uid(f'planned:{iso}'); eid=uid(f'exec:{iso}')
 orderno=f'OF-SYN-{day.strftime("%y%m%d")}'
 qty=10 if i%7 not in (0,) else 12
 planned_setup=600; planned_run=qty*900
 planned_total=planned_setup+planned_run
 # Initial 3 weeks: longer setup and more downtime. Weeks 4-6: standard work reduces both.
 setup=480 if after else 720 + (i%3)*60
 run=qty*900 + (i%4)*120 + (0 if after else 240)
 downtime=300 + (i%3)*120 if after else 900 + (i%4)*180
 actual=setup+run+downtime
 delay=actual-planned_total
 # 2 NCs in baseline and 1 in improvement phase; nonconformities are independent events.
 nc_day=i in (5,12,20)
 scrap=1 if nc_day else (1 if i in (3,9,17) else 0)
 good=qty-scrap
 po_status='completed'
 con.execute("INSERT INTO production_orders(id,order_number,product_version_id,route_id,planned_quantity,unit_code,planned_start_at,planned_end_at,actual_start_at,actual_end_at,status,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?)",
  (oid,orderno,version,route,qty,unit_piece,dt,f'{iso}T13:00:00Z',dt,f'{iso}T{(8+actual//3600):02d}:{(actual%3600)//60:02d}:00Z',po_status,user))
 con.execute("INSERT INTO planned_operations(id,production_order_id,route_operation_id,sequence_number,workstation_id,planned_start_at,planned_end_at,planned_setup_seconds,planned_run_seconds,planned_quantity,status) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
  (pid,oid,routeop,10,workstation,dt,f'{iso}T13:00:00Z',planned_setup,planned_run,qty,'completed'))
 con.execute("INSERT INTO operation_executions(id,planned_operation_id,execution_number,resource_id,started_at,ended_at,execution_type,status,recorded_by) VALUES(?,?,?,?,?,?,?,?,?)",
  (eid,pid,1,resource,dt,f'{iso}T{(8+actual//3600):02d}:{(actual%3600)//60:02d}:00Z','initial','completed',user))
 # Time categories partition elapsed time; they sum exactly to actual elapsed seconds.
 for j,(cat,dur) in enumerate((('setup',setup),('run',run),('downtime',downtime)),1):
  if dur:
   con.execute("INSERT INTO time_records(id,execution_id,time_category,duration_seconds,started_at,ended_at,source_type,source_reference,recorded_by) VALUES(?,?,?,?,?,?,?,?,?)",
    (uid(f'time:{iso}:{cat}'),eid,cat,dur,None,None,'calculated',f'SYN:{orderno}:{cat}',user))
 con.execute("INSERT INTO quantity_records(id,execution_id,quantity_type,quantity,unit_code,recorded_at,recorded_by,source_reference) VALUES(?,?,?,?,?,?,?,?)",
  (uid(f'good:{iso}'),eid,'good',good,unit_piece,f'{iso}T15:00:00Z',user,f'SYN:{orderno}:good'))
 if scrap:
  con.execute("INSERT INTO quantity_records(id,execution_id,quantity_type,quantity,unit_code,recorded_at,recorded_by,source_reference) VALUES(?,?,?,?,?,?,?,?)",
   (uid(f'scrap:{iso}'),eid,'scrap',scrap,unit_piece,f'{iso}T15:00:00Z',user,f'SYN:{orderno}:scrap'))
 if downtime>0:
  # one stop event during the run; event duration equals the downtime bucket
  con.execute("INSERT INTO production_events(id,planned_operation_id,event_type,started_at,ended_at,reason_code,description,impact_category,source_reference,recorded_by) VALUES(?,?,?,?,?,?,?,?,?,?)",
   (uid(f'stop:{iso}'),pid,'stop',f'{iso}T10:00:00Z',f'{iso}T{10+downtime//3600:02d}:{(downtime%3600)//60:02d}:00Z','SETUP' if i%2 else 'MATERIAL','Arrêt synthétique : réglage ou attente matière.','time',f'SYN:{orderno}:stop',user))
 if delay>0:
  con.execute("INSERT INTO deviation_records(id,planned_operation_id,deviation_type,detected_at,reference_value,observed_value,deviation_value,unit_code,severity,status,calculation_version) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
   (uid(f'dev:{iso}'),pid,'time',f'{iso}T16:00:00Z',planned_total,actual,delay,unit_s,'high' if delay>900 else 'low','closed' if after else 'treated','delta-v1.1'))
 # Quality check every 2nd working day; NC days are out of tolerance.
 if i%2==0 or nc_day:
  insp=uid(f'insp:{iso}'); ir=uid(f'inspectresult:{iso}')
  measured=20.4 if nc_day else (19.9 if i%4==0 else 20.0)
  result='nonconforming' if nc_day else 'conforming'
  con.execute("INSERT INTO inspections(id,control_plan_id,planned_operation_id,production_order_id,inspector_id,inspection_type,started_at,completed_at,status) VALUES(?,?,?,?,?,?,?,?,?)",
   (insp,control_plan,pid,oid,user,'in_process',f'{iso}T15:10:00Z',f'{iso}T15:20:00Z','completed'))
  con.execute("INSERT INTO inspection_results(id,inspection_id,control_point_id,measured_value,result_status,comment,recorded_at,recorded_by) VALUES(?,?,?,?,?,?,?,?)",
   (ir,insp,control_point,measured,result,'Mesure synthétique; aucun produit réel.',f'{iso}T15:20:00Z',user))
  if nc_day:
   ncid=uid(f'nc:{iso}')
   con.execute("INSERT INTO nonconformities(id,reference_code,inspection_result_id,production_order_id,planned_operation_id,description,severity,detected_at,status,origin_type,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
    (ncid,f'NC-SYN-{day.strftime("%y%m%d")}',ir,oid,pid,'Cote hors tolérance dans le jeu de démonstration.', 'major' if i<16 else 'minor',f'{iso}T15:21:00Z','closed' if after else 'treatment','inspection',user))
   con.execute("INSERT INTO case_nonconformities(case_id,nonconformity_id) VALUES(?,?)",(case_id,ncid))
 con.execute("INSERT INTO case_deviations(case_id,deviation_id) SELECT ?,id FROM deviation_records WHERE planned_operation_id=? AND deviation_type='time'",(case_id,pid))
 orders.append((oid,pid,eid,orderno,qty,good,scrap,planned_total,actual,delay,after,nc_day))
 stats.append({'date':iso,'week':day.isocalendar().week,'order':orderno,'planned_qty':qty,'good_qty':good,'scrap_qty':scrap,'planned_seconds':planned_total,'actual_seconds':actual,'delay_seconds':delay,'downtime_seconds':downtime,'after_improvement':after,'nonconformity':nc_day})
# Measurable improvement: compare mean actual duration, mean stop duration and first-pass quality.
base=[x for x in stats if not x['after_improvement']]; post=[x for x in stats if x['after_improvement']]
base_avg=sum(x['actual_seconds'] for x in base)/len(base); post_avg=sum(x['actual_seconds'] for x in post)/len(post)
base_stop=sum(x['downtime_seconds'] for x in base)/len(base); post_stop=sum(x['downtime_seconds'] for x in post)/len(post)
base_yield=sum(x['good_qty'] for x in base)/sum(x['planned_qty'] for x in base); post_yield=sum(x['good_qty'] for x in post)/sum(x['planned_qty'] for x in post)
for m_id, ref_start,ref_end,eval_start,eval_end,baseval,obsval,unit,method in [
 (uid('benefit:duration'),'2026-08-31T00:00:00Z','2026-09-18T23:59:59Z','2026-09-21T00:00:00Z','2026-10-09T23:59:59Z',base_avg,post_avg,unit_s,'Moyenne des durées d exécution par OF'),
 (uid('benefit:downtime'),'2026-08-31T00:00:00Z','2026-09-18T23:59:59Z','2026-09-21T00:00:00Z','2026-10-09T23:59:59Z',base_stop,post_stop,unit_s,'Moyenne des durées d arrêt par OF')]:
 con.execute("INSERT INTO benefit_measurements(id,case_id,action_item_id,reference_start,reference_end,evaluation_start,evaluation_end,baseline_value,observed_value,difference_value,unit_code,measurement_method,data_source_reference,measured_at,validated_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
  (m_id,case_id,action_id,ref_start,ref_end,eval_start,eval_end,round(baseval,2),round(obsval,2),round(obsval-baseval,2),unit,method,'demo://synthetic-six-week-dataset','2026-10-10T12:00:00Z',user))
# Yield is expressed as percentage points, so add unit '%' and use a different measurement.
con.execute("INSERT OR IGNORE INTO units(code,name,dimension,symbol,is_base_unit,conversion_to_base) VALUES('pct','Pourcentage','ratio','%',1,1.0)")
con.execute("INSERT INTO benefit_measurements(id,case_id,action_item_id,reference_start,reference_end,evaluation_start,evaluation_end,baseline_value,observed_value,difference_value,unit_code,measurement_method,data_source_reference,measured_at,validated_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
 (uid('benefit:yield'),case_id,action_id,'2026-08-31T00:00:00Z','2026-09-18T23:59:59Z','2026-09-21T00:00:00Z','2026-10-09T23:59:59Z',round(base_yield*100,2),round(post_yield*100,2),round((post_yield-base_yield)*100,2),'pct','Quantité bonne / quantité planifiée × 100','demo://synthetic-six-week-dataset','2026-10-10T12:00:00Z',user))
# Record verification of effectiveness after the reference/evaluation windows.
con.execute("INSERT INTO effectiveness_reviews(id,action_item_id,reviewed_by,reference_period_start,reference_period_end,evaluation_period_start,evaluation_period_end,result,methodology,conclusion,reviewed_at) VALUES(?,?,?,?,?,?,?,?,?,?,?)",
 (uid('review:setup-improvement'),action_id,user,'2026-08-31T00:00:00Z','2026-09-18T23:59:59Z','2026-09-21T00:00:00Z','2026-10-09T23:59:59Z','effective','Comparaison des moyennes de 15 OF de référence et de 15 OF après action; résultats synthétiques.','Réduction de la durée moyenne et des arrêts dans le scénario; ne pas interpréter comme un résultat industriel réel.','2026-10-10T12:00:00Z'))
# A completed ORION run captures the 6-week period and the headline metrics.
run_id=uid('orion:weekly-analysis')
con.execute("INSERT INTO analysis_runs(id,analysis_type,scope_type,scope_reference,period_start,period_end,method_name,method_version,parameters_json,input_snapshot_reference,status,started_at,completed_at,created_by) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
 (run_id,'comparison','workstation','POSTE-01','2026-08-31T00:00:00Z','2026-10-09T23:59:59Z','before_after_summary','1.1.0',json.dumps({'baseline_orders':len(base),'evaluation_orders':len(post),'synthetic':True},separators=(',',':')),'demo://snapshot/nexus-v1.1-six-weeks','completed','2026-10-10T12:00:00Z','2026-10-10T12:01:00Z',user))
for code,val,unit,n in [('AVG_ACTUAL_SECONDS',post_avg,unit_s,len(post)),('AVG_DOWNTIME_SECONDS',post_stop,unit_s,len(post)),('GOOD_YIELD_PCT',post_yield*100,'pct',len(post)),('BASELINE_AVG_SECONDS',base_avg,unit_s,len(base))]:
 con.execute("INSERT INTO analysis_metrics(id,analysis_run_id,metric_code,metric_value,unit_code,sample_size,definition_version,quality_status,dimensions_json) VALUES(?,?,?,?,?,?,?,?,?)",
  (uid('metric:'+code),run_id,code,round(val,2),unit,n,'1.1.0','valid',json.dumps({'period':'post' if code!='BASELINE_AVG_SECONDS' else 'baseline','source':'synthetic'})))
# Register migration V1.1 is already in schema; annotate generated dataset in settings.
con.execute("INSERT OR IGNORE INTO app_settings(setting_key,setting_value,value_type,description) VALUES('dataset_period','2026-08-31/2026-10-09','string','Période de production entièrement synthétique sur six semaines')")
con.execute("INSERT OR IGNORE INTO app_settings(setting_key,setting_value,value_type,description) VALUES('dataset_notice','SYNTHETIC_NOT_REAL','string','Toutes les données de production, qualité, arrêts et gains sont fictives')")
con.commit()
# Enforce checks on the final fixture.
con.execute('PRAGMA foreign_keys=ON')
assert con.execute('PRAGMA foreign_key_check').fetchall()==[], con.execute('PRAGMA foreign_key_check').fetchall()
assert con.execute('PRAGMA integrity_check').fetchone()[0]=='ok'
assert con.execute("SELECT COUNT(*) FROM production_orders WHERE order_number LIKE 'OF-SYN-%'").fetchone()[0]==30
assert con.execute('SELECT COUNT(*) FROM nonconformities WHERE reference_code LIKE \'NC-SYN-%\'').fetchone()[0]==3
# Check the new global-role unique index.
row=con.execute("SELECT user_id,role_id FROM user_roles WHERE scope_type='global' AND scope_id IS NULL LIMIT 1").fetchone()
if row:
 try:
  con.execute("INSERT INTO user_roles(user_id,role_id,scope_type,scope_id) VALUES(?,?,'global',NULL)",row)
  raise AssertionError('global duplicate role was not blocked')
 except sqlite3.IntegrityError: pass
# Export seed SQL as all inserts from the final DB (schema remains separate); this makes a reproducible fixture.
# To avoid hand-maintaining inserts, dump every user table row in dependency-safe order.
tables=[r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")]
# Parent-first order is required because the seed enables foreign-key enforcement.
parents={t:set(r[2] for r in con.execute(f'PRAGMA foreign_key_list("{t}")') if r[2] != t) for t in tables}
seed_order=[]; remaining=set(tables)
while remaining:
 ready=sorted(t for t in remaining if parents[t].isdisjoint(remaining))
 if not ready: raise RuntimeError('Foreign-key cycle in seed export: '+repr(remaining))
 seed_order.extend(ready); remaining.difference_update(ready)
seed_lines=['-- NEXUS Industrial V1.1 — jeu 100 % synthétique; appliquer sur un schéma V1.1 vide.','PRAGMA foreign_keys=ON;','BEGIN IMMEDIATE;']
for t in seed_order:
 if t == 'schema_migrations': continue  # schema script already inserts migration versions 1 and 2
 rows=con.execute(f'SELECT * FROM "{t}"').fetchall(); cols=[x[1] for x in con.execute(f'PRAGMA table_info("{t}")')]
 for row in rows:
  vals=[]
  for v in row:
   if v is None: vals.append('NULL')
   elif isinstance(v,(int,float)): vals.append(repr(v))
   else: vals.append("'"+str(v).replace("'","''")+"'")
  seed_lines.append('INSERT INTO "'+t+'" ('+', '.join('"'+c+'"' for c in cols)+') VALUES ('+', '.join(vals)+');')
seed_lines+=['COMMIT;']
seed=ROOT/'nexus_industrial_seed_v1_1.sql'; seed.write_text('\n'.join(seed_lines)+'\n',encoding='utf-8')
con.close()
# Reports and metrics
con=sqlite3.connect(db); con.row_factory=sqlite3.Row
obj_counts={t:con.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables}
summary={
 'schema_version':con.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0],
 'tables':con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'").fetchone()[0],
 'indexes':con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='index' AND name NOT LIKE 'sqlite_%'").fetchone()[0],
 'triggers':con.execute("SELECT COUNT(*) FROM sqlite_master WHERE type='trigger'").fetchone()[0],
 'production_orders_total':con.execute('SELECT COUNT(*) FROM production_orders').fetchone()[0],
 'synthetic_orders':con.execute("SELECT COUNT(*) FROM production_orders WHERE order_number LIKE 'OF-SYN-%'").fetchone()[0],
 'executions_synthetic':con.execute("SELECT COUNT(*) FROM operation_executions e JOIN planned_operations p ON p.id=e.planned_operation_id JOIN production_orders po ON po.id=p.production_order_id WHERE po.order_number LIKE 'OF-SYN-%'").fetchone()[0],
 'stop_events_synthetic':con.execute("SELECT COUNT(*) FROM production_events WHERE source_reference LIKE 'SYN:OF-SYN-%:stop'").fetchone()[0],
 'deviations_synthetic':con.execute("SELECT COUNT(*) FROM deviation_records WHERE calculation_version='delta-v1.1'").fetchone()[0],
 'inspections_total':con.execute('SELECT COUNT(*) FROM inspections').fetchone()[0],
 'ncs_synthetic':con.execute("SELECT COUNT(*) FROM nonconformities WHERE reference_code LIKE 'NC-SYN-%'").fetchone()[0],
 'improvement_measurements':con.execute("SELECT COUNT(*) FROM benefit_measurements WHERE data_source_reference='demo://synthetic-six-week-dataset'").fetchone()[0],
 'foreign_key_violations':len(con.execute('PRAGMA foreign_key_check').fetchall()),
 'integrity_check':con.execute('PRAGMA integrity_check').fetchone()[0],
 'baseline_avg_seconds':round(base_avg,2),'post_avg_seconds':round(post_avg,2),'avg_time_change_pct':round((post_avg-base_avg)/base_avg*100,2),
 'baseline_avg_stop_seconds':round(base_stop,2),'post_avg_stop_seconds':round(post_stop,2),'avg_stop_change_pct':round((post_stop-base_stop)/base_stop*100,2),
 'baseline_good_yield_pct':round(base_yield*100,2),'post_good_yield_pct':round(post_yield*100,2),'yield_change_percentage_points':round((post_yield-base_yield)*100,2),
 'period_start':str(days[0]),'period_end':str(days[-1]),'baseline_orders':len(base),'evaluation_orders':len(post)
}
con.close()
report=ROOT/'nexus_v1_1_validation_report.txt'
report.write_text('NEXUS INDUSTRIAL V1.1 — RAPPORT DE VALIDATION\n'+'='*48+'\n\n'+json.dumps(summary,ensure_ascii=False,indent=2)+'\n\nRéserves : données entièrement fictives; résultats de comparaison illustratifs; activation PRAGMA foreign_keys requise pour chaque connexion SQLite. Le schéma n’est pas validé pour une exploitation industrielle critique sans revue métier, sécurité et qualification complémentaire.\n',encoding='utf-8')
# Daily-level CSV for analysis and charts, generated without third-party dependencies.
csv=ROOT/'nexus_six_week_production.csv'
with csv.open('w',encoding='utf-8',newline='') as f:
 import csv as csvmod
 w=csvmod.DictWriter(f,fieldnames=list(stats[0].keys()));w.writeheader();w.writerows(stats)
readme=ROOT/'README_NEXUS_V1_1.md'
readme.write_text(f'''# NEXUS Industrial V1.1 — schéma renforcé et données synthétiques\n\n## Contenu\n- `nexus_industrial_schema_v1_1.sql` : schéma V1 + patch V1.1, index, triggers et migration versionnée.\n- `nexus_industrial_seed_v1_1.sql` : export complet des données de démonstration. À appliquer sur une base vide après le schéma.\n- `nexus_industrial_demo_v1_1.sqlite` : base SQLite prête à explorer.\n- `nexus_six_week_production.csv` : un enregistrement par ordre synthétique, utile pour les graphiques.\n- `test_nexus_v1_1.py` : tests de régression.\n- `nexus_v1_1_validation_report.txt` : métriques et contrôles.\n\n## Période\nDu {days[0]} au {days[-1]} inclus, 30 jours ouvrés, 30 ordres synthétiques additionnels.\n\n## Durcissements V1.1\n- Index unique partiel pour empêcher les doubles affectations de rôle global lorsque `scope_id IS NULL`.\n- Index ciblés sur le suivi de production, les arrêts, les écarts, les contrôles qualité, les non-conformités et les mesures de bénéfice.\n- Triggers de cohérence entre ordre, opération, plan de contrôle et non-conformité.\n- Migration enregistrée en version 2.\n\n## Connexion SQLite\nActiver les clés étrangères dans chaque connexion : `PRAGMA foreign_keys = ON;` SQLite ne l'active pas globalement par défaut.\n\n## Données et interprétation\nTout est fictif et ne représente ni Framatome ni un site industriel réel. La phase après amélioration est scénarisée pour montrer comment comparer des périodes; elle ne prouve aucun gain réel.\n\n## Exécution des tests\n`python test_nexus_v1_1.py`\n\n## Recréation\n`python build_nexus_v11.py` régénère le schéma, la base, le seed, le CSV et le rapport à partir des fichiers V1 présents dans le même dossier.\n''',encoding='utf-8')
# Tests script
(ROOT/'test_nexus_v1_1.py').write_text(r'''#!/usr/bin/env python3
"""Regression/integrity tests for NEXUS Industrial V1.1 synthetic demo."""
import sqlite3, unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parent
DB=ROOT/'nexus_industrial_demo_v1_1.sqlite'
class V11Tests(unittest.TestCase):
 def setUp(self):
  self.db=sqlite3.connect(DB); self.db.execute('PRAGMA foreign_keys=ON'); self.db.row_factory=sqlite3.Row
 def tearDown(self): self.db.close()
 def test_schema_version(self): self.assertEqual(self.db.execute('SELECT MAX(version) FROM schema_migrations').fetchone()[0],2)
 def test_integrity_and_foreign_keys(self):
  self.assertEqual(self.db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
  self.assertEqual(self.db.execute('PRAGMA foreign_key_check').fetchall(),[])
 def test_six_week_orders(self): self.assertEqual(self.db.execute("SELECT COUNT(*) FROM production_orders WHERE order_number LIKE 'OF-SYN-%'").fetchone()[0],30)
 def test_workday_span(self):
  r=self.db.execute("SELECT MIN(planned_start_at),MAX(planned_start_at) FROM production_orders WHERE order_number LIKE 'OF-SYN-%'").fetchone()
  self.assertEqual(r[0],'2026-08-31T08:00:00Z'); self.assertEqual(r[1],'2026-10-09T08:00:00Z')
 def test_synthetic_stops_and_deviations_exist(self):
  self.assertEqual(self.db.execute("SELECT COUNT(*) FROM production_events WHERE source_reference LIKE 'SYN:OF-SYN-%:stop'").fetchone()[0],30)
  self.assertGreater(self.db.execute("SELECT COUNT(*) FROM deviation_records WHERE calculation_version='delta-v1.1'").fetchone()[0],0)
 def test_three_synthetic_ncs(self): self.assertEqual(self.db.execute("SELECT COUNT(*) FROM nonconformities WHERE reference_code LIKE 'NC-SYN-%'").fetchone()[0],3)
 def test_benefits_reconcile(self):
  rows=self.db.execute("SELECT baseline_value,observed_value,difference_value FROM benefit_measurements WHERE data_source_reference='demo://synthetic-six-week-dataset'").fetchall()
  self.assertEqual(len(rows),3)
  for r in rows:self.assertAlmostEqual(r['observed_value']-r['baseline_value'],r['difference_value'],places=5)
 def test_global_role_duplicate_rejected(self):
  row=self.db.execute("SELECT user_id,role_id FROM user_roles WHERE scope_type='global' AND scope_id IS NULL LIMIT 1").fetchone()
  with self.assertRaises(sqlite3.IntegrityError): self.db.execute("INSERT INTO user_roles(user_id,role_id,scope_type,scope_id) VALUES(?,?,'global',NULL)",tuple(row))
 def test_inspection_wrong_operation_order_rejected(self):
  # Build two valid orders and operations, then try to cross-link an inspection.
  order_ids=[r[0] for r in self.db.execute("SELECT id FROM production_orders WHERE order_number LIKE 'OF-SYN-%' LIMIT 2")]
  op_ids=[r[0] for r in self.db.execute('SELECT id FROM planned_operations WHERE production_order_id IN (?,?)',(order_ids[0],order_ids[1]))]
  if len(op_ids)<2:self.fail('fixture lacks two operations')
  plan=self.db.execute("SELECT id FROM control_plans WHERE code='PC-DEMO'").fetchone()[0]
  user=self.db.execute('SELECT id FROM users LIMIT 1').fetchone()[0]
  with self.assertRaises(sqlite3.IntegrityError):
   self.db.execute("INSERT INTO inspections(id,control_plan_id,planned_operation_id,production_order_id,inspector_id,inspection_type,started_at,status) VALUES('bad-cross-link',?,?,?,?,?,?,?)",(plan,op_ids[0],order_ids[1],user,'in_process','2026-10-10T08:00:00Z','planned'))
 def test_time_deviation_arithmetic(self):
  bad=self.db.execute("SELECT COUNT(*) FROM deviation_records WHERE calculation_version='delta-v1.1' AND abs(deviation_value-(observed_value-reference_value))>=0.000001").fetchone()[0]
  self.assertEqual(bad,0)
if __name__=='__main__': unittest.main(verbosity=2)
''',encoding='utf-8')
# Execute tests, capture results.
res=subprocess.run([sys.executable,str(ROOT/'test_nexus_v1_1.py')],capture_output=True,text=True)
(ROOT/'nexus_v1_1_test_output.txt').write_text(res.stdout+'\n'+res.stderr,encoding='utf-8')
if res.returncode:
 print(res.stdout);print(res.stderr);raise SystemExit(res.returncode)
# Final bundle
bundle=ROOT/'nexus_industrial_v1_1_full_pack.zip'
files=['nexus_industrial_schema_v1_1.sql','nexus_industrial_seed_v1_1.sql','nexus_industrial_demo_v1_1.sqlite','nexus_six_week_production.csv','test_nexus_v1_1.py','nexus_v1_1_validation_report.txt','nexus_v1_1_test_output.txt','README_NEXUS_V1_1.md','build_nexus_v11.py']
with zipfile.ZipFile(bundle,'w',zipfile.ZIP_DEFLATED) as z:
 for name in files:z.write(ROOT/name,arcname=name)
print(json.dumps(summary,ensure_ascii=False,indent=2));print('TESTS PASS');print(res.stdout);print('BUNDLE',bundle,'SIZE',bundle.stat().st_size)
