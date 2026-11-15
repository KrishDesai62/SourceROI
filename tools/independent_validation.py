"""External annotation handoff and immutable split audit, not an independent reviewer.

External operators supply documents/labels, verify reviewer identity, keep the
final set hidden from implementation/tuning, then freeze before agent execution.
"""
import argparse
from datetime import datetime,timezone,date
import hashlib
import json
from pathlib import Path
import re

TOPICS=['legitimate_policy_change','effective_date','jurisdiction','contradictory_documents','paraphrased_evidence',
        'interacting_changes','protected_behaviors','missing_evidence','outdated_evidence','new_dependency']


def digest(x):return hashlib.sha256(json.dumps(x,sort_keys=True).encode()).hexdigest()

def template():
    return {'version':1,'status':'awaiting_external_annotation','implementation_authors':['Codex'],
        'reviewers':[],'development':[],'final':[],
        'required_topics':TOPICS,'instructions':'External source owners supply independently pre-established labels and evidence. Do not use evaluated-model answers as labels. Keep final documents/labels hidden from tuning; use disjoint document families.',
        'case_schema':{'id':'','document_group':'','topics':[],'before_documents':[{'id':'','text':''}],
            'after_documents':[{'id':'','text':'','authority':'','jurisdiction':'','effective_from':'','effective_to':''}],'approved_updates':[],'protected_behaviors':[],'scope':{'jurisdiction':'','as_of':'','policy_scope':''},'question':'','expected_before':'','expected_after':'',
            'release_outcome':'ACCEPT|BLOCK|REVIEW','label_basis':'source_owner|preexisting_external',
            'reviewer':'','review_status':'complete','label_established_at':'','outputs_seen_by_labeler':False,'source_citations':[{'version':'after','document_id':'','quote':''}]}}


