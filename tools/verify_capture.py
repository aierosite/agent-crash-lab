"""Offline raw-capture and observed-browser compatibility replay, no network/model calls."""
from pathlib import Path
from hashlib import sha256
import json,runpy
ROOT=Path(__file__).resolve().parents[1];D=ROOT/'verification/capture-study'
def verify():
 api=runpy.run_path(str(ROOT/'token_capture.py'));reference=json.loads((D/'reference.json').read_bytes());record=json.loads((D/'browser-verified.json').read_bytes())
 assert record['mode']=='actual-public-browser-python-webassembly-import' and record['independentBlindEvaluation'] is False
 assert all(sha256((ROOT/name).read_bytes()).hexdigest()==digest for name,digest in record['sourceFingerprints'].items())
 observed={row['id']:row['report'] for row in record['rows']};assert len(observed)==len(reference['cases'])==4
 for case in reference['cases']:
  directory=ROOT/case['capture'];assert sha256((directory/'capture.json').read_bytes()).hexdigest()==case['captureSha256']
  result,bundle=api['review'](directory);assert result['source_integrity']['matched'] and result['assessment_accepted']
  assert result['gate']==case['expectedGate'] and len(result['uninterpreted_records'])==case['expectedUnparsed']
  assert sha256(bundle).hexdigest()==case['bundleSha256'] and result['assessment']==observed[case['id']]
 return {'format':'agent-crash-lab/capture-compatibility-replay-v1','captures':4,'originalRawFilesVerified':sum(1+2*len(json.loads((ROOT/c['capture']/'capture.json').read_bytes())['records']) for c in reference['cases']),'observedFullBrowserReportsMatched':4,'newModelCalls':0,'networkRequests':0,'independentBlindEvaluation':False,'meaning':'Offline equality replay of raw supplied-byte captures and four same-author actual browser imports, not a new browser run, source-authentication proof or independent financial accuracy.'}
if __name__=='__main__':print(json.dumps(verify()))
