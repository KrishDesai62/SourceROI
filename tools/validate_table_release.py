"""Synthetic table update/repair through existing strict assurance; no inference."""
import json
from pathlib import Path
import shutil
import sys
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'workspace/.deps'))
from sourceroi.live import assurance as a,facts
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze,run_data_ci
ROOT=Path(__file__).resolve().parents[1];ART=ROOT/'docs/artifacts/native-tables';BASE=ROOT/'workspace/native-table-release'


def dump(name,data):
    with (ART/name).open('x') as f:json.dump(data,f,indent=2);f.write('\n')


def main(output=None, workspace=None):
    global ART,BASE
    if workspace is not None:BASE=Path(workspace).resolve()
    if output is not None:
        ART=Path(output).resolve()
        if ART.exists():raise ValueError('Output exists; preserve historical evidence')
    if BASE.exists():raise ValueError('Immutable fixture exists')
    ART.mkdir(parents=True,exist_ok=True)
    source=BASE/'source';(source/'sources').mkdir(parents=True)
    def text(n):return f'company,attribute,period,value,unit\nOrion,revenue,FY2025,{n},USD\n'
    (source/'sources/report.csv').write_text(text(12))
    contract={'version':1,'operation':'lookup','operands':[{'subject':'Orion','predicate':'revenue','unit':'USD','period':'FY2025'}]}
    q='Orion revenue for FY2025?';scope={'jurisdiction':'US','policy_scope':'synthetic-table'}
    task={'id':'revenue','question':q,'expected':'12','scoring':'numeric','requires_grounding':True,'scope':scope,
        'answer_contract':{'version':1,'type':'numeric'},'calculation_contract':contract,
        'calculation_authorization':facts.authorize(q,scope,contract,reviewer='Codex synthetic task author',rationale='Explicit fixture lookup, not independent human approval'),
        'evidence':[{'document_id':'fixture::report.csv','quote':'Orion,revenue,FY2025,12,USD'}]}
    config={'id':'table-release-fixture','benchmark':'benchmark.jsonl','model':{'name':'not-called','local_only':True,'base_url':'http://127.0.0.1:1/v1'},
        'sources':[{'id':'fixture','path':'sources','authority':'Codex synthetic engineering fixture','jurisdiction':'US','policy_scope':'synthetic-table'}],
        'settings':{'chunk_strategy':'sentences','table_evidence':True,'answering_mode':'source_calculation','calculation_reviewers':['Codex synthetic task author'],
            'retrieval_policy':{'name':'predicate'},'release_policy':'strict_grounded','max_model_calls_per_run':8,'max_run_seconds':30}}
    (source/'project.json').write_text(json.dumps(config));(source/'benchmark.jsonl').write_text(json.dumps(task)+'\n')
    freeze(read_config(source),BASE/'accepted')
    for name,n in [('candidate',15),('repaired',14)]:
        shutil.copytree(source,BASE/name);(BASE/name/'sources/report.csv').write_text(text(n))
    before=read_config(BASE/'accepted');candidate=read_config(BASE/'candidate');repaired=read_config(BASE/'repaired')
    def plan(cfg):
        spec=a.propose(before,cfg,intent={'expected_tasks':['revenue'],'protected_tasks':[],
            'declared_by':'Codex synthetic fixture author','rationale':'Authored intended update to 14; no source owner or human validation'})
        approval=a.review(spec,reviewer='Codex synthetic fixture author',rationale='Explicit authored target 14; not independent review',
            expected_changes={'revenue':'14'},expected_evidence={'revenue':[{'document_id':'fixture::report.csv','quote':'Orion,revenue,FY2025,14,USD'}]})
        return spec,approval
    spec,approval=plan(candidate);repair_spec,repair_review=plan(repaired)
    with patch('sourceroi.live.provider._post',side_effect=AssertionError('No model request in deterministic validation')):
        release=a.execute(before,repaired,repair_spec,approval=repair_review,max_calls=2,max_seconds=30,policy='strict_grounded')
        ci=run_data_ci(before,candidate,max_tasks=1)
        repair=a.verify_repair(before,candidate,spec,repaired,repair_spec,approval=approval,repair_approval=repair_review,max_calls=4,max_seconds=30)
    assert release['verdict']=='REVIEW' and release['check_statuses']['numeric_evidence']=='PASS'
    assert ci['verdict']=='blocked' and repair['before']['verdict']=='BLOCK' and repair['after']['verdict']=='REVIEW'
    assert (BASE/'candidate/sources/report.csv').read_text()==text(15)
    dump('table-release.json',release);dump('table-data-ci.json',ci);dump('table-isolated-repair.json',repair)
    dump('table-workflow-summary.json',{'kind':'explicit_synthetic_engineering_validation','strict_release':release['verdict'],
        'exact_answer':release['check_statuses']['exact_answer'],'numeric_evidence':release['check_statuses']['numeric_evidence'],
        'semantic_review':release['check_statuses']['semantic_review'],'data_ci':ci['verdict'],'repair_before':repair['before']['verdict'],
        'repair_after':repair['after']['verdict'],'repair_overall':repair['verdict'],'candidate_unchanged':True,'actual_model_calls':0,'independent_semantic_quality':None,
        'interpretation':'Repair resolves frozen numerical expectations but independent review remains required; no strict ACCEPT or automatic repair is claimed.'})
    print(json.dumps({'release':release['verdict'],'ci':ci['verdict'],'repair':repair['verdict'],'after':repair['after']['verdict'],'new_model_calls':0}))


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output',type=Path)
    parser.add_argument('--workspace',type=Path)
    args=parser.parse_args();main(args.output,args.workspace)
