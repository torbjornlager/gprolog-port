"""Local TLS and HTTP boundary tests; no external service or system trust edits."""
import http.server
import json
import os
from pathlib import Path
import ssl
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parent
checks=0

def command(*args):
    args=(os.environ.get('OPENSSL',args[0]),*args[1:])
    result=subprocess.run(args,capture_output=True,timeout=15)
    assert result.returncode==0,(args[0],result.stderr.decode(errors='replace'))

def certificate(root,name,san,days=1):
    key=root/(name+'.key');csr=root/(name+'.csr');cert=root/(name+'.pem')
    ext=root/(name+'.ext');ext.write_text('subjectAltName='+san+'\nextendedKeyUsage=serverAuth\n')
    command('openssl','req','-new','-newkey','rsa:2048','-nodes','-keyout',str(key),
            '-out',str(csr),'-subj','/CN=localhost')
    command('openssl','x509','-req','-in',str(csr),'-CA',str(root/'ca.pem'),
            '-CAkey',str(root/'ca.key'),'-CAcreateserial','-out',str(cert),
            '-extfile',str(ext),
            *(['-not_before','20000101000000Z','-not_after','20010101000000Z'] if days<0 else ['-days',str(days)]))
    return cert,key

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        path=urlsplit(self.path).path
        if path.startswith('/slow'):time.sleep(.3)
        if path.startswith('/r'):
            hops=int(path.split('/')[1][1:])
            if hops:
                self.send_response(302)
                self.send_header('Location',f'/r{hops-1}/call')
                self.end_headers();return
        if path.startswith('/source'):body=b'p(from_https).'
        elif path.startswith('/missing'):
            self.send_response(404);self.end_headers();return
        else:body=b'success([v(ready)],false).'
        self.send_response(200);self.end_headers()
        try:self.wfile.write(body)
        except (OSError,ssl.SSLError):pass

class Server:
    def __init__(self,cert=None,key=None):
        self.http=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
        self.http.daemon_threads=True
        if cert:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            context.load_cert_chain(cert,key)
            self.http.socket=context.wrap_socket(self.http.socket,server_side=True)
        self.uri=('https' if cert else 'http')+f'://127.0.0.1:{self.http.server_port}'
        self.thread=threading.Thread(target=self.http.serve_forever,daemon=True);self.thread.start()
    def close(self):self.http.shutdown();self.http.server_close();self.thread.join(timeout=2)

def run(goal,ca=None):
    env=dict(os.environ);env.pop('ISO_CA_FILE',None)
    if ca is not None:env['ISO_CA_FILE']=str(ca)
    result=subprocess.run([os.environ.get('ISO_WORKER','./query-worker'),f'query(({goal}),ok)','1'],
                          input='',text=True,capture_output=True,env=env,timeout=5)
    assert result.returncode==0,(result.returncode,result.stdout,result.stderr)
    return [json.loads(line) for line in result.stdout.splitlines()]

def success(goal,ca=None):
    global checks
    result=run(goal,ca)
    assert result==[{'type':'success','answers':['ok'],'more':False}],(goal,result)
    checks+=1

def error(goal,kind,ca=None):
    global checks
    result=run(goal,ca)
    assert len(result)==1 and result[0]['type']=='error' and kind in result[0]['term'],(goal,result)
    checks+=1

def main():
    with tempfile.TemporaryDirectory(prefix='isobase-tls-') as tmp:
        root=Path(tmp);servers=[]
        command('openssl','req','-x509','-newkey','rsa:2048','-nodes',
                '-keyout',str(root/'ca.key'),'-out',str(root/'ca.pem'),'-days','1',
                '-subj','/CN=Disposable ISOBASE test CA','-addext','basicConstraints=critical,CA:TRUE')
        ca=root/'ca.pem'
        try:
            plain=Server();servers.append(plain)
            good=Server(*certificate(root,'good','IP:127.0.0.1'));servers.append(good)
            wrong=Server(*certificate(root,'wrong','DNS:wrong.invalid'));servers.append(wrong)
            expired=Server(*certificate(root,'expired','IP:127.0.0.1',-1));servers.append(expired)
            goal=lambda uri:f"rpc('{uri}',p(X)),X=ready"
            success(goal(good.uri),ca)
            error(goal(good.uri),'https_certificate_error')
            error(goal(wrong.uri),'https_certificate_error',ca)
            error(goal(expired.uri),'https_certificate_error',ca)
            error(goal(good.uri),'https_ca_file_error',root/'missing.pem')
            error(goal(plain.uri.replace('http:','https:')),'https_handshake_error',ca)
            success(goal(good.uri+'/r5'),ca)
            error(goal(good.uri+'/r6'),'http_redirect_error',ca)
            for uri in [plain.uri,good.uri]:
                error(f"rpc('{uri}/slow',p(X),[http_timeout(0.02)])",'http_timeout',ca)
                error(f"rpc('{plain.uri}',p(X),[src_uri('{uri}/slow'),http_timeout(0.02)])",'http_timeout',ca)
                error(f"rpc('{plain.uri}',p(X),[src_uri('{uri}/missing')])",'http_status_error',ca)
            # Source fetching completes before the remote request is sent.
            # Use the real node to verify compilation/execution of fetched source.
            from shared_db_tests import Node
            node=Node(ROOT/'shared-example.pl')
            try:
                target=f'http://127.0.0.1:{node.port}'
                success(f"rpc('{target}',p(X),[src_uri('{good.uri}/source')]),X=from_https",ca)
                error(f"rpc('{target}',p(X),[src_uri('{wrong.uri}/source')])",'https_certificate_error',ca)
            finally:node.close()
            # Repeated TLS rejection must not exhaust the 16 promise slots.
            success(f"findall(N,(between(1,24,N),promise('{wrong.uri}',true,R),catch(yield(R,_),error(https_certificate_error,_),true)),Ns),length(Ns,24)",ca)
        finally:
            for server in reversed(servers):server.close()
    print(f'PASS {checks} local HTTPS/source/redirect checks; temporary CA only, verification enabled')

if __name__=='__main__':main()
