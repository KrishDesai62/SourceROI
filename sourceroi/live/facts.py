"""Narrow literal numerical fact binding and opt-in calculation.

No answer keys enter this module. Grammar support is explicit, not universal
semantic extraction. Operator-authorized formula use is distinct from independent
claim adjudication; neither provenance nor arithmetic authorizes strict release.
"""
from decimal import Decimal, localcontext
import hashlib
import json
import re

NUMBER = r'[+-]?(?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d+)?'
PERIOD = r'[A-Za-z0-9][A-Za-z0-9_-]{0,39}'


def digest(value):
    return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def literal(value):
    return r'\s+'.join(re.escape(w) for w in value.split())


def validate(contract):
    if contract is None:return
    if not isinstance(contract,dict) or set(contract)!={'version','operation','operands'} or contract.get('version')!=1:
        raise ValueError('Calculation contract must be version 1 with operation and operands')
    operation=contract['operation'];operands=contract['operands']
    count=1 if operation=='lookup' else 2
    if operation not in ('lookup','add','subtract','greater_than','less_than','equal') or not isinstance(operands,list) or len(operands)!=count:
        raise ValueError('Unsupported operation or operand count')
    for operand in operands:
        if not isinstance(operand,dict) or set(operand)!={'subject','predicate','unit','period'} or any(not isinstance(v,str) or not v.strip() or len(v)>120 for v in operand.values()):
            raise ValueError('Operands require literal subject, predicate, unit and period; no values or formulas')
        if not re.fullmatch(PERIOD,operand['period']):raise ValueError('Period must be a single explicit year/quarter/identifier')
    if len({o['unit'].casefold() for o in operands})!=1:raise ValueError('Operand units differ; implicit conversion is unsupported')


def authorize(question,scope,contract,*,reviewer,rationale):
    """Explicit operator action; this is not identity authentication/human review."""
    validate(contract)
    if contract is None or any(not isinstance(v,str) or not v.strip() for v in (reviewer,rationale)):
        raise ValueError('Authorization requires contract, reviewer and rationale')
    return {'version':1,'reviewer':reviewer,'rationale':rationale,
            'binding':digest({'question':question,'scope':scope or {},'contract':contract})}


def authorized(question,scope,contract,approval,reviewers):
    validate(contract)
    return (contract is not None and isinstance(approval,dict) and approval.get('version')==1
            and approval.get('reviewer') in reviewers and bool(str(approval.get('rationale') or '').strip())
            and approval.get('binding')==digest({'question':question,'scope':scope or {},'contract':contract}))


def _assertions(text,operand):
    """Only contiguous predicate-bound statements/series; never scan arbitrary tails."""
    anchor=r'(?<!\w)'+literal(operand['subject'])+r'\s+'+literal(operand['predicate'])
    unit=literal(operand['unit']);copula=r'\s+(?:is|are|was|were|equals)\s+'
    assertions=[]
    for head in re.finditer(anchor+copula,text,re.I):
        cursor=head.end();series=[]
        term=re.compile(r'('+NUMBER+r')\s+'+unit+r'\s+for\s+('+PERIOD+r')(?!\w)',re.I)
        while True:
            match=term.match(text,cursor)
            if not match:break
            series.append((match[1],match[2],head.start(),match.end()))
            cursor=match.end()
            sep=re.match(r'(?:\s*,\s*(?:and\s+)?|\s+and\s+)',text[cursor:],re.I)
            if not sep:break
            cursor+=sep.end()
        # An unparsed clause could change the subject/qualification: refuse it.
        if series and re.fullmatch(r'[\s.!?]*',text[cursor:]):assertions.extend(series)
    front=anchor+r'\s+for\s+('+PERIOD+r')'+copula+r'('+NUMBER+r')\s+'+unit+r'(?!\w)'
    for match in re.finditer(front,text,re.I):
        if re.fullmatch(r'[\s.!?]*',text[match.end():]):assertions.append((match[2],match[1],match.start(),match.end()))
    return assertions


