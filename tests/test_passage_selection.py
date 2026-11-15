"""Generic development regressions; no IRS answer keys or external review claims."""
import hashlib
from pathlib import Path

import pytest
from sourceroi.live.ingest import sentence_passages, scan_sources
from sourceroi.live.policies import select_context, task_kind
from sourceroi.live.maintenance import record, summarize
from sourceroi.live.grounding import score_review


def config(tmp_path, text):
    (tmp_path/'sources').mkdir()
    (tmp_path/'sources'/'policy.txt').write_text(text)
    return {'_root':str(tmp_path), 'settings':{'chunk_strategy':'sentences', 'chunk_chars':1100,
        'max_chunks':3, 'retrieval_policy':{'name':'passage_coverage','k':3}},
        'sources':[{'id':'policy','path':'sources'}]}


def test_literal_offsets_stable_ids_and_qualifier(tmp_path):
    text='Rev. Proc. 2021-17 establishes the limit. The overseas allowance is 18.5 units. However, contractors are excluded. The domestic allowance is 12 units.'
    cfg=config(tmp_path,text);docs,chunks=scan_sources(cfg)
    assert any('Rev. Proc. 2021-17 establishes the limit.' in c['text'] for c in chunks)
    assert any('18.5 units. However, contractors are excluded.' in c['text'] for c in chunks)
    for c in chunks:
        assert c['text']==text[c['start']:c['end']]
        assert hashlib.sha256(c['text'].encode()).hexdigest()[:12] in c['id']
        assert c['document_fingerprint']==docs[0]['fingerprint']
    assert chunks==scan_sources(cfg)[1]
    cfg['settings'].pop('chunk_strategy')
    assert all('#chunk-p' not in c['id'] for c in scan_sources(cfg)[1])


def test_long_sentences_flag_fragment_and_preserve_nonspace():
    text='A '+('large qualification '*40)+'ends.'
    parts=sentence_passages(text,80)
    assert all(p['fragmented'] and len(p['text'])<=80 for p in parts)
    assert ''.join(p['text'].replace(' ','') for p in parts)==text.replace(' ','')


def test_multiple_predicates_without_gold_or_same_source_duplication(tmp_path):
    cfg=config(tmp_path,'The domestic allowance is 12 units. The overseas allowance is 18 units. The depreciation amount is 99 units. The domestic allowance is 12 units.')
    _,chunks=scan_sources(cfg)
    selected,trace=select_context('What is the overseas allowance minus the domestic allowance?',chunks,cfg)
    joined=' '.join(c['text'] for c in selected)
    assert '18 units' in joined and '12 units' in joined
    assert '99 units' not in joined
    assert len(selected)==2
    assert trace['operand_terms'] and trace['removed_exact_duplicates']
    assert task_kind('A minus B')=='comparison'
    assert score_review('question','6',selected,[c['id'] for c in selected],{})['groundedness'] is None


def test_competing_sources_not_deduplicated(tmp_path):
    cfg=config(tmp_path,'The retention limit is 12 days.')
    _,chunks=scan_sources(cfg)
    chunks.append({**chunks[0], 'id':'other::policy#chunk0', 'source_id':'other','text':'The retention limit is 16 days.'})
    cfg['sources'].append({'id':'other','path':'sources'})
    # Different numbers are not deduplicated. Selection itself isn't a conflict resolver.
    from sourceroi.live.evidence import select_passages
    _,trace=select_passages('retention limit',chunks,3)
    assert not trace['removed_exact_duplicates']


def test_third_study_arm_is_separate_and_automation_not_human(tmp_path):
    path=tmp_path/'study.jsonl'
    for event in ['start','complete']:
        record(path,protocol_id='protocol',session_id='B',participant_id='automation',
               origin='automation',workflow='maintained_with_diff',change_id='frozen',event=event)
    result=summarize(path)
    assert result['completed_declared_human_sessions']==[]
    assert result['excluded_automated_sessions']==1
    assert result['time_savings'] is None


