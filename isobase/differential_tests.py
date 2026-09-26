"""Compare a supported /call subset against the local Trinity demonstrator."""
import http.client
import json
import os
from pathlib import Path
import shutil
import socket
import subprocess
import tempfile
import time
import urllib.parse

from comparison_config import record_run
swi,trinity=record_run('differential')

def get(port,params):
    c=http.client.HTTPConnection('127.0.0.1',port,timeout=3)
    c.request('GET','/call?'+urllib.parse.urlencode(params))
    r=c.getresponse();body=r.read().decode();c.close()
    assert r.status==200,(r.status,body)
    return body if params.get('format')=='prolog' else json.loads(body)

processes=[]
with tempfile.TemporaryFile(mode='w+') as log:
    try:
        s=socket.socket();s.bind(('127.0.0.1',0));reference_port=s.getsockname()[1];s.close()
        shared=str(Path('shared-example.pl').resolve()).replace("'","''")
        goal=f"node:node({reference_port},[profile(isobase),auth(open),ip('127.0.0.1'),load_shared_db_file('{shared}')]),thread_get_message(stop)"
        reference=subprocess.Popen([swi,'-q','-s',str(trinity/'load.pl'),'-g',goal],stdout=log,stderr=log)
        processes.append(reference)
        node=subprocess.Popen(['./isobase-node','--auth','open','--port','0','--shared-db','shared-example.pl'],stdout=subprocess.PIPE,stderr=log,text=True)
        processes.append(node);port=json.loads(node.stdout.readline())['port']
        for _ in range(100):
            try:get(reference_port,{'goal':'true'});break
            except (OSError,http.client.HTTPException):time.sleep(.05)
        else:
            log.seek(0);raise AssertionError(log.read())
        cases=[
          {'goal':'_goal=hello'},
          {'goal':'_Goal=member(X,[a,b]),call(_Goal)'},
          {'goal':'_Goal=member(X,[a,b]),call(_Goal),T=_Goal'},
          {'goal':'_Goal=member(X,[a,b]),call(_Goal),T=X'},
          {'goal':'_A=X,X=ok'},
          {'goal':'_Goal=member(X,[a,b]),once(call(_Goal))'},
          {'goal':'findall(N,between(1,110,N),L)'},
          {'goal':'between(1,110,N)'},
          {'goal':'true','limit':0},
          {'goal':'fail','limit':0},
          {'goal':'throw(ball)','limit':0},
          {'goal':'repeat,fail','limit':0},
          {'goal':'between(1,3,X)','limit':1},
          {'goal':'between(1,3,X)','offset':1,'limit':0},
          {'goal':'true'}, {'goal':'fail'}, {'goal':'X=hello'},
          {'goal':'X=Y'}, {'goal':'X=[1,2]'}, {'goal':'X=pair(A,A)'},
          {'goal':'X=hello','template':'ignored(Y)'},
          {'goal':'_Hidden=1,X=ok'},
          {'goal':'colour(X)','src_text':'colour(red). colour(blue).'},
          {'goal':'findall(N,between(1,3,N),X)'},
          {'goal':'between(1,5,X)','limit':2},
          {'goal':'between(1,5,X)','limit':1,'offset':2},
          {'goal':'between(1,5,X)','limit':2,'offset':3},
          {'goal':'between(1,5,X)','limit':2,'once':'true'},
          {'goal':'between(1,3,X)','template':'pair(X,X)','format':'prolog'},
          {'goal':'X=[1,2]','template':'X','format':'prolog'},
          {'goal':'fail','format':'prolog'},
          {'goal':'(X=Y;X=Z)','template':'pair(X,X)','format':'prolog'},
          {'goal':'human(X)'},
          {'goal':'price(widget,X)'},
          {'goal':'list_price(widget,X)','src_text':'list_price(widget,999).'},
          {'goal':'price(widget,X)','src_text':'list_price(widget,999).'},
          {'goal':'call(price,widget,X)','src_text':'list_price(widget,999).'},
          {'goal':'price(widget,X)','src_text':'price(widget,42).'},
          {'goal':'list_price(widget,X)','src_text':':- dynamic list_price/2.'},
          {'goal':'price(widget,X)','src_text':':- dynamic list_price/2.'},
          {'goal':'human(X)','limit':1},
          {'goal':'human(X)','offset':1,'limit':2},
        ]
        mismatches=[]
        for params in cases:
            actual=get(port,params);expected=get(reference_port,params)
            if params.get('format')=='prolog':
                # Compare parsed terms, including variable sharing, rather than
                # spelling of independently generated variable names.
                result=subprocess.run([swi,'-q','-g',
                    'read_term(user_input,A,[]),read_term(user_input,B,[]),(A=@=B->halt;halt(1))'],
                    input=actual+expected,text=True,capture_output=True,timeout=3)
                same=result.returncode==0
            else:same=actual==expected
            if not same:mismatches.append((params,actual,expected))
        assert not mismatches,json.dumps(mismatches,indent=2)
        print(f'PASS {len(cases)} differential /call responses against Trinity')
    finally:
        for p in processes:p.terminate()
        for p in processes:
            try:p.wait(timeout=5)
            except subprocess.TimeoutExpired:p.kill();p.wait()
