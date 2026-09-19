"""Exact source URLs, ordered failures and transport-slot recovery on local HTTP."""
import http.server
import json
import os
import subprocess
import threading
import time

class SourceHandler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        self.server.paths.append(self.path)
        if self.path == '/slow': time.sleep(.2)
        sources={'/source/':b'p(slash).', '/source%20name':b'p(encoded).',
                 '/source?name=a%2Fb':b'p(query).', '/a':b'p(a).', '/b':b'p(b).',
                 '/slow':b'p(slow).'}
        body=sources.get(self.path)
        if self.path.startswith('/call?'): body=b'success([v],false).'
        if self.path == '/large': body=b' '*(1024*1024+1)
        if self.path == '/nul': body=b'p(a).\x00'
        self.send_response(200 if body is not None else 404);self.end_headers()
        try:self.wfile.write(body or b'')
        except (BrokenPipeError,ConnectionResetError):pass

class SourceServer:
    def __init__(self):
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),SourceHandler)
        self.server.daemon_threads=True;self.server.paths=[]
        self.uri=f'http://127.0.0.1:{self.server.server_port}'
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True)
        self.thread.start()
    def close(self):
        self.server.shutdown();self.server.server_close();self.thread.join(timeout=2)

def run(goal):
    result=subprocess.run([os.environ.get('ISO_WORKER','./query-worker'),f'query(({goal}),ok)','1'],
                          input='',text=True,capture_output=True,timeout=10)
    assert result.returncode==0,(result.stdout,result.stderr)
    got=[json.loads(line) for line in result.stdout.splitlines()]
    assert got==[{'type':'success','answers':['ok'],'more':False}],(goal,got)

def main():
    fixture=SourceServer();checks=0
    try:
        u=fixture.uri
        for path,kind in [('missing','http_status_error'),('slow','http_timeout'),
                          ('large','response_too_large_or_invalid'),('nul','response_too_large_or_invalid')]:
            deadline=0.02 if path=='slow' else 2
            fixture.server.paths.clear()
            # A failed middle source stops composition before /b and the final RPC.
            run(f"catch(rpc('{u}',true,[src_uri('{u}/a'),src_uri('{u}/{path}'),src_uri('{u}/b'),http_timeout({deadline})]),error({kind},_),Caught=yes),Caught==yes")
            assert fixture.server.paths==['/a','/'+path],fixture.server.paths
            checks+=1
            # All failures happen within one worker, exceeding its 16 transport slots.
            run(f"findall(N,(between(1,24,N),catch(rpc('{u}',true,[src_uri('{u}/{path}'),http_timeout({deadline})]),error({kind},_),Caught=yes),Caught==yes),Ns),length(Ns,24),rpc('{u}',true)")
            checks+=1
        # Remote-timeout validation must precede source I/O; transport-timeout
        # validation must occur before the first download using that deadline.
        for options,kind in [
            (f"timeout(bad),src_uri('{u}/a')",'type_error(number,bad)'),
            (f"src_uri('{u}/a'),http_timeout(none)",'type_error(number,none)'),
            (f"src_uri('{u}/a'),http_timeout(301)",'domain_error(timeout,301)'),
        ]:
            fixture.server.paths.clear()
            run(f"catch(rpc('{u}',true,[{options}]),error({kind},_),Caught=yes),Caught==yes")
            assert fixture.server.paths==[],fixture.server.paths
            checks+=1
        print(f'PASS {checks} source failure/order/slot recovery checks')
    finally:fixture.close()

if __name__=='__main__':main()
