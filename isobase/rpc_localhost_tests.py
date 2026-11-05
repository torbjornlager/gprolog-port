"""Local-node resolution uses the listener, fresh stateless source and normal policy."""
import http.server
import json
import os
from pathlib import Path
import tempfile
import threading
from shared_db_tests import Node
from outbound_test_policy import allow

class Source(http.server.BaseHTTPRequestHandler):
    def log_message(self,*args):pass
    def do_GET(self):
        self.server.requests.append(self.path)
        self.send_response(200);self.end_headers();self.wfile.write(b'localhost_loaded(one). localhost_loaded(two).')

def main():
    source=http.server.ThreadingHTTPServer(('127.0.0.1',0),Source);source.requests=[]
    thread=threading.Thread(target=source.serve_forever);thread.start()
    uri=f'http://127.0.0.1:{source.server_port}/source.pl';allow(uri)
    with tempfile.TemporaryDirectory() as d:
        shared=Path(d)/'shared.pl';shared.write_text('localhost_shared(shared).')
        node=Node(shared)
        try:
            goals=[
                "findall(X,rpc(localhost,member(X,[a,b]),[limit(1)]),[a,b])",
                "rpc(localhost,localhost_shared(shared))",
                "findall(X,rpc(localhost,localhost_loaded(X),[src_uri('"+uri+"'),limit(1)]),[one,two])",
                "promise(localhost,localhost_loaded(X),R,[src_uri('"+uri+"'),template(v(X)),once(true)]),var(X),yield(R,success([v(one),v(two)],false)),var(X)",
                "rpc(localhost,localhost_loaded(ok),[src_text('localhost_loaded(ok).')]),catch(rpc(localhost,localhost_loaded(_)),_,Missing=true),Missing==true",
                "catch(rpc(localhost,parent_only(_)),_,Missing=true),Missing==true",
                "promise(localhost,fail,R),yield(R,failure)",
                "promise(localhost,throw(local_error),R),yield(R,error(local_error))",
            ]
            for goal in goals:
                answer=node.call(goal,src_text='parent_only(secret).')
                assert answer['type']=='success',(goal,answer)
            assert source.requests==['/source.pl','/source.pl'],source.requests
            # Unconfigured/direct workers do not acquire a general loopback grant.
            from source_tests import query
            old=os.environ.pop('ISO_LOCAL_NODE_URI',None)
            try:
                answer=query('',"catch(rpc(localhost,true),E,true)",'E')[0]
                assert 'outbound_denied' in answer['answers'][0],answer
            finally:
                if old is not None:os.environ['ISO_LOCAL_NODE_URI']=old
            print('PASS localhost RPC/promise: configured listener, paging, shared/private isolation, caller-fetched source, failure/error and unchanged outbound grants')
        finally:node.close();source.shutdown();source.server_close();thread.join()
if __name__=='__main__':main()
