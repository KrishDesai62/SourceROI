"""Declared-intent proposal controls on old fixtures and separate authored development cases."""
import json
from pathlib import Path
import shutil
import sys
import tempfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from examples.knowledge_change.demo import workspace
from sourceroi.live import assurance as a
from sourceroi.live.config import read_config
from sourceroi.live.data_ci import freeze
from tools.validate_knowledge_assurance import scenario,SCENARIOS

DEVELOPMENT=[
 {'id':'enrollment_numeric_prefix','before':{'enrollment_age':21},'after':{'enrollment_age':25},'q':'What is enrollment age?','old':'21','new':'25','quote':'21','intent':'expected','expected_class':'PROPOSED_CHANGE'},
 {'id':'protected_months','before':{'coverage_months':12},'after':{'coverage_months':18},'q':'What is coverage months?','old':'12','new':None,'quote':'12','intent':'protected','expected_class':'PROTECTED_UNCHANGED'},
 {'id':'unchanged_code_numeric_substring','before':{'category_code':3,'shipping_days':30},'after':{'category_code':3,'shipping_days':14},'q':'What is category code?','old':'3','new':None,'quote':'"category_code": 3','intent':'expected','expected_class':'NO_SUPPORTED_CHANGE'},
 {'id':'same_number_unrelated_field','before':{'return_days':30,'shipping_days':30},'after':{'return_days':30,'shipping_days':14},'q':'What is return days?','old':'30','new':None,'quote':'"return_days": 30','intent':'expected','expected_class':'NO_SUPPORTED_CHANGE'},
 {'id':'jurisdiction_changes','before':{'enrollment_age':21},'after':{'enrollment_age':25},'q':'What is enrollment age?','old':'21','new':None,'quote':'21','intent':'expected','scope_change':True,'expected_class':'AMBIGUOUS_REVIEW'},
 {'id':'unknown_authority','before':{'enrollment_age':21},'after':{'enrollment_age':25},'q':'What is enrollment age?','old':'21','new':None,'quote':'21','intent':'expected','unknown_authority':True,'expected_class':'AMBIGUOUS_REVIEW'},
 {'id':'conflicting_facts','before':{'enrollment_age':21},'after':{'enrollment_age':25},'q':'What is enrollment age?','old':'21','new':None,'quote':'21','intent':'expected','conflict':True,'expected_class':'AMBIGUOUS_REVIEW'},
 {'id':'unknown_intent','before':{'enrollment_age':21},'after':{'enrollment_age':25},'q':'What is enrollment age?','old':'21','new':None,'quote':'21','intent':None,'expected_class':'AMBIGUOUS_REVIEW'}]


def main(out):
    out=Path(out)
    if out.exists():raise ValueError('Output exists')
    exposed=[];dev=[];unknown_intent_proposals=[]
    with tempfile.TemporaryDirectory(prefix='proposal-v2-') as tmp:
        root=Path(tmp)
        for name in SCENARIOS:
            before,after,_,approval,_=scenario(root/name,name)
            intent={'expected_tasks':list(approval['expected_changes']),'protected_tasks':approval['protected_tasks'],'declared_by':approval['reviewer'],'rationale':approval['rationale']} if approval else None
            spec=a.propose(before,after,intent=intent)
            unknown_intent_proposals.extend(a.propose(before,after)['evaluation_proposals'])
            exposed.append({'case':name,'proposals':spec['evaluation_proposals'],'approved_expected_changes':approval['expected_changes'] if approval else {},'authority':'Authored fixture owner declaration, not independent validation'})
        for case in DEVELOPMENT:
            source=root/case['id']/'source';workspace(source);shutil.rmtree(source/'sources/policy');(source/'sources/policy').mkdir()
            (source/'sources/policy/record.json').write_text(json.dumps(case['before']))
            task={'id':'t','question':case['q'],'expected':case['old'],'evidence':[{'document_id':'policy::record.json','quote':case['quote']}]}
            (source/'benchmark.jsonl').write_text(json.dumps(task)+'\n')
            if case.get('unknown_authority'):
                p=source/'project.json';obj=json.loads(p.read_text());obj['sources'][0].pop('authority',None);p.write_text(json.dumps(obj))
            frozen=root/case['id']/'accepted';freeze(read_config(source),frozen)
            candidate=root/case['id']/'candidate';shutil.copytree(source,candidate)
            (candidate/'sources/policy/record.json').write_text(json.dumps(case['after']))
            if case.get('scope_change'):
                p=candidate/'project.json';obj=json.loads(p.read_text());obj['sources'][0]['jurisdiction']='EU';obj['sources'][0]['scope']='EU enrollment';p.write_text(json.dumps(obj))
            if case.get('conflict'):(candidate/'sources/policy/other.json').write_text('{"enrollment_age":30}')
            intent={'expected_tasks':['t'] if case['intent']=='expected' else [],'protected_tasks':['t'] if case['intent']=='protected' else [],'declared_by':'authored development owner','rationale':'Pre-established fixture intent'} if case['intent'] else None
            spec=a.propose(read_config(frozen),read_config(candidate),intent=intent);proposal=spec['evaluation_proposals'][0] if spec['evaluation_proposals'] else {'classification':'NO_SUPPORTED_CHANGE','suggested_expected':None}
            dev.append({'case':case,'proposal':proposal,'matches_authored_class':proposal['classification']==case['expected_class'],'matches_authored_revision':proposal['suggested_expected']==case['new']})
    proposals=[p for c in exposed for p in c['proposals'] if p['classification']=='PROPOSED_CHANGE']
    correct=sum(p['suggested_expected']==c['approved_expected_changes'].get(p['task_id']) for c in exposed for p in c['proposals'] if p['classification']=='PROPOSED_CHANGE')
    result={'kind':'proposal_v2_validation','independent_labels':False,'exposed_cases':exposed,'separate_development_cases':dev,
        'summary':{'exposed_proposed_revisions':len(proposals),'correct_against_authored_intent':correct,'incorrect':len(proposals)-correct,'without_declared_intent_proposed':sum(p['classification']=='PROPOSED_CHANGE' for p in unknown_intent_proposals),'without_declared_intent_ambiguous':sum(p['classification']=='AMBIGUOUS_REVIEW' for p in unknown_intent_proposals),
            'ambiguous_items':sum(p['classification']=='AMBIGUOUS_REVIEW' for c in exposed for p in c['proposals']),
            'protected_incorrectly_proposed':sum(p['suggested_expected'] is not None for c in exposed for p in c['proposals'] if p['classification']=='PROTECTED_UNCHANGED'),
            'development_class_matches':sum(r['matches_authored_class'] for r in dev),'development_revision_matches':sum(r['matches_authored_revision'] for r in dev),'development_cases':len(dev)},
        'limitation':'Declared source-owner intent is additional required input before automatic prefilling. Unknown intent suppresses revisions, reducing automation; all cases authored/exposed, not independent held-out.'}
    out.write_text(json.dumps(result,indent=2)+'\n');print(json.dumps(result['summary'],indent=2));return result

if __name__=='__main__':main(sys.argv[1])
