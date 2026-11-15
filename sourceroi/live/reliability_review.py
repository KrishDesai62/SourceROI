"""Validation evidence packets: deterministic integrity vs explicit human judgments.

No model judge, no automatic semantic truth and no self-certified independence.
Reviewer allowlists/independence declarations require an external operator.
"""
from datetime import date
from .data_ci import digest
from .grounding import score_review,evidence_key


def packet(sample):
    return {'sample_key':digest(sample),'sample':sample,'status':'pending','reviewer':None,
        'independent_of_generator':None,'semantic_correctness':None,'citation_correctness':None,
        'scope_appropriate':None,'uses_outdated_fact':None,'claims':[],
        'rubric':'Judge answer meaning, cited claim support, temporal/jurisdiction applicability; quote supplied cited evidence for supported claims. Do not infer entailment from shared words or numbers.'}


def evaluate(sample,review=None,*,allowed_reviewers=()):
    known={c['id']:c for c in sample['context']};citations=sample.get('citations',[])
    if not isinstance(citations,list) or any(not isinstance(c,str) for c in citations):raise ValueError('Invalid citations')
    invalid=[c for c in citations if c not in known];applicability=[]
    requested=sample.get('scope',{})
    for cid in citations:
        if cid not in known:continue
        doc=known[cid];checks=[]
        if requested.get('jurisdiction'):
            jurisdiction=doc.get('jurisdiction');checks.append(None if jurisdiction is None else jurisdiction in (requested['jurisdiction'],'global'))
        if requested.get('policy_scope'):
            checks.append(None if doc.get('policy_scope') is None else doc['policy_scope']==requested['policy_scope'])
        if requested.get('as_of'):
            try:
                when=date.fromisoformat(requested['as_of'])
                start=date.fromisoformat(doc['effective_from']) if doc.get('effective_from') else None
                end=date.fromisoformat(doc['effective_to']) if doc.get('effective_to') else None
                checks.append(None if start is None and end is None else (start is None or start<=when) and (end is None or when<end))
            except (ValueError,TypeError):checks.append(None)
        applicability.append({'citation':cid,'applicable':False if False in checks else None if None in checks else True,
                               'basis':'Explicit scope/date metadata only; no semantic scope inference'})
    result={'sample_key':digest(sample),'deterministic':{'response_contract_valid':sample.get('response_contract_valid'),
        'answer_format_valid':sample.get('answer_contract_valid'),'invalid_citations':invalid,'missing_citations':not citations,'explicit_applicability':applicability},
        'semantic_correctness':None,'citation_correctness':None,'scope_appropriate':None,'uses_outdated_fact':None,
        'groundedness':None,'review_status':'pending','judgment_method':'unreviewed; deterministic checks are not semantic ground truth'}
    if review is None:return result
    if review.get('sample_key')!=result['sample_key']:raise ValueError('Review/sample version mismatch')
    if review.get('status')!='complete' or review.get('reviewer') not in allowed_reviewers or review.get('independent_of_generator') is not True:
        raise ValueError('Complete review by externally authorized independent reviewer required')
    for field in ('semantic_correctness','citation_correctness','scope_appropriate','uses_outdated_fact'):
        if type(review.get(field)) is not bool:raise ValueError('Review must explicitly adjudicate every dimension')
    grounding=score_review(sample['question'],sample['answer'],sample['context'],citations,
        {evidence_key(sample['question'],sample['answer'],sample['context']):review})
    if review['citation_correctness'] and (invalid or not citations or grounding['groundedness']<1):raise ValueError('Citation correctness conflicts with supplied claim/citation integrity')
    if review['scope_appropriate'] and any(c['applicable'] is False for c in applicability):raise ValueError('Review conflicts with explicit source scope/date constraints')
    return {**result,**grounding,**{k:review[k] for k in ('semantic_correctness','citation_correctness','scope_appropriate','uses_outdated_fact')},
            'review_status':'complete','reviewer':review['reviewer'],'judgment_method':'Externally supplied human adjudication; reviewer independence is an operator assertion, not cryptographic proof'}
