"""Repeated concurrent source isolation and continuation cleanup, local only."""
import concurrent.futures
import http.client
import json
import os
import subprocess
import time
import urllib.parse

exe=os.environ.get('ISO_COMPILED_NODE','./isobase-node')
args=[exe,'--auth','open','--port','0','--max-queries','8','--idle-ms','500','--time-ms','2000']
if 'ISO_COMPILED_NODE' not in os.environ:args+=['--shared-db','shared-example.pl']
node=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
    port=json.loads(node.stdout.readline())['port']
    def call(params):
        c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
        c.request('GET','/call?'+urllib.parse.urlencode(params))
        r=c.getresponse();body=json.loads(r.read());c.close()
        assert r.status==200,(r.status,body)
        return body
    def work(client):
        for iteration in range(50):
            token=f'client{client}_round{iteration}'
            params=dict(goal='local(X),price(widget,P)',src_text=f'local({token}). local(done). list_price(widget,999).',limit=1)
            assert call(params)=={'type':'success','data':[{'X':token,'P':'100'}],'more':True}
            params.update(offset=1)
            assert call(params)=={'type':'success','data':[{'X':'done','P':'100'}],'more':False}
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as pool:list(pool.map(work,range(8)))
    # Queries exhausted: supervisors (and their workers) must have been reaped.
    children=lambda:[line for line in subprocess.check_output(['ps','-axo','pid=,ppid='],text=True).splitlines() if int(line.split()[1])==node.pid]
    deadline=time.monotonic()+2
    while children() and time.monotonic()<deadline:time.sleep(.02)
    assert not children(),children()
    print('PASS endurance: 400 private queries, 800 pages, 8 concurrent clients, no retained child processes')
finally:
    node.terminate();node.wait(timeout=5)
    assert node.returncode==0,(node.returncode,node.stderr.read())
