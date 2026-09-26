import concurrent.futures
import http.client
import json
import os
import select
import socket
import subprocess
import time
import urllib.parse

node=subprocess.Popen([os.environ.get('ISO_NODE','./isobase-node'),'--auth','open','--port','0','--max-queries','2','--time-ms','600','--idle-ms','300'],stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
try:
    assert select.select([node.stdout],[],[],3)[0], 'startup timeout'
    started=node.stdout.readline()
    assert started, node.stderr.read()
    port=json.loads(started)['port']
    def call(goal, **params):
        params={'goal':goal,**params}
        c=http.client.HTTPConnection('127.0.0.1',port,timeout=4)
        c.request('GET','/call?'+urllib.parse.urlencode(params))
        r=c.getresponse();body=r.read().decode();status=r.status;c.close()
        return status, body if params.get('format')=='prolog' else json.loads(body)
    status,b=call('between(1,5,X)',limit=2)
    assert status==200 and b=={'type':'success','data':[{'X':'1'},{'X':'2'}],'more':True},(status,b)
    def child_ids():
        lines=subprocess.check_output(['ps','-axo','pid=,ppid='],text=True).splitlines()
        return {int(a) for a,b in (line.split() for line in lines) if int(b)==node.pid}
    retained=child_ids();assert len(retained)==1
    status,b=call('between(1,5,X)',limit=1,offset=2)
    assert b=={'type':'success','data':[{'X':'3'}],'more':True},b
    assert child_ids()==retained, 'continuation was restarted'
    status,b=call('between(1,5,X)',limit=2,offset=3)
    assert b=={'type':'success','data':[{'X':'4'},{'X':'5'}],'more':False},b
    assert call('true')[1]=={'type':'success','data':[{}],'more':False}
    assert call('member(X,[a,b,c])',limit=1,offset=2)[1]=={'type':'success','data':[{'X':'c'}],'more':False}
    assert call('repeat,fail',limit=0)[1]=={'type':'failure'}
    assert call('fail')[1]=={'type':'failure'}
    assert call('X=hello',template='ignored(Y)')[1]['data']==[{'X':'hello'}]
    assert call('X=Y')[1]['data'][0]['X']==call('X=Y')[1]['data'][0]['Y']
    assert call('X=[1,2]')[1]['data']==[{'X':'[1,2]'}]
    assert call('_Hidden=1,X=ok')[1]['data']==[{'X':'ok'}]
    assert call('colour(X)',src_text='colour(red). colour(blue).')[1]['data']==[{'X':'red'},{'X':'blue'}]
    assert call('between(1,3,X)',format='prolog',template='pair(X,X)')[1]=='success([pair(1,1),pair(2,2),pair(3,3)],false).\n'
    assert call('fail',format='prolog')[1]=='failure.\n'
    assert call('X=[1,2]',format='prolog',template='X')[1]=='success([[1,2]],false).\n'
    assert call('throw(oops)',format='prolog')[1]=='error(oops).\n'
    assert call('write(oops)')[1]['type']=='error'
    assert call('p',src_text='p :- halt.')[1]['type']=='error'
    assert call('between(1,5,X)',offset=3,limit=1,once='true')[1]=={'type':'success','data':[{'X':'4'}],'more':False}
    # A new query evicts an idle continuation when capacity is full.
    assert call('between(1,9,A)',limit=1)[1]['more']
    assert call('between(1,9,B)',limit=1)[1]['more']
    assert call('true')[0]==200
    time.sleep(.45)
    assert call('true')[0]==200
    # Cache miss after expiry follows the demonstrator's restart-and-offset rule.
    assert call('between(1,9,A)',offset=1,limit=1,once='true')[1]['data']==[{'A':'2'}]
    for kwargs in [{'limit':10000000001},{'limit':-1},{'offset':-1},{'format':'xml'},{'once':'maybe'},{'timeout':'nan'}]:
        assert call('true',**kwargs)[0]==400
    started=time.monotonic()
    assert call('repeat,fail',timeout=.08)[1]['type']=='error'
    assert time.monotonic()-started<1
    # A running query does not hold up another client.
    with concurrent.futures.ThreadPoolExecutor() as pool:
        running=pool.submit(call,'repeat,fail')
        time.sleep(.05)
        started=time.monotonic();assert call('X=ok')[1]['data']==[{'X':'ok'}]
        assert time.monotonic()-started<.4
        assert running.result()[1]['type']=='error'
    # Repeated requests should release all capacity.
    for _ in range(20):assert call('true')[0]==200
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
    c.request('GET','/call?goal=true&goal=fail');r=c.getresponse();assert r.status==400;r.read();c.close()
    for path in ['/call?goal=%00','/call?goal=%GG','/missing','/call']:
        c=http.client.HTTPConnection('127.0.0.1',port,timeout=2)
        c.request('GET',path);r=c.getresponse();assert r.status in (400,404);r.read();c.close()
    print('PASS HTTP: formats, paging, source, bindings, admission, expiry, deadlines and concurrent requests')
finally:
    node.terminate()
    try:node.wait(timeout=5)
    except subprocess.TimeoutExpired:node.kill();node.wait();raise
    assert node.returncode==0,(node.returncode,node.stderr.read())
    assert not node.stderr.read()
