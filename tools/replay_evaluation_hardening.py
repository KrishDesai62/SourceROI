"""Offline authored regressions and read-only empirical replay. No inference.

Writes a fresh evidence directory; fixture reviews are internal test assertions,
not independent semantic approvals. Frozen inputs and historical outputs stay read-only.
"""
from copy import deepcopy
import argparse
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark,scan_sources
from sourceroi.live.data_ci import freeze,digest
from sourceroi.live import assurance as a
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.maintenance_evidence import value_proposal
from sourceroi.live.evaluation_inputs import maintained_tasks,packet,assert_parity
from tools.run_empirical_experiment import conventional

ROUTE={'version':1,'rules':[{'contains':'CURRENT','source_ids':['current']}]}

def write(path,value):
    with Path(path).open('x') as f:json.dump(value,f,indent=2);f.write('\n')


def proposal_cases(cases):
    results=[]
    with tempfile.TemporaryDirectory() as tmp:
        for case in cases:
            configs=[]
            contract={'version':1,'operation':'lookup','operands':[{'subject':'Orion','predicate':'revenue','period':'FY2025','unit':'USD'}]}
            for side in ('before','after'):
                root=Path(tmp)/case['id']/side;(root/'docs').mkdir(parents=True)
                (root/'docs'/('report.'+case['format'])).write_text(case[side])
                task={'id':'lookup','question':'What is Orion revenue for FY2025 in USD?','expected':'999999','scoring':'numeric','calculation_contract':contract}
                (root/'benchmark.jsonl').write_text(json.dumps(task)+'\n')
                cfg={'sources':[{'id':'data','path':'docs','authority':'Authored frozen fixture'}], 'settings':{'chunk_strategy':'sentences','table_evidence':True},'model':{'name':'not-called'}}
                (root/'project.json').write_text(json.dumps(cfg));configs.append(read_config(root))
            proposal=value_proposal(task,*configs)
            observed=proposal['expected'] if proposal else None
            results.append({'id':case['id'],'expected_suggestion':case['suggestion'],'observed_suggestion':observed,'matched':observed==case['suggestion'],'proposal':proposal,'gold_independence_probe':'Task expected deliberately set to 999999'})
    return {'label_authority':'Frozen Codex-authored development cases; not independently adjudicated','cases':results,
        'supported_cases':sum(c['suggestion'] is not None for c in cases),
        'supported_proposals':sum(r['observed_suggestion'] is not None and r['expected_suggestion'] is not None for r in results),
        'wrong_proposals':sum(r['observed_suggestion'] is not None and not r['matched'] for r in results),
        'negative_cases':sum(c['suggestion'] is None for c in cases),'negative_abstentions':sum(r['expected_suggestion'] is None and r['observed_suggestion'] is None for r in results)}


