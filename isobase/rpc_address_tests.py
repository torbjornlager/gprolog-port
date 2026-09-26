from outbound_test_policy import allow
"""Node address errors must precede source downloads and RPC/promise traffic."""
import http.server
import threading
from source_tests import answers

SOURCE='''
address_rpc(U,Options) :- rpc(U,true,Options).
address_promise(U,Options) :- promise(U,true,R,[template(v)|Options]),yield(R,success([v],false)).
address_rejected(U,Operation,Options) :-
    catch((call(Operation,U,Options),Outcome=accepted),
          error(domain_error(http_uri,U),_),Outcome=rejected),Outcome==rejected.
'''
class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.server.paths.append(self.path)
        if self.path.startswith('/source?'):
            body=b'available.'
        elif self.path.split('?')[0] in ['/call','/nested/call','/encoded%3F%23/call']:
            body=b'success([v],false).'
        else:
            self.send_response(404);self.end_headers();return
        self.send_response(200);self.end_headers();self.wfile.write(body)

def check(execute):
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
    server.paths=[]
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    allow(base)
    invalid=[base+s for s in ['?old=value','?','#fragment','#','/nested?x','/nested#x']]
    invalid += ['http://127.0.0.1:'+p for p in ['bad','','-1','+80','1.5','65536','99999999999999999999999']]
    invalid += ['http://','http:///path','http://:80','http://[::1]:bad',
                'http://[::1]:','http://[::1','http://user@127.0.0.1:80']
    checks=0
    try:
        for operation in ['address_rpc','address_promise']:
            for uri in invalid:
                server.paths.clear()
                execute(f"address_rejected('{uri}',{operation},[src_uri('{base}/source?name=a%2Fb')])")
                assert server.paths==[],(uri,server.paths)
                checks+=1
            for suffix in ['', '/', '/nested', '/nested/', '/encoded%3F%23']:
                server.paths.clear()
                execute(f"{operation}('{base}{suffix}',[])")
                expected=suffix.rstrip('/')+'/call?'
                assert len(server.paths)==1 and server.paths[0].startswith(expected),server.paths
                checks+=1
            # Source-resource queries keep their exact meaning.
            server.paths.clear()
            execute(f"{operation}('{base}',[src_uri('{base}/source?name=a%2Fb')])")
            assert server.paths[0]=='/source?name=a%2Fb' and len(server.paths)==2,server.paths
            checks+=1
            execute(f"{operation}('127.0.0.1':{server.server_port},[])")
            # Invalid attempts must not exhaust the 16 asynchronous request slots.
            execute(f"findall(N,(between(1,24,N),address_rejected('{base}?x',{operation},[])),Ns),length(Ns,24),{operation}('{base}',[])")
            checks+=2
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2)
    return checks

def check_node(node):
    def execute(goal):
        result=node.call(goal+',Verified=ok')
        assert result['type']=='success' and all(r['Verified']=='ok' for r in result['data']) and len(result['data'])==1,(goal,result)
    return check(execute)

def main():
    def execute(goal):
        result=answers(SOURCE,goal,'ok')
        assert result==['ok'],(goal,result)
    print(f'PASS {check(execute)} RPC/promise address, no-I/O, path and source URL checks')

if __name__=='__main__':main()
