"""Versioned, domain-neutral HTTP agent restriction contract.

Acknowledgments are integration assertions, not proof against a dishonest agent.
"""
import hashlib
import json

CONTROL_NAMES = {'max_chunks', 'max_context_chars', 'excluded_passage_ids', 'deduplicate_passages'}


def validate_controls(controls):
    if not isinstance(controls, dict) or not set(controls) <= CONTROL_NAMES:
        raise ValueError('Unsupported retrieval control')
    for name, value in controls.items():
        if name in ('max_chunks', 'max_context_chars') and (type(value) is not int or value < 1):
            raise ValueError(f'{name} must be positive integer')
        if name == 'deduplicate_passages' and type(value) is not bool:
            raise ValueError('deduplicate_passages must be boolean')
        if name == 'excluded_passage_ids' and (not isinstance(value, list) or not all(isinstance(v, str) for v in value)):
            raise ValueError('excluded_passage_ids must be a list of strings')


def restriction_digest(payload):
    fields = {k: payload[k] for k in ('task_id', 'question', 'allowed_source_ids', 'excluded_source_ids',
                                      'excluded_document_ids', 'retrieval_controls')}
    if 'knowledge_version' in payload:fields['knowledge_version']=payload['knowledge_version']
    if 'execution_identity' in payload:fields['execution_identity']=payload['execution_identity']
    return hashlib.sha256(json.dumps(fields, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def attach_contract(payload, agent, controls):
    validate_controls(controls)
    if agent.get('protocol_version', 1) != 2:
        if agent.get('knowledge_manifest') is not None or agent.get('execution_identity') is not None:raise ValueError('Knowledge-version checks require agent protocol v2')
        if controls:
            raise ValueError('Agent protocol v1 cannot enforce requested retrieval controls; configure v2')
        return payload
    if not set(controls) <= set(agent.get('capabilities', [])):
        raise ValueError('Agent does not declare all requested retrieval capabilities')
    payload = {**payload, 'protocol_version': 2, 'retrieval_controls': controls}
    if agent.get('knowledge_manifest') is not None:
        manifest=agent['knowledge_manifest']
        if not isinstance(manifest,dict) or not manifest or any(not isinstance(k,str) or not isinstance(v,str) or len(v)!=64 for k,v in manifest.items()):raise ValueError('Invalid knowledge manifest')
        payload['knowledge_version']=hashlib.sha256(json.dumps(manifest,sort_keys=True).encode()).hexdigest()
    if agent.get('execution_identity') is not None:
        identity=agent['execution_identity']
        if not isinstance(identity,dict) or set(identity)!={'model','prompt','retrieval'} or any(not isinstance(v,str) or not v for v in identity.values()):raise ValueError('Invalid execution identity')
        payload['execution_identity']=identity
    payload['request_id'] = restriction_digest(payload)
    return payload


def check_acknowledgment(payload, response):
    if payload.get('protocol_version') != 2:
        return
    if 'knowledge_version' in payload and response.get('knowledge_version')!=payload['knowledge_version']:
        raise ValueError('Agent used a different knowledge version')
    if 'execution_identity' in payload and response.get('execution_identity')!=payload['execution_identity']:
        raise ValueError('Agent model/prompt/retrieval identity changed')
    enforced = response.get('enforced_restrictions')
    if not isinstance(enforced, dict) or response.get('request_id') != payload['request_id']:
        raise ValueError('Agent omitted or mismatched restriction acknowledgment')
    for name in ('allowed_source_ids', 'excluded_source_ids', 'excluded_document_ids'):
        actual = enforced.get(name)
        if not isinstance(actual, list) or not all(isinstance(x, str) for x in actual) or sorted(actual) != sorted(payload[name]):
            raise ValueError('Agent did not acknowledge the exact requested restrictions')
    if json.dumps(response.get('retrieval_controls_applied'), sort_keys=True) != json.dumps(payload['retrieval_controls'], sort_keys=True):
        raise ValueError('Agent did not acknowledge the exact requested retrieval controls')


def callback_for(answer_question):
    """Bridge a trusted application's answer function into release assurance.

    The application must return its observed manifest and retrieval trace; the
    bridge never invents citations, usage, labels or provenance acknowledgments.
    Manifest assertions do not sandbox/authenticate a dishonest application.
    """
    from copy import deepcopy
    import time
    from .ingest import scan_sources
    from .data_ci import digest
    from .answer_contract import normalize,check
    def callback(cfg,tasks):
        docs,chunks=scan_sources(cfg);manifest={d['id']:d['fingerprint'] for d in docs};known={c['id'] for c in chunks};rows=[]
        for task in tasks:
            start=time.perf_counter()
            response=answer_question(question=task['question'],task_id=task['id'],snapshot_root=cfg['_root'],
                knowledge_manifest=deepcopy(manifest),scope=deepcopy(task.get('scope',{})),
                contracts={k:deepcopy(task[k]) for k in ('answer_contract','evidence_contract','calculation_contract','calculation_authorization') if k in task})
            if not isinstance(response,dict) or response.get('knowledge_manifest')!=manifest or response.get('knowledge_version')!=digest(manifest):
                raise ValueError('Application must report the observed frozen knowledge manifest/version')
            identity=cfg.get('agent',{}).get('execution_identity')
            if identity is not None and response.get('execution_identity')!=identity:raise ValueError('Application execution identity changed')
            retrieved=response.get('retrieved_chunk_ids');citations=response.get('citations')
            if any(not isinstance(v,list) or any(not isinstance(i,str) for i in v) for v in (retrieved,citations)):
                raise ValueError('Application must return explicit retrieval and citation ID lists')
            if not set(retrieved)<=known:raise ValueError('Application retrieval trace is outside the registered index')
            if response.get('response_complete') is not True:raise ValueError('Application execution is incomplete')
            raw=response.get('answer');contract=task.get('answer_contract');value=normalize(raw,contract) if contract else str(raw)
            valid,reason=check(raw,contract)
            usage=response.get('usage',{})
            if not isinstance(usage,dict):raise ValueError('Application usage must be an object or omitted')
            for key in ('prompt_tokens','completion_tokens'):
                if usage.get(key) is not None and (type(usage[key]) is not int or usage[key]<0):raise ValueError('Invalid application token usage')
            rows.append({'id':task['id'],'answer':value,'actual':value,'raw_answer':raw,'raw_response':response,
                'answer_contract_valid':valid,'answer_contract_reason':reason,'answer_origin':'external_callback',
                'retrieved_chunk_ids':retrieved,'citations':citations,'invalid_citations':[c for c in citations if c not in retrieved],
                'knowledge_manifest':deepcopy(manifest),'knowledge_version':digest(manifest),'execution_identity':response.get('execution_identity'),
                'response_complete':True,'json_format_valid':True,'prompt_tokens':usage.get('prompt_tokens'),'completion_tokens':usage.get('completion_tokens'),
                'end_to_end_latency_ms':round((time.perf_counter()-start)*1000,3),'usage_source':'application_reported' if usage else 'unavailable'})
        if {d['id']:d['fingerprint'] for d in scan_sources(cfg)[0]}!=manifest:raise ValueError('Application source files changed during execution')
        return {'tasks':rows,'metrics':{'total_tokens':sum(r['prompt_tokens']+r['completion_tokens'] for r in rows)
            if all(r['prompt_tokens'] is not None and r['completion_tokens'] is not None for r in rows) else None,
            'total_cost_usd':None},'adapter_identity':'trusted-callback-v1; assertions are not independent source attestation'}
    return callback
