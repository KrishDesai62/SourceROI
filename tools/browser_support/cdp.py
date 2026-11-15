"""Minimal loopback-only Chrome DevTools test client (no browser download)."""
import base64
import hashlib
import json
import os
import socket
import struct
from urllib.parse import urlsplit

class CDP:
    def __init__(self,url):
        u=urlsplit(url)
        if u.scheme!='ws' or u.hostname not in ('127.0.0.1','localhost'):raise ValueError('Only loopback CDP permitted')
        self.sock=socket.create_connection((u.hostname,u.port),timeout=10);self.buffer=b'';self.number=0
        key=base64.b64encode(os.urandom(16)).decode()
        self.sock.sendall((f'GET {u.path} HTTP/1.1\r\nHost: {u.netloc}\r\nUpgrade: websocket\r\nConnection: Upgrade\r\nSec-WebSocket-Key: {key}\r\nSec-WebSocket-Version: 13\r\n\r\n').encode())
        data=b''
        while b'\r\n\r\n' not in data:data+=self.sock.recv(4096)
        headers,self.buffer=data.split(b'\r\n\r\n',1)
        accept=base64.b64encode(hashlib.sha1((key+'258EAFA5-E914-47DA-95CA-C5AB0DC85B11').encode()).digest())
        if b'101' not in headers.splitlines()[0] or accept not in headers:raise ValueError('CDP WebSocket upgrade failed')
    def read(self,n):
        while len(self.buffer)<n:
            chunk=self.sock.recv(max(n-len(self.buffer),4096))
            if not chunk:raise RuntimeError('CDP disconnected')
            self.buffer+=chunk
        result,self.buffer=self.buffer[:n],self.buffer[n:];return result
    def send(self,value):
        data=json.dumps(value).encode();length=len(data);header=bytes([0x81])
        header+=bytes([0x80|length]) if length<126 else bytes([0xfe])+struct.pack('!H',length) if length<65536 else bytes([0xff])+struct.pack('!Q',length)
        mask=os.urandom(4);self.sock.sendall(header+mask+bytes(v^mask[i%4] for i,v in enumerate(data)))
    def receive(self):
        a,b=self.read(2);size=b&127
        if size==126:size=struct.unpack('!H',self.read(2))[0]
        elif size==127:size=struct.unpack('!Q',self.read(8))[0]
        if size>16*1024*1024:raise ValueError('CDP message limit')
        mask=self.read(4) if b&128 else None;data=self.read(size)
        if mask:data=bytes(v^mask[i%4] for i,v in enumerate(data))
        if a&15==8:raise RuntimeError('Browser closed CDP')
        if a&15!=1:return self.receive()
        return json.loads(data)
    def call(self,method,params=None):
        self.number+=1;number=self.number;self.send({'id':number,'method':method,'params':params or {}})
        while True:
            result=self.receive()
            if result.get('id')==number:
                if 'error' in result:raise RuntimeError(str(result['error']))
                return result.get('result',{})
    def evaluate(self,expression):
        r=self.call('Runtime.evaluate',{'expression':expression,'returnByValue':True,'awaitPromise':True})
        if r.get('exceptionDetails'):raise RuntimeError(str(r['exceptionDetails']))
        return r.get('result',{}).get('value')
    def close(self):self.sock.close()
