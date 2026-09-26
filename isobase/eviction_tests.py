"""Check insertion-order eviction, worker reaping and active-query protection."""
import concurrent.futures
import http.client
import json
import os
import select
import subprocess
import time
import urllib.parse

node=subprocess.Popen([os.environ.get('ISO_NODE','./isobase-node'),'--auth','open','--port','0',
    '--max-queries','2','--time-ms','2000','--idle-ms','5000'],
    stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
    assert select.select([node.stdout],[],[],3)[0]
    port=json.loads(node.stdout.readline())['port']
    def call(goal,**params):
        c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        c.request('GET','/call?'+urllib.parse.urlencode(dict(goal=goal,**params)))
        r=c.getresponse();body=json.loads(r.read());c.close();return r.status,body
    def processes():
        return {int(pid):int(parent) for pid,parent in
            (line.split() for line in subprocess.check_output(['ps','-axo','pid=,ppid='],text=True).splitlines())}
    def children():return {pid for pid,parent in processes().items() if parent==node.pid}
    def page(name,offset=0):
        status,body=call(f'between(1,9,{name})',offset=offset,limit=1)
        assert status==200 and body['data']==[{name:str(offset+1)}] and body['more'],body
    page('A');a=children();assert len(a)==1
    workers_a={pid for pid,parent in processes().items() if parent in a};assert len(workers_a)==1
    page('B');b=children()-a;assert len(b)==1
    # Evict the first cached entry, including its worker; preserve B.
    page('C');current=children();assert len(current)==2 and b<=current and not(a&current)
    assert not ((a|workers_a)&processes().keys()),'evicted processes survived'
    c=current-b
    # A cache hit keeps its supervisor, but refreshes insertion order.
    page('B',1);assert children()==current
    page('D');assert b<=children() and not(c&children()),'recached B was not newest'
    # A's evicted continuation is recreated and skips to the requested offset.
    page('A',1);assert not(a&children())
    # Drain cached entries so two active requests own all capacity.
    call('between(1,9,A)',offset=2,limit=20)
    call('between(1,9,D)',offset=1,limit=20)
    assert not children()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        first=pool.submit(call,'repeat,fail')
        second=pool.submit(call,'repeat,fail')
        deadline=time.monotonic()+1
        while len(children())<2 and time.monotonic()<deadline:time.sleep(.01)
        active=children();assert len(active)==2
        status,body=call('true')
        assert status==503 and body['type']=='error',(status,body)
        assert children()==active,'an active computation was evicted'
        assert first.result()[1]['type']=='error'
        assert second.result()[1]['type']=='error'
    assert call('true')[0]==200 and not children()
    # With one active and one cached query, only the cached one is evicted.
    with concurrent.futures.ThreadPoolExecutor() as pool:
        running=pool.submit(call,'repeat,fail')
        deadline=time.monotonic()+1
        while not children() and time.monotonic()<deadline:time.sleep(.01)
        active=children();assert len(active)==1
        page('E');cached=children()-active
        page('F');assert active<=children() and not(cached&children())
        assert running.result()[1]['type']=='error'
    print('PASS eviction: oldest idle first, reinsertion order, offset replay, process cleanup and active-query protection')
finally:
    node.terminate()
    try:node.wait(timeout=5)
    except subprocess.TimeoutExpired:node.kill();node.wait();raise
    assert node.returncode==0,(node.returncode,node.stderr.read())
    assert not node.stderr.read()