def extract(context,operand,cfg,scope=None):
    """Return every matching candidate with provenance and explicit uncertainty."""
    validate({'version':1,'operation':'lookup','operands':[operand]})
    from .evidence_contract import precheck
    eligible,screen=precheck('',context,cfg,None,scope)
    sources={s['id']:s for s in cfg.get('sources',[])};facts=[];uncertain=[]
    for c in eligible:
        text=c['text']
        if c.get('chunk_strategy')=='table':
            from .tables import bind
            bound,issues=bind(c,operand,{**sources.get(c['source_id'],{}),**c},scope)
            facts.extend(bound);uncertain.extend(issues);continue
        if not re.search(r'(?<!\w)'+literal(operand['subject'])+r'\s+'+literal(operand['predicate'])+r'(?!\w)',text,re.I):continue
        if c['id'] in screen['unknown_applicability_ids']:
            uncertain.append({'passage_id':c['id'],'reason':'unknown_applicability'});continue
        expected=f"{c.get('document_id')}#chunk-p{c.get('start')}-{c.get('end')}-{hashlib.sha256(text.encode()).hexdigest()[:12]}"
        if (c.get('chunk_strategy')!='sentences' or c.get('fragmented') or c.get('id')!=expected
            or type(c.get('start')) is not int or type(c.get('end')) is not int or c['end']-c['start']!=len(text)
            or not re.fullmatch(r'[a-f0-9]{64}',c.get('document_fingerprint',''))):
            uncertain.append({'passage_id':c['id'],'reason':'unverified_or_fragmented_passage_provenance'});continue
        if re.search(r'\b(?:not|never|except|unless|however|excluded|but|only|if)\b',text,re.I):
            uncertain.append({'passage_id':c['id'],'reason':'qualified_or_negative_statement_requires_review'});continue
        for value,period,start,end in _assertions(text,operand):
            if period.casefold()!=operand['period'].casefold():continue
            metadata={**sources.get(c['source_id'],{}),**c}
            facts.append({'id':digest([c['id'],start,end,operand]),'source_id':c['source_id'],
                'source_version':c['document_fingerprint'],'document_id':c['document_id'],'passage_id':c['id'],
                'quote':text[start:end],'quote_start':c['start']+start,'quote_end':c['start']+end,
                'passage_sha256':hashlib.sha256(text.encode()).hexdigest(),
                'content_hash':hashlib.sha256(text[start:end].encode()).hexdigest(),
                **operand,'value':format(Decimal(value.replace(',','')),'f'),
                **{k:metadata.get(k) for k in ('effective_from','effective_to','jurisdiction','policy_scope','authority')},
                'applicability':'explicit_scope_metadata_checked' if scope else 'no_scope_requested','ambiguity':'unadjudicated_literal_grammar'})
    values={Decimal(f['value']) for f in facts}
    state='conflict' if len(values)>1 else 'supported_grammar' if facts else 'out_of_scope' if screen['excluded_inapplicable_ids'] and not eligible else 'ambiguous' if uncertain else 'missing'
    for fact in facts:fact['conflict']=len(values)>1
    return {'state':state,'facts':facts,'uncertainties':uncertain,'scope_check':screen,'semantic_approval':None}


def _calculate_in_process(context,contract,cfg,scope=None):
    validate(contract)
    result={'status':'REVIEW','binding_status':'missing_contract','value':None,'operation':None,
            'operands':[],'semantic_approval':None,'origin':'literal_source_calculation',
            'limitations':'Supported grammar and arithmetic are not independent semantic truth. Task intent needs operator authorization; strict release still requires independent reviews.'}
    if contract is None:return result
    result['operation']=contract['operation']
    # Structural span hashes alone cannot authenticate a supplied source version.
    # Rebind against the actual registered index before returning any value.
    from .ingest import scan_sources
    indexed={c['id']:c for c in scan_sources(cfg)[1]}
    fields=('id','text','start','end','document_fingerprint','source_id','document_id','chunk_strategy','fragmented','table')
    if len({c['id'] for c in context})!=len(context) or any(c['id'] not in indexed or any(c.get(k)!=indexed[c['id']].get(k) for k in fields) for c in context):
        result['binding_status']='invalid_provenance';return result
    context=[indexed[c['id']] for c in context]
    for operand in contract['operands']:result['operands'].append(extract(context,operand,cfg,scope))
    states=[r['state'] for r in result['operands']]
    if any(s!='supported_grammar' for s in states):
        result['binding_status']=next(s for s in ('conflict','ambiguous','out_of_scope','missing') if s in states);return result
    # Doubt in a relevant candidate must not be hidden by another successful match.
    if any(r['uncertainties'] for r in result['operands']):
        result['binding_status']='ambiguous';return result
    values=[Decimal(r['facts'][0]['value']) for r in result['operands']]
    with localcontext() as ctx:
        ctx.prec=max(28,sum(len(v.as_tuple().digits) for v in values)+8)
        op=contract['operation']
        answer=values[0] if op=='lookup' else sum(values) if op=='add' else values[0]-values[1] if op=='subtract' else values[0]>values[1] if op=='greater_than' else values[0]<values[1] if op=='less_than' else values[0]==values[1]
    result.update(binding_status='supported_grammar',value=('true' if answer else 'false') if type(answer) is bool else format(answer,'f'))
    return result


