"""Restore a new local SQLite database from the compressed SQL seed export."""
from __future__ import annotations
import argparse,gzip,sqlite3
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--source',default='exports/warehouse_monitor_seed.sql.gz')
 ap.add_argument('--destination',default='data/warehouse_monitor.db')
 ap.add_argument('--overwrite',action='store_true')
 args=ap.parse_args(); source=ROOT/args.source; dest=ROOT/args.destination
 if not source.is_file(): raise FileNotFoundError(source)
 if dest.exists() and not args.overwrite: raise FileExistsError(f'{dest} exists; choose another destination or pass --overwrite after backing it up')
 dest.parent.mkdir(parents=True,exist_ok=True)
 if dest.exists(): dest.unlink()
 conn=sqlite3.connect(dest)
 try:
  # One executescript call is substantially faster than issuing hundreds of
  # thousands of individual INSERT statements from a large SQLite dump.
  with gzip.open(source,'rt',encoding='utf-8') as stream:
   conn.executescript(stream.read())
  integrity=conn.execute('PRAGMA integrity_check').fetchone()[0]
  fk=conn.execute('PRAGMA foreign_key_check').fetchall()
  if integrity!='ok' or fk: raise RuntimeError(f'Restored database failed checks: integrity={integrity}; fk={len(fk)}')
  print(f'PASS: restored {dest}; integrity={integrity}; FK violations={len(fk)}')
 except Exception:
  conn.close()
  if dest.exists(): dest.unlink()
  raise
 finally:
  try: conn.close()
  except Exception: pass
 return 0
if __name__=='__main__': raise SystemExit(main())