def replay(root,traces):
    before=read_config(root/'accepted');after=read_config(root/'candidate');tasks=load_benchmark(before)
    spec=a.propose(before,after,intent=json.loads((root/'intent.json').read_text()))
    decisions=json.loads((root/'review-decisions-DRAFT.json').read_text())
    proposal=next(p for p in spec['evidence_proposals'] if p['task_id']=='medical')
    review=a.review(spec,reviewer='Codex-operated deterministic replay fixture, NOT independent',
        rationale='Internal test assertion only; no real operator/customer/semantic approval',
        expected_changes=decisions['expected_changes'],expected_evidence=decisions['expected_evidence'],protected_tasks=decisions['protected_tasks'],
        evidence_updates={'medical':{'proposal_id':proposal['id'],'semantic_equivalence':True,'rationale':'Fixture assertion of unchanged value only; not an independent semantic judgment'}})
    def callback(cfg,selected):
        year=2024 if cfg['_root']==before['_root'] else 2025
        return {'tasks':[deepcopy(t['row']) for t in traces if t['phase']=='primary' and t['version']==year and t['task_id'] in {x['id'] for x in selected}], 'metrics':{}}
    with patch('sourceroi.live.engine.run_chat',side_effect=AssertionError('Offline replay cannot generate')):
        release=a.execute(before,after,spec,approval=review,callback=callback,persist=False,max_calls=20)
    revised=maintained_tasks(tasks,spec,review);left=packet(after,revised,spec=spec,approval=review)
    right=deepcopy(left);parity=assert_parity(left,right)
    primary=[t for t in traces if t['phase']=='primary' and t['version']==2025]
    contexts={t['task_id']:t['retrieved_evidence'] for t in primary}
    ordinary=conventional(after,revised,[deepcopy(t['row']) for t in primary],contexts)
    # Reproduce historical asymmetric medical evidence as an explicit mismatch.
    mismatch=deepcopy(right)
    mismatch['evidence_requirements']['medical']=deepcopy(next(t for t in tasks if t['id']=='medical')['evidence'])
    try:assert_parity(left,mismatch)
    except ValueError as e:parity['historical_asymmetry_rejected']=str(e)
    routing=[]
    class Captured(Exception):pass
    def stop(question,context,cfg):
        raise Captured({'question':question,'retrieved_ids':[c['id'] for c in context],'guard':cfg.get('_grounding_precheck')})
    for cfg,year in ((before,2024),(after,2025)):
        declared=deepcopy(cfg);declared['settings']['retrieval_contract']=deepcopy(ROUTE)
        # Counterfactual config identity is explicitly distinct from frozen originals.
        declared['_config_hash']=digest({k:v for k,v in declared.items() if not k.startswith('_')})
        _,chunks=scan_sources(declared)
        for task in tasks:
            with patch('sourceroi.live.engine.run_chat',side_effect=stop):
                try:
                    row=evaluate_variant(declared,[task],chunks,[])['tasks'][0]
                    result={'would_generate':False,'actual':row['actual'],'guard':row['grounding_precheck'],'retrieved_ids':row['retrieved_chunk_ids']}
                except Captured as e:result={'would_generate':True,**e.args[0]}
            old=next(t for t in traces if t['phase']=='data_ci' and t['version']==year and t['task_id']==task['id'])
            primary_row=next(t for t in traces if t['phase']=='primary' and t['version']==year and t['task_id']==task['id'])
            routing.append({'task_id':task['id'],'version':year,'supported':task['expected']!='INSUFFICIENT_EVIDENCE',
                'historical_data_ci_actual':old['actual_answer'],'historical_data_ci_origin':old['answer_origin'],
                'declared_config_sha256':declared['_config_hash'],
                'same_retrieval_as_historical_primary':result['retrieved_ids']==primary_row['row']['retrieved_chunk_ids'],**result})
    return spec,review,release,ordinary,parity,routing


def main():
    p=argparse.ArgumentParser();p.add_argument('--output',type=Path,required=True);args=p.parse_args()
    args.output.mkdir(parents=True,exist_ok=False)
    root=Path('workspace/execution-resolution/benchmark-v1')
    traces=json.loads(Path('docs/artifacts/full-empirical-benchmark/analysis/final/all-40-logical-task-traces.json').read_text())
    cases=json.loads(Path('docs/artifacts/evaluation-hardening/frozen-proposal-cases.json').read_text())['cases']
    write(args.output/'proposal-coverage.json',proposal_cases(cases))
    spec,review,release,ordinary,parity,routing=replay(root,traces)
    for name,value in [('new-offline-plan',spec),('fixture-review-NOT-independent',review),('replayed-release',release),('replayed-conventional',ordinary),('input-parity',parity),('routing-counterfactual',routing)]:write(args.output/(name+'.json'),value)
    write(args.output/'summary.json',{'new_model_generations':0,'historical_trace_count':len(traces),'sourceROI':release['verdict'],'conventional':ordinary['verdict'],
        'blocking_tasks':release.get('blocking_tasks'),'citation_status':release['check_statuses']['citation_integrity'],
        'semantic_status':release['check_statuses']['semantic_review'],
        'routing_2025_supported_software_abstentions':sum(r['supported'] and not r['would_generate'] for r in routing if r['version']==2025),
        'routing_matches_primary':sum(r['same_retrieval_as_historical_primary'] for r in routing),
        'caution':'Counterfactual routing checks eligibility, not future answer accuracy. Replayed real answers are unchanged. Review assertions are authored fixtures.'})
    print((args.output/'summary.json').read_text())

if __name__=='__main__':main()
