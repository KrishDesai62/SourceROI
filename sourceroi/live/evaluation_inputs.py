"""Shared review materialization and fail-closed comparative input parity."""
from copy import deepcopy
from .data_ci import digest


def maintained_tasks(tasks,spec,approval):
    from .assurance import validate_review
    validate_review(spec,approval)
    result=deepcopy(tasks);approval=approval or {}
    proposals={p['id']:p for p in spec.get('evidence_proposals',[])}
    for task in result:
        tid=task['id']
        if tid in approval.get('expected_changes',{}):
            task['expected']=approval['expected_changes'][tid];task['accepted_answers']=[task['expected']]
            task['evidence']=deepcopy(approval.get('expected_evidence',{}).get(tid,[]))
        if tid in approval.get('evidence_updates',{}):
            proposal=proposals[approval['evidence_updates'][tid]['proposal_id']]
            task['evidence']=deepcopy(proposal['replacement_evidence'])
    return result


def packet(cfg,tasks,*,spec,approval,semantic_reviews=None,reviewers=()):
    from .ingest import scan_sources,load_benchmark
    from .release_policy import resolve
    docs,_=scan_sources(cfg)
    return {'version':1,'source_versions':{d['id']:d['fingerprint'] for d in docs},
        'source_metadata':deepcopy(cfg['sources']),'configuration_version':cfg['_config_hash'],
        'frozen_task_version':digest(load_benchmark(cfg)),
        'tasks':deepcopy(tasks),'expected_answers':{t['id']:t['expected'] for t in tasks},
        'evidence_requirements':{t['id']:deepcopy(t.get('evidence',[])) for t in tasks},
        'scope':{t['id']:deepcopy(t.get('scope',{})) for t in tasks},
        'citation_requirements':{t['id']:t.get('requires_grounding',False) or resolve(cfg)['name']=='strict_grounded' for t in tasks},
        'intent':deepcopy(spec.get('intent',{})),'approval':deepcopy(approval),
        'semantic_reviews':deepcopy(semantic_reviews or {}),'reviewers':list(reviewers),'policy':resolve(cfg),
        'routing_contract':deepcopy(cfg.get('settings',{}).get('retrieval_contract'))}


def assert_parity(left,right):
    if left.get('version')!=1 or right.get('version')!=1:raise ValueError('Comparison packet version missing or invalid')
    required={'source_versions','source_metadata','configuration_version','frozen_task_version','tasks','expected_answers','evidence_requirements','scope','citation_requirements','intent','approval','semantic_reviews','reviewers','policy','routing_contract'}
    if not required<=set(left) or not required<=set(right):raise ValueError('Comparison packet incomplete')
    mismatched=[k for k in sorted(set(left)|set(right)) if digest(left.get(k))!=digest(right.get(k))]
    if mismatched:raise ValueError('Comparative evaluation input mismatch: '+', '.join(mismatched))
    return {'status':'VERIFIED_INPUT_PARITY','sha256':digest(left),'independent_semantics':None}
