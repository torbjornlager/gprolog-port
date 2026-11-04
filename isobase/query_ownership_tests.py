"""Two independent owners must not consume or evict each other's live workers."""
import concurrent.futures
import http.client
import json
import os
import select
import subprocess
import time
from urllib.parse import urlencode

node = subprocess.Popen([os.environ.get('ISO_NODE', './isobase-node'), '--auth', 'open',
                         '--port', '0', '--max-queries', '4', '--max-owner-queries', '2',
                         '--require-query-owner', '1', '--require-query-budget', '1', '--max-budget-queries', '2', '--time-ms', '800', '--idle-ms', '8000'],
                        stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
try:
    assert select.select([node.stdout], [], [], 5)[0]
    port = json.loads(node.stdout.readline())['port']
    def call(owner, goal='between(1,20,X)', offset=0, limit=1, budget=None):
        headers = {} if owner is None else {'X-Web-Prolog-Query-Owner': owner, 'X-Web-Prolog-Query-Budget': budget if budget is not None else owner}
        c = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
        c.request('GET', '/call?' + urlencode(dict(goal=goal,offset=offset,limit=limit)),headers=headers)
        r = c.getresponse(); result = r.status,json.loads(r.read());c.close();return result
    def children():
        rows = subprocess.check_output(['ps','-axo','pid=,ppid='],text=True)
        return {int(pid) for pid,parent in (r.split() for r in rows.splitlines()) if int(parent)==node.pid}
    A,B='a'*64,'b'*64
    assert call(A)[1]['type']=='success';a=children();assert len(a)==1
    assert call(B,offset=1)[1]['type']=='success';b=children()-a;assert len(b)==1
    assert call(A,offset=1)[1]['type']=='success' and children()==a|b
    assert call(None)[0]==400 and children()==a|b
    assert call('forged')[0]==400 and children()==a|b
    # Fill the owner's quota, then replace its oldest idle worker, preserving B.
    call(A,'between(100,120,X)');assert len(children())==3
    call(A,'between(200,220,X)');assert b<=children() and not(a&children()) and len(children())==3
    assert call('c'*64,'true',budget=A)[0]==503 and b<=children()
    assert call(B,offset=2)[1]['type']=='success' and b<=children()
    # Drain all cached work before the active-capacity checks.
    call(A,'between(100,120,X)',1,100)
    call(A,'between(200,220,X)',1,100)
    call(B,offset=3,limit=100)
    assert not children()
    with concurrent.futures.ThreadPoolExecutor() as pool:
        jobs=[pool.submit(call,A,'repeat,fail') for _ in range(2)]
        end=time.monotonic()+2
        while len(children())<2 and time.monotonic()<end:time.sleep(.01)
        assert len(children())==2
        assert call(A,'true')[0]==503
        assert call(B,'true')[0]==200
        assert all(job.result()[1]['type']=='error' for job in jobs)
    assert call(A,'true')[0]==200 and not children()
    print('PASS query ownership: separate continuations, owner-only eviction, required/malformed identity, quota fairness, deadline recovery')
finally:
    node.terminate()
    try:node.wait(timeout=5)
    except subprocess.TimeoutExpired:node.kill();node.wait();raise
    assert node.returncode==0,(node.returncode,node.stderr.read())
