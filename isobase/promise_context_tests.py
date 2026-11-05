"""GNU request/root promise ownership and retirement with controlled HTTP peers."""
import argparse
import http.client
import http.server
import json
import os
from pathlib import Path
import re
import secrets
import select
import socket
import subprocess
import tempfile
import threading
import time
from urllib.parse import urlencode
from outbound_test_policy import allow

ROOT=Path(__file__).resolve().parent
NODE=Path(os.environ.get('ISO_NODE',ROOT/'isobase-node')).resolve()
WORKER=Path(os.environ.get('ISO_WORKER',ROOT/'query-worker')).resolve()
ROWS=[]

def wait_for(predicate,label,seconds=5):
    end=time.monotonic()+seconds
    while not predicate():
        assert time.monotonic()<end,label
        time.sleep(.01)

def check(id,title,operation):
    row=dict(candidate='gnu',id=id,title=title)
    try:row.update(status='pass',observation=operation())
    except Exception as e:row.update(status='fail',detail=str(e))
    ROWS.append(row);print(id,row['status'],*( [row['detail']] if row.get('detail') else []),flush=True)

class Gate:
    def __init__(self):
        self.arrived=threading.Event();self.release=threading.Event();self.closed=threading.Event();self.attempted=threading.Event();self.count=0

class Peer:
    def __init__(self):
        self.gates={};self.lock=threading.Lock();fixture=self
        class Handler(http.server.BaseHTTPRequestHandler):
            def log_message(self,*args):pass
            def do_GET(self):
                key=self.path.split('?')[0].split('/')[2]
                if self.path.startswith('/hold/'):
                    gate=fixture.gate(key);gate.count+=1;gate.arrived.set();end=time.monotonic()+15
                    while not gate.release.wait(.01):
                        if select.select([self.connection],[],[],0)[0]:
                            try:
                                if self.connection.recv(1,socket.MSG_PEEK)==b'':gate.closed.set()
                            except (ConnectionResetError,OSError):gate.closed.set()
                        if time.monotonic()>end:return
                    gate.attempted.set();value='first'
                else:value=key
                body=('success(['+value+'],false).\n').encode()
                try:
                    self.send_response(200);self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body);self.wfile.flush()
                except (BrokenPipeError,ConnectionResetError):pass
        self.server=http.server.ThreadingHTTPServer(('127.0.0.1',0),Handler);self.server.daemon_threads=True
        self.url=f'http://127.0.0.1:{self.server.server_port}';allow(self.url)
        self.thread=threading.Thread(target=self.server.serve_forever,daemon=True);self.thread.start()
    def gate(self,key):
        with self.lock:return self.gates.setdefault(key,Gate())
    def close(self):
        for gate in self.gates.values():gate.release.set()
        self.server.shutdown();self.server.server_close();self.thread.join()

class Node:
    def __init__(self,private=False,idle=10000):
        self.tmp=tempfile.TemporaryDirectory(prefix='gnu-context-');self.token=None
        command=[str(NODE),'--port','0','--max-queries','8','--time-ms','5000','--idle-ms',str(idle)]
        if private:
            token=Path(self.tmp.name)/'token';self.token=secrets.token_hex(32)
            fd=os.open(token,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,'w') as f:f.write(self.token+'\n')
            command+=['--auth-token-file',str(token)]
        else:command+=['--auth','open']
        self.process=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        assert select.select([self.process.stdout],[],[],5)[0],'node readiness'
        self.port=json.loads(self.process.stdout.readline())['port']
    def call(self,goal,template='ok',owner=None,offset=0,limit=10):
        headers={}
        if self.token:headers['Authorization']='Bearer '+self.token
        if owner:headers['X-Web-Prolog-Query-Owner']=owner
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=8)
        c.request('GET','/call?'+urlencode(dict(goal=goal,template=template,format='prolog',offset=offset,limit=limit)),headers=headers)
        r=c.getresponse();body=r.read().decode();status=r.status;c.close();assert status==200,(status,body)
        return ''.join(body.split())
    def descendants(self):
        rows=[tuple(map(int,line.split())) for line in subprocess.check_output(['ps','-axo','pid=,ppid='],text=True).splitlines()]
        seen={self.process.pid}
        while True:
            more={pid for pid,parent in rows if parent in seen};new=seen|more
            if new==seen:return seen-{self.process.pid}
            seen=new
    def close(self):
        self.process.terminate();assert self.process.wait(timeout=5)==0,self.process.stderr.read();self.tmp.cleanup()

def missing(ref):return f'catch((yield({ref},_)->Access=granted;Access=denied),_,Access=denied),Access==denied'
def held_goal(uri):return f"promise('{uri}',true,R,[template(first)]),member(Phase,[created,barrier,collect]),(Phase==collect->yield(R,A);A=Phase)"
def created(node,goal,owner):
    body=node.call(goal,'v(R,A)',owner,limit=1)
    match=re.fullmatch(r'success\(\[v\((\d+),created\)\],true\)\.',body);assert match,body
    return match[1],body

