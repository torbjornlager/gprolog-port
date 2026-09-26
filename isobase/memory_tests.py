"""Memory enforcement and mixed-load soak. All nodes and fixtures are disposable."""
import argparse
import concurrent.futures
import http.client
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import threading
import time
import urllib.parse

ROOT=Path(__file__).resolve().parent
SOURCE="grow :- between(1,1000000,N),number_codes(N,C),atom_codes(A,C),atom_concat('"+'x'*1024+"',A,_),fail.\n"
FIXTURE=r'''
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "memory.h"
static void pause_ms(long ms) {
  struct timespec t={ms/1000,(ms%1000)*1000000};nanosleep(&t,NULL);
}
int main(int argc,char **argv) {
  if(argc>1&&!strcmp(argv[1],"--measure")) {
    for(int i=2;i<argc;i++) {
      uint64_t bytes;
      if(iso_memory_bytes((pid_t)atoi(argv[i]),&bytes))
        printf("%s %llu\n",argv[i],(unsigned long long)bytes);
    }
    return 0;
  }
  if(argc>1&&strstr(argv[1],"idle")) {
    puts("{\"type\":\"success\",\"answers\":[\"ok\"],\"more\":true}");fflush(stdout);
  }
  pause_ms(200);
  for(int i=0;i<192;i++) {
    volatile char *p=malloc(1024*1024);if(!p)return 2;
    for(int j=0;j<1024*1024;j+=4096)p[j]=1;
    pause_ms(5);
  }
  pause_ms(10000);return 0;
}
'''

def table():
    return {int(p):(int(parent),int(rss)*1024) for p,parent,rss in
            (line.split() for line in subprocess.check_output(['ps','-axo','pid=,ppid=,rss='],text=True).splitlines())}

def event(p):
    assert select.select([p.stdout],[],[],5)[0], 'supervisor event timeout'
    line=p.stdout.readline();assert line,(p.poll(),p.stderr.read())
    return json.loads(line)

def stop(p):
    if p.poll() is None:
        p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait();raise
    for stream in [p.stdin,p.stdout,p.stderr]:
        if stream:stream.close()

