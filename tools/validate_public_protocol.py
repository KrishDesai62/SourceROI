"""Public documents + local MOCK chat HTTP integration; zero real model calls.

This deliberately abstaining protocol stub has no tokenizer, model, or answer key.
It reports no usage, so token savings, costs, and semantic support stay unknown.
"""
import argparse
from copy import deepcopy
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import sys
import threading

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from sourceroi.live.config import read_config
from sourceroi.live.study import run_study, export_study


def validate(project, output):
    requests = []
    class MockChat(BaseHTTPRequestHandler):
        def log_message(self, *_):
            pass
        def do_POST(self):
            if self.path != '/v1/chat/completions':
                self.send_error(404)
                return
            body = json.loads(self.rfile.read(int(self.headers['Content-Length'])))
            # Keep only counts/shape diagnostics. Do not log questions, sources or credentials.
            assert isinstance(body['messages'], list)
            requests.append({'message_count': len(body['messages']), 'has_model': bool(body.get('model'))})
            reply = {'model': 'protocol-stub-not-an-llm',
                     'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps({'answer': 'INSUFFICIENT_EVIDENCE', 'citations': []})}}],
                     'usage': {}}
            encoded = json.dumps(reply).encode()
            self.send_response(200)
            self.send_header('Content-Type', 'application/json')
            self.send_header('Content-Length', str(len(encoded)))
            self.end_headers()
            self.wfile.write(encoded)
    cfg = deepcopy(read_config(project))
    server = ThreadingHTTPServer(('127.0.0.1', 0), MockChat)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        cfg['model']['base_url'] = f'http://127.0.0.1:{server.server_port}/v1'
        cfg['model']['name'] = 'protocol-stub-not-an-llm'
        cfg['model']['api_key_env'] = 'SOURCEROI_UNUSED_MOCK_CREDENTIAL'
        cfg['measurement_kind'] = 'local_test_adapter'
        report = run_study(cfg)
        report['protocol_validation'] = {'external_documents': True, 'real_model_calls': 0,
            'mock_http_requests': len(requests), 'invented_usage': False,
            'note': 'Abstaining protocol stub only; no real-model optimization evidence.'}
        # Persist the explicit protocol classification as well as the ordinary completed report.
        from sourceroi.live import db
        db.finish(cfg, report['run_id'], report)
        export_study(report, output)
        return report
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


if __name__ == '__main__':
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--project', required=True)
    p.add_argument('--output', type=Path, required=True)
    args = p.parse_args()
    result = validate(args.project, args.output)
    print(json.dumps({'output': str(args.output), 'mock_requests': result['api_calls'],
                      'real_model_calls': 0, 'verdict': result['recommendation']['deployment_verdict']}))
