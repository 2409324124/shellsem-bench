"""After-implementation integration check: preserve artifacts after API exhaustion."""
import json
import os
from pathlib import Path
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from unittest.mock import patch
from runner.config import Config
from runner.execute import run,ROOT
from runner.scoring import summarize,read_events


@unittest.skipUnless(os.environ.get('SHELLSEM_DOCKER_TESTS')=='1','Docker integration opt-in')
class RecoveryTests(unittest.TestCase):
    def test_api_exhaustion_keeps_and_grades_the_existing_submission(self):
        requests=[]
        solution=(ROOT/'reference/BSH001.sh').read_text()
        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):
                body=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                requests.append(body)
                if len(requests)>1:
                    self.send_response(503);self.send_header('Content-Type','application/json');self.end_headers()
                    self.wfile.write(b'{"error":{"message":"Service unavailable"}}');return
                self.send_response(200);self.send_header('Content-Type','text/event-stream');self.end_headers()
                delta={'role':'assistant','tool_calls':[{'index':0,'id':'write_once','type':'function','function':{'name':'write','arguments':json.dumps({'path':'/workspace/solution.sh','content':solution})}}]}
                for item in ({'delta':delta,'finish_reason':None},{'delta':{},'finish_reason':'tool_calls'}):
                    chunk={'id':'mock','object':'chat.completion.chunk','created':1,'model':'test','choices':[{'index':0,**item}]}
                    self.wfile.write(('data: '+json.dumps(chunk)+'\n\n').encode())
                self.wfile.write(b'data: [DONE]\n\n')
            def log_message(self,*args):pass
        server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with tempfile.TemporaryDirectory() as d:
                directory=Path(d)
                with patch('runner.execute.load_config',return_value=Config(f'http://127.0.0.1:{server.server_port}/v1','fake-test-key','test')):
                    result=run('BSH001','preview',directory,45)
                score=summarize(result,read_events(directory/'events.jsonl'))
                self.assertEqual(len(requests),4)
                self.assertEqual(result['status'],'generation_error')
                self.assertEqual(result['artifact_origin'],'interrupted')
                self.assertEqual(score['submission'],{'status':'pass','passed':6,'total':6})
                self.assertEqual(score['generation']['failure'],'api_server_error')
                self.assertEqual(score['generation']['retry_count'],2)
                self.assertIn('retry_exhausted',score['generation']['anomalies'])
                self.assertEqual((directory/'solution.sh').read_text(),solution)
        finally:server.shutdown();server.server_close();thread.join()
