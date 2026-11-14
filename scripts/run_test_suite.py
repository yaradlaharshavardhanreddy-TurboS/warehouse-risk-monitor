"""Run pytest and persist its exact exit code and summary for audit evidence."""
import json,subprocess,sys
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
p=subprocess.run([sys.executable,'-m','pytest','-q'],cwd=ROOT,text=True,stdout=subprocess.PIPE,stderr=subprocess.STDOUT)
print(p.stdout)
report={'generated_at_utc':datetime.now(timezone.utc).isoformat(),'command':[sys.executable,'-m','pytest','-q'],'exit_code':p.returncode,'passed':p.returncode==0,'output':p.stdout}
out=ROOT/'reports'/'test_execution.json';out.parent.mkdir(exist_ok=True);out.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8')
raise SystemExit(p.returncode)
