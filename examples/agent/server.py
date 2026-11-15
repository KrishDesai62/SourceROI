"""Domain-neutral v2 reference agent. Local lexical extraction, NOT an LLM.

Run: python examples/agent/server.py --project MY_WORKSPACE --port 8777
No model calls, invented usage, expected answers, or production side effects.
"""
import argparse
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from sourceroi.live.adapter import validate_controls, restriction_digest
from sourceroi.live.config import read_config
from sourceroi.live.ingest import scan_sources
from sourceroi.live.policies import select_context


def evaluate(payload, cfg):
    if payload.get('protocol_version') != 2 or payload.get('request_filter_ack') is not True:
        raise ValueError('This example requires the v2 restriction contract')
    controls = payload.get('retrieval_controls', {})
    validate_controls(controls)
    if payload.get('request_id') != restriction_digest(payload):
        raise ValueError('Request hash mismatch')
    documents, chunks = scan_sources(cfg)
    sources = {s['id'] for s in cfg['sources']}
    known_docs, known_passages = {d['id'] for d in documents}, {c['id'] for c in chunks}
    for field in ('allowed_source_ids', 'excluded_source_ids', 'excluded_document_ids'):
        if not isinstance(payload.get(field), list) or not all(isinstance(v, str) for v in payload[field]):
            raise ValueError('Restriction IDs must be lists')
    allowed, excluded, disabled_docs = (set(payload[f]) for f in ('allowed_source_ids', 'excluded_source_ids', 'excluded_document_ids'))
    excluded_passages = set(controls.get('excluded_passage_ids', []))
    if not allowed <= sources or not excluded <= sources or allowed & excluded or not disabled_docs <= known_docs or not excluded_passages <= known_passages:
        raise ValueError('Invalid or contradictory restrictions')
    filtered = [c for c in chunks if c['source_id'] in allowed and c['source_id'] not in excluded and c['document_id'] not in disabled_docs and c['id'] not in excluded_passages]
    settings = {**cfg.get('settings', {}), **{k: v for k, v in controls.items() if k != 'excluded_passage_ids'}}
    settings.pop('retrieval_policy', None)
    context, _ = select_context(payload['question'], filtered, {**cfg, 'settings': settings})
    return {'answer': '\n\n'.join(c['text'] for c in context) if context else 'INSUFFICIENT_EVIDENCE',
            'citations': [c['id'] for c in context], 'model': 'reference-lexical-extractor', 'usage': {},
            'filter_applied': True, 'request_id': payload['request_id'],
            'enforced_restrictions': {k: payload[k] for k in ('allowed_source_ids', 'excluded_source_ids', 'excluded_document_ids')},
            'retrieval_controls_applied': controls}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True)
    parser.add_argument('--port', type=int, default=8777)
    args = parser.parse_args()
    cfg = read_config(args.project)
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            if self.path != '/evaluate':
                self.send_error(404)
                return
            try:
                length = int(self.headers.get('Content-Length', 0))
                if not 0 < length <= 64000:
                    raise ValueError('Invalid request size')
                result = evaluate(json.loads(self.rfile.read(length)), cfg)
                data = json.dumps(result).encode()
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.send_header('Content-Length', str(len(data)))
                self.end_headers()
                self.wfile.write(data)
            except (KeyError, TypeError, ValueError):
                self.send_error(400, 'Invalid evaluation request')
    server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    print(f'Local reference agent: http://127.0.0.1:{server.server_port}/evaluate (not an LLM)')
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
