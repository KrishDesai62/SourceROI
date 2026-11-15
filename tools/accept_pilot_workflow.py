"""Fresh-distribution internal pilot acceptance; synthetic sources, zero inference.

Exercises existing public onboarding/CLI/callback/review/study contracts. Outputs
are engineering checks, never real owner, independent reviewer or customer data.
"""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[1]


def run(output):
    output=Path(output).resolve()
    if output.exists():raise ValueError('Choose a new output directory')
    output.mkdir(parents=True)
    commands=[]
    def invoke(args,expected=0):
        proc=subprocess.run([sys.executable,*map(str,args)],cwd=ROOT,
                            env={**os.environ,'PYTHONNOUSERSITE':'1'},capture_output=True,text=True,timeout=60)
        row={'argv':list(map(str,args)),'returncode':proc.returncode,'stdout':proc.stdout,'stderr':proc.stderr}
        commands.append(row)
        (output/'commands.json').write_text(json.dumps(commands,indent=2))
        assert proc.returncode==expected,row
        return proc.stdout
    bundle={'version':1,'owner':'INTERNAL SYNTHETIC FIXTURE; no real owner',
            'labels_established_at':'2020-01-01T00:00:00Z','labels_from_evaluated_model':False,
            'before_documents':[],'after_documents':[],'tasks':[]}
    for version,days in [('before',30),('after',14)]:
        for name,text in [('returns.txt',f'Return window is {days} days.'),('warranty.txt','Warranty is 365 days.')]:
            bundle[version+'_documents'].append({'source_id':'policy','name':name,'text':text,
                'metadata':{'authority':'Internal synthetic fixture','jurisdiction':'US','policy_scope':'pilot-fixture'}})
    for tid,question,name,old,new,intended in [('returns','What is the return window?','returns.txt',30,14,True),
                                              ('warranty','What is the warranty?','warranty.txt',365,365,False)]:
        bundle['tasks'].append({'id':tid,'question':question,'expected_before':str(old),'expected_after':str(new),
            'intended_change':intended,'scope':{'jurisdiction':'US','policy_scope':'pilot-fixture'},
            'evidence_before':[{'document_id':'policy::'+name,'quote':bundle['before_documents'][0 if intended else 1]['text']}],
            'evidence_after':[{'document_id':'policy::'+name,'quote':bundle['after_documents'][0 if intended else 1]['text']}]})
    bundle_path=output/'synthetic-owner-input.json';bundle_path.write_text(json.dumps(bundle))
    pilot=output/'onboarded'
    invoke(['tools/source_owner_onboarding.py','prepare','--input',bundle_path,'--output',pilot])
    accepted=pilot/'accepted';candidate=pilot/'candidate'
    spec=pilot/'change.json'
    invoke(['-m','sourceroi','--project',candidate,'change-plan','--baseline',accepted,'--intent',pilot/'intent.json','--output',spec])
    # The actual workflow must refuse the generated unreviewed DRAFT.
    invoke(['-m','sourceroi','--project',candidate,'change-review','--spec',spec,
            '--decisions',pilot/'review-decisions-DRAFT.json','--output',pilot/'must-not-exist.json'],expected=2)
    assert not (pilot/'must-not-exist.json').exists()
    decision=json.loads((pilot/'review-decisions-DRAFT.json').read_text())
    decision['rationale']='INTERNAL SYNTHETIC acceptance assertion only; no independent owner approval'
    decisions=pilot/'synthetic-decisions.json';decisions.write_text(json.dumps(decision))
    approval=pilot/'synthetic-approval.json'
    invoke(['-m','sourceroi','--project',candidate,'change-review','--spec',spec,'--decisions',decisions,'--output',approval])
    def release(target,plan,review,path,code):
        invoke(['tools/check_external_release.py','--authorize-execution','--baseline',accepted,'--candidate',target,'--spec',plan,
                '--approval',review,'--adapter','examples.connected_rag.synthetic_pilot_adapter:answer',
                '--max-calls','4','--max-seconds','30','--output',path],expected=code)
    result=pilot/'release.json';release(candidate,spec,approval,result,4)
    report=json.loads(result.read_text())
    assert report['verdict']=='REVIEW' and report['check_statuses']['semantic_review']=='REVIEW'
    pending=pilot/'pending-claims.json'
    invoke(['tools/release_review_packet.py','export','--report',result,'--baseline',accepted,'--candidate',candidate,'--output',pending])
    invoke(['tools/prepare_external_evaluation.py','build','--baseline',accepted,'--candidate',candidate,
            '--release',result,'--output',output/'handoff'])
    invoke(['tools/prepare_external_evaluation.py','verify','--root',output/'handoff'])
    bad=output/'bad-candidate';shutil.copytree(candidate,bad,ignore=shutil.ignore_patterns('.sourceroi'))
    (bad/'sources/policy/warranty.txt').write_text('Warranty is 100 days.')
    badspec=output/'bad-change.json'
    invoke(['-m','sourceroi','--project',bad,'change-plan','--baseline',accepted,'--intent',pilot/'intent.json','--output',badspec])
    badapproval=output/'bad-approval.json'
    invoke(['-m','sourceroi','--project',bad,'change-review','--spec',badspec,'--decisions',decisions,'--output',badapproval])
    badresult=output/'bad-release.json';release(bad,badspec,badapproval,badresult,3)
    blocked=json.loads(badresult.read_text());assert blocked['verdict']=='BLOCK'
    # No real participants: automation events exercise all three arms but yield no human savings.
    study=output/'automated-study.jsonl'
    for arm in ('maintained_full_suite','maintained_with_diff','sourceroi'):
        for event in ('start','complete'):
            invoke(['tools/maintenance_study.py','record','--log',study,'--protocol-id','internal-fixture',
                '--session-id',arm,'--participant-id','AUTOMATION-NOT-A-PERSON','--origin','automation',
                '--workflow',arm,'--change-id','synthetic-update','--event',event])
    summary=json.loads(invoke(['tools/maintenance_study.py','summarize','--log',study]))
    assert not summary['completed_declared_human_sessions'] and summary['excluded_automated_sessions']==3 and summary['time_savings'] is None
    result={'status':'VERIFIED_INTERNAL_INTEGRATION','independent_adoption':False,'source_owner':'synthetic',
            'strict_release':report['verdict'],'protected_regression':blocked['verdict'],'semantic_quality':None,
            'real_model_calls':0,'actual_human_sessions':0,'three_arm_automation_excluded':3,
            'source_roi_internal_changes_required':False,'adapter':'existing trusted callback_for bridge',
            'command_count':len(commands),'pending_review_items':len(json.loads(pending.read_text())['items'])}
    (output/'summary.json').write_text(json.dumps(result,indent=2))
    return result

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--output',type=Path,required=True)
    print(json.dumps(run(p.parse_args().output),indent=2))
