"""Thin integration example, NOT an application or a simulated customer backend.

Replace the import/call with your existing read-only RAG function. It must bind to
snapshot_root and report actual document hashes and actual retrieved passage IDs.
No labels, expected values, fabricated citations or invented usage are supplied.
"""


def answer(*,question,task_id,snapshot_root,knowledge_manifest,scope,contracts):
    from your_existing_rag import answer_with_trace
    return answer_with_trace(question=question,task_id=task_id,
        corpus_root=snapshot_root,expected_manifest=knowledge_manifest,
        scope=scope,contracts=contracts)
