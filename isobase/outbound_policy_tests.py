"""S01 real forbidden fixtures, exact pins, proxy/redirect isolation and fail-closed policy."""
import http.client
import urllib.parse
import select
import http.server
import json
import os
from pathlib import Path
import socket
import subprocess
import tempfile
import threading

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.server.requests.append((self.path,self.headers.get('Host')))
        if self.path.startswith('/redirect'):
            self.send_response(302);self.send_header('Location',self.server.redirect);self.end_headers();return
        body=b'p(ok).' if self.path.startswith('/source') else b'success([v],false).'
        self.send_response(200);self.end_headers();self.wfile.write(body)
class Server:
    def __init__(self,ipv6=False):
        class HTTP(http.server.ThreadingHTTPServer):address_family=socket.AF_INET6 if ipv6 else socket.AF_INET
        self.server=HTTP(('::1' if ipv6 else '127.0.0.1',0),Handler)
        self.server.requests=[];self.server.redirect='';self.port=self.server.server_port
        self.uri=f'http://[::1]:{self.port}' if ipv6 else f'http://127.0.0.1:{self.port}'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def close(self):self.server.shutdown();self.server.server_close();self.thread.join()

def main():
    allowed,denied,proxy=Server(),Server(),Server();checks=0
    try:
        with tempfile.TemporaryDirectory(prefix='outbound-security-') as tmp:
            policy=Path(tmp)/'policy';policy.touch(mode=0o600)
            env=dict(os.environ,ISO_OUTBOUND_POLICY=str(policy))
            # Deliberately point all ambient proxies at a forbidden fixture.
            for name in ['http_proxy','HTTP_PROXY','https_proxy','HTTPS_PROXY','ALL_PROXY','all_proxy']:
                env[name]=proxy.uri
            env['NO_PROXY']=env['no_proxy']=''
            def write(text):policy.write_text(text);policy.chmod(0o600)
            def rule(host='127.0.0.1',ip='127.0.0.1',port=None):
                return f'http {host} {port or allowed.port} {ip}\n'
            def run(goal,configuration=env):
                nonlocal checks
                p=subprocess.run([os.environ.get('ISO_WORKER','./query-worker'),f'query(({goal}),ok)','1'],input='',text=True,capture_output=True,env=configuration,timeout=6)
                got=[json.loads(line) for line in p.stdout.splitlines()]
                assert p.returncode==0 and got==[{'type':'success','answers':['ok'],'more':False}],(goal,p.returncode,got,p.stderr)
                checks+=1
            def error(goal,kind='outbound_denied',configuration=env):
                run(f'catch(({goal},Caught=no),error({kind},_),Caught=yes),Caught==yes',configuration)
            def operations(uri):
                return [f"rpc('{uri}',true)",f"promise('{uri}',true,R,[template(v)]),yield(R,success([v],false))",
                        f"rpc('{allowed.uri}',true,[src_uri('{uri}/source')])"]
            write(rule())
            for goal in operations(allowed.uri):run(goal)
            # Approved names are pinned even when they cannot resolve in DNS.
            write(rule()+rule('peer.invalid'))
            run(f"rpc('http://peer.invalid:{allowed.port}',true)")
            assert allowed.server.requests[-1][1]==f'peer.invalid:{allowed.port}'
            for uri in [denied.uri,f'http://localhost:{allowed.port}',
                        f'https://127.0.0.1:{allowed.port}','http://169.254.169.254',
                        'http://10.0.0.1','http://[fd00::1]','http://[::ffff:127.0.0.1]',
                        f'http://2130706433:{denied.port}',f'http://0x7f000001:{denied.port}']:
                for goal in operations(uri):error(goal)
            assert denied.server.requests==[] and proxy.server.requests==[]
            # An alternative numeric spelling can only reach its approved canonical endpoint.
            run(f"rpc('http://2130706433:{allowed.port}',true)")
            # No policy, unreadable/missing, malformed, overly broad or unsafe files fail closed.
            no_policy=dict(env);no_policy.pop('ISO_OUTBOUND_POLICY')
            error(f"rpc('{allowed.uri}',true)",configuration=no_policy)
            for text in ['',rule()+'garbage\n',rule('*'),rule(':'),rule(ip='localhost'),rule()+rule(),rule(ip='::ffff:127.0.0.1')]:
                write(text);error(f"rpc('{allowed.uri}',true)",'outbound_denied' if not text else 'outbound_policy_invalid')
            write(rule());policy.chmod(0o644);error(f"rpc('{allowed.uri}',true)",'outbound_policy_invalid')
            policy.unlink();error(f"rpc('{allowed.uri}',true)",'outbound_policy_invalid')
            target=Path(tmp)/'target';target.write_text(rule());target.chmod(0o600);policy.symlink_to(target)
            error(f"rpc('{allowed.uri}',true)",'outbound_policy_invalid');policy.unlink();write(rule())
            # All redirects are blocked, including same-origin and source redirects.
            for location in [denied.uri+'/call',allowed.uri+'/call','/call','file:///etc/passwd']:
                allowed.server.redirect=location
                for goal in operations(allowed.uri+'/redirect'):error(goal,'http_redirect_denied')
            assert denied.server.requests==[] and proxy.server.requests==[]
            error(f"rpc('{allowed.uri}',true,[src_uri('{denied.uri}/source')])")
            run(f"findall(N,(between(1,24,N),catch(promise('{denied.uri}',true,_),error(outbound_denied,_),true)),Ns),length(Ns,24),rpc('{allowed.uri}',true)")
            # Policy changes are observed on the next transfer in the same worker.
            # Each already-started transfer retains its original immutable pin.
            write(rule())
            worker=subprocess.Popen([os.environ.get('ISO_WORKER','./query-worker'),
                f"query((between(1,4,X),rpc('{allowed.uri}',true)),X)",'1'],
                stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=env)
            try:
                assert select.select([worker.stdout],[],[],5)[0]
                assert json.loads(worker.stdout.readline())['answers']==['1']
                before=len(allowed.server.requests)
                write('')
                # Paging may have already prefetched one approved answer.
                for _ in range(3):
                    worker.stdin.write('next\n');worker.stdin.flush()
                    assert select.select([worker.stdout],[],[],5)[0]
                    event=json.loads(worker.stdout.readline())
                    if event['type']=='error':break
                assert event['type']=='error' and 'outbound_denied' in event['term'],event
                assert len(allowed.server.requests)==before
                checks+=1
            finally:
                worker.terminate();worker.wait(timeout=5)
            # The controller flag reaches the worker, and clients cannot select a policy.
            write(rule())
            for configured in [False,True]:
                node_env=dict(env);node_env.pop('ISO_OUTBOUND_POLICY',None)
                argv=[os.environ.get('ISO_NODE','./isobase-node'),'--auth','open','--port','0']
                if configured:argv+=['--outbound-policy',str(policy)]
                node=subprocess.Popen(argv,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True,env=node_env)
                try:
                    assert select.select([node.stdout],[],[],5)[0]
                    port=json.loads(node.stdout.readline())['port']
                    goal=f"rpc('{allowed.uri}',true)"
                    if not configured:goal=f'catch(({goal},C=no),error(outbound_denied,_),C=yes),C==yes'
                    connection=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                    connection.request('GET','/call?'+urllib.parse.urlencode(dict(goal=goal,template='ok',format='prolog')))
                    response=connection.getresponse();body=response.read().decode().strip();connection.close()
                    assert response.status==200 and body=='success([ok],false).',body
                    checks+=1
                finally:
                    node.terminate();node.wait(timeout=5)
            ipv6=Server(ipv6=True)
            try:
                write(rule()+f'http [::1] {ipv6.port} ::1\n')
                run(f"rpc('{ipv6.uri}',true)")
                write(rule());error(f"rpc('{ipv6.uri}',true)")
                assert len(ipv6.server.requests)==1
            finally:ipv6.close()
            assert denied.server.requests==[] and proxy.server.requests==[]
            print(f'PASS {checks} outbound policy checks; forbidden and proxy fixtures received zero requests')
    finally:
        for server in [allowed,denied,proxy]:server.close()

if __name__=='__main__':main()
