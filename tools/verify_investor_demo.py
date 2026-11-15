"""Verify existing authored demos from an extracted source distribution.

All outcomes are synthetic engineering evidence; no LLM, customer or human review.
"""
import argparse
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def verify(output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Choose a new output directory')
    output.mkdir(parents=True)
    commands=[]
    def call(args):
        p=subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,capture_output=True,text=True,timeout=90)
        commands.append({'args':list(map(str,args)),'exit_code':p.returncode,'stdout':p.stdout,'stderr':p.stderr})
        (output/'commands.json').write_text(json.dumps(commands,indent=2))
        assert p.returncode==0,commands[-1]
        return p.stdout
    replay=json.loads(call(['tools/investor_demo.py']))
    assert replay['mode']=='IMMUTABLE_SYNTHETIC_REPLAY' and replay['live_inference'] is False
    # Preserved deterministic legacy agent: source attribution/valuation, not LLM inference.
    result=json.loads(call(['-m','sourceroi','demo','--project',ROOT/'examples/finance','evaluate','--json']))
    assert result['metrics']['task_count']>0
    ablation=call(['-m','sourceroi','demo','--project',ROOT/'examples/finance','ablate'])
    optimization=call(['-m','sourceroi','demo','--project',ROOT/'examples/finance','optimize'])
    assert 'Highest impact documents:' in ablation and 'modeled' in optimization
    call(['tools/validate_table_release.py','--output',output/'table-evidence','--workspace',output/'table-workspace'])
    table=json.loads((output/'table-evidence/table-workflow-summary.json').read_text())
    call(['tools/accept_pilot_workflow.py','--output',output/'callback-workflow'])
    callback=json.loads((output/'callback-workflow/summary.json').read_text())
    release=json.loads((output/'callback-workflow/bad-release.json').read_text())
    assert release['tasks'] and any(t.get('candidate_causes') for t in release['tasks'])
    summary={'status':'VERIFIED_INTERNAL_SYNTHETIC_DEMONSTRATION','independent_adoption':False,
        'dataset_task_count':result['metrics']['task_count'],'dataset_passed':result['metrics']['passed'],
        'source_document_ablation_executed':True,'modeled_optimization_executed':True,
        'actual_economic_savings':None,'live_model_calls':0,'semantic_accuracy':None,
        'intent_impact_evaluation_maintenance':callback['status'],'data_ci':table['data_ci'],
        'diagnosis_recorded':True,'repair':table['repair_overall'],'strict_release':callback['strict_release'],
        'protected_regression':callback['protected_regression'],'longitudinal_history':'SQLite release records written',
        'limitations':'Exposed authored fixtures and legacy deterministic agent; not model efficacy, competitive superiority or independent approval'}
    (output/'summary.json').write_text(json.dumps(summary,indent=2))
    return summary

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',required=True,type=Path)
    print(json.dumps(verify(p.parse_args().output),indent=2))