def supervisor_checks(directory):
    exe=directory/'query-supervisor'
    shutil.copy2(os.environ.get('ISO_SUPERVISOR',ROOT/'query-supervisor'),exe)
    source=directory/'fixture.c';source.write_text(FIXTURE)
    probe=directory/'query-worker'
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-I',str(ROOT),str(source),'-o',str(probe)],check=True)
    for mode in ['active','idle']:
        p=subprocess.Popen([str(exe),f'query({mode},ok)','1','--time-ms','5000','--idle-ms','5000','--memory-mb','64'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            if mode=='idle':assert event(p)['more'] is True
            deadline=time.monotonic()+2;worker=None
            while not worker and time.monotonic()<deadline:
                worker=next((pid for pid,(parent,_) in table().items() if parent==p.pid),None)
            assert worker
            started=time.monotonic()
            assert event(p)=={'type':'error','term':'memory_limit_exceeded'}
            assert time.monotonic()-started<3
            assert p.wait(timeout=3)==0
            assert worker not in table(),'worker was not reaped'
            assert not p.stdout.read() and not p.stderr.read()
        finally:stop(p)
    # A real Prolog atom-growth goal allocates outside the fixed Prolog stacks.
    src=directory/'grow.pl';src.write_text(SOURCE)
    p=subprocess.Popen([os.environ.get('ISO_SUPERVISOR',str(ROOT/'query-supervisor')),'query(grow,ok)','1','--source',str(src),'--memory-mb','24','--time-ms','5000'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert event(p)=={'type':'error','term':'memory_limit_exceeded'}
        assert p.wait(timeout=3)==0
        assert not p.stdout.read() and not p.stderr.read()
    finally:stop(p)
    for exe,args in [(ROOT/'query-supervisor',['query(true,ok)','1']),(ROOT/'isobase-node',[])]:
        for value in ['0','-1','1048577','bad']:
            p=subprocess.run([str(exe),*args,'--memory-mb',value],capture_output=True,timeout=3)
            assert p.returncode==2,(exe,value,p.returncode)
    # The node must forward the budget to its startup snapshot validator too.
    p=subprocess.run([str(ROOT/'isobase-node'),'--auth','open','--port','0','--shared-db',str(src),'--memory-mb','1'],capture_output=True,text=True,timeout=5)
    assert p.returncode==2 and not p.stdout and 'memory_limit_exceeded' in p.stderr,p
    # Accounting failure must not silently disable the limit.
    (directory/'memory.h').write_text('#include <stdint.h>\n#define ISO_MEMORY_POLL_MS 50\nstatic int iso_memory_bytes(pid_t pid,uint64_t *bytes){(void)pid;(void)bytes;return 0;}\n')
    shutil.copy2(ROOT/'supervisor.c',directory/'supervisor.c')
    broken=directory/'broken-supervisor'
    subprocess.run(['cc','-Wall','-Wextra','-Werror','-I',str(ROOT),str(directory/'supervisor.c'),'-o',str(broken)],check=True)
    p=subprocess.Popen([str(broken),'query(active,ok)','1'],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        assert event(p)=={'type':'error','term':'memory_monitor_failed'}
        assert p.wait(timeout=3)==0
    finally:stop(p)
    return probe

def soak(probe,seconds,total_mb=None):
    directories_before=set(Path('/tmp').glob('gprolog-http-*'))
    directory=None
    limit=256 if total_mb else 24
    args=[os.environ.get('ISO_NODE',str(ROOT/'isobase-node')),'--auth','open','--port','0','--max-queries','8','--memory-mb',str(limit),'--time-ms','5000','--idle-ms','150']
    if total_mb:args+=['--total-memory-mb',str(total_mb)]
    p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    sampling=threading.Event();samples=[];observed=set();sample_errors=[];rejections=[]
    error_term='total_memory_limit_exceeded' if total_mb else 'memory_limit_exceeded'
    # Larger atoms reach the aggregate budget before GNU's separate atom-count
    # ceiling, including when only one pressure client remains in flight.
    pressure_source=SOURCE.replace('x'*1024,'x'*8192) if total_mb else SOURCE
    class AdmissionRejected(Exception):pass
    try:
        assert select.select([p.stdout],[],[],5)[0]
        line=p.stdout.readline();assert line,p.stderr.read()
        port=json.loads(line)['port']
        directories=set(Path('/tmp').glob('gprolog-http-*'))-directories_before
        assert len(directories)==1,directories
        directory=directories.pop()
        def call(goal,**params):
            c=http.client.HTTPConnection('127.0.0.1',port,timeout=7)
            try:
                c.request('GET','/call?'+urllib.parse.urlencode(dict(goal=goal,**params)))
                r=c.getresponse();body=r.read().decode()
                if total_mb and r.status==503:
                    assert json.loads(body)=={'type':'error','data':'total_memory_limit_exceeded'},body
                    rejections.append(1);raise AdmissionRejected()
                assert r.status==200,(r.status,body)
                return body if params.get('format')=='prolog' else json.loads(body)
            finally:c.close()
        def measure():
            processes=table();children={pid for pid,(parent,_) in processes.items() if parent==p.pid}
            workers={pid for pid,(parent,_) in processes.items() if parent in children}
            observed.update(children|workers)
            data=subprocess.check_output([str(probe),'--measure',str(p.pid),*map(str,children|workers)],text=True)
            memory={int(pid):int(n) for pid,n in (line.split() for line in data.splitlines())}
            query=max((memory.get(pid,0)+sum(memory.get(w,0) for w in workers if processes[w][0]==pid) for pid in children),default=0)
            samples.append((memory.get(p.pid,0),query,sum(memory.values())))
        for _ in range(8):assert call('true')['type']=='success'
        measure();baseline=samples[-1][0];assert baseline>0
        def sample():
            try:
                while not sampling.wait(.1):measure()
            except Exception as error:sample_errors.append(error)
        sampler=threading.Thread(target=sample);sampler.start()
        deadline=time.monotonic()+seconds
        def pressure(client):
            count=0
            while time.monotonic()<deadline:
                try:result=call('grow',src_text=pressure_source+f'% client {client}\n')
                except AdmissionRejected:time.sleep(.01);continue
                assert result=={'type':'error','data':error_term},result
                count+=1
            return count
        def healthy(client):
            count=0;max_latency=0
            while time.monotonic()<deadline:
                start=time.monotonic()
                goal=f'between(1,3,X),Tag={client}'
                try:
                    assert call(goal,limit=1)['more']
                    assert call(goal,offset=1,limit=2)['more'] is False
                except AdmissionRejected:time.sleep(.01);continue
                max_latency=max(max_latency,time.monotonic()-start);count+=1
            return count,max_latency
        try:
            with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
                futures=[pool.submit(pressure,i) for i in range(2)]+[pool.submit(healthy,i) for i in range(2)]
                outcomes=[f.result() for f in futures]
            assert call('grow',src_text=pressure_source,format='prolog')==f'error({error_term}).\n'
            # Expired cached queries must release both processes as well.
            for i in range(4):assert call(f'between(1,9,X),Tag={i}',limit=1)['more']
            time.sleep(.5)
        finally:sampling.set();sampler.join(timeout=5)
        assert not sampler.is_alive() and not sample_errors,sample_errors
        for _ in range(8):assert call('true')['type']=='success'
        deadline=time.monotonic()+3
        while any(parent==p.pid for parent,_ in table().values()) and time.monotonic()<deadline:time.sleep(.02)
        processes=table()
        assert not any(parent==p.pid for parent,_ in processes.values()),'retained supervisor'
        assert not observed.intersection(processes),'retained query process'
        assert not list(directory.iterdir()),'retained query source file'
        measure();final=samples[-1][0]
        assert final<=baseline+16*1024*1024,(baseline,final)
        assert max(outcomes[2][1],outcomes[3][1])<3,outcomes
        assert outcomes[2][0] and outcomes[3][0],outcomes
        print(json.dumps(dict(seconds=seconds,memory_limit_mib=limit,total_memory_limit_mib=total_mb,admission_rejections=len(rejections),exhaustions=sum(outcomes[:2])+1,
              healthy_pages=2*(outcomes[2][0]+outcomes[3][0]),max_healthy_pair_seconds=max(outcomes[2][1],outcomes[3][1]),
              node_baseline_bytes=baseline,node_final_bytes=final,node_peak_bytes=max(x[0] for x in samples),
              sampled_query_peak_bytes=max(x[1] for x in samples),sampled_total_peak_bytes=max(x[2] for x in samples),retained_query_processes=0,retained_source_files=0),indent=2),flush=True)
    finally:
        sampling.set();p.terminate()
        try:p.wait(timeout=5)
        except subprocess.TimeoutExpired:p.kill();p.wait();raise
        assert p.returncode==0,(p.returncode,p.stderr.read())
        assert not p.stderr.read()
        stop(p)
        if directory is not None:assert not directory.exists(),'retained node temporary directory'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--seconds',type=float,default=5)
    parser.add_argument('--total-memory-mb',type=int)
    args=parser.parse_args();assert args.seconds>0
    with tempfile.TemporaryDirectory(prefix='isobase-memory-') as d:
        probe=supervisor_checks(Path(d));soak(probe,args.seconds,args.total_memory_mb)
    print('PASS memory: active/idle enforcement, atom growth, monitor failure, concurrent recovery and expiry')

if __name__=='__main__':main()
