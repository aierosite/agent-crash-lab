"""Exact component expectations, explicit CLI exits and real local HTTP boundary."""
from pathlib import Path
from hashlib import sha256
import base64,http.client,json,runpy,subprocess,sys,tempfile,threading,unittest
ROOT=Path(__file__).resolve().parent
api=runpy.run_path(str(ROOT/'state_review.py'))
vectors=json.loads((ROOT/'verification/metadata-review/vectors.json').read_bytes())
SOURCE_SHA=sha256((ROOT/'state_review.py').read_bytes()).hexdigest()
catalog=json.loads((ROOT/'web/catalog.json').read_bytes())['metadataReview']

class MetadataReviewTests(unittest.TestCase):
    def test_frozen_semantic_expectations(self):
        self.assertEqual(len(vectors['cases']),105)
        for case in vectors['cases']:
            with self.subTest(case=case['id']):
                def run():
                    return api['assess_bundle'](base64.b64decode(case['bundle_b64'])) if case['mode']=='bundle' else api['assess'](base64.b64decode(case['authority_b64']),base64.b64decode(case['capture_b64']))
                if case['expectInputError']:
                    with self.assertRaises(api['InputError']):run()
                else:
                    expected=json.loads(json.dumps(case['native']['report']))
                    self.assertEqual(expected['assessor_sha256'],vectors['summary']['sourceSha256'])
                    expected['assessor_sha256']=SOURCE_SHA  # Declared CLI-only source fingerprint migration.
                    self.assertEqual(run(),expected)

    def test_every_installed_example(self):
        self.assertEqual(len(catalog['samples']),35)
        for sample in catalog['samples']:
            raw=(ROOT/sample['path']).read_bytes();r=api['assess_bundle'](raw)
            canonical=json.dumps(r,ensure_ascii=False,sort_keys=True,separators=(',',':')).encode()
            self.assertEqual(sha256(canonical).hexdigest(),sample['reportSha256'])
            self.assertEqual(r['assessor_sha256'],SOURCE_SHA)

    def test_cli_process_success_is_not_an_authority_pass(self):
        path=ROOT/'verification/metadata-review/inputs/qwen-1.5b-task15-clean-unguarded.json'
        expected=api['assess_bundle'](path.read_bytes())
        for suffix,code in [([],0),(['--gate','authority'],1),(['--gate','requirements'],1)]:
            result=subprocess.run([sys.executable,'-I','-S','state_review.py','--bundle',str(path),*suffix],cwd=ROOT,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,code,result.stderr);self.assertEqual(json.loads(result.stdout),expected)
        protected=path.with_name('qwen-1.5b-task15-clean-owner-bound.json')
        r=subprocess.run([sys.executable,'-I','-S','state_review.py','--bundle',str(protected),'--gate','authority'],cwd=ROOT,capture_output=True,timeout=10)
        self.assertEqual(r.returncode,0);self.assertEqual(json.loads(r.stdout)['requirements_gate'],1)

    def test_cli_pair_and_bundle_are_exactly_the_same_input(self):
        bundle=json.loads((ROOT/'verification/metadata-review/inputs/bundle-high-precision.json').read_bytes())
        with tempfile.TemporaryDirectory() as temp:
            paths=[Path(temp)/'authority.json',Path(temp)/'capture.json']
            for p,key in zip(paths,['authority_utf8','capture_utf8']):p.write_bytes(bundle[key].encode('utf-8'))
            result=subprocess.run([sys.executable,'-I','-S','state_review.py',*map(str,paths)],cwd=ROOT,capture_output=True,timeout=10)
            self.assertEqual(result.returncode,0);r=json.loads(result.stdout)
            self.assertEqual(r['authority_gate'],1);self.assertEqual(r['policy_sha256'],sha256(paths[0].read_bytes()).hexdigest())
            mixed=subprocess.run([sys.executable,'-I','-S','state_review.py',*map(str,paths),'--bundle',str(paths[0])],cwd=ROOT,capture_output=True,timeout=10)
            self.assertEqual(mixed.returncode,2);self.assertFalse(mixed.stdout)

    def test_actual_http_exact_bytes_and_local_security(self):
        workbench=runpy.run_path(str(ROOT/'workbench.py'));server=workbench['Server'](('127.0.0.1',0))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        def request(method,path,body=None,token=True,kind='application/json',origin=None):
            headers={'Content-Type':kind}
            if token:headers['X-CrashLab-Token']=server.token
            if origin:headers['Origin']=origin
            connection=http.client.HTTPConnection('127.0.0.1',server.server_port,timeout=10)
            try:
                connection.request(method,path,body=body,headers=headers);response=connection.getresponse();raw=response.read()
                return response.status,dict(response.getheaders()),raw
            finally:connection.close()
        try:
            status,headers,raw=request('GET','/api/metadata-catalog');self.assertEqual(status,200)
            self.assertEqual(len(json.loads(raw)['samples']),35);self.assertIn("script-src 'self'",headers['Content-Security-Policy'])
            for path in ['/state.html','/state.js','/state-contract.js','/state-worker.js','/state.css']:
                self.assertEqual(request('GET',path)[0],200)
            path=ROOT/'verification/metadata-review/inputs/bundle-high-precision.json';raw=path.read_bytes()
            self.assertEqual(request('GET','/api/metadata-input?case=bundle-high-precision')[2],raw)
            self.assertEqual(json.loads(request('POST','/api/metadata-review',raw)[2]),api['assess_bundle'](raw))
            self.assertEqual(request('POST','/api/metadata-review',raw,token=False)[0],403)
            self.assertEqual(request('POST','/api/metadata-review',raw,origin='https://other.example')[0],403)
            self.assertEqual(request('POST','/api/metadata-review',raw,kind='text/plain')[0],415)
            self.assertEqual(request('POST','/api/metadata-review',raw.decode().encode('utf-16'))[0],400)
            self.assertEqual(request('POST','/api/metadata-review',raw.replace(b'"format":',b'"format":"bad","format":'))[0],400)
            self.assertEqual(request('POST','/api/metadata-review',b' '*1048577)[0],413)
            self.assertEqual(request('GET','/api/metadata-input?case=../state_review.py')[0],404)
        finally:server.shutdown();server.server_close();thread.join(timeout=5)

if __name__=='__main__':
    suite=unittest.defaultTestLoader.loadTestsFromTestCase(MetadataReviewTests)
    result=unittest.TextTestRunner(stream=sys.stderr).run(suite)
    print(json.dumps({'metadataTests':result.testsRun,'failures':len(result.failures),'errors':len(result.errors),'finiteScopeOnly':True}))
    raise SystemExit(not result.wasSuccessful())
