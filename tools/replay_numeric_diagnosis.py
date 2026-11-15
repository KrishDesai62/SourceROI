"""Post-experiment development diagnosis; never rescored as agent accuracy."""
from copy import deepcopy
import contextlib
import io
import json
from pathlib import Path
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from tools.validate_engineering_sprint import ART,BASE,dump
from sourceroi.live import db
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,_extract
from sourceroi.live.cli import main


def run():
    out=ART/'numeric-diagnosis.json'
    if out.exists():raise ValueError('Preserve previous diagnosis')
    cfg=read_config(BASE/'passage_coverage');entry=json.loads((ART/'passage_coverage.json').read_text())
    docs,chunks=scan_sources(cfg)
    spec={ident:{'operation':operation,'operands':[{'subject':'depreciation','period':p,'unit':'cents per mile'} for p in periods]}
        for ident,operation,periods in [('depreciation_2025','lookup',['2025']),('depreciation_difference','subtract',['2025','2023'])]}
    dump(ART/'post-experiment-calculation-declarations.json',{'phase':'Post-inference development declarations, not frozen primary comparison or independently authored labels','by_task':spec})
    dump(ART/'calculation-spec.json',spec)
    rid=db.begin(cfg,'diagnostic_replay',[])
    replay={'variants':[deepcopy(entry['variant'])],'manifest':{d['id']:d['fingerprint'] for d in docs},
        'origin':'Replay of real recorded responses for diagnosis only; usage fields inherited, not new usage','source_run_id':entry['run_id'],'new_generation_calls':0}
    db.finish(cfg,rid,replay)
    argv=['--project',cfg['_root'],'diagnose','--run-id',rid,'--calculation-spec',str(ART/'calculation-spec.json'),'--output',str(out)]
    stdout=io.StringIO()
    with patch('sourceroi.live.provider._post',side_effect=AssertionError('No new inference')),contextlib.redirect_stdout(stdout):exit_code=main(argv)
    assert exit_code==0
    diagnoses=json.loads(out.read_text())
    text=_extract(BASE/'passage_coverage/sources/current/CURRENT notice.pdf')
    for item in diagnoses['findings']:
        proposal=item.get('numeric_evidence_proposal',{})
        assert proposal.get('status')=='REVIEW' and proposal.get('semantic_approval') is None
        for value in proposal.get('inputs',[]):
            for hit in value['matches']:assert text[hit['quote_start']:hit['quote_end']]==hit['quote']
    dump(ART/'numeric-diagnosis-execution.json',{'argv':argv,'exit_code':exit_code,'stdout':stdout.getvalue(),'new_generation_calls':0,
        'phase':'post-experiment development replay','source_run_id':entry['run_id'],'replay_run_id':rid,'production_answers_changed':False,'independent_semantic_quality':None})
    print(json.dumps([(r['task_id'],r['numeric_evidence_proposal']['candidate_value'],r['numeric_evidence_proposal']['status']) for r in diagnoses['findings']]))


if __name__=='__main__':run()
