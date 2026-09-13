import os
"""Private worker lifecycle tests; this is not ISOBASE conformance yet."""
import json
import subprocess

def run(term, limit=2, commands='next\n' * 10):
    p = subprocess.run([os.environ.get('ISO_WORKER','./query-worker'), term, str(limit)], input=commands,
                       text=True, capture_output=True, timeout=10)
    assert p.returncode == 0, (p.returncode, p.stderr)
    assert not p.stderr, p.stderr
    return [json.loads(line) for line in p.stdout.splitlines()]

pages = run('query(between(1,5,X),X)')
assert [p['answers'] for p in pages] == [['1','2'],['3','4'],['5']]
assert [p['more'] for p in pages] == [True,True,False]
assert run('query(fail,X)') == [{'type':'failure'}]
assert run('query(true,ok)')[0]['answers'] == ['ok']
assert run('query((X=one;X=two),pair(X,X))')[0]['answers'] == ['pair(one,one)','pair(two,two)']
assert run('query(((X=1;X=2),!),X)')[0]['answers'] == ['1']
assert run('query(throw(oops),X)')[0]['term'] == 'oops'
events = run('query((X=first;throw(later_error)),X)',1)
assert events[0]['answers'] == ['first'] and events[0]['more']
assert events[1]['term'] == 'later_error'
assert len(run('query(between(1,100,X),X)',1,'stop\n')) == 1
assert len(run('query(between(1,100,X),X)',1,'')) == 1
assert run('query((,bad),X)')[0]['type'] == 'error'
assert run('query(true,\'a"b\')')[0]['answers'] == ['\'a"b\'']
p = subprocess.run([os.environ.get('ISO_WORKER','./query-worker'),'--recovery-test'],capture_output=True,text=True,timeout=20)
assert p.returncode == 0, (p.stdout,p.stderr)
memory = json.loads(p.stdout)
assert memory['before'] == memory['after']
print('PASS query paging, sharing, cut, failure, exceptions, cancellation, EOF, parsing, escaping')
print('PASS 1000 recovered queries:', memory)
