#!/usr/bin/env python3
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