def select(context,contract,cfg,scope=None):
    """Retain all predicate-bound candidates, including conflicting values."""
    validate(contract)
    if contract is None:return [],{'fact_selection':'missing_contract'}
    extracted=[extract(context,o,cfg,scope) for o in contract['operands']]
    ids={f['passage_id'] for r in extracted for f in r['facts']}
    # Preserve unresolved relevant passages for review rather than hiding them.
    ids|={u['passage_id'] for r in extracted for u in r['uncertainties']}
    return [c for c in context if c['id'] in ids],{'fact_selection':[r['state'] for r in extracted],
        'fact_candidates':extracted,'abstain_without_context':True,'limitation':'Explicit contract-bound grammar selection, not independently adjudicated relevance.'}


def answer(question,context,contract,approval,cfg,scope=None):
    """Explicit non-LLM answer mode. Missing authorization/support abstains."""
    from .evidence_contract import abstention
    from .answer_contract import check
    calculation=calculate(context,contract,cfg,scope)
    approved=authorized(question,scope,contract,approval,cfg.get('settings',{}).get('calculation_reviewers',[]))
    supported=approved and calculation['binding_status']=='supported_grammar'
    trace={'abstain':not supported,'reasons':[] if supported else ['unapproved_calculation_contract' if not approved else calculation['binding_status']],
           'entailment':'unverified','available_ids':[c['id'] for c in context]}
    result=abstention(trace,cfg);result.update(answer_origin='source_calculation',calculation=calculation,
        usage_source='not_called_source_calculation',model_name='source-bound-calculation-v1')
    calculation['operation_authorized']=approved
    if supported:
        value=calculation['value'];valid,reason=check(value,cfg.get('_answer_contract'))
        if not valid:
            calculation.update(binding_status='answer_type_mismatch')
            trace.update(abstain=True,reasons=['answer_type_mismatch'])
            return result
        ids=list(dict.fromkeys(f['passage_id'] for operand in calculation['operands'] for f in operand['facts']))
        result.update(answer=value,normalized_answer=value,raw_answer=value,citations=ids,
                      answer_contract_valid=True,answer_contract_reason=reason,grounding_precheck=trace)
    result['raw_response']={'mode':'source_calculation','calculation':calculation,'answer':result['answer']}
    return result


def unresolved_table_subjects(groups,calculation):
    """Resolve lexical header/value separation only from actual bound cells.

    Callers must first verify the operation authorization and real source binding.
    This satisfies a necessary subject check, never semantic adjudication.
    """
    if calculation.get('binding_status')!='supported_grammar':return groups
    subjects=[f['subject']+' '+f['predicate'] for o in calculation['operands'] for f in o['facts'] if f.get('table_format')]
    return [g for g in groups if not any(re.search(r'(?<!\w)'+literal(a)+r'(?!\w)',s,re.I) for a in g for s in subjects)]


def calculate(context,contract,cfg,scope=None):
    from .ingest import _WORKER_ACTIVE
    if _WORKER_ACTIVE:return _calculate_in_process(context,contract,cfg,scope)
    from .parser_boundary import calculate as isolated_calculate
    return isolated_calculate(cfg,context,contract,scope)
