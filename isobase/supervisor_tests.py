"""Exercise supervision through pipes, including non-cooperating Prolog goals."""
import json
import os
import select
import signal
import subprocess
import tempfile
import shutil
from pathlib import Path
import time

class Query:
    def __init__(self, goal, template='X', limit=2, options=(), executable=None):
        self.p = subprocess.Popen([executable or os.environ.get('ISO_SUPERVISOR','./query-supervisor'),f'query(({goal}),({template}))',
                                   str(limit),*options],stdin=subprocess.PIPE,
                                  stdout=subprocess.PIPE,stderr=subprocess.PIPE)
        self.pending = b''
        self.worker = None

    def event(self, timeout=3):
        end = time.monotonic()+timeout
        while b'\n' not in self.pending:
            left = end-time.monotonic()
            assert left>0 and select.select([self.p.stdout],[],[],left)[0], 'event timeout'
            data = os.read(self.p.stdout.fileno(),65536)
            assert data, ('unexpected EOF',self.p.poll(),self.p.stderr.read())
            self.pending += data
        line,self.pending = self.pending.split(b'\n',1)
        return json.loads(line)

    def send(self, data):
        self.p.stdin.write(data)
        self.p.stdin.flush()

    def remember_worker(self):
        end=time.monotonic()+2
        found=[]
        while not found and time.monotonic()<end and self.p.poll() is None:
            lines = subprocess.check_output(['ps','-axo','pid=,ppid='],text=True).splitlines()
            found = [int(a) for a,b in (line.split() for line in lines) if int(b)==self.p.pid]
            if not found:time.sleep(.01)
        assert len(found)==1,found
        self.worker = found[0]

    def ended(self, code=0):
        assert self.p.wait(timeout=3)==code
        assert not self.pending and not self.p.stdout.read(), 'extra or partial event'
        assert not self.p.stderr.read()
        if self.worker:
            try:
                os.kill(self.worker,0)
            except ProcessLookupError:
                pass
            else:
                raise AssertionError('worker not reaped')
        self.p.stdin.close();self.p.stdout.close();self.p.stderr.close()

queries = []
def start(*a,**k):
    q=Query(*a,**k);queries.append(q);return q

try:
    q=start('between(1,5,X)')
    assert q.event()=={'type':'success','answers':['1','2'],'more':True}
    q.remember_worker()
    q.send(b'next\n');assert q.event()['answers']==['3','4']
    q.send(b'next\n');assert q.event()=={'type':'success','answers':['5'],'more':False}
    q.ended()

    q=start('repeat,fail',options=['--time-ms','150'])
    q.remember_worker()
    assert q.event()['term']=='time_limit_exceeded';q.ended()

    # Lookahead has already written part of a page inside the worker.
    q=start('X=first;repeat,fail',options=['--time-ms','150'])
    assert q.event()=={'type':'error','term':'time_limit_exceeded'};q.ended()

    q=start('between(1,5,X)',limit=1,options=['--idle-ms','150'])
    assert q.event()['more'];q.remember_worker()
    q.send(b'n')  # Partial command does not extend continuation lifetime.
    assert q.event()['term']=='continuation_expired';q.ended()

    q=start('repeat,fail',options=['--time-ms','2000'])
    q.remember_worker();q.send(b'stop\n')
    assert q.event()['term']=='cancelled';q.ended()

    q=start('repeat,fail')
    q.remember_worker();q.p.stdin.close()
    assert q.event()['term']=='controller_disconnected';q.ended()

    q=start('between(1,5,X)',limit=1)
    assert q.event()['more'];q.remember_worker();q.send(b'invalid\n')
    assert q.event()['term']=='protocol_error';q.ended()

    q=start('length(X,10000)',options=['--max-output','128'])
    assert q.event()['term']=='output_limit_exceeded';q.ended()

    q=start('length(X,1000000)',options=['--heap-kb','64'])
    assert q.event()['type']=='error';q.ended()

    q=start('repeat,fail')
    q.remember_worker();os.kill(q.worker,signal.SIGKILL)
    assert q.event()['term']=='worker_exit';q.ended()

    q=start('repeat,fail')
    q.remember_worker();q.p.terminate();q.ended(128+signal.SIGTERM)

    # Idle time is separate from the active budget, and queries are independent.
    a=start('between(1,3,X)',limit=1,options=['--time-ms','200','--idle-ms','1000'])
    b=start('member(X,[a,b])',limit=1)
    assert a.event()['answers']==['1'];assert b.event()['answers']==['a']
    time.sleep(.25)
    a.send(b'next\n');assert a.event()['answers']==['2']
    b.send(b'next\n');assert b.event()['answers']==['b'];b.ended()
    a.send(b'next\n');assert a.event()['answers']==['3'];a.ended()

    # Late worker exceptions survive paging as complete events.
    q=start('X=first;throw(later_error)',limit=1)
    assert q.event()['answers']==['first'];q.send(b'next\n')
    assert q.event()['term']=='later_error';q.ended()

    with tempfile.TemporaryDirectory(prefix='isobase-supervisor-') as d:
        path=Path(d)/'source.pl';path.write_text('colour(red). colour(blue).')
        q=start('colour(X)',options=['--source',str(path)])
        assert q.event()['answers']==['red','blue'];q.ended()
        path.write_text('p :- halt.')
        q=start('p',options=['--source',str(path)])
        assert 'permission_error' in q.event()['term'];q.ended()

        # Deterministic transport fixture verifies a cumulative active budget.
        # It is intentionally not a Prolog worker; policy tests run separately.
        exe=Path(d)/'query-supervisor'
        shutil.copyfile(os.environ.get('ISO_SUPERVISOR','./query-supervisor'),exe)
        exe.chmod(0o755)
        worker=Path(d)/'query-worker'
        # Avoid charging a cold Python interpreter startup against the 1s
        # fixture budget; only the two intentional delays should dominate it.
        worker.write_text("#!/bin/sh\n"
                          "sleep 0.6\n"
                          "printf '%s\\n' '{\"type\":\"success\",\"answers\":[\"1\"],\"more\":true}'\n"
                          "read -r command\n"
                          "sleep 0.6\n"
                          "printf '%s\\n' '{\"type\":\"success\",\"answers\":[\"2\"],\"more\":false}'\n")
        worker.chmod(0o755)
        q=start('true',executable=str(exe),options=['--time-ms','1000'])
        first=q.event();assert first.get('answers')==['1'],first
        q.send(b'next\n')
        assert q.event()['term']=='time_limit_exceeded';q.ended()
    print('PASS supervisor: paging, deadlines, cancellation, EOF, output/heap bounds, worker death, signals and isolation')
finally:
    for q in queries:
        if q.p.poll() is None:
            q.p.terminate()
            try:q.p.wait(timeout=3)
            except subprocess.TimeoutExpired:q.p.kill();q.p.wait()
