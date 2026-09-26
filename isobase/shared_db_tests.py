from outbound_test_policy import allow
"""Shared snapshot lifecycle and namespace tests over HTTP."""
import http.client
import json
import os
from pathlib import Path
import select
import subprocess
import tempfile
import urllib.parse

SOURCE='''
unicode_label('東京😀').
human(socrates). human(plato). human(aristotle).
list_price(widget,100). list_price(gadget,250).
price(I,P) :- list_price(I,P).
inspect_price(X) :- clause(list_price(widget,X),true).
via_call(I,P) :- call(list_price(I,P)).
via_variable(I,P) :- G=list_price(I,P), G.
via_apply(I,P) :- call(list_price,I,P).
via_map(Ps) :- maplist(list_price,[widget,gadget],Ps).
via_bag(Ps) :- bagof(P,I^list_price(I,P),Ps).
word --> [shared].
shared_phrase(X) :- phrase(word,X).
edge(a,b). edge(b,c).
path(A,B) :- edge(A,B).
path(A,B) :- edge(A,C),path(C,B).
'''
class Node:
    def __init__(self,path):
        self.p=subprocess.Popen([os.environ.get('ISO_NODE','./isobase-node'),'--auth','open','--port','0','--shared-db',str(path)],
                                stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        assert select.select([self.p.stdout],[],[],4)[0], 'startup timeout'
        line=self.p.stdout.readline()
        if not line:
            self.p.wait(timeout=3)
            raise AssertionError(self.p.stderr.read())
        self.port=json.loads(line)['port']
        allow(f'http://127.0.0.1:{self.port}')
    def call(self,goal,**params):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=3)
        c.request('GET','/call?'+urllib.parse.urlencode({'goal':goal,**params}))
        r=c.getresponse();body=r.read().decode();c.close()
        assert r.status==200,(r.status,body)
        return json.loads(body)
    def close(self):
        self.p.terminate()
        try:self.p.wait(timeout=4)
        except subprocess.TimeoutExpired:self.p.kill();self.p.wait();raise
        assert self.p.returncode==0,(self.p.returncode,self.p.stderr.read())
        assert not self.p.stderr.read()

def test_shared():
    with tempfile.TemporaryDirectory(prefix='shared-tests-') as d:
        path=Path(d)/'shared.pl';path.write_text(SOURCE)
        node=Node(path)
        try:
            from proof_tree_tests import check_inspection
            check_inspection(node)
            assert node.call('price(widget,X)')['data']==[{'X':'100'}]
            shadow='list_price(widget,999). list_price(gadget,999). word --> [local].'
            assert node.call('list_price(widget,X)',src_text=shadow)['data']==[{'X':'999'}]
            for predicate in ['price','via_call','via_variable','via_apply']:
                assert node.call(f'{predicate}(widget,X)',src_text=shadow)['data']==[{'X':'100'}]
            for predicate in ['via_map','via_bag']:
                assert node.call(f'{predicate}(X)',src_text=shadow)['data']==[{'X':'[100,250]'}]
            assert node.call('shared_phrase(X)',src_text=shadow)['data']==[{'X':'[shared]'}]
            assert node.call('phrase(word,X)',src_text=shadow)['data']==[{'X':'[local]'}]
            assert node.call('path(a,X)')['data']==[{'X':'b'},{'X':'c'}]
            assert node.call('price(widget,X)',src_text='price(_,42).')['data']==[{'X':'42'}]
            assert node.call('price(widget,X)')['data']==[{'X':'100'}]
            assert node.call('list_price(widget,X)',src_text=':- dynamic list_price/2.')['data']==[{'X':'100'}]
            assert node.call('list_price(widget,X)',src_text=':- dynamic list_price/2. list_price(widget,8).')['data']==[{'X':'8'}]
            assert node.call('price(widget,X)',src_text=':- dynamic list_price/2.')['data']==[{'X':'100'}]
            for goal in ["'$shared$price'(widget,X)",
                         'assertz(list_price(widget,7))','retractall(list_price(_,_))']:
                assert node.call(goal)['type']=='error',goal
            assert node.call('clause(local(X),B),B==price(widget,X)',src_text='local(X):-price(widget,X).')['type']=='success'
            assert node.call('clause(price(widget,X),B),B==list_price(widget,X)')['type']=='success'
            page=node.call('human(X)',limit=1)
            assert page['data']==[{'X':'socrates'}] and page['more']
            path.write_text('human(new). price(widget,5).')
            # Both a continuation and a newly created query retain the startup snapshot.
            assert node.call('human(X)',limit=2,offset=1)['data']==[{'X':'plato'},{'X':'aristotle'}]
            assert node.call('price(widget,X)')['data']==[{'X':'100'}]
            other=Node(path)
            try:assert other.call('price(widget,X)')['data']==[{'X':'5'}]
            finally:other.close()
            path.unlink()
            assert node.call('human(X)',once='true')['data']==[{'X':'socrates'},{'X':'plato'},{'X':'aristotle'}]
        finally:node.close()
        for contents in ['bad(.', 'p :- halt.', ':- initialization(halt).', 'p :- missing.',
                         "'$shared$hack'.", 'x.'+' '*(1024*1024), 'x.\x00']:
            path.write_text(contents)
            p=subprocess.run([os.environ.get('ISO_NODE','./isobase-node'),'--auth','open','--port','0','--shared-db',str(path)],
                             capture_output=True,text=True,timeout=4)
            assert p.returncode!=0 and not p.stdout and p.stderr,(contents[:40],p.stdout,p.stderr)
        p=subprocess.run(['./isobase-node','--auth','open','--port','0','--shared-db',str(Path(d)/'missing')],capture_output=True,text=True,timeout=4)
        assert p.returncode!=0 and not p.stdout
    print('PASS shared DB: local shadowing, shared call context, protected clauses, snapshots, restart and startup validation')

if __name__=='__main__':test_shared()
