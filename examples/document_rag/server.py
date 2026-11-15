"""Read-only document RAG example; no SourceROI imports or evaluation labels.

Authored by Codex, not independent customer software. Lexical document retrieval
and regex extraction are genuine execution but not a general semantic model.
"""
import argparse
import hashlib
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import json
from pathlib import Path
import re


def digest(value,compact=False):return hashlib.sha256(json.dumps(value,sort_keys=True,**({'separators':(',',':')} if compact else {})).encode()).hexdigest()

def identity(ranking):return {'model':'document-regex-extractor-v1','prompt':digest('Extract the first stated day count from the highest ranked applicable document'), 'retrieval':digest({'algorithm':'lexical_document_overlap_v1','ranking':ranking})}

def load(root):
    root=Path(root).resolve();docs=[];manifest={}
    for path in sorted((root/'sources').glob('*/*.txt')):
        if not path.resolve().is_relative_to(root):raise ValueError('Escaping source file')
        text=path.read_text(encoding='utf-8-sig');sid=path.parent.name;docid=sid+'::'+path.name
        docs.append({'id':docid,'source':sid,'text':text});manifest[docid]=hashlib.sha256(text.encode()).hexdigest()
    return docs,manifest


def evaluate(payload,roots,ranking):
    if payload.get('protocol_version')!=2 or payload.get('request_filter_ack') is not True:raise ValueError('v2 required')
    fields={k:payload[k] for k in ('task_id','question','allowed_source_ids','excluded_source_ids','excluded_document_ids','retrieval_controls','knowledge_version','execution_identity')}
    if digest(fields,compact=True)!=payload.get('request_id') or payload['execution_identity']!=identity(ranking):raise ValueError('Identity mismatch')
    selected=None
    for root in roots:
        docs,manifest=load(root)
        if digest(manifest)==payload['knowledge_version']:selected=(docs,manifest);break
    if selected is None:raise ValueError('Unavailable knowledge version')
    docs,manifest=selected;known={d['source'] for d in docs}
    allowed=set(payload['allowed_source_ids']);excluded=set(payload['excluded_source_ids']);disabled=set(payload['excluded_document_ids'])
    if not (allowed|excluded)<=known or allowed&excluded or not disabled<=set(manifest) or payload['retrieval_controls']:raise ValueError('Unsupported restrictions')
    stop={'what','how','many','days','is','the','answer','only','number','period','a','for'}
    question=set(re.findall('[a-z]+',payload['question'].lower()))-stop
    ranked=[]
    for doc in docs:
        if doc['source'] not in allowed or doc['source'] in excluded or doc['id'] in disabled:continue
        score=len(question&set(re.findall('[a-z]+',doc['text'].lower())))
        if not score:continue
        if doc['source']==('archive' if ranking=='prefer_archive' else 'current'):score+=.25
        ranked.append((score,doc['id'],doc['text']))
    ranked.sort(key=lambda r:(-r[0],r[1]));result=ranked[:1]
    match=re.search(r'\b(\d+)\s+days\b',result[0][2]) if result else None
    citations=[result[0][1]+'#chunk0'] if match else []
    return {'answer':match.group(1) if match else 'INSUFFICIENT_EVIDENCE','citations':citations,
        'retrieved_chunk_ids':[r[1]+'#chunk0' for r in result],'knowledge_manifest':manifest,'knowledge_version':digest(manifest),
        'execution_identity':identity(ranking),'filter_applied':True,'request_id':payload['request_id'],
        'enforced_restrictions':{k:payload[k] for k in ('allowed_source_ids','excluded_source_ids','excluded_document_ids')},
        'retrieval_controls_applied':{},'response_complete':True,'model':'document-regex-extractor-v1','usage':{}}


def main():
    p=argparse.ArgumentParser();p.add_argument('--root',type=Path,action='append',required=True);p.add_argument('--ranking-file',type=Path,required=True);args=p.parse_args()
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass
        def do_POST(self):
            if self.path!='/evaluate':self.send_error(404);return
            try:
                n=int(self.headers.get('Content-Length','0'))
                if not 0<n<=64000:raise ValueError('Size')
                payload=json.loads(self.rfile.read(n));ranking=json.loads(args.ranking_file.read_text())['ranking']
                data=json.dumps(evaluate(payload,args.root,ranking)).encode()
                self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(data)));self.end_headers();self.wfile.write(data)
            except (ValueError,KeyError,TypeError,OSError):self.send_error(400,'Invalid request or version/identity unavailable')
    server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
    print(json.dumps({'endpoint':'http://127.0.0.1:'+str(server.server_port)+'/evaluate','execution_identity':identity(json.loads(args.ranking_file.read_text())['ranking'])}),flush=True)
    try:server.serve_forever()
    finally:server.server_close()

if __name__=='__main__':main()
