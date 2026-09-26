from outbound_test_policy import allow
"""Real GNU/SWI HTTP interoperability plus controlled transport fault tests."""
import http.client
import http.server
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import threading
import time
import urllib.parse

ROOT=Path(__file__).resolve().parent
from comparison_config import record_run
SWI,TRINITY=record_run('rpc')

def worker(goal, template='X', source=None):
    with tempfile.NamedTemporaryFile(mode='w',suffix='.pl') as f:
        args=[os.environ.get('ISO_WORKER','./query-worker'),f'query(({goal}),{template})','100']
        if source is not None:
            f.write(source);f.flush();args+=['--source',f.name]
        p=subprocess.run(args,input='',text=True,capture_output=True,timeout=10)
        assert p.returncode==0,(p.returncode,p.stdout,p.stderr)
        return [json.loads(line) for line in p.stdout.splitlines()]

def expect(goal, answers, template='X', source=None):
    got=worker(goal,template,source)
    assert got==[{'type':'success','answers':answers,'more':False}],(goal,got)

def error(goal, contains):
    got=worker(goal)
    assert got[0]['type']=='error' and contains in got[0]['term'],(goal,got)

def get(port,goal,source=None):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=8)
    params={'goal':goal}
    if source is not None:params['src_text']=source
    c.request('GET','/call?'+urllib.parse.urlencode(params))
    r=c.getresponse();body=r.read();c.close()
    assert r.status==200,(r.status,body)
    return json.loads(body)

class Handler(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args): pass
    def do_GET(self):
        parsed=urllib.parse.urlsplit(self.path)
        query=urllib.parse.parse_qs(parsed.query)
        remote_goal=query.get('goal',[''])[0].strip('()')
        if self.path.startswith('/redirect-source'):
            self.send_response(302);self.send_header('Location','/source');self.end_headers()
            self.wfile.write(b'redirect body must not become source');return
        if self.path.startswith('/redirect-loop'):
            self.send_response(302);self.send_header('Location','/redirect-loop');self.end_headers();return
        if self.path.startswith('/redirect-file'):
            self.send_response(302);self.send_header('Location','file:///not-a-web-prolog-source');self.end_headers();return
        if self.path.startswith('/status-error'):
            self.send_response(503);self.end_headers();return
        if self.path.startswith('/slow') or remote_goal=='fixture_slow':time.sleep(.25)
        if self.path.startswith('/bad'):body=b'not_a_response.'
        elif self.path.startswith('/variable'):body=b'X.'
        elif self.path.startswith('/large'):body=b'a'*(1024*1024+1)
        elif self.path.startswith('/source'):body=b'from_uri(remote).'
        else:body=b'success([ready],false).'
        self.send_response(200);self.end_headers()
        try:self.wfile.write(body)
        except (BrokenPipeError,ConnectionResetError):pass

