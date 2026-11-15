"""Exercise existing Data CI on recorded real agent outputs; no new inference.

The legacy API requires unchanged labels/references. Its stale-reference alarms
must not be confused with the review-aware release or a fair maintained baseline.
"""
from copy import deepcopy
import json
from unittest.mock import patch
from tools.validate_real_world_e2e import ART,BASE,dump
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import run_data_ci
from sourceroi.live import db

release=json.loads((ART/'release.json').read_text());before=read_config(BASE/'accepted');after=read_config(BASE/'candidate')

def recorded(cfg,tasks,chunks,excluded):
    if excluded:raise ValueError('This replay supports only the recorded full-corpus versions')
    result=deepcopy(release['baseline'] if cfg['_root']==before['_root'] else release['candidate'])
    if {r['id'] for r in result['tasks']}!={t['id'] for t in tasks}:raise ValueError('Replay task scope mismatch')
    return result

with patch('sourceroi.live.data_ci.evaluate_variant',side_effect=recorded),patch('sourceroi.live.provider._post',side_effect=RuntimeError('No model/network allowed during replay')):
    report=run_data_ci(before,after,max_tasks=6)
report['execution_origin']='Replay of exact recorded before/candidate outputs, zero new inference; latency/tokens inside variants are original recorded measurements'
report['recorded_release_id']=release['run_id'];report['label_scope']='Original benchmark values/references, because legacy Data CI requires unchanged labels; planned changes may generate stale-reference warnings'
db.finish(after,report['run_id'],report)
dump(ART/'legacy-data-ci-replay.json',report)
print(json.dumps({'verdict':report['verdict'],'new_failures':report['comparison']['lost_tasks'],'evidence_warnings':report['simple_check_comparison']['reference_coverage_failures'],'new_model_calls':0},indent=2))
