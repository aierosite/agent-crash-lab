"""Actual loopback transport checks; replay only, no runtime/model/RPC execution."""
from pathlib import Path
from hashlib import sha256
import json,runpy,threading,unittest,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
app=runpy.run_path(str(ROOT/'workbench.py'))
review=runpy.run_path(str(ROOT/'receipt_journal.py'))['assess_bundle']
samples=json.loads((ROOT/'verification/receipt-journal/samples.json').read_bytes())

def bundle(row):
    return {'format':'agent-crash-lab/native-journal-bundle-v1',**{k+'_utf8':(ROOT/row[k]).read_bytes().decode('utf-8') for k in ['journal','policy']}}

class JournalHTTPTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=app['Server'](('127.0.0.1',0))
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.base='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join(3)
    def request(self,path,body=None,headers=None):
        h={'Content-Type':'application/json','X-CrashLab-Token':self.server.token,**(headers or {})}
        raw=None if body is None else body if type(body) is bytes else json.dumps(body,ensure_ascii=True).encode()
        req=urllib.request.Request(self.base+path,data=raw,headers=h)
        try:response=urllib.request.urlopen(req,timeout=12)
        except urllib.error.HTTPError as e:response=e
        return response.status,response.read()
    def test_complete_http_reports_and_raw_crlf_match_direct_kernel(self):
        for row in samples:
            b=bundle(row);self.assertIn('\r\n',b['policy_utf8'])
            code,raw=self.request('/api/native-journal-review',b)
            self.assertEqual(code,200,raw)
            value=json.loads(raw);self.assertEqual(value,review(b['journal_utf8'],b['policy_utf8']))
            self.assertEqual(value['policy_sha256'],sha256((ROOT/row['policy']).read_bytes()).hexdigest())
    def test_installed_source_catalog_and_exact_data_only_downloads(self):
        for name in ['journal.html','journal.js','journal-contract.js','journal-worker.js','journal.css']:
            code,raw=self.request('/'+name);self.assertEqual(code,200);self.assertEqual(raw,(ROOT/'web'/name).read_bytes())
        code,raw=self.request('/api/native-journal-catalog');self.assertEqual(code,200)
        c=json.loads(raw);self.assertEqual(c['format'],'agent-crash-lab/native-journal-workbench-v1')
        for name,item in c['files'].items():
            self.assertEqual(item,{'bytes':(ROOT/name).stat().st_size,'sha256':sha256((ROOT/name).read_bytes()).hexdigest()})
        for row in samples:
            for part in ['journal','policy']:
                code,raw=self.request('/api/native-journal-input?case='+row['id']+'&part='+part)
                self.assertEqual(code,200);self.assertEqual(raw,(ROOT/row[part]).read_bytes())
        for query in ['case=../../session&part=journal','case=before-payment&part=../../receipt_journal.py','case=before-payment&part=reference']:
            self.assertEqual(self.request('/api/native-journal-input?'+query)[0],404)
    def test_strict_bounded_text_transport_no_paths_or_extra_fields(self):
        good=bundle(samples[0])
        cases=[{**good,'journal_utf8':{}},{**good,'policy_utf8':True},{**good,'path':'receipt_journal.py'},
               {**good,'journal_utf8':'\ud800'},{**good,'policy_utf8':''},
               {**good,'policy_utf8':' '*16385},{**good,'journal_utf8':' '*4194305},
               {**good,'format':'wrong'}, {'path':'../../session.json'}]
        for bad in cases:
            code,raw=self.request('/api/native-journal-review',bad)
            self.assertEqual(code,400,raw);self.assertEqual(set(json.loads(raw)),{'error'})
        raw=json.dumps(good).encode();duplicate=raw[:-1]+b',"format":"agent-crash-lab/native-journal-bundle-v1"}'
        self.assertEqual(self.request('/api/native-journal-review',duplicate)[0],400)
    def test_malformed_native_success_never_has_a_report(self):
        data=ROOT/'verification/receipt-journal/controls'
        for name in ['boolean-success','before-payment-torn-block-result']:
            b={'format':'agent-crash-lab/native-journal-bundle-v1','journal_utf8':(data/(name+'.jsonl')).read_bytes().decode(),'policy_utf8':(data/(name+'.policy.json')).read_bytes().decode()}
            code,raw=self.request('/api/native-journal-review',b);value=json.loads(raw)
            if name=='boolean-success':self.assertEqual(code,400);self.assertEqual(set(value),{'error'})
            else:
                self.assertEqual(code,200);self.assertEqual(value,review(b['journal_utf8'],b['policy_utf8']))
                self.assertIsNone(value['assessment']['principal_received'])
    def test_existing_origin_token_and_body_limits_cover_new_route(self):
        good=bundle(samples[0]);path='/api/native-journal-review'
        for headers,status in [({'Origin':'https://example.com'},403),({'X-CrashLab-Token':'wrong'},403),({'Content-Type':'text/plain'},415),({'Content-Length':str(app['MAX_BODY']+1)},413)]:
            self.assertEqual(self.request(path,good,headers)[0],status)
        self.assertEqual(self.request('/api/native-journal-catalog',headers={'Host':'example.com'})[0],403)

if __name__=='__main__':unittest.main()
