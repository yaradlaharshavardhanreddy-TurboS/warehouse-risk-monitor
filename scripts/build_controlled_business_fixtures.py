"""Write explicitly synthetic negative fixtures without touching the source DB."""
import csv,json
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]; OUT=ROOT/'docs'/'phase10'; OUT.mkdir(parents=True,exist_ok=True)
rows=[
 {'scenario_id':'SYN-BIZ-001','issue_type':'INCOMPATIBLE_LOT_ZONE_ASSIGNMENT','entity_type':'INVENTORY_LOT','entity_id':'SYN-LOT-000001','related_entity_id':'SYN-ZONE-FREEZER-001','label_status':'CONFIRMED_SYNTHETIC','scenario_origin':'CONTROLLED_SYNTHETIC','evidence':'Fixture assigns a DAIRY lot to a FREEZER zone; the documented mapping requires DAIRY -> COLD. This is an isolated negative test fixture, not an operational database row.'},
 {'scenario_id':'SYN-BIZ-002','issue_type':'ALARM_MISSING_AFFECTED_LOT_LINK','entity_type':'ALARM','entity_id':'SYN-ALARM-000001','related_entity_id':'SYN-LOT-000002','label_status':'CONFIRMED_SYNTHETIC','scenario_origin':'CONTROLLED_SYNTHETIC','evidence':'Fixture models an environmental alarm with an affected lot but deliberately omits the alarm_lots bridge record. This is an isolated negative test fixture, not an operational database row.'}
]
fields=list(rows[0])
for name in ['controlled_business_edge_cases.csv','controlled_business_edge_case_ground_truth.csv']:
 with (OUT/name).open('w',newline='',encoding='utf-8') as f:
  w=csv.DictWriter(f,fieldnames=fields);w.writeheader();w.writerows(rows)
manifest={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'scenario_origin':'CONTROLLED_SYNTHETIC','scenario_count':len(rows),'source_database_modified':False,'interpretation':'Synthetic negative fixtures for incompatible storage placement and missing alarm-to-lot bridge coverage. They are not source-database facts.'}
(OUT/'controlled_business_edge_case_manifest.json').write_text(json.dumps(manifest,indent=2)+'\n',encoding='utf-8')
print('Wrote two controlled business fixtures; operational database was not modified.')
