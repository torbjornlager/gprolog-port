"""Pinned comparison inputs and per-run provenance; never treats SWI as an oracle."""
import argparse
import ctypes
import ctypes.util
from datetime import datetime, timezone
import tempfile
import hashlib
import json
import os
from pathlib import Path
import platform
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parent
PROJECT=ROOT.parent
LOCK_PATH=ROOT/'comparison-lock.json'
LOCK=json.loads(LOCK_PATH.read_text())
CONTRACT_DIR=ROOT/'contracts'/LOCK['contract_version']
RUN_DIRECTORIES={}

def output(args):
    return subprocess.check_output([str(a) for a in args],text=True,stderr=subprocess.STDOUT).strip()

def digest(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()

def verify_contract():
    if {p.name for p in CONTRACT_DIR.iterdir()}!=set(LOCK['contract_sha256']):
        raise RuntimeError('Contract file set differs from the lock')
    for name,expected in LOCK['contract_sha256'].items():
        if digest(CONTRACT_DIR/name)!=expected:
            raise RuntimeError(f'Contract input changed: {name}; version/review the contract and lock together')
    contract=json.loads((CONTRACT_DIR/'contract.json').read_text())
    if contract['version']!=LOCK['contract_version']:raise RuntimeError('Contract version mismatch')
    return contract

def verify_checkout(path,expected):
    actual=output(['git','-C',path,'rev-parse','HEAD'])
    if actual!=expected:raise RuntimeError(f'Comparison revision mismatch at {path}: expected {expected}, got {actual}')
    if output(['git','-C',path,'status','--porcelain','--untracked-files=normal']):
        raise RuntimeError(f'Comparison checkout is modified: {path}; use a clean checkout at the locked revision')

def executable(env,default):
    selected=os.environ.get(env,default)
    found=shutil.which(selected)
    if not found:raise RuntimeError(f'Missing executable {selected}; configure {env}')
    return str(Path(found).resolve())

def comparison_inputs():
    verify_contract()
    trinity=Path(os.environ.get('TRINITY_ROOT',PROJECT.parent/'trinity-demonstrator')).resolve()
    gnu=Path(os.environ.get('GPROLOG_SOURCE',PROJECT/'gprolog')).resolve()
    for name,path in [('trinity',trinity),('gprolog',gnu)]:verify_checkout(path,LOCK['repositories'][name]['commit'])
    swi=executable('SWIPL','swipl')
    gprolog=executable('GPROLOG',str(PROJECT/'install/bin/gprolog'))
    for name,exe,pattern in [('swi',swi,r'SWI-Prolog version ([\d.]+)'),('gprolog',gprolog,r'GNU Prolog\) ([\d.]+)')]:
        version=re.search(pattern,output([exe,'--version']))
        if not version or version[1]!=LOCK['versions'][name]:raise RuntimeError(f'{name} version mismatch; expected {LOCK["versions"][name]}')
    return swi,trinity,gprolog,gnu

def curl_runtime():
    library=ctypes.util.find_library('curl')
    if not library:raise RuntimeError('Cannot identify libcurl runtime')
    lib=ctypes.CDLL(library);lib.curl_version.restype=ctypes.c_char_p
    return lib.curl_version().decode()

def record_run(label,strict=None):
    mode=os.environ.get('COMPARISON_MODE','baseline')
    if mode not in ('baseline','source-pinned'):raise RuntimeError('COMPARISON_MODE must be baseline or source-pinned')
    if strict is None:strict=mode=='baseline'
    swi,trinity,gprolog,gnu=comparison_inputs()
    cc=executable('CC','cc')
    toolchain={'cc':output([cc,'--version']).splitlines()[0], 'curl_config':output([os.environ.get('CURL_CONFIG','curl-config'),'--version']), 'curl_runtime':curl_runtime()}
    host={'system':platform.system(),'machine':platform.machine(),'release':platform.release()}
    exact=toolchain==LOCK['baseline_toolchain'] and host==LOCK['baseline_platform']
    if strict and not exact:raise RuntimeError('Platform/toolchain differs from the locked baseline; select COMPARISON_MODE=source-pinned explicitly to record another environment')
    node_path=Path(os.environ.get('ISO_COMPILED_NODE',ROOT/'isobase-node')).resolve()
    binaries={}
    for name,path in [('swi',swi),('gprolog',gprolog),('gplc',PROJECT/'install/bin/gplc'),('node',node_path),('node_worker',node_path.parent/'query-worker'),('rpc_worker',os.environ.get('ISO_WORKER',ROOT/'query-worker')),('supervisor',node_path.parent/'query-supervisor')]:
        path=Path(path).resolve()
        if path.is_file():binaries[name]={'path':str(path),'sha256':digest(path)}
    runtime_match=all(binaries.get(name,{}).get('sha256')==expected for name,expected in LOCK['baseline_runtime_sha256'].items())
    if strict and not runtime_match:raise RuntimeError('Runtime binary differs from the locked baseline build')
    # Include dirty/new implementation sources, rather than labelling them HEAD.
    sources={p.name:digest(p) for p in sorted(ROOT.iterdir()) if p.suffix in ('.c','.h','.pl','.py') or p.name=='Makefile'}
    report={'schema':1,'mode':'baseline' if strict else 'source-pinned','python':platform.python_version(),'contract_version':LOCK['contract_version'],'lock_sha256':digest(LOCK_PATH),'comparison_revisions':{k:v['commit'] for k,v in LOCK['repositories'].items()},'implementation_head':output(['git','-C',PROJECT,'rev-parse','HEAD']),'implementation_status':output(['git','-C',PROJECT,'status','--porcelain']),'source_sha256':sources,'platform':host,'toolchain':toolchain,'baseline_environment_match':exact,'baseline_runtime_match':runtime_match,'binaries':binaries,'note':'Binary fingerprints identify observed artifacts; source revisions and runtime versions alone do not prove build provenance.'}
    parent=ROOT/'build'/'comparison-runs';parent.mkdir(parents=True,exist_ok=True)
    stamp=datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')
    target=Path(tempfile.mkdtemp(prefix=f'{label}-{stamp}-',dir=parent))
    RUN_DIRECTORIES[label]=target
    (target/'provenance.json').write_text(json.dumps(report,indent=2)+'\n')
    print(f'Comparison inputs verified ({report["mode"]}): contract {LOCK["contract_version"]}; provenance {target / "provenance.json"}',flush=True)
    return swi,trinity

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    group=parser.add_mutually_exclusive_group()
    group.add_argument('--strict-environment',action='store_true',help='Require the baseline environment (default)')
    group.add_argument('--exploratory',action='store_true',help='Allow other builds while retaining source/version pins; not exact baseline evidence')
    args=parser.parse_args()
    try:record_run('preflight',False if args.exploratory else True if args.strict_environment else None)
    except (RuntimeError,subprocess.CalledProcessError,OSError) as error:parser.exit(2,f'{error}\n')
