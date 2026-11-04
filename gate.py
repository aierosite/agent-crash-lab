"""Strict CI gate: 0 within+useful, 1 observed breach/failure, 2 inconclusive/rejected."""
from pathlib import Path
import argparse,importlib.util,json,sys
ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('acl_workbench',ROOT/'workbench.py');app=importlib.util.module_from_spec(spec);spec.loader.exec_module(app)
def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--bundle',required=True);a=p.parse_args()
    try:
        with open(a.bundle,'rb') as f:raw=f.read(app.MAX_BODY+1)
        if len(raw)>app.MAX_BODY:raise ValueError('Bundle too large')
        b=json.loads(raw)
        out=app.assess_bundle(b)
        code=app.gate(out['report']);out['gate']={'exitCode':code,'meaning':{0:'within-declared-scope-and-required-output-passed',1:'observed-breach-or-required-output-failed',2:'inconclusive-or-rejected'}[code]}
        sys.stdout.buffer.write(json.dumps(out,ensure_ascii=False,separators=(',',':')).encode()+b'\n');return code
    except (OSError,ValueError,KeyError,AttributeError,TypeError,RecursionError):
        print(json.dumps({'gate':{'exitCode':2,'meaning':'invalid-or-unreadable-bundle'}}));return 2
if __name__=='__main__':raise SystemExit(main())
