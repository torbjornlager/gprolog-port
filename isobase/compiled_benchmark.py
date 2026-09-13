"""Compare native/shared snapshot startup and memory; macOS footprint + summed RSS.
Optional manual benchmark, not a correctness test. Leaves results in build/benchmark*.
"""
import http.client
import json
import os
from pathlib import Path
import statistics
import subprocess
import tempfile
import time
import urllib.parse
from build_shared import build

ROOT=Path(__file__).resolve().parent

def process_tree(pid):
    rows={int(a):(int(b),int(c)) for a,b,c in (line.split() for line in
          subprocess.check_output(['ps','-axo','pid=,ppid=,rss='],text=True).splitlines())}
    ids={pid}
    while True:
        new={p for p,(parent,_) in rows.items() if parent in ids}
        if new<=ids:break
        ids|=new
    return sorted(ids),sum(rows[p][1] for p in ids)/1024

def measure(executable,source,capacity):
    args=[str(executable),'--port','0','--max-queries',str(capacity),'--time-ms','5000','--idle-ms','60000']
    if source:args+=['--shared-db',str(source)]
    p=subprocess.Popen(args,stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
    try:
        line=p.stdout.readline()
        assert line,p.stderr.read()
        port=json.loads(line)['port']
        def call(goal,template='ok',limit=1):
            c=http.client.HTTPConnection('127.0.0.1',port,timeout=8)
            c.request('GET','/call?'+urllib.parse.urlencode(dict(goal=goal,template=template,format='prolog',limit=limit)))
            r=c.getresponse();body=r.read().decode();c.close()
            assert r.status==200 and body.startswith('success('),(r.status,body)
        times=[]
        for _ in range(12):
            before=time.perf_counter();call('item(10000,_)');times.append((time.perf_counter()-before)*1000)
        for i in range(capacity):call(f'item(10000,_),between(1,100,N{i})',f'N{i}')
        ids,rss=process_tree(p.pid)
        assert len(ids)==1+2*capacity,(capacity,ids)
        with tempfile.TemporaryDirectory() as temp:
            output=Path(temp)/'footprint.json'
            subprocess.run(['/usr/bin/footprint','--noCategories','-f','bytes','-j',str(output),
                            *[arg for pid in ids for arg in ['-p',str(pid)]]],stdout=subprocess.DEVNULL,check=True,timeout=30)
            data=json.loads(output.read_text())
            assert not data.get('errors'),data
        return dict(capacity=capacity,summed_rss_mib=round(rss,2),
            macos_footprint_mib=round(data['total footprint']/1024**2,2),
            median_fresh_query_ms=round(statistics.median(times),2))
    finally:
        p.terminate();p.wait(timeout=10)

if __name__=='__main__':
    with tempfile.TemporaryDirectory(prefix='compiled-benchmark-') as temp:
        source=Path(temp)/'catalogue.pl'
        source.write_text(''.join(f'item({i},record({i},[a,b,c,d,e,f,g,h])).\n' for i in range(1,10001)))
        output=ROOT/'build'/('benchmark-'+str(time.time_ns()))
        before=time.perf_counter();bundle=build(source,output)
        verification=subprocess.run([str(bundle/'query-worker'),
            r'query((\+ (between(1,10000,I),\+item(I,_))),ok)','1'],
            input='',capture_output=True,text=True,check=True,timeout=10)
        assert json.loads(verification.stdout)=={'type':'success','answers':['ok'],'more':False},verification.stdout
        result={'facts':10000,'source_bytes':source.stat().st_size,'build_seconds':round(time.perf_counter()-before,2),
                'native_executable_bytes':(bundle/'query-worker').stat().st_size,
                'interpreted_executable_bytes':(ROOT/'query-worker').stat().st_size,'measurements':[]}
        for capacity in [8,16,32]:
            for mode in ['interpreted','compiled']:
                row=measure(ROOT/'isobase-node' if mode=='interpreted' else bundle/'isobase-node',source if mode=='interpreted' else None,capacity)
                row['mode']=mode;result['measurements'].append(row);print(json.dumps(row),flush=True)
        (bundle/'results.json').write_text(json.dumps(result,indent=2)+'\n')
        print('Results:',bundle/'results.json',flush=True)
