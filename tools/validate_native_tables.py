"""Replay unchanged frozen development cases, with table support explicitly opt-in.

No native startup or inference. Historical source files, labels and reports are
read-only. All provider access is blocked during this deterministic comparison.
"""
from copy import deepcopy
from datetime import datetime,timezone
import json
import argparse
import hashlib
import tarfile
from pathlib import Path
import shutil
import sys
import time
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from sourceroi.live import facts
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources,extract_document
from sourceroi.live.experiment import audit_native_log
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'docs/artifacts/native-tables';BASE=ROOT/'workspace/native-tables'


def main():
    if BASE.exists() or (ART/'comparison.json').exists():raise ValueError('Immutable destination exists')
    frozen=json.loads((ROOT/'docs/artifacts/final-hardening/numerical-frozen-cases.json').read_text())
    (ART/'replay-plan.json').write_text(json.dumps({'frozen_at':datetime.now(timezone.utc).isoformat(),'labels':'Identical earlier Codex-authored development cases; not independent','cases':frozen,
        'settings':'Only opt-in table_evidence differs between before/after. No grammar or expected value is altered after replay.','native_gate':'PENDING; no native launch, at most 2/30 only if independently reconciliable'},indent=2)+'\n')
    BASE.mkdir();versions={}
    code=list((ROOT/'sourceroi/live').glob('*.py'))+[Path(__file__).resolve()]
    hashes={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in code}
    (ART/'code-freeze.json').write_text(json.dumps(hashes,indent=2)+'\n')
    with tarfile.open(ART/'as-run-code.tar.gz','x:gz') as archive:
        for p in code:archive.add(p,arcname=str(p.relative_to(ROOT)))
    with patch('sourceroi.live.provider._post',side_effect=AssertionError('No inference permitted')):
        for label,enabled in [('before',False),('after',True)]:
            records=[]
            for case in frozen['cases']:
                original=ROOT/'workspace/final-hardening-numerics'/case['id'];dest=BASE/label/case['id'];shutil.copytree(original,dest)
                public=json.loads((dest/'project.json').read_text());public['settings']['table_evidence']=enabled;(dest/'project.json').write_text(json.dumps(public,indent=2)+'\n')
                cfg=read_config(dest);scope=case.get('scope',{'jurisdiction':'US','policy_scope':'synthetic'});start=time.perf_counter();docs,chunks=scan_sources(cfg)
                try:
                    approval=facts.authorize(case['question'],scope,case['contract'],reviewer='Codex development author',rationale='Explicit existing frozen development operation; no human approval')
                    result=facts.answer(case['question'],chunks,case['contract'],approval,{**cfg,'_answer_contract':{'version':1,'type':case.get('answer_type','numeric')}},scope)
                    row={'id':case['id'],'kind':case['kind'],'actual':result['answer'],'expected':case['expected'],'passed':result['answer']==case['expected'],
                        'binding_status':result['calculation']['binding_status'],'calculation':result['calculation'],'citations':result['citations'],'elapsed_ms':1000*(time.perf_counter()-start)}
                    source_text={d['id']:extract_document(dest/d['path'],cfg) for d in docs}
                    for operand in result['calculation']['operands']:
                        for fact in operand['facts']:
                            text=source_text[fact['document_id']];assert text[fact['quote_start']:fact['quote_end']]==fact['quote']
                            for cell in fact.get('cells',[]):assert text[cell['start']:cell['end']]==cell['quote']
                except ValueError as exc:
                    if not case.get('expect_validation_error'):raise
                    row={'id':case['id'],'kind':case['kind'],'passed':True,'validation_error':str(exc)}
                records.append(row)
            supported=[r for r in records if r['kind']=='supported_numeric'];safety=[r for r in records if r['kind']=='safety']
            versions[label]={'records':records,'supported_correct':sum(r['passed'] for r in supported),'supported_n':len(supported),
                'supported_false_abstentions':sum(r['actual']=='INSUFFICIENT_EVIDENCE' for r in supported),'safety_pass':sum(r['passed'] for r in safety),'safety_n':len(safety),
                'unsupported_rejected':sum(r['kind']=='unsupported_contract' and r['passed'] for r in records)}
    native={}
    for label,filename,count in [('irs','irs-e2e/model-server.log',11),('engineering','engineering-sprint/local-server.log',11),('grounded','grounded-reasoning/local-server.log',11)]:
        native[label]=audit_native_log((ROOT/'workspace'/filename).read_text(),count)
    result={'versions':versions,'new_live_requests':0,'new_real_generations':0,'external_spend_usd':0,'independent_semantic_quality':None,
        'native_result':'PENDING','native_log_audits':native,'source_audit':'https://github.com/ggml-org/llama.cpp/blob/b12345/tools/server/server-http.cpp#L245',
        'native_blocker':'Pinned HTTP request/response logger registration is commented out. Native task/timing totals are insufficient for independent request correlation. No live smoke was authorized through the gate.'}
    (ART/'comparison.json').write_text(json.dumps(result,indent=2)+'\n')
    print(json.dumps({k:{x:v[x] for x in ['supported_correct','supported_n','supported_false_abstentions','safety_pass','safety_n','unsupported_rejected']} for k,v in versions.items()},indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,default=ART);p.add_argument('--workspace',type=Path,default=BASE);args=p.parse_args()
    ART=args.output.resolve();BASE=args.workspace.resolve();ART.mkdir(parents=True,exist_ok=True);main()
