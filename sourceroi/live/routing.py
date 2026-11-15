"""Explicit versioned source restrictions shared by app evaluation and Data CI.

Rules restrict sources; they never infer latest/authoritative facts from dates or
answer labels. Multiple matches intersect. Scope/conflict checks still run.
"""
from .data_ci import digest


def validate(contract,source_ids):
    if contract is None:return
    if not isinstance(contract,dict) or set(contract)!={'version','rules'} or contract['version']!=1:raise ValueError('retrieval_contract must be version 1 with rules')
    rules=contract['rules']
    if not isinstance(rules,list) or not 1<=len(rules)<=32:raise ValueError('retrieval_contract needs 1..32 explicit source rules')
    for rule in rules:
        if not isinstance(rule,dict) or set(rule)-{'contains','source_ids','case_sensitive'} or not {'contains','source_ids'}<=set(rule):raise ValueError('Routing rules require contains and source_ids')
        if not isinstance(rule['contains'],str) or not rule['contains'].strip() or len(rule['contains'])>120:raise ValueError('Invalid routing question selector')
        if type(rule.get('case_sensitive',True)) is not bool:raise ValueError('case_sensitive must be boolean')
        ids=rule['source_ids']
        if not isinstance(ids,list) or not ids or any(not isinstance(i,str) or i not in source_ids for i in ids) or len(ids)!=len(set(ids)):raise ValueError('Routing sources must be distinct registered IDs')


def restrict(question,chunks,cfg):
    contract=cfg.get('settings',{}).get('retrieval_contract')
    known={s['id'] for s in cfg['sources']};validate(contract,known)
    allowed=set(known);matched=[]
    for index,rule in enumerate((contract or {}).get('rules',[])):
        selector=rule['contains'];text=question
        if not rule.get('case_sensitive',True):selector=selector.casefold();text=text.casefold()
        if selector in text:allowed &= set(rule['source_ids']);matched.append(index)
    selected=[c for c in chunks if c['source_id'] in allowed]
    return selected,{'version':1,'contract_sha256':digest(contract),'matched_rule_indices':matched,
        'allowed_source_ids':sorted(allowed),'excluded_chunk_ids':[c['id'] for c in chunks if c['source_id'] not in allowed],
        'basis':'Explicit declared source restriction, not semantic authority or conflict adjudication'}