def http_isolation(peer,private):
    node=Node(private);owner=secrets.token_hex(32);key='private' if private else 'anonymous';gate=peer.gate(key)
    goal=held_goal(peer.url+'/hold/'+key)
    try:
        ref,first=created(node,goal,owner);assert gate.arrived.wait(5),'producer arrival'
        original=node.descendants();assert original,'retained query has an execution process'
        denied=node.call(missing(ref));assert denied=='success([ok],false).',denied
        cleaned=node.call(f'promise_cleanup({ref})');assert cleaned=='success([ok],false).',cleaned
        # Equal numeric references in a different worker identify only its own answer.
        own=node.call(f"promise('{peer.url}/fast/second',true,Local,[template(second)]),yield(Local,success([second],false))",'Local')
        local=re.fullmatch(r'success\(\[(\d+)\],false\)\.',own);assert local,own
        gate.release.set()
        collected=node.call(goal,'v(R,A)',owner,offset=1,limit=2)
        assert collected==f'success([v({ref},barrier),v({ref},success([first],false))],false).',collected
        assert gate.count==1,'continuation must resume the original worker without restarting its promise'
        wait_for(lambda:not node.descendants(),'all owned execution processes reaped')
        assert gate.count==1,'one request from retained origin'
        return dict(auth='same bearer' if private else 'anonymous',reference=ref,first=first,foreign_denial=denied,foreign_cleanup=cleaned,foreign_own_answer=own,numeric_reference_collision=(local[1]==ref),origin_collection=collected,origin_requests=gate.count,execution_processes_reaped=True)
    finally:gate.release.set();node.close()

def retirement(peer,idle):
    node=Node(idle=idle);owner=secrets.token_hex(32);key='retire';gate=peer.gate(key)
    goal=held_goal(peer.url+'/hold/'+key)
    try:
        ref,first=created(node,goal,owner);assert gate.arrived.wait(5),'producer arrival'
        wait_for(lambda:not node.descendants(),'idle context execution processes reaped')
        assert gate.closed.wait(5),'retirement closes the producer connection before release'
        gate.release.set();assert gate.attempted.wait(5),'forced late producer response'
        denied=node.call(missing(ref));assert denied=='success([ok],false).',denied
        recovered=node.call('true');assert recovered=='success([ok],false).',recovered
        wait_for(lambda:not node.descendants(),'post-retirement capacity recovered')
        return dict(reference=ref,first=first,peer_closed_before_release=True,late_response_attempted=True,fresh_request_denied=denied,capacity_recovered=True)
    finally:gate.release.set();node.close()

def remote_forwarding(peer):
    origin=Node();remote=Node();owner=secrets.token_hex(32);gate=peer.gate('remote')
    uri=f'http://127.0.0.1:{remote.port}';allow(uri)
    goal=held_goal(peer.url+'/hold/remote')
    try:
        ref,first=created(origin,goal,owner);assert gate.arrived.wait(5),'remote test origin arrival'
        denied=origin.call(f"\\+rpc('{uri}',yield({ref},_))");assert denied=='success([ok],false).',denied
        cleaned=origin.call(f"rpc('{uri}',promise_cleanup({ref}))");assert cleaned=='success([ok],false).',cleaned
        gate.release.set();collected=origin.call(goal,'v(R,A)',owner,offset=1,limit=2)
        assert collected==f'success([v({ref},barrier),v({ref},success([first],false))],false).',collected
        assert gate.count==1
        wait_for(lambda:not origin.descendants() and not remote.descendants(),'both nodes reclaim completed execution processes')
        return dict(reference=ref,remote_collection_denied=denied,remote_cleanup_harmless=cleaned,origin_collection=collected,origin_requests=gate.count)
    finally:gate.release.set();origin.close();remote.close()


def standalone(peer,cleanup):
    key='root-cleanup' if cleanup else 'root-stop';gate=peer.gate(key)
    if cleanup:
        goal=f"promise('{peer.url}/hold/{key}',true,R,[template(first)]),(X=created;X=barrier;(promise_cleanup(R),promise('{peer.url}/fast/second',true,S,[template(second)]),yield(S,success([second],false)),X=collected))"
    else:goal=held_goal(peer.url+'/hold/'+key);goal=f'({goal}),X=A'
    p=subprocess.Popen([str(WORKER),f'query(({goal}),X)','1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert select.select([p.stdout],[],[],5)[0],'root first page'
        first=json.loads(p.stdout.readline());assert first==dict(type='success',answers=['created'],more=True),first
        assert gate.arrived.wait(5),'root producer arrival'
        p.stdin.write('next 10\n' if cleanup else 'stop\n');p.stdin.flush()
        if cleanup:
            assert select.select([p.stdout],[],[],5)[0],'root cleanup continuation'
            after=json.loads(p.stdout.readline());assert after==dict(type='success',answers=['barrier','collected'],more=False),after
        assert p.wait(timeout=5)==0,p.stderr.read()
        assert gate.closed.wait(5),'root retirement/cleanup closes pending transport'
        gate.release.set();assert gate.attempted.wait(5),'root late completion attempted'
        return dict(first=first,explicit_cleanup=cleanup,transport_closed_before_late_response=True,exit_code=p.returncode)
    finally:
        gate.release.set()
        if p.poll() is None:p.kill();p.wait()
        p.stdin.close()


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('--report',type=Path);args=parser.parse_args()
    peer=Peer()
    try:
        check('GCTX-001','Anonymous fresh requests cannot collect/dispose retained-context promises',lambda:http_isolation(peer,False))
        check('GCTX-002','Equal authentication alone does not retain ownership across HTTP requests',lambda:http_isolation(peer,True))
        check('GCTX-003','Idle request retirement closes pending transport before forced late completion',lambda:retirement(peer,200))
        check('GCTX-004','Standalone root stop retires pending transport',lambda:standalone(peer,False))
        check('GCTX-005','Standalone root cleanup preserves a later promise and retires the old transport',lambda:standalone(peer,True))
        check('GCTX-006','Forwarding a reference through real RPC grants no access at another GNU node',lambda:remote_forwarding(peer))
    finally:peer.close()
    if args.report:args.report.write_text(json.dumps(dict(suite='gnu-promise-context-0.1',results=ROWS,counts={s:sum(r['status']==s for r in ROWS) for s in ['pass','fail']}),indent=2)+'\n')
    return int(any(r['status']!='pass' for r in ROWS))
if __name__=='__main__':raise SystemExit(main())
