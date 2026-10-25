"""Canonical URI text inputs and checked Host:Port; isolated worker supported."""
import argparse
import http.server
import json
from pathlib import Path
import subprocess
import threading
import urllib.parse
from outbound_test_policy import allow
ROOT = Path(__file__).resolve().parent

class Peer(http.server.BaseHTTPRequestHandler):
    def log_message(self, *_): pass
    def do_GET(self):
        fields=urllib.parse.parse_qs(urllib.parse.urlsplit(self.path).query)
        self.server.requests.append((self.path,fields))
        template=fields.get('template',[''])[0]
        body=(b'success([pair(ok,ok)],false).\n' if 'pair(' in template else b'success([v(ok)],false).\n')
        self.send_response(200);self.send_header('Content-Length',str(len(body)))
        self.end_headers();self.wfile.write(body)

def run(worker):
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Peer)
    server.daemon_threads=True;server.requests=[]
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    uri=f'http://127.0.0.1:{server.server_port}';allow(uri);count=0
    def expect(goal):
        nonlocal count
        p=subprocess.run([worker,f'query(({goal}),ok)','100'],cwd=ROOT,input='',capture_output=True,text=True,timeout=10)
        actual=[json.loads(line) for line in p.stdout.splitlines()]
        assert p.returncode==0 and actual==[{'type':'success','answers':['ok'],'more':False}],(goal,p.returncode,actual,p.stderr)
        count+=1
    try:
        for value,error in [('42','type_error(text,42)'),('1.5','type_error(text,1.5)'),('foo(bar)','type_error(text,foo(bar))'),('localhost:bad','type_error(integer,bad)'),('localhost:P','instantiation_error'),('U','instantiation_error')]:
            for kind in ['rpc','promise']:
                options=f"[src_uri('{uri}/source')]"
                goal=f'rpc({value},true,{options})' if kind=='rpc' else f'promise({value},true,_,{options})'
                before=len(server.requests)
                expect(f'catch(({goal},fail),error({error},_),true),var(U),var(P)')
                assert len(server.requests)==before
        chars='['+','.join(repr(c) for c in uri)+']'
        codes='['+','.join(str(ord(c)) for c in uri)+']'
        for value in [repr(uri),json.dumps(uri),chars,codes,f"'127.0.0.1':{server.server_port}"]:
            expect(f'rpc({value},X=ok),X==ok')
            expect(f'promise({value},Y=ok,R,[template(pair(Y,Y))]),yield(R,A),A==success([pair(ok,ok)],false),var(Y)')
        print(f'PASS {count} URI type, zero-request, text-form, Host:Port and sharing assertions')
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--worker',default=str(ROOT/'query-worker'))
    run(str(Path(p.parse_args().worker).resolve()))
