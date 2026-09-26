"""Regressions for speculative browser connections and partial HTTP headers."""
import http.client
import json
import os
import select
import socket
import subprocess
import time

node=subprocess.Popen([os.environ.get('ISO_NODE','./isobase-node'),'--auth','open','--port','0'],
                      stdout=subprocess.PIPE,stderr=subprocess.PIPE,text=True)
connections=[]
def connect(port):
    s=socket.create_connection(('127.0.0.1',port),timeout=4)
    connections.append(s)
    return s

def response(s):
    r=http.client.HTTPResponse(s);r.begin()
    return r.status,json.loads(r.read())

try:
    assert select.select([node.stdout],[],[],3)[0]
    port=json.loads(node.stdout.readline())['port']
    idle=connect(port)
    idle_start=time.monotonic()
    warmed=connect(port)
    time.sleep(2.3)  # The previous reader queued HTTP 400 before any request.
    assert not select.select([warmed],[],[],0)[0], 'unsolicited HTTP response'
    warmed.sendall(f'GET /call?goal=true HTTP/1.1\r\nHost: localhost:{port}\r\n\r\n'.encode())
    assert response(warmed)==(200,{'type':'success','data':[{}],'more':False})

    partial=connect(port)
    partial.sendall(b'GET /call?goal=true HTTP/1.1\r\nHost:')
    assert response(partial)==(408,{'type':'error','data':'incomplete_request'})

    oversized=connect(port)
    oversized.sendall(b'GET /call?goal=true HTTP/1.1\r\nX-Fill: '+b'a'*262144)
    assert response(oversized)==(431,{'type':'error','data':'request_headers_too_large'})

    # An unused connection eventually closes silently, without a stale 400.
    assert select.select([idle],[],[],max(0,12-(time.monotonic()-idle_start)))[0]
    assert idle.recv(4096)==b'', 'idle connection received an HTTP error'

    final=connect(port)
    final.sendall(b'GET /call?goal=true HTTP/1.1\r\n')
    time.sleep(.05)
    final.sendall(f'Host: localhost:{port}\r\n\r\n'.encode())
    assert response(final)[0]==200
    print('PASS request reader: delayed first request, silent idle close, partial timeout, oversized headers and fragmentation')
finally:
    for s in connections:s.close()
    node.terminate()
    try:node.wait(timeout=4)
    except subprocess.TimeoutExpired:node.kill();node.wait();raise
    assert node.returncode==0,(node.returncode,node.stderr.read())
    assert not node.stderr.read()
