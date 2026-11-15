"""Event logging for externally run, counterbalanced equal-authority human study."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.maintenance import record,summarize
p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
r=sub.add_parser('record')
for name in ('protocol-id','session-id','participant-id','origin','workflow','change-id','event'):r.add_argument('--'+name,required=True)
r.add_argument('--edit-count',type=int,default=0)
s=sub.add_parser('summarize')
for action in (r,s):action.add_argument('--log',type=Path,required=True)
a=p.parse_args();values=vars(a);action=values.pop('action');path=values.pop('log')
print(json.dumps(record(path,**values) if action=='record' else summarize(path),indent=2))
