"""HTTP, bundle, CI and archived native evidence tests."""
from pathlib import Path
from datetime import datetime,timezone
import argparse,hashlib,json,runpy,subprocess,sys,tempfile,threading,time,tomllib,unittest,urllib.request,urllib.error
ROOT=Path(__file__).resolve().parent
exports=runpy.run_path(str(ROOT/'tools/export_bundle.py'));app=exports['app']

class WorkbenchTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.server=app.Server(('127.0.0.1',0));cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start();cls.base='http://127.0.0.1:'+str(cls.server.server_port)
    @classmethod
    def tearDownClass(cls):cls.server.shutdown();cls.server.server_close();cls.thread.join(timeout=3)
    def fetch(self,path,body=None,headers=None):
        h={'Content-Type':'application/json','X-CrashLab-Token':self.server.token}
        if headers:h.update(headers)
        req=urllib.request.Request(self.base+path,data=json.dumps(body).encode() if body is not None else None,headers=h)
        try:r=urllib.request.urlopen(req,timeout=10)
        except urllib.error.HTTPError as e:r=e
        raw=r.read();return r.status,r.headers,raw
    def json(self,path,body=None,headers=None):
        code,h,b=self.fetch(path,body,headers);return code,json.loads(b)
    def test_http_serves_real_engine_and_static_csp(self):
        code,h,html=self.fetch('/');self.assertEqual(code,200);self.assertIn(b'Agent Crash Lab',html);self.assertIn("frame-ancestors 'none'",h['Content-Security-Policy'])
        health=self.json('/api/health')[1];self.assertEqual(health['ok'],True)
        version=tomllib.loads((ROOT/'pyproject.toml').read_text())['project']['version']
        self.assertEqual(health['version'],version)
        self.assertEqual(json.loads((ROOT/'RELEASE_MANIFEST.json').read_bytes())['version'],version)
        self.assertEqual(self.fetch('/../../session.json')[0],404)
    def test_catalog_and_curated_case_outcomes(self):
        self.assertTrue(json.loads((ROOT/'web/catalog.json').read_bytes()) == exports['browser_catalog'](),
                        'Catalog drift')
        results={}
        for c in app.CURATED:
            code,out=self.json('/api/run',{'id':c['id']});self.assertEqual(code,200);self.assertEqual(out['report']['invocation']['status'],'assessed');self.assertFalse(out['execution']['liveModel']);results[c['id']]=out['report']
        self.assertTrue(any(c['status']=='breached' for c in results['double-payment']['constraints']))
        self.assertTrue(all(u['status']=='passed' for u in results['double-payment']['utility']['required']))
        for name in ('durable-recovery','legitimate-installments'):
            self.assertTrue(all(c['status']=='within' for c in results[name]['constraints']))
        self.assertTrue(any(u['status']=='failed' for u in results['paid-wrong-answer']['utility']['required']))
        self.assertTrue(any(c['intent']=='B' and c['status']=='unknown' for c in results['missing-evidence']['constraints']))
    def test_bundle_roundtrip_preserves_exact_bytes_and_result(self):
        code,b=self.json('/api/bundle',{'id':'double-payment'});self.assertEqual(code,200)
        t,ss=app.data_for(app.CATALOG['double-payment']);self.assertEqual(b['task_utf8'].encode(),t);self.assertEqual({k:v.encode() for k,v in b['sources_utf8'].items()},ss)
        code,out=self.json('/api/assess',b);self.assertEqual(code,200);self.assertEqual(out['report'],app.core.assess(t,ss))
    def test_corrupted_input_is_rejected_without_financial_conclusion(self):
        b=self.json('/api/bundle',{'id':'double-payment'})[1];b['sources_utf8']['recording']+=' '
        code,out=self.json('/api/assess',b);self.assertEqual(code,200);self.assertEqual(out['report']['invocation']['status'],'rejected');self.assertNotIn('constraints',out['report'])

    def test_malformed_json_and_unicode_have_actionable_errors(self):
        for raw,message in [(b'{','The input is not valid JSON. Import a corrected bundle.'),
                            (b'\xff','The input contains invalid text encoding. Import a valid JSON bundle.')]:
            with self.subTest(raw=raw):
                req=urllib.request.Request(self.base+'/api/assess',data=raw,
                    headers={'Content-Type':'application/json','X-CrashLab-Token':self.server.token})
                with self.assertRaises(urllib.error.HTTPError) as context:urllib.request.urlopen(req,timeout=10)
                self.assertEqual(context.exception.code,400)
                self.assertEqual(json.loads(context.exception.read()),{'error':message})
        b=self.json('/api/bundle',{'id':'double-payment'})[1];b['task_utf8']='\ud800'
        code,out=self.json('/api/assess',b);self.assertEqual(code,400)
        self.assertEqual(out['error'],'The bundle contains invalid Unicode text. Import a valid UTF-8 bundle.')
    def test_cross_origin_host_token_and_content_type_rejected(self):
        self.assertEqual(self.json('/api/run',{'id':'double-payment'},{'Origin':'https://attacker.example'})[0],403)
        self.assertEqual(self.json('/api/run',{'id':'double-payment'},{'X-CrashLab-Token':'wrong'})[0],403)
        self.assertEqual(self.fetch('/api/catalog',headers={'Host':'attacker.example'})[0],403)
        self.assertEqual(self.json('/api/run',{'id':'double-payment'},{'Content-Type':'text/plain'})[0],415)
    def test_input_routes_are_bounded_and_no_file_path_execution(self):
        self.assertEqual(self.json('/api/run',{'id':'../../session'})[0],400)
        self.assertEqual(self.json('/api/run',{'id':[]})[0],400)
        b=self.json('/api/bundle',{'id':'durable-recovery'})[1];b['unexpected']=True;self.assertEqual(self.json('/api/assess',b)[0],400)
        self.assertEqual(self.json('/api/assess',{'format':'wrong','path':'../../session.json'})[0],400)
        self.assertEqual(self.fetch('/api/run',{'id':'double-payment'},{'Content-Length':str(app.MAX_BODY+1)})[0],413)
    def test_gate_cli_observed_failure_pass_and_uncertainty(self):
        cases=[('double-payment','',1),('durable-recovery','',0),
               ('durable-recovery','open',2),('durable-recovery','none',2),
               ('model-corrupt','none',1),('durable-recovery','extra',2)]
        temp=Path(tempfile.mkdtemp(prefix='Crash Lab CLI With Spaces '))
        for i,(name,mode,code) in enumerate(cases):
            bundle=self.json('/api/bundle',{'id':name})[1]
            if mode=='extra':
                bundle['unexpected']=True
            elif mode:
                owner=json.loads(bundle['task_utf8']);owner['authority']['kind']='counterfactual'
                if mode=='open':owner['run']['closed_horizon']=False
                else:owner['constraints']=[]
                bundle['task_utf8']=json.dumps(owner)
            file=temp/(str(i)+'.json');file.write_text(json.dumps(bundle))
            r=subprocess.run([sys.executable,'-I','-S',str(ROOT/'gate.py'),'--bundle',str(file)],cwd=temp,capture_output=True,timeout=10)
            self.assertEqual(r.returncode,code,r.stderr.decode());self.assertEqual(json.loads(r.stdout)['gate']['exitCode'],code)
    def test_archived_native_receipts_and_process_evidence(self):
        raw=(ROOT/'evidence/native-observation.json').read_bytes();data=json.loads(raw);pre=json.loads((ROOT/'evidence/native-precommit.json').read_text());summary=self.json('/api/native-result')[1]
        self.assertEqual(summary['evidenceSha256'],hashlib.sha256(raw).hexdigest());self.assertEqual(data['nativeSendAttempts'],5);self.assertTrue(data['ownedNodeStopped']);self.assertTrue(summary['successful'])
        for run in data['runs']:
            self.assertEqual([w['exitCode'] for w in run['workers']],[77,0,0]);self.assertTrue(run['ownedNodeStopped']);self.assertEqual(run['merchantBalanceIncrease'],run['expectedMerchantIncrease'])
            recover=run['workers'][1]['events'][-1];self.assertEqual(recover['recoveredWithoutNewSend'],run['policy']=='durable')
            scenario={'id':'native','baseline':'native-'+run['policy']}
            report=app.core.assess(*app.data_for(scenario))
            self.assertEqual(report['invocation']['status'],'assessed')
            for c in report['constraints']:
                if c['metric']=='merchant_gross_principal':self.assertEqual(c['exact_total'],pre['expectedPolicies'][run['policy']][c['intent']])
            self.assertEqual([u['status'] for u in report['utility']['required']],['passed','passed'])
    def test_launcher_checks_health_and_stops_its_own_child(self):
        r=subprocess.run([sys.executable,'-I','-S',str(ROOT/'launch.py'),'--no-browser','--check'],cwd=tempfile.gettempdir(),capture_output=True,text=True,timeout=15)
        self.assertEqual(r.returncode,0,r.stderr)
        url=r.stdout.splitlines()[0].split(' ',3)[3]
        with self.assertRaises((urllib.error.URLError,ConnectionError)):
            urllib.request.urlopen(url+'api/health',timeout=2)

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--report');a=p.parse_args();start=time.perf_counter();suite=unittest.defaultTestLoader.loadTestsFromTestCase(WorkbenchTests);r=unittest.TextTestRunner(verbosity=2).run(suite)
    doc={'atUtc':datetime.now(timezone.utc).isoformat(),'testsRun':r.testsRun,'successful':r.wasSuccessful(),'elapsedSeconds':time.perf_counter()-start,'python':sys.version,'coreSha256':app.CORE_SHA256,'workbenchSha256':hashlib.sha256((ROOT/'workbench.py').read_bytes()).hexdigest(),'failures':[(str(t),s) for t,s in r.failures],'errors':[(str(t),s) for t,s in r.errors],'classification':'Local HTTP/CLI and archived native evidence checks'}
    if a.report:Path(a.report).write_text(json.dumps(doc,indent=2)+'\n')
    raise SystemExit(0 if r.wasSuccessful() else 1)