def freeze(protocol,destination):
    destination=Path(destination)
    if destination.exists():raise ValueError('Frozen protocol destination exists')
    if protocol.get('version')!=1:raise ValueError('Unsupported protocol')
    people=protocol.get('reviewers',[])
    reviewers={p['id'] for p in people if p.get('independent_of_implementation') is True and p.get('operator_verified') is True}
    authors={x.lower() for x in protocol.get('implementation_authors',[])}|{'codex','chatgpt','evaluated model'}
    if not reviewers or any(r.lower() in authors for r in reviewers):raise ValueError('Independent externally verified reviewers required')
    groups={};documents={};seen_ids=set();tags={};normalized={};shingles={}
    for split in ('development','final'):
        cases=protocol.get(split)
        if not isinstance(cases,list) or not cases:raise ValueError('Nonempty development and final annotations required')
        groups[split]=set();documents[split]=set();normalized[split]=set();shingles[split]=[];tags[split]=set()
        for case in cases:
            if case.get('id') in seen_ids:raise ValueError('Duplicate case identity')
            seen_ids.add(case.get('id'))
            if case.get('reviewer') not in reviewers or case.get('review_status')!='complete' or case.get('label_basis') not in ('source_owner','preexisting_external'):
                raise ValueError('Labels must be externally established and approved')
            if any(not isinstance(case.get(k),str) or not case[k].strip() for k in ('id','document_group','question','expected_before','expected_after')):raise ValueError('Incomplete annotation')
            if not isinstance(case.get('approved_updates',[]),list) or not isinstance(case.get('protected_behaviors',[]),list) or not isinstance(case.get('scope',{}),dict):raise ValueError('Invalid update/protected/scope annotation')
            if any(not isinstance(v,str) for v in case.get('protected_behaviors',[])):raise ValueError('Protected behaviors need explicit IDs/descriptions')
            if set(case.get('scope',{}))-{'jurisdiction','as_of','policy_scope'} or any(not isinstance(v,str) for v in case.get('scope',{}).values()):raise ValueError('Invalid annotated scope')
            if not isinstance(case.get('before_documents'),list) or not isinstance(case.get('after_documents'),list):raise ValueError('Before/after documents must be lists')
            if case.get('scope',{}).get('as_of'):
                try:date.fromisoformat(case['scope']['as_of'])
                except (ValueError,TypeError):raise ValueError('Invalid annotation as_of date')
            for document in case.get('before_documents',[])+case.get('after_documents',[]):
                for key in ('effective_from','effective_to'):
                    if document.get(key):
                        try:date.fromisoformat(document[key])
                        except (ValueError,TypeError):raise ValueError('Invalid source effective date')
            if case.get('release_outcome') not in ('ACCEPT','BLOCK','REVIEW'):raise ValueError('Invalid outcome')
            try:established=datetime.fromisoformat(case.get('label_established_at','').replace('Z','+00:00'))
            except (ValueError,TypeError):raise ValueError('Pre-established label timestamp required')
            if established.tzinfo is None or established>datetime.now(timezone.utc) or case.get('outputs_seen_by_labeler') is not False:raise ValueError('Labels must precede evaluation without model-output exposure')
            groups[split].add(case['document_group']);tags[split].update(case.get('topics',[]))
            docs={}
            for version in ('before','after'):
                records=case.get(version+'_documents')
                if not isinstance(records,list):raise ValueError('Missing source documents')
                for doc in records:
                    if not doc.get('id') or not isinstance(doc.get('text'),str) or not doc['text'].strip():raise ValueError('Missing source text')
                    docs[(version,doc['id'])]=doc['text'];documents[split].add(digest(doc['text']))
                    words=re.findall(r'[a-z0-9]+',doc['text'].lower());normalized[split].add(' '.join(words))
                    if len(words)>=5:shingles[split].append(set(tuple(words[i:i+5]) for i in range(len(words)-4)))
            refs=case.get('source_citations',[])
            if not refs:raise ValueError('Independent source citations required')
            for ref in refs:
                text=docs.get((ref.get('version'),ref.get('document_id')),'')
                if not isinstance(ref.get('quote'),str) or not ref['quote'].strip() or ref['quote'] not in text:raise ValueError('Annotation citation is not in supplied version')
            for update in case.get('approved_updates',[]):
                if not isinstance(update,dict) or update.get('approved_by') not in reviewers:raise ValueError('Factual update needs an externally authorized approver')
                ident=update.get('document_id')
                for version,key in (('before','before_quote'),('after','after_quote')):
                    quote=update.get(key)
                    if not isinstance(quote,str) or not quote.strip() or quote not in docs.get((version,ident),''):raise ValueError('Approved factual update citation does not match source version')
    if groups['development']&groups['final'] or documents['development']&documents['final'] or normalized['development']&normalized['final']:
        raise ValueError('Development/final document or family overlap')
    if any(len(a&b)/len(a|b)>=.9 for a in shingles['development'] for b in shingles['final']):raise ValueError('Near duplicate document overlap')
    if any(not set(TOPICS)<=tags[split] for split in ('development','final')):raise ValueError('Required challenge topics missing')
    artifact={'kind':'externally_annotated_validation_protocol','version':1,'frozen_at':datetime.now(timezone.utc).isoformat(),
        'protocol_sha256':digest(protocol),'protocol':protocol,'independence_status':'Operator-attested; tool cannot authenticate human independence or prove that final labels were never exposed',
        'audit':{'document_group_overlap':[],'exact_document_overlap':[],'near_duplicate_threshold':.9,'semantic_overlap':'not automatically ruled out'},
        'document_versions':{split:[{'case_id':c['id'],'versions':{v:{d['id']:digest(d['text']) for d in c[v+'_documents']} for v in ('before','after')}} for c in protocol[split]] for split in ('development','final')},
        'label_version':digest({split:[{k:v for k,v in c.items() if k not in ('before_documents','after_documents')} for c in protocol[split]] for split in ('development','final')}),
        'execution_state':'not_run','model_outputs':None}
    destination.parent.mkdir(parents=True,exist_ok=True);destination.write_text(json.dumps(artifact,indent=2)+'\n')
    return artifact

if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);s=p.add_subparsers(dest='command',required=True)
    t=s.add_parser('template');t.add_argument('--output',type=Path,required=True)
    f=s.add_parser('freeze');f.add_argument('--input',type=Path,required=True);f.add_argument('--output',type=Path,required=True)
    args=p.parse_args()
    if args.command=='template':
        if args.output.exists():raise SystemExit('Output exists')
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(template(),indent=2)+'\n');print('Pending external annotation; no independent labels created')
    else:
        result=freeze(json.loads(args.input.read_text()),args.output);print(json.dumps({'protocol_sha256':result['protocol_sha256'],'execution_state':result['execution_state']}))
