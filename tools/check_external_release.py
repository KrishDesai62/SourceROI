"""Run an existing RAG application's trusted local callback through strict release.

No application is supplied or simulated here. Import a developer-provided
MODULE:FUNCTION implementing the documented question/snapshot response contract.
"""
import argparse
import importlib
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.adapter import callback_for
from sourceroi.live.assurance import execute,markdown,EXIT_CODES,validate_spec,validate_review
from sourceroi.live.config import read_config


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    for name in ('baseline','candidate','spec','approval','output'):p.add_argument('--'+name,type=Path,required=True)
    p.add_argument('--authorize-execution',action='store_true',help='Explicit operator authorization to import/call trusted application code; does not authorize paid or native inference')
    p.add_argument('--adapter',required=True,help='Trusted developer MODULE:FUNCTION; may execute application code')
    p.add_argument('--review-packet',type=Path);p.add_argument('--reviewers',type=Path)
    p.add_argument('--max-calls',type=int,default=12);p.add_argument('--max-seconds',type=int,default=120)
    a=p.parse_args(argv)
    if not a.authorize_execution:p.error('Execution not authorized. Run offline preflight first; add --authorize-execution only after actual operator approval and generation accounting controls.')
    if a.output.exists() or a.output.with_suffix('.md').exists():p.error('Use a new output; evidence is immutable')
    try:
        before=read_config(a.baseline);after=read_config(a.candidate)
        spec=json.loads(a.spec.read_text());approval=json.loads(a.approval.read_text())
        validate_spec(spec);validate_review(spec,approval)
    except (ValueError,OSError,KeyError,TypeError):p.error('Invalid paths, configuration, specification or bound review. Check offline dry-run and review files before executing the application.')
    module,sep,name=a.adapter.partition(':')
    if not sep or not module or not name:p.error('Use MODULE:FUNCTION')
    try:function=getattr(importlib.import_module(module),name)
    except (ImportError,AttributeError):p.error('Adapter import failed. Make your trusted MODULE:FUNCTION importable; no adapter function was dispatched.')
    if not callable(function):p.error('Adapter must be callable')
    reviews=json.loads(a.review_packet.read_text())['items'] if a.review_packet else []
    report=execute(before,after,spec,
        approval=approval,callback=callback_for(function),max_calls=a.max_calls,max_seconds=a.max_seconds,
        policy='strict_grounded',semantic_reviews={r['sample_key']:r for r in reviews if r.get('status')=='complete'},reviewers=json.loads(a.reviewers.read_text()) if a.reviewers else [])
    a.output.parent.mkdir(parents=True,exist_ok=True)
    with a.output.open('x') as f:json.dump(report,f,indent=2);f.write('\n')
    a.output.with_suffix('.md').write_text(markdown(report))
    print(json.dumps({'verdict':report['verdict'],'exit_code':EXIT_CODES[report['verdict']],'report':str(a.output),'semantic_review':report['check_statuses'].get('semantic_review')},indent=2))
    return EXIT_CODES[report['verdict']]


if __name__=='__main__':raise SystemExit(main())
