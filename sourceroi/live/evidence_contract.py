"""Necessary-evidence screening, not semantic entailment or independent truth."""
from datetime import date
import re


def validate(contract):
    if contract is None:return
    if not isinstance(contract,dict) or set(contract)-{'version','subject_aliases','abstain_on_conflict'} or contract.get('version')!=1:raise ValueError('Invalid evidence contract')
    groups=contract.get('subject_aliases',[])
    if not isinstance(groups,list) or len(groups)>16 or any(not isinstance(g,list) or not g or any(not isinstance(s,str) or not s.strip() or len(s)>120 for s in g) for g in groups):raise ValueError('Subject aliases must be nonempty synonym groups')
    if type(contract.get('abstain_on_conflict',True)) is not bool:raise ValueError('Conflict flag must be boolean')


def has_fact_predicate(text):
    """Exclude isolated document navigation markers, not substantive assertions."""
    text=text.strip()
    if not any(ch.isalpha() for ch in text):return False
    if re.fullmatch(r'\[Page\s+\d+\]',text,re.I):return False
    if re.fullmatch(r'(?:SECTION|CHAPTER|PART)\s+\d+[A-Z]?[.)]?',text,re.I):return False
    if re.fullmatch(r'See\s+(?:sections?|§)\s*\d+[A-Za-z0-9().-]*(?:\s+(?:and|or)\s+\d+[A-Za-z0-9().-]*)?(?:\s+of(?:\s+Rev\.?(?:\s+Proc\.?)?(?:\s+\d{4}-\d+)?)?)?\.?',text,re.I):return False
    return True


def _precheck_in_process(question,context,cfg,contract=None,scope=None):
    validate(contract);scope=scope or {};sources={s['id']:s for s in cfg.get('sources',[])}
    eligible=[];excluded=[];unknown=[]
    for c in context:
        metadata={**sources.get(c.get('source_id'),{}),**c};states=[]
        for key in ('jurisdiction','policy_scope'):
            if scope.get(key):states.append(None if metadata.get(key) is None else metadata[key] in (scope[key],'global'))
        if scope.get('as_of'):
            try:
                now=date.fromisoformat(scope['as_of']);start=date.fromisoformat(metadata['effective_from']) if metadata.get('effective_from') else None;end=date.fromisoformat(metadata['effective_to']) if metadata.get('effective_to') else None
                states.append(None if start is None and end is None else (start is None or start<=now) and (end is None or now<end))
            except (ValueError,TypeError):states.append(None)
        if False in states:excluded.append(c['id'])
        else:
            eligible.append(c)
            if None in states:unknown.append(c['id'])
    text='\n'.join(c['text'] for c in eligible).lower()
    missing=[g for g in (contract or {}).get('subject_aliases',[]) if not any(re.search(r'(?<!\w)'+re.escape(a.lower())+r'(?!\w)',text) for a in g)]
    conflicts=[];shapes={}
    for c in eligible:
        for line in re.split(r'\n|(?<=[.!?])\s+',c['text']):
            if not re.search(r'\d',line) or not has_fact_predicate(line):continue
            shape=re.sub(r'\d+(?:\.\d+)?','<value>',line.strip().lower())
            if shape in shapes and shapes[shape]['text']!=line.strip().lower():conflicts.append([shapes[shape]['id'],c['id']])
            shapes[shape]={'id':c['id'],'text':line.strip().lower()}
    reasons=[]
    if not eligible:reasons.append('no_applicable_supplied_context')
    if missing:reasons.append('declared_subject_requirement_missing')
    if contract and contract.get('abstain_on_conflict',True) and conflicts:reasons.append('potential_same_predicate_numeric_conflict')
    trace={'version':1,'abstain':bool(reasons),'reasons':reasons,'available_ids':[c['id'] for c in context],
        'eligible_ids':[c['id'] for c in eligible],'excluded_inapplicable_ids':excluded,'unknown_applicability_ids':unknown,
        'missing_declared_alias_groups':missing,'potential_conflicts':conflicts,
        'entailment':'unverified','basis':'Explicit necessary evidence contract and metadata only; positive matches never establish claim entailment'}
    return eligible,trace


def abstention(trace,cfg):
    return {'answer':'INSUFFICIENT_EVIDENCE','normalized_answer':'INSUFFICIENT_EVIDENCE','raw_answer':None,'raw_response':None,
        'citations':[],'invalid_citations':[],'json_format_valid':True,'response_complete':True,'answer_contract_valid':True,
        'answer_contract_reason':'software abstention, no factual value generated','grounding_precheck':trace,'answer_origin':'evidence_precheck',
        'input_tokens':0,'output_tokens':0,'context_tokens':0,'model_cost_usd':0.0,'data_cost_usd':0.0,'model_latency_ms':0.0,
        'cost_type':'not_called','usage_source':'not_called_evidence_contract','model_name':cfg['model']['name']}


def precheck(question,context,cfg,contract=None,scope=None):
    from .analysis_boundary import active,call
    if active():return _precheck_in_process(question,context,cfg,contract,scope)
    result=call('precheck',question=question,chunks=context,cfg={'sources':cfg.get('sources',[])},contract=contract,scope=scope)
    return result[0],result[1]
