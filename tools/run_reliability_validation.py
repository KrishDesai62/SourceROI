"""Bounded approved-local-model pilot, untouched comparison and controlled Data CI."""
import argparse
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.ingest import load_benchmark,scan_sources
from sourceroi.live.engine import evaluate_variant
from sourceroi.live.validation import Budget
from sourceroi.live.provider import count_context_tokens
from sourceroi.live.reliability_study import run_reliability_study,export_reliability,choices
from sourceroi.live.data_ci import freeze,run_data_ci
from sourceroi.live.diagnosis import test_source_addition
from local_llm import MODEL,RUNTIME,checksum


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project',type=Path,default=Path('workspace/reliability-24'))
    p.add_argument('--output',type=Path,default=Path('docs/artifacts/reliability-local.json'))
    p.add_argument('--ci-root',type=Path,default=Path('workspace/reliability-ci-proof'))
    args=p.parse_args()
    if args.output.exists() or args.output.with_suffix('.plan.json').exists() or args.ci_root.exists():
        raise ValueError('Preserve existing reports and snapshots: choose new --output and --ci-root paths before any inference. Replays are not fresh held-out evidence.')
    manifest=json.loads(Path('workspace/.local-llm/manifest.json').read_text())
    if manifest['model']!=MODEL or checksum(manifest['model_file'])!=MODEL['sha256']:
        raise ValueError('Approved model manifest/checksum differs')
    cfg=read_config(args.project)
    if not cfg['model'].get('local_only') or cfg['model']['base_url']!='http://127.0.0.1:8788/v1':
        raise ValueError('Only the approved localhost model may be used')
    cfg['settings']['max_model_calls_per_run']=320;cfg['settings']['max_run_seconds']=900
    args.project.joinpath('project.json').write_text(json.dumps({k:v for k,v in cfg.items() if not k.startswith('_')},indent=2)+'\n')
    cfg=read_config(args.project)
    previous=json.loads(Path('docs/artifacts/local-llm-96.json').read_text())['frozen_policies']['sourceroi']
    tasks=load_benchmark(cfg);dev=[t for t in tasks if t['split']=='development'];held=[t for t in tasks if t['split']=='heldout']
    plan={'kind':'bounded_reliability_plan','model':MODEL,'runtime':RUNTIME,'external_api_spend_usd':0,
          'max_generation_calls':320,'max_seconds':900,'max_server_rss_bytes':8*1024**3,
          'model_slots':1,'context_size':4096,'cpu_threads':4,
          'resource_limit_note':'Process RSS checked before generation; this is not a complete OS/GPU memory accounting guarantee.',
          'benchmark_sha256':hashlib.sha256((args.project/cfg['benchmark']).read_bytes()).hexdigest(),
          'development_tasks':len(dev),'heldout_tasks':len(held),'candidate_policies':choices(cfg,previous),
          'comparison_max_calls':len(choices(cfg,previous))*len(dev)+8*len(held),
          'pilot_max_calls':4,'data_ci_max_calls':16,'source_addition_max_calls':2,
          'quality_rule':'No newly failed tasks; exact published gold answers. Human grounding review pending.',
          'code_sha256':{name:hashlib.sha256((Path('sourceroi/live')/name).read_bytes()).hexdigest() for name in
                         ('evidence.py','policies.py','engine.py','reliability_study.py','data_ci.py','diagnosis.py')}}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    planpath=args.output.with_suffix('.plan.json');planpath.write_text(json.dumps(plan,indent=2)+'\n')
    guard=Budget(cfg['settings']);peaks=[]
    server_prefix=manifest['server']+' --model '+manifest['model_file']+' '
    def resource_check():
        found=False
        for line in subprocess.check_output(['ps','-axo','rss=,command='],text=True).splitlines():
            fields=line.strip().split(None,1)
            if len(fields)==2 and fields[1].startswith(server_prefix):
                found=True;rss=int(fields[0])*1024;peaks.append(rss)
                if rss>plan['max_server_rss_bytes']:raise ValueError('Local server RSS cap exceeded')
        if not found:raise ValueError('Approved local server is not running')
    guard.resource_check=resource_check
    chunks=scan_sources(cfg)[1]
    pilot=[];pilot_start=time.perf_counter()
    for policy in ({'name':'original'},{'name':'evidence_aware','fallback':True,'max_context_tokens':2500}):
        local=deepcopy(cfg);local['_experiment_budget']=guard;local['settings']['retrieval_policy']=policy
        local['_context_token_counter']=lambda context,local=local:count_context_tokens(context,local)
        pilot.append(evaluate_variant(local,dev[:2],chunks,[]))
    forecast=(time.perf_counter()-pilot_start)/4*(plan['comparison_max_calls']+plan['data_ci_max_calls']+2)
    pilot_report={'actual_calls':guard.calls,'forecast_seconds':forecast,'variants':pilot}
    args.output.with_suffix('.pilot.json').write_text(json.dumps(pilot_report,indent=2)+'\n')
    print(json.dumps({'event':'pilot_complete','actual_calls':guard.calls,'forecast_seconds':round(forecast,1),'duration_limit':900}),flush=True)
    if forecast>guard.remaining_seconds():raise ValueError('Pilot forecast exceeds duration cap; full run not started')
    try:
        result=run_reliability_study(cfg,previous,budget=guard,notify=lambda event:print(json.dumps(event),flush=True))
    except Exception:
        from sourceroi.live import db
        rows=db.list_runs(cfg,1)
        if rows:
            saved=db.get(cfg,rows[0]['id'])
            args.output.with_suffix('.incomplete.json').write_text(json.dumps(saved,indent=2)+'\n')
        raise
    export_reliability(result,args.output)
    # Controlled old/exposed cases only, explicitly separate from fresh optimization evidence.
    ci_root=args.ci_root
    if ci_root.exists():raise ValueError('Data CI proof destination exists; preserve it and choose a new run directory')
    ci_root.mkdir()
    old=read_config('workspace/local-llm-96')
    frozen=ci_root/'baseline';freeze(old,frozen)
    candidate=ci_root/'candidate';shutil.copytree(frozen,candidate)
    old_tasks=load_benchmark(old)
    tids=['squad-57112686b654c5140001fbd3','squad-5725d34089a1e219009abf51','hotpot-5a8db19d5542994ba4e3dd00','hotpot-5ab859a955429934fafe6d7b']
    reference=next(t for t in old_tasks if t['id']==tids[0])['evidence'][0]['document_id']
    did={d['id']:d for d in scan_sources(read_config(candidate))[0]}
    (candidate/did[reference]['path']).unlink()
    ci=run_data_ci(read_config(frozen),read_config(candidate),task_ids=tids,max_tasks=4,repair=True,ablate=True,budget=guard)
    ci['experiment_kind']='controlled_published_document_removal_on_previously_exposed_cases'
    ci['fresh_heldout_evidence']=False
    args.output.with_suffix('.data-ci.json').write_text(json.dumps(ci,indent=2)+'\n')
    addition_task=[t for t in old_tasks if t['id']==tids[0]]
    addition=test_source_addition(old,addition_task,scan_sources(old)[1],['squad'],'squad',guard)
    args.output.with_suffix('.source-addition.json').write_text(json.dumps(addition,indent=2)+'\n')
    summary={'actual_total_generation_calls':guard.calls,'max_generation_calls':320,
             'elapsed_seconds':round(time.monotonic()-guard.started,2),'max_seconds':900,
             'maximum_observed_server_rss_bytes':max(peaks,default=None),'external_api_spend_usd':0,
             'fresh_study_verdict':result['verdict'],'data_ci_verdict':ci['verdict']}
    args.output.with_suffix('.session.json').write_text(json.dumps(summary,indent=2)+'\n')
    print(json.dumps({'event':'session_complete',**summary}),flush=True)


if __name__=='__main__':main()
