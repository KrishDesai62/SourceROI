from sourceroi.live.evidence_contract import precheck,has_fact_predicate


def chunk(id,text):return {'id':id,'document_id':id.split('#')[0],'source_id':'irs','title':'IRS notice','text':text}

def test_pdf_navigation_is_not_a_conflicting_policy_fact():
    context=[chunk('irs::a#0','[Page 1]\nSECTION 1.\nSee section 4 of Rev.\nMedical mileage is 21 cents per mile.'),
             chunk('irs::a#1','[Page 2]\nSECTION 3.\nSee section 5 of Rev.\nMedical mileage is 21 cents per mile.')]
    _,trace=precheck('Medical mileage?',context,{'sources':[{'id':'irs'}]}, {'version':1,'subject_aliases':[['medical']]})
    assert not trace['potential_conflicts'] and not trace['abstain']

def test_rate_assertions_still_trigger_numeric_conflict():
    context=[chunk('irs::a#0','Business mileage is 67 cents per mile.'),chunk('irs::b#0','Business mileage is 70 cents per mile.')]
    _,trace=precheck('Business mileage?',context,{'sources':[{'id':'irs'}]}, {'version':1,'subject_aliases':[['business']]})
    assert trace['potential_conflicts'] and trace['abstain']
    assert has_fact_predicate('The maximum is 70 cents per mile.')

def test_approved_update_preserves_declared_numeric_scoring(tmp_path):
    import json
    from pathlib import Path
    from examples.knowledge_change.demo import workspace,external_agent
    from sourceroi.live import assurance as a
    from sourceroi.live.config import read_config
    from sourceroi.live.data_ci import freeze
    source=workspace(tmp_path/'source');p=Path(source['_root'])/'benchmark.jsonl'
    tasks=[json.loads(x) for x in p.read_text().splitlines()];tasks[0]['scoring']='numeric';tasks[0]['answer_contract']={'version':1,'type':'numeric'}
    p.write_text('\n'.join(json.dumps(t) for t in tasks));freeze(source,tmp_path/'accepted')
    import shutil
    shutil.copytree(tmp_path/'source',tmp_path/'candidate');before=read_config(tmp_path/'accepted');after=read_config(tmp_path/'candidate')
    (tmp_path/'candidate/sources/general').mkdir(exist_ok=True)
    (tmp_path/'candidate/sources/policy/returns.json').write_text('{"returns_days":14}')
    spec=a.propose(before,after)
    approval=a.review(spec,reviewer='Codex unit fixture, not human approval',rationale='Test declared numeric semantics',expected_changes={'returns':'14'},protected_tasks=['warranty'],expected_evidence={'returns':[{'document_id':'policy::returns.json','quote':'14'}]})
    def callback(cfg,ts):
        result=external_agent(cfg,ts)
        for r in result['tasks']:
            if cfg['_root']==after['_root'] and r['id']=='returns':r['answer']='14.0';r['raw_answer']=14.0
        return result
    report=a.execute(before,after,spec,approval=approval,callback=callback)
    assert next(r for r in report['tasks'] if r['task_id']=='returns')['candidate_correct']
    assert report['verdict']=='ACCEPT' # Explicit legacy scope; not semantic approval.

def test_cross_reference_prefix_does_not_hide_substantive_rate_assertions():
    assert not has_fact_predicate('See section 4 of Rev.')
    assert not has_fact_predicate('See section 5 of')
    assert has_fact_predicate('See section 4: the rate is 67 cents per mile.')
    assert has_fact_predicate('See section 5: the rate is 70 cents per mile.')
