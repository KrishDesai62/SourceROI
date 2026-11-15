"""Separate, read-only record RAG application. Standard library only.

No SourceROI imports, benchmark/expected labels, model calls or commercial APIs.
Authored by Codex for engineering validation, not an independent customer app.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re


def digest(value,compact=False):
    return hashlib.sha256(json.dumps(value,sort_keys=True,**({'separators':(',',':')} if compact else {})).encode()).hexdigest()


def load(root):
    root=Path(root).resolve();docs=[];manifest={}
    folder=root/'sources/policy'
    for p in sorted(folder.glob('*.json')):
        if not p.resolve().is_relative_to(root):raise ValueError('Symlink outside knowledge root')
        data=json.loads(p.read_text());text=json.dumps(data,ensure_ascii=False,indent=2)
        ident='policy::'+p.name;manifest[ident]=hashlib.sha256(text.encode()).hexdigest()
        docs.append({'id':ident,'text':text,'data':data})
    if not docs:raise ValueError('No knowledge records')
    return docs,manifest


def evaluate(payload,roots):
    if payload.get('protocol_version')!=2 or payload.get('request_filter_ack') is not True:raise ValueError('v2 required')
    fields={k:payload[k] for k in ('task_id','question','allowed_source_ids','excluded_source_ids','excluded_document_ids','retrieval_controls','knowledge_version')}
    if digest(fields,compact=True)!=payload.get('request_id'):raise ValueError('Bad request digest')
    if payload['retrieval_controls']:raise ValueError('Unsupported controls')
    chosen=None
    for root in roots:
        docs,manifest=load(root)
        if digest(manifest)==payload['knowledge_version']:chosen=(docs,manifest);break
    if chosen is None:raise ValueError('Requested knowledge version is not available')
    docs,manifest=chosen
    allowed=set(payload['allowed_source_ids']);excluded=set(payload['excluded_source_ids']);disabled=set(payload['excluded_document_ids'])
    if not (allowed|excluded)<={'policy'} or allowed&excluded or not disabled<=set(manifest):raise ValueError('Invalid restrictions')
    question=set(re.findall('[a-z0-9]+',payload['question'].lower()))
    ranked=[]
    for doc in docs:
        if 'policy' not in allowed or 'policy' in excluded or doc['id'] in disabled:continue
        for field,value in doc['data'].items():
            words=set(re.findall('[a-z0-9]+',field.lower()))
            score=len(question&words)/max(1,len(words))
            if score>0:ranked.append((score,doc['id'],str(value)))
    ranked.sort(key=lambda r:(-r[0],r[1]))
    ids=[ranked[0][1]+'#chunk0'] if ranked else []
    return {'answer':ranked[0][2] if ranked else 'INSUFFICIENT_EVIDENCE','citations':ids,'retrieved_chunk_ids':ids,
        'filter_applied':True,'request_id':payload['request_id'],'enforced_restrictions':{k:payload[k] for k in ('allowed_source_ids','excluded_source_ids','excluded_document_ids')},
        'retrieval_controls_applied':{},'knowledge_version':digest(manifest),'knowledge_manifest':manifest,
        'model':'independent-code-record-retriever-v1','usage':{}}


def main():
    p=argparse.ArgumentParser();p.add_argument('--baseline',type=Path,required=True);p.add_argument('--candidate',type=Path,required=True,action='append');p.add_argument('--port',type=int,default=0)
    args=p.parse_args()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.path!='/evaluate':self.send_error(404);return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=64000:raise ValueError('Size limit')
                response=evaluate(json.loads(self.rfile.read(n)),[args.baseline]+args.candidate)
                data=json.dumps(response).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (ValueError,KeyError,TypeError,OSError):self.send_error(400,'Invalid request or unavailable knowledge version')
    server=ThreadingHTTPServer(('127.0.0.1',args.port),Handler)
    print('http://127.0.0.1:'+str(server.server_port)+'/evaluate',flush=True)
    try:server.serve_forever()
    finally:server.server_close()

if __name__=='__main__':main()