processes=[]
server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler)
threading.Thread(target=server.serve_forever,daemon=True).start()
fake=f'http://127.0.0.1:{server.server_port}'
allow(fake)
with tempfile.TemporaryFile(mode='w+') as log:
    try:
        sock=socket.socket();sock.bind(('127.0.0.1',0));sp=sock.getsockname()[1];sock.close()
        shared=str(ROOT/'shared-example.pl')
        start=f"node:node({sp},[profile(isobase),auth(open),ip('127.0.0.1'),load_shared_db_file('{shared}')]),thread_get_message(stop)"
        swi=subprocess.Popen([SWI,'-q','-s',str(TRINITY/'load.pl'),'-g',start],stdout=log,stderr=log);processes.append(swi)
        node_args=[os.environ.get('ISO_COMPILED_NODE','./isobase-node'),'--auth','open','--port','0','--time-ms','5000']
        if 'ISO_COMPILED_NODE' not in os.environ:node_args+=['--shared-db',shared]
        node=subprocess.Popen(node_args,stdout=subprocess.PIPE,stderr=log,text=True);processes.append(node)
        gp=json.loads(node.stdout.readline())['port']
        for _ in range(100):
            try:get(sp,'true');break
            except (OSError,http.client.HTTPException):time.sleep(.05)
        else:log.seek(0);raise AssertionError(log.read())
        gu=f'http://127.0.0.1:{gp}';su=f'http://127.0.0.1:{sp}'
        allow(gu);allow(su)
        for uri in [gu,su]:
            expect(f"rpc('{uri}',member(X,[a,b,c]),[limit(1)])",['a','b','c'])
            expect(f"rpc('{uri}',member(X,[a,b,c]),[limit(2),once(true)])",['a','b'])
            expect(f"rpc('{uri}',(X=pair(A,A),A=z))",['pair(z,z)'])
            expect(f"rpc('{uri}',(X=A,A=B)),X=z",['z'],template='B')
            expect(f"rpc('{uri}',q(X),[src_text('q(red). q(blue).'),limit(1)])",['red','blue'])
            expect(f"rpc('{uri}',q(X),[src_list([q(one),q(two)])])",['one','two'])
            expect(f"rpc('{uri}',q(X),[src_predicates([q/1,r/1]),limit(1)])",['first','second'],source='q(X):-r(X). r(first). r(second).')
            expect(f"rpc('{uri}',from_uri(X),[src_uri('{fake}/source')])",['remote'])
            expect(f"rpc('{uri}',q(X),[src_text('q(a).'),src_list([q(b)])])",['a','b'])
            expect(f"rpc('{uri}',q(X),[src_list([q(a)]),src_text('q(b).'),src_list([q(c)])])",['a','b','c'])
            expect(f"rpc('{uri}',true,[timeout(T)]),var(T),X=ok",['ok'])
            expect(f"rpc('{uri}',true,[once(O)]),X=O",['true'])
            assert worker(f"rpc('{uri}',fail)")==[{'type':'failure'}]
            zero=worker(f"rpc('{uri}',throw(should_not_run),[limit(0)])")
            assert zero==[{'type':'failure'}],('GNU' if uri==gu else 'SWI',zero)
            error(f"rpc('{uri}',throw(boom))",'boom')
            expect(f"promise('{uri}',member(X,[a,b,c]),R,[template(X),limit(1),offset(1)]),yield(R,M),M=success([Y],true)",['b'],template='Y')
            expect(f"promise('{uri}',fail,R),yield(R,M)",['failure'],template='M')
            expect(f"promise('{uri}',throw(boom),R),yield(R,M)",['error(boom)'],template='M')
        # Unicode src_text lists must represent code points/characters, not bytes.
        for uri in [gu,su]:
            for conversion in ['atom_codes','atom_chars']:
                expect(f"{conversion}('label(\\'東京😀\\').',Text),rpc('{uri}',label(A),[src_text(Text)]),atom_codes(A,X)",
                       ["'.'(26481,'.'(20140,'.'(128512,[])))"])
            expect(f"rpc('{uri}',from_uri(X),[src_uri('{fake}/redirect-source')])",['remote'])
        # Stable state-machine outcomes compared on both calling runtimes.
        promise_cases=[
            ("(yield(123,M)->Out=bad;Out=missing)",'missing'),
            ("yield(123,_,[on_timeout(Out=missing)])",'missing'),
            (f"promise('{gu}',true,R),yield(R,success([true],false)),yield(R,_,[on_timeout(Out=gone)])",'gone'),
            (f"promise('{gu}',fail,R),yield(R,failure),Out=ok",'ok'),
            (f"promise('{gu}',throw(ball),R),yield(R,error(ball)),Out=ok",'ok'),
            (f"promise('{gu}',true,R),findall(M,yield(R,M),Ms),Ms=[success([true],false)],Out=once",'once'),
            (f"promise('{fake}',fixture_slow,R),yield(R,M,[timeout(0),on_timeout(Out=timeout)]),var(M),yield(R,success([ready],false))",'timeout'),
            (f"promise('{fake}',fixture_slow,R),(yield(R,_,[timeout(0),on_timeout(fail)])->fail;true),yield(R,success([ready],false)),Out=retained",'retained'),
            (f"promise('{fake}',fixture_slow,R),catch(yield(R,_,[timeout(0),on_timeout(throw(ball))]),ball,true),yield(R,success([ready],false)),Out=retained",'retained'),
            (f"promise('{gu}',X=a,R,[template(X)]),var(X),yield(R,success([Y],false)),Y=a,var(X),Out=isolated",'isolated'),
        ]
        for goal,expected in promise_cases:
            for caller in [gp,sp]:
                result=get(caller,goal)
                assert result['type']=='success' and result['data'][0]['Out']==expected,(caller,goal,result)
        print(f'PASS {len(promise_cases)} promise state cases on GNU and SWI')
        # SWI's client drives GNU's server, including native remote pagination.
        for goal in [
            f"findall(X,rpc('{gu}',member(X,[a,b,c])),[a,b,c])",
            f"promise('{gu}',true,R),yield(R,success([true],false))",
            f"findall(X,rpc('{gu}',member(X,[a,b,c]),[limit(1)]),[a,b,c])",
            f"findall(X,rpc('{gu}',q(X),[src_text(\"q(a). q(b).\"),limit(1)]),[a,b])",
            f"promise('{gu}',member(X,[a,b,c]),R,[template(X),limit(1),offset(1)]),yield(R,success([b],true))",
        ]:
            result=get(sp,goal);assert result['type']=='success', (goal,result)
        result=get(sp,f"findall(X,rpc('{gu}',q(X),[src_predicates([q/1]),limit(1)]),Xs)",'q(a). q(b).')
        assert result['type']=='success' and result['data'][0]['Xs']=='[a,b]',result
        result=get(sp,f"findall(X,rpc('{gu}',q(X),[src_list([q([a,b]),q([c])])]),Xs)")
        assert result['type']=='success' and result['data'][0]['Xs']=='[[a,b],[c]]',result
        # Through HTTP workers in both directions, not only standalone worker.
        for caller,remote in [(gp,su),(sp,gu),(gp,gu)]:
            result=get(caller,f"findall(X,rpc('{remote}',member(X,[a,b,c]),[limit(1)]),Xs)")
            assert result['type']=='success' and result['data'][0]['Xs']=='[a,b,c]',result
        # Shared wrappers retain their context for timeout callbacks too.
        result=get(gp,f"promise('{fake}/slow',true,R),yield(R,_,[timeout(0),on_timeout(price(widget,X))])",'list_price(widget,999).')
        assert result['type']=='success' and result['data'][0]['X']=='100',result
        # Yield timeout retains reference; callback remains behind local policy.
        expect(f"promise('{fake}/slow',true,R),yield(R,M,[timeout(0),on_timeout(X=timed_out)]),var(M),yield(R,success([ready],false))",['timed_out'])
        expect(f"promise('{fake}/slow',true,R),yield(R,_,[timeout(0)]),yield(R,success([X],false))",['ready'])
        error(f"promise('{fake}/slow',true,R),yield(R,_,[timeout(0),on_timeout(open('/tmp/no',write,S))])",'permission_error')
        expect(f"promise('{fake}',true,R),yield(R,_),yield(R,_,[on_timeout(X=gone)])",['gone'])
        expect(f"promise('{fake}/slow',true,R),promise_cleanup(R),yield(R,_,[on_timeout(X=gone)])",['gone'])
        # A mismatching result still consumes a received response.
        expect(f"promise('{fake}',true,R),(yield(R,wrong,[])->fail;true),yield(R,_,[on_timeout(X=gone)])",['gone'])
        error(f"rpc('{fake}/slow',true,[http_timeout(0.01)])",'http_timeout')
        error(f"rpc('{fake}/bad',true)",'remote_protocol_error')
        error(f"rpc('{fake}/variable',true)",'remote_protocol_error')
        error(f"rpc('{fake}/large',true)",'response_too_large')
        error(f"rpc('{fake}/status-error',true)",'http_status_error')
        error(f"rpc('{fake}/redirect-loop',true)",'http_redirect_error')
        error(f"rpc('{fake}/redirect-file',true)",'http_transport_error')
        # Transport errors and malformed replies must free the promise slot.
        for path,kind in [('status-error','http_status_error'),('bad','remote_protocol_error')]:
            expect(f"findall(N,(between(1,24,N),promise('{fake}/{path}',true,R),catch(yield(R,_),error({kind},_),true),yield(R,_,[on_timeout(true)])),Ns),length(Ns,X)",['24'])
        error("rpc('file:///etc/passwd',true)",'http_uri')
        error(f"rpc('{gu}',true,[once(maybe)])",'boolean')
        error(f"rpc('{gu}',true,[limit(-1)])",'request_range')
        got=worker('true',source='rpc(a,b).')
        assert got[0]['type']=='error' and 'redefine' in got[0]['term'],got
        error(f"rpc('{gu}',true,[src_predicates([human/1])])",'permission_error')
        error(f"findall(R,(between(1,17,_),promise('{fake}/slow',true,R)),_)",'promise_limit_exceeded')
        # Cyclic templates/options are rejected before starting a transfer.
        error(f"T=f(T),promise('{fake}',true,R,[template(T)])",'representation_error(cyclic_term)')
        expect(f"T=f(T),catch(promise('{fake}',true,R,[template(T)]),error(representation_error(cyclic_term),_),X=handled)",['handled'])
        result=get(gp,"T=f(T),throw(T)")
        assert result['type']=='error' and 'cyclic_term' in str(result),result
        error("T=f(T),throw(T)",'representation_error(cyclic_term)')
        # yield/2 keeps waiting on a nonmatching message; supervisor cancels it.
        q=subprocess.Popen(['./query-supervisor',f"query((promise('{fake}',true,R),yield(R,wrong)),ok)",'1','--time-ms','400'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        message=json.loads(q.stdout.readline());q.wait(timeout=3)
        assert message=={'type':'error','term':'time_limit_exceeded'},message
        # IO overlaps: both requests have time to finish during the first wait.
        expect(f"promise('{fake}/slow',true,A),promise('{fake}/slow',true,B),yield(A,_),yield(B,success([X],false),[timeout(0.1),on_timeout(fail)])",['ready'])
        expect(f"promise('{fake}',true,R),integer(R),R>=1000000000,R=<9999999999,yield(R,success([X],false))",['ready'])
        # Repeated completion returns slots to the pool.
        expect(f"findall(X,(between(1,40,X),promise('{fake}',true,R),yield(R,_)),Xs),length(Xs,N)",['40'],template='N')
        print('PASS RPC GNU→GNU, GNU→SWI, SWI→GNU; source transfer, pagination, promises, timeouts, cleanup and policy')
    finally:
        for p in processes:p.terminate()
        for p in processes:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
        server.shutdown();server.server_close()
