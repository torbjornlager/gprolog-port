"""Build an isolated node bundle with validated native shared predicates.
Example: python3 build_shared.py shared-example.pl --output build/example
The output directory must not already exist. Runtime snapshots remain supported
by the ordinary build. No source directives execute during generation.
"""
import argparse
import hashlib
import json
import os
import platform
import re
from pathlib import Path
import shutil
import stat
import subprocess
import tempfile

ROOT=Path(__file__).resolve().parent

def fix_arm64_comparisons(assembly):
    """Pinned ma2asm uses Nearest_Immediate (logical immediates) for CMP.
    CMP needs an unsigned 12-bit arithmetic immediate, optionally shifted 12.
    Use the backend's own x7 scratch register for the other integer constants.
    This touches generated assembly only, not the installed compiler/runtime.
    """
    count=0
    def replace(match):
        nonlocal count
        value=int(match.group(1))
        if 0<=value<=4095 or (0<=value<=4095*4096 and value%4096==0):return match.group(0)
        count+=1
        bits=value & ((1<<64)-1)
        lines=[f'\tmovz x7, #{bits & 65535}']
        for shift in (16,32,48):
            part=(bits>>shift)&65535
            if part:lines.append(f'\tmovk x7, #{part}, lsl #{shift}')
        lines.append('\tcmp x0, x7')
        return '\n'.join(lines)
    # Compiler comments can contain byte-oriented escaped atom text.
    # Preserve every byte while modifying ASCII instructions only.
    text=assembly.read_text(encoding="latin-1")
    text=re.sub(r'^[ \t]*cmp[ \t]+x0,[ \t]*#(-?\d+)[ \t]*$',replace,text,flags=re.MULTILINE)
    assembly.write_text(text,encoding="latin-1")
    return count

def build(source,output):
    output=Path(output).resolve()
    if output.exists():raise ValueError(f'Output already exists: {output}; choose a new directory')
    # Nonblocking open rejects FIFOs/devices without hanging the build.
    fd=os.open(source,os.O_RDONLY|os.O_NONBLOCK)
    with os.fdopen(fd,'rb') as stream:
        if not stat.S_ISREG(os.fstat(stream.fileno()).st_mode):raise ValueError('Source must be a regular file')
        data=stream.read(1024*1024+1)
    if len(data)>1024*1024 or b'\0' in data:raise ValueError('Source must be text without NUL, at most 1 MiB')
    subprocess.run(['make','all','shared-compiler'],cwd=ROOT,check=True)
    output.parent.mkdir(parents=True,exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='.native-build-',dir=output.parent) as temp:
        stage=Path(temp)
        snapshot=stage/'shared-source.pl';snapshot.write_bytes(data)
        native=stage/'shared-native.pl'
        env=os.environ.copy()
        # Build-time parsing is not charged against the runtime query budget.
        env.update(GLOBALSZ='131072',LOCALSZ='32768',TRAILSZ='16384',CSTRSZ='4096')
        subprocess.run([str(ROOT/'shared-compiler'),str(snapshot),str(native)],cwd=ROOT,env=env,check=True)
        install=Path(env.get('GPROLOG_ROOT',str(ROOT.parent)))/'install/bin'
        env['PATH']=str(install)+os.pathsep+env.get('PATH','')
        files=['query.pl','source.pl','policy.pl','prologue.pl','text.pl','rpc.pl','terms.c','transport.c','worker.c']
        assembly=stage/'shared-native.s'
        subprocess.run([str(install/'gplc'),'-S',str(native),'-o',str(assembly)],cwd=ROOT,env=env,check=True)
        fixes=fix_arm64_comparisons(assembly) if platform.machine() in ('arm64','aarch64') else 0
        subprocess.run([str(install/'gplc'),'--no-top-level',*[str(ROOT/f) for f in files],str(assembly),
                        '-L','-lcurl','-L','-lpthread','-o',str(stage/'query-worker')],cwd=ROOT,env=env,check=True)
        for file in ['isobase-node','query-supervisor']:shutil.copy2(ROOT/file,stage/file)
        # Smoke-test the finished native worker before publishing the bundle.
        result=subprocess.run([str(stage/'query-worker'),'query(true,ok)','1'],input='',capture_output=True,text=True,check=True,
                              env={k:v for k,v in env.items() if not k.startswith('ISO_')},timeout=5)
        assert json.loads(result.stdout)=={'type':'success','answers':['ok'],'more':False},result.stdout
        (stage/'manifest.json').write_text(json.dumps({'mode':'compiled','arm64_comparison_fixes':fixes,'source_sha256':hashlib.sha256(data).hexdigest(),
            'source_bytes':len(data),'implementation_sha256':{f:hashlib.sha256((ROOT/f).read_bytes()).hexdigest()
            for f in [*files,'compile_shared.pl','compile_shared.c','build_shared.py','http.c','supervisor.c','protocol.h']}},indent=2)+'\n')
        # Rename publishes only a complete build; failures leave no output bundle.
        os.rename(stage,output)
    return output

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source',type=Path)
    parser.add_argument('--output',required=True,type=Path)
    args=parser.parse_args()
    try:print(build(args.source,args.output))
    except (OSError,ValueError,subprocess.SubprocessError,AssertionError) as error:
        parser.exit(1,f'{error}\n')
