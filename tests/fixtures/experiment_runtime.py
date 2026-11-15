"""Explicit fake runtime for accounting tests. No model or factual answerer."""
import argparse
from http.server import BaseHTTPRequestHandler
import json
import os
from pathlib import Path
import socketserver
import threading
import time
p=argparse.ArgumentParser();p.add_argument('--socket',required=True);p.add_argument('--key-file',required=True);a=p.parse_args()
key=Path(a.key_file).read_text().strip();lock=threading.Lock()
def event(**fields):
    with lock:print(json.dumps(fields),flush=True)
class Handler(BaseHTTPRequestHandler):
    def log_message(self,*_):pass
    def reply(self,status,data):
        raw=json.dumps(data).encode();self.send_response(status);self.send_header('Content-Length',str(len(raw)));self.end_headers();self.wfile.write(raw)
    def authorized(self):
        if self.headers.get('Authorization')!='Bearer '+key:
            event(event='unauthorized',path=self.path,request_id=self.headers.get('X-SourceROI-Request'));self.reply(401,{'error':'unauthorized'});return False
        return True
    def do_GET(self):
        if self.authorized():self.reply(200,{'status':'ok'})
    def do_POST(self):
        if not self.authorized():return
        body=json.loads(self.rfile.read(int(self.headers.get('Content-Length','0'))))
        if self.path=='/tokenize':self.reply(200,{'tokens':[1,2]});return
        rid=self.headers.get('X-SourceROI-Request');event(event='accepted_chat',request_id=rid)
        if body.get('mode')=='crash':os._exit(7)
        if body.get('mode')=='delay':time.sleep(10)
        status=500 if body.get('mode')=='fail' else 200
        data={'choices':[{'message':{'content':'{"answer":"fixture","citations":[]}'},'finish_reason':'stop'}]}
        if body.get('mode')!='no_usage':data['usage']={'prompt_tokens':5,'completion_tokens':2,'total_tokens':7}
        event(event='response',request_id=rid,status=status);self.reply(status,data)
class Server(socketserver.ThreadingMixIn,socketserver.UnixStreamServer):daemon_threads=True
with Server(a.socket,Handler) as server:server.serve_forever(poll_interval=.02)
