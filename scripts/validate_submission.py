"""Read-only final validator for database, business rules and submission artifacts."""
from __future__ import annotations
import argparse, csv, json, sqlite3, sys
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DB=ROOT/'data'/'warehouse_monitor.db'
DOC=ROOT/'docs'/'phase10'
PRODUCT_ZONE={'DAIRY':'COLD','PRODUCE':'COLD','PHARMA':'COLD','FROZEN_FOOD':'FREEZER','ELECTRONICS':'AMBIENT'}
EXPECTED={'warehouses':10,'zones':100,'sensors':500,'sensor_readings':1_000_000,'inventory_lots':10_000,'sensor_zone_assignments':500,'lot_zone_assignments':10_000}
checks=[]
def check(ok, name, detail=''):
    checks.append({'check':name,'passed':bool(ok),'detail':detail})
    print(('PASS' if ok else 'FAIL')+': '+name+(f' — {detail}' if detail else ''))
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--database',default=str(DB)); ap.add_argument('--profile',choices=['starter','full'],default='full'); ap.add_argument('--report',default='docs/phase10/comprehensive_validation.json'); a=ap.parse_args()
    db=Path(a.database)
    check(db.exists(),'Database file exists',str(db))
    if db.exists():
        con=sqlite3.connect(f'file:{db.resolve()}?mode=ro',uri=True); con.row_factory=sqlite3.Row
        try:
            integrity=con.execute('PRAGMA integrity_check').fetchone()[0]; check(integrity=='ok','SQLite integrity',integrity)
            fk=con.execute('PRAGMA foreign_key_check').fetchall(); check(not fk,'Foreign-key integrity',f'{len(fk)} violations')
            tables={r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'")}
            required={'warehouses','zones','sensors','sensor_zone_assignments','sensor_readings','door_events','storage_requirements','inventory_lots','lot_zone_assignments','alarms','alarm_lots','inspections','remediations','sensor_outages'}
            check(required.issubset(tables),'Required relational tables',f'{len(tables)} tables; missing {sorted(required-tables)}')
            counts={t:con.execute(f' SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in sorted(tables)}
            scale={'starter':{'warehouses':2,'zones':20,'sensors':100,'sensor_readings':20000,'inventory_lots':500},'full':EXPECTED}[a.profile]
            for table,n in scale.items(): check(counts.get(table)==n,f'{a.profile} profile count: {table}',f'expected {n:,}; found {counts.get(table)}')
            dup=con.execute('SELECT COUNT(*) FROM (SELECT sensor_id FROM sensor_zone_assignments WHERE effective_to IS NULL GROUP BY sensor_id HAVING COUNT(*)<>1)').fetchone()[0]
            active=con.execute("SELECT COUNT(*) FROM sensors WHERE lifecycle_state='ACTIVE'").fetchone()[0]
            assigned=con.execute("SELECT COUNT(DISTINCT a.sensor_id) FROM sensor_zone_assignments a JOIN sensors s ON s.sensor_id=a.sensor_id WHERE s.lifecycle_state='ACTIVE' AND a.effective_to IS NULL").fetchone()[0]
            check(dup==0 and active==assigned,'One current zone assignment per active sensor',f'active={active}; assigned={assigned}; duplicate groups={dup}')
            overlap=con.execute('''SELECT COUNT(*) FROM sensor_zone_assignments a JOIN sensor_zone_assignments b ON a.sensor_id=b.sensor_id AND a.assignment_id<b.assignment_id AND a.effective_from<COALESCE(b.effective_to,'9999-12-31 23:59:59') AND b.effective_from<COALESCE(a.effective_to,'9999-12-31 23:59:59')''').fetchone()[0]
            check(overlap==0,'Sensor assignment effective periods do not overlap',f'{overlap} overlapping pairs')
            bad=con.execute('''SELECT COUNT(*) FROM inventory_lots l JOIN lot_zone_assignments a ON a.lot_id=l.lot_id AND a.released_at IS NULL JOIN zones z ON z.zone_id=a.zone_id WHERE (l.product_type IN ('DAIRY','PRODUCE','PHARMA') AND z.zone_type<>'COLD') OR (l.product_type='FROZEN_FOOD' AND z.zone_type<>'FREEZER') OR (l.product_type='ELECTRONICS' AND z.zone_type<>'AMBIENT')''').fetchone()[0]
            check(bad==0,'Active inventory assignments use compatible zone types',f'{bad} incompatible assignments')
            orphan=con.execute('SELECT COUNT(*) FROM alarm_lots x LEFT JOIN alarms a ON a.alarm_id=x.alarm_id LEFT JOIN inventory_lots l ON l.lot_id=x.lot_id WHERE a.alarm_id IS NULL OR l.lot_id IS NULL').fetchone()[0]
            check(orphan==0,'Alarm-to-lot bridge references are valid',f'{orphan} orphan links')
            bad_lifecycle=con.execute("SELECT COUNT(*) FROM alarms WHERE (lifecycle_state IN ('RESOLVED','CLOSED') AND resolved_at IS NULL) OR (lifecycle_state IN ('OPEN','ACKNOWLEDGED','INVESTIGATING') AND resolved_at IS NOT NULL)").fetchone()[0]
            check(bad_lifecycle==0,'Alarm lifecycle timestamps match state',f'{bad_lifecycle} inconsistent alarms')
            bad_ins=con.execute("SELECT COUNT(*) FROM inspections WHERE (inspection_status='COMPLETED' AND completed_at IS NULL) OR (inspection_status<>'COMPLETED' AND completed_at IS NOT NULL)").fetchone()[0]
            check(bad_ins==0,'Inspection completion timestamps match status',f'{bad_ins} inconsistent inspections')
            bad_rem=con.execute("SELECT COUNT(*) FROM remediations WHERE (remediation_status='COMPLETED' AND (started_at IS NULL OR completed_at IS NULL)) OR (completed_at IS NOT NULL AND started_at IS NULL)").fetchone()[0]
            check(bad_rem==0,'Remediation lifecycle timestamps are coherent',f'{bad_rem} inconsistent remediations')
            check(counts.get('alarms',0)>0,'Risk detector output exists',f"{counts.get('alarms',0):,} alarms")
            check(counts.get('inspections',0)>0,'Inspection workflow records exist',f"{counts.get('inspections',0):,} inspections")
            check(counts.get('remediations',0)>0,'Remediation workflow records exist',f"{counts.get('remediations',0):,} remediations")
        finally: con.close()
    readme=(ROOT/'README.md').read_text(encoding='utf-8') if (ROOT/'README.md').exists() else ''
    for term,label in [('Project Overview','README overview'),('Features','README features'),('Installation','README installation'),('Usage','README usage'),('Architecture','README architecture')]: check(term.lower() in readme.lower(),label)
    for rel in ['docs/ARCHITECTURE_AND_DECISIONS.md','docs/DATA_GENERATION_AND_VALIDATION.md','docs/AI_USAGE_AND_PROMPT_HISTORY.md','scripts/run_profiles.py','scripts/validate_submission.py','scripts/restore_database.py']:
        check((ROOT/rel).is_file() and (ROOT/rel).stat().st_size>100,f'Submission artifact: {rel}')
    gt=DOC/'ground_truth.csv'; evidence_ok=False; rows=0
    if gt.exists():
        with gt.open(encoding='utf-8',newline='') as f:
            reader=csv.DictReader(f); fields=set(reader.fieldnames or []); rows_list=list(reader); rows=len(rows_list)
            evidence_ok={'evidence','label_status','source_tables','issue_type'}.issubset(fields) and all(r.get('evidence') and r.get('source_tables') for r in rows_list)
    check(evidence_ok,'Source-derived ground truth schema/evidence is valid',f'{rows} source-derived candidates; empty is permitted when no qualifying source anomaly exists')
    controlled=DOC/'controlled_sensor_ground_truth.csv'; fixture_ok=False; fixture_rows=0
    if controlled.exists():
        with controlled.open(encoding='utf-8',newline='') as f:
            cr=csv.DictReader(f); crows=list(cr); fixture_rows=len(crows)
            fixture_ok=fixture_rows>0 and all(r.get('evidence') and r.get('scenario_origin')=='CONTROLLED_SYNTHETIC' and r.get('label_status')=='CONFIRMED_SYNTHETIC' for r in crows)
    check(fixture_ok,'Controlled sensor ground truth contains evidence-backed synthetic labels',f'{fixture_rows} fixture rows')
    business=DOC/'controlled_business_edge_cases.csv'; business_ok=False; business_rows=0
    if business.exists():
        with business.open(encoding='utf-8',newline='') as f:
            br=csv.DictReader(f); brows=list(br); business_rows=len(brows)
            business_ok=business_rows>=2 and all(r.get('evidence') and r.get('scenario_origin')=='CONTROLLED_SYNTHETIC' for r in brows)
    check(business_ok,'Controlled business edge cases are explicitly synthetic and evidenced',f'{business_rows} fixture rows')
    repro=ROOT/'reports'/'profile_execution_reproducibility.json'
    repro_ok=False; repro_detail='report missing'
    if repro.exists():
        try:
            payload=json.loads(repro.read_text(encoding='utf-8'))
            profs=payload.get('profiles',{})
            repro_ok=all(name in profs and profs[name].get('two_run_reproducibility')=='PASS' for name in ('starter','full'))
            repro_detail='; '.join(f"{name}={profs.get(name,{}).get('two_run_reproducibility','MISSING')}" for name in ('starter','full'))
        except Exception as exc: repro_detail=str(exc)
    check(repro_ok,'Starter and full two-run reproducibility report',repro_detail)
    result={'profile':a.profile,'database':str(db),'checks':checks,'passed':sum(x['passed'] for x in checks),'failed':sum(not x['passed'] for x in checks),'success':all(x['passed'] for x in checks)}
    out=ROOT/a.report; out.parent.mkdir(parents=True,exist_ok=True); out.write_text(json.dumps(result,indent=2)+'\n',encoding='utf-8')
    print(f"\nVALIDATION: {result['passed']} passed; {result['failed']} failed. Report: {out.relative_to(ROOT)}")
    return 0 if result['success'] else 1
if __name__=='__main__': raise SystemExit(main())
