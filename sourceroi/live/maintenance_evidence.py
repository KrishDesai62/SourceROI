"""Review-only evidence replacements and explicit-contract value proposals.

Lexical/numeric screens are necessary checks, never semantic-equivalence approval.
"""
from decimal import Decimal,InvalidOperation
import difflib
import re
from pathlib import Path
from .data_ci import digest
from .ingest import extract_document,sentence_passages,scan_sources
from .config import secure_path


def tokens(text):return set(re.findall(r'[a-z]+',text.casefold()))


def evidence_proposals(baseline,candidate,tasks):
    before_docs,_=scan_sources(baseline);after_docs,_=scan_sources(candidate)
    before={d['id']:d for d in before_docs};after={d['id']:d for d in after_docs}
    sources={s['id']:s for s in candidate['sources']};result=[]
    for task in tasks:
        refs=task.get('evidence',[])
        if not refs:continue
        replacements=[];bindings=[];valid=True;changed=False
        for ref in refs:
            did=ref['document_id']
            if did not in before or did not in after:valid=False;break
            oldtext=extract_document(secure_path(Path(baseline['_root']),before[did]['path']),baseline)
            newtext=extract_document(secure_path(Path(candidate['_root']),after[did]['path']),candidate)
            if not ref['quote'] or ref['quote'] not in oldtext:valid=False;break
            if ref['quote'] in newtext:
                quote=ref['quote'];start=newtext.index(quote)
            else:
                changed=True;hits=[]
                for span in sentence_passages(newtext,6000):
                    if span['fragmented']:continue
                    quote=span['text']
                    ratio=difflib.SequenceMatcher(None,' '.join(ref['quote'].split()).casefold(),' '.join(quote.split()).casefold()).ratio()
                    groups=task.get('evidence_contract',{}).get('subject_aliases',[])
                    if groups and any(not any(re.search(r'(?<!\w)'+re.escape(alias)+r'(?!\w)',quote,re.I) for alias in group) for group in groups):continue
                    anchors=tokens(task['question'])-{'what','how','the','is','are','a','in','for','of','many','days','long','current','annual','notice','rate','cents','per','mile','does','it'}
                    if not anchors & tokens(quote):continue
                    # Numeric preservation is necessary only. Other numbers/qualifiers
                    # may change meaning and still require explicit semantic review.
                    try:
                        expected=Decimal(task['expected'])
                        nums={Decimal(v.replace(',','')) for v in re.findall(r'[+-]?\d[\d,]*(?:\.\d+)?',quote)}
                        if expected not in nums:continue
                    except InvalidOperation:pass
                    from .evidence_contract import precheck
                    _,screen=precheck(task['question'],[{'id':'proposal','text':quote,'source_id':after[did]['source_id']}],candidate,None,task.get('scope'))
                    if not screen['eligible_ids'] or screen['unknown_applicability_ids']:continue
                    if not sources[after[did]['source_id']].get('authority'):continue
                    if ratio>=.45:hits.append((ratio,span))
                hits.sort(key=lambda x:-x[0])
                if not hits or len(hits)>1 and abs(hits[0][0]-hits[1][0])<.1:valid=False;break
                span=hits[0][1];quote=span['text'];start=span['start']
            replacements.append({'document_id':did,'quote':quote})
            bindings.append({'document_id':did,'before_version':before[did]['fingerprint'],'after_version':after[did]['fingerprint'],
                'old_quote':ref['quote'],'new_quote':quote,'start':start,'end':start+len(quote)})
        if valid and changed:
            body={'version':1,'task_id':task['id'],'kind':'EVIDENCE_ONLY_REVIEW','frozen_expected':task['expected'],
                'replacement_evidence':replacements,'provenance':bindings,'semantic_equivalence':'UNKNOWN',
                'requires_explicit_review':True,'expected_answer_unchanged':True,
                'qualification_changes':any(set(re.findall(r'\b(?:not|except|unless|only|if)\b',p['old_quote'],re.I))!=set(re.findall(r'\b(?:not|except|unless|only|if)\b',p['new_quote'],re.I)) for p in bindings)}
            result.append({**body,'id':digest(body)})
    return result


def value_proposal(task,baseline,candidate):
    contract=task.get('calculation_contract')
    if not contract:return None
    from .facts import calculate
    from .routing import restrict
    old=calculate(restrict(task['question'],scan_sources(baseline)[1],baseline)[0],contract,baseline,task.get('scope'))
    new=calculate(restrict(task['question'],scan_sources(candidate)[1],candidate)[0],contract,candidate,task.get('scope'))
    if old['binding_status']!='supported_grammar' or new['binding_status']!='supported_grammar' or old['value']==new['value']:return None
    facts=[f for operand in new['operands'] for f in operand['facts']]
    if not facts or any(not f.get('authority') for f in facts):return None
    return {'expected':new['value'],'before_source_value':old['value'],'document_id':facts[0]['document_id'],
        'before_quote':None,'after_quote':facts[0]['quote'],'source_facts':facts,'binding':new,
        'proposal_origin':'explicit_contract_source_binding','independent_of_expected_label':True,'semantic_approval':None}


def validate_update(spec,tid,decision):
    if not isinstance(decision,dict) or set(decision)!={'proposal_id','semantic_equivalence','rationale'} or decision['semantic_equivalence'] is not True or not isinstance(decision['rationale'],str) or not decision['rationale'].strip():raise ValueError('Evidence update requires explicit equivalence decision and rationale; unknown is not approval')
    proposal=next((p for p in spec.get('evidence_proposals',[]) if p['id']==decision['proposal_id'] and p['task_id']==tid),None)
    if not proposal or proposal['id']!=digest({k:v for k,v in proposal.items() if k!='id'}):raise ValueError('Evidence proposal identity/task mismatch')
    if proposal.get('qualification_changes'):raise ValueError('Changed qualifications cannot be approved as evidence-only equivalence; review semantics/intent separately')
    return proposal
