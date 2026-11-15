"""Internal acceptance fixture, not a customer app or LLM.

Reads the actual frozen corpus, never expected benchmark labels. Use your own
application for a genuine external pilot; this deterministic fixture is not RAG
quality evidence.
"""
import re
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources
from sourceroi.live.data_ci import digest


def answer(*, question, task_id, snapshot_root, knowledge_manifest, scope, contracts):
    docs,chunks=scan_sources(read_config(snapshot_root))
    observed={d['id']:d['fingerprint'] for d in docs}
    pattern=(r'Return window is (\d+) days\.' if question=='What is the return window?'
             else r'Warranty is (\d+) days\.' if question=='What is the warranty?' else None)
    matches=[(c,re.search(pattern,c['text'])) for c in chunks] if pattern else []
    matches=[(c,m) for c,m in matches if m]
    values={m[1] for _,m in matches}
    ids=[c['id'] for c,_ in matches]
    return {'answer':next(iter(values)) if len(values)==1 else 'INSUFFICIENT_EVIDENCE',
            'retrieved_chunk_ids':ids,'citations':ids if len(values)==1 else [],
            'knowledge_manifest':observed,'knowledge_version':digest(observed),
            'response_complete':True}  # No invented model usage.
