"""Node-wide admission, idle eviction and active shedding using controlled workers."""
import concurrent.futures
import http.client
import json
import os
from pathlib import Path
import select
import shutil
import subprocess
import tempfile
import time
import urllib.parse

ROOT=Path(__file__).resolve().parent
TEST_OVERHEAD_MB=0
FIXTURE=r'''
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <time.h>
#include "memory.h"
static void delay(long ms){struct timespec t={ms/1000,(ms%1000)*1000000};nanosleep(&t,NULL);}
static void answer(int more){
  printf("{\"type\":\"success\",\"answers\":[%s],\"more\":%s}\n",
    getenv("ISO_JSON_BINDINGS")?"{}":"\"ok\"",more?"true":"false");fflush(stdout);
}
int main(int argc,char **argv){
  if(argc==3&&!strcmp(argv[1],"--measure")){
    uint64_t bytes;if(!iso_memory_bytes((pid_t)atoi(argv[2]),&bytes))return 2;
    printf("%llu\n",(unsigned long long)bytes);return 0;
  }
  const char *goal=argc>1?argv[1]:"",*mode=strstr(goal,"hold");int hold=mode!=NULL;
  int idle=strstr(goal,"idle")!=NULL;
  if(idle){mode=strstr(goal,"idle");hold=1;answer(1);delay(200);}
  if(!mode)mode=strstr(goal,"run");
  int size=mode?atoi(mode+(hold?4:3)):0;
  int shared_pressure=0;const char *shared=getenv("ISO_SHARED_DB");
  if(shared){
    FILE *f=fopen(shared,"r");char token[32];
    if(f){shared_pressure=fscanf(f,"%31s",token)==1&&!strcmp(token,"oversized.");fclose(f);}
    if(shared_pressure)size=64;
  }
  if(!hold&&mode)delay(200);
  for(int i=0;i<size;i++){
    volatile char *p=malloc(1024*1024);if(!p)return 2;
    for(int j=0;j<1024*1024;j+=4096)p[j]=1;
    if(!hold)delay(10);
  }
  if(shared_pressure)delay(200);
  if(!hold&&mode)delay(1200);
  if(!idle)answer(hold);
  char command[64];while(hold&&fgets(command,sizeof command,stdin))answer(1);
  return 0;
}
'''

def processes():
    return {int(p):int(parent) for p,parent in (line.split() for line in subprocess.check_output(['ps','-axo','pid=,ppid='],text=True).splitlines())}

def until(predicate,timeout=4):
    deadline=time.monotonic()+timeout
    while time.monotonic()<deadline:
        value=predicate()
        if value:return value
        time.sleep(.01)
    raise AssertionError('condition timed out')

class Node:
    def __init__(self,exe,total=48,**settings):
        before=set(Path('/tmp').glob('gprolog-http-*'))
        args=[str(exe),'--port','0','--max-queries','8','--total-memory-mb',str(total+TEST_OVERHEAD_MB),'--time-ms','5000','--idle-ms','5000']
        args += [str(x) for key,value in settings.items() for x in ('--'+key.replace('_','-'),value)]
        self.p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            assert select.select([self.p.stdout],[],[],5)[0]
            line=self.p.stdout.readline();assert line,self.p.stderr.read()
            self.port=json.loads(line)['port']
            dirs=set(Path('/tmp').glob('gprolog-http-*'))-before;assert len(dirs)==1,dirs
            self.directory=dirs.pop()
            self.seen=set()
        except Exception:
            self.p.terminate();self.p.wait(timeout=5);raise
    def call(self,goal,**params):
        c=http.client.HTTPConnection('127.0.0.1',self.port,timeout=7)
        try:
            c.request('GET','/call?'+urllib.parse.urlencode(dict(goal=goal,**params)))
            r=c.getresponse();body=r.read().decode()
            return r.status,body if params.get('format')=='prolog' else json.loads(body)
        finally:c.close()
    def children(self):
        ps=processes();children={pid for pid,parent in ps.items() if parent==self.p.pid}
        self.seen.update(children|{pid for pid,parent in ps.items() if parent in children})
        return children
    def empty(self):
        until(lambda:not self.children())
        assert not self.seen.intersection(processes()),'retained query process'
        assert not list(self.directory.iterdir()),'retained query source'
    def close(self):
        self.p.terminate()
        try:assert self.p.wait(timeout=5)==0
        finally:
            if self.p.poll() is None:self.p.kill();self.p.wait()
        assert not self.p.stderr.read()
        assert not self.directory.exists()
        assert not self.seen.intersection(processes()),'query survived shutdown'
        self.p.stdout.close();self.p.stderr.close()

def success(result):
    assert result[0]==200 and result[1]['type']=='success',result

