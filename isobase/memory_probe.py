"""Measure aggregate RSS of temporary node process trees (not unique RAM).
Run manually: python3 memory_probe.py. No changes to the development node.
"""
import http.client
import json
import subprocess
import time
import urllib.parse


def snapshot(root):
    rows={}
    for line in subprocess.check_output(['ps','-axo','pid=,ppid=,rss=,comm='],text=True).splitlines():
        pid,ppid,rss,command=line.strip().split(None,3)
        rows[int(pid)]=(int(ppid),int(rss),command)
    ids={root}
    while True:
        added={pid for pid,(parent,_,_) in rows.items() if parent in ids}
        if added<=ids:break
        ids|=added
    groups={'node':0,'supervisors':0,'workers':0}
    counts={key:0 for key in groups}
    for pid in ids:
        _,rss,command=rows[pid]
        group='node' if pid==root else 'supervisors' if command.endswith('query-supervisor') else 'workers'
        groups[group]+=rss;counts[group]+=1
    return {'rss_mib':{k:round(v/1024,2) for k,v in groups.items()},
            'total_rss_mib':round(sum(groups.values())/1024,2),'processes':counts}

for workload in ['small','retained_list_100000']:
    for capacity in [8,16,32]:
        node=subprocess.Popen(['./isobase-node','--auth','open','--port','0','--max-queries',str(capacity),
            '--idle-ms','60000','--time-ms','3000','--shared-db','shared-example.pl'],
            stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
        try:
            port=json.loads(node.stdout.readline())['port']
            empty=snapshot(node.pid)
            for index in range(capacity):
                name=f'N{index}'
                goal=f'between(1,100,{name})'
                if workload=='retained_list_100000':goal=f'length(L,100000),{goal}'
                params={'goal':goal,'template':name,'format':'prolog','limit':1}
                c=http.client.HTTPConnection('127.0.0.1',port,timeout=5)
                c.request('GET','/call?'+urllib.parse.urlencode(params))
                r=c.getresponse();body=r.read().decode();c.close()
                assert r.status==200 and body=='success([1],true).\n',(r.status,body)
            time.sleep(.1)
            full=snapshot(node.pid)
            assert full['processes']=={'node':1,'supervisors':capacity,'workers':capacity},full
            print(json.dumps({'workload':workload,'capacity':capacity,'empty':empty,'full':full}),flush=True)
        finally:
            node.terminate()
            try:node.wait(timeout=10)
            except subprocess.TimeoutExpired:node.kill();node.wait();raise
            assert node.returncode==0,node.stderr.read()