def test_conflicting_predicate_preserved_even_at_target_one(tmp_path):
    from sourceroi.live.evidence import select_passages
    from sourceroi.live.evidence_contract import precheck
    cfg=config(tmp_path,'The retention limit is 12 days.')
    _,chunks=scan_sources(cfg)
    chunks.append({**chunks[0],'id':'other::policy#chunk0','source_id':'other','text':'The retention limit is 16 days.'})
    selected,trace=select_passages('What is the retention limit?',chunks,1)
    assert len(selected)==2 and trace['target_k_exceeded_for_conflict']
    assert precheck('retention',selected,cfg,{'version':1})[1]['abstain']


def test_scope_filtered_before_ranking_and_unknown_retained(tmp_path,monkeypatch):
    import sourceroi.live.engine as engine
    from sourceroi.live.evidence_contract import abstention
    cfg=config(tmp_path,'The retention limit is 12 days.')
    cfg['model']={'name':'unused'}
    cfg['sources'][0]['jurisdiction']='US'
    _,chunks=scan_sources(cfg)
    task={'id':'scope','question':'retention limit?', 'expected':'INSUFFICIENT_EVIDENCE',
          'scoring':'exact','category':'test','requires_grounding':True,'scope':{'jurisdiction':'CA'}}
    monkeypatch.setattr(engine,'run_chat',lambda *args:pytest.fail('Scope guard must avoid generation'))
    variant=engine.evaluate_variant(cfg,[task],chunks,[])
    row=variant['tasks'][0]
    assert row['correct'] and row['prompt_tokens']==0
    assert row['selection']['pre_ranking_scope']['excluded_inapplicable_ids']==[chunks[0]['id']]
    cfg['sources'][0].pop('jurisdiction')
    from sourceroi.live.evidence_contract import precheck
    eligible,trace=precheck('retention',chunks,cfg,None,{'jurisdiction':'CA'})
    assert eligible and trace['unknown_applicability_ids']


def test_numeric_proposal_preserves_both_inputs_and_never_approves(tmp_path):
    from sourceroi.live.evidence import numeric_proposal
    cfg=config(tmp_path,'The overseas allowance is 18.5 units for Q2, and 12.25 units for Q1.')
    cfg['sources'][0]['jurisdiction']='US';_,chunks=scan_sources(cfg)
    spec={'operation':'subtract','operands':[{'subject':'overseas allowance','unit':'units','period':p} for p in ['Q2','Q1']]}
    result=numeric_proposal(chunks,spec,cfg,{'jurisdiction':'US'})
    assert result['candidate_value']=='6.25'
    assert len(result['inputs'])==2 and all(i['matches'] for i in result['inputs'])
    assert result['status']=='REVIEW' and result['semantic_approval'] is None
    text=(tmp_path/'sources/policy.txt').read_text()
    for i in result['inputs']:
        for m in i['matches']:assert text[m['quote_start']:m['quote_end']]==m['quote']
    spec['operands'][0]['subject']='domestic allowance'
    assert numeric_proposal(chunks,spec,cfg,{'jurisdiction':'US'})['candidate_value'] is None


def test_numeric_proposal_rejects_conflict_negation_scope_and_unit_conversion(tmp_path):
    from sourceroi.live.evidence import numeric_proposal
    cfg=config(tmp_path,'The retention allowance is 18 units for Q1. The retention allowance is 20 units for Q1.')
    _,chunks=scan_sources(cfg)
    spec={'operation':'lookup','operands':[{'subject':'retention allowance','unit':'units','period':'Q1'}]}
    assert numeric_proposal(chunks,spec,cfg)['candidate_value'] is None
    assert numeric_proposal(chunks[:1],spec,cfg,{'jurisdiction':'US'})['reasons']==['unknown_applicability']
    denied={**chunks[0],'text':'The retention allowance is not 18 units for Q1.'}
    assert numeric_proposal([denied],spec,cfg)['candidate_value'] is None
    spec['operation']='subtract';spec['operands'].append({**spec['operands'][0],'unit':'dollars'})
    with pytest.raises(ValueError,match='units differ'):numeric_proposal(chunks,spec,cfg)


