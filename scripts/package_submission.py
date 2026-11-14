"""Create a clean source/evidence package without local databases or secrets."""
from __future__ import annotations
import zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
DIST=ROOT/'dist'; OUT=DIST/'warehouse-risk-monitor-submission.zip'
EXCLUDE_DIRS={'.git','.venv','venv','env','__pycache__','.pytest_cache','.mypy_cache','backups','node_modules'}
EXCLUDE_FILES={'.env','warehouse_monitor.db','warehouse_monitor_backup.db','warehouse_monitor-wal','warehouse_monitor-shm','warehouse_monitor_seed.sql'}

def include(path:Path)->bool:
    rel=path.relative_to(ROOT)
    if any(part in EXCLUDE_DIRS for part in rel.parts): return False
    if path.name in EXCLUDE_FILES or path.suffix in {'.pyc','.pyo'}: return False
    if rel.parts and rel.parts[0]=='data' and path.suffix in {'.db','.sqlite','.sqlite3'}: return False
    if rel.parts and rel.parts[0]=='reports':
        return path.name in {'profile_execution_reproducibility.json','test_execution.json'}
    if rel.parts and rel.parts[0]=='dist': return False
    return path.is_file()

def main():
    DIST.mkdir(exist_ok=True)
    if OUT.exists(): OUT.unlink()
    count=0
    with zipfile.ZipFile(OUT,'w',compression=zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for p in sorted(ROOT.rglob('*')):
            if include(p):
                z.write(p,Path('warehouse-risk-monitor')/p.relative_to(ROOT))
                count+=1
    print(f'PASS: packaged {count} files -> {OUT.relative_to(ROOT)} ({OUT.stat().st_size:,} bytes)')
    with zipfile.ZipFile(OUT) as z:
        bad=z.testzip()
        if bad: raise RuntimeError(f'Archive verification failed at {bad}')
    print('PASS: ZIP archive integrity verified; operational DB and virtualenv excluded.')
    return 0
if __name__=='__main__': raise SystemExit(main())
