"""Compare fresh HTTP lookup latency locally, without Docker or live-node changes.
Usage: python3 swi_latency_benchmark.py build/benchmark-... [--samples 60]
All nodes have 32-slot/cache capacity; timed queries fully finish, leaving no
cached continuation. Ten warm-up requests per implementation precede sampling.
"""
import argparse
import hashlib
import http.client
import json
import math
from pathlib import Path
import random
import select
import shutil
import socket
import statistics
import subprocess
import tempfile
import time
import urllib.parse

ROOT=Path(__file__).resolve().parent

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle',type=Path)
    parser.add_argument('--samples',type=int,default=60)
    args=parser.parse_args();bundle=args.bundle.resolve()
    source=bundle/'shared-source.pl'
    manifest=json.loads((bundle/'manifest.json').read_text())
    assert hashlib.sha256(source.read_bytes()).hexdigest()==manifest['source_sha256']
    processes=[];ports={};timings={mode:[] for mode in ['gnu_snapshot','gnu_compiled','swi_isobase']}
    request='/call?'+urllib.parse.urlencode(dict(goal='item(10000,_)',template='ok',format='prolog',limit=1))
    def lookup(mode):
        before=time.perf_counter_ns()
        c=http.client.HTTPConnection('127.0.0.1',ports[mode],timeout=8)
        c.request('GET',request);r=c.getresponse();body=r.read().decode();c.close()
        elapsed=(time.perf_counter_ns()-before)/1e6
        assert r.status==200 and body.strip()=='success([ok],false).',(mode,r.status,body)
        return elapsed
    with tempfile.TemporaryFile(mode='w+') as log:
        try:
            for mode in ['gnu_snapshot','gnu_compiled']:
                executable=ROOT/'isobase-node' if mode=='gnu_snapshot' else bundle/'isobase-node'
                command=[str(executable),'--port','0','--max-queries','32','--time-ms','5000']
                if mode=='gnu_snapshot':command+=['--shared-db',str(source)]
                p=subprocess.Popen(command,stdout=subprocess.PIPE,stderr=log,text=True);processes.append(p)
                ports[mode]=json.loads(p.stdout.readline())['port']
            with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
            ports['swi_isobase']=port
            swi=shutil.which('swipl') or '/Applications/SWI-Prolog.app/Contents/MacOS/swipl'
            goal=f"node:node({port},[profile(isobase),auth(open),ip('127.0.0.1'),cache_size(32),load_shared_db_file('{str(source)}')]),format('BENCH_READY~n'),flush_output,thread_get_message(stop)"
            p=subprocess.Popen([swi,'-q','-s','/Users/lager/trinity-demonstrator/load.pl','-g',goal],stdout=subprocess.PIPE,stderr=log,text=True);processes.append(p)
            deadline=time.monotonic()+15
            while time.monotonic()<deadline:
                if select.select([p.stdout],[],[],.1)[0]:
                    if p.stdout.readline().strip()=='BENCH_READY':break
                if p.poll() is not None:break
            else:raise RuntimeError('SWI startup timed out')
            lookup('swi_isobase')
            modes=list(timings);rng=random.Random(42)
            for _ in range(10):
                for mode in modes:lookup(mode)
            for _ in range(args.samples):
                rng.shuffle(modes)
                for mode in modes:timings[mode].append(lookup(mode))
            result={'goal':'item(10000,_)','facts':10000,'source_sha256':manifest['source_sha256'],
                'capacity':32,'occupied_cache_entries':0,'samples_per_mode':args.samples,
                'warmups_per_mode':10,'transport':'new localhost HTTP connection per request; no Docker',
                'results':{mode:{'median_ms':round(statistics.median(values),3),
                    'p95_ms':round(sorted(values)[math.ceil(.95*len(values))-1],3),
                    'samples_ms':values} for mode,values in timings.items()}}
            output=bundle/'swi-latency-results.json';output.write_text(json.dumps(result,indent=2)+'\n')
            print(json.dumps({mode:{k:v for k,v in row.items() if k!='samples_ms'} for mode,row in result['results'].items()},indent=2))
            print('Results:',output)
        finally:
            for p in processes:p.terminate()
            for p in processes:
                try:p.wait(timeout=5)
                except subprocess.TimeoutExpired:p.kill();p.wait()

if __name__=='__main__':main()