def test_context_budget_cannot_drop_conflicting_side(tmp_path):
    cfg=config(tmp_path,'The retention limit is 12 days. The retention limit is 16 days.')
    cfg['settings']['retrieval_policy']['k']=1
    cfg['settings']['max_context_chars']=35
    _,chunks=scan_sources(cfg)
    selected,trace=select_context('retention limit?',chunks,cfg)
    assert not selected and trace['budget_conflict_abstention']


def test_diagnosis_exposes_review_proposal_without_rewriting_answer(tmp_path):
    from sourceroi.live.diagnosis import diagnose
    cfg=config(tmp_path,'The overseas allowance is 18 units for Q2 and 12 units for Q1.')
    _,chunks=scan_sources(cfg)
    task={'id':'gap','question':'overseas allowance Q2 minus Q1?',
          'evidence':[{'document_id':chunks[0]['document_id'],'quote':'18 units for Q2'}]}
    row={'actual':'99','retrieved_chunk_ids':[c['id'] for c in chunks]}
    spec={'operation':'subtract','operands':[{'subject':'overseas allowance','unit':'units','period':p} for p in ['Q2','Q1']]}
    result=diagnose(task,row,chunks,cfg,calculation=spec)
    assert result['classification']=='generation_or_scoring_failure'
    assert result['numeric_evidence_proposal']['candidate_value']=='6'
    assert result['numeric_evidence_proposal']['status']=='REVIEW'
    assert row['actual']=='99'


def test_new_chunking_is_a_review_bound_configuration_change(tmp_path):
    from examples.knowledge_change.demo import workspace
    from sourceroi.live import assurance as a
    from sourceroi.live.data_ci import freeze,run_data_ci
    from sourceroi.live.config import read_config
    cfg=workspace(tmp_path/'source');freeze(cfg,tmp_path/'accepted')
    before=read_config(tmp_path/'accepted');spec=a.propose(before,cfg)
    cfg['settings']['chunk_strategy']='sentences'
    with pytest.raises(ValueError,match='settings differ'):run_data_ci(before,cfg)
    with pytest.raises(ValueError,match='Stale'):
        a.execute(before,cfg,spec,callback=lambda *args:pytest.fail('Stale config must not execute'))


def test_cli_exposes_numeric_proposal_from_persisted_run(tmp_path,capsys):
    import json
    from sourceroi.live import db
    from sourceroi.live.cli import main
    cfg=config(tmp_path,'The overseas allowance is 18 units for Q2 and 12 units for Q1.')
    cfg.update(id='test',model={'name':'unused','base_url':'http://127.0.0.1:9/v1','local_only':True},benchmark='benchmark.jsonl')
    task={'id':'gap','question':'overseas allowance Q2 minus Q1?','expected':'6','scoring':'numeric',
          'evidence':[{'document_id':'policy::policy.txt','quote':'18 units for Q2'}]}
    (tmp_path/'benchmark.jsonl').write_text(json.dumps(task)+'\n')
    (tmp_path/'project.json').write_text(json.dumps({k:v for k,v in cfg.items() if not k.startswith('_')}))
    docs,chunks=scan_sources(cfg)
    row={'id':'gap','actual':'99','correct':False,'retrieved_chunk_ids':[c['id'] for c in chunks]}
    rid=db.begin(cfg,'baseline',[]);db.finish(cfg,rid,{'variants':[{'tasks':[row]}],'manifest':{d['id']:d['fingerprint'] for d in docs}})
    spec={'gap':{'operation':'subtract','operands':[{'subject':'overseas allowance','unit':'units','period':p} for p in ['Q2','Q1']]}}
    path=tmp_path/'calculation.json';path.write_text(json.dumps(spec));output=tmp_path/'findings.json'
    assert main(['--project',str(tmp_path),'diagnose','--run-id',rid,'--calculation-spec',str(path),'--output',str(output)])==0
    proposal=json.loads(output.read_text())['findings'][0]['numeric_evidence_proposal']
    assert proposal['candidate_value']=='6' and proposal['semantic_approval'] is None
