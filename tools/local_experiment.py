"""Audit owned experiments or demonstrate accounting with an explicit fake runtime.

Live mode intentionally unavailable until native server correlation is verified.
No model is loaded by any command in this tool.
"""
import argparse
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.experiment import Experiment,reconcile


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__);sub=p.add_subparsers(dest='action',required=True)
    a=sub.add_parser('audit');a.add_argument('--root',type=Path,required=True)
    f=sub.add_parser('fixture');f.add_argument('--output',type=Path,required=True);f.add_argument('--max-calls',type=int,default=2)
    f.add_argument('--failure',action='store_true')
    args=p.parse_args(argv)
    if args.action=='fixture':
        fixture=Path(__file__).resolve().parents[1]/'tests/fixtures/experiment_runtime.py'
        with Experiment(args.output,max_calls=args.max_calls,fixture_command=[sys.executable,str(fixture)]) as runner:
            def call(_):
                try:runner.post('http://127.0.0.1:1/v1/chat/completions',{'mode':'fail' if args.failure else 'ok'})
                except Exception:pass # Errors remain captured; reconciliation decides completeness.
            with ThreadPoolExecutor(max_workers=5) as pool:list(pool.map(call,range(5)))
        report=reconcile(args.output)
    else:report=reconcile(args.root)
    print(json.dumps(report,indent=2))
    return 0 if report['status']=='RECONCILED' else 5


if __name__=='__main__':raise SystemExit(main())