def main():
    global TEST_OVERHEAD_MB
    with tempfile.TemporaryDirectory(prefix='isobase-total-memory-') as tmp:
        root=Path(tmp);exe=root/'isobase-node'
        shutil.copy2(os.environ.get('ISO_NODE',ROOT/'isobase-node'),exe)
        shutil.copy2(ROOT/'query-supervisor',root/'query-supervisor')
        source=root/'worker.c';source.write_text(FIXTURE)
        subprocess.run(['cc','-Wall','-Wextra','-Werror','-I',str(ROOT),str(source),'-o',str(root/'query-worker')],check=True)
        # Keep fixture thresholds meaningful with an instrumented controller.
        calibration=Node(exe,total=1024)
        try:
            baseline=int(subprocess.check_output([str(root/'query-worker'),'--measure',str(calibration.p.pid)],text=True))
            TEST_OVERHEAD_MB=max(0,(baseline+1024*1024-1)//(1024*1024)-2)
        finally:calibration.close()
        node=Node(exe)
        try:
            success(node.call('hold8',limit=1,src_text='a.'));a=node.children();assert len(a)==1
            success(node.call('hold9',limit=1,src_text='b.'));b=node.children()-a;assert len(b)==1
            success(node.call('hold10',limit=1,src_text='c.'));current=node.children()
            assert len(current)==2 and b<=current and not a&current,'oldest idle not evicted for admission'
            c=current-b
            success(node.call('hold9',offset=1,limit=1,src_text='b.'));assert node.children()==current
            success(node.call('hold11',limit=1,src_text='d.'))
            assert b<=node.children() and not c&node.children(),'recached query was not newest'
            # A memory-evicted query follows the ordinary cache-miss replay path.
            success(node.call('hold8',offset=1,limit=1,src_text='a.'))
            assert not a&node.children()
        finally:node.close()
        node=Node(exe)
        try:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                active=[pool.submit(node.call,'run0'),pool.submit(node.call,'run0')]
                until(lambda:len(node.children())==2);pids=node.children()
                assert node.call('true')==(503,{'type':'error','data':'total_memory_limit_exceeded'})
                assert node.call('true',format='prolog')==(503,'error(total_memory_limit_exceeded).\n')
                assert node.children()==pids,'active query evicted merely to admit another'
                for result in active:success(result.result())
            node.empty();success(node.call('true'));node.empty()
        finally:node.close()
        # The per-query limit is deliberately much higher than the aggregate
        # limit. Only the node can stop these individually admissible workers.
        node=Node(exe,total=80,memory_mb=256)
        try:
            success(node.call('hold8',limit=1,src_text='idle.'));idle=node.children()
            with concurrent.futures.ThreadPoolExecutor() as pool:
                heavy=[pool.submit(node.call,'run44',src_text=f'heavy{i}.') for i in range(2)]
                healthy=pool.submit(node.call,'run0')
                until(lambda:len(node.children())==4)
                results=[future.result() for future in heavy]
                assert sum(r==(200,{'type':'error','data':'total_memory_limit_exceeded'}) for r in results)==1,results
                assert sum(r[1]['type']=='success' for r in results)==1,results
                success(healthy.result());assert not idle&node.children()
            node.empty();success(node.call('true'));node.empty()
        finally:node.close()
        # Pressure caused by idle allocations is handled even without a new request.
        node=Node(exe,total=48,memory_mb=256)
        try:
            success(node.call('hold8',limit=1));idle=node.children()
            success(node.call('idle52',limit=1))
            until(lambda:not idle&node.children())
            until(lambda:not node.children()) # the oversized idle continuation also goes
            node.empty();success(node.call('true'))
        finally:node.close()
        # Startup validation must count the validator inside the total budget.
        shared=root/'shared.pl';shared.write_text('p(a).')
        p=subprocess.run([str(exe),'--port','0','--shared-db',str(shared),'--total-memory-mb','16'],capture_output=True,text=True,timeout=5)
        assert p.returncode==2 and 'total_memory_limit_exceeded' in p.stderr,p
        shared.write_text('oversized.')
        p=subprocess.run([str(exe),'--port','0','--shared-db',str(shared),'--total-memory-mb',str(24+TEST_OVERHEAD_MB)],capture_output=True,text=True,timeout=5)
        assert p.returncode==2 and not p.stdout and 'total_memory_limit_exceeded' in p.stderr,p
        for value in ['0','-1','1048577','bad']:
            p=subprocess.run([str(exe),'--total-memory-mb',value],capture_output=True,timeout=3)
            assert p.returncode==2,(value,p.returncode)
        # Compile an isolated fault-injection node; production has no test flag.
        marker=root/'accounting-failed'
        wrapper='''#define iso_memory_bytes native_iso_memory_bytes
#define iso_query_memory native_iso_query_memory
#include HEADER
#undef iso_memory_bytes
#undef iso_query_memory
static int iso_memory_bytes(pid_t pid,uint64_t *bytes){
  return access(MARKER,F_OK)==0?0:native_iso_memory_bytes(pid,bytes);
}
static int iso_query_memory(pid_t pid,uint64_t *bytes){
  return access(MARKER,F_OK)==0?0:native_iso_query_memory(pid,bytes);
}
'''.replace('HEADER',json.dumps(str(ROOT/'memory_tree.h'))).replace('MARKER',json.dumps(str(marker)))
        (root/'memory_tree.h').write_text(wrapper)
        shutil.copy2(ROOT/'http.c',root/'http.c')
        broken=root/'fault-node'
        subprocess.run(['cc','-std=c11','-Wall','-Wextra','-Werror','-pthread','-I',str(ROOT),str(root/'http.c'),'-o',str(broken)],check=True)
        node=Node(broken,total=128)
        try:
            with concurrent.futures.ThreadPoolExecutor() as pool:
                running=pool.submit(node.call,'run0')
                until(lambda:len(node.children())==1)
                marker.touch()
                assert running.result()==(200,{'type':'error','data':'memory_monitor_failed'})
                node.empty()
                assert node.call('true')==(503,{'type':'error','data':'memory_monitor_failed'})
                marker.unlink();success(node.call('true'));node.empty()
        finally:node.close()
        print('PASS total memory: admission/503, oldest-idle eviction, recaching, active protection, largest-active shedding, idle pressure, startup and cleanup')

if __name__=='__main__':main()
